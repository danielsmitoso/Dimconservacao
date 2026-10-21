"""Senha do time e leitura dos secrets (configurados no Streamlit Cloud)."""
from __future__ import annotations

import hmac

import streamlit as st


def segredo(secao: str, chave: str) -> str | None:
    """Valor de [secao] chave nos secrets, ou None se não configurado
    (rodando local sem .streamlit/secrets.toml)."""
    try:
        return st.secrets[secao][chave]
    except Exception:  # noqa: BLE001 -- sem arquivo/seção/chave: tudo vira None
        return None


def exigir_senha() -> None:
    """Pede a senha do time antes de mostrar qualquer dado. Sem senha
    configurada (uso local), libera direto."""
    senha = segredo("app", "senha")
    if not senha or st.session_state.get("autenticado"):
        return
    st.markdown("#### 🔒 Acesso restrito ao time")
    with st.form("login"):
        digitada = st.text_input("Senha do time", type="password")
        entrar = st.form_submit_button("Entrar")
    if entrar:
        if hmac.compare_digest(digitada.encode(), str(senha).encode()):
            st.session_state["autenticado"] = True
            st.rerun()
        st.error("Senha incorreta.")
    st.stop()
