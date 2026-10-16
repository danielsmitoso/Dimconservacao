# DimConservação

Ferramenta de dimensionamento e análise de contratos de conservação rodoviária (Motiva).

Calcula quantas equipes/equipamentos são necessários para roçada (manual e mecanizada),
atividades de "Full Service" (aceiro, drenagem, capina, refilamento, calçada, placas,
remoção de lixo) e equipes especialistas (EPS/barreira, defensa, NC, varrição, poda) —
a partir de uma planilha de inventário de trechos. Compara o dimensionado com o
contratado e exporta um relatório executivo em PowerPoint.

> **Status: versão piloto.** Os valores de produtividade/ciclos vêm pré-preenchidos,
> mas parte deles é **estimativa a validar** (marcado no próprio app) — não use para
> decisão de contrato real sem revisar com o time técnico. Ver roadmap em
> `Roadmap_DimConservacao_2026.pptx` (quando disponível) — Fase 1 "Validação com Dados
> Reais" é o marco para isso.

## Como abrir a ferramenta (sem instalar nada)

O app está publicado em **https://dimconservacao.streamlit.app** — basta abrir esse
link em qualquer navegador (Chrome, Edge), não precisa instalar Python nem nada no
seu computador.

> **Use só dados fictícios/de exemplo nesse link por enquanto.** A questão de dado
> real de contrato num servidor de terceiros (Streamlit Cloud) ainda não foi resolvida
> — ver `retroanalises/perguntas_pendentes.md` (pergunta 4). Compartilhe só o link do
> app com a equipe, nunca o link do repositório GitHub.

## Como rodar localmente (para quem for desenvolver/testar)

### 1. Instalar o Python (só na primeira vez)

1. Baixe o Python 3.12 em https://www.python.org/downloads/ (marque a opção
   "Add Python to PATH" durante a instalação).
2. Confirme a instalação abrindo o PowerShell e rodando:
   ```powershell
   python --version
   ```
   Se o comando `python` não funcionar (comum em máquinas corporativas Motiva),
   use o caminho completo do Python, por exemplo:
   ```
   C:\Users\<seu.usuario>\AppData\Local\Programs\Python\Python312\python.exe
   ```

### 2. Instalar as dependências do projeto (só na primeira vez)

Abra o PowerShell **na pasta do projeto** e rode:

```powershell
python -m pip install -r requirements.txt
```

(Troque `python` pelo caminho completo se necessário, como no passo 1.)

### 3. Abrir o app

```powershell
python -m streamlit run app.py
```

Isso abre automaticamente uma aba no seu navegador padrão em `http://localhost:8501`.
Se não abrir sozinho, copie esse endereço e cole no navegador.

Para fechar: volte no PowerShell e aperte `Ctrl+C`.

## Como usar

0. **Topo da página — Unidade / contrato avaliado:** digite o nome da unidade (ex.:
   "AutoBAn — Lote Norte"). Ele aparece no cabeçalho, no relatório PowerPoint e na
   memória de cálculo em Excel.
1. **Aba Inventário**: envie o export Quasar (expansor "🛰️ Importar mapeamento Quasar") ou
   uma planilha. Sem nenhum dos dois, baixe a **planilha modelo** (colorida, com
   validação de dados, aba de instruções e aba de exemplo), preencha e envie de volta.
   Colunas mínimas: `trecho`, `km_inicial`, `km_final`, `area_verde_m2`; opcionais:
   `rodovia`, `pct_manual`, `pct_mecanizada`, `equipamento_predominante`, `eps_barreira_m`,
   `defensa_m`, `placas_qtd`, `bueiros_qtd`, `calcada_m2`, `aceiro_km`,
   `drenagem_plataforma_km`, `drenagem_fora_plataforma_km`. O botão "Usar inventário de
   exemplo" carrega dados fictícios para conhecer a ferramenta.
   - **Auditoria do Quasar** (aparece depois de gerar o inventário): extensão física por
     rodovia, cobertura do mapeamento, lacunas, km com canteiro central, alertas. Confira
     antes de usar os números.
   - **Regra do Trator 4,70** (ligada por padrão na importação do Quasar): polígono indicado
     para Trator 1.7m, com canteiro mais largo que 5 m (ajustável) e sem bloqueio físico
     (coluna "Bloqueio Físico" = Sim, ou observação citando drenagem, EPS, barreira ou
     defensa), passa a aceitar também o Trator 4.7m. A largura é a "Largura média" do Quasar
     ou, onde não vem, área ÷ comprimento do polígono (é a mesma conta). Eixo-zero, braço
     articulado e Spider não mudam: foram indicados por restrição de acesso.
2. **Aba Vegetação e Clima** (opcional, recomendada): estima os **ciclos de roçada pelo
   crescimento da vegetação**. Informe a altura máxima do contrato (30 cm, 50 cm ou outra),
   a altura pós-corte (3–5 cm), o solo, o estado (clima de referência já embutido para os
   27 estados, ponto da capital; em SP, Campinas; não precisa de internet) ou a coordenada do trecho (consulta gratuita à
   NASA POWER — envia só a coordenada) e as espécies predominantes com a % de cobertura.
   A água disponível de cada mês vem de um **balanço hídrico** (chuva − evaporação, com a
   água que o solo guarda de um mês para o outro; o solo escolhido define quanto ele guarda).
   O app mostra o crescimento mês a mês, quantos dias a vegetação leva para chegar à
   altura máxima (prazo máximo para a equipe percorrer o trecho e voltar) e os ciclos de
   chuva e seca, indicando qual mês de cada período define os ciclos (o de crescimento
   mais rápido). Com medições de campo (dias desde a roçada + altura medida), o modelo é
   calibrado — o app compara com o crescimento previsto para todos os dias desde a roçada,
   mesmo que eles cubram mais de um mês, e mostra a conta de cada medição. A **memória de
   cálculo** (crescimento térmico de cada espécie × água disponível × fator de calibração →
   cm/dia → dias até a altura máxima → ciclos) aparece na tela e vai para o Excel. O botão **"Usar estes ciclos..."** preenche as abas de roçada.
3. **Aba Roçada Manual**: escolha *Metas de performance* ou *Personalizado*, ajuste ciclos
   e meses (chuva/seca). **Ciclos são contados dentro de cada período** (ex.: 10 ciclos nos
   7 meses de chuva), não por ano. A **proposta de divisão de equipes** enche cada equipe até a
   capacidade do ciclo, na ordem dos km, cortando o trecho onde a capacidade acaba —
   só a última equipe pode ter folga. Dá para aceitar uma ocupação máxima acima de 100%
   e impedir que uma equipe atravesse de uma rodovia para outra.
4. **Aba Roçada Mecanizada**: a área mecanizada vai para o equipamento que o Quasar indica
   (Trator 4.7m, Trator 1.7m, Trator com braço articulado, Eixo-zero, Spider). Quando um
   polígono indica mais de um ("Trator 1.7m, Spider"), são **alternativas** — qualquer um faria
   a área inteira, ela não é dividida: preenche primeiro a folga das unidades que já são
   necessárias e o resto vai para o de maior produtividade (quadro "🔀 Áreas em que mais de
   um equipamento pode trabalhar"). A **tabela de substituição** (🔁) diz quem pode fazer área
   indicada para outro, por tamanho e acesso: o Trator 1.7m faz área do 4.7m, o Eixo-zero faz
   as duas, o braço articulado faz a do Spider (editável). O app usa isso só para ocupar a
   folga de unidades que já existem e eliminar unidades parciais (quadro "♻️ Remanejamentos").
   Mostra a frota necessária por equipamento (somável), o equipamento
   recomendado por trecho (com o mix e a justificativa técnica) e a divisão de trechos
   por unidade de cada equipamento. Informe a frota disponível para ver sobra/falta.
5. **Aba Full Service**: aceiro, drenagem, capina, refilamento, calçada, placas, remoção de lixo.
   **Aceiro e Drenagem fora da plataforma** são em **ciclos por ano** (como nos contratos
   Artesp: 1 ciclo/ano, feito na seca): informe 2 cenários para comparar (padrão 1 e 2
   ciclos/ano), quando a atividade é feita (seca, chuva ou ano todo) e quantos meses dura
   a janela, e escolha o cenário que entra no dimensionamento. Fora da janela não há equipe
   alocada. As demais atividades seguem com ciclos por período de chuva e de seca.
6. **Aba Especialistas**: EPS/barreira, defensa metálica, NC, varrição, poda.
7. **Aba Análise de Contrato**: informe quantas equipes/unidades o contrato atual prevê por
   atividade e veja déficit/excedente (com %).
8. **Aba Exportar Relatório**: baixe (a) o **PowerPoint executivo** e (b) a **memória de
   cálculo em Excel**, com premissas em azul e o cálculo passo a passo em fórmulas do
   Excel, para conferir qualquer número.

> **Tudo se atualiza sozinho:** números e textos são recalculados a cada alteração, e os
> arquivos para download são montados no momento do clique, com o estado atual da tela.
>
> **Campos pré-preenchidos** (quantidades de Full Service/Especialistas e o "Contratado"
> da Análise de Contrato) acompanham o inventário e o cálculo enquanto você não mexer
> neles. Se você digitar um valor próprio, ele é mantido mesmo que o inventário mude.

## Estrutura do projeto

```
app.py                      # aplicação Streamlit (interface)
modules/
  dimensionamento.py         # motor de cálculo (equipes = f(quantidade, produtividade, ciclos))
  parametros_padrao.py       # valores-padrão de produtividade/ciclos/metas (editável)
  inventario.py               # leitura/validação da planilha de inventário
  quasar.py                   # leitura, auditoria e agregação do export Quasar (satélite)
  mecanizacao.py              # equipamento por trecho, frota mecanizada
  crescimento.py              # modelo de crescimento da vegetação -> ciclos (clima dos 27 estados embutido)
  export_excel.py             # memória de cálculo em Excel (fórmulas)
  export_pptx.py              # geração do relatório executivo em PowerPoint
tests/
  test_app.py                 # teste automatizado (roda o app de verdade com o inventário de exemplo)
retroanalises/
  retro_log.md                 # histórico da rotina diária de retroanálise (apêndice)
  perguntas_pendentes.md       # perguntas em aberto para o usuário
  melhorias_propostas.md       # backlog vivo de melhorias de produto
assets/                        # logo Motiva (branca/roxa), usada no app e no PPTX
dados_exemplo/                 # planilhas de exemplo (fictícias)
dados_quasar/                  # exports Quasar reais (dado sensível — no .gitignore)
requirements.txt               # dependências Python
```

## Publicação (deixar acessível sem instalar Python)

**Decisão (2026-09-22):** publicar no **Streamlit Community Cloud** (gratuito).
Isso gera um link público único — qualquer pessoa da unidade abre esse link no
navegador (Chrome, Edge) e o app já aparece pronto, sem instalar Python nem
nada: o "trabalho extra com Python" das seções acima é só para QUEM DESENVOLVE
o app testando localmente, não se repete para quem só for usar o link.

> **Atenção — dados sensíveis:** por ora, o piloto continua com dados
> fictícios/de exemplo. O app público no Streamlit Cloud roda em servidor de
> terceiros (fora da rede Motiva) — antes de subir dado real de contrato,
> revisitar essa decisão (ver `retroanalises/perguntas_pendentes.md`, pergunta 4).

### Passo a passo para publicar (só precisa ser feito 1 vez, por quem tiver as contas)

Criar contas e fazer login é algo que só a pessoa dona da conta pode fazer —
não é automatizável. Passo a passo:

1. **Criar uma conta gratuita no GitHub** (se ainda não tiver):
   - Acesse https://github.com/signup.
   - Informe um e-mail, crie uma senha e um nome de usuário.
   - Confirme o e-mail (o GitHub manda um link/código de verificação).
2. **Subir esta pasta como um repositório no GitHub:**
   - Na página inicial do GitHub, clique em "New" (novo repositório).
   - Dê um nome (ex.: `dimconservacao`), marque como **privado** (recomendado,
     mesmo com dados fictícios) e crie.
   - Suba os arquivos desta pasta.
   > **⚠️ Atenção — o `.gitignore` NÃO funciona no upload manual pelo site do
   > GitHub.** Se você usar "uploading an existing file" e arrastar os
   > arquivos, o GitHub sobe tudo que for arrastado, mesmo o que está no
   > `.gitignore` (ex.: `dados_quasar/`, que tem dado real sensível) — isso já
   > aconteceu uma vez neste projeto (ver `retroanalises/retro_log.md`,
   > 2026-09-22 noite). Duas formas seguras de evitar:
   > - **Recomendado:** usar o **GitHub Desktop** (app gratuito oficial,
   >   https://desktop.github.com) — "Add local repository" apontando para
   >   esta pasta e "Publish repository". Ele respeita o `.gitignore`
   >   automaticamente.
   > - **Pelo site:** arraste só as pastas/arquivos que devem ir (`app.py`,
   >   `README.md`, `requirements.txt`, `.gitignore`, `modules/`, `assets/`,
   >   `dados_exemplo/`, `retroanalises/`) — **nunca** arraste `dados_quasar/`.
   > Se algo sensível subir por engano, apagar o arquivo num novo commit NÃO
   > basta — ele continua acessível no histórico do Git. É preciso apagar e
   > recriar o repositório do zero.
3. **Criar uma conta gratuita no Streamlit Community Cloud:**
   - Acesse https://share.streamlit.io/signup (ou o botão "Sign up" em
     https://streamlit.io/cloud).
   - Escolha "Continue with GitHub" e autorize o Streamlit Cloud a acessar sua
     conta do GitHub (login único, sem senha nova).
4. **Publicar o app:**
   - No painel do Streamlit Cloud, clique em "New app" (ou "Create app").
   - Selecione o repositório criado no passo 2, o branch (`main`) e o arquivo
     principal: `app.py`.
   - Clique em "Deploy" — o Streamlit Cloud instala as dependências do
     `requirements.txt` e publica automaticamente. Leva alguns minutos na
     primeira vez.
5. **Guardar o link:** o Streamlit Cloud gera uma URL fixa (algo como
   `https://dimconservacao.streamlit.app`) — esse é o link para compartilhar
   com quem for usar a ferramenta. Cole o link aqui no README quando estiver
   disponível.

> **Atualizações depois de publicado:** qualquer alteração no código, se
> enviada para o mesmo repositório no GitHub, é publicada automaticamente
> pelo Streamlit Cloud no mesmo link — não precisa repetir os passos acima.

## Ambiente de desenvolvimento conhecido

- Python 3.12 em `C:\Users\18-103236\AppData\Local\Programs\Python\Python312\python.exe`
  (os aliases `python`/`py` não funcionam direto no PowerShell corporativo — use o
  caminho completo).
- Para checar sintaxe sem erro de encoding: leia o arquivo com
  `codecs.open(arquivo, 'r', 'utf-8')` antes de `ast.parse`.

### Teste automatizado (antes de publicar qualquer mudança)

Na pasta do projeto, rode:

```
C:\Users\18-103236\AppData\Local\Programs\Python\Python312\python.exe tests/test_app.py
```

O teste abre o app "por baixo dos panos" (sem navegador), carrega o inventário
de exemplo e confere que: as quantidades de Full Service/Especialistas batem
com o inventário; o "Contratado" acompanha o dimensionado; uma edição manual
não é apagada; e o modelo de crescimento funciona para os 27 estados e preenche
as abas de roçada; que a calibração por medição de campo considera todos os dias
desde a roçada; que a memória de cálculo do crescimento bate com o resultado; e que
equipamentos alternativos não dividem a área; que a tabela de substituição elimina
unidades parciais sem criar unidade nova; que a regra do Trator 4,70 respeita largura e
bloqueio; e que Aceiro/Drenagem fora usam ciclos por ano. Leva cerca de 1 minuto e termina
com `12/12 testes passaram`.
Não exige instalar nada além do que já está no `requirements.txt`.
