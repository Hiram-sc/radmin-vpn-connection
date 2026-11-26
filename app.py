
import hashlib

import streamlit as st
import pandas as pd

from modules.execution_lock import (
    RECURSO_PADRAO,
    abrir_turno,
    fechar_turno,
    turno_ativo
)
from modules.spreadsheet import (
    carregar_planilha,
    montar_registros
)
from modules.ui_state import calcular_estado
from modules.validation import validar_registros
from modules.vpn_automation import (
    RadminAutomation,
    processar_lote
)


# ==========================================
# CONFIGURAÇÃO
# ==========================================

st.set_page_config(
    page_title="Automação Radmin VPN",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# ==========================================
# ESTILO
# ==========================================

st.markdown("""
<style>

.main-title {
    font-size: 30px;
    font-weight: bold;
    margin-bottom: 5px;
}

.subtitle {
    color: #888888;
    font-size: 15px;
    margin-bottom: 25px;
}

</style>
""", unsafe_allow_html=True)


# ==========================================
# ESTADO DA SESSÃO
# ==========================================

defaults = {
    "dados_redes": None,
    "formulario_aberto": False,
    "dados_preenchidos": False,
    "rede_selecionada": None,
    "confirmacao_usuario": False,
    "resultados_lote": None,
    "upload_id": None
}

for chave, valor in defaults.items():

    if chave not in st.session_state:
        st.session_state[chave] = valor


# ==========================================
# APOIO
# ==========================================

def _identificador_arquivo(arquivo):
    """Identidade do upload, para detectar troca de planilha."""

    if arquivo is None:

        return None

    try:

        return hashlib.sha256(arquivo.getvalue()).hexdigest()

    except Exception:

        return None


def _estado_real_radmin():
    """Consulta a janela real do Radmin.

    Retorna (janela_encontrada, formulario_encontrado). Em caso de falha,
    retorna (None, None) para que o estado da sessão não seja alterado.
    """

    try:

        automacao = RadminAutomation()

        if not automacao.localizar_janela():

            return False, False

        return True, bool(automacao.localizar_formulario())

    except Exception:

        return None, None


def _iniciar_execucao():
    """Tenta reservar o desktop para esta execução."""

    if abrir_turno():

        return True

    st.error(
        "Outra execução de automação está em andamento "
        "(outra aba, outra sessão ou outro processo). "
        "Aguarde a conclusão antes de iniciar uma nova."
    )

    return False


# ==========================================
# CABEÇALHO
# ==========================================

st.markdown(
    '<div class="main-title">🔐 SISTEMA DE VPN</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">AUTOMAÇÃO RADMIN VPN</div>',
    unsafe_allow_html=True
)

st.divider()


# ==========================================
# IMPORTAÇÃO
# ==========================================

st.subheader("Importação de redes")

st.write(
    "Selecione a planilha Excel contendo "
    "os nomes das redes e suas respectivas senhas."
)

st.info(
    "Formato obrigatório: colunas Nome e Senha. "
    "Arquivo .xlsx."
)

arquivo = st.file_uploader(
    "Selecione sua planilha Excel",
    type=["xlsx"],
    key="upload_planilha"
)


# ==========================================
# ESTADO DERIVADO DA REALIDADE
# ==========================================

upload_id = _identificador_arquivo(arquivo)

janela_encontrada = None
formulario_encontrado = None

if upload_id is not None and (
    st.session_state.formulario_aberto
    or st.session_state.dados_preenchidos
):

    janela_encontrada, formulario_encontrado = _estado_real_radmin()

estado = calcular_estado(
    upload_id_anterior=st.session_state.upload_id,
    upload_id_atual=upload_id,
    formulario_aberto=st.session_state.formulario_aberto,
    dados_preenchidos=st.session_state.dados_preenchidos,
    janela_encontrada=janela_encontrada,
    formulario_encontrado=formulario_encontrado
)

st.session_state.upload_id = upload_id
st.session_state.formulario_aberto = estado["formulario_aberto"]
st.session_state.dados_preenchidos = estado["dados_preenchidos"]

if estado["reiniciar"]:

    st.session_state.resultados_lote = None

if upload_id is not None and estado["aviso"]:

    st.warning(estado["aviso"])


# ==========================================
# PROCESSAMENTO
# ==========================================

if arquivo is None:

    st.warning("Aguardando o envio da planilha.")

else:

    try:

        df = carregar_planilha(arquivo)

        st.session_state.dados_redes = df

        st.success("Planilha carregada com sucesso!")

        # ======================================
        # RESUMO
        # ======================================

        registros = montar_registros(df)

        total = len(registros)

        linhas_ignoradas = len(df) - total

        st.subheader("Resumo da importação")

        col1, col2 = st.columns(2)

        col1.metric(
            "Redes identificadas",
            total
        )

        col2.metric(
            "Colunas identificadas",
            len(df.columns)
        )

        if linhas_ignoradas:

            st.caption(
                f"{linhas_ignoradas} linha(s) totalmente vazia(s) "
                "ignorada(s)."
            )

        # ======================================
        # VALIDAÇÃO
        # ======================================

        validos, erros_validacao = validar_registros(
            registros
        )

        st.subheader("Validação")

        if total == 0:

            st.error("A planilha não possui registros.")

        elif erros_validacao:

            st.error(
                f"{len(erros_validacao)} registro(s) "
                f"inválido(s) encontrado(s)."
            )

            for erro in erros_validacao:

                st.write(f"- {erro}")

        else:

            st.success(
                f"{len(validos)} registro(s) válido(s)."
            )

        # ======================================
        # VISUALIZAÇÃO
        # ======================================

        st.subheader("Redes encontradas")

        # Não exibir senhas na interface.
        st.dataframe(
            df[["Nome"]],
            width="stretch",
            hide_index=True
        )

        # ======================================
        # AUTOMAÇÃO
        # ======================================

        st.divider()

        st.subheader("Execução da automação")

        ocupado = turno_ativo()

        st.caption(
            f"Recurso de execução ({RECURSO_PADRAO}): "
            + ("em andamento" if ocupado else "livre")
        )

        if st.button(
            "Revalidar estado do Radmin",
            width="stretch",
            key="revalidar_estado"
        ):

            janela, formulario = _estado_real_radmin()

            if janela is None:

                st.warning(
                    "Não foi possível consultar o Radmin VPN."
                )

            elif not janela:

                st.warning("O Radmin VPN não está aberto.")

            elif not formulario:

                st.warning(
                    "O formulário de conexão do Radmin "
                    "não está aberto."
                )

            else:

                st.success(
                    "Radmin VPN aberto e formulário identificado."
                )

            st.session_state.formulario_aberto = bool(
                janela and formulario
            )

            if not formulario:

                st.session_state.dados_preenchidos = False

        if ocupado:

            if st.button(
                "Liberar execução",
                key="liberar_execucao"
            ):

                fechar_turno()

                st.info("Execução liberada.")

                st.rerun()

        if not validos:

            st.warning(
                "Corrija os registros inválidos antes de prosseguir."
            )

        else:

            st.warning(
                "O Radmin VPN será localizado automaticamente no "
                "computador que executa o Streamlit. Caso não seja "
                "encontrado, abra-o manualmente."
            )

            autorizado = st.checkbox(
                "Conferi os dados e autorizo a operação.",
                key="confirmacao_usuario"
            )

            # ==================================
            # SELEÇÃO DA REDE
            # ==================================

            indice = st.selectbox(
                "Selecione a rede que deseja processar",

                options=list(range(len(validos))),

                format_func=lambda i: validos[i]["nome"],

                key="selecao_rede"
            )

            registro = validos[indice]

            nome = registro["nome"]
            senha = registro["senha"]

            st.write(
                f"**Rede selecionada:** {nome} "
                f"(linha {registro['linha']})"
            )

            # ==================================
            # ABRIR FORMULÁRIO
            # ==================================

            if st.button(
                "1. Abrir formulário do Radmin",
                width="stretch",
                disabled=not autorizado
            ):

                if _iniciar_execucao():

                    try:

                        radmin = RadminAutomation()

                        abertura = radmin.garantir_radmin_aberto()

                        resultado = radmin.preparar_entrada()

                        st.session_state.formulario_aberto = True
                        st.session_state.dados_preenchidos = False

                        st.success(
                            f"{abertura['mensagem']} "
                            f"{resultado['mensagem']}"
                        )

                    except Exception as erro:

                        fechar_turno()

                        st.error(
                            f"Erro ao abrir formulário: {erro}"
                        )

            # ==================================
            # PREENCHER CAMPOS
            # ==================================

            if st.session_state.formulario_aberto:

                if st.button(
                    "2. Preencher nome e senha",
                    width="stretch",
                    disabled=not autorizado
                ):

                    if _iniciar_execucao():

                        try:

                            radmin = RadminAutomation()

                            resultado = radmin.preencher_formulario(
                                nome,
                                senha
                            )

                            st.session_state.dados_preenchidos = True

                            if resultado.get("campos_validados"):

                                st.success(
                                    f"{resultado['mensagem']} "
                                    "Campos relidos e conferidos."
                                )

                            else:

                                st.warning(
                                    f"{resultado['mensagem']} Não foi possível "
                                    "reler os campos; confira manualmente "
                                    "antes de enviar."
                                )

                        except Exception as erro:

                            fechar_turno()

                            st.error(
                                f"Erro ao preencher formulário: {erro}"
                            )

            # ==================================
            # CONFIRMAR ENVIO
            # ==================================

            if st.session_state.dados_preenchidos:

                st.warning(
                    "Confira o nome e a senha no formulário "
                    "do Radmin antes de enviar."
                )

                if st.button(
                    "3. Confirmar e enviar entrada",
                    type="primary",
                    width="stretch",
                    disabled=not autorizado
                ):

                    if _iniciar_execucao():

                        try:

                            radmin = RadminAutomation()

                            resultado = radmin.confirmar_entrada()

                            st.info(resultado["mensagem"])

                            # O nome na lista não comprova conexão.
                            # Só há sucesso com estado Online confirmado.

                            with st.spinner(
                                "Verificando o estado da conexão..."
                            ):

                                verificacao = radmin.aguardar_conexao(
                                    nome
                                )

                            if verificacao["sucesso"]:

                                st.success(verificacao["mensagem"])

                            elif verificacao["estado"] == "indeterminado":

                                st.warning(verificacao["mensagem"])

                            else:

                                st.error(verificacao["mensagem"])

                            st.session_state.dados_preenchidos = False

                        except Exception as erro:

                            st.error(
                                f"Erro durante a confirmação: {erro}"
                            )

                        finally:

                            fechar_turno()

            # ==================================
            # PROCESSAMENTO EM LOTE
            # ==================================

            st.divider()

            st.subheader("Processamento em lote")

            st.write(
                f"Serão processadas {len(validos)} rede(s) "
                "sequencialmente, uma por vez, na ordem da planilha."
            )

            st.caption(
                "Redes já conectadas não serão desconectadas. "
                "O estado atual das conexões é preservado."
            )

            if st.button(
                "Executar todas as redes válidas",
                width="stretch",
                disabled=not autorizado,
                key="botao_lote"
            ):

                if _iniciar_execucao():

                    try:

                        automacao = RadminAutomation()

                        progresso = st.progress(0)

                        andamento = st.empty()

                        def atualizar_andamento(
                            posicao,
                            total_lote,
                            item
                        ):

                            andamento.write(
                                f"Processando {posicao}/{total_lote}: "
                                f"{item['nome']}"
                            )

                            progresso.progress(
                                posicao / total_lote
                            )

                        resultados = processar_lote(
                            automacao,
                            validos,
                            ao_processar=atualizar_andamento
                        )

                        andamento.write("Processamento concluído.")

                        st.session_state.resultados_lote = [
                            {
                                "Linha": item["linha"],
                                "Rede": item["nome"],
                                "Resultado": (
                                    "Sucesso"
                                    if item["sucesso"]
                                    else "Falha"
                                ),
                                "Estado": item["estado"],
                                "Campos": (
                                    "Sim"
                                    if item.get("campos_validados") is True
                                    else "Não"
                                    if item.get("campos_validados") is False
                                    else "-"
                                ),
                                "Mensagem": item["mensagem"]
                            }
                            for item in resultados
                        ]

                    finally:

                        fechar_turno()

            if st.session_state.resultados_lote:

                st.subheader("Resultado do lote")

                tabela = st.session_state.resultados_lote

                sucessos = sum(
                    1 for item in tabela
                    if item["Resultado"] == "Sucesso"
                )

                coluna1, coluna2 = st.columns(2)

                coluna1.metric("Sucessos", sucessos)

                coluna2.metric(
                    "Falhas",
                    len(tabela) - sucessos
                )

                st.dataframe(
                    pd.DataFrame(tabela),
                    width="stretch",
                    hide_index=True
                )

    except Exception as erro:

        st.session_state.dados_redes = None

        st.error(
            f"Não foi possível carregar a planilha: {erro}"
        )


# ==========================================
# RODAPÉ
# ==========================================

st.divider()

st.caption(
    "Sistema de Automação Radmin VPN | "
    "Importação, validação e gerenciamento de redes"
)
