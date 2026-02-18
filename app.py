import streamlit as st
from database import init_db

st.set_page_config(page_title="Traffic Manager", layout="wide")

init_db()

# ── CSS Global ────────────────────────────────────
st.markdown("""
<style>
    /* Esconder menu hamburger e footer */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Cards de métricas com borda lateral colorida */
    div[data-testid="stMetric"] {
        background: rgba(27, 110, 243, 0.08);
        border-left: 4px solid #1B6EF3;
        border-radius: 8px;
        padding: 12px 16px;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.4rem;
        font-weight: 700;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        opacity: 0.8;
    }

    /* Espaçamento entre seções */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    h2, h3 {
        margin-top: 1.5rem !important;
    }

    /* Expanders mais limpos */
    details[data-testid="stExpander"] {
        border: 1px solid rgba(250, 250, 250, 0.1);
        border-radius: 8px;
        margin-bottom: 8px;
    }

    /* Dataframes */
    .stDataFrame {
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────
st.sidebar.title("Traffic Manager")

# ── Home ──────────────────────────────────────────
st.title("Traffic Manager")
st.markdown("Gerencie investimentos, leads e vendas dos seus clientes de tráfego.")
st.markdown(
    """
    **Páginas:**
    - **Clientes** — cadastrar e gerenciar clientes
    - **Lançamentos** — registrar métricas diárias
    - **Dashboard** — resumo mensal com barra de verba
    """
)
