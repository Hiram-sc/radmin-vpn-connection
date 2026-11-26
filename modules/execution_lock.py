"""Proteção de execução da automação.

Um único desktop pode ser controlado por um único job por vez. O controle
é feito com um mutex nomeado do Windows, o que vale entre threads,
sessões do navegador e processos distintos na mesma sessão Windows.

Por que um mutex nomeado e não um threading.Lock:

- o lock de Python só protege o processo atual; duas instâncias do
  Streamlit (porta 8501 e porta 443, por exemplo) não se enxergariam;
- o mutex nomeado é liberado pelo sistema operacional quando o processo
  termina, então não existe lock órfão após uma queda;
- o nome pode ser derivado do recurso, permitindo que o mesmo mecanismo
  proteja, no futuro, um agente por máquina em vez de um desktop único.

Limitações conhecidas (documentadas, não resolvidas aqui):

- o mutex pertence a uma thread; por isso ele é mantido por uma thread
  dedicada que permanece viva enquanto o turno estiver aberto;
- o turno expira por TTL caso o usuário abandonar o fluxo;
- um job travado mantém o turno até o TTL expirar, porque Python não
  permite encerrar uma thread à força.
"""

import ctypes
import os
import sys
import threading
import time


RECURSO_PADRAO = "console@" + os.environ.get(
    "COMPUTERNAME",
    "desconhecido"
).upper()

_PREFIXO_MUTEX = "Local\\automacao-radmin:"

TTL_PADRAO = 600.0
_INTERVALO_RENOVACAO = 1.0

_WAIT_OBJECT_0 = 0x00000000
_WAIT_ABANDONED = 0x00000080


class ExecucaoEmAndamento(RuntimeError):
    """O recurso de execução já está em uso por outro job."""


def nome_do_mutex(recurso):

    seguro = "".join(
        caractere
        if (caractere.isalnum() or caractere in "-_.@:")
        else "_"
        for caractere in recurso
    )

    return _PREFIXO_MUTEX + seguro


# ==========================================
# API DO WINDOWS
# ==========================================

_KERNEL32 = None


def _kernel32():

    global _KERNEL32

    if _KERNEL32 is not None:

        return _KERNEL32

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CreateMutexW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_bool,
        ctypes.c_wchar_p
    ]

    kernel32.WaitForSingleObject.restype = ctypes.c_uint32
    kernel32.WaitForSingleObject.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32
    ]

    kernel32.ReleaseMutex.restype = ctypes.c_bool
    kernel32.ReleaseMutex.argtypes = [ctypes.c_void_p]

    kernel32.CloseHandle.restype = ctypes.c_bool
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]

    _KERNEL32 = kernel32

    return kernel32


def _adquirir_handle_windows(nome):

    kernel32 = _kernel32()

    handle = kernel32.CreateMutexW(None, False, nome)

    if not handle:

        return None

    resultado = kernel32.WaitForSingleObject(handle, 0)

    if resultado in (_WAIT_OBJECT_0, _WAIT_ABANDONED):

        return handle

    kernel32.CloseHandle(handle)

    return None


def _liberar_handle_windows(handle):

    kernel32 = _kernel32()

    kernel32.ReleaseMutex(handle)
    kernel32.CloseHandle(handle)


# ==========================================
# FALLBACK (SISTEMAS SEM MUTEX NOMEADO)
# ==========================================

_FALLBACK_LOCKS = {}
_FALLBACK_GUARD = threading.Lock()


def _adquirir_handle_fallback(nome):

    with _FALLBACK_GUARD:

        trava = _FALLBACK_LOCKS.setdefault(nome, threading.Lock())

    if trava.acquire(blocking=False):

        return trava

    return None


# ==========================================
# MUTEX NOMEADO
# ==========================================

class MutexNomeado:

    def __init__(self, recurso=RECURSO_PADRAO, ttl=TTL_PADRAO):

        self.recurso = recurso
        self.nome = nome_do_mutex(recurso)
        self.ttl = float(ttl)

        self._thread = None
        self._handle = None

        self._evento_liberar = threading.Event()
        self._evento_resultado = threading.Event()

        self._resultado = False
        self._prazo = 0.0
        self._expirou = False

    @property
    def ativo(self):

        return (
            self._thread is not None
            and self._thread.is_alive()
            and not self._expirou
        )

    def adquirir(self, timeout=5.0):

        if self.ativo:

            return True

        if self._thread is not None:

            self.liberar()

        self._evento_liberar.clear()
        self._evento_resultado.clear()

        self._resultado = False
        self._expirou = False
        self._prazo = time.monotonic() + self.ttl

        self._thread = threading.Thread(
            target=self._manter,
            name=f"mutex-{self.recurso}",
            daemon=True
        )

        self._thread.start()

        if not self._evento_resultado.wait(timeout):

            return False

        return self._resultado

    def renovar(self):

        if not self.ativo:

            return False

        self._prazo = time.monotonic() + self.ttl

        return True

    def liberar(self, timeout=5.0):

        thread = self._thread

        if thread is None:

            return

        self._evento_liberar.set()
        thread.join(timeout)

        self._thread = None
        self._handle = None

    def _manter(self):

        try:

            if sys.platform == "win32":

                handle = _adquirir_handle_windows(self.nome)

            else:

                handle = _adquirir_handle_fallback(self.nome)

        except Exception:

            handle = None

        if handle is None:

            self._resultado = False
            self._evento_resultado.set()

            return

        self._handle = handle
        self._resultado = True

        self._evento_resultado.set()

        try:

            while not self._evento_liberar.is_set():

                restante = self._prazo - time.monotonic()

                if restante <= 0:

                    self._expirou = True

                    break

                self._evento_liberar.wait(
                    min(_INTERVALO_RENOVACAO, restante)
                )

        finally:

            try:

                if sys.platform == "win32":

                    _liberar_handle_windows(handle)

                else:

                    handle.release()

            except Exception:

                pass


# ==========================================
# TURNOS (REGISTRO POR RECURSO)
# ==========================================

_TURNOS = {}
_TURNOS_GUARD = threading.Lock()


def abrir_turno(recurso=RECURSO_PADRAO, ttl=TTL_PADRAO):
    """Abre (ou renova) o turno de execução do recurso.

    Retorna True quando o turno é do processo atual e False quando outro
    processo/sessão detém o recurso.
    """

    with _TURNOS_GUARD:

        mutex = _TURNOS.get(recurso)

        if mutex is not None and mutex.ativo:

            mutex.renovar()

            return True

        if mutex is not None:

            _TURNOS.pop(recurso, None)
            mutex.liberar()

        novo = MutexNomeado(recurso, ttl=ttl)

        if not novo.adquirir():

            return False

        _TURNOS[recurso] = novo

        return True


def fechar_turno(recurso=RECURSO_PADRAO):

    with _TURNOS_GUARD:

        mutex = _TURNOS.pop(recurso, None)

    if mutex is not None:

        mutex.liberar()


def turno_ativo(recurso=RECURSO_PADRAO):

    with _TURNOS_GUARD:

        mutex = _TURNOS.get(recurso)

        if mutex is None:

            return False

        if mutex.ativo:

            return True

        _TURNOS.pop(recurso, None)

    mutex.liberar()

    return False
