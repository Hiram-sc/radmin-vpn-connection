"""Fase 0.5 — turno de execução exclusivo, inclusive entre processos."""

import os
import subprocess
import sys
import time
import unittest

from pathlib import Path
from uuid import uuid4

from modules.execution_lock import (
    MutexNomeado,
    abrir_turno,
    fechar_turno,
    nome_do_mutex,
    turno_ativo
)


RAIZ = Path(__file__).resolve().parents[1]


def recurso_novo(rotulo):

    return f"teste-{rotulo}:{os.getpid()}:{uuid4().hex[:8]}"


def rodar_filho(script, recurso, timeout=30):
    """Executa um processo Python separado e devolve (saida, codigo)."""

    processo = subprocess.run(
        [sys.executable, "-c", script, recurso],
        cwd=str(RAIZ),
        capture_output=True,
        text=True,
        timeout=timeout
    )

    return processo.stdout.strip(), processo.returncode


TENTAR = (
    "import sys\n"
    "from modules.execution_lock import abrir_turno, fechar_turno\n"
    "recurso = sys.argv[1]\n"
    "if abrir_turno(recurso):\n"
    "    print('ADQUIRIDO', flush=True)\n"
    "    fechar_turno(recurso)\n"
    "else:\n"
    "    print('BLOQUEADO', flush=True)\n"
)

SEGURAR = (
    "import sys, time\n"
    "from modules.execution_lock import abrir_turno\n"
    "recurso = sys.argv[1]\n"
    "if abrir_turno(recurso):\n"
    "    print('ADQUIRIDO', flush=True)\n"
    "    time.sleep(60)\n"
    "else:\n"
    "    print('BLOQUEADO', flush=True)\n"
)


class TestNomeDoMutex(unittest.TestCase):

    def test_nome_deriva_do_recurso(self):

        self.assertEqual(
            nome_do_mutex("console@PC"),
            "Local\\automacao-radmin:console@PC"
        )

    def test_caracteres_inseguros_sao_substituidos(self):

        nome = nome_do_mutex("a b\\c/d")

        self.assertEqual(nome, "Local\\automacao-radmin:a_b_c_d")


class TestMutexNomeado(unittest.TestCase):

    def test_segundo_mutex_do_mesmo_recurso_falha(self):

        recurso = recurso_novo("mutex")
        primeiro = MutexNomeado(recurso)
        segundo = MutexNomeado(recurso)

        try:

            self.assertTrue(primeiro.adquirir())
            self.assertFalse(segundo.adquirir())

        finally:

            primeiro.liberar()
            segundo.liberar()

    def test_recurso_liberado_pode_ser_readquirido(self):

        recurso = recurso_novo("mutex")
        primeiro = MutexNomeado(recurso)
        segundo = MutexNomeado(recurso)

        try:

            self.assertTrue(primeiro.adquirir())
            primeiro.liberar()

            self.assertTrue(segundo.adquirir())

        finally:

            primeiro.liberar()
            segundo.liberar()

    def test_expira_por_ttl(self):

        recurso = recurso_novo("ttl")
        curto = MutexNomeado(recurso, ttl=0.2)
        novo = MutexNomeado(recurso)

        try:

            self.assertTrue(curto.adquirir())

            time.sleep(0.6)

            self.assertFalse(curto.ativo)
            self.assertTrue(novo.adquirir())

        finally:

            curto.liberar()
            novo.liberar()


class TestTurnos(unittest.TestCase):

    def test_abrir_turno_e_idempotente(self):

        recurso = recurso_novo("turno")

        try:

            self.assertTrue(abrir_turno(recurso))
            self.assertTrue(turno_ativo(recurso))
            self.assertTrue(abrir_turno(recurso))
            self.assertTrue(turno_ativo(recurso))

        finally:

            fechar_turno(recurso)

    def test_fechar_turno_desativa(self):

        recurso = recurso_novo("turno")

        self.assertTrue(abrir_turno(recurso))

        fechar_turno(recurso)

        self.assertFalse(turno_ativo(recurso))

    def test_segundo_processo_e_bloqueado(self):

        recurso = recurso_novo("processo")

        try:

            self.assertTrue(abrir_turno(recurso))

            saida, codigo = rodar_filho(TENTAR, recurso)

            self.assertEqual(codigo, 0)
            self.assertEqual(saida, "BLOQUEADO")

        finally:

            fechar_turno(recurso)

    def test_novo_processo_adquire_apos_liberacao(self):

        recurso = recurso_novo("processo")

        self.assertTrue(abrir_turno(recurso))
        fechar_turno(recurso)

        saida, codigo = rodar_filho(TENTAR, recurso)

        self.assertEqual(codigo, 0)
        self.assertEqual(saida, "ADQUIRIDO")

    def test_sem_lock_orfao_apos_processo_encerrado(self):

        recurso = recurso_novo("orfao")

        processo = subprocess.Popen(
            [sys.executable, "-c", SEGURAR, recurso],
            cwd=str(RAIZ),
            stdout=subprocess.PIPE,
            text=True
        )

        try:

            linha = processo.stdout.readline().strip()

            self.assertEqual(linha, "ADQUIRIDO")

            processo.terminate()
            processo.wait(timeout=15)

            self.assertIsNotNone(processo.returncode)

            # O Windows libera o mutex quando o processo encerra.
            self.assertTrue(abrir_turno(recurso))

        finally:

            if processo.poll() is None:

                processo.kill()
                processo.wait(timeout=15)

            if processo.stdout is not None:

                processo.stdout.close()

            fechar_turno(recurso)


if __name__ == "__main__":

    unittest.main()
