# Log de Retroanálises — DimConservação

Este arquivo é o histórico (apêndice, nunca sobrescrito) das execuções da rotina
diária de retroanálise do projeto DimConservação. Cada execução acrescenta uma
nova entrada no final, com: resumo do que foi revisado, progresso vs roadmap,
sugestões de melhoria do dia e pendências abertas.

Ver também `perguntas_pendentes.md` (perguntas ao usuário ainda sem resposta).

---

## 2026-09-15 — Reconstrução do projeto (dia 1)

**Contexto:** a pasta original do projeto (`C:\Users\18-103236\Downloads\DimConservacao\`)
e a tarefa agendada `retroanalise-dimconservacao-diaria` foram perdidas — nenhum
arquivo restante foi encontrado em nenhum local do computador. Reconstruído do
zero a partir do prompt da rotina antiga + memória de projetos anteriores
(SPVias, RioSP FS 4.0, Mitigação AutoBAn, Mecanização) + esclarecimentos do
usuário nesta conversa.

**Decisões fechadas com o usuário:**
- Projeto agora vive em `C:\Users\18-103236\OneDrive - Motiva\Área de Trabalho\Dim.Conserva\`
  (OneDrive, com backup automático — antes era só em Downloads local, o que
  provavelmente contribuiu para a perda).
- Stack: Python + Streamlit (mantido do projeto original).
- Publicação-alvo: Streamlit Community Cloud (gratuito, link direto, zero
  instalação) — **decisão tomada relaxando a restrição de dados só-local, válida
  apenas para o piloto com dados fictícios**; precisa ser revisitada antes de
  usar dados reais de contrato (ver pendência abaixo).
- Inventário mínimo: `trecho`, `km_inicial`, `km_final`, `area_verde_m2` (SEM
  itens de pavimento) + colunas opcionais para EPS/barreira, defensa, placas,
  bueiros, calçada.
- Lógica de dimensionamento: equipes = (quantidade × ciclos/ano) ÷ (produtividade
  diária × dias úteis disponíveis no período), calculado separadamente para
  cenário chuva e seca (mostrados lado a lado, não só o pico).
- Tipos de contrato suportados nesta v1: **Full Service** (pacote fechado:
  roçada + aceiro + drenagem + capina + refilamento + calçada + placas +
  remoção de lixo) e **Especialistas** (EPS/barreira, defensa metálica, NC,
  varrição, poda).
- Produtividade: valores-padrão sugeridos e editáveis (não começa zerado).
- Relatório de saída: só PowerPoint (paleta Motiva, roxo 5E22F3).

**O que foi construído hoje:**
- `app.py` — interface Streamlit com 7 abas (Inventário, Roçada Manual, Roçada
  Mecanizada, Full Service, Especialistas, Análise de Contrato, Exportar
  Relatório).
- `modules/dimensionamento.py` — motor de cálculo genérico (mesma fórmula usada
  nos estudos SPVias/RioSP).
- `modules/parametros_padrao.py` — valores-padrão de produtividade/ciclos/metas,
  cada um marcado com a fonte (`referencia` = veio de estudo real documentado
  na memória; `estimativa` = genérico, precisa validação).
- `modules/inventario.py` — leitura/validação da planilha + gerador de
  inventário de exemplo (fictício) para demonstração.
- `modules/export_pptx.py` — geração do relatório executivo `.pptx`.
- `README.md` — instruções completas de instalação/uso/publicação para usuário
  leigo.
- Testado ponta a ponta no navegador (inventário de exemplo → roçada manual
  chuva/seca com números conferidos manualmente → Full Service → exportação do
  PPTX): tudo funcionando sem erro.

**Progresso vs roadmap:** o `Roadmap_DimConservacao_2026.pptx` também foi
perdido e ainda não foi recriado — não é possível comparar com precisão o
progresso vs as 4 fases sem ele (ver pendência). Pelo que se sabe do prompt
original, estamos ainda ANTES da Fase 1 (Validação com Dados Reais, Jun/2026):
hoje o app só tem dados fictícios e boa parte dos parâmetros de produtividade é
estimativa não validada.

**Sugestões de melhoria (para próximas rodadas):**
1. Validar com o time técnico (ex: Marcos, citado nas memórias de RioSP como
   referência de campo) os valores de produtividade marcados "estimativa" em
   `parametros_padrao.py` — são a maior fonte de erro potencial do
   dimensionamento hoje.
2. Recriar (ou obter) o `Roadmap_DimConservacao_2026.pptx` para permitir
   acompanhamento de fase por fase nas próximas retroanálises.
3. Resolver a decisão de hospedagem definitiva (Streamlit Cloud externo vs.
   alternativa interna Motiva) antes de qualquer dado real de contrato entrar
   no app — hoje só dados fictícios devem ser usados.

**Pendências abertas:** ver `perguntas_pendentes.md`.

---

## 2026-09-17 — Revisão técnica de rotina (dia 2)

**Contexto:** execução automática agendada, sem interação do usuário nesta
conversa. Nenhuma das 5 perguntas pendentes de 2026-09-15 foi respondida ainda
(nem em conversa, nem no `perguntas_pendentes.md`) — todas seguem em aberto.

**Revisão técnica:** `ast.parse` (UTF-8) em `app.py` e nos 4 módulos de
`modules/` — todos sem erro de sintaxe. Não foram encontrados bugs funcionais.
Único achado: `import math` em `app.py` estava sem uso (o cálculo já é feito
via `modules/dimensionamento.py`, que importa `math` internamente) — removido
por ser código morto trivial. Após a remoção, `ast.parse` revalidado (OK) e o
app foi subido (`streamlit run app.py --server.port 8501`) só para confirmar
HTTP 200 na porta local; respondeu 200 normalmente e o processo de teste foi
encerrado em seguida.

**Portabilidade:** sem mudanças. `requirements.txt` continua só com pacotes
gratuitos/open-source (`streamlit`, `pandas`, `openpyxl`, `python-pptx`), sem
nada pago/licenciado. `.streamlit/config.toml` não tem caminho específico de
máquina. Pasta do projeto ainda não é um repositório git (confirmado hoje) —
isso é pré-requisito para a publicação no Streamlit Cloud (pergunta pendente
nº 5) quando o usuário decidir criar as contas GitHub/Streamlit.

**Documentação:** `README.md` seguiu revisado e completo (instalação,
dependências, uso de cada aba, publicação, ambiente conhecido) — nenhuma
lacuna nova identificada hoje. Não houve alteração.

**Progresso vs roadmap — ALERTA DE PRAZO:** o `Roadmap_DimConservacao_2026.pptx`
continua sem ser encontrado/recriado (pendência recorrente, ver pergunta nº 3).
Usando as datas de referência do prompt da rotina: a Fase 1 (Validação com
Dados Reais) tinha como marco **Jun/2026**, que já passou — e hoje (17/09/2026)
já estamos dentro da janela nominal da Fase 3 (Set-Out/2026). Porém o estado
funcional real do app é de **pré-Fase 1**: só dados fictícios, maior parte dos
parâmetros de produtividade ainda marcada "estimativa (a validar)", sem
hospedagem definitiva e sem repositório/versionamento. Isso configura risco
alto de atraso generalizado em todas as fases seguintes — não é um atraso
pontual de uma entrega, é uma defasagem estrutural entre o cronograma original
e o estado atual do projeto (agravada pela perda e reconstrução do projeto em
15/09/2026). Recomenda-se re-baselinar o roadmap com o usuário assim que o
PPTX for recriado ou substituído (pergunta nº 3), em vez de tentar "recuperar"
as datas originais.

**Sugestões de melhoria de hoje (priorizadas por impacto):**
1. **Re-baselinar o roadmap** com o usuário — as datas de Jun/Jul/Set/Nov de
   2026 não refletem mais a realidade pós-reconstrução; sem isso, toda
   comparação futura de "progresso vs fase" desta rotina fica sem base sólida.
2. **Validar produtividade real** (perguntas 1 e 2 pendentes) continua sendo o
   maior risco técnico do dimensionamento — nenhuma resposta ainda recebida.
3. **Iniciar versionamento git local** da pasta do projeto (mesmo antes de
   decidir GitHub/Streamlit Cloud) — reduz o risco de nova perda de trabalho
   como a de 15/09/2026 e é pré-requisito técnico para a futura publicação.

**Pendências abertas:** as 5 perguntas de 2026-09-15 seguem todas sem resposta
— ver `perguntas_pendentes.md`.

---

## 2026-09-17 — Ajuste de rota da rotina (mesmo dia, após retorno do usuário)

**Decisão do usuário:** pausar a comparação de progresso vs roadmap de fases
nesta rotina. Foco agora é deixar o aplicativo o mais "redondo" possível —
entender a fundo a funcionalidade de cada aba, levantar melhorias concretas de
produto/UX/lógica, e construir isso em conjunto com o usuário (propor,
perguntar, ajustar com o retorno dele) antes de propor roadmap e próximos
passos. A rotina agendada (`SKILL.md` da tarefa
`retroanalise-dimconservacao-diaria`) foi ajustada para refletir essa ordem de
prioridade: revisão funcional > técnica > portabilidade > documentação >
melhorias de produto > (roadmap pausado) > perguntas > log > resumo. O roteiro
de fases não foi apagado, só pausado — retomamos quando o usuário pedir.

---

## 2026-09-17 — Sessão de brainstorming de melhorias (mesmo dia, continuação)

**Contexto:** usuário confirmou que conseguiu abrir e rodar o app localmente
(usando o comando correto com caminho completo do Python). Achou a interface
pouco intuitiva ainda, mas topou construir aos poucos. Trouxe 5 ideias de
melhoria de produto em um brainstorming livre, capturadas e estruturadas no
novo arquivo `retroanalises/melhorias_propostas.md` (backlog vivo de produto,
separado do log e das perguntas pontuais):

1. Inventário: % de área manual x mecanizada por trecho (hoje cada modalidade
   é calculada como se cobrisse 100% da área verde — duplicação incorreta).
2. Camada de dados de recorrência/histórico por atividade (ex: acionamentos de
   EPS/barreira e defensa, volume e características de NC), importada junto
   com o inventário, para calibrar os parâmetros de ciclos/meta com dado real
   da unidade quando existir.
3. Relatório PPTX mais rico (não mais longo): matriz de risco
   probabilidade×impacto, componente financeiro (peso em R$ do contrato),
   sumário executivo, indicadores visuais de conformidade.
4. Identidade visual Motiva: logo no app e no relatório.
5. Aprofundar uso de dados sem depender de API — em especial, taxa de
   crescimento de vegetação por região (hoje o dimensionamento usa só ciclos
   fixos/teóricos) e a fonte de mapeamento por satélite que a Motiva já usa em
   outros projetos (conecta com o item 1).

Nenhum código foi alterado ainda — os itens 1, 2, 4 e 9 (financeiro) dependem
de decisões/dados do usuário antes de implementar (perguntas 6 a 9 registradas
em `perguntas_pendentes.md`). O item 3 (relatório mais rico) e parte do item 5
podem começar a ser desenhados mesmo sem a resposta, na próxima sessão.

**Pendências abertas:** perguntas 1-5 (2026-09-15) seguem sem resposta; novas
perguntas 6-9 (2026-09-17) adicionadas — ver `perguntas_pendentes.md`.

---

## 2026-09-17 — Respostas do usuário e item liberado para implementação

Usuário respondeu às perguntas 6, 7 e 9 do mesmo dia (ver seção "Respondidas"
em `perguntas_pendentes.md`):
- **% manual x mecanizada (pergunta 6):** sempre soma 100%; mapeamento real já
  existe e pode ser extraído do sistema como planilha Excel — **item 1 do
  backlog agora está pronto para implementação técnica** (só falta a planilha
  real chegar para validar o formato exato de coluna).
- **Recorrência EPS/defensa/NC (pergunta 7):** direção definida — usar uma taxa
  de manutenção por volume vs. capacidade da equipe, em vez de importar
  histórico bruto de eventos. Simplifica a implementação futura. Valor real da
  taxa ainda pendente.
- **Financeiro (pergunta 9):** confirmado que cada contrato tem preço unitário
  por equipe/mês — dá para incorporar ao relatório quando os valores forem
  levantados.
- **Logo da Motiva (pergunta 8):** usuário colou a imagem na conversa (duas
  versões: roxa sobre fundo claro, branca sobre fundo roxo), mas uma imagem
  colada no chat não é salva automaticamente em disco — pedido para o usuário
  salvar o arquivo fisicamente para eu poder referenciá-lo no código.

Nenhum código foi alterado ainda nesta entrada — próxima sessão pode começar a
implementação do item 1 (divisão manual x mecanizada) e do componente
financeiro básico do relatório, que já não dependem mais de decisão do
usuário.

---

## 2026-09-17 — Implementação: Quasar + logo Motiva (mesmo dia, continuação)

Usuário enviou os arquivos reais: 2 planilhas de export Quasar (mapeamento de
área manual x mecanizada por satélite, `dados_quasar/QUASAR_AB.xlsx` e
`QUASAR_SOROCABANA.xlsx` — juntas, ~8.100 polígonos reais cobrindo 13
rodovias) e as 2 versões da logomarca Motiva (`assets/logo_motiva_branca.png`,
`assets/logo_motiva_roxa.png`).

**Implementado e testado nesta sessão:**
1. **Item 1 do backlog (manual x mecanizada) — concluído.** Novo módulo
   `modules/quasar.py` lê o export Quasar (detecta a aba de dados
   automaticamente, robusto a variação de nome de coluna entre regionais) e
   agrega os polígonos por rodovia + faixa de km em linhas de inventário com
   `area_verde_m2`/`pct_manual`/`pct_mecanizada`. Nova seção na aba Inventário
   do app para fazer esse upload. `modules/inventario.py` ganhou
   `area_por_modalidade()` e as abas Roçada Manual/Mecanizada passaram a usar
   essa ponderação (com fallback 100%/100% — cenário isolado — quando o
   inventário não tem os percentuais, sem quebrar inventários antigos).
   Testado: sintaxe OK, fluxo completo Quasar→inventário→dimensionamento
   rodado com os 2 arquivos reais (soma manual+mecanizada bate com a área
   total), navegador testado com inventário de exemplo sem regressão. Upload
   real do Quasar não pôde ser testado via automação de navegador (sem suporte
   a seletor de arquivo do SO) — validado por script Python direto.
2. **Item 4 do backlog (logo Motiva) — concluído.** `st.logo()` no app,
   logo branca na capa do PPTX (fundo roxo) e logo roxa no rodapé de todos os
   slides de conteúdo. Testado: PPTX de teste gerado com 1 imagem de logo por
   slide, sem erro.
3. **Item 2 do backlog (taxa de manutenção EPS/defensa) — proposta técnica
   entregue, aguardando validação.** Em vez de implementar a taxa simples que
   o usuário sugeriu, propus reaproveitar o padrão já usado pela atividade NC
   (modelo de demanda reativa por incidência, em vez do modelo cíclico
   preventivo) — detalhado em `melhorias_propostas.md` item 2 e
   `perguntas_pendentes.md`. Ainda não implementado (é mudança de UX, não só
   valor de parâmetro).

**Segurança de dados:** os arquivos Quasar reais (`dados_quasar/`) contêm dado
operacional real de contrato Motiva (coordenadas, % mecanização por trecho).
Adicionei `dados_quasar/` ao `.gitignore` preventivamente, já que a decisão de
hospedagem para dados reais (pergunta 4, ainda em aberto) não está resolvida
— evita que esses dados vazem para um repositório remoto se o usuário
inicializar o git antes de resolver essa pendência.

**Pendências abertas:** perguntas 1-5 (2026-09-15, valores reais de
produtividade) seguem sem resposta; pergunta 7-continuação (validação da
proposta de taxa reativa) aguardando resposta do usuário — ver
`perguntas_pendentes.md`.

---

## 2026-09-18 — Revisão funcional de rotina (dia 3, execução automática)

**Contexto:** execução automática agendada, sem interação do usuário nesta
conversa. Seguindo o ajuste de rota de 2026-09-17: foco em revisão funcional
das 7 abas primeiro, roadmap/fases seguem pausados.

**Revisão funcional — achado principal:** a aba **Roçada Mecanizada** calcula
corretamente a necessidade por tipo de equipamento, mas (diferente da Roçada
Manual) nunca salva o resultado em `st.session_state`. Consequência prática:
a Roçada Mecanizada não aparece nem na aba **Análise de Contrato** nem no
**relatório PPTX exportado** — o usuário pode calcular tudo certo nessa aba e
o relatório final sai incompleto sem nenhum aviso de erro. Não é um bug de
código morto trivial (não dá pra simplesmente copiar o padrão da Manual)
porque a Mecanizada calcula por tipo de equipamento como alternativas
independentes, não um único número de pico. Documentado como item 6 do
backlog (`melhorias_propostas.md`) e pergunta 10 (`perguntas_pendentes.md`) —
aguardando decisão do usuário sobre como representar isso antes de
implementar.

Demais abas revisadas (Inventário, Roçada Manual, Full Service, Especialistas,
Análise de Contrato, Exportar Relatório) — fluxo coerente, mensagens de aviso
adequadas quando falta inventário, fonte de cada parâmetro visível. Nenhum
outro problema funcional grave identificado hoje.

**Revisão técnica:** `ast.parse` (UTF-8) em `app.py` e nos 5 módulos de
`modules/` (incluindo `quasar.py`, novo desde 17/09) — todos sem erro de
sintaxe. Único achado: duas variáveis mortas na aba Roçada Mecanizada de
`app.py` (`total_equipes_pico` e `melhor_cenario`, atribuídas mas nunca
usadas) — removidas. Revalidado com `ast.parse` (OK) e o app foi subido
(`streamlit run app.py --server.port 8501`) só para confirmar HTTP 200;
respondeu 200 normalmente e o processo de teste foi encerrado em seguida.

**Portabilidade:** sem mudanças. `requirements.txt` continua só com pacotes
gratuitos/open-source, nada pago/licenciado. Pasta ainda não é repositório
git (mesma pendência de 17/09, nº 5).

**Documentação:** `README.md` estava desatualizado desde a implementação do
Quasar/logo (17/09) — não mencionava a seção de importação Quasar na aba
Inventário nem as pastas `assets/`, `dados_quasar/` e
`retroanalises/melhorias_propostas.md` na estrutura do projeto. Atualizado
hoje (mudança pequena e segura, só documentação).

**Sugestões de melhoria de produto priorizadas hoje (por impacto em deixar o
app redondo):**
1. **Resolver a lacuna da Roçada Mecanizada** (achado principal acima) — é a
   maior inconsistência funcional encontrada até agora: uma aba inteira de
   cálculo "invisível" no relatório final. Aguardando resposta do usuário
   (pergunta 10).
2. Seguir os itens já em aberto do backlog: item 2 (taxa de manutenção
   EPS/defensa — proposta técnica pronta, aguardando validação, pergunta 7) e
   item 3 (relatório executivo mais rico — matriz de risco, componente
   financeiro, sumário executivo).
3. Item 5 do backlog (taxa real de crescimento de vegetação por região) segue
   como melhoria de precisão de médio prazo, sem decisão/dado necessário
   ainda para começar a desenhar.

**Pendências abertas:** perguntas 1-5 (2026-09-15) e 7-continuação (taxa
reativa EPS/defensa) seguem sem resposta; nova pergunta 10 (2026-09-18,
representação da Mecanizada) adicionada — ver `perguntas_pendentes.md`.

---

## 2026-09-18 — Sessão de ajustes com o usuário (mesmo dia, continuação)

**Contexto:** o usuário revisou o resultado da execução automática de hoje e
trouxe um lote grande de feedback de produto/design em uma única mensagem.
Implementado nesta sessão (todos validados com `ast.parse` + teste funcional
com dados reais, quando aplicável):

1. **Bug crítico corrigido — extração de rodovia no Quasar
   (`modules/quasar.py`).** O código extraía a rodovia do 1º token do ID
   Motiva, o que já funcionava para o arquivo Sorocabana, mas uma primeira
   tentativa de correção (escanear todos os tokens por um padrão genérico
   "2 letras + dígitos") criou um bug pior: tokens do meio do ID como
   `CL11`/`CC2` (canteiro lateral/central) eram confundidos com rodovias,
   fragmentando a `SP-330` em dezenas de "rodovias" falsas (`CL-10` a
   `CL-23`). Corrigido para olhar só o 1º token, removendo o prefixo `VG`
   quando colado direto no código (`VGSP-330` → `SP-330`). **Validado com os
   2 arquivos reais:** rodovias do arquivo AB agora saem limpas (SP-102,
   SP-300, SP-330, SP-348, sem fantasmas) e a extensão total caiu de 246,5 km
   (com o bug) para 157,0 km (correta) — uma correção de ~36%.
2. **Extensão do Quasar agora conta segmentos distintos, não soma bruta.**
   Cada km físico de rodovia tem vários polígonos (canteiro lateral nos dois
   sentidos + canteiro central) — `agregar_por_trecho` agora conta posições
   de km distintas (`nunique`) em vez de somar o comprimento de cada polígono,
   evitando inflar a extensão. `inventario.preparar_inventario` ajustado para
   respeitar essa extensão pré-calculada em vez de recalcular ingenuamente.
   Área verde continua somando normalmente (aditiva, correta desde a v1).
3. **Resumo de % manual x mecanizado da concessionária** — novo bloco de
   métricas na aba Inventário (quando há `pct_manual`/`pct_mecanizada`),
   ponderado pela área de cada trecho, além do detalhamento por trecho que já
   existia.
4. **Terminologia: "roçadores" em vez de "equipes" na Roçada Manual.** A
   produtividade da Roçada Manual é por colaborador individual, não por
   equipe — a Análise de Contrato (e o PPTX) agora usam "roçador(es)" para
   essa modalidade e "equipe(s)" para as demais (Full Service/Especialistas).
5. **Full Service — Aceiro, Drenagem de plataforma e Drenagem fora de
   plataforma ganharam coluna de inventário própria** (`aceiro_km`,
   `drenagem_plataforma_km`, `drenagem_fora_plataforma_km`) em vez de usar a
   extensão total da rodovia — esses serviços não cobrem 100% da rodovia
   (trechos urbanos/APP ficam de fora). A aba também ganhou campo de
   quantidade editável manualmente (mesmo padrão já usado em Especialistas),
   já que a maioria das planilhas ainda não vai ter essas colunas novas.
6. **PPTX — logo não fica mais coberta pela tabela.** A logo estava no
   rodapé (posição fixa), e uma tabela comprida (Full Service + Especialistas
   juntos numa tabela só) podia sobrepor. Reposicionada para o canto superior
   direito (ao lado do título, nunca coberta por conteúdo) e o relatório
   agora gera um slide por grupo de atividade (Full Service, Especialistas)
   em vez de uma tabela única gigante — mais alinhado a um deck executivo.
   Testado: PPTX de teste gerado com 5 slides, logo presente em todos.
7. **Primeiro passo de identidade visual na interface.** CSS leve aplicado
   (cards de métrica com fundo lavanda/borda roxa, títulos em roxo escuro,
   abas com destaque) — polimento inicial, não um redesign completo; próximos
   incrementos dependem de feedback do usuário sobre essa direção.

**Conhecimento de domínio capturado na memória persistente** (para não se
perder entre sessões): estrutura física do Quasar (canteiro lateral/central,
sentidos, formato real do ID Motiva — ver `project_quasar_estrutura_dados`
na memória), terminologia roçadores x equipes, granularidade de inventário
por atividade Full Service, e a diretriz de design (executivo no PPTX,
"gourmetização" da interface).

**Pendências abertas:** ver perguntas 11-13 novas em `perguntas_pendentes.md`
(confirmação dos códigos de rodovia extraídos, origem dos dados reais de
aceiro/drenagem, validação do resumo % manual x mecanizado). Perguntas
1-5, 7-continuação e 10 seguem sem resposta.

---

## 2026-09-18 — Segunda rodada de ajustes com o usuário (mesmo dia, continuação)

**Contexto:** usuário trouxe mais uma leva de melhorias de produto. Todas
implementadas e testadas nesta sessão (sintaxe + fluxo real + app aberto no
navegador, sem erros no console):

1. **Planilha modelo para download (aba Inventário).** Quando não há
   mapeamento Quasar disponível, o usuário pode baixar um `.xlsx` modelo
   (`inv.gerar_planilha_modelo()`) com a aba "Inventario" (só cabeçalho, todas
   as colunas mínimas + opcionais, incluindo as novas de aceiro/drenagem) e
   uma aba "Instruções" explicando cada coluna (obrigatória ou não). O texto
   solto "Colunas mínimas necessárias: ..." foi removido da interface — essa
   informação agora vive dentro do arquivo modelo.
2. **Removida a frase "versão piloto (dados fictícios)"** do subtítulo do
   app, já que dados reais (Quasar) já estão em uso. O botão "Usar inventário
   de exemplo (dados fictícios)" foi mantido como estava (pedido explícito do
   usuário).
3. **Composição real de equipe + proposta de divisão por trecho (Roçada
   Manual).** Uma equipe tem 9 colaboradores, mas só 6 fazem roçada (1
   motorista + 2 em atividades complementares) — editável na interface
   (`pp.COMPOSICAO_EQUIPE_ROCADA_MANUAL`, padrão 9/6). Nova função
   `dim.propor_divisao_por_trecho()` agrupa trechos consecutivos (por km) até
   a capacidade de uma equipe por ciclo, propondo qual equipe cobre qual
   trecho contínuo — e divide automaticamente um trecho que sozinho já
   excede a capacidade de uma equipe em partes iguais (ex: "Trecho 2 (parte
   1/2)"), em vez de estourar 100% de ocupação. Testado com o inventário de
   exemplo (3 trechos grandes → 5 equipes, todas ≤100% de ocupação, batendo
   com a estimativa simples de colaboradores÷6) e com o Quasar real AB (146
   colaboradores → 34 equipes propostas, mais que a estimativa simples de 25
   porque o algoritmo prioriza manter cada equipe num trecho contínuo — isso
   é esperado e está explicado na própria interface).
4. **Mesma lógica replicada na Roçada Mecanizada.** A seção "Maior trecho"
   (só 1 ponto) virou um ranking dos 5 trechos de maior demanda mecanizada, e
   cada tipo de equipamento ganhou um expansor com a proposta de divisão de
   trechos entre as unidades necessárias daquele equipamento (mesma função
   `propor_divisao_por_trecho`). Testado visualmente: Giro Zero com 2
   unidades propostas, cobrindo Trecho1+2 (95% de ocupação) e Trecho3 (67%).

**Teste de UI no navegador:** app aberto localmente (porta 8503), inventário
de exemplo carregado, abas Roçada Manual e Roçada Mecanizada navegadas e
expansores abertos — tudo renderizando corretamente, sem erros no console do
navegador. Processo de teste encerrado ao final.

**Pendências abertas:** ver perguntas 11-13 (rodada anterior) ainda sem
resposta. Nenhuma pergunta nova nesta rodada — os itens pedidos foram
suficientemente claros para implementar diretamente.

---

## 2026-09-21 — Retroanálise diária (foco: funcionalidade; roadmap pausado)

**Contexto:** nenhuma resposta nova do usuário desde 2026-09-18 (perguntas 1-5,
7-cont., 10-13 seguem abertas). Código não havia mudado desde 09-18. Sintaxe OK
em `app.py` e todos os `modules/` (`ast.parse` UTF-8).

**Revisão funcional (leigo, primeira vez):**
- **Análise de Contrato:** "Contratado" inicia igual ao dimensionado → tudo "Conforme"
  por padrão; e a `key` fixa pode manter valor antigo se o dimensionado mudar. Só
  mostra déficit em unidades, sem % nem semáforo. (Backlog 17, 18; pergunta 14.)
- **Roçada Mecanizada:** continua ausente da Análise de Contrato e do PPTX (item 6,
  pergunta 10 ainda sem resposta) — é a maior incoerência entre abas hoje.
- **Meses sazonais:** nenhuma validação de chuva+seca = 12 nas abas de cálculo
  (erro silencioso). **Corrigido** (backlog 16).
- **Exportar:** nome do arquivo usava só `replace(' ', '_')` — contrato com `/` ou `:`
  quebraria o download. **Corrigido.**
- Full Service/Especialistas/Inventário: coerentes entre si; Especialistas rotula
  "Cenário 1/2" enquanto o relatório usa Chuva/Seca (inconsistência menor).

**Mudanças de código (pequenas):** `app.py` — função `avisar_meses()` chamada nas 4
abas, `re.sub` no nome do PPTX; `requirements.txt` — `streamlit>=1.50` (app usa
`width='stretch'`). **Validado:** AppTest do Streamlit roda o script sem exceção e
dispara o aviso ao colocar 9+7 meses; servidor em `--server.port 8511` respondeu
HTTP 200 (health OK) e foi encerrado.

**Portabilidade:** nenhuma dependência nova nem paga; tudo Python puro (streamlit,
pandas, openpyxl, python-pptx). Pendência aberta segue a mesma: hospedagem para
dados reais (pergunta 4). `dados_quasar/` está no `.gitignore` (ok).

**Documentação:** README segue coerente com o app; falta um mini "primeiro uso em 5
passos" e menção ao aviso de meses — evoluir na próxima rodada.

**Sugestões do dia:** (1) tornar "Contratado" neutro até preenchimento + desvio %
com semáforo (17/18); (2) resolver Mecanizada na Análise/PPTX (pergunta 10);
(3) gráfico pizza manual × mecanizado no Inventário (passo 2 da interface, item 12).

**Pendências abertas:** perguntas 1-5, 7-cont., 10-14.

---

## 2026-09-21 (tarde) — Rodada de melhorias pedidas pelo usuário

**Pedido:** unidade avaliada; auditoria do Quasar (extensão); só 2 modalidades na roçada manual; divisão de equipes com máximo aproveitamento e sinergia; textos com atualização automática; mecanização com equipamento ideal por trecho; memória de cálculo em Excel; planilha modelo formatada. Detalhe em `melhorias_propostas.md` itens 19–26.

**Achado mais importante (autocorreção):** a auditoria mostrou que a extensão do Quasar AB que eu tinha validado em 09-18 como "157,0 km (a correta)" estava **pela metade**. Causa: usei o comprimento do polígono (0,5 km) como passo entre posições, mas no AB os polígonos estão a cada 1,0 km. Extensão correta: 314 km (SP-330 148 + SP-348 158 + SP-102 6 + SP-300 2), coerente com a contagem de km de canteiro central da própria planilha do usuário (157/73/6/2). Sorocabana: 447 km. Novo critério: extensão = (último km − primeiro km) + passo mediano entre posições, por rodovia. Consequência derivada: o AB mapeia só 50% de cada km — a área verde pode estar subestimada (pergunta 15).

**Divisão de equipes:** algoritmo trocado (enchimento contínuo com corte de trecho no km) — AB: 14 equipes (antes 34), 13 a 100%. Bug corrigido de passagem: trechos eram ordenados por texto ("km 100" antes de "km 11").

**Mecanização:** frota mista somável por equipamento (resolve item 6 / pergunta 10 sem depender da resposta); equipamento recomendado por trecho a partir da indicação do Quasar (mix, largura, inclinação); alerta de subutilização.

**Validação:** ast.parse OK em todos os módulos; AppTest do Streamlit rodou o app inteiro sem exceção com Quasar AB, Quasar Sorocabana (via uploader simulado) e inventário de exemplo; servidor respondeu HTTP 200 e foi visto no navegador; fórmulas do Excel recalculadas com motor independente (biblioteca `formulas`) batem 9/9 com o app. Não testado: abrir a memória de cálculo no Excel de verdade (sem Excel/LibreOffice na máquina) e o upload real de arquivo pelo navegador.

**Limitações/observações:** produtividades dos equipamentos são estimativas minhas (pergunta 16); `download_button` com função exige Streamlit ≥ 1.52 (requirements ajustado, versão mínima não confirmada em changelog); a divisão pode juntar rodovias distintas numa equipe (sinalizado; pergunta 18).

**Pendências abertas:** perguntas 1-5, 7-cont., 10-18 (10 fica parcialmente resolvida pela frota mista — aguardando confirmação do usuário).

---

## 2026-09-21 (noite) — Correção: erro ao gerar inventário do Quasar + mensagens em português

**Relato do usuário:** ao clicar em "Gerar inventário a partir do Quasar" apareceu `agregar_por_trecho() takes 1 to 2 positional arguments but 3 were given`.
**Causa:** o servidor Streamlit estava aberto enquanto o código era atualizado; os módulos `modules/*` continuaram em memória na versão antiga (2 argumentos), enquanto o `app.py` novo chamava com 3. O arquivo em disco estava correto (testado com AppTest).
**Correções:** (1) `app.py` recarrega (`importlib.reload`) os módulos a cada execução — o app nunca mais roda código antigo por ter sido atualizado com a tela aberta; (2) as funções em cache incluem `quasar.VERSAO` na chave, evitando reaproveitar DataFrame gerado por versão antiga (faltaria `largura_m`/`inclinacao`); (3) novo `modules/erros.py` traduz erros técnicos (arquivo não é .xlsx, coluna ausente, texto em coluna numérica, arquivo aberto em outro programa, versão antiga em memória, etc.) para português com orientação, mantendo o detalhe técnico num expansor "Detalhe técnico (para suporte)". **Testado:** fluxo Quasar AB sem erro; arquivo inválido gera mensagem em português.
**Ação do usuário:** fechar o PowerShell do app e abrir de novo (`python -m streamlit run app.py`) para pegar o código novo na primeira vez.

---

## 2026-09-22 — Retroanálise diária (foco: funcionalidade; roadmap pausado; nenhuma alteração de código)

**Contexto:** nenhuma resposta nova do usuário desde 2026-09-18/21 (perguntas 1-5,
7-cont., 10-18 seguem abertas). Código não mudou desde 2026-09-21 (noite).
Sintaxe OK em `app.py` e todos os `modules/` (`ast.parse` UTF-8, 9 arquivos).
Como nenhuma alteração de código foi feita nesta execução, o app não foi
subido (regra da rotina: só rodar se algo mudou).

**Revisão funcional (leigo, primeira vez) — releitura completa de `app.py`
(abas Inventário, Roçada Manual, Roçada Mecanizada, Full Service,
Especialistas, Análise de Contrato, Exportar):**
- As 7 abas estão coerentes entre si, com validação de inventário ausente
  (`st.warning` orientando a carregar antes), mensagens de erro traduzidas
  (`modules/erros.py`), e textos/números realmente recalculados a cada
  interação (conferido lendo o código, não só a documentação).
- **Achado (documentação desatualizada, não bug):** o item 18 do backlog
  ("mostrar % de desvio e semáforo") estava marcado `[ ]`, mas o % de desvio
  já está implementado e funcionando (`app.py:747-759`) — herdado até no PPTX.
  Só falta a parte de cor por faixa de severidade (hoje é binário: vermelho
  para qualquer déficit, azul para qualquer excedente). Corrigido o status no
  backlog para `[~]` e registrada a pergunta 19 (limiares 5%/15% foram um
  chute meu, preciso confirmar antes de colorir).
- **Item 17 (campo "Contratado" pré-preenchido igual ao dimensionado) segue
  sem correção** — confirmado que o código ainda usa `value=int(dimensionado)`
  com `key` fixa (`app.py:747`). Não mexi porque a pergunta 14 (like começar
  vazio, ou subir planilha do quadro contratado) ainda não tem resposta e
  qualquer uma das 3 opções é uma mudança de comportamento visível — prefiro
  esperar a decisão a escolher por conta própria.
- **Especialistas rotula "Cenário 1/2"** enquanto Manual/Mecanizada/Full
  Service usam "Chuva/Seca" — revisitei este ponto (marcado como
  "inconsistência menor" em 2026-09-21) e decidi NÃO uniformizar: Especialistas
  inclui NC, que é demanda distribuída no ano (12/12), não sazonal — forçar o
  rótulo "Chuva/Seca" ali seria semanticamente errado. Mantido como está.
- **README** já resolveu o gap apontado ontem ("falta mini primeiro uso em 5
  passos") — o "Como usar" tem passo 0-7 numerados, incluindo o aviso de meses
  sazonais implícito no fluxo. Nenhuma ação necessária.

**Revisão técnica:** nenhum `TODO`/`FIXME`/`except` genérico fora do único
`except Exception` já existente e intencional (`app.py:265`, com fallback
seguro para 100% de cobertura ao falhar a auditoria prévia do Quasar). Nenhum
código morto óbvio encontrado nesta passada.

**Portabilidade:** sem dependências novas, pagas ou específicas de máquina.
Pendência de hospedagem para dados reais (pergunta 4) inalterada.

**Sugestões de melhoria do dia (produto, priorizadas por impacto em "app
redondo"):**
1. **Cor por faixa no desvio (item 18)** — baixo esforço, alto impacto
   executivo; só falta confirmar os limiares (pergunta 19).
2. **Decidir o comportamento do campo "Contratado" (item 17 / pergunta 14)** —
   é o maior risco de leitura errada do app hoje (usuário lê "✅ Conforme" sem
   ter informado nada); só precisa de uma escolha entre as 3 opções já
   propostas para eu implementar.
3. Nenhum item novo de funcionalidade surgiu nesta rodada — o backlog já
   cobre bem o que falta; o gargalo agora é resposta do usuário às perguntas
   represadas (14, 15, 16, 17, 18), não falta de análise.

**Pendências abertas:** perguntas 1-5, 7-cont., 10-20 (19 e 20 novas nesta
rodada). Nenhuma mudança de código hoje.

---

## 2026-09-22 (tarde) — Usuário respondeu 15 perguntas represadas (1, 2, 3, 4, 5, 7-cont., 10-19)

**Contexto:** o usuário passou por praticamente todas as perguntas em aberto
de uma vez, em áudio transcrito. Resumo das decisões (detalhe completo, com o
texto de cada resposta, está em `perguntas_pendentes.md`, seção Respondidas):

- **1, 16** (produtividade real roçada/equipamentos): manter estimativa
  editável — o usuário de cada unidade ajusta quando tiver o dado real. Sem
  mudança de código (já era assim).
- **2, 3** (metas Full Service, roadmap): em stand-by, sem prioridade agora.
- **4, 5** (hospedagem): manter Streamlit Community Cloud; usuário vai criar
  as contas GitHub/Streamlit, pediu instruções — **README atualizado** com
  passo a passo completo de criação de conta e publicação (seção
  "Publicação"). Esclarecido que o "trabalho extra com Python" de hoje é só
  do ambiente de desenvolvimento, não se repete para quem usa o link
  publicado — não há necessidade de reescrever o app como página estática.
- **7 (continuação)** (taxa reativa EPS/defensa): aprovado ("vamos testar esse
  modelo"). **Implementado:** seletor Preventivo/Reativo na aba Especialistas
  para EPS/barreira e defensa metálica (`app.py`, `modules/parametros_padrao.py`
  — novo `ATIVIDADES_COM_MODO_REATIVO`, `meta_dia_reativo`). Modo Reativo:
  taxa de acionamentos/km/ano × extensão do inventário = volume anual,
  dimensionado como a NC (1 ciclo, 12 meses, sem sazonalidade).
- **10** (mecanização mix): validado pelo usuário — a lógica de
  complementaridade por trecho (largura/velocidade/inclinação) bate com a
  realidade de campo. **Achado durante a validação:** o texto de indicação do
  Robô estava errado ("áreas pequenas e planas" — o usuário descreveu como
  "áreas inclinadas ou de difícil acesso"); corrigido, junto com o texto do
  Trator 1.7m (agora cita "locais mais estreitos onde o 4.7m não entra").
- **11** (extensão por rodovia): códigos confirmados corretos. Sobre "maior
  extensão x soma": o app já faz os dois — extensão por rodovia na aba
  Auditoria, soma total na aba Inventário. Nenhuma ação necessária.
- **12** (origem aceiro/drenagem): confirmado que é inventário à parte (sem
  fonte automatizada hoje). Recomendei manter 2 uploads (Quasar + planilha
  modelo) com merge por trecho/rodovia+km a construir — aguardando
  confirmação do usuário antes de implementar o merge.
- **13** (resumo % manual/mecanizado): confirmado que está bom como está.
- **14** (campo "Contratado"): decidido manter como está (pré-preenchido igual
  ao dimensionado). Backlog 17 marcado como decidido, sem mudança de código.
- **15** (cobertura 50% do Quasar AB): o usuário confirmou que o mapeamento é
  para ser contínuo (1 polígono a cada 500 m) e que a área total do AB (9,6
  milhões m²) está próxima do real. Mantido o padrão de NÃO extrapolar por
  default; **suavizado o texto do alerta** em `modules/quasar.py` para não
  soar como subestimação confirmada, já que o total bateu nesta unidade.
- **17** (divisão de área com 2+ equipamentos): mantido 50/50 — o usuário
  confirmou que normalmente não se sabe a % real hoje; sugeriu como
  possibilidade futura perguntar ao usuário na interface (novo item de
  backlog 28, baixa prioridade).
- **18** (equipe atravessar rodovias): o usuário detalhou que a decisão
  correta depende da distância real de deslocamento entre rodovias, não só de
  "são vizinhas" — deu o exemplo de SP-300/SP-102 (longe) x pontas da SP-330
  (podem ter sinergia dependendo de onde cada rodovia se conecta). **Não
  implementado:** falta a fonte do dado de distância entre rodovias — nova
  pergunta registrada (18 atualizada) sobre de onde viria esse dado.
- **19** (limiares do semáforo): aprovados como ponto de partida (5%/15%).
  **Implementado:** cor por faixa de severidade na Análise de Contrato
  (`app.py`) — verde ≤5%, amarelo 5-15%, vermelho >15% de déficit.
- **Pedido extra:** pesquisar se existe API gratuita para trazer dado real de
  pluviometria/crescimento de vegetação (em vez de ciclos fixos por
  atividade). **Pesquisado:** NASA POWER (clima/chuva histórica, sem cadastro)
  e Embrapa SATVeg/AgroAPI (NDVI, gratuito, dado brasileiro) — ambas viáveis
  tecnicamente, mas travadas hoje porque nem o inventário nem o Quasar têm
  coordenada geográfica por trecho (só rodovia+km). Registrado como item 5/30
  do backlog e pergunta 23, não implementado (precisa da coordenada primeiro,
  e o elo "clima/NDVI → nº de ciclos" ainda exige um modelo agronômico a
  validar com especialista antes de virar fórmula).
- **Pedido extra:** reorganizar `melhorias_propostas.md` para separar o que
  ainda falta implementar do que já foi feito — adicionado um resumo "O que
  ainda falta evoluir/implementar" logo no topo do arquivo.

**Mudanças de código:** `app.py` (modo reativo na aba Especialistas; semáforo
por faixa na Análise de Contrato), `modules/parametros_padrao.py`
(`ATIVIDADES_COM_MODO_REATIVO`, `meta_dia_reativo`, correção dos textos de
indicação do Robô e do Trator 1.7m), `modules/quasar.py` (texto do alerta de
cobertura suavizado). `README.md` (seção Publicação reescrita, passo a passo
completo).

**Validado:** `ast.parse` OK em todos os arquivos alterados; `AppTest` do
Streamlit rodou o app completo (inventário de exemplo → troca dos 2 modos
para Reativo → aba Análise de Contrato com déficit máximo simulado) sem
exceção em nenhum passo; exportação PPTX e Excel geradas com sucesso incluindo
os novos dados do modo reativo; servidor subiu na porta 8512 e respondeu HTTP
200, depois encerrado.

**Pendências abertas:** perguntas 12, 17 (baixa prioridade), 18 (atualizada),
23 (novas/atualizadas) — todas as demais perguntas antigas (1-16, 19) foram
respondidas nesta rodada. Ver `perguntas_pendentes.md` para o texto completo.
