def _analisar_celula(valor, rotulo, linha):
    """Devolve (texto, mensagem_de_erro)."""

    if valor is None:
        return None, f"Linha {linha}: célula {rotulo} vazia."

    if isinstance(valor, str):

        if valor == "":
            return None, f"Linha {linha}: célula {rotulo} vazia."

        if not valor.strip():
            return None, (
                f"Linha {linha}: célula {rotulo} contém apenas espaços."
            )

        return valor.strip(), None

    texto = str(valor).strip()

    if not texto:
        return None, f"Linha {linha}: célula {rotulo} vazia."

    return texto, None


def validar_registros(registros):

    validos = []
    erros = []
    nomes_encontrados = set()

    for registro in registros:

        linha = registro.get("linha")

        nome, erro_nome = _analisar_celula(
            registro.get("nome"),
            "Nome",
            linha
        )

        if erro_nome is not None:
            erros.append(erro_nome)
            continue

        senha, erro_senha = _analisar_celula(
            registro.get("senha"),
            "Senha",
            linha
        )

        if erro_senha is not None:
            erros.append(erro_senha)
            continue

        identificador = nome.casefold()

        if identificador in nomes_encontrados:
            erros.append(
                f"Linha {linha}: nome duplicado ({nome})."
            )
            continue

        nomes_encontrados.add(identificador)

        validos.append({
            "nome": nome,
            "senha": senha,
            "linha": linha
        })

    return validos, erros
