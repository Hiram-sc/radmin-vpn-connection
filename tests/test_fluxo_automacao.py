"""Testes isolados do fluxo de automação.

Estes testes usam mocks e não interagem com o Radmin VPN real.
Não comprovam o funcionamento da interface do Radmin.
"""

import io
import unittest

from unittest.mock import Mock, patch

import pandas as pd

from modules.spreadsheet import (
    carregar_planilha,
    montar_registros
)
from modules.validation import validar_registros
from modules.vpn_automation import (
    RadminAutomation,
    processar_lote
)


# ==========================================
# AUXILIARES
# ==========================================

OFFSET_CAMPO_REDE = (80, 37)
OFFSET_CAMPO_SENHA = (50, 115)


def criar_automacao_sem_interface():
    """Cria a instância sem inicializar o Desktop/UIA."""

    return RadminAutomation.__new__(RadminAutomation)


class InfoFalsa:

    def __init__(
        self,
        class_name="QWidget",
        automation_id="",
        control_type="Window"
    ):

        self.class_name = class_name
        self.automation_id = automation_id
        self.control_type = control_type


class RetanguloFalso:

    def __init__(self, left=0, top=0, largura=100, altura=20):

        self.left = left
        self.top = top
        self._largura = largura
        self._altura = altura

    def width(self):

        return self._largura

    def height(self):

        return self._altura


class ElementoFalso:

    def __init__(
        self,
        texto,
        pai=None,
        class_name="QWidget",
        filhos=None,
        automation_id="",
        control_type="Window",
        retangulo=None
    ):

        self._texto = texto
        self._pai = pai
        self._filhos = filhos or []

        self.element_info = InfoFalsa(
            class_name,
            automation_id,
            control_type
        )

        self._retangulo = retangulo or RetanguloFalso()

        self.focado = False
        self.clicado = False

    def window_text(self):

        return self._texto

    def parent(self):

        return self._pai

    def rectangle(self):

        return self._retangulo

    def set_focus(self):

        self.focado = True

    def click_input(self):

        self.clicado = True

    def descendants(self):

        for filho in self._filhos:

            yield filho

            yield from filho.descendants()


# ==========================================
# PLANILHA E REGISTROS
# ==========================================

class TestRegistros(unittest.TestCase):

    def test_associa_nome_senha_e_linha(self):

        dataframe = pd.DataFrame({
            "Nome": ["Rede A", "Rede B"],
            "Senha": ["senha-a", "senha-b"]
        })

        registros = montar_registros(dataframe)

        self.assertEqual(registros, [
            {"nome": "Rede A", "senha": "senha-a", "linha": 2},
            {"nome": "Rede B", "senha": "senha-b", "linha": 3}
        ])

    def test_exige_colunas_obrigatorias(self):

        with self.assertRaises(ValueError):

            montar_registros(pd.DataFrame({
                "Nome": ["Rede A"]
            }))

    def test_carregar_planilha_normaliza_valores(self):

        dataframe = pd.DataFrame({
            "Nome": ["  Rede A  "],
            "Senha": [12345]
        })

        buffer = io.BytesIO()

        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:

            dataframe.to_excel(writer, index=False)

        buffer.seek(0)

        carregado = carregar_planilha(buffer)

        self.assertEqual(carregado.iloc[0]["Nome"], "Rede A")
        self.assertEqual(carregado.iloc[0]["Senha"], "12345")


# ==========================================
# VALIDAÇÃO
# ==========================================

class TestValidacao(unittest.TestCase):

    def test_registros_validos(self):

        validos, erros = validar_registros([
            {"nome": "Rede A", "senha": "s1", "linha": 2},
            {"nome": "Rede B", "senha": "s2", "linha": 3}
        ])

        self.assertEqual(len(validos), 2)
        self.assertEqual(erros, [])

    def test_vazio_e_duplicado(self):

        validos, erros = validar_registros([
            {"nome": "", "senha": "s1", "linha": 2},
            {"nome": "Rede A", "senha": "", "linha": 3},
            {"nome": "Rede A", "senha": "s2", "linha": 4},
            {"nome": "rede a", "senha": "s3", "linha": 5},
            {"nome": "Rede B", "senha": "s4", "linha": 6}
        ])

        self.assertEqual(len(validos), 2)
        self.assertEqual(len(erros), 3)

    def test_normaliza_espacos(self):

        validos, erros = validar_registros([
            {"nome": "  Rede A  ", "senha": "  s1  ", "linha": 2}
        ])

        self.assertEqual(erros, [])
        self.assertEqual(validos[0]["nome"], "Rede A")
        self.assertEqual(validos[0]["senha"], "s1")


# ==========================================
# FORMULÁRIO (DIÁLOGO FILHO)
# ==========================================

class TestLocalizarFormulario(unittest.TestCase):

    def test_encontra_dialogo_filho_por_classe(self):

        automacao = criar_automacao_sem_interface()

        dialogo = ElementoFalso(
            "Radmin VPN",
            class_name="CDlgJoinNetwork",
            automation_id="MainWindow.DlgJoinNetwork",
            control_type="Window"
        )

        automacao.janela = ElementoFalso(
            "Radmin VPN",
            class_name="CMainWnd",
            filhos=[dialogo]
        )

        self.assertTrue(automacao.localizar_formulario())
        self.assertIs(automacao.formulario, dialogo)

    def test_encontra_dialogo_filho_por_automation_id(self):

        automacao = criar_automacao_sem_interface()

        dialogo = ElementoFalso(
            "Radmin VPN",
            class_name="QWidget",
            automation_id="MainWindow.DlgJoinNetwork",
            control_type="Window"
        )

        automacao.janela = ElementoFalso(
            "Radmin VPN",
            class_name="CMainWnd",
            filhos=[dialogo]
        )

        self.assertTrue(automacao.localizar_formulario())
        self.assertIs(automacao.formulario, dialogo)

    def test_erro_com_dois_dialogos(self):

        automacao = criar_automacao_sem_interface()

        automacao.janela = ElementoFalso(
            "Radmin VPN",
            class_name="CMainWnd",
            filhos=[
                ElementoFalso(
                    "Radmin VPN",
                    class_name="CDlgJoinNetwork"
                ),
                ElementoFalso(
                    "Radmin VPN",
                    class_name="CDlgJoinNetwork"
                )
            ]
        )

        with self.assertRaises(RuntimeError):

            automacao.localizar_formulario()

    def test_fallback_janela_toplevel(self):

        automacao = criar_automacao_sem_interface()

        automacao.janela = ElementoFalso(
            "Radmin VPN",
            class_name="CMainWnd"
        )

        top_level = ElementoFalso(
            "Radmin VPN",
            class_name="Qt51515QWindowIcon",
            retangulo=RetanguloFalso(0, 0, 360, 228)
        )

        automacao.desktop = Mock()
        automacao.desktop.windows = Mock(
            return_value=[top_level]
        )

        self.assertTrue(automacao.localizar_formulario())
        self.assertIs(automacao.formulario, top_level)


class TestPreencherFormulario(unittest.TestCase):

    def _montar_automacao(self, filhos, retangulo=None):

        automacao = criar_automacao_sem_interface()

        dialogo = ElementoFalso(
            "Radmin VPN",
            class_name="CDlgJoinNetwork",
            filhos=filhos,
            retangulo=retangulo
        )

        automacao.formulario = dialogo
        automacao.localizar_formulario = Mock(return_value=True)

        return automacao

    def test_usa_automation_ids_dos_campos(self):

        campo_rede = ElementoFalso(
            "",
            automation_id=(
                "MainWindow.DlgJoinNetwork.tab_private.LENetName"
            ),
            control_type="Edit"
        )

        campo_senha = ElementoFalso(
            "",
            automation_id=(
                "MainWindow.DlgJoinNetwork.tab_private.LEPassword"
            ),
            control_type="Edit"
        )

        automacao = self._montar_automacao(
            [campo_rede, campo_senha]
        )

        preenchidos = []

        def preencher(elemento, valor):

            preenchidos.append((elemento, valor))

            return valor

        automacao._preencher_elemento = preencher
        automacao._preencher_campo = Mock(
            side_effect=AssertionError(
                "As coordenadas não devem ser usadas."
            )
        )

        with patch(
            "modules.vpn_automation.pyperclip.copy"
        ) as copiar:
            resultado = automacao.preencher_formulario(
                "Rede A",
                "senha-a"
            )

        copiar.assert_called_once_with("")

        self.assertTrue(resultado["campos_validados"])

        self.assertEqual(
            [valor for _, valor in preenchidos],
            ["Rede A", "senha-a"]
        )

        self.assertIs(preenchidos[0][0], campo_rede)
        self.assertIs(preenchidos[1][0], campo_senha)

        automacao._preencher_campo.assert_not_called()

    def test_fallback_por_coordenadas_sem_campos(self):

        retangulo = RetanguloFalso(10, 20, 360, 228)

        automacao = self._montar_automacao(
            [],
            retangulo=retangulo
        )

        automacao._preencher_elemento = Mock(
            side_effect=AssertionError(
                "O elemento não deveria ser usado."
            )
        )
        automacao._preencher_campo = Mock(
            side_effect=lambda x, y, valor: valor
        )

        with patch(
            "modules.vpn_automation.pyperclip.copy"
        ) as copiar:
            resultado = automacao.preencher_formulario(
                "Rede A",
                "senha-a"
            )

        copiar.assert_called_once_with("")

        chamadas = automacao._preencher_campo.call_args_list

        self.assertEqual(
            chamadas[0].args,
            (
                retangulo.left + OFFSET_CAMPO_REDE[0],
                retangulo.top + OFFSET_CAMPO_REDE[1],
                "Rede A"
            )
        )
        self.assertEqual(
            chamadas[1].args,
            (
                retangulo.left + OFFSET_CAMPO_SENHA[0],
                retangulo.top + OFFSET_CAMPO_SENHA[1],
                "senha-a"
            )
        )

        self.assertTrue(resultado["campos_validados"])


class TestConfirmarEntrada(unittest.TestCase):

    def test_clica_no_botao_entrar(self):

        botao = ElementoFalso(
            "Entrar",
            automation_id=(
                "MainWindow.DlgJoinNetwork.joinPushButton"
            ),
            control_type="Button"
        )

        automacao = criar_automacao_sem_interface()

        automacao.formulario = ElementoFalso(
            "Radmin VPN",
            class_name="CDlgJoinNetwork",
            filhos=[botao]
        )
        automacao.localizar_formulario = Mock(
            return_value=True
        )

        with patch(
            "modules.vpn_automation.pyautogui.press"
        ) as pressionar, patch(
            "modules.vpn_automation.time.sleep"
        ):

            resultado = automacao.confirmar_entrada()

        self.assertTrue(botao.clicado)
        pressionar.assert_not_called()
        self.assertTrue(resultado["sucesso"])

    def test_fallback_enter_sem_botao(self):

        automacao = criar_automacao_sem_interface()

        automacao.formulario = ElementoFalso(
            "Radmin VPN",
            class_name="CDlgJoinNetwork"
        )
        automacao.localizar_formulario = Mock(
            return_value=True
        )

        with patch(
            "modules.vpn_automation.pyautogui.press"
        ) as pressionar, patch(
            "modules.vpn_automation.time.sleep"
        ):

            automacao.confirmar_entrada()

        pressionar.assert_called_once_with("enter")

    def test_formulario_ja_aberto_nao_aciona_menu(self):

        automacao = criar_automacao_sem_interface()

        automacao.localizar_janela = Mock(
            return_value=True
        )
        automacao.localizar_formulario = Mock(
            return_value=True
        )
        automacao.localizar_elemento = Mock(
            side_effect=AssertionError(
                "O menu não deve ser acionado."
            )
        )

        self.assertTrue(
            automacao.abrir_formulario_rede()
        )

        automacao.localizar_elemento.assert_not_called()


# ==========================================
# LOCALIZAÇÃO DA JANELA DO RADMIN (MOCK)
# ==========================================

class TestLocalizarJanelaRadmin(unittest.TestCase):

    def test_localiza_janela_ja_aberta(self):

        automacao = criar_automacao_sem_interface()

        automacao.localizar_janela = Mock(return_value=True)

        resultado = automacao.garantir_radmin_aberto()

        self.assertTrue(resultado["sucesso"])
        self.assertEqual(resultado["mensagem"], "Radmin VPN localizado.")

    def test_erro_claro_quando_janela_ausente(self):

        automacao = criar_automacao_sem_interface()

        automacao.localizar_janela = Mock(return_value=False)

        with self.assertRaises(RuntimeError) as contexto:

            automacao.garantir_radmin_aberto()

        self.assertIn(
            "Abra o Radmin VPN manualmente",
            str(contexto.exception)
        )


# ==========================================
# CONEXÃO INDIVIDUAL (MOCK)
# ==========================================

class TestConectarRede(unittest.TestCase):

    def test_sucesso_envia_nome_e_senha_corretos(self):

        automacao = criar_automacao_sem_interface()

        automacao.garantir_radmin_aberto = Mock(
            return_value={"sucesso": True}
        )
        automacao.obter_status_redes = Mock(return_value={})
        automacao.preparar_entrada = Mock(
            return_value={"sucesso": True}
        )
        automacao.preencher_formulario = Mock(
            return_value={
                "sucesso": True,
                "campos_validados": True
            }
        )
        automacao.confirmar_entrada = Mock(
            return_value={"sucesso": True}
        )
        automacao.aguardar_conexao = Mock(
            return_value={
                "sucesso": True,
                "estado": "conectado",
                "mensagem": "ok"
            }
        )

        resultado = automacao.conectar_rede(
            "Rede A",
            "senha-a"
        )

        automacao.preencher_formulario.assert_called_once_with(
            "Rede A",
            "senha-a"
        )

        self.assertTrue(resultado["sucesso"])
        self.assertEqual(resultado["estado"], "conectado")
        self.assertTrue(resultado["campos_validados"])

    def test_nao_reconecta_rede_online(self):

        automacao = criar_automacao_sem_interface()

        automacao.garantir_radmin_aberto = Mock(
            return_value={"sucesso": True}
        )
        automacao.obter_status_redes = Mock(
            return_value={"Rede A": "Online"}
        )
        automacao.preparar_entrada = Mock()

        resultado = automacao.conectar_rede(
            "Rede A",
            "senha-a"
        )

        automacao.preparar_entrada.assert_not_called()

        self.assertTrue(resultado["sucesso"])
        self.assertEqual(resultado["estado"], "ja_conectada")

    def test_nao_reconecta_rede_online_ignorando_caixa(self):

        automacao = criar_automacao_sem_interface()

        automacao.garantir_radmin_aberto = Mock(
            return_value={"sucesso": True}
        )
        automacao.obter_status_redes = Mock(
            return_value={"rede a": "Online"}
        )
        automacao.preparar_entrada = Mock()

        resultado = automacao.conectar_rede(
            "Rede A",
            "senha-a"
        )

        automacao.preparar_entrada.assert_not_called()

        self.assertEqual(resultado["estado"], "ja_conectada")

    def test_falha_de_preenchimento_retorna_estrutura(self):

        automacao = criar_automacao_sem_interface()

        automacao.garantir_radmin_aberto = Mock(
            return_value={"sucesso": True}
        )
        automacao.obter_status_redes = Mock(return_value={})
        automacao.preparar_entrada = Mock(
            return_value={"sucesso": True}
        )
        automacao.preencher_formulario = Mock(
            side_effect=RuntimeError("campo não preenchido")
        )

        resultado = automacao.conectar_rede(
            "Rede A",
            "senha-a"
        )

        self.assertFalse(resultado["sucesso"])
        self.assertEqual(resultado["estado"], "falha")
        self.assertIn("campo não preenchido", resultado["mensagem"])

    def test_campos_nao_relidos_ficam_indeterminados(self):

        automacao = criar_automacao_sem_interface()

        automacao.garantir_radmin_aberto = Mock(
            return_value={"sucesso": True}
        )
        automacao.obter_status_redes = Mock(return_value={})
        automacao.preparar_entrada = Mock(
            return_value={"sucesso": True}
        )
        automacao.preencher_formulario = Mock(
            return_value={
                "sucesso": True,
                "campos_validados": False
            }
        )
        automacao.confirmar_entrada = Mock(
            return_value={"sucesso": True}
        )
        automacao.aguardar_conexao = Mock(
            return_value={
                "sucesso": True,
                "estado": "conectado",
                "mensagem": "ok"
            }
        )

        resultado = automacao.conectar_rede(
            "Rede A",
            "senha-a"
        )

        self.assertFalse(resultado["campos_validados"])


# ==========================================
# STATUS POR HIERARQUIA (SEM POSIÇÃO)
# ==========================================

class TestStatusRedes(unittest.TestCase):

    def _montar_janela(self, agrupar_por_linha):

        if agrupar_por_linha:

            linha_a = ElementoFalso("linha-a")
            linha_a._filhos = [
                ElementoFalso("Rede A", linha_a),
                ElementoFalso("Online", linha_a)
            ]

            linha_b = ElementoFalso("linha-b")
            linha_b._filhos = [
                ElementoFalso("Rede B", linha_b),
                ElementoFalso("Offline", linha_b)
            ]

            return ElementoFalso(
                "Radmin VPN",
                class_name="CMainWnd",
                filhos=[linha_a, linha_b]
            )

        container = ElementoFalso("container")
        container._filhos = [
            ElementoFalso("Rede A", container),
            ElementoFalso("Rede B", container),
            ElementoFalso("Online", container)
        ]

        return ElementoFalso(
            "Radmin VPN",
            class_name="CMainWnd",
            filhos=[container]
        )

    def test_associa_status_pela_hierarquia(self):

        automacao = criar_automacao_sem_interface()

        automacao.janela = self._montar_janela(True)
        automacao.listar_redes = Mock(
            return_value=["Rede A", "Rede B"]
        )

        status = automacao.obter_status_redes()

        self.assertEqual(status, {
            "Rede A": "Online",
            "Rede B": "Offline"
        })

    def test_nao_associa_quando_ambiguo(self):

        automacao = criar_automacao_sem_interface()

        automacao.janela = self._montar_janela(False)
        automacao.listar_redes = Mock(
            return_value=["Rede A", "Rede B"]
        )

        status = automacao.obter_status_redes()

        self.assertEqual(status, {})


# ==========================================
# AGUARDAR CONEXÃO
# ==========================================

class TestAguardarConexao(unittest.TestCase):

    def test_confirma_online(self):

        automacao = criar_automacao_sem_interface()

        automacao.detectar_erro = Mock(return_value=None)
        automacao.obter_status_redes = Mock(
            return_value={"Rede A": "Online"}
        )

        resultado = automacao.aguardar_conexao("Rede A")

        self.assertTrue(resultado["sucesso"])
        self.assertEqual(resultado["estado"], "conectado")

    def test_confirma_online_ignorando_caixa(self):

        automacao = criar_automacao_sem_interface()

        automacao.detectar_erro = Mock(return_value=None)
        automacao.obter_status_redes = Mock(
            return_value={"rede a": "Online"}
        )

        resultado = automacao.aguardar_conexao("Rede A")

        self.assertTrue(resultado["sucesso"])
        self.assertEqual(resultado["estado"], "conectado")

    def test_detecta_erro(self):

        automacao = criar_automacao_sem_interface()

        automacao.detectar_erro = Mock(
            return_value="Senha incorreta"
        )
        automacao.obter_status_redes = Mock(return_value={})

        resultado = automacao.aguardar_conexao("Rede A")

        self.assertFalse(resultado["sucesso"])
        self.assertEqual(resultado["estado"], "falha")
        self.assertEqual(resultado["mensagem"], "Senha incorreta")


# ==========================================
# PROCESSAMENTO EM LOTE
# ==========================================

class TestProcessarLote(unittest.TestCase):

    def test_continua_apos_falha_e_preserva_associacao(self):

        chamadas = []

        class AutomacaoFalsa:

            def conectar_rede(self, nome, senha):

                chamadas.append((nome, senha))

                if nome == "Rede B":

                    raise RuntimeError("falha simulada")

                return {
                    "nome": nome,
                    "sucesso": True,
                    "estado": "conectado",
                    "mensagem": "ok"
                }

        registros = [
            {"nome": "Rede A", "senha": "senha-a", "linha": 2},
            {"nome": "Rede B", "senha": "senha-b", "linha": 3},
            {"nome": "Rede C", "senha": "senha-c", "linha": 4}
        ]

        progresso = []

        resultados = processar_lote(
            AutomacaoFalsa(),
            registros,
            ao_processar=lambda posicao, total, item: progresso.append(
                (posicao, total, item["nome"])
            )
        )

        self.assertEqual(chamadas, [
            ("Rede A", "senha-a"),
            ("Rede B", "senha-b"),
            ("Rede C", "senha-c")
        ])

        self.assertEqual(len(progresso), 3)

        self.assertEqual(len(resultados), 3)

        self.assertTrue(resultados[0]["sucesso"])
        self.assertFalse(resultados[1]["sucesso"])
        self.assertTrue(resultados[2]["sucesso"])

        self.assertEqual(resultados[1]["linha"], 3)
        self.assertEqual(resultados[1]["estado"], "falha")


if __name__ == "__main__":

    unittest.main()
