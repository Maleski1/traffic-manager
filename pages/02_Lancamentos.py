import streamlit as st
import pandas as pd
from datetime import date
from database import (
    init_db,
    listar_clientes,
    obter_cliente,
    listar_produtos,
    salvar_lancamento,
    listar_lancamentos_mes,
    obter_lancamento,
    obter_metricas_produto,
    excluir_lancamento,
)

init_db()
st.title("Lançamentos")

# ── Seletor de cliente (sidebar) ──────────────────
clientes = listar_clientes()
if not clientes:
    st.warning("Nenhum cliente cadastrado. Vá para a página Clientes.")
    st.stop()

opcoes = {c["id"]: c["nome"] for c in clientes}
cliente_id = st.sidebar.selectbox(
    "Cliente",
    options=list(opcoes.keys()),
    format_func=lambda x: opcoes[x],
    key="lanc_cliente",
)

cliente = obter_cliente(cliente_id)
st.subheader(f"Cliente: {cliente['nome']}")

# ── Seletor de mês ────────────────────────────────
hoje = date.today()
col_m, col_a = st.sidebar.columns(2)
mes = col_m.selectbox("Mês", range(1, 13), index=hoje.month - 1)
ano = col_a.number_input("Ano", value=hoje.year, min_value=2020, max_value=2030)

# ── Formulário ────────────────────────────────────
st.subheader("Novo Lançamento")
data_sel = st.date_input("Data", value=hoje)
existente = obter_lancamento(cliente_id, data_sel.isoformat())

produtos = listar_produtos(cliente_id)

# Carregar métricas existentes por produto
metricas_existentes = {}
if existente:
    for m in obter_metricas_produto(existente["id"]):
        metricas_existentes[m["produto_id"]] = m

with st.form("lancamento", clear_on_submit=False):
    metricas_form = []
    investimento_generico = 0.0

    if produtos:
        st.markdown("**Métricas por Produto**")
        for p in produtos:
            st.caption(f"📦 {p['nome']}")
            existing = metricas_existentes.get(p["id"], {})
            pc1, pc2, pc3, pc4 = st.columns(4)
            inv = pc1.number_input(
                "Investimento (R$)", min_value=0.0, step=10.0,
                value=existing.get("investimento", 0.0),
                key=f"i_{p['id']}",
            )
            leads = pc2.number_input(
                "Leads", min_value=0, step=1,
                value=existing.get("leads", 0),
                key=f"l_{p['id']}",
            )
            vendas = pc3.number_input(
                "Vendas", min_value=0, step=1,
                value=existing.get("vendas", 0),
                key=f"v_{p['id']}",
            )
            faturamento = pc4.number_input(
                "Faturamento (R$)", min_value=0.0, step=10.0,
                value=existing.get("faturamento", 0.0),
                key=f"f_{p['id']}",
            )
            metricas_form.append({
                "produto_id": p["id"],
                "investimento": inv,
                "leads": leads,
                "vendas": vendas,
                "faturamento": faturamento,
            })
    else:
        st.info("Nenhum produto cadastrado. Cadastre na página Clientes para separar investimento por produto.")
        investimento_generico = st.number_input(
            "Investimento total do dia (R$)",
            min_value=0.0,
            step=10.0,
            value=existente["investimento"] if existente else 0.0,
        )

    obs = st.text_input(
        "Observação",
        value=existente["observacao"] if existente else "",
    )

    label = "Atualizar" if existente else "Salvar"
    if st.form_submit_button(label):
        salvar_lancamento(
            cliente_id, data_sel.isoformat(), investimento_generico, obs,
            metricas_form if produtos else None,
        )
        # Sincroniza session_state com o BD para garantir valores corretos no próximo render
        saved = obter_lancamento(cliente_id, data_sel.isoformat())
        if saved and produtos:
            for m in obter_metricas_produto(saved["id"]):
                pid = m["produto_id"]
                st.session_state[f"i_{pid}"] = m["investimento"]
                st.session_state[f"l_{pid}"] = m["leads"]
                st.session_state[f"v_{pid}"] = m["vendas"]
                st.session_state[f"f_{pid}"] = m["faturamento"]
        st.success(f"Lançamento {'atualizado' if existente else 'salvo'}!")
        st.rerun()

# ── Tabela do mês ─────────────────────────────────
st.subheader(f"Lançamentos — {mes:02d}/{ano}")
lancamentos = listar_lancamentos_mes(cliente_id, ano, mes)

if not lancamentos:
    st.info("Nenhum lançamento neste mês.")
else:
    df = pd.DataFrame(lancamentos)

    df_display = df[["data", "investimento", "leads", "vendas", "faturamento", "roas", "cpl", "cpv"]].copy()
    df_display.columns = ["Data", "Investimento", "Leads", "Vendas", "Faturamento", "ROAS", "CPL", "CPV"]

    st.dataframe(
        df_display.style.format({
            "Investimento": "R$ {:,.2f}",
            "Faturamento": "R$ {:,.2f}",
            "ROAS": lambda v: f"{v:.2f}x" if pd.notna(v) else "—",
            "CPL": lambda v: f"R$ {v:,.2f}" if pd.notna(v) else "—",
            "CPV": lambda v: f"R$ {v:,.2f}" if pd.notna(v) else "—",
            "Leads": "{:,.0f}",
            "Vendas": "{:,.0f}",
        }),
        use_container_width=True,
        hide_index=True,
    )

    # ── Exclusão via selectbox ────────────────────
    st.markdown("---")
    opcoes_excluir = {l["id"]: f"{l['data']} — R$ {l['investimento']:,.2f}" for l in lancamentos}
    lanc_sel = st.selectbox(
        "Selecione um lançamento para excluir",
        options=list(opcoes_excluir.keys()),
        format_func=lambda x: opcoes_excluir[x],
    )
    if st.button("Excluir lançamento selecionado", type="primary"):
        excluir_lancamento(lanc_sel)
        st.success("Lançamento excluído!")
        st.rerun()
