"""Fase 0.2 — mensagens de validação."""

import unittest

from modules.validation import validar_registros


class TestMensagens(unittest.TestCase):

    def test_nome_vazio(self):

        validos, erros = validar_registros([
            {"nome": None, "senha": "s1", "linha": 2}
        ])

        self.assertEqual(validos, [])
        self.assertEqual(erros, ["Linha 2: célula Nome vazia."])

    def test_senha_vazia(self):

        validos, erros = validar_registros([
            {"nome": "Rede A", "senha": None, "linha": 3}
        ])

        self.assertEqual(validos, [])
        self.assertEqual(erros, ["Linha 3: célula Senha vazia."])

    def test_nome_so_com_espacos(self):

        validos, erros = validar_registros([
            {"nome": "   ", "senha": "s1", "linha": 4}
        ])

        self.assertEqual(validos, [])
        self.assertEqual(
            erros,
            ["Linha 4: célula Nome contém apenas espaços."]
        )

    def test_senha_so_com_espacos(self):

        validos, erros = validar_registros([
            {"nome": "Rede A", "senha": "   ", "linha": 5}
        ])

        self.assertEqual(validos, [])
        self.assertEqual(
            erros,
            ["Linha 5: célula Senha contém apenas espaços."]
        )

    def test_duplicado_mantido(self):

        validos, erros = validar_registros([
            {"nome": "Rede A", "senha": "s1", "linha": 2},
            {"nome": "rede a", "senha": "s2", "linha": 3}
        ])

        self.assertEqual(len(validos), 1)
        self.assertEqual(erros, ["Linha 3: nome duplicado (rede a)."])

    def test_celula_vazia_nao_ocupa_nome(self):

        validos, erros = validar_registros([
            {"nome": None, "senha": "s1", "linha": 2},
            {"nome": "Rede A", "senha": "s2", "linha": 3}
        ])

        self.assertEqual(len(validos), 1)
        self.assertEqual(len(erros), 1)

    def test_espacos_aparas_em_registro_valido(self):

        validos, erros = validar_registros([
            {"nome": "  Rede A  ", "senha": "  s1  ", "linha": 2}
        ])

        self.assertEqual(erros, [])
        self.assertEqual(validos[0]["nome"], "Rede A")
        self.assertEqual(validos[0]["senha"], "s1")


if __name__ == "__main__":

    unittest.main()
