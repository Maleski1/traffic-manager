import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
from database import (
    init_db, listar_clientes, obter_cliente,
    resumo_mensal, listar_lancamentos_mes,
    resumo_mensal_por_produto, metricas_diarias_por_produto,
)

init_db()
st.title("Dashboard")

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
    key="dash_cliente",
)

cliente = obter_cliente(cliente_id)
st.subheader(f"Cliente: {cliente['nome']}")

# ── Seletor de mês ────────────────────────────────
hoje = date.today()
col_m, col_a = st.sidebar.columns(2)
mes = col_m.selectbox("Mês", range(1, 13), index=hoje.month - 1)
ano = col_a.number_input("Ano", value=hoje.year, min_value=2020, max_value=2030)

resumo = resumo_mensal(cliente_id, ano, mes)
verba = cliente["verba_mensal"]

# ── Mês anterior (para delta) ─────────────────────
if mes == 1:
    mes_ant, ano_ant = 12, ano - 1
else:
    mes_ant, ano_ant = mes - 1, ano

resumo_ant = resumo_mensal(cliente_id, ano_ant, mes_ant)


def _delta(atual, anterior):
    """Retorna string delta % e o valor numérico para st.metric."""
    if not anterior or anterior == 0:
        return None
    pct = (atual - anterior) / anterior * 100
    return f"{pct:+.1f}%"


# ── Barra de verba (HTML/CSS) ─────────────────────
st.subheader("Consumo da Verba")

if verba > 0:
    pct = resumo["total_investido"] / verba
    pct_display = min(pct, 1.0)
    pct_text = f"{pct:.0%}"

    if pct > 0.8:
        bar_color = "#EF4444"
    elif pct > 0.6:
        bar_color = "#F59E0B"
    else:
        bar_color = "#22C55E"

    st.markdown(f"""
    <div style="
        background: rgba(250,250,250,0.08);
        border-radius: 10px;
        height: 36px;
        position: relative;
        overflow: hidden;
        margin-bottom: 8px;
    ">
        <div style="
            background: linear-gradient(90deg, {bar_color}CC, {bar_color});
            width: {pct_display * 100:.1f}%;
            height: 100%;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            min-width: 60px;
            transition: width 0.5s ease;
        ">
            <span style="
                color: white;
                font-weight: 700;
                font-size: 0.85rem;
                text-shadow: 0 1px 2px rgba(0,0,0,0.3);
            ">{pct_text}</span>
        </div>
    </div>
    <p style="margin: 0; font-size: 0.9rem; opacity: 0.8;">
        <strong>R$ {resumo['total_investido']:,.2f}</strong> de
        <strong>R$ {verba:,.2f}</strong>
    </p>
    """, unsafe_allow_html=True)

    if pct > 1.0:
        st.error("Verba ultrapassada!")
    elif pct > 0.8:
        st.warning("Verba quase esgotada.")
else:
    st.info("Verba mensal não definida para este cliente.")

# ── Métricas gerais (com delta vs mês anterior) ───
st.subheader("Resumo do Mês")

# Conversão geral
conversao = round(resumo["total_vendas"] / resumo["total_leads"] * 100, 1) if resumo["total_leads"] else None
conversao_ant = round(resumo_ant["total_vendas"] / resumo_ant["total_leads"] * 100, 1) if resumo_ant["total_leads"] else None

c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
c1.metric(
    "Investido", f"R$ {resumo['total_investido']:,.2f}",
    delta=_delta(resumo["total_investido"], resumo_ant["total_investido"]),
    delta_color="inverse",
)
c2.metric(
    "Faturamento", f"R$ {resumo['total_faturamento']:,.2f}",
    delta=_delta(resumo["total_faturamento"], resumo_ant["total_faturamento"]),
)
c3.metric(
    "ROAS", f"{resumo['roas']:.2f}x" if resumo["roas"] else "—",
    delta=_delta(resumo["roas"], resumo_ant["roas"]) if resumo["roas"] and resumo_ant["roas"] else None,
)
c4.metric(
    "Leads", resumo["total_leads"],
    delta=_delta(resumo["total_leads"], resumo_ant["total_leads"]),
)
c5.metric(
    "Vendas", resumo["total_vendas"],
    delta=_delta(resumo["total_vendas"], resumo_ant["total_vendas"]),
)
cpl_str = f"R$ {resumo['cpl_medio']:,.2f}" if resumo["cpl_medio"] else "—"
c6.metric(
    "CPL Médio", cpl_str,
    delta=_delta(resumo["cpl_medio"], resumo_ant["cpl_medio"]) if resumo["cpl_medio"] and resumo_ant["cpl_medio"] else None,
    delta_color="inverse",
)
c7.metric(
    "Conversão", f"{conversao:.1f}%" if conversao else "—",
    delta=_delta(conversao, conversao_ant) if conversao and conversao_ant else None,
)

# ── Breakdown por produto ─────────────────────────
resumo_produtos = resumo_mensal_por_produto(cliente_id, ano, mes)

if resumo_produtos:
    st.subheader("Desempenho por Produto")

    cols_prod = st.columns(len(resumo_produtos))
    for i, rp in enumerate(resumo_produtos):
        with cols_prod[i]:
            st.markdown(f"**{rp['produto_nome']}**")
            st.metric("Investimento", f"R$ {rp['total_investimento']:,.2f}")
            st.metric("Leads", rp["total_leads"])
            st.metric("Vendas", rp["total_vendas"])
            st.metric("Faturamento", f"R$ {rp['total_faturamento']:,.2f}")
            st.metric("ROAS", f"{rp['roas']:.2f}x" if rp["roas"] else "—")
            st.metric("Conversão", f"{rp['conversao']:.1f}%" if rp["conversao"] else "—")

    # ── Pizza: Distribuição de investimento ────────
    df_pie = pd.DataFrame(resumo_produtos)
    if df_pie["total_investimento"].sum() > 0:
        st.subheader("Distribuição de Investimento por Produto")
        fig_pie = px.pie(
            df_pie,
            values="total_investimento",
            names="produto_nome",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig_pie.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#FAFAFA",
            margin=dict(l=0, r=0, t=40, b=0),
        )
        fig_pie.update_traces(textinfo="percent+label", textfont_size=13)
        st.plotly_chart(fig_pie, use_container_width=True)

# ── Gráficos Plotly ───────────────────────────────
lancamentos = listar_lancamentos_mes(cliente_id, ano, mes)

plotly_layout = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font_color="#FAFAFA",
    margin=dict(l=0, r=0, t=40, b=0),
    xaxis=dict(showgrid=False),
    yaxis=dict(showgrid=True, gridcolor="rgba(250,250,250,0.06)"),
)

if lancamentos:
    df = pd.DataFrame(lancamentos)
    df["data"] = pd.to_datetime(df["data"])

    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.subheader("Investimento Diário")
        fig_inv = px.area(
            df, x="data", y="investimento",
            labels={"data": "Data", "investimento": "R$"},
            color_discrete_sequence=["#1B6EF3"],
        )
        fig_inv.update_traces(
            fill="tozeroy",
            fillcolor="rgba(27,110,243,0.15)",
            line=dict(width=2.5),
        )
        fig_inv.update_layout(**plotly_layout)
        st.plotly_chart(fig_inv, use_container_width=True)

    with col_g2:
        st.subheader("ROAS Diário")
        df_roas = df.dropna(subset=["roas"])
        if not df_roas.empty:
            fig_roas = px.line(
                df_roas, x="data", y="roas",
                labels={"data": "Data", "roas": "ROAS"},
                color_discrete_sequence=["#F59E0B"],
                markers=True,
            )
            fig_roas.add_hline(
                y=1.0, line_dash="dash", line_color="rgba(239,68,68,0.5)",
                annotation_text="Break-even",
                annotation_font_color="#EF4444",
            )
            fig_roas.update_layout(**plotly_layout)
            st.plotly_chart(fig_roas, use_container_width=True)
        else:
            st.info("Sem dados de faturamento para calcular ROAS.")

    # ── Gráficos por produto ──────────────────────
    dados_prod = metricas_diarias_por_produto(cliente_id, ano, mes)

    if dados_prod:
        df_mp = pd.DataFrame(dados_prod)
        df_mp["data"] = pd.to_datetime(df_mp["data"])

        col_g3, col_g4 = st.columns(2)

        with col_g3:
            st.subheader("Leads por Produto")
            fig_leads = px.bar(
                df_mp, x="data", y="leads", color="produto_nome",
                labels={"data": "Data", "leads": "Leads", "produto_nome": "Produto"},
                barmode="group",
            )
            fig_leads.update_layout(**plotly_layout)
            st.plotly_chart(fig_leads, use_container_width=True)

        with col_g4:
            st.subheader("Vendas por Produto")
            fig_vendas = px.bar(
                df_mp, x="data", y="vendas", color="produto_nome",
                labels={"data": "Data", "vendas": "Vendas", "produto_nome": "Produto"},
                barmode="group",
            )
            fig_vendas.update_layout(**plotly_layout)
            st.plotly_chart(fig_vendas, use_container_width=True)
    else:
        col_g3, col_g4 = st.columns(2)
        with col_g3:
            st.subheader("Leads por Dia")
            fig_leads = px.bar(
                df, x="data", y="leads",
                labels={"data": "Data", "leads": "Leads"},
                color_discrete_sequence=["#8B5CF6"],
            )
            fig_leads.update_layout(**plotly_layout)
            st.plotly_chart(fig_leads, use_container_width=True)
        with col_g4:
            st.subheader("Vendas por Dia")
            fig_vendas = px.bar(
                df, x="data", y="vendas",
                labels={"data": "Data", "vendas": "Vendas"},
                color_discrete_sequence=["#22C55E"],
            )
            fig_vendas.update_layout(**plotly_layout)
            st.plotly_chart(fig_vendas, use_container_width=True)
else:
    st.info("Sem lançamentos para exibir gráficos.")
