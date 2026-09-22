# Perguntas Pendentes — DimConservação

Este arquivo registra perguntas que só o usuário (Daniel) pode responder, feitas
durante a rotina diária de retroanálise. Cada pergunta tem data de criação e
status. Quando respondida (pelo usuário, aqui no arquivo ou em conversa), marcar
como **[RESPONDIDA]** com a resposta e a data, sem apagar o histórico.

---

## Em aberto

### 2. [2026-09-15 → em stand-by desde 2026-09-22] Metas/produtividade das atividades "estimativa (a validar)"
Várias atividades de Full Service (aceiro, capina, refilamento, calçada) estão
com meta/dia e ciclos/ano marcados como estimativa no `parametros_padrao.py`.
**Resposta em 2026-09-22:** manter as estimativas por ora, aprofundar aos
poucos depois — não é prioridade agora.

### 3. [2026-09-15 → em stand-by desde 2026-09-22] Roadmap perdido
O `Roadmap_DimConservacao_2026.pptx` também foi perdido. **Resposta em
2026-09-22:** deixar em stand-by (consistente com o AJUSTE DE ROTA de
2026-09-17 — comparação com roadmap pausada até o usuário pedir para retomar).

### 12. [2026-09-18 → recomendação dada em 2026-09-22, aguardando confirmação] Como estruturar o upload de Aceiro/Drenagem e outras atividades sem cobertura no Quasar
**Resposta do usuário (2026-09-22):** é um inventário à parte — o Quasar só
levanta área verde (manual/mecanizada), as outras atividades (aceiro,
drenagem, EPS/barreira, defensa, placas, calçada) não têm hoje uma fonte de
dado real automatizada. O usuário perguntou se é melhor ter dois uploads
separados (um do Quasar, outro dessas atividades) ou juntar tudo em um só, e
pediu uma recomendação como especialista de desenvolvimento.

**Recomendação:** manter DOIS uploads (não juntar), por 3 motivos: (1) já é o
padrão que o app usa hoje — Quasar gera a área verde, planilha modelo cobre o
resto; juntar exigiria refazer o parser do Quasar para aceitar colunas extras
que ele nunca vai preencher; (2) os dois dados têm ciclo de vida diferente —
Quasar é atualizado por satélite (auditável, versionado), as outras atividades
são levantamento manual da equipe de campo, que muda em outro ritmo; (3) já
existe o mecanismo de merge natural: gerar o inventário do Quasar primeiro, e
a planilha modelo (com `trecho`/`rodovia`/`km_inicial`/`km_final` preenchidos
IGUAIS aos do Quasar) pode ser importada por cima e casada por chave
trecho+rodovia — hoje isso ainda não existe como um "merge" automático, é uma
melhoria a construir (ver pergunta nova abaixo).
**Pergunta:** confirma esse caminho (2 uploads, com merge por
trecho/rodovia+km a construir) antes de eu implementar o merge?

### 17. [2026-09-21] Polígono com 2+ equipamentos indicados: como dividir a área?
Hoje divido igualmente (ex.: "Trator 1.7m, Spider" = 50% para cada).
**Resposta do usuário (2026-09-22):** normalmente não se sabe essa % exata
hoje — é uma estimativa dentro de cada polígono mesmo. Sugeriu como
possibilidade futura perguntar ao próprio usuário no app (input manual por
polígono/trecho) em vez de manter fixo 50/50. **Mantido 50/50 por ora** — vira
item de backlog (ver `melhorias_propostas.md`), não é urgente.

### 18. [2026-09-21 → detalhado em 2026-09-22, falta fonte de dado] Sinergia entre rodovias: como considerar a distância real de deslocamento?
**Resposta do usuário (2026-09-22):** a lógica de "máximo aproveitamento" está
certa em espírito, mas hoje o app trata qualquer rodovia vizinha como
igualmente combinável — na prática o que importa é a DISTÂNCIA de
deslocamento entre o ponto onde uma equipe termina e o ponto onde a próxima
rodovia começa. Exemplo dado: SP-300 é longe de SP-102, então juntar as duas
na mesma equipe gera deslocamento excessivo; já a ponta da SP-330 pode ter
sinergia com a SP-300 (se estiver fisicamente próxima) e o meio da SP-330 com
a SP-102 (se for o ponto mais próximo dela), dependendo de ONDE cada rodovia
se conecta. Ou seja, a decisão de juntar equipes entre rodovias deveria
considerar a distância real entre os pontos de km, com um limite máximo de
deslocamento aceitável, não só "são rodovias vizinhas, pode juntar".
**Por que não dá pra implementar ainda:** isso exige um dado que o app não tem
hoje — a distância física (ou pelo menos o ponto de interseção/proximidade)
entre pares de rodovias. **Pergunta:** de onde viria esse dado? Opções: (a)
você informa manualmente uma tabela simples "rodovia A × rodovia B → distância
km" para as rodovias de cada unidade; (b) o Quasar ou outro sistema Motiva já
tem coordenadas (lat/lon) por km que dariam pra calcular a distância
automaticamente; (c) outra fonte que você tenha em mente. Também preciso de um
"limite máximo de deslocamento aceitável" (km) — tem um valor de referência,
ou fica editável na interface?

### 23. [2026-09-22] Coordenadas geográficas por trecho — pré-requisito para pluviometria/NDVI automáticos (ver item 5 do backlog)
Pesquisei (a pedido do usuário) se existe API gratuita para trazer dado real
de pluviometria e crescimento de vegetação, para calibrar os ciclos/ano em vez
de usar valor fixo por atividade. Encontrei duas opções gratuitas e sem
restrição de uso comercial: **NASA POWER** (clima/pluviometria histórica desde
1981, por coordenada, sem cadastro) e **Embrapa SATVeg/AgroAPI** (índice de
vegetação NDVI/EVI por coordenada, dado brasileiro, gratuito). Detalhe técnico
completo no `melhorias_propostas.md` item 5. **Trava:** as duas APIs pedem
latitude/longitude, e nem o inventário nem o export Quasar têm essa
informação hoje (só rodovia + km). **Pergunta:** existe algum sistema da
Motiva que converta rodovia+km em coordenada (ex: cadastro de marco
quilométrico, ou o próprio Quasar em outra aba/exportação), ou isso também
precisaria ser levantado à parte?

---

## Respondidas

### 1. [2026-09-15 → RESPONDIDA em 2026-09-22] Produtividade real da roçada mecanizada por equipamento
**Resposta:** manter a estimativa genérica editável como já está — o usuário
(de cada unidade) vai imputar/ajustar o valor real quando tiver, direto na
interface. Não é necessário buscar o valor real agora.

### 4. [2026-09-15 → RESPONDIDA em 2026-09-22] Hospedagem definitiva
**Resposta:** manter Streamlit Community Cloud por enquanto, sem se preocupar
com a restrição de dados reais por ora — MAS só se o acesso for bem didático
para o usuário final: idealmente um link único que abre tudo pronto, sem
trabalho extra de instalação/execução (o "trabalho extra com Python" que
existe hoje é só para o desenvolvedor rodar localmente, não para quem for usar
o app publicado). Pediu recomendação de especialista sobre a melhor forma de
construir isso. **Resposta técnica:** Streamlit Community Cloud já entrega
exatamente esse resultado — uma vez publicado, o link público abre o app
pronto no navegador, sem instalação nenhuma para o usuário final; o "trabalho
com Python" de hoje é 100% do ambiente de desenvolvimento (Daniel rodando
local para testar), não se repete para quem usa o link. Não há necessidade de
reescrever o app como página HTML/JS estática — isso jogaria fora o motor de
cálculo em Python (dimensionamento, leitura do Quasar, geração de PPTX/Excel)
e seria um retrabalho enorme sem ganho real, já que o Streamlit Cloud resolve
o "zero instalação" do jeito que está. Ação: seguir com Streamlit Cloud;
passos de publicação detalhados no `README.md` (seção "Publicação"). A
questão de dado real de contrato em servidor de terceiros continua não
totalmente resolvida (o usuário decidiu não se preocupar com isso agora), mas
fica registrada para revisitar antes de subir dado sensível de verdade.

### 5. [2026-09-15 → RESPONDIDA em 2026-09-22] Conta GitHub/Streamlit Cloud
**Resposta:** o usuário vai criar as contas, só precisava das instruções.
Passo a passo detalhado adicionado ao `README.md` (seção "Publicação").

### 7 (continuação). [2026-09-17 → RESPONDIDA/IMPLEMENTADA em 2026-09-22] Taxa de manutenção EPS/barreira e defensa
**Resposta:** o usuário concordou com o modelo proposto (modo Preventivo +
modo Reativo por km/ano de acionamentos, reaproveitando o padrão da NC) e
pediu para testar — "se não funcionar, recalculamos a rota". **Implementado**
nesta sessão: seletor "Modo de cálculo" na aba Especialistas para EPS/barreira
e defensa metálica. Testado com `AppTest` (troca de modo sem exceção) e
exportação PPTX/Excel com os novos dados (sem erro). Ver `retro_log.md` de
hoje para o detalhe técnico.

### 10. [2026-09-18 → RESPONDIDA/VALIDADA em 2026-09-22] Como representar a Roçada Mecanizada na Análise de Contrato / PPTX
Já havia sido resolvido em 2026-09-21 com a frota mista somável (equipamento
vira linha própria na Análise de Contrato e no PPTX). **Nesta sessão, o
usuário validou a lógica de fundo:** confirmou que na realidade de campo os
equipamentos se complementam por característica do trecho (trator 1.7m em
locais estreitos onde o 4.7m não entra; 4.7m com mais produtividade em
canteiros largos; giro-zero/eixo-zero mais rápido mas exige terreno regular;
robô e braço articulado para áreas inclinadas/difícil acesso). **Achado:** o
texto de indicação do Robô estava desalinhado com isso (dizia "áreas pequenas,
planas e repetitivas") — corrigido para "áreas inclinadas ou de difícil
acesso, operado remotamente", e o texto do Trator 1.7m ajustado para
mencionar explicitamente "locais mais estreitos onde o 4.7m não entra" (ver
`modules/parametros_padrao.py`).

### 11. [2026-09-18 → RESPONDIDA em 2026-09-22] Códigos de rodovia extraídos do Quasar / forma de apresentar a extensão
**Resposta:** os códigos de rodovia do AB (SP-102, SP-300, SP-330, SP-348)
estão corretos. Sobre a extensão: cada rodovia tem sua própria extensão linear
(ex: SP-348 ~158 km, conferível pelo km final no relatório do Quasar) — o
usuário perguntou se o certo é reportar a maior extensão ou a soma de todas,
e pediu recomendação como especialista em dimensionamento de conservação.
**Resposta técnica:** o app já faz exatamente a combinação recomendada — a
aba "Auditoria do Quasar" mostra a extensão física POR RODOVIA (tabela
`por_rodovia`), e a aba Inventário mostra a extensão TOTAL como a SOMA de
todos os trechos (que já é, na prática, a soma das extensões de cada
rodovia). Não há ação necessária: o formato pedido (detalhe por rodovia + soma
total) já existe nas duas abas.

### 13. [2026-09-18 → RESPONDIDA em 2026-09-22] Resumo de % manual x mecanizado
**Resposta:** está bom como foi construído, não precisa alterar por ora.

### 14. [2026-09-21 → RESPONDIDA em 2026-09-22] Campo "Contratado" na Análise de Contrato
**Resposta:** manter como está (pré-preenchido igual ao dimensionado). Se no
futuro parecer necessário melhorar, ajusta-se então. Backlog item 17 marcado
como "mantido, sem ação por ora".

### 15. [2026-09-21 → RESPONDIDA em 2026-09-22] Cobertura de 50% do Quasar AB — amostral ou faltam polígonos?
**Resposta:** o mapeamento é para ser contínuo (1 polígono a cada 500 m — ou
seja, 2 por km, não 1 a cada km). A área total do AB (9,6 milhões m²) está
próxima do real, "mais ou menos isso mesmo" — o usuário acredita que o
levantamento está correto. **Ação:** mantido o padrão de NÃO extrapolar por
default (a extrapolação continua disponível como opção manual, mas
desligada). Suavizado o texto do alerta de cobertura em `modules/quasar.py`
para não sugerir subestimação como certeza, já que o total já bateu com o
esperado nesta unidade — mantendo o alerta como checagem para outras unidades
onde o total possa não bater.

### 16. [2026-09-21 → RESPONDIDA em 2026-09-22] Produtividade real dos equipamentos mecanizados
**Resposta:** mesma linha da pergunta 1 — manter as estimativas editáveis, o
usuário ajusta quando tiver o valor real por unidade.

### 19. [2026-09-22 → RESPONDIDA/IMPLEMENTADA em 2026-09-22] Faixas de severidade do desvio na Análise de Contrato
**Resposta:** os limiares sugeridos (≤5% verde, 5–15% amarelo, >15% vermelho)
podem ser usados como ponto de partida; depois da primeira versão, recolher
feedback de uso para recalibrar se necessário. **Implementado** nesta sessão
em `app.py` (aba Análise de Contrato) — testado com `AppTest` simulando
déficit máximo, sem exceção.

### 6. [2026-09-17 → RESPONDIDA em 2026-09-17] Divisão de área manual x mecanizada por trecho
**Resposta:** os dois percentuais sempre somam 100% da área verde. Já existe
hoje o mapeamento manual x mecanizada — dá para extrair do sistema uma
planilha Excel com esse levantamento. **Assumido (a confirmar na prática ao
receber a planilha):** como o mapeamento vem de um levantamento real, o
percentual deve ser por trecho, não único para o contrato — vou desenhar dessa
forma e ajustamos se a planilha vier em outro nível de granularidade.

### 7. [2026-09-17 → RESPONDIDA parcialmente em 2026-09-17] Dados de recorrência/histórico por atividade
**Resposta:** em vez de importar o histórico bruto (log de cada acionamento),
a direção proposta pelo usuário é ter uma **taxa de manutenção/recorrência**
(por volume) para EPS/barreira, defensa e NC, comparada contra a capacidade de
cada equipe, para dimensionar — ou seja, um parâmetro calculado (taxa) e não
uma importação de eventos brutos. **Concluído em 2026-09-22:** ver pergunta 7
(continuação) acima — modelo aprovado e implementado.

### 9. [2026-09-17 → RESPONDIDA em 2026-09-17] Custo por equipe/equipamento (financeiro)
**Resposta:** sim, cada contrato tem preço unitário por equipe por mês, e dá
para trazer isso ao relatório. Valores reais específicos ainda precisam ser
levantados quando formos implementar (mesmo fluxo das perguntas 1/2).

### 6. [2026-09-17 → dado real recebido em 2026-09-17] Mapeamento Quasar
Usuário enviou os 2 arquivos reais de exemplo (`dados_quasar/QUASAR_AB.xlsx`,
`dados_quasar/QUASAR_SOROCABANA.xlsx`). Implementado e testado — ver item 1 de
`melhorias_propostas.md`.

### 8. [2026-09-17 → RESPONDIDA em 2026-09-17] Logo da Motiva
Usuário salvou os arquivos em `assets/logo_motiva_branca.png` e
`assets/logo_motiva_roxa.png`. Já aplicado no app e no relatório PPTX.
