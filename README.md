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

Se o projeto já estiver publicado no Streamlit Community Cloud, basta abrir o link
que foi compartilhado com você em qualquer navegador (Chrome, Edge) — não precisa
instalar Python nem nada no seu computador.

> **Pendente:** o link de publicação ainda não existe nesta versão — ver
> `retroanalises/perguntas_pendentes.md`. Enquanto isso, use as instruções abaixo
> para rodar localmente.

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
2. **Aba Roçada Manual**: escolha *Metas de performance* ou *Personalizado*, ajuste ciclos
   e meses (chuva/seca). A **proposta de divisão de equipes** enche cada equipe até a
   capacidade do ciclo, na ordem dos km, cortando o trecho onde a capacidade acaba —
   só a última equipe pode ter folga. Dá para aceitar uma ocupação máxima acima de 100%
   e impedir que uma equipe atravesse de uma rodovia para outra.
3. **Aba Roçada Mecanizada**: a área mecanizada é distribuída entre os equipamentos que
   o Quasar indica (Trator 4.7m, Trator 1.7m, Trator com braço articulado, Eixo-zero,
   Spider). Mostra a frota necessária por equipamento (somável), o equipamento
   recomendado por trecho (com o mix e a justificativa técnica) e a divisão de trechos
   por unidade de cada equipamento. Informe a frota disponível para ver sobra/falta.
4. **Aba Full Service**: aceiro, drenagem, capina, refilamento, calçada, placas, remoção de lixo.
5. **Aba Especialistas**: EPS/barreira, defensa metálica, NC, varrição, poda.
6. **Aba Análise de Contrato**: informe quantas equipes/unidades o contrato atual prevê por
   atividade e veja déficit/excedente (com %).
7. **Aba Exportar Relatório**: baixe (a) o **PowerPoint executivo** e (b) a **memória de
   cálculo em Excel**, com premissas em azul e o cálculo passo a passo em fórmulas do
   Excel, para conferir qualquer número.

> **Tudo se atualiza sozinho:** números e textos são recalculados a cada alteração, e os
> arquivos para download são montados no momento do clique, com o estado atual da tela.

## Estrutura do projeto

```
app.py                      # aplicação Streamlit (interface)
modules/
  dimensionamento.py         # motor de cálculo (equipes = f(quantidade, produtividade, ciclos))
  parametros_padrao.py       # valores-padrão de produtividade/ciclos/metas (editável)
  inventario.py               # leitura/validação da planilha de inventário
  quasar.py                   # leitura, auditoria e agregação do export Quasar (satélite)
  mecanizacao.py              # equipamento por trecho, frota mecanizada
  export_excel.py             # memória de cálculo em Excel (fórmulas)
  export_pptx.py              # geração do relatório executivo em PowerPoint
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
   - Suba os arquivos desta pasta — pelo site do GitHub (arrastar e soltar os
     arquivos em "uploading an existing file") é o caminho mais simples para
     quem não usa `git` no dia a dia; não é necessário subir a pasta
     `dados_quasar/` (já está no `.gitignore` por conter dado sensível).
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
