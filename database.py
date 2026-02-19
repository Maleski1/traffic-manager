import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "traffic.db"


def _conn():
    os.makedirs(DB_PATH.parent, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE,
                verba_mensal REAL NOT NULL DEFAULT 0.0,
                ativo INTEGER NOT NULL DEFAULT 1,
                criado_em TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS produtos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id INTEGER NOT NULL,
                nome TEXT NOT NULL,
                ativo INTEGER NOT NULL DEFAULT 1,
                criado_em TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (cliente_id) REFERENCES clientes(id),
                UNIQUE(cliente_id, nome)
            );
            CREATE TABLE IF NOT EXISTS lancamentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id INTEGER NOT NULL,
                data TEXT NOT NULL,
                investimento REAL NOT NULL DEFAULT 0.0,
                leads INTEGER NOT NULL DEFAULT 0,
                vendas INTEGER NOT NULL DEFAULT 0,
                faturamento REAL NOT NULL DEFAULT 0.0,
                observacao TEXT DEFAULT '',
                criado_em TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (cliente_id) REFERENCES clientes(id),
                UNIQUE(cliente_id, data)
            );
            CREATE TABLE IF NOT EXISTS metricas_produto (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lancamento_id INTEGER NOT NULL,
                produto_id INTEGER NOT NULL,
                investimento REAL NOT NULL DEFAULT 0.0,
                leads INTEGER NOT NULL DEFAULT 0,
                vendas INTEGER NOT NULL DEFAULT 0,
                faturamento REAL NOT NULL DEFAULT 0.0,
                FOREIGN KEY (lancamento_id) REFERENCES lancamentos(id) ON DELETE CASCADE,
                FOREIGN KEY (produto_id) REFERENCES produtos(id),
                UNIQUE(lancamento_id, produto_id)
            );
        """)
        # Migração: adicionar coluna faturamento se não existir
        try:
            conn.execute("ALTER TABLE lancamentos ADD COLUMN faturamento REAL NOT NULL DEFAULT 0.0")
        except sqlite3.OperationalError:
            pass
        # Migração: adicionar coluna investimento em metricas_produto
        try:
            conn.execute("ALTER TABLE metricas_produto ADD COLUMN investimento REAL NOT NULL DEFAULT 0.0")
        except sqlite3.OperationalError:
            pass


# ── Clientes ──────────────────────────────────────

def criar_cliente(nome: str, verba_mensal: float) -> int:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO clientes (nome, verba_mensal) VALUES (?, ?)",
            (nome.strip(), verba_mensal),
        )
        return cur.lastrowid


def listar_clientes(apenas_ativos: bool = True) -> list[dict]:
    with _conn() as conn:
        sql = "SELECT * FROM clientes"
        if apenas_ativos:
            sql += " WHERE ativo = 1"
        sql += " ORDER BY nome"
        return [dict(r) for r in conn.execute(sql).fetchall()]


def obter_cliente(cliente_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM clientes WHERE id = ?", (cliente_id,)
        ).fetchone()
        return dict(row) if row else None


def atualizar_cliente(cliente_id: int, nome: str, verba_mensal: float):
    with _conn() as conn:
        conn.execute(
            "UPDATE clientes SET nome = ?, verba_mensal = ? WHERE id = ?",
            (nome.strip(), verba_mensal, cliente_id),
        )


def desativar_cliente(cliente_id: int):
    with _conn() as conn:
        conn.execute(
            "UPDATE clientes SET ativo = 0 WHERE id = ?", (cliente_id,)
        )


# ── Produtos ─────────────────────────────────────

def criar_produto(cliente_id: int, nome: str) -> int:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO produtos (cliente_id, nome) VALUES (?, ?)",
            (cliente_id, nome.strip()),
        )
        return cur.lastrowid


def listar_produtos(cliente_id: int, apenas_ativos: bool = True) -> list[dict]:
    with _conn() as conn:
        sql = "SELECT * FROM produtos WHERE cliente_id = ?"
        if apenas_ativos:
            sql += " AND ativo = 1"
        sql += " ORDER BY nome"
        return [dict(r) for r in conn.execute(sql, (cliente_id,)).fetchall()]


def desativar_produto(produto_id: int):
    with _conn() as conn:
        conn.execute("UPDATE produtos SET ativo = 0 WHERE id = ?", (produto_id,))


# ── Lançamentos ───────────────────────────────────

def salvar_lancamento(
    cliente_id: int,
    data: str,
    investimento: float = 0.0,
    observacao: str = "",
    metricas_produtos: list[dict] | None = None,
):
    """Salva lançamento diário.

    metricas_produtos: lista de dicts com keys produto_id, investimento, leads, vendas, faturamento.
    O investimento total é agregado a partir dos produtos. Se não houver produtos,
    usa o parâmetro investimento direto.
    """
    with _conn() as conn:
        # INSERT OR IGNORE preserva o id existente (evita CASCADE delete nas métricas)
        conn.execute(
            """INSERT OR IGNORE INTO lancamentos
               (cliente_id, data, investimento, leads, vendas, faturamento, observacao)
               VALUES (?, ?, 0, 0, 0, 0.0, ?)""",
            (cliente_id, data, observacao),
        )
        conn.execute(
            "UPDATE lancamentos SET observacao = ? WHERE cliente_id = ? AND data = ?",
            (observacao, cliente_id, data),
        )
        row = conn.execute(
            "SELECT id FROM lancamentos WHERE cliente_id = ? AND data = ?",
            (cliente_id, data),
        ).fetchone()
        lancamento_id = row["id"]

        # Carregar métricas existentes antes de deletar (usado como fallback)
        existing_metricas = {
            row["produto_id"]: dict(row)
            for row in conn.execute(
                "SELECT * FROM metricas_produto WHERE lancamento_id = ?", (lancamento_id,)
            ).fetchall()
        }

        # Limpar métricas antigas e inserir novas
        conn.execute("DELETE FROM metricas_produto WHERE lancamento_id = ?", (lancamento_id,))

        total_inv = 0.0
        total_leads = 0
        total_vendas = 0
        total_fat = 0.0

        if metricas_produtos:
            for m in metricas_produtos:
                ex = existing_metricas.get(m["produto_id"], {})
                # Se o formulário enviou zeros mas o BD já tinha dados, preservar BD
                form_vazio = not any([m["investimento"], m["leads"], m["vendas"], m["faturamento"]])
                tinha_dados = any([ex.get("investimento"), ex.get("leads"), ex.get("vendas"), ex.get("faturamento")])
                if form_vazio and tinha_dados:
                    inv_s = ex["investimento"]; leads_s = ex["leads"]
                    vendas_s = ex["vendas"]; fat_s = ex["faturamento"]
                else:
                    inv_s = m["investimento"]; leads_s = m["leads"]
                    vendas_s = m["vendas"]; fat_s = m["faturamento"]
                conn.execute(
                    """INSERT INTO metricas_produto
                       (lancamento_id, produto_id, investimento, leads, vendas, faturamento)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (lancamento_id, m["produto_id"], inv_s, leads_s, vendas_s, fat_s),
                )
                total_inv += inv_s
                total_leads += leads_s
                total_vendas += vendas_s
                total_fat += fat_s
        else:
            total_inv = investimento

        # Atualizar totais no lançamento
        conn.execute(
            """UPDATE lancamentos
               SET investimento = ?, leads = ?, vendas = ?, faturamento = ?
               WHERE id = ?""",
            (total_inv, total_leads, total_vendas, total_fat, lancamento_id),
        )


def listar_lancamentos_mes(cliente_id: int, ano: int, mes: int) -> list[dict]:
    prefix = f"{ano:04d}-{mes:02d}"
    with _conn() as conn:
        rows = conn.execute(
            """SELECT * FROM lancamentos
               WHERE cliente_id = ? AND data LIKE ?
               ORDER BY data""",
            (cliente_id, f"{prefix}%"),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        inv = d["investimento"]
        d["cpl"] = round(inv / d["leads"], 2) if d["leads"] else None
        d["cpv"] = round(inv / d["vendas"], 2) if d["vendas"] else None
        d["roas"] = round(d["faturamento"] / inv, 2) if inv else None
        result.append(d)
    return result


def obter_lancamento(cliente_id: int, data: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM lancamentos WHERE cliente_id = ? AND data = ?",
            (cliente_id, data),
        ).fetchone()
        return dict(row) if row else None


def obter_metricas_produto(lancamento_id: int) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """SELECT mp.*, p.nome as produto_nome
               FROM metricas_produto mp
               JOIN produtos p ON p.id = mp.produto_id
               WHERE mp.lancamento_id = ?
               ORDER BY p.nome""",
            (lancamento_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def excluir_lancamento(lancamento_id: int):
    with _conn() as conn:
        conn.execute("DELETE FROM metricas_produto WHERE lancamento_id = ?", (lancamento_id,))
        conn.execute("DELETE FROM lancamentos WHERE id = ?", (lancamento_id,))


def resumo_mensal(cliente_id: int, ano: int, mes: int) -> dict:
    prefix = f"{ano:04d}-{mes:02d}"
    with _conn() as conn:
        row = conn.execute(
            """SELECT
                 COALESCE(SUM(investimento), 0) as total_investido,
                 COALESCE(SUM(leads), 0) as total_leads,
                 COALESCE(SUM(vendas), 0) as total_vendas,
                 COALESCE(SUM(faturamento), 0) as total_faturamento,
                 COUNT(*) as dias
               FROM lancamentos
               WHERE cliente_id = ? AND data LIKE ?""",
            (cliente_id, f"{prefix}%"),
        ).fetchone()
        d = dict(row)
        d["cpl_medio"] = (
            round(d["total_investido"] / d["total_leads"], 2)
            if d["total_leads"]
            else None
        )
        d["cpv_medio"] = (
            round(d["total_investido"] / d["total_vendas"], 2)
            if d["total_vendas"]
            else None
        )
        d["roas"] = (
            round(d["total_faturamento"] / d["total_investido"], 2)
            if d["total_investido"]
            else None
        )
        return d


def resumo_mensal_por_produto(cliente_id: int, ano: int, mes: int) -> list[dict]:
    prefix = f"{ano:04d}-{mes:02d}"
    with _conn() as conn:
        rows = conn.execute(
            """SELECT
                 p.id as produto_id,
                 p.nome as produto_nome,
                 COALESCE(SUM(mp.investimento), 0) as total_investimento,
                 COALESCE(SUM(mp.leads), 0) as total_leads,
                 COALESCE(SUM(mp.vendas), 0) as total_vendas,
                 COALESCE(SUM(mp.faturamento), 0) as total_faturamento
               FROM metricas_produto mp
               JOIN lancamentos l ON l.id = mp.lancamento_id
               JOIN produtos p ON p.id = mp.produto_id
               WHERE l.cliente_id = ? AND l.data LIKE ?
               GROUP BY p.id, p.nome
               ORDER BY p.nome""",
            (cliente_id, f"{prefix}%"),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            inv = d["total_investimento"]
            d["roas"] = round(d["total_faturamento"] / inv, 2) if inv else None
            d["cpl"] = round(inv / d["total_leads"], 2) if d["total_leads"] else None
            d["conversao"] = round(d["total_vendas"] / d["total_leads"] * 100, 1) if d["total_leads"] else None
            result.append(d)
        return result


def metricas_diarias_por_produto(cliente_id: int, ano: int, mes: int) -> list[dict]:
    prefix = f"{ano:04d}-{mes:02d}"
    with _conn() as conn:
        rows = conn.execute(
            """SELECT
                 l.data,
                 p.nome as produto_nome,
                 mp.investimento,
                 mp.leads,
                 mp.vendas,
                 mp.faturamento
               FROM metricas_produto mp
               JOIN lancamentos l ON l.id = mp.lancamento_id
               JOIN produtos p ON p.id = mp.produto_id
               WHERE l.cliente_id = ? AND l.data LIKE ?
               ORDER BY l.data, p.nome""",
            (cliente_id, f"{prefix}%"),
        ).fetchall()
        return [dict(r) for r in rows]
