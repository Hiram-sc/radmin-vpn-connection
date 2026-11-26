
import os
import time

from pathlib import Path

import pyautogui
import pyperclip

from pywinauto import Desktop


# ==========================================
# MENSAGENS DE ERRO DO RADMIN
# ==========================================

PALAVRAS_ERRO = (
    "incorreta",
    "incorreto",
    "inválid",
    "invalid",
    "falha",
    "erro",
    "error",
    "não foi possível",
    "nao foi possivel",
    "negado",
    "denied"
)

# Rótulos fixos da interface: não são mensagens de erro.
TEXTOS_IGNORADOS = {
    "radmin vpn",
    "conectar à rede",
    "conectar a rede",
    "nome da rede",
    "nome da rede:",
    "senha",
    "senha:",
    "cancelar",
    "entrar",
    "online",
    "offline"
}

# Controles que carregam entrada do usuário, não avisos.
TIPOS_SEM_TEXTO_DE_ERRO = {
    "Edit",
    "Document",
    "Button",
    "MenuItem",
    "TabItem",
    "Tab"
}


class RadminAutomation:

    def __init__(self):

        self.desktop = Desktop(backend="uia")

        self.janela = None
        self.formulario = None

        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.3

    # ==========================================
    # LOCALIZAR JANELA PRINCIPAL
    # ==========================================

    def localizar_janela(self):

        janelas = self.desktop.windows(
            title="Radmin VPN",
            visible_only=True
        )

        for janela in janelas:

            try:

                if (
                    janela.element_info.class_name
                    == "CMainWnd"
                ):

                    self.janela = janela
                    return True

            except Exception:
                continue

        self.janela = None

        return False

    # ==========================================
    # LISTAR REDES EXISTENTES
    # ==========================================

    def listar_redes(self):

        if self.janela is None:

            if not self.localizar_janela():

                raise RuntimeError(
                    "Janela principal do Radmin não localizada."
                )

        redes = set()

        for elemento in self.janela.descendants():

            try:

                nome = elemento.window_text().strip()

                if not nome:
                    continue

                classe = elemento.element_info.class_name

                if classe == "QElideLabel":

                    if nome.casefold() not in {
                        "online",
                        "offline"
                    }:

                        redes.add(nome)

            except Exception:
                continue

        return sorted(
            redes,
            key=str.casefold
        )

    # ==========================================
    # LOCALIZAR ELEMENTO PELO TEXTO
    # ==========================================

    def localizar_elemento(self, nome, tipo=None):

        if self.janela is None:

            raise RuntimeError(
                "Janela principal não localizada."
            )

        for elemento in self.janela.descendants():

            try:

                texto = elemento.window_text().strip()

                if texto != nome:
                    continue

                if tipo is not None:

                    if (
                        elemento.element_info.control_type
                        != tipo
                    ):
                        continue

                return elemento

            except Exception:
                continue

        return None

    # ==========================================
    # LOCALIZAR FORMULÁRIO
    # ==========================================

    def localizar_formulario(self):

        if self.janela is None:

            self.localizar_janela()

        # Nesta versão o formulário é um diálogo filho
        # da janela principal (CDlgJoinNetwork), e não
        # uma janela top-level.

        if self.janela is not None:

            dialogos = []

            for elemento in self.janela.descendants():

                try:

                    info = elemento.element_info

                    classe = info.class_name

                    automation_id = (
                        info.automation_id or ""
                    )

                    if (
                        classe == "CDlgJoinNetwork"
                        or automation_id.endswith(
                            "DlgJoinNetwork"
                        )
                    ):

                        dialogos.append(elemento)

                except Exception:

                    continue

            if len(dialogos) > 1:

                self.formulario = None

                raise RuntimeError(
                    "Mais de um formulário candidato foi encontrado."
                )

            if len(dialogos) == 1:

                self.formulario = dialogos[0]

                return True

        # Fallback: versões em que o formulário é
        # uma janela top-level.

        candidatos = []

        janelas = self.desktop.windows(
            visible_only=True
        )

        for janela in janelas:

            try:

                if janela.window_text().strip() != "Radmin VPN":
                    continue

                if (
                    janela.element_info.class_name
                    != "Qt51515QWindowIcon"
                ):
                    continue

                retangulo = janela.rectangle()

                largura = retangulo.width()
                altura = retangulo.height()

                if (
                    300 <= largura <= 450
                    and 180 <= altura <= 280
                ):

                    candidatos.append(janela)

            except Exception:
                continue

        if len(candidatos) != 1:

            self.formulario = None

            if len(candidatos) > 1:

                raise RuntimeError(
                    "Mais de um formulário candidato foi encontrado."
                )

            return False

        self.formulario = candidatos[0]

        return True

    # ==========================================
    # ABRIR FORMULÁRIO
    # ==========================================

    def abrir_formulario_rede(self):

        if not self.localizar_janela():

            raise RuntimeError(
                "Radmin VPN não está aberto."
            )

        if self.localizar_formulario():

            return True

        self.janela.set_focus()

        menu = self.localizar_elemento(
            "Rede",
            "MenuItem"
        )

        if menu is None:

            raise RuntimeError(
                "Menu Rede não encontrado."
            )

        menu.click_input()

        time.sleep(1)

        opcao = self.localizar_elemento(
            "Conectar à rede",
            "MenuItem"
        )

        if opcao is None:

            raise RuntimeError(
                "Opção Conectar à rede não encontrada."
            )

        opcao.click_input()

        time.sleep(2)

        if not self.localizar_formulario():

            raise RuntimeError(
                "Formulário de entrada não localizado."
            )

        return True

    # ==========================================
    # PREPARAR ENTRADA
    # ==========================================

    def preparar_entrada(self):

        print("Preparando Radmin VPN...")

        if not self.localizar_janela():

            raise RuntimeError(
                "Radmin VPN não está aberto."
            )

        self.abrir_formulario_rede()

        return {
            "sucesso": True,
            "mensagem": "Formulário localizado."
        }

    # ==========================================
    # PREENCHER FORMULÁRIO
    # ==========================================

    def preencher_formulario(self, nome, senha):

        if not nome or not senha:

            raise ValueError(
                "Nome e senha são obrigatórios."
            )

        if not self.localizar_formulario():

            raise RuntimeError(
                "Formulário de entrada não encontrado."
            )

        retangulo = self.formulario.rectangle()

        esquerda = retangulo.left
        topo = retangulo.top

        self.formulario.set_focus()

        # Coordenadas relativas identificadas
        # durante os testes visuais.

        campo_rede = (80, 37)
        campo_senha = (50, 115)

        elemento_rede = self._localizar_elemento_formulario(
            "LENetName",
            "Edit"
        )

        elemento_senha = self._localizar_elemento_formulario(
            "LEPassword",
            "Edit"
        )

        try:

            # Campo da rede
            if elemento_rede is not None:

                valor_rede = self._preencher_elemento(
                    elemento_rede,
                    nome
                )

            else:

                valor_rede = self._preencher_campo(
                    esquerda + campo_rede[0],
                    topo + campo_rede[1],
                    nome
                )

            # Campo da senha
            if elemento_senha is not None:

                valor_senha = self._preencher_elemento(
                    elemento_senha,
                    senha
                )

            else:

                valor_senha = self._preencher_campo(
                    esquerda + campo_senha[0],
                    topo + campo_senha[1],
                    senha
                )

        finally:

            pyperclip.copy("")

        if valor_rede is not None and valor_rede != str(nome):

            raise RuntimeError(
                "O campo de rede não recebeu o nome esperado."
            )

        if valor_senha is not None and valor_senha != str(senha):

            raise RuntimeError(
                "O campo de senha não recebeu a senha esperada."
            )

        campos_validados = (
            valor_rede is not None
            and valor_senha is not None
        )

        return {
            "sucesso": True,
            "campos_validados": campos_validados,
            "mensagem": "Campos preenchidos."
        }

    # ==========================================
    # PREENCHER E RELER UM CAMPO
    # ==========================================

    def _preencher_campo(self, x, y, valor):
        """Preenche um campo e tenta reler o conteúdo.

        Retorna o texto relido ou None quando a leitura
        não é possível (por exemplo, campo protegido).
        """

        pyautogui.click(x, y)

        pyautogui.hotkey("ctrl", "a")

        pyperclip.copy(str(valor))

        pyautogui.hotkey("ctrl", "v")

        time.sleep(0.5)

        marcador = "__radmin_verificacao__"

        try:

            pyperclip.copy(marcador)

            pyautogui.hotkey("ctrl", "a")

            pyautogui.hotkey("ctrl", "c")

            time.sleep(0.1)

            lido = pyperclip.paste()

        except Exception:

            return None

        if lido is None or lido == marcador:

            return None

        return lido

    # ==========================================
    # LOCALIZAR CAMPO PELO AUTOMATION ID
    # ==========================================

    def _localizar_elemento_formulario(
        self,
        sufixo,
        tipo=None
    ):

        if self.formulario is None:

            return None

        for elemento in self.formulario.descendants():

            try:

                info = elemento.element_info

                automation_id = (
                    info.automation_id or ""
                )

                if not automation_id.endswith(sufixo):

                    continue

                if (
                    tipo is not None
                    and info.control_type != tipo
                ):

                    continue

                return elemento

            except Exception:

                continue

        return None

    # ==========================================
    # PREENCHER E RELER UM ELEMENTO
    # ==========================================

    def _preencher_elemento(self, elemento, valor):
        """Preenche o controle identificado e tenta reler.

        Retorna o texto relido ou None quando a leitura
        não é possível (por exemplo, campo protegido).
        """

        try:

            elemento.set_focus()

        except Exception:

            retangulo = elemento.rectangle()

            pyautogui.click(
                retangulo.left + retangulo.width() // 2,
                retangulo.top + retangulo.height() // 2
            )

        pyautogui.hotkey("ctrl", "a")

        pyperclip.copy(str(valor))

        pyautogui.hotkey("ctrl", "v")

        time.sleep(0.5)

        marcador = "__radmin_verificacao__"

        try:

            pyperclip.copy(marcador)

            pyautogui.hotkey("ctrl", "a")

            pyautogui.hotkey("ctrl", "c")

            time.sleep(0.1)

            lido = pyperclip.paste()

        except Exception:

            return None

        if lido is None or lido == marcador:

            return None

        return lido

    # ==========================================
    # ENVIAR SOLICITAÇÃO
    # ==========================================

    def confirmar_entrada(self):

        if not self.localizar_formulario():

            raise RuntimeError(
                "Formulário não encontrado para confirmação."
            )

        self.formulario.set_focus()

        botao = self._localizar_elemento_formulario(
            "joinPushButton",
            "Button"
        )

        if botao is not None:

            botao.click_input()

        else:

            # Fallback para versões sem o botão identificado.

            pyautogui.press("enter")

        time.sleep(3)

        return {
            "sucesso": True,
            "mensagem": (
                "Solicitação enviada. "
                "É necessário verificar o resultado no Radmin."
            )
        }

    # ==========================================
    # VERIFICAR REDES DA PLANILHA
    # ==========================================

    def verificar_redes(self, registros):

        redes_radmin = self.listar_redes()

        indice = {
            nome.casefold(): nome
            for nome in redes_radmin
        }

        resultados = []

        for registro in registros:

            nome = registro["nome"]

            encontrada = nome.casefold() in indice

            resultados.append({

                "nome": nome,

                "encontrada": encontrada,

                "nome_radmin": indice.get(
                    nome.casefold()
                )

            })

        return resultados

    # ==========================================
    # ABRIR OU LOCALIZAR O RADMIN
    # ==========================================

    def garantir_radmin_aberto(self):

        if not self.localizar_janela():

            raise RuntimeError(
                "Radmin VPN não está aberto. "
                "Abra o Radmin VPN manualmente "
                "e tente novamente."
            )

        return {
            "sucesso": True,
            "mensagem": "Radmin VPN localizado."
        }

    # ==========================================
    # DETECTAR MENSAGENS DE ERRO
    # ==========================================

    def detectar_erro(self):
        """Procura mensagens de erro apenas nas janelas de diálogo.

        A janela principal é ignorada de propósito: ela contém rótulos
        fixos que podem conter palavras como "inválido" sem que exista
        erro algum, o que gerava falso positivo.
        """

        for origem in self._origens_de_erro():

            for texto in self._textos_de_erro(origem):

                minusculo = texto.casefold()

                if any(
                    palavra in minusculo
                    for palavra in PALAVRAS_ERRO
                ):

                    return texto

        return None

    # ==========================================
    # ORIGENS VÁLIDAS PARA MENSAGEM DE ERRO
    # ==========================================

    def _origens_de_erro(self):

        origens = []

        try:

            if self.formulario is None:

                self.localizar_formulario()

        except Exception:

            pass

        if self.formulario is not None:

            origens.append(self.formulario)

        try:

            janelas = self.desktop.windows(visible_only=True)

        except Exception:

            janelas = []

        for janela in janelas:

            try:

                titulo = (janela.window_text() or "").casefold()

                classe = janela.element_info.class_name

            except Exception:

                continue

            if "radmin" not in titulo:

                continue

            # A janela principal só exibe rótulos de rede.
            if classe == "CMainWnd":

                continue

            if janela is self.formulario:

                continue

            origens.append(janela)

        return origens

    # ==========================================
    # TEXTOS CANDIDATOS A MENSAGEM DE ERRO
    # ==========================================

    def _textos_de_erro(self, origem):

        for elemento in origem.descendants():

            try:

                info = elemento.element_info

                if info.control_type in TIPOS_SEM_TEXTO_DE_ERRO:

                    continue

                texto = (elemento.window_text() or "").strip()

            except Exception:

                continue

            if not texto or len(texto) > 300:

                continue

            if texto.casefold() in TEXTOS_IGNORADOS:

                continue

            yield texto

    # ==========================================
    # OBTER STATUS DAS REDES (ONLINE/OFFLINE)
    # ==========================================

    def obter_status_redes(self):
        """Associa nomes e status pela hierarquia de controles.

        Não utiliza posição de elementos. Quando a associação
        não é inequívoca, o status é omitido.
        """

        redes = self.listar_redes()

        if not redes:

            return {}

        if self.janela is None and not self.localizar_janela():

            return {}

        status = {}

        for elemento in self.janela.descendants():

            try:

                texto = elemento.window_text().strip()

            except Exception:

                continue

            minusculo = texto.casefold()

            if minusculo not in {"online", "offline"}:

                continue

            valor = "Online" if minusculo == "online" else "Offline"

            no = elemento

            for _ in range(4):

                try:

                    no = no.parent()

                except Exception:

                    break

                if no is None:

                    break

                try:

                    if no.element_info.class_name == "CMainWnd":

                        break

                    textos = {
                        descendente.window_text().strip()
                        for descendente in no.descendants()
                    }

                except Exception:

                    continue

                encontrados = [
                    rede
                    for rede in redes
                    if rede in textos
                ]

                if len(encontrados) == 1:

                    status[encontrados[0]] = valor
                    break

        return status

    # ==========================================
    # AGUARDAR CONFIRMAÇÃO DA CONEXÃO
    # ==========================================

    def aguardar_conexao(self, nome, timeout=20):

        limite = time.time() + timeout

        ultimo_status = None

        while time.time() < limite:

            erro = self.detectar_erro()

            if erro:

                return {
                    "sucesso": False,
                    "estado": "falha",
                    "mensagem": erro
                }

            status = {
                chave.casefold(): valor
                for chave, valor in self.obter_status_redes().items()
            }

            ultimo_status = status.get(nome.casefold())

            if ultimo_status == "Online":

                return {
                    "sucesso": True,
                    "estado": "conectado",
                    "mensagem": f"Conexão confirmada para {nome}."
                }

            time.sleep(1)

        if ultimo_status == "Offline":

            return {
                "sucesso": False,
                "estado": "offline",
                "mensagem": f"A rede {nome} permanece offline."
            }

        return {
            "sucesso": False,
            "estado": "indeterminado",
            "mensagem": (
                "Não foi possível confirmar o estado "
                "da conexão."
            )
        }

    # ==========================================
    # CONECTAR UMA REDE (FLUXO COMPLETO)
    # ==========================================

    def conectar_rede(self, nome, senha, timeout=20):

        try:

            if not nome or not senha:

                raise ValueError(
                    "Nome e senha são obrigatórios."
                )

            self.garantir_radmin_aberto()

            status_inicial = {
                chave.casefold(): valor
                for chave, valor in self.obter_status_redes().items()
            }

            if status_inicial.get(nome.casefold()) == "Online":

                return {
                    "nome": nome,
                    "sucesso": True,
                    "estado": "ja_conectada",
                    "mensagem": (
                        f"A rede {nome} já estava conectada."
                    ),
                    "campos_validados": None
                }

            self.preparar_entrada()

            preenchimento = self.preencher_formulario(
                nome,
                senha
            )

            self.confirmar_entrada()

            verificacao = self.aguardar_conexao(
                nome,
                timeout=timeout
            )

            return {
                "nome": nome,
                "sucesso": verificacao["sucesso"],
                "estado": verificacao["estado"],
                "mensagem": verificacao["mensagem"],
                "campos_validados": preenchimento.get(
                    "campos_validados"
                )
            }

        except Exception as erro:

            return {
                "nome": nome,
                "sucesso": False,
                "estado": "falha",
                "mensagem": str(erro),
                "campos_validados": None
            }


def processar_lote(automacao, registros, ao_processar=None):

    resultados = []

    total = len(registros)

    for posicao, registro in enumerate(registros, start=1):

        if ao_processar is not None:

            ao_processar(posicao, total, registro)

        try:

            resultado = automacao.conectar_rede(
                registro["nome"],
                registro["senha"]
            )

        except Exception as erro:

            resultado = {
                "nome": registro["nome"],
                "sucesso": False,
                "estado": "falha",
                "mensagem": str(erro)
            }

        resultados.append({

            "linha": registro.get("linha"),

            "nome": registro["nome"],

            "sucesso": bool(resultado.get("sucesso")),

            "estado": resultado.get(
                "estado",
                "indeterminado"
            ),

            "mensagem": resultado.get("mensagem", ""),

            "campos_validados": resultado.get(
                "campos_validados"
            )

        })

    return resultados
