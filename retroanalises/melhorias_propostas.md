# Backlog de Melhorias — DimConservação

Este arquivo é o backlog vivo de melhorias de PRODUTO/FUNCIONALIDADE do app,
levantadas em conversas com o usuário. Diferente do `retro_log.md` (histórico
do que já foi feito) e do `perguntas_pendentes.md` (perguntas específicas em
aberto), aqui ficam as ideias de melhoria ainda não implementadas, para
trabalharmos incrementalmente. Cada item tem status: `[ ]` a fazer, `[~]` em
decisão/aguardando resposta, `[x]` feito (mover para o log quando concluído).

## O que ainda falta evoluir/implementar (atualizado em 2026-09-22)

Resumo rápido — detalhe de cada um mais abaixo, no número correspondente:

- **Item 3** `[ ]` Relatório executivo mais rico (matriz de risco, componente
  financeiro, sumário executivo) — ideias levantadas, não validadas ainda.
- **Item 5** `[ ]` Aprofundar uso de dados reais (API pluviometria/NDVI) para
  calibrar ciclos — bloqueado por falta de coordenada geográfica por trecho
  (pergunta 23).
- **Item 10** `[~]` Merge automático entre o inventário do Quasar (área verde)
  e a planilha de outras atividades (aceiro, drenagem, EPS, defensa) —
  aguardando confirmação do usuário (pergunta 12).
- **Item 27** `[ ]` Sinergia entre rodovias por distância real de deslocamento
  (em vez de "vizinha = pode juntar") — bloqueado por falta de dado de
  distância entre rodovias (pergunta 18).
- **Item 28** `[ ]` Divisão de área de polígono com 2+ equipamentos — considerar
  pedir a % ao usuário em vez de sempre dividir igual. Baixa prioridade.

Tudo o mais abaixo já está `[x]` implementado ou foi `[x]` decidido manter
como está (ver `perguntas_pendentes.md` para o histórico de respostas do
usuário).

---

## 1. [x] Inventário — % de área manual x mecanizada por trecho — IMPLEMENTADO em 2026-09-17

**Problema:** hoje o app trata a área verde de cada trecho como se fosse 100%
atendida pela roçada manual E também 100% pela roçada mecanizada (são cálculos
independentes). Na prática, cada trecho tem uma parte da área verde que só dá
pra fazer manual (ex: taludes íngremes, canteiro estreito) e outra parte que dá
pra fazer com máquina — não é a mesma área contada duas vezes.

**Decidido em 2026-09-17:** os dois percentuais somam sempre 100% da área
verde do trecho. Já existe hoje o mapeamento real (extraível do sistema da
Motiva como planilha Excel) — não é estimativa manual. Assumindo que o
percentual é por trecho (a confirmar quando a planilha real chegar).

**O que foi implementado (2026-09-17):**
- Novo módulo `modules/quasar.py`: lê o export Quasar (identifica automaticamente
  a aba com os dados — robusto a variações de nome de coluna entre regionais,
  testado com os 2 arquivos reais enviados: QUASAR AB e QUASAR SOROCABANA, ~3.700
  e ~4.400 polígonos respectivamente) e agrega os polígonos por rodovia + faixa
  de km (tamanho configurável, padrão 5 km) em linhas de inventário com
  `area_verde_m2`, `pct_manual`, `pct_mecanizada` (soma sempre 100%) e o
  equipamento predominante de cada trecho.
- Nova seção na aba Inventário do app: "🛰️ Importar mapeamento Quasar" — upload
  do .xlsx, escolha do tamanho de agrupamento, gera o inventário automaticamente.
- `modules/inventario.py`: `pct_manual`/`pct_mecanizada` viraram colunas
  opcionais reconhecidas; nova função `area_por_modalidade()` pondera a área de
  cada trecho pelo percentual real quando disponível.
- Abas Roçada Manual e Mecanizada agora usam `area_por_modalidade()` — se o
  inventário não tiver os percentuais (ex: inventário manual antigo), o app
  avisa e mantém o comportamento anterior (100% em cada modalidade, cenário
  isolado) para não quebrar nada existente.
- **Testado:** sintaxe OK, fluxo completo Quasar → inventário → dimensionamento
  rodado com os dois arquivos reais (soma manual+mecanizada bate com a área
  total), e testado no navegador com o inventário de exemplo (sem regressão).
  Não foi possível testar o upload real do Quasar via automação de navegador
  (a ferramenta de teste não abre o seletor de arquivo do sistema operacional)
  — validado por script Python direto em vez disso.

## 2. [x] Taxa de manutenção/recorrência (EPS/barreira, defensa) — IMPLEMENTADO em 2026-09-22

**Pedido do usuário em 2026-09-17:** ao invés de simplesmente implementar a
ideia inicial dele (uma "taxa de manutenção"), pensar como especialista em
dimensionamento de conservação rodoviária sobre a melhor forma de fazer isso.

**Análise:** hoje EPS/barreira e defensa metálica são modeladas no app como
atividade **preventiva cíclica** (mesma lógica da roçada: extensão total ×
ciclos/ano de varredura completa). Mas na prática, dano em EPS/barreira e
defensa é majoritariamente **reativo** (causado por acidente/sinistro), não
uma varredura periódica — o dado real que existe na unidade ("histórico de
acionamentos") é uma taxa de incidência, não um número de varreduras.

**A atividade "Atendimento a Não Conformidades (NC)" no app já resolve
exatamente esse problema** (`modules/parametros_padrao.py`): não usa
extensão × ciclos, usa `quantidade` = volume de ocorrências informado
manualmente, `meta_dia` = ocorrências atendidas por dia por equipe, ciclos=1/
meses=12 (demanda distribuída no ano). É literalmente um modelo de demanda
reativa, já funcionando.

**Proposta (reaproveitar o padrão da NC, sem inventar fórmula nova):**
adicionar um segundo modo de cálculo para EPS/barreira e defensa, análogo ao
seletor "Modalidade contratual" da Roçada Manual:
- **Modo Preventivo (atual):** extensão do inventário × ciclos/ano de
  inspeção/varredura completa.
- **Modo Reativo (novo):** usuário informa a taxa histórica real
  (acionamentos por km por ano, vinda do histórico da unidade) — o app
  multiplica pela extensão do inventário para estimar o volume anual de
  acionamentos esperado, e dimensiona como a NC já faz hoje (`meta_dia` =
  acionamentos atendidos por equipe por dia).
- Se o contrato precisa das duas coisas (inspeção periódica E resposta a
  sinistro), o dimensionamento final pode ser a soma ou o maior dos dois
  modos — a definir com o usuário.

**Vantagem:** não precisa de fórmula nova nem de importar histórico bruto —
só reaproveita o padrão que a NC já usa, com um novo campo de taxa por km/ano
alimentado pelo histórico real da unidade quando o usuário tiver.

**Aprovado pelo usuário em 2026-09-22** ("concordo, vamos testar esse modelo").
**Implementado:** seletor "Modo de cálculo" (Preventivo/Reativo) na aba
Especialistas, só para EPS/barreira e defensa (`pp.ATIVIDADES_COM_MODO_REATIVO`
em `parametros_padrao.py`). No modo Reativo: taxa de acionamentos/km/ano ×
extensão do inventário (convertida de m para km) = volume anual, dimensionado
como a NC (ciclos=1, meses=12/12, sem sazonalidade). Meta/dia reativa nova
(`meta_dia_reativo`, estimativa a validar). **Não implementado (deixado para
decidir com uso real):** somar Preventivo + Reativo quando o contrato precisa
das duas coisas — hoje é um OU outro, escolhido pelo usuário. **Testado:**
`ast.parse` OK; `AppTest` trocando os dois selects para Reativo sem exceção;
exportação PPTX e Excel geradas com sucesso incluindo as linhas reativas.

## 3. [ ] Relatório executivo mais rico (não mais longo)

Pedido do usuário: pensar como especialista em apresentações executivas para
deixar o PPTX mais rico em informação por slide, não necessariamente maior.
Ideias levantadas nesta sessão para validar com o usuário:
- Matriz de risco (probabilidade × impacto) por atividade crítica — visual
  2x2, ligada a histórico de NC/déficit de equipe.
- Componente financeiro: peso em R$ do contrato, custo do dimensionado x
  custo do contratado (desvio financeiro do déficit/excedente), não só
  contagem de equipes. **Confirmado em 2026-09-17:** cada contrato tem preço
  unitário por equipe/mês e dá para trazer — falta só levantar os valores reais
  na hora de implementar (ver `perguntas_pendentes.md` item 9).
- Um slide de sumário executivo no início com os 3-4 achados mais críticos,
  antes do detalhe por atividade.
- Indicadores visuais tipo semáforo para status de conformidade.

## 4. [x] Identidade visual Motiva (logo) — IMPLEMENTADO em 2026-09-17

Usuário salvou os 2 arquivos de logo (branca e roxa) em `assets/`. Aplicado:
- `app.py`: `st.logo()` com a versão roxa (aparece na sidebar/topo do app).
- `modules/export_pptx.py`: versão branca na capa (fundo roxo), versão roxa no
  rodapé de todos os slides de conteúdo (fundo branco).
- Testado: PPTX gerado de teste confirma 1 imagem de logo em cada slide, sem
  erro.

## 5. [ ] Aprofundar uso de dados (sem API) para precisão do cálculo

Hoje o modelo dimensiona só por ciclos fixos (teóricos/estimados), não pela
taxa real de crescimento da vegetação. Ideal seria conhecer a taxa de
crescimento por região/trecho para calibrar os ciclos de forma mais exata, em
vez de ciclos genéricos. O usuário mencionou que a Motiva já tem projetos de
mapeamento via satélite (para área manual x mecanizada, item 1) e também
projetos para conhecer taxa de crescimento de vegetação.

**Proposta a explorar:** já que não há API disponível hoje, pensar em como
importar esses dados "manualmente" para dentro do modelo — ex: upload de uma
planilha de mapeamento/crescimento por trecho, ou campos de input por região
que alimentem o cálculo de ciclos em vez de um valor fixo por atividade.

**Pesquisa feita em 2026-09-22 (pedido do usuário: "será que não conseguimos
usar alguma API para trazer esses dados?"):** existem, sim, duas fontes
gratuitas e sem restrição de uso comercial:
- **NASA POWER** (power.larc.nasa.gov) — série histórica de pluviometria e
  clima desde 1981, por coordenada (lat/lon), API REST pública, **sem
  cadastro**. Daria para trazer o regime de chuva real de cada trecho em vez
  de assumir "7 meses de chuva / 5 de seca" fixo.
- **Embrapa SATVeg / AgroAPI** (satveg.cnptia.embrapa.br) — série temporal de
  índice de vegetação (NDVI/EVI) por coordenada, dado brasileiro, gratuito,
  baseado em satélite (MODIS/Sentinel-2). Poderia servir de proxy da taxa de
  crescimento da vegetação por região, em vez de um número de ciclos/ano
  genérico.

**Trava encontrada:** as duas APIs pedem latitude/longitude por ponto — o
inventário e o export Quasar de hoje só têm rodovia + km, sem coordenada
geográfica. Sem isso, não dá para consultar essas APIs automaticamente. Ver
pergunta 23 em `perguntas_pendentes.md`.

**Avaliação:** mesmo resolvendo a coordenada, ainda falta o elo entre
"pluviometria/NDVI históricos" → "quantos ciclos/ano de roçada" — isso é um
modelo agronômico/biológico (crescimento por espécie, resposta a chuva/solo),
não um cálculo direto. Recomendo tratar como 2 passos: **(1)** curto prazo —
se a coordenada existir, trazer a pluviometria histórica real só como
REFERÊNCIA na tela (para o usuário comparar com os meses de chuva/seca que
informou manualmente), sem ainda automatizar o número de ciclos; **(2)** longo
prazo — modelo preditivo de ciclos por espécie/região, que precisa de
validação com um especialista agronômico antes de virar fórmula no app. Não
implementado nesta sessão — depende da resposta sobre coordenadas (pergunta
23) e não é pequeno o suficiente para fazer sem alinhar o escopo antes.

---

## 6. [~] Roçada Mecanizada não aparece na Análise de Contrato nem no relatório PPTX — IDENTIFICADO em 2026-09-18

**Problema encontrado na revisão funcional de hoje:** diferente da Roçada
Manual (que salva o resultado do cenário de pico em
`st.session_state["resumo_rocada"]`), a aba Roçada Mecanizada não salva nada
em lugar nenhum. Resultado prático: quem usa o app, calcula a roçada
mecanizada, mas ao chegar na aba **Análise de Contrato** ou no **relatório
PPTX exportado**, só vê "Roçada Manual" (mais Full Service/Especialistas) —
a mecanizada simplesmente não existe nesses dois lugares, mesmo tendo sido
calculada. Para um usuário leigo isso pode passar despercebido (nenhum erro
aparece) e o relatório final sai incompleto.

**Por que não é um conserto trivial:** a Roçada Manual tem um único número de
"pico" (uma modalidade, uma produtividade). Já a Mecanizada calcula por tipo
de equipamento (Trator, Giro Zero, Robô, ...) como alternativas independentes
("se ESSE equipamento sozinho atendesse tudo") — não são somáveis nem existe
hoje um "equipes/equipamentos necessários" único para representar a aba
inteira, que é o formato que a Análise de Contrato e o slide de resumo do
PPTX esperam.

**Resolvido em 2026-09-21** com a opção (b) — frota mista somável, cada
equipamento vira linha própria (ver item 24). **Validado pelo usuário em
2026-09-22:** confirmou que a lógica de complementaridade por trecho (largura,
velocidade, inclinação) reflete a realidade de campo. Achado no processo:
o texto de indicação do Robô estava errado (dizia "áreas pequenas e planas",
o usuário descreveu como "áreas inclinadas ou de difícil acesso") — corrigido
em `parametros_padrao.py`, junto com o texto do Trator 1.7m (agora menciona
explicitamente "locais mais estreitos onde o 4.7m não entra").

## 7. [x] Extensão do Quasar inflada por canteiro/sentido + rodovia mal extraída — IMPLEMENTADO em 2026-09-18

**Problema relatado pelo usuário:** a extensão total em km do inventário
gerado pelo Quasar não batia com a realidade da rodovia. Ele explicou que
dentro de 1 km físico existem vários polígonos (canteiro lateral nos dois
sentidos + canteiro central) e que o código da rodovia vem no ID Motiva
(ex: SP-102, SP-330).

**Implementado:** ver detalhe técnico completo em `retro_log.md` (entrada de
2026-09-18). Resumo: `_extrair_rodovia` corrigida para ler o 1º token do ID
(removendo prefixo `VG` quando colado direto), e `agregar_por_trecho` passou
a contar posições de km distintas em vez de somar o comprimento bruto dos
polígonos. Validado contra os 2 arquivos reais — extensão do arquivo AB
caiu de 246,5 km para 157,0 km (a correta). **Pendente:** pergunta 11 em
`perguntas_pendentes.md` — confirmar com o usuário se os códigos de rodovia
extraídos (incluindo os compostos com barra do arquivo Sorocabana) fazem
sentido.

## 8. [x] % manual x mecanizado do total da concessionária — IMPLEMENTADO em 2026-09-18

Novo bloco de métricas na aba Inventário (quando há `pct_manual`/
`pct_mecanizada`), calculado como média ponderada pela área de cada trecho,
complementando o detalhamento por trecho que já existia.

## 9. [x] Terminologia "roçadores" em vez de "equipes" — IMPLEMENTADO em 2026-09-18

A Roçada Manual dimensiona colaboradores individuais (roçadores), não
equipes. Corrigido na Análise de Contrato e no PPTX (as demais atividades
continuam como "equipe(s)"). Ver detalhe em `retro_log.md`.

## 10. [~] Full Service — inventário próprio para Aceiro/Drenagem — colunas prontas em 2026-09-18, merge de upload pendente

Aceiro, Drenagem de plataforma e Drenagem fora de plataforma ganharam coluna
de inventário própria (em vez de usar a extensão total da rodovia) + campo
de quantidade editável manualmente na interface. **Resposta do usuário em
2026-09-22 (pergunta 12):** é um inventário à parte mesmo — o Quasar só cobre
área verde, essas atividades não têm hoje fonte automatizada. Perguntou se é
melhor 2 uploads separados ou 1 só; recomendei manter 2 uploads (Quasar +
planilha modelo) com um MERGE por `trecho`+`rodovia`+km entre os dois, em vez
de juntar tudo num parser só — aguardando confirmação do usuário antes de
construir o merge (ver `perguntas_pendentes.md` item 12). Hoje, sem o merge,
o usuário ainda precisa editar a planilha gerada pelo Quasar à mão para
acrescentar essas colunas antes de reenviar.

## 11. [x] PPTX — logo sobreposta pela tabela — IMPLEMENTADO em 2026-09-18

Logo reposicionada do rodapé (podia ser coberta por tabela comprida) para o
canto superior direito, ao lado do título — posição fixa, nunca coberta por
conteúdo. O relatório também passou a gerar um slide por grupo de atividade
(Full Service, Especialistas) em vez de uma tabela única com tudo junto,
seguindo boas práticas de apresentação executiva (pedido do usuário: "pense
como designer de apresentações executivas").

## 12. [~] Interface mais "gourmetizada" (impacto visual) — primeiro passo em 2026-09-18

Pedido do usuário: pensar como especialista em desenvolvimento de apps para
dar mais impacto visual à interface (hoje é essencialmente Streamlit padrão
com a logo/paleta aplicada). **Feito nesta sessão (passo 1, incremental):**
CSS leve com a identidade Motiva — cards de métrica com fundo lavanda/borda
roxa, títulos (h1/h2/h3) em roxo escuro, abas com destaque visual. **Próximos
passos possíveis (não implementados ainda, aguardando ver a reação do
usuário a este primeiro passo):** ícones/ilustrações temáticas, layout em
cards para as seções de cada aba, gráficos visuais (ex: pizza do % manual x
mecanizado em vez de só métricas numéricas), sidebar de navegação/resumo.

## 13. [x] Planilha modelo para download — IMPLEMENTADO em 2026-09-18

Aba Inventário ganhou botão "Baixar planilha modelo" (.xlsx com aba
"Instruções" explicando cada coluna) para quando não há mapeamento Quasar
disponível. O texto solto com a lista de colunas mínimas/opcionais foi
removido da interface — vive só na planilha modelo agora.

## 14. [x] Remover "versão piloto (dados fictícios)" do subtítulo — IMPLEMENTADO em 2026-09-18

Removido porque dados reais (Quasar) já estão em uso. Botão "Usar inventário
de exemplo (dados fictícios)" mantido como estava.

## 15. [x] Proposta de divisão de equipes/equipamentos por trecho — IMPLEMENTADO em 2026-09-18

Roçada Manual e Mecanizada agora propõem não só "quantas pessoas/máquinas",
mas "qual equipe/equipamento cobre qual trecho contínuo da rodovia", já
considerando a composição real de uma equipe (9 pessoas, 6 roçadores ativos,
editável). Ver detalhe técnico completo em `retro_log.md` (2026-09-18,
segunda rodada). Na Mecanizada, a antiga seção "maior trecho" (só 1 ponto)
virou um ranking dos 5 trechos de maior demanda + divisão por equipamento.

## Feedback recebido nesta sessão (2026-09-17)

O usuário confirmou que conseguiu abrir e rodar o app localmente. Achou a
interface pouco intuitiva ainda, mas topou ir construindo aos poucos — os 5
itens acima foram levantados por ele para tratar nas próximas sessões (não
foram implementados ainda).

## 16. [x] Alerta de meses sazonais que não fecham 12 — IMPLEMENTADO em 2026-09-21

Nas 4 abas de dimensionamento (Manual, Mecanizada, Full Service, Especialistas)
o app agora avisa quando "meses chuva + meses seca" ≠ 12 (exceto o caso 12/12,
usado na NC, que é demanda distribuída no ano). Antes, um erro de digitação
(ex: 9+5) gerava resultado silenciosamente errado. Também: nome do arquivo
PPTX exportado agora é sanitizado (nome de contrato com `/`, `:` etc. quebrava
o download) e `requirements.txt` passou a exigir `streamlit>=1.50` (o app usa
`width='stretch'`, que não existe em versões antigas — risco em instalação nova).

## 17. [x] Análise de Contrato: o campo "Contratado" já vem igual ao dimensionado — DECIDIDO em 2026-09-22: manter como está

**Problema:** em `app.py` (aba Análise de Contrato) o campo "Contratado" é
inicializado com `value=int(dimensionado)`. Resultado: ao abrir a aba, TODAS as
atividades aparecem "✅ Conforme" — o usuário leigo pode ler isso como
resultado real, quando na verdade ele ainda não informou nada. Além disso, como
o widget tem `key` fixa, se o dimensionado mudar depois (ex: troca de
inventário), o "Contratado" pode ficar preso no valor antigo e gerar falso
déficit/excedente sem o usuário perceber.
**Proposta:** iniciar o campo vazio/0 com status "— informe o contratado" (cinza)
até o usuário preencher; ou oferecer upload de uma planilha "quadro contratado"
(atividade × quantidade) para preencher tudo de uma vez.
**Resposta do usuário (2026-09-22):** manter como está por ora; revisitar se
parecer necessário mais adiante. Nenhuma mudança de código feita.

## 18. [x] Análise de Contrato/PPTX: mostrar % de desvio e semáforo — IMPLEMENTADO em 2026-09-22

O desvio percentual (ex.: "Déficit de 3 equipe(s) (-25%)") já aparecia na tela
e no PPTX. **Cor por faixa de severidade implementada nesta sessão:** ≤5%
déficit → verde, 5–15% → amarelo, >15% → vermelho (limiares aprovados pelo
usuário como ponto de partida, "depois colhemos feedback para recalibrar").
Excedente continua neutro (azul informativo) — não há leitura de "excesso é
ruim" definida ainda. Testado com `AppTest` simulando déficit máximo (100%),
sem exceção.

---

## Rodada de 2026-09-21 — pedido do usuário (8 itens) — todos IMPLEMENTADOS

19. [x] **Unidade avaliada** — campo no topo do app; vai para o cabeçalho, título da Análise, capa do PPTX e Excel.
20. [x] **Auditoria do Quasar** — nova seção na aba Inventário + aba "Auditoria Quasar" no Excel. **Achou um erro meu anterior:** a extensão do AB (157 km) estava pela metade — os polígonos do AB existem a cada 1,0 km (cada um cobre 0,5 km), e a extensão usava o comprimento do polígono como passo. Correto: ~314 km (bate com a contagem de km de canteiro central da própria planilha: 157/73/6/2). Sorocabana: 447 km (cobertura contínua). Também achou: ordenação de trechos por texto ("km 100" antes de "km 11"), 2 IDs repetidos na Sorocabana, e **cobertura de 50% no AB** (pergunta 15).
21. [x] **Modalidade contratual** — só "Metas de performance" e "Personalizado".
22. [x] **Divisão de equipes com máximo aproveitamento** — algoritmo de enchimento contínuo: cada equipe é cheia até a capacidade do ciclo, trecho cortado no km exato; só a última pode ter folga. Nº de equipes agora = ⌈colaboradores ÷ roçadores por equipe⌉ (AB: 14 equipes, 13 a 100% e a última a 86%; antes 34). Controles: ocupação máxima (aceitar >100%) e permitir/impedir atravessar rodovias. Sugere quando aceitar ~107% eliminaria uma equipe.
23. [x] **Textos com atualização automática** — inventário do Quasar recalcula ao mudar o agrupamento; textos e resumos são f-strings sobre o estado atual; downloads são montados no clique; resultados são zerados/recalculados a cada execução.
24. [x] **Mecanização como especialista** — catálogo alinhado ao Quasar (Trator 4.7m, 1.7m, braço articulado, Eixo-zero, Spider, Robô). Área mecanizada distribuída por equipamento (frota mista **somável**, resolve o item 6/pergunta 10 — cada equipamento vira linha na Análise de Contrato e no PPTX), equipamento recomendado por trecho (mix, largura/inclinação médias, justificativa técnica), divisão por unidade, alerta de equipamento subutilizado (ex.: Trator 4.7m com 2.695 m² no AB).
25. [x] **Memória de cálculo em Excel** (aba Exportar) — premissas em azul + fórmulas reais (dias disponíveis → demanda → necessário → ROUNDUP). **Validado:** as fórmulas foram recalculadas com um motor independente e batem 9/9 com o app. Abas: Resumo, Memória de cálculo, Análise de Contrato, Inventário, Divisões, Auditoria Quasar, Premissas.
26. [x] **Planilha modelo formatada** — cabeçalho roxo (obrigatória) / lilás (opcional), comentários por coluna, validação (≥0, % 0–100, lista de equipamentos), zebra, painel congelado, abas Instruções e Exemplo. Novas colunas opcionais: `rodovia`, `equipamento_predominante`.

Pendentes ligados a esta rodada: perguntas 15 (cobertura 50% do AB), 16 (produtividades dos equipamentos), 17 (divisão de área quando o polígono lista 2+ equipamentos), 18 (equipe atravessar rodovias). Backlog 17/18 (Análise de Contrato: "Contratado" neutro) segue aguardando a pergunta 14 — o desvio % já entrou.

**Todas resolvidas em 2026-09-22** — ver `perguntas_pendentes.md` (seção Respondidas).

---

## Rodada de 2026-09-22 — respostas do usuário às pendências (ver `perguntas_pendentes.md`)

Itens novos abertos nesta rodada, a partir das respostas do usuário:

27. [ ] **Sinergia entre rodovias por distância real de deslocamento** — hoje
    o app permite uma equipe atravessar de uma rodovia para outra sempre que
    são "vizinhas" no mesmo agrupamento; o usuário explicou que a decisão
    correta depende da distância física entre o ponto onde uma equipe termina
    e onde a próxima rodovia começa (ex.: SP-300 é longe de SP-102, mas pode
    haver sinergia entre a ponta de uma rodovia e o início de outra se forem
    fisicamente próximas). **Bloqueado por falta de dado:** precisa de uma
    fonte de distância entre rodovias (tabela manual ou coordenadas) — ver
    pergunta 18 (atualizada) em `perguntas_pendentes.md`.
28. [ ] **Divisão de área quando o polígono lista 2+ equipamentos — considerar
    input do usuário** — hoje divide igualmente (50/50). O usuário confirmou
    que normalmente não se sabe a % real, e sugeriu como possibilidade futura
    perguntar ao usuário diretamente na interface (por trecho/polígono) em vez
    de manter fixo. Baixa prioridade, mantido 50/50 por ora (pergunta 17).
29. Ver item 10 acima — merge de upload Quasar + outras atividades (mesmo tema, detalhado lá).
30. [ ] **API de pluviometria/NDVI para calibrar ciclos por região** — pesquisa
    feita (NASA POWER + Embrapa SATVeg, ambas gratuitas). Bloqueado por falta
    de coordenada geográfica por trecho no inventário/Quasar. Ver item 5 e
    pergunta 23.
