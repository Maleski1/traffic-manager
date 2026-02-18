import streamlit as st
from database import (
    criar_cliente,
    listar_clientes,
    atualizar_cliente,
    desativar_cliente,
    criar_produto,
    listar_produtos,
    desativar_produto,
)

st.title("Clientes")

# ── Cadastro ──────────────────────────────────────
st.subheader("Novo Cliente")
with st.form("novo_cliente", clear_on_submit=True):
    nome = st.text_input("Nome do cliente")
    verba = st.number_input("Verba mensal (R$)", min_value=0.0, step=100.0)
    if st.form_submit_button("Cadastrar"):
        if not nome.strip():
            st.error("Informe o nome do cliente.")
        else:
            try:
                criar_cliente(nome, verba)
                st.success(f"Cliente '{nome}' cadastrado!")
                st.rerun()
            except Exception as e:
                if "UNIQUE" in str(e):
                    st.error("Já existe um cliente com esse nome.")
                else:
                    st.error(str(e))

# ── Lista ─────────────────────────────────────────
st.subheader("Clientes Ativos")
clientes = listar_clientes()

if not clientes:
    st.info("Nenhum cliente cadastrado ainda.")
else:
    for c in clientes:
        with st.expander(f"{c['nome']}  —  Verba: R$ {c['verba_mensal']:,.2f}"):
            # ── Dados do cliente ──────────────────
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                novo_nome = st.text_input("Nome", value=c["nome"], key=f"n_{c['id']}")
            with col2:
                nova_verba = st.number_input(
                    "Verba (R$)",
                    value=c["verba_mensal"],
                    min_value=0.0,
                    step=100.0,
                    key=f"v_{c['id']}",
                )
            with col3:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Salvar", key=f"s_{c['id']}"):
                    atualizar_cliente(c["id"], novo_nome, nova_verba)
                    st.success("Atualizado!")
                    st.rerun()
                if st.button("Desativar", key=f"d_{c['id']}"):
                    desativar_cliente(c["id"])
                    st.warning(f"'{c['nome']}' desativado.")
                    st.rerun()

            # ── Produtos / Funis ──────────────────
            st.markdown("---")
            st.markdown("**Produtos / Funis**")

            produtos = listar_produtos(c["id"])
            if produtos:
                for p in produtos:
                    pc1, pc2 = st.columns([4, 1])
                    pc1.write(f"• {p['nome']}")
                    if pc2.button("Remover", key=f"rp_{p['id']}"):
                        desativar_produto(p["id"])
                        st.rerun()
            else:
                st.caption("Nenhum produto cadastrado.")

            col_np, col_btn = st.columns([3, 1])
            novo_produto = col_np.text_input(
                "Nome do produto",
                key=f"np_{c['id']}",
                placeholder="Ex: Curso X, Mentoria Y...",
                label_visibility="collapsed",
            )
            if col_btn.button("Adicionar", key=f"ap_{c['id']}"):
                if novo_produto.strip():
                    try:
                        criar_produto(c["id"], novo_produto)
                        st.success(f"Produto '{novo_produto}' adicionado!")
                        st.rerun()
                    except Exception as e:
                        if "UNIQUE" in str(e):
                            st.error("Já existe um produto com esse nome.")
                        else:
                            st.error(str(e))
                else:
                    st.error("Informe o nome do produto.")
