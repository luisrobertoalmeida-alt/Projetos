"""
lotofacil_pkg/v21_5_meta_competitivo.py
-----------------------------------------
V21.5-FULL — Meta-Aprendizado Competitivo Real.

Implementa um sistema de ranking ELO para os modelos do ensemble.
Cada concurso simulado no backtest é tratado como uma "partida":
  - o modelo que teve mais acertos ganha ELO
  - o modelo que teve menos acertos perde ELO

O ELO alimenta diretamente o fator multiplicativo usado em analise.py:
    peso_final = peso_base * fator_elo(modelo)

Funções exportadas:
  atualizar_elo_concurso   — atualiza ELOs a partir de acertos por modelo
  fator_elo                — converte ELO em fator multiplicativo [0.5, 2.0]
  get_ranking_elo          — retorna ranking atual ordenado por ELO
  salvar_elo               — persiste no SQLite
  carregar_elo             — carrega do SQLite (fallback JSON)
  relatorio_meta_competitivo — relatório completo para o dashboard
"""
import json
import math
from datetime import datetime, timezone
from statistics import mean, stdev
from pathlib import Path

from .config import PASTA_DADOS, MODELOS_ENSEMBLE

# ── Parâmetros ELO ─────────────────────────────────────────────────────────
ELO_INICIAL    = 1500.0
ELO_K_FACTOR   = 32.0      # sensibilidade: quanto o ELO muda por partida
ELO_MIN        = 1000.0
ELO_MAX        = 2500.0
FATOR_MIN      = 0.50      # modelo em má fase: recebe 50% do peso base
FATOR_MAX      = 2.00      # modelo em boa fase: recebe até 200% do peso base
ELO_REFERENCIA = 1500.0    # ponto neutro → fator = 1.0

_ARQ_ELO = Path(PASTA_DADOS) / "elo_modelos.json"

# ── Modelos conhecidos ──────────────────────────────────────────────────────
MODELOS_PADRAO = list(MODELOS_ENSEMBLE)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Persistência (JSON como camada primária; SQLite espelhado quando disponível)
def carregar_elo() -> dict:
    """Carrega ELOs persistidos. Retorna dict {nome: elo}."""
    # Tenta SQLite primeiro
    try:
        from .v21_0_sqlite import get_db
        conn = get_db()
        rows = conn.execute("""
            SELECT model_id, elo
            FROM elo_modelos
            WHERE id IN (
                SELECT MAX(id) FROM elo_modelos GROUP BY model_id
            )
        """).fetchall()
        if rows:
            return {r["model_id"]: float(r["elo"]) for r in rows}
    except Exception:
        pass

    # Fallback JSON
    if _ARQ_ELO.exists():
        try:
            data = json.loads(_ARQ_ELO.read_text(encoding="utf-8"))
            return {k: float(v) for k, v in data.items()}
        except Exception:
            pass

    return {m: ELO_INICIAL for m in MODELOS_PADRAO}


def salvar_elo(elos: dict, concurso: int | None = None) -> None:
    """Persiste ELOs no JSON e espelha no SQLite."""
    _ARQ_ELO.parent.mkdir(parents=True, exist_ok=True)
    _ARQ_ELO.write_text(
        json.dumps(elos, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    # Espelha no SQLite se disponível
    try:
        from .v21_0_sqlite import get_db
        conn = get_db()
        ts = _now()
        with conn:
            for nome, elo in elos.items():
                conn.execute(
                    "INSERT INTO elo_modelos (model_id, elo, concurso, atualizado_em) VALUES (?,?,?,?)",
                    (nome, elo, concurso, ts)
                )
    except Exception:
        pass


def _prob_esperada_elo(elo_a: float, elo_b: float) -> float:
    """Probabilidade esperada de A vencer B segundo a fórmula ELO."""
    return 1.0 / (1.0 + 10.0 ** ((elo_b - elo_a) / 400.0))


def _clipar(valor: float, minimo: float, maximo: float) -> float:
    return max(minimo, min(maximo, valor))


def atualizar_elo_concurso(
    acertos_por_modelo: dict[str, float],
    concurso: int | None = None,
) -> dict:
    """
    Atualiza o ELO de cada modelo com base nos acertos obtidos num concurso.

    Estratégia de torneio: cada modelo disputa contra a média dos demais.
    Acertos acima da média = vitória; abaixo = derrota; igual = empate.

    Args:
        acertos_por_modelo: {nome_modelo: media_acertos_neste_concurso}
        concurso: número do concurso simulado (para rastreabilidade)

    Returns:
        dict com elos_anteriores, elos_novos, deltas, vencedor e concurso
    """
    if not acertos_por_modelo:
        return {}

    elos = carregar_elo()
    # Garante que todos os modelos presentes têm ELO
    for nome in acertos_por_modelo:
        if nome not in elos:
            elos[nome] = ELO_INICIAL

    acertos_list = list(acertos_por_modelo.values())
    media_geral = mean(acertos_list) if acertos_list else 0.0

    elos_anteriores = dict(elos)
    elos_novos = dict(elos)
    deltas = {}

    for nome, acertos in acertos_por_modelo.items():
        elo_a = elos[nome]

        # Adversário virtual: o "modelo médio" tem ELO = média dos demais
        outros = [v for n, v in elos.items() if n != nome]
        elo_adversario = mean(outros) if outros else ELO_INICIAL

        # Resultado: 1=vitória, 0=derrota, 0.5=empate
        if acertos > media_geral + 0.1:
            resultado = 1.0
        elif acertos < media_geral - 0.1:
            resultado = 0.0
        else:
            resultado = 0.5

        esperado = _prob_esperada_elo(elo_a, elo_adversario)
        delta = ELO_K_FACTOR * (resultado - esperado)
        novo_elo = _clipar(elo_a + delta, ELO_MIN, ELO_MAX)

        elos_novos[nome] = round(novo_elo, 2)
        deltas[nome] = round(delta, 2)

    salvar_elo(elos_novos, concurso=concurso)

    vencedor = max(acertos_por_modelo, key=lambda n: acertos_por_modelo[n])
    return {
        "concurso":        concurso,
        "acertos_modelos": acertos_por_modelo,
        "media_acertos":   round(media_geral, 4),
        "elos_anteriores": elos_anteriores,
        "elos_novos":      elos_novos,
        "deltas":          deltas,
        "vencedor":        vencedor,
    }


def fator_elo(nome: str, elos: dict | None = None) -> float:
    """
    Converte o ELO de um modelo em fator multiplicativo para o peso base.

    ELO 1500 (neutro)  → fator 1.00
    ELO 1700 (+200)    → fator ~1.7783
    ELO 1300 (-200)    → fator ~0.5623
    ELO 1000 (mínimo)  → fator 0.50 (clampado — a fórmula pura daria ~0.2371)
    ELO 2500 (máximo)  → fator 2.00 (clampado — a fórmula pura daria ~17.7828)

    Fórmula: fator = 10^( (elo - 1500) / 800 )
    clampado em [FATOR_MIN, FATOR_MAX].
    """
    if elos is None:
        elos = carregar_elo()
    elo = elos.get(nome, ELO_INICIAL)
    fator = 10.0 ** ((elo - ELO_REFERENCIA) / 800.0)
    return round(_clipar(fator, FATOR_MIN, FATOR_MAX), 4)


def fatores_elo_todos(elos: dict | None = None) -> dict:
    """Retorna {nome_modelo: fator_elo} para todos os modelos conhecidos."""
    if elos is None:
        elos = carregar_elo()
    return {nome: fator_elo(nome, elos) for nome in elos}


def get_ranking_elo(elos: dict | None = None) -> list[dict]:
    """
    Retorna lista ordenada por ELO decrescente.
    Cada entrada: {posicao, nome, elo, fator, status}
    """
    if elos is None:
        elos = carregar_elo()

    ranking = []
    for pos, (nome, elo) in enumerate(
        sorted(elos.items(), key=lambda x: x[1], reverse=True), start=1
    ):
        fator = fator_elo(nome, elos)
        if elo >= 1600:
            status = "🏆 DESTAQUE"
        elif elo >= 1500:
            status = "✅ ATIVO"
        elif elo >= 1350:
            status = "👁 OBSERVAÇÃO"
        elif elo >= 1200:
            status = "⚠️ QUARENTENA"
        else:
            status = "🚫 SUSPENSO"

        ranking.append({
            "posicao": pos,
            "nome":    nome,
            "elo":     elo,
            "fator":   fator,
            "status":  status,
        })
    return ranking


def relatorio_meta_competitivo() -> dict:
    """
    Gera relatório completo do sistema competitivo para o dashboard.

    Returns:
        dict com ranking, campeão, estatísticas e histórico recente de ELO
    """
    elos = carregar_elo()
    ranking = get_ranking_elo(elos)
    fatores = fatores_elo_todos(elos)

    # Histórico de ELO por concurso (últimas 50 entradas por modelo)
    historico_elo = {}
    try:
        from .v21_0_sqlite import get_db
        conn = get_db()
        for nome in elos:
            rows = conn.execute("""
                SELECT elo, concurso, atualizado_em
                FROM elo_modelos
                WHERE model_id = ?
                ORDER BY id DESC LIMIT 50
            """, (nome,)).fetchall()
            historico_elo[nome] = [
                {"elo": r["elo"], "concurso": r["concurso"]}
                for r in reversed(rows)
            ]
    except Exception:
        pass

    campeao = ranking[0] if ranking else {}
    ultimos = ranking[-1] if len(ranking) > 1 else {}

    elo_vals = list(elos.values())
    return {
        "ranking":           ranking,
        "fatores":           fatores,
        "campeao":           campeao,
        "ultimo_colocado":   ultimos,
        "historico_elo":     historico_elo,
        "estatisticas": {
            "media_elo":   round(mean(elo_vals), 1) if elo_vals else ELO_INICIAL,
            "max_elo":     round(max(elo_vals), 1) if elo_vals else ELO_INICIAL,
            "min_elo":     round(min(elo_vals), 1) if elo_vals else ELO_INICIAL,
            "desvio_elo":  round(stdev(elo_vals), 1) if len(elo_vals) > 1 else 0.0,
        },
        "versao": "V21.5-FULL",
        "timestamp": _now(),
    }
