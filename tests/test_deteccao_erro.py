"""Fase 0.3 — detecção de mensagens de erro do Radmin.

A janela principal do Radmin contém rótulos fixos. A detecção deve olhar
apenas diálogos (e o formulário de conexão), ignorando a janela principal,
para não transformar um rótulo em falso positivo.
"""

import unittest

from modules.vpn_automation import RadminAutomation


# ==========================================
# AUXILIARES
# ==========================================

class InfoFalsa:

    def __init__(self, class_name="QWidget", control_type="Window"):

        self.class_name = class_name
        self.control_type = control_type


class ElementoFalso:

    def __init__(self, texto, control_type="Text", filhos=None):

        self._texto = texto
        self._filhos = filhos or []
        self.element_info = InfoFalsa(
            class_name="QLabel",
            control_type=control_type
        )

    def window_text(self):

        return self._texto

    def descendants(self):

        for filho in self._filhos:

            yield filho

            yield from filho.descendants()


class JanelaFalsa:

    def __init__(self, titulo, classe="QMessageBox", filhos=None):

        self._titulo = titulo
        self._filhos = filhos or []
        self.element_info = InfoFalsa(
            class_name=classe,
            control_type="Window"
        )

    def window_text(self):

        return self._titulo

    def descendants(self):

        for filho in self._filhos:

            yield filho

            yield from filho.descendants()


class DesktopFalso:

    def __init__(self, janelas):

        self._janelas = janelas

    def windows(self, visible_only=True):

        return list(self._janelas)


def criar_automacao(janelas, formulario=None):
    """Instância sem UIA, com Desktop e formulário controlados."""

    automacao = RadminAutomation.__new__(RadminAutomation)

    automacao.desktop = DesktopFalso(janelas)
    automacao.janela = None
    automacao.formulario = formulario

    # Evita que _origens_de_erro tente abrir a interface real.
    automacao.localizar_formulario = lambda: False

    return automacao


class TestDetectarErro(unittest.TestCase):

    def test_janela_principal_nao_gera_falso_positivo(self):

        # "inválida" apareceria num rótulo fixo da janela principal.
        janela = JanelaFalsa(
            "Radmin VPN",
            classe="CMainWnd",
            filhos=[ElementoFalso("Senha inválida")]
        )

        automacao = criar_automacao([janela])

        self.assertIsNone(automacao.detectar_erro())

    def test_janela_de_outro_programa_e_ignorada(self):

        janela = JanelaFalsa(
            "Outro programa",
            filhos=[ElementoFalso("Falha grave")]
        )

        automacao = criar_automacao([janela])

        self.assertIsNone(automacao.detectar_erro())

    def test_caixa_de_dialogo_e_detectada(self):

        janela = JanelaFalsa(
            "Radmin VPN",
            classe="QMessageBox",
            filhos=[ElementoFalso("Senha incorreta.")]
        )

        automacao = criar_automacao([janela])

        self.assertEqual(
            automacao.detectar_erro(),
            "Senha incorreta."
        )

    def test_campo_de_edicao_e_ignorado(self):

        janela = JanelaFalsa(
            "Radmin VPN",
            classe="QMessageBox",
            filhos=[
                ElementoFalso(
                    "erro de digitação",
                    control_type="Edit"
                )
            ]
        )

        automacao = criar_automacao([janela])

        self.assertIsNone(automacao.detectar_erro())

    def test_formulario_aberto_e_detectado(self):

        formulario = JanelaFalsa(
            "Radmin VPN",
            classe="QDialog",
            filhos=[ElementoFalso("Não foi possível conectar.")]
        )

        automacao = criar_automacao([], formulario=formulario)

        self.assertEqual(
            automacao.detectar_erro(),
            "Não foi possível conectar."
        )

    def test_texto_muito_longo_e_ignorado(self):

        janela = JanelaFalsa(
            "Radmin VPN",
            classe="QMessageBox",
            filhos=[ElementoFalso("erro " + "x" * 400)]
        )

        automacao = criar_automacao([janela])

        self.assertIsNone(automacao.detectar_erro())

    def test_rotulo_fixo_da_interface_e_ignorado(self):

        janela = JanelaFalsa(
            "Radmin VPN",
            classe="QMessageBox",
            filhos=[ElementoFalso("Senha:")]
        )

        automacao = criar_automacao([janela])

        self.assertIsNone(automacao.detectar_erro())

    def test_sem_janelas_retorna_none(self):

        automacao = criar_automacao([])

        self.assertIsNone(automacao.detectar_erro())

    def test_falha_ao_listar_janelas_retorna_none(self):

        class DesktopQuebrado:

            def windows(self, visible_only=True):

                raise RuntimeError("UIA indisponível")

        automacao = RadminAutomation.__new__(RadminAutomation)

        automacao.desktop = DesktopQuebrado()
        automacao.janela = None
        automacao.formulario = None
        automacao.localizar_formulario = lambda: False

        self.assertIsNone(automacao.detectar_erro())


if __name__ == "__main__":

    unittest.main()
