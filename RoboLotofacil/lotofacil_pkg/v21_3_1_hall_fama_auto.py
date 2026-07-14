"""
lotofacil_pkg/v21_3_1_hall_fama_auto.py
-----------------------------------------
V21.5-FULL — Hall da Fama de Modelos.

Registra automaticamente o ranking dos modelos após cada backtest
e mantém histórico separado por janela temporal:
  - Últimos 500 concursos
  - Últimos 1000 concursos
  - Geral (todos os backtests)

O Hall da Fama combina ELO + score científico + médias de acertos
para produzir um ranking composto estável.

Funções exportadas:
  registrar_hall_fama          — registra um snapshot do ranking
  get_hall_fama                — retorna o ranking atual por janela
  relatorio_hall_fama          — texto formatado para o dashboard
  registrar_hall_fama_auto     — interface compatível com V21.3.1 anterior
"""
import json
from datetime import datetime, timezone
from statistics import mean


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _score_composto(
    elo: float,
    media_acertos: float,
    pct_11: float,
    pct_12: float,
    pct_13: float,
) -> float:
    """
    Score composto para o Hall da Fama.
    Combina ELO normalizado + acertos médios + taxas de prêmio.
    Escala: quanto maior, melhor.
    """
    elo_norm    = (elo - 1000.0) / 1500.0          # 0→0, 1500→0.33, 2500→1.0
    acertos_norm = max(0.0, (media_acertos - 9.0) / 4.0)  # 9→0, 13→1.0
    taxa_premio  = 0.50 * pct_11 + 0.35 * pct_12 + 0.15 * pct_13
    return round(
        0.35 * elo_norm + 0.40 * acertos_norm + 0.25 * taxa_premio, 6
    )


def registrar_hall_fama(
    ranking_cientifico: list[dict],
    janela: str = "geral",
) -> list[dict]:
    """
    Registra um snapshot do ranking no Hall da Fama (SQLite).

    Args:
        ranking_cientifico: lista de dicts com campos do backtest científico
                            (nome, score_cientifico, media_melhor, media_geral,
                             pct_11_mais, pct_12_mais, pct_13_mais)
        janela: "500", "1000" ou "geral"

    Returns:
        Lista de dicts do ranking registrado (com score_composto e posicao).
    """
    # Busca ELOs atuais para enriquecer o ranking
    elos = {}
    try:
        from .v21_5_meta_competitivo import carregar_elo
        elos = carregar_elo()
    except Exception:
        pass

    entradas = []
    for r in ranking_cientifico:
        nome = r.get("nome", "")
        elo  = elos.get(nome, 1500.0)
        media_acertos = r.get("media_geral", r.get("media_melhor", 0.0))
        pct_11 = r.get("pct_11_mais", 0.0)
        pct_12 = r.get("pct_12_mais", 0.0)
        pct_13 = r.get("pct_13_mais", 0.0)
        sc = _score_composto(elo, media_acertos, pct_11, pct_12, pct_13)
        entradas.append({
            "nome":          nome,
            "elo":           round(elo, 1),
            "media_acertos": round(media_acertos, 4),
            "pct_11_mais":   round(pct_11, 4),
            "pct_12_mais":   round(pct_12, 4),
            "pct_13_mais":   round(pct_13, 4),
            "score_composto": sc,
            "janela":         janela,
        })

    # Ordena pelo score composto
    entradas.sort(key=lambda x: x["score_composto"], reverse=True)
    for pos, e in enumerate(entradas, start=1):
        e["posicao"] = pos

    # Persiste no SQLite
    try:
        from .v21_0_sqlite import get_db
        conn = get_db()
        ts = _now()
        with conn:
            for e in entradas:
                conn.execute("""
                    INSERT INTO hall_fama
                    (nome, elo, media_acertos, pct_11_mais, pct_12_mais,
                     pct_13_mais, score_composto, janela, posicao, criado_em)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                """, (
                    e["nome"], e["elo"], e["media_acertos"],
                    e["pct_11_mais"], e["pct_12_mais"], e["pct_13_mais"],
                    e["score_composto"], e["janela"], e["posicao"], ts,
                ))
    except Exception:
        pass

    return entradas


def get_hall_fama(janela: str = "geral", limit: int = 20) -> list[dict]:
    """
    Retorna o ranking mais recente do Hall da Fama para a janela indicada.

    Args:
        janela: "500", "1000" ou "geral"
        limit:  máximo de entradas retornadas

    Returns:
        Lista de dicts ordenada por posição, com campos completos.
    """
    try:
        from .v21_0_sqlite import get_db
        conn = get_db()

        # Pega o timestamp mais recente para a janela
        row = conn.execute("""
            SELECT MAX(criado_em) as ts FROM hall_fama WHERE janela = ?
        """, (janela,)).fetchone()

        if not row or not row["ts"]:
            return []

        ts_max = row["ts"]
        rows = conn.execute("""
            SELECT nome, elo, media_acertos, pct_11_mais, pct_12_mais,
                   pct_13_mais, score_composto, posicao, criado_em
            FROM hall_fama
            WHERE janela = ? AND criado_em = ?
            ORDER BY posicao ASC
            LIMIT ?
        """, (janela, ts_max, limit)).fetchall()

        return [dict(r) for r in rows]
    except Exception:
        return []


def relatorio_hall_fama(janela: str = "geral") -> str:
    """Relatório formatado do Hall da Fama para o dashboard."""
    ranking = get_hall_fama(janela)

    if not ranking:
        # Tenta construir a partir dos dados de ELO disponíveis
        try:
            from .v21_5_meta_competitivo import get_ranking_elo
            ranking_elo = get_ranking_elo()
            if not ranking_elo:
                return "Hall da Fama ainda não populado.\nExecute o Backtest Científico para gerar dados."
            linhas = [
                f"Hall da Fama — Ranking ELO (janela: {janela})",
                "=" * 55,
            ]
            for e in ranking_elo[:7]:
                linhas.append(
                    f"  {e['posicao']}º  {e['nome']:<14}  "
                    f"ELO {e['elo']:.0f}  {e['status']}"
                )
            return "\n".join(linhas)
        except Exception:
            return "Hall da Fama ainda não populado.\nExecute o Backtest Científico para gerar dados."

    titulo = {
        "500":   "Últimos 500 concursos",
        "1000":  "Últimos 1000 concursos",
        "geral": "Geral (todos os backtests)",
    }.get(janela, janela)

    linhas = [
        f"🏆 Hall da Fama — {titulo}",
        "=" * 60,
        f"{'Pos':<4} {'Modelo':<14} {'ELO':>6} {'Média':>6} {'11+':>5} {'12+':>5} {'Score':>7}",
        "-" * 60,
    ]
    for e in ranking:
        linhas.append(
            f"  {e['posicao']:<3} {e['nome']:<14} "
            f"{e['elo']:>6.0f} "
            f"{e['media_acertos']:>6.3f} "
            f"{e['pct_11_mais']*100:>4.1f}% "
            f"{e['pct_12_mais']*100:>4.1f}% "
            f"{e['score_composto']:>7.4f}"
        )
    return "\n".join(linhas)


def registrar_hall_fama_auto(registrar_func, resultado: dict) -> None:
    """
    Interface compatível com o stub da V21.3.1.
    Agora faz a persistência real via registrar_hall_fama().
    'registrar_func' é ignorado (era um wrapper sem implementação).
    """
    try:
        # Tenta extrair ranking do resultado do backtest científico
        ranking_raw = resultado.get("ranking_modelos") or resultado.get("ranking") or []
        if ranking_raw:
            registrar_hall_fama(ranking_raw, janela="geral")
            return

        # Fallback: cria entrada única com os dados disponíveis
        nome = resultado.get("configuracao", resultado.get("modelo", "desconhecido"))
        entrada = [{
            "nome":          nome,
            "score_cientifico": resultado.get("score", 0.0),
            "media_melhor":  resultado.get("maximo", 0.0),
            "media_geral":   resultado.get("media", 0.0),
            "pct_11_mais":   resultado.get("taxa11", 0.0),
            "pct_12_mais":   resultado.get("taxa12", 0.0),
            "pct_13_mais":   resultado.get("taxa13", 0.0),
        }]
        registrar_hall_fama(entrada, janela="geral")
    except Exception:
        pass
