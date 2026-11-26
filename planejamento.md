# Plano — Automação Radmin VPN pelo painel (`app.py`)

> Documento de planejamento. Não executar as etapas marcadas com **AUTORIZAÇÃO**
> sem aprovação explícita do usuário.
>
> Data de referência: 2026-11-25
> Projeto: estrutura atual do repositório

---

## 1. Contexto atual

### O que já funciona (validado)

- Upload de `.xlsx`, normalização e validação (`modules/spreadsheet.py`, `modules/validation.py`).
- Associação `nome`, `senha`, `linha` por registro.
- Localização da janela principal `CMainWnd`.
- Localização do diálogo filho `CDlgJoinNetwork`
  (`MainWindow.DlgJoinNetwork`) por classe e AutomationId.
- Preenchimento de `LENetName` e `LEPassword` por AutomationId.
- Clique em `joinPushButton` (o diálogo fechou após o envio).
- Fallbacks preservados: coordenadas `(80,37)` / `(50,115)` e tecla `Enter`.
- Testes isolados consolidados em seis módulos sob `tests/`; execução pendente de dependências.
- Smoke test do Streamlit OK.

### Evidência do teste real (rede `S. REI DO ÂNCORA'`)

- Formulário preenchido e solicitação enviada.
- Nenhuma mensagem de erro detectada.
- Diálogo fechou após o clique.
- Estado retornado: `indeterminado`.
- `obter_status_redes()` retornou `{'HIRAM': 'Online'}`.
- A única ocorrência de `Online` na janela pertence a
  `userInfoWidget.LStatus` (status do usuário logado), **não** a uma rede.
- As linhas de rede (`CNetworkWidget`) contêm apenas o nome, sem texto
  `Online`/`Offline`.

### Bloqueador principal

`obter_status_redes()` não consegue provar o estado por rede. Consequências:

- `aguardar_conexao()` nunca confirma a rede alvo.
- O painel individual termina em aviso `indeterminado`.
- O lote marca tudo como “Falha”.
- Existe risco de falso positivo: o rótulo do usuário pode ser associado a uma
  rede de mesmo nome.

---

## 2. Objetivo

Fazer o painel `app.py`:

1. Confirmar conexão **somente** com evidência real de estado da rede.
2. Nunca confundir status do usuário com status de rede.
3. Distinguir `conectado`, `já conectada`, `offline`, `falha` e `indeterminado`.
4. Evitar enviar a rede errada quando a seleção mudar no painel.
5. Permitir lote com resultado confiável, sem desconectar redes existentes.
6. Continuar rodando com `streamlit run app.py`, preservando a arquitetura atual.

---

## 3. Restrições permanentes

- Não desconectar redes existentes.
- Não alterar configurações de rede.
- Não reconstruir a arquitetura nem migrar de framework.
- Não alterar coordenadas comprovadas sem evidência.
- Não usar heurística de posição para `Online`/`Offline`.
- Se não confirmar, retornar `indeterminado` — nunca “sucesso”.
- Nunca exibir, gravar ou registrar senhas.
- Interação com o Radmin real somente com autorização específica.
- Processamento em lote somente com autorização específica.

---

## 4. Fase 0 — Baseline antes de alterar

- [x] Revisar `git status` e os arquivos incluídos antes de cada commit.
- [x] Criar commits do baseline e da reorganização de testes.
- [x] Confirmar versões registradas:
  - `pywinauto==0.6.9`
  - `pyautogui==0.9.54`
  - `pyperclip==1.11.0`
  - `streamlit==1.66.1`
- [ ] Rodar linha de base quando as dependências estiverem instaladas:

```powershell
.\venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(pathlib.Path(p).read_text(encoding='utf-8'), filename=p) for p in ['app.py', 'modules/execution_lock.py', 'modules/spreadsheet.py', 'modules/ui_state.py', 'modules/validation.py', 'modules/vpn_automation.py', 'tests/diagnostico_radmin.py', 'tests/test_controle_execucao.py', 'tests/test_detectacao_erro.py', 'tests/test_estado_interface.py', 'tests/test_fluxo_automacao.py', 'tests/test_planilha.py', 'tests/test_validacao.py']]"
.\venv\Scripts\python.exe -B -m unittest -v tests.test_planilha tests.test_validacao tests.test_estado_interface tests.test_controle_execucao tests.test_deteccao_erro tests.test_fluxo_automacao
```

**Critério de saída:** seis módulos de teste OK, validação estática OK, dependências instaladas.

---

## 5. Fase 1 (P0) — Detecção real de estado por rede

### 5.1 Diagnóstico somente leitura — **AUTORIZAÇÃO**

**Objetivo:** descobrir como o Radmin representa o estado de cada rede.

**Pré-condição:** Radmin aberto, sessão Windows interativa.

**O que ler, sem clicar e sem preencher:**

Para cada `CNetworkWidget` dentro da janela principal:

- AutomationId do widget.
- Nome da rede (`NetworkName` / `QElideLabel`).
- Todos os textos do subtree.
- ControlTypes e classes dos filhos.
- Imagens/ícones (`Image`, `HelpText`, `FullDescription`, `LocalizedControlType`).
- Botões/menus presentes no subtree (ex.: “Desconectar”, “Sair”).
- Comparar uma rede sabidamente **Online** (`HIRAM`) com uma rede
  sabidamente **Offline**.
- Verificar explicitamente que `userInfoWidget.LStatus` fica **fora** do escopo.

Script sugerido (somente leitura, não clica):

```python
from modules.vpn_automation import RadminAutomation

radmin = RadminAutomation()

if not radmin.localizar_janela():
    raise SystemExit("Radmin nao localizado")

janela = radmin.janela

def textos(no, limite=40):
    vistos = []
    for d in no.descendants():
        try:
            t = d.window_text().strip()
        except Exception:
            continue
        if t and t not in vistos:
            vistos.append(t)
    return vistos[:limite]

for elemento in janela.descendants():
    try:
        info = elemento.element_info
        if info.class_name != "CNetworkWidget":
            continue

        print("\n=== CNetworkWidget ===")
        print("automation_id:", info.automation_id)
        print("textos:", textos(elemento))

        for d in elemento.descendants():
            try:
                di = d.element_info
                print(
                    " -",
                    di.control_type,
                    "| class=", repr(di.class_name),
                    "| name=", repr(di.name),
                    "| automation_id=", repr(di.automation_id),
                    "| help=", repr(getattr(di, "help_text", None)),
                    "| full=", repr(getattr(di, "full_description", None)),
                )
            except Exception:
                continue
    except Exception:
        continue
```

**Saída esperada:** identificar, por rede, um atributo estável que diferencie
Online de Offline (texto, ícone, descrição de acessibilidade ou botão).

**Critério de parada:** se não houver evidência inequívoca,
**não inventar heurística**. Manter `indeterminado` e propor alternativa.

### 5.2 Matriz de decisão

| Evidência encontrada | Implementação |
|---|---|
| Texto `Online`/`Offline` dentro de `CNetworkWidget` | Mapear por widget, sem subir para ancestrais genéricos |
| Ícone/imagem com nome ou descrição estável | Mapear ícone → estado |
| Botão “Desconectar” presente apenas quando conectado | Usar presença do botão como evidência |
| Nenhuma evidência UIA | Manter `indeterminado`; avaliar menu de contexto com autorização ou confirmação visual |

### 5.3 Implementação de `obter_status_redes()`

Arquivo: `modules/vpn_automation.py`; método atual em `modules/vpn_automation.py:827`.

Regras:

- [ ] Iterar **somente** widgets `CNetworkWidget`.
- [ ] Ignorar `userInfoWidget` e `LStatus`.
- [ ] Dentro de cada widget, obter o nome da rede.
- [ ] Obter o estado pela evidência definida na Fase 5.2.
- [ ] Se houver ambiguidade (mais de um nome ou mais de um estado), omitir.
- [ ] Manter assinatura `obter_status_redes(self) -> dict[str, str]`.
- [ ] Manter retorno `{}` quando não for possível.

Pseudocódigo:

```python
def obter_status_redes(self):
    redes = self.listar_redes()
    if not redes:
        return {}

    if self.janela is None and not self.localizar_janela():
        return {}

    status = {}

    for widget in self.janela.descendants():
        # 1. filtrar class_name == "CNetworkWidget"
        # 2. nome = unico QElideLabel != Online/Offline
        # 3. estado = evidencia real (texto/icone/botao)
        # 4. se nome in redes e estado valido: status[nome] = estado

    return status
```

### 5.4 Testes da Fase 1

- [ ] `CNetworkWidget` com texto `Online` → mapeia corretamente.
- [ ] `CNetworkWidget` com texto `Offline` → mapeia corretamente.
- [ ] `userInfoWidget.LStatus` com `Online` **não** gera associação.
- [ ] Rede `HIRAM` não é marcada por engano.
- [ ] Widget ambíguo é omitido.
- [ ] Testes existentes continuam passando.

### 5.5 Critério de aceite da Fase 1

- [ ] Verificação real somente leitura mostra o estado da rede alvo sem
      cliques e sem uso de credenciais.
- [ ] Nenhum falso `Online` para `HIRAM` causado por `userInfoWidget`.
- [ ] `indeterminado` permanece quando não há evidência.

---

## 6. Fase 2 (P1) — Estado e segurança do painel

Arquivo: `app.py`.

### 6.1 Reset ao trocar de planilha

- [ ] Calcular identidade do arquivo:

```python
import hashlib

conteudo = arquivo.getvalue()
assinatura = hashlib.sha256(conteudo).hexdigest()
```

- [ ] Guardar em `st.session_state["assinatura_planilha"]`.
- [ ] Se mudar, resetar:
  - `formulario_aberto = False`
  - `dados_preenchidos = False`
  - `resultados_lote = None`
  - `selecao_rede = 0`
  - `confirmacao_usuario = False`

**Motivo:** evita índice inválido e estado herdado de outra planilha.

### 6.2 Reset ao trocar a rede selecionada

- [ ] Guardar `rede_em_preenchimento` ao preencher.
- [ ] Se `nome` atual != `rede_em_preenchimento`, resetar:
  - `formulario_aberto = False`
  - `dados_preenchidos = False`

**Motivo:** impede confirmar os dados da rede anterior com outra rede
selecionada na tela.

### 6.3 Conferir o nome antes de confirmar

- [ ] Estender `confirmar_entrada(self, nome_esperado=None)`.
- [ ] Se `nome_esperado` for informado, reler `LENetName` e comparar.
- [ ] Se divergir, levantar `RuntimeError` e **não** clicar em “Entrar”.
- [ ] Se não for possível reler, avisar e seguir apenas com autorização
      explícita (ou bloquear, conforme decisão do usuário).
- [ ] No painel, chamar `radmin.confirmar_entrada(nome_esperado=nome)`.

### 6.4 Estado após o envio

- [ ] Após confirmar (sucesso ou não), definir `formulario_aberto = False`
      e `dados_preenchidos = False`.
- [ ] Se o diálogo não existir mais, não exibir o passo 2.

### 6.5 Semântica do resultado do lote

- [ ] Ajustar a tabela:

| Estado | Rótulo |
|---|---|
| `conectado` | Sucesso |
| `ja_conectada` | Já conectada |
| `indeterminado` | Não confirmado |
| `offline` | Falha |
| `falha` | Falha |

- [ ] Contar “Sucesso” apenas para `conectado`.
- [ ] Exibir separadamente “Não confirmados”.

### 6.6 Testes da Fase 2

- [ ] Reset ao trocar de planilha.
- [ ] Reset ao trocar de rede.
- [ ] `confirmar_entrada` bloqueia nome divergente.
- [ ] `confirmar_entrada` mantém compatibilidade sem `nome_esperado`.
- [ ] Rótulos do lote corretos por estado.
- [ ] Testes existentes continuam passando.

### 6.7 Critério de aceite da Fase 2

- [ ] Trocar de planilha não gera erro de índice.
- [ ] Trocar de rede nunca confirma dados da rede anterior.
- [ ] Resultado do lote diferencia “não confirmado” de “falha”.

---

## 7. Fase 3 (P2) — Operação segura e validação do lote

### 7.1 Lock de execução

- [ ] Criar `threading.Lock` em nível de módulo (mesmo processo do Streamlit).
- [ ] Envolver execução individual e lote com `lock.acquire(blocking=False)`.
- [ ] Se ocupado, exibir aviso: “Já existe uma execução em andamento.”
- [ ] Liberar no `finally`.

**Motivo:** duas abas/usuários não podem disputar mouse e teclado.

### 7.2 Acesso ao painel

- [ ] Documentar execução local:

```powershell
.\venv\Scripts\python.exe -B -m streamlit run app.py --server.address 127.0.0.1
```

- [ ] Se precisar de LAN, usar proxy reverso com autenticação.
- [ ] Não expor publicamente sem autenticação.

### 7.3 Radmin minimizado

- [ ] Em `preparar_entrada()` ou `localizar_janela()`, tentar `restore()`
      antes de focar.
- [ ] Se não for possível restaurar, erro claro orientando abrir o Radmin.

### 7.4 Validação real do lote — **AUTORIZAÇÃO**

- [ ] Usar planilha de teste com 2–3 redes.
- [ ] Confirmar se o Radmin troca de rede automaticamente.
- [ ] Se exigir desconexão, **parar** e pedir autorização específica para
      desconectar; não implementar desconexão automática sem aprovação.
- [ ] Comparar tabela do painel com o estado real no Radmin.
- [ ] Verificar que `indeterminado` nunca aparece como sucesso.

### 7.5 Critério de aceite da Fase 3

- [ ] Duas execuções simultâneas são bloqueadas.
- [ ] Painel não fica exposto sem autenticação.
- [ ] Radmin minimizado é restaurado ou gera erro claro.
- [ ] Lote validado com autorização, sem desconexão automática.

---

## 8. Fase 4 (P3) — Pendências menores

- [ ] Decidir sobre `.xls`:
  - manter restrito a `.xlsx`, ou
  - adicionar `xlrd` e testes.
- [ ] Separar validação por campo:
  - nome relido = confirmado;
  - senha não relível = aviso explícito.
- [ ] Avaliar `set_text` como alternativa ao clipboard.
- [ ] Refinar `detectar_erro()` com teste real de senha incorreta
      (**AUTORIZAÇÃO**).
- [ ] Adicionar logging sem senha (rede, etapa, estado).

---

## 9. Critérios de aceite globais

- [ ] Individual: “Sucesso” somente com estado `conectado` comprovado.
- [ ] Individual: `indeterminado` exibido como aviso, nunca como sucesso.
- [ ] Nenhum falso `Online` causado por `userInfoWidget`.
- [ ] Lote: cada linha com estado correto; “Não confirmado” separado de “Falha”.
- [ ] Nenhuma desconexão automática.
- [ ] Nenhuma alteração de configuração de rede.
- [ ] Senhas nunca exibidas, gravadas ou registradas.
- [ ] `py_compile` OK.
- [ ] Todos os testes isolados OK.
- [ ] Smoke test do Streamlit OK.
- [ ] Validação real somente com autorização.

---

## 10. Comandos de verificação

```powershell
# Validação estática sem dependências externas
.\venv\Scripts\python.exe -B -c "import ast, pathlib; [ast.parse(pathlib.Path(p).read_text(encoding='utf-8'), filename=p) for p in ['app.py', 'modules/execution_lock.py', 'modules/spreadsheet.py', 'modules/ui_state.py', 'modules/validation.py', 'modules/vpn_automation.py', 'tests/diagnostico_radmin.py', 'tests/test_controle_execucao.py', 'tests/test_detectacao_erro.py', 'tests/test_estado_interface.py', 'tests/test_fluxo_automacao.py', 'tests/test_planilha.py', 'tests/test_validacao.py']]"

# Testes isolados após instalação das dependências
.\venv\Scripts\python.exe -B -m unittest -v tests.test_planilha tests.test_validacao tests.test_estado_interface tests.test_controle_execucao tests.test_deteccao_erro tests.test_fluxo_automacao

# Diagnósticos manuais, somente com autorização
.\venv\Scripts\python.exe -B tests\diagnostico_radmin.py janelas
.\venv\Scripts\python.exe -B tests\diagnostico_radmin.py programa
.\venv\Scripts\python.exe -B tests\diagnostico_radmin.py formulario
.\venv\Scripts\python.exe -B tests\diagnostico_radmin.py campos

# Smoke test do painel, somente com autorização
.\venv\Scripts\python.exe -B -m streamlit run app.py --server.headless true --server.address 127.0.0.1 --server.port 8601
```

---

## 11. Portões de autorização

| Portão | Ação | Requer |
|---|---|---|
| A | Diagnóstico somente leitura do estado por rede | Autorização explícita |
| B | Alterações de código das Fases 1 e 2 | Agente de execução |
| C | Tentativa real individual | Autorização explícita, uma por vez |
| D | Processamento em lote real | Autorização explícita + política de desconexão definida |
| E | Teste com senha incorreta | Autorização explícita |

**Regra:** nenhuma senha pode ser impressa, gravada em arquivo ou incluída em log.

---

## 12. Rollback

- [ ] Antes de alterar, criar commit de checkpoint.
- [ ] Se algo falhar: `git diff` para revisar e `git restore <arquivo>` para voltar.
- [ ] Não usar `git reset --hard` sem confirmação (pode apagar trabalho não commitado).

---

## 13. Checklist resumido para rodar depois

1. [x] Fase 0 — baseline + commits.
2. [ ] Autorizar diagnóstico somente leitura (Portão A).
3. [ ] Executar script da seção 5.1 e registrar evidências.
4. [ ] Escolher a linha da matriz 5.2.
5. [ ] Trocar para o agente de execução.
6. [ ] Implementar `obter_status_redes()` (seção 5.3).
7. [ ] Implementar ajustes do painel (seção 6).
8. [ ] Atualizar testes e rodar `py_compile` + `unittest`.
9. [ ] Smoke test do Streamlit.
10. [ ] Autorizar tentativa real individual (Portão C).
11. [ ] Comparar resultado do painel com o Radmin real.
12. [ ] Implementar lock e restrição de acesso (seção 7).
13. [ ] Autorizar validação de lote (Portão D).
14. [ ] Só então considerar o painel “oficial”.

---

## 14. Observações finais

- O formulário já está resolvido; o problema restante é **status**, não preenchimento.
- O painel atual executa, mas não pode afirmar sucesso com segurança.
- A correção do status é a única mudança que depende de evidência real do Radmin.
- Sem essa evidência, a decisão correta continua sendo `indeterminado`.
- O venv do projeto contém apenas `pip`; a instalação das dependências segue pendente.
- Os diagnósticos manuais estão consolidados em `tests/diagnostico_radmin.py`.
- A abertura automática do Radmin não está implementada; `garantir_radmin_aberto()` apenas localiza a janela.