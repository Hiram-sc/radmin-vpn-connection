"""Fase 0.1 — normalização de células da planilha."""

import io
import unittest

import pandas as pd

from modules.spreadsheet import (
    carregar_planilha,
    montar_registros,
    normalizar_celula
)


def montar_planilha(dados):

    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:

        pd.DataFrame(dados).to_excel(writer, index=False)

    buffer.seek(0)

    return buffer


class TestNormalizarCelula(unittest.TestCase):

    def test_nan_vira_none(self):

        self.assertIsNone(normalizar_celula(float("nan")))

    def test_none_continua_none(self):

        self.assertIsNone(normalizar_celula(None))

    def test_pd_na_vira_none(self):

        self.assertIsNone(normalizar_celula(pd.NA))

    def test_float_inteiro_nao_ganha_ponto_zero(self):

        self.assertEqual(normalizar_celula(123456.0), "123456")

    def test_float_nao_inteiro_preservado(self):

        self.assertEqual(normalizar_celula(12.5), "12.5")

    def test_inteiro_vira_texto(self):

        self.assertEqual(normalizar_celula(12345), "12345")

    def test_texto_apara_espacos(self):

        self.assertEqual(normalizar_celula("  Rede A  "), "Rede A")

    def test_texto_so_com_espacos_vira_none(self):

        self.assertIsNone(normalizar_celula("   "))

    def test_texto_vazio_vira_none(self):

        self.assertIsNone(normalizar_celula(""))

    def test_booleano_vira_texto(self):

        self.assertEqual(normalizar_celula(True), "True")


class TestPlanilha(unittest.TestCase):

    def test_linha_totalmente_vazia_e_ignorada(self):

        buffer = montar_planilha({
            "Nome": ["Rede A", None, "Rede B"],
            "Senha": ["s1", None, "s2"]
        })

        df = carregar_planilha(buffer)
        registros = montar_registros(df)

        self.assertEqual(len(df), 3)
        self.assertEqual(len(registros), 2)
        self.assertEqual(
            [item["nome"] for item in registros],
            ["Rede A", "Rede B"]
        )
        self.assertEqual(
            [item["linha"] for item in registros],
            [2, 4]
        )

    def test_senha_numerica_e_convertida_sem_ponto_zero(self):

        buffer = montar_planilha({
            "Nome": ["Rede A"],
            "Senha": [123456]
        })

        df = carregar_planilha(buffer)
        registros = montar_registros(df)

        self.assertEqual(registros[0]["senha"], "123456")

    def test_senha_numerica_com_linha_vazia(self):

        buffer = montar_planilha({
            "Nome": ["Rede A", "Rede B", None],
            "Senha": [123456, None, None]
        })

        df = carregar_planilha(buffer)
        registros = montar_registros(df)

        self.assertEqual(len(registros), 2)
        self.assertEqual(registros[0]["senha"], "123456")
        self.assertIsNone(registros[1]["senha"])

    def test_celula_so_com_espacos_nao_e_ignorada(self):

        buffer = montar_planilha({
            "Nome": ["Rede A"],
            "Senha": ["   "]
        })

        df = carregar_planilha(buffer)
        registros = montar_registros(df)

        self.assertEqual(len(registros), 1)
        self.assertIsNone(registros[0]["senha"])

    def test_colunas_obrigatorias(self):

        buffer = montar_planilha({"Rede": ["Rede A"]})

        with self.assertRaises(ValueError):

            carregar_planilha(buffer)


if __name__ == "__main__":

    unittest.main()
