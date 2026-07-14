"""
lotofacil_pkg/v20_5_validacao_cientifica.py
--------------------------------------------
Validação Científica Automática — V20.5

Objetivo: transformar resultados de backtest em métricas objetivas e comparáveis,
permitindo saber exatamente quais módulos contribuem e quais apenas adicionam
complexidade.

Funções exportadas:
  benchmark_vs_aleatorio     — compara média de acertos do robô contra apostas aleatórias
  benchmark_vs_base          — compara contra estratégia-base fixa (dezenas mais frequentes)
  estabilidade_por_janela    — calcula score de estabilidade em múltiplas janelas históricas
  ranking_versoes            — ordena versões do robô por score composto
  ganho_estatistico          — calcula ganho real (em desvios-padrão) sobre o aleatório
  relatorio_validacao        — consolida todas as métricas em um único dict/JSON

Notas de design:
  - Todas as funções são puras (sem I/O, sem estado global).
  - I/O (salvar JSON) fica em gerar_relatorio_validacao(), separado da lógica.
  - "Ganho estatístico" é expresso em desvios-padrão (efeito-z), não em percentual,
    para evitar inflar resultados em amostras pequenas.
"""
import json
import math
import random
from statistics import mean, stdev
from typing import Any


# ── helpers internos ──────────────────────────────────────────────────────────

def _media_acertos(resultados: list[dict]) -> float:
    """Média de acertos por registro. Aceita 'acertos' ou 'media_acertos'."""
    if not resultados:
        return 0.0
    vals = [float(r.get("acertos", r.get("media_acertos", 0.0))) for r in resultados]
    return mean(vals)


def _desvio_acertos(resultados: list[dict]) -> float:
    """Desvio padrão dos acertos. Retorna 0.0 se menos de 2 registros."""
    if len(resultados) < 2:
        return 0.0
    vals = [float(r.get("acertos", r.get("media_acertos", 0.0))) for r in resultados]
    return stdev(vals)


def _simular_aleatório(n_jogos: int, n_concursos: int, seed: int | None = 42) -> list[dict]:
    """
    Gera resultados simulados de apostas completamente aleatórias.

    Cada jogo aleatório escolhe 15 números de 1–25; o 'concurso' também é
    aleatório. Usado como baseline interno quando não há histórico externo.

    Args:
        n_jogos:     jogos por concurso simulado.
        n_concursos: quantidade de concursos a simular.
        seed:        semente para reprodutibilidade (None = aleatório).

    Returns:
        Lista de dicts com chave 'acertos' (média de acertos do lote de jogos).
    """
    rng = random.Random(seed)
    numeros = list(range(1, 26))
    resultados = []
    for _ in range(n_concursos):
        sorteio = set(rng.sample(numeros, 15))
        acertos_lote = [
            len(set(rng.sample(numeros, 15)) & sorteio)
            for _ in range(n_jogos)
        ]
        resultados.append({"acertos": mean(acertos_lote)})
    return resultados


# ── funções públicas ──────────────────────────────────────────────────────────

def benchmark_vs_aleatorio(
    resultados_robo: list[dict],
    n_jogos_por_concurso: int = 10,
    seed: int | None = 42,
) -> dict[str, Any]:
    """
    Compara o desempenho médio do robô contra apostas completamente aleatórias.

    Simula internamente um baseline aleatório com o mesmo número de concursos
    e jogos por concurso que o robô avaliou.

    Args:
        resultados_robo:       lista de dicts com 'acertos' ou 'media_acertos'.
        n_jogos_por_concurso:  jogos simulados por concurso no baseline aleatório.
        seed:                  semente para o baseline (None = não-determinístico).

    Returns:
        Dict com:
          - media_robo:      média de acertos do robô
          - media_aleatorio: média de acertos do baseline aleatório
          - delta:           media_robo - media_aleatorio (positivo = melhor)
          - ganho_relativo:  delta / media_aleatorio (fração; 0.0 se baseline = 0)
          - veredito:        "SUPERIOR", "EQUIVALENTE" ou "INFERIOR"
    """
    n = len(resultados_robo)
    if n == 0:
        return {
            "media_robo": 0.0,
            "media_aleatorio": 0.0,
            "delta": 0.0,
            "ganho_relativo": 0.0,
            "veredito": "SEM_DADOS",
        }

    aleatorio = _simular_aleatório(n_jogos_por_concurso, n, seed=seed)
    media_robo = round(_media_acertos(resultados_robo), 4)
    media_ale = round(_media_acertos(aleatorio), 4)
    delta = round(media_robo - media_ale, 4)
    ganho_rel = round(delta / media_ale, 4) if media_ale else 0.0

    if delta > 0.05:
        veredito = "SUPERIOR"
    elif delta < -0.05:
        veredito = "INFERIOR"
    else:
        veredito = "EQUIVALENTE"

    return {
        "media_robo": media_robo,
        "media_aleatorio": media_ale,
        "delta": delta,
        "ganho_relativo": ganho_rel,
        "veredito": veredito,
    }


def benchmark_vs_base(
    resultados_robo: list[dict],
    resultados_base: list[dict],
) -> dict[str, Any]:
    """
    Compara o robô contra uma estratégia-base externa (ex.: dezenas mais frequentes).

    Args:
        resultados_robo:  lista de dicts com 'acertos' ou 'media_acertos'.
        resultados_base:  lista de dicts com 'acertos' ou 'media_acertos'.
                          Pode ter tamanho diferente — a comparação usa médias.

    Returns:
        Dict com:
          - media_robo:   média de acertos do robô
          - media_base:   média de acertos da estratégia-base
          - delta:        media_robo - media_base
          - veredito:     "SUPERIOR", "EQUIVALENTE" ou "INFERIOR"
    """
    media_robo = round(_media_acertos(resultados_robo), 4)
    media_base = round(_media_acertos(resultados_base), 4)
    delta = round(media_robo - media_base, 4)

    if delta > 0.05:
        veredito = "SUPERIOR"
    elif delta < -0.05:
        veredito = "INFERIOR"
    else:
        veredito = "EQUIVALENTE"

    return {
        "media_robo": media_robo,
        "media_base": media_base,
        "delta": delta,
        "veredito": veredito,
    }


def estabilidade_por_janela(
    resultados: list[dict],
    janelas: dict[str, int] | None = None,
) -> dict[str, Any]:
    """
    Calcula a média de acertos nas últimas N entradas para cada janela definida.

    Permite identificar se o robô é mais consistente em janelas curtas (recentes)
    ou longas (histórico amplo).

    Args:
        resultados: lista de dicts com 'acertos' ou 'media_acertos', em ordem
                    cronológica (mais antigo primeiro).
        janelas:    dict {nome: tamanho}, ex. {"30d": 30, "60d": 60, "90d": 90}.
                    Se None, usa {"30": 30, "60": 60, "90": 90}.

    Returns:
        Dict {nome_janela: {"media": float, "desvio": float, "n": int}}.
    """
    if janelas is None:
        janelas = {"30": 30, "60": 60, "90": 90}

    resultado = {}
    for nome, tamanho in janelas.items():
        fatia = resultados[-tamanho:] if len(resultados) >= tamanho else resultados
        n = len(fatia)
        media = round(_media_acertos(fatia), 4) if n > 0 else 0.0
        desvio = round(_desvio_acertos(fatia), 4) if n >= 2 else 0.0
        resultado[nome] = {"media": media, "desvio": desvio, "n": n}
    return resultado


def ganho_estatistico(
    resultados_robo: list[dict],
    n_jogos_por_concurso: int = 10,
    seed: int | None = 42,
) -> dict[str, Any]:
    """
    Calcula o ganho estatístico do robô sobre o aleatório em desvios-padrão (z-score).

    Um z > 0 significa que o robô está acima do esperado por acaso.
    Interpretação prática:
      z < 0.5  → ganho desprezível
      z ∈ [0.5, 1.0) → ganho pequeno
      z ∈ [1.0, 2.0) → ganho moderado
      z >= 2.0 → ganho relevante (estatisticamente)

    Args:
        resultados_robo:      lista de dicts com 'acertos' ou 'media_acertos'.
        n_jogos_por_concurso: jogos simulados por concurso no baseline.
        seed:                 semente para reprodutibilidade.

    Returns:
        Dict com:
          - z_score:      (media_robo - media_aleatorio) / desvio_aleatorio
          - interpretacao: label legível
          - media_robo:   média de acertos do robô
          - media_aleatorio, desvio_aleatorio: parâmetros do baseline
    """
    n = len(resultados_robo)
    if n == 0:
        return {
            "z_score": 0.0,
            "interpretacao": "SEM_DADOS",
            "media_robo": 0.0,
            "media_aleatorio": 0.0,
            "desvio_aleatorio": 0.0,
        }

    aleatorio = _simular_aleatório(n_jogos_por_concurso, n, seed=seed)
    media_robo = _media_acertos(resultados_robo)
    media_ale = _media_acertos(aleatorio)
    desvio_ale = _desvio_acertos(aleatorio)

    if desvio_ale == 0.0:
        z = 0.0
    else:
        z = (media_robo - media_ale) / desvio_ale

    z = round(z, 4)

    if z >= 2.0:
        interpretacao = "GANHO_RELEVANTE"
    elif z >= 1.0:
        interpretacao = "GANHO_MODERADO"
    elif z >= 0.5:
        interpretacao = "GANHO_PEQUENO"
    elif z >= -0.5:
        interpretacao = "EQUIVALENTE_AO_ALEATORIO"
    else:
        interpretacao = "ABAIXO_DO_ALEATORIO"

    return {
        "z_score": z,
        "interpretacao": interpretacao,
        "media_robo": round(media_robo, 4),
        "media_aleatorio": round(media_ale, 4),
        "desvio_aleatorio": round(desvio_ale, 4),
    }


def ranking_versoes(
    versoes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Ordena versões do robô por score composto decrescente.

    Cada entrada deve conter ao menos:
      - "nome":  identificador da versão (ex. "V19", "V20.1")
      - "score": valor numérico [0, 1] representando desempenho geral

    Campos opcionais usados como critério de desempate:
      - "z_score":    ganho estatístico sobre aleatório (peso secundário)
      - "estabilidade": score de estabilidade (peso terciário)

    Args:
        versoes: lista de dicts descrevendo cada versão.

    Returns:
        Lista ordenada do melhor para o pior, com campo "posicao" adicionado.
    """
    def _chave(v: dict) -> tuple:
        return (
            float(v.get("score", 0.0)),
            float(v.get("z_score", 0.0)),
            float(v.get("estabilidade", 0.0)),
        )

    ordenadas = sorted(versoes, key=_chave, reverse=True)
    for i, v in enumerate(ordenadas, start=1):
        v["posicao"] = i
    return ordenadas


def relatorio_validacao(
    resultados_robo: list[dict],
    resultados_base: list[dict] | None = None,
    versoes: list[dict] | None = None,
    n_jogos_por_concurso: int = 10,
    seed: int | None = 42,
    janelas: dict[str, int] | None = None,
) -> dict[str, Any]:
    """
    Consolida todas as métricas de validação científica em um único relatório.

    Args:
        resultados_robo:      histórico de resultados do robô.
        resultados_base:      resultados da estratégia-base (opcional).
        versoes:              lista de versões para ranking (opcional).
        n_jogos_por_concurso: jogos por concurso no baseline aleatório.
        seed:                 semente para reprodutibilidade.
        janelas:              dict de janelas para estabilidade (ver estabilidade_por_janela).

    Returns:
        Dict com seções:
          - vs_aleatorio:    resultado de benchmark_vs_aleatorio()
          - vs_base:         resultado de benchmark_vs_base() ou None
          - estabilidade:    resultado de estabilidade_por_janela()
          - ganho:           resultado de ganho_estatistico()
          - ranking_versoes: resultado de ranking_versoes() ou []
          - resumo:          dict com campos de alto nível para exibição rápida
    """
    vs_ale = benchmark_vs_aleatorio(resultados_robo, n_jogos_por_concurso, seed)
    vs_base = (
        benchmark_vs_base(resultados_robo, resultados_base)
        if resultados_base is not None
        else None
    )
    estab = estabilidade_por_janela(resultados_robo, janelas)
    ganho = ganho_estatistico(resultados_robo, n_jogos_por_concurso, seed)
    rank = ranking_versoes(list(versoes)) if versoes else []

    resumo = {
        "total_concursos_avaliados": len(resultados_robo),
        "media_acertos_robo": vs_ale["media_robo"],
        "veredito_vs_aleatorio": vs_ale["veredito"],
        "veredito_vs_base": vs_base["veredito"] if vs_base else "N/A",
        "z_score": ganho["z_score"],
        "interpretacao_ganho": ganho["interpretacao"],
        "versao_lider": rank[0]["nome"] if rank else "N/A",
    }

    return {
        "vs_aleatorio": vs_ale,
        "vs_base": vs_base,
        "estabilidade": estab,
        "ganho": ganho,
        "ranking_versoes": rank,
        "resumo": resumo,
    }


def gerar_relatorio_validacao(
    resultados_robo: list[dict],
    arquivo: str = "validacao_cientifica.json",
    resultados_base: list[dict] | None = None,
    versoes: list[dict] | None = None,
    n_jogos_por_concurso: int = 10,
    seed: int | None = 42,
    janelas: dict[str, int] | None = None,
) -> dict[str, Any]:
    """
    Gera e persiste o relatório de validação científica em JSON.

    Esta é a única função com I/O neste módulo. Toda a lógica fica em
    relatorio_validacao(), que é pura e testável sem disco.

    Args:
        arquivo: caminho de saída do JSON.
        (demais args: ver relatorio_validacao)

    Returns:
        O mesmo dict retornado por relatorio_validacao().
    """
    dados = relatorio_validacao(
        resultados_robo,
        resultados_base=resultados_base,
        versoes=versoes,
        n_jogos_por_concurso=n_jogos_por_concurso,
        seed=seed,
        janelas=janelas,
    )
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)
    return dados
