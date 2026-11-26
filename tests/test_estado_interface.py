"""Fase 0.4 — estado de sessão derivado da realidade observada."""

import unittest

from modules.ui_state import calcular_estado


class TestCalcularEstado(unittest.TestCase):

    def test_sem_upload_reinicia_e_avisa(self):

        estado = calcular_estado(
            upload_id_anterior="a",
            upload_id_atual=None,
            formulario_aberto=True,
            dados_preenchidos=True
        )

        self.assertTrue(estado["reiniciar"])
        self.assertFalse(estado["formulario_aberto"])
        self.assertFalse(estado["dados_preenchidos"])
        self.assertEqual(
            estado["aviso"],
            "Aguardando o envio da planilha."
        )

    def test_mesmo_arquivo_preserva_estado(self):

        estado = calcular_estado(
            upload_id_anterior="a",
            upload_id_atual="a",
            formulario_aberto=True,
            dados_preenchidos=True
        )

        self.assertFalse(estado["reiniciar"])
        self.assertTrue(estado["formulario_aberto"])
        self.assertTrue(estado["dados_preenchidos"])
        self.assertIsNone(estado["aviso"])

    def test_novo_upload_reinicia(self):

        estado = calcular_estado(
            upload_id_anterior="a",
            upload_id_atual="b",
            formulario_aberto=True,
            dados_preenchidos=True
        )

        self.assertTrue(estado["reiniciar"])
        self.assertFalse(estado["formulario_aberto"])
        self.assertFalse(estado["dados_preenchidos"])

    def test_janela_ausente_reseta_estado(self):

        estado = calcular_estado(
            upload_id_anterior="a",
            upload_id_atual="a",
            formulario_aberto=True,
            dados_preenchidos=True,
            janela_encontrada=False
        )

        self.assertFalse(estado["formulario_aberto"])
        self.assertFalse(estado["dados_preenchidos"])
        self.assertEqual(
            estado["aviso"],
            "O Radmin VPN não está aberto nesta máquina."
        )

    def test_formulario_ausente_reseta_estado(self):

        estado = calcular_estado(
            upload_id_anterior="a",
            upload_id_atual="a",
            formulario_aberto=True,
            dados_preenchidos=True,
            janela_encontrada=True,
            formulario_encontrado=False
        )

        self.assertFalse(estado["formulario_aberto"])
        self.assertFalse(estado["dados_preenchidos"])
        self.assertEqual(
            estado["aviso"],
            "O formulário de conexão do Radmin não está aberto."
        )

    def test_formulario_fechado_limpa_dados_preenchidos(self):

        estado = calcular_estado(
            upload_id_anterior="a",
            upload_id_atual="a",
            formulario_aberto=False,
            dados_preenchidos=True
        )

        self.assertFalse(estado["formulario_aberto"])
        self.assertFalse(estado["dados_preenchidos"])
        self.assertIsNone(estado["aviso"])

    def test_realidade_desconhecida_nao_altera(self):

        estado = calcular_estado(
            upload_id_anterior="a",
            upload_id_atual="a",
            formulario_aberto=True,
            dados_preenchidos=True,
            janela_encontrada=None,
            formulario_encontrado=None
        )

        self.assertTrue(estado["formulario_aberto"])
        self.assertTrue(estado["dados_preenchidos"])
        self.assertIsNone(estado["aviso"])

    def test_estado_observado_aberto_mantem(self):

        estado = calcular_estado(
            upload_id_anterior="a",
            upload_id_atual="a",
            formulario_aberto=True,
            dados_preenchidos=True,
            janela_encontrada=True,
            formulario_encontrado=True
        )

        self.assertTrue(estado["formulario_aberto"])
        self.assertTrue(estado["dados_preenchidos"])
        self.assertIsNone(estado["aviso"])


if __name__ == "__main__":

    unittest.main()
