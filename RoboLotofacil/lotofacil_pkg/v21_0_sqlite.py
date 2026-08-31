"""
lotofacil_pkg/v21_0_sqlite.py
------------------------------
V21.1-A — Camada SQLite integrada ao RoboLotofacilPro.

Substitui gradualmente os JSONs por persistência unificada em SQLite,
mantendo compatibilidade total com o código existente (os JSONs
continuam funcionando em paralelo durante a transição).

Uso:
    from .v21_0_sqlite import get_db, inicializar_banco_v21
    conn = get_db()
"""

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
import math
import logging

from .config import PASTA_DADOS

# ── Configuração ──────────────────────────────────────────────────────────────
_DB_PATH  = Path(PASTA_DADOS) / "lotofacil_v21.db"
_LOG_PATH = Path(PASTA_DADOS) / "v21_2.log"
_local    = threading.local()

# Garante que a pasta existe antes de abrir o log (evita FileNotFoundError
# quando o diretório ainda não foi criado pela primeira execução).
_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(filename=str(_LOG_PATH), level=logging.ERROR)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_db() -> sqlite3.Connection:
    """Retorna conexão thread-safe (singleton por thread)."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return _local.conn


# ── Schema ────────────────────────────────────────────────────────────────────
_SCHEMA = """
CREATE TABLE IF NOT EXISTS modelos (
    id           TEXT PRIMARY KEY,
    nome         TEXT NOT NULL,
    status       TEXT DEFAULT 'ATIVO',
    score        REAL DEFAULT 0.0,
    criado_em    TEXT NOT NULL,
    atualizado_em TEXT
);

CREATE TABLE IF NOT EXISTS pesos_modelos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id      TEXT NOT NULL,
    peso          REAL NOT NULL,
    concurso      INTEGER,
    atualizado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS desempenho (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    data_registro     TEXT NOT NULL,
    origem            TEXT DEFAULT 'manual',
    concurso          INTEGER,
    resultado_real    TEXT,
    qtd_jogos         INTEGER,
    melhor_acerto     INTEGER,
    media_acertos     REAL,
    distribuicao      TEXT,
    modo              TEXT,
    indice_confianca  REAL,
    diversidade       REAL,
    taxa_mutacao      REAL,
    metadata          TEXT
);

CREATE TABLE IF NOT EXISTS ranking_modelos (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    nome             TEXT NOT NULL,
    score_cientifico REAL,
    media_melhor     REAL,
    media_geral      REAL,
    pct_11_mais      REAL,
    pct_12_mais      REAL,
    pct_13_mais      REAL,
    geracoes         INTEGER,
    ultimos          TEXT,
    atualizado_em    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS historico_eventos (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    evento     TEXT NOT NULL,
    model_id   TEXT,
    payload    TEXT,
    criado_em  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS geracoes_performance (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    data               TEXT NOT NULL,
    qtd_jogos          INTEGER,
    janela             INTEGER,
    geracoes           INTEGER,
    pop_size           INTEGER,
    modo               TEXT,
    diversidade        REAL,
    taxa_mutacao       REAL,
    media_sobreposicao REAL,
    max_sobreposicao   INTEGER,
    score_estrutural   REAL,
    metadata           TEXT
);

CREATE TABLE IF NOT EXISTS contexto_concurso (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    concurso INTEGER,
    repetidas INTEGER,
    pares INTEGER,
    impares INTEGER,
    soma_total INTEGER,
    dispersao REAL,
    criado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS aprendizado_registros (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    data_registro  TEXT NOT NULL,
    origem         TEXT,
    concurso       INTEGER,
    melhor_acerto  INTEGER,
    media_acertos  REAL,
    modo           TEXT,
    payload        TEXT
);

CREATE TABLE IF NOT EXISTS elo_modelos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id      TEXT NOT NULL,
    elo           REAL NOT NULL,
    concurso      INTEGER,
    atualizado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS walkforward_indicadores (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    robustez_temporal  REAL,
    estabilidade       REAL,
    overfitting_nivel  TEXT,
    trend_robustez     TEXT,
    n_janelas          INTEGER,
    delta_vs_baseline  REAL,
    score_robustez_raw REAL,
    concurso_inicio    INTEGER,
    concurso_fim       INTEGER,
    payload            TEXT,
    criado_em          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hall_fama (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    nome             TEXT NOT NULL,
    elo              REAL,
    media_acertos    REAL,
    pct_11_mais      REAL,
    pct_12_mais      REAL,
    pct_13_mais      REAL,
    score_composto   REAL,
    janela           TEXT,
    posicao          INTEGER,
    criado_em        TEXT NOT NULL
);
"""


def inicializar_banco_v21() -> bool:
    """Cria todas as tabelas. Idempotente — seguro chamar sempre na inicialização."""
    conn = get_db()
    conn.executescript(_SCHEMA)
    conn.commit()
    return True


# ── Gravadores — chamados pelos módulos existentes ────────────────────────────

def db_registrar_desempenho(registro: dict) -> None:
    """
    Espelha um registro de desempenho (já gravado em JSON) no SQLite.
    Chamado por backtest.registrar_desempenho_historico_robo().
    """
    conn = get_db()
    try:
        with conn:
            conn.execute("""
                INSERT INTO desempenho
                (data_registro, origem, concurso, resultado_real, qtd_jogos,
                 melhor_acerto, media_acertos, distribuicao, modo,
                 indice_confianca, diversidade, taxa_mutacao, metadata)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                registro.get("data_registro", _now()),
                registro.get("origem", "manual"),
                registro.get("concurso"),
                json.dumps(registro.get("resultado_real", [])),
                registro.get("qtd_jogos"),
                registro.get("melhor_acerto"),
                registro.get("media_acertos"),
                json.dumps(registro.get("distribuicao_acertos", {})),
                registro.get("modo"),
                registro.get("indice_confianca"),
                registro.get("diversidade"),
                registro.get("taxa_mutacao"),
                json.dumps({k: v for k, v in registro.items()
                            if k not in ("data_registro", "origem", "concurso",
                                         "resultado_real", "qtd_jogos", "melhor_acerto",
                                         "media_acertos", "distribuicao_acertos", "modo",
                                         "indice_confianca", "diversidade", "taxa_mutacao")}),
            ))
    except Exception:
        pass  # Nunca quebra o fluxo principal


def db_registrar_evento_poda(nome: str, estado: str, score: float, peso_novo: float) -> None:
    """
    Espelha resultado da poda inteligente no SQLite.
    Chamado por v20_2_poda_inteligente.avaliar_e_podar_modelos().
    """
    conn = get_db()
    try:
        evento = "suspensão" if estado == "SUSPENSO" else ("observacao" if estado == "OBSERVACAO" else "ativo")
        with conn:
            conn.execute("""
                INSERT INTO historico_eventos (evento, model_id, payload, criado_em)
                VALUES (?,?,?,?)
            """, (evento, nome, json.dumps({"estado": estado, "score": score, "peso_novo": peso_novo}), _now()))
    except Exception:
        pass


def db_registrar_ranking_cientifico(ranking: list) -> None:
    """
    Espelha ranking do backtest científico no SQLite.
    Chamado por backtest.executar_backtest_cientifico_massivo().
    """
    conn = get_db()
    try:
        with conn:
            for r in ranking:
                conn.execute("""
                    INSERT INTO ranking_modelos
                    (nome, score_cientifico, media_melhor, media_geral,
                     pct_11_mais, pct_12_mais, pct_13_mais, geracoes, ultimos, atualizado_em)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                """, (
                    r.get("nome"), r.get("score_cientifico"),
                    r.get("media_melhor"), r.get("media_geral"),
                    r.get("pct_11_mais"), r.get("pct_12_mais"), r.get("pct_13_mais"),
                    r.get("geracoes"), json.dumps(r.get("ultimos", [])), _now()
                ))
    except Exception:
        pass


def db_registrar_geracao(geracao: dict) -> None:
    """
    Espelha uma geração de apostas no SQLite.
    Chamado por apostas.registrar_performance_geracao().
    """
    conn = get_db()
    try:
        with conn:
            conn.execute("""
                INSERT INTO geracoes_performance
                (data, qtd_jogos, janela, geracoes, pop_size, modo,
                 diversidade, taxa_mutacao, media_sobreposicao, max_sobreposicao,
                 score_estrutural, metadata)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                geracao.get("data", _now()),
                geracao.get("qtd_jogos"), geracao.get("janela"),
                geracao.get("geracoes"), geracao.get("pop_size"), geracao.get("modo"),
                geracao.get("diversidade"), geracao.get("taxa_mutacao"),
                geracao.get("media_sobreposicao"), geracao.get("max_sobreposicao"),
                geracao.get("score_estrutural_medio"),
                json.dumps({k: v for k, v in geracao.items()
                            if k not in ("data", "qtd_jogos", "janela", "geracoes",
                                         "pop_size", "modo", "diversidade", "taxa_mutacao",
                                         "media_sobreposicao", "max_sobreposicao",
                                         "score_estrutural_medio")}),
            ))
    except Exception:
        pass


def db_registrar_aprendizado(registro: dict) -> None:
    """
    Espelha um registro de aprendizado no SQLite.
    Chamado por aprendizado.registrar_resultado_aprendizado().
    """
    conn = get_db()
    try:
        with conn:
            conn.execute("""
                INSERT INTO aprendizado_registros
                (data_registro, origem, concurso, melhor_acerto, media_acertos, modo, payload)
                VALUES (?,?,?,?,?,?,?)
            """, (
                registro.get("data_registro", _now()),
                registro.get("origem", "manual"),
                registro.get("concurso"),
                registro.get("melhor_acerto"),
                registro.get("media_acertos"),
                registro.get("modo"),
                json.dumps(registro),
            ))
    except Exception:
        pass


# ── Leitores — usados pelo dashboard e meta-aprendizado ──────────────────────

def db_ranking_modelos(limit: int = 20) -> list[dict]:
    conn = get_db()
    rows = conn.execute("""
        SELECT nome, score_cientifico, media_melhor, media_geral,
               pct_11_mais, pct_12_mais, atualizado_em
        FROM ranking_modelos
        ORDER BY atualizado_em DESC, score_cientifico DESC
        LIMIT ?
    """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def db_desempenho_recente(limit: int = 30) -> list[dict]:
    conn = get_db()
    rows = conn.execute("""
        SELECT data_registro, concurso, melhor_acerto, media_acertos, qtd_jogos, modo
        FROM desempenho
        ORDER BY data_registro DESC
        LIMIT ?
    """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def db_eventos_recentes(limit: int = 50) -> list[dict]:
    conn = get_db()
    rows = conn.execute("""
        SELECT evento, model_id, payload, criado_em
        FROM historico_eventos
        ORDER BY criado_em DESC
        LIMIT ?
    """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def db_prob_recuperacao(model_id: str) -> float:
    """Probabilidade de recuperação com suavização Bayesiana."""
    conn = get_db()
    rows = conn.execute("""
        SELECT evento FROM historico_eventos
        WHERE model_id = ? AND evento IN ('suspensão', 'observacao', 'ativo')
        ORDER BY criado_em
    """, (model_id,)).fetchall()
    if not rows:
        return 0.5
    susps = sum(1 for r in rows if r["evento"] in ("suspensão", "observacao"))
    recs = sum(1 for r in rows if r["evento"] == "ativo")
    eventos=max(len(rows),1)
    prob=(recs+1)/(susps+2) if susps>0 else 0.5
    confianca=min(1.0,eventos/20)
    return round(0.5*(1-confianca)+prob*confianca,4)

def db_limiar_dinamico(percentil: float = 20.0) -> float:
    conn = get_db()
    rows = conn.execute("""
        SELECT media_acertos FROM desempenho
        WHERE media_acertos > 0
        ORDER BY data_registro DESC
        LIMIT 200
    """).fetchall()
    scores = sorted([r["media_acertos"] for r in rows])
    if len(scores) < 5:
        return 0.0
    p=max(0,min(100,percentil))/100.0
    pos=(len(scores)-1)*p
    lo=int(math.floor(pos)); hi=int(math.ceil(pos))
    if lo==hi: return float(scores[lo])
    return float(scores[lo] + (scores[hi]-scores[lo])*(pos-lo))


# Nota (2026-07-19): db_salvar_peso_modelo/db_ultimos_pesos foram removidas
# — nunca tinham nenhum chamador real (só v21_3_1_dashboard_real.py, também
# removido por ser código órfão). A tabela pesos_modelos segue existindo no
# schema, mas nada grava nela; ver ARQUITETURA.md.
