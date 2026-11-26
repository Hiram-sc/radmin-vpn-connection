"""Cálculo do estado de interface a partir da realidade observada.

O estado guardado em st.session_state pode divergir da janela real do
Radmin (refresh do navegador, formulário fechado pelo usuário, outra aba
que abriu o diálogo). Este módulo concentra a decisão em uma função pura,
testável sem Streamlit.
"""


def calcular_estado(
    upload_id_anterior,
    upload_id_atual,
    formulario_aberto,
    dados_preenchidos,
    janela_encontrada=None,
    formulario_encontrado=None
):
    """Devolve o estado que deve ser gravado na sessão.

    janela_encontrada / formulario_encontrado podem ser None (desconhecido):
    nesse caso a realidade observada não altera o estado.
    """

    if upload_id_atual is None:

        return {
            "reiniciar": True,
            "formulario_aberto": False,
            "dados_preenchidos": False,
            "aviso": "Aguardando o envio da planilha."
        }

    novo_arquivo = upload_id_atual != upload_id_anterior

    if novo_arquivo:

        formulario_aberto = False
        dados_preenchidos = False

    aviso = None

    if janela_encontrada is False:

        formulario_aberto = False
        dados_preenchidos = False

        aviso = "O Radmin VPN não está aberto nesta máquina."

    elif formulario_encontrado is False:

        formulario_aberto = False
        dados_preenchidos = False

        aviso = "O formulário de conexão do Radmin não está aberto."

    elif not formulario_aberto:

        dados_preenchidos = False

    return {
        "reiniciar": novo_arquivo,
        "formulario_aberto": bool(formulario_aberto),
        "dados_preenchidos": bool(dados_preenchidos),
        "aviso": aviso
    }
