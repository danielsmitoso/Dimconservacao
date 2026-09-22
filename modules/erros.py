"""Tradução de erros técnicos para mensagens em português, com orientação do
que o usuário pode fazer -- o detalhe técnico original continua disponível
(para quem der suporte), mas não é a primeira coisa que a pessoa lê."""
import zipfile


def traduzir_erro(erro: Exception, contexto: str = "processar o arquivo") -> tuple[str, str]:
    """Devolve (mensagem amigável, detalhe técnico)."""
    detalhe = f"{type(erro).__name__}: {erro}"
    texto = str(erro)

    if (isinstance(erro, zipfile.BadZipFile) or "not a zip file" in texto.lower()
            or "format cannot be determined" in texto.lower()):
        msg = ("O arquivo não parece ser uma planilha Excel (.xlsx) válida — pode estar corrompido, ser um .xls "
               "antigo ou ter sido renomeado. Abra no Excel e use 'Salvar como' → Pasta de Trabalho do Excel (.xlsx).")
    elif isinstance(erro, PermissionError):
        msg = "Não foi possível abrir o arquivo — ele pode estar aberto em outro programa. Feche-o e envie novamente."
    elif isinstance(erro, UnicodeDecodeError):
        msg = ("Não consegui ler os acentos do arquivo CSV. Salve-o em Excel (.xlsx) ou como CSV com codificação UTF-8.")
    elif isinstance(erro, KeyError):
        coluna = texto.strip("'\" ")
        msg = (f"Não encontrei a coluna '{coluna}' no arquivo. Confira se o cabeçalho está na primeira linha e se "
               "os nomes das colunas seguem a planilha modelo.")
    elif "no columns to parse" in texto.lower() or type(erro).__name__ == "EmptyDataError":
        msg = "O arquivo está vazio ou sem cabeçalho. Confira se os dados começam na primeira linha da primeira aba."
    elif isinstance(erro, ValueError) and ("could not convert" in texto or "invalid literal" in texto):
        msg = ("Há valores que não são números onde deveria haver número (ex.: texto em coluna de km ou de área). "
               "Confira as colunas numéricas do arquivo.")
    elif isinstance(erro, ValueError) and any(t in texto for t in ("Worksheet", "sheet")):
        msg = "Não encontrei a aba esperada no arquivo. Confira se é o arquivo certo."
    elif isinstance(erro, ValueError):
        msg = texto  # as mensagens do próprio app já são escritas em português
    elif isinstance(erro, TypeError) and "positional argument" in texto:
        msg = ("O programa está com uma versão antiga em memória (foi atualizado enquanto estava aberto). "
               "Feche a janela do PowerShell onde o app roda, abra de novo com "
               "'python -m streamlit run app.py' e recarregue a página.")
    else:
        msg = "Ocorreu um erro inesperado ao " + contexto + ". Tente novamente; se persistir, envie o detalhe técnico abaixo a quem dá suporte."
    return msg, detalhe
