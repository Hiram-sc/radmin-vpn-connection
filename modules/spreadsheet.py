import pandas as pd


COLUNAS_OBRIGATORIAS = ("Nome", "Senha")


def normalizar_celula(valor):
    """Converte uma célula da planilha em texto ou None.

    Regras:
    - célula vazia (NaN/None) -> None;
    - número inteiro (inclusive float inteiro) -> texto sem ".0";
    - demais valores -> texto sem espaços nas extremidades;
    - texto vazio ou só com espaços -> None.
    """

    if valor is None:
        return None

    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(valor, bool):
        return str(valor)

    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))

    if isinstance(valor, int):
        return str(valor)

    texto = str(valor).strip()

    if not texto:
        return None

    return texto


def carregar_planilha(arquivo):

    if arquivo is None:
        raise ValueError("Nenhuma planilha foi enviada.")

    arquivo.seek(0)

    df = pd.read_excel(arquivo)

    # Normalizar títulos das colunas
    df.columns = [
        str(coluna).strip()
        for coluna in df.columns
    ]

    faltantes = set(COLUNAS_OBRIGATORIAS) - set(df.columns)

    if faltantes:
        raise ValueError(
            f"Colunas obrigatórias ausentes: {', '.join(sorted(faltantes))}"
        )

    df = df[list(COLUNAS_OBRIGATORIAS)].copy()

    for coluna in COLUNAS_OBRIGATORIAS:
        df[coluna] = df[coluna].map(normalizar_celula)

    return df


def _linha_de_origem(indice, posicao):
    """Número da linha na planilha (cabeçalho = linha 1)."""

    try:
        return int(indice) + 2
    except (TypeError, ValueError):
        return posicao + 2


def montar_registros(df):
    """Converte o DataFrame em registros com nome, senha e linha de origem.

    Linhas totalmente vazias (nome e senha ausentes) são ignoradas.
    """

    if "Nome" not in df.columns or "Senha" not in df.columns:
        raise ValueError(
            "O DataFrame deve conter as colunas Nome e Senha."
        )

    registros = []

    for posicao, (indice, linha) in enumerate(df.iterrows()):

        nome = normalizar_celula(linha["Nome"])
        senha = normalizar_celula(linha["Senha"])

        if nome is None and senha is None:
            continue

        registros.append({
            "nome": nome,
            "senha": senha,
            "linha": _linha_de_origem(indice, posicao)
        })

    return registros
