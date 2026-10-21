# Gestão de Demandas

Painel de acompanhamento das demandas da equipe (Motiva), no mesmo padrão do
DimConservação: **sobe a planilha → o app lê, confere e gera os painéis**.

Lê a planilha de demandas **no formato que a equipe já usa** (ex.:
`Gestão 4.0 - NTec.xlsx`) e mostra avanço, atrasos, prazos da semana, carga por
responsável, pauta da reunião semanal e pendências de dado. Exporta um
PowerPoint executivo e uma base consolidada em Excel.

**Memória:** cada planilha importada é gravada como uma "foto" num banco de dados
online (Supabase). Qualquer pessoa do time sobe a versão nova; o app mostra o que
é novo, o que mudou e o que saiu, e guarda o histórico (quando concluiu, quantas
vezes o prazo foi adiado, evolução semana a semana).

> **Status: MVP (Fases 1 e 3).** Para publicar com o banco online e a senha do
> time, siga **`PASSO_A_PASSO_PUBLICACAO.md`**. Desenho e decisões em aberto em
> `esboco/Proposta_App_Gestao_Demandas.md`.

## Como abrir o app (local)

**Jeito mais fácil:** dê duplo clique em **`Abrir_App.bat`** (na pasta do
projeto). Abre uma janela preta e, em alguns segundos, o app no navegador em
`http://localhost:8501`. Para fechar o app, feche a janela preta. O app só
funciona enquanto essa janela estiver aberta.

**Pelo PowerShell (para quem desenvolve):**

Python 3.12 em `C:\Users\18-103236\AppData\Local\Programs\Python\Python312\python.exe`
(os aliases `python`/`py` podem não funcionar no PowerShell corporativo — use o
caminho completo).

Na pasta do projeto:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Abre em `http://localhost:8501`. Para fechar: `Ctrl+C` no PowerShell.

Sem `.streamlit/secrets.toml`, o app local grava num banco **só desta máquina**
(`dados_locais/historico.db`) e não pede senha. Para usar o banco do time
localmente, veja o final do `PASSO_A_PASSO_PUBLICACAO.md`.

> **Dado sensível (decisão de 19/10/2026):** banco no Supabase (fora da rede
> Motiva) com o link protegido por senha do time. A planilha tem nomes e temas
> de RH: em temas de RH, prefira o cargo ao nome da pessoa. O `.gitignore` impede
> que a planilha real, a pasta `esboco/`, o banco local e as senhas subam para o
> GitHub.

## Como usar

0. **Topo:** senha do time (no app publicado), nome da área/equipe e **data de
   posição** (padrão: hoje — os prazos são comparados com ela e a importação é
   gravada com ela). **Modo demonstração** carrega duas semanas fictícias num
   banco temporário, sem tocar no banco do time.
1. **📥 Importar planilha atualizada:** preencha seu nome, envie a planilha
   `.xlsx` e confira a **prévia** (novas, atualizadas com o que mudou, sem
   mudança, saíram da planilha, e "parece a mesma demanda com outro nome" para
   confirmar). Só grava ao clicar em **💾 Gravar importação**.
2. **Filtros** de frente e responsável valem para todas as abas e para os
   arquivos exportados. "Incluir as que saíram da planilha" mostra também as
   demandas apagadas do Excel (com o último status conhecido).
3. **📊 Visão geral:** 8 indicadores, status por frente, avanço ponderado por
   frente e pontos de atenção gerados automaticamente.
4. **🗂️ Frentes e entregas:** cada entrega com farol, avanço e prazo final;
   abre para ver as ações (com o último comentário semanal).
5. **👥 Responsáveis:** carga de cada pessoa (ações em aberto, atrasadas, peso
   em aberto); áreas de apoio separadas como dependência externa.
6. **📅 Prazos:** gráfico por semana de prazo + listas de atrasadas, da semana,
   mais adiante e sem prazo.
7. **📝 Pauta semanal:** concluído desde a importação anterior, atrasado,
   compromissos da semana, impedimentos.
8. **🕓 Histórico:** evolução do avanço e das atrasadas por importação, o que
   mudou na última, prazos replanejados, linha do tempo de cada demanda (com
   todos os comentários já registrados), demandas que saíram, lista de
   importações e **desfazer a última importação**.
9. **🔎 Qualidade dos dados:** o que impede um indicador confiável, com **aba e
   linha** da planilha para corrigir.
10. **📑 Exportar:** PowerPoint executivo e base consolidada em Excel.

## Como o app lê a planilha

**Modelo atual (rev.01, desde 21/10/2026)** — uma aba por **frente**:

| Coluna (pelo nome do cabeçalho) | O que o app faz |
|---|---|
| **Título/Tarefa** | `Título` = **entrega** (linha-mãe) · `Tarefa` = **ação** |
| **Tarefa** | nome da entrega ou da ação |
| **Responsável** | um por linha (se houver mais de um, conta para cada um e aparece na aba Qualidade) |
| **Status** | À iniciar / Em andamento / Concluído |
| **Peso** | 1 a 3 (ação sem peso não entra no avanço, como na planilha) |
| **%** | **vale o % digitado** (ex.: 80% em andamento); vazio = 0/50/100% pelo status; Concluído = sempre 100% |
| **Prazo/Conclusão** | prazo da ação (ou data de conclusão, se concluída) |
| colunas com datas (13/10/2026, 20/10/2026...) | comentário da semana; o último preenchido vira "último comentário" e todos ficam no histórico |

- As colunas são encontradas **pelo nome do cabeçalho**, não pela posição: dá
  para inserir ou mover colunas sem quebrar a leitura (renomear o cabeçalho, não).
- Abas sem cabeçalho de tarefas (ex.: **Painel Indicadores**) são ignoradas;
  aba só com o modelo ("TAREFA PRINCIPAL" / "AÇÕES" vazias) aparece como vazia.
- Linha de tarefa sem nome é ignorada (com aviso, se tiver responsável/status).
- As fórmulas de avanço da planilha **não** são usadas: o app recalcula
  Σ(peso × %) ÷ Σ peso.
- **Trava de segurança:** se mais de 30% das ações vierem com status fora da
  lista, a prévia avisa que as colunas não foram reconhecidas e o botão
  **Gravar** fica bloqueado.

**Modelo antigo (até 19/10/2026)** continua aceito: sem a coluna Título/Tarefa,
o tipo da linha vem da formatação (negrito com fundo = entrega, negrito sem fundo
= subgrupo, demais = ação).

## Regras (em `modules/regras.py`)

| Sinal da ação | Regra |
|---|---|
| ✅ Concluída | Status = Concluído |
| ⚠️ Atrasada | Não concluída e data < data de posição |
| ⏰ Vence em 7 dias | Não concluída e data nos próximos 7 dias |
| 🟣 No prazo | Não concluída e data depois de 7 dias |
| ⚪ Sem prazo | Não concluída e sem data |
| ⏳ Aguardando (marcador) | Comentário cita aguardando, chamado, requisição, retorno, em análise, pedido |

Farol da entrega: 🔴 alguma ação atrasada · 🟡 algo vence em 7 dias ou mais da
metade das ações abertas sem prazo · 🟢 no prazo · ✅ todas concluídas.
Janela de dias, áreas de apoio e palavras de "aguardando" são constantes no
topo de `regras.py`.

## Como funciona a memória (em `modules/banco.py` e `modules/historico.py`)

- Três tabelas: **importacoes** (quem, quando, data de posição), **demandas**
  (identidade) e **situacoes** (a foto de cada demanda em cada importação).
- **Identidade da demanda** = frente › entrega › ação (sem acento, minúsculo).
  Quando a chave não bate, a prévia sugere que é a mesma demanda e a pessoa
  confirma: ↪️ mesma ação em outra entrega ou em outra aba (só se o par for
  único) e ✏️ ação renomeada (todas as palavras do nome antigo estão no novo,
  ex.: "Catalogar placas" → "Estoque - Catalogar placas", ou texto ≥ 85% igual).
- Tudo que é histórico é **calculado** a partir das fotos (nada derivado é
  gravado): concluída na última importação, prazo original e quantas vezes
  mudou, data em que entrou, eventos. Por isso **desfazer** é só marcar a
  importação como desfeita.
- Demanda que some da planilha **não é apagada**: fica "fora da planilha" com o
  último status; se voltar, é reconhecida como a mesma.
- No Postgres (Supabase) as tabelas ficam no schema `gestao`, fora da API
  pública do Supabase.

## Estrutura do projeto

```
app.py                  # aplicação Streamlit (interface)
modules/
  importador.py         # leitura da planilha no formato atual
  regras.py             # sinais, farol, avanço, pontos de atenção, carga, pauta
  qualidade.py          # checagens de dados
  banco.py              # memória: grava/lê as importações (Supabase ou SQLite local)
  historico.py          # prévia da importação, estado atual, eventos, evolução
  acesso.py             # senha do time e leitura dos secrets
  exemplo.py            # planilha de exemplo fictícia (mesmo formato)
  export_pptx.py        # relatório executivo em PowerPoint
  export_excel.py       # base consolidada em Excel
tests/test_app.py       # teste automatizado
assets/                 # logo Motiva
dados_exemplo/          # planilha de exemplo fictícia
esboco/                 # proposta e esboço visual (tem dado real -- não sobe)
.streamlit/secrets.toml.exemplo  # modelo das senhas (o secrets.toml real não sobe)
Abrir_App.bat           # abre o app local com duplo clique
PASSO_A_PASSO_PUBLICACAO.md     # contas GitHub/Supabase/Streamlit Cloud
```

## Teste automatizado (antes de publicar qualquer mudança)

```
C:\Users\18-103236\AppData\Local\Programs\Python\Python312\python.exe tests/test_app.py
```

Confere a leitura do formato atual (entregas, subgrupos, linhas-modelo), os
sinais por prazo, o avanço ponderado igual ao da planilha, o farol, a carga por
responsável, as checagens de qualidade, que PPTX e Excel abrem, que o app roda
com o exemplo e que o filtro de frente funciona; e a memória: comparação entre
importações, renomeação aceita/recusada, demanda que sai e volta, desfazer,
persistência em arquivo, modo demonstração isolado do banco do time e a senha.
Usa só bancos temporários (nunca o do time). Se a planilha real estiver na
pasta (`Gestão 4.0 - NTec.xlsx` e `... - rev.01.xlsx`), também confere a
leitura delas (127 ações no rev.01, igual ao Painel Indicadores) e a passagem
de uma para a outra. Termina com `21/21 testes passaram`.

## Próximas fases

Ver `esboco/Proposta_App_Gestao_Demandas.md`, seção 8: planilha modelo com
datas prevista/conclusão separadas e status *Impedido* (Fase 2), curva S com
data de início (resto da Fase 3), leitura direta do SharePoint (Fase 4).
