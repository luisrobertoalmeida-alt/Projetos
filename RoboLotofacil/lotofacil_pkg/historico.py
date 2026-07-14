"""
lotofacil_pkg/historico.py
---------------------------
Carregamento e normalização do histórico de concursos a partir de CSV.
"""
import os
import pandas as pd

from . import config as _cfg
from .config import MIN_HIST, ARQUIVO_CSV_PADRAO, NUMEROS, TAMANHO_JOGO
from .utils import parse_data_br, contar_pares, soma_jogo, intersecao, distancia_jogos, limitar
from collections import Counter
from statistics import mean
import math

from .persistencia import normalizar_df_resultados, carregar_csv_resultados


def contar_linhas_arquivo(caminho_csv: str) -> int:
    """Conta linhas do arquivo eficientemente sem carregar todo o conteúdo em memória."""
    with open(caminho_csv, "r", encoding="utf-8-sig", errors="ignore") as f:
        total = 0
        for _ in f:
            total += 1
        return total


def carregar_csv_ultimas_linhas(caminho_csv: str, ultimas_linhas: int | None = None) -> list[str]:
    if ultimas_linhas is None:
        return pd.read_csv(caminho_csv)

    total_linhas = contar_linhas_arquivo(caminho_csv)
    if total_linhas <= 1:
        return pd.read_csv(caminho_csv)

    dados = max(0, total_linhas - 1)
    if ultimas_linhas >= dados:
        return pd.read_csv(caminho_csv)

    pular = dados - ultimas_linhas
    skiprows = range(1, pular + 1)
    return pd.read_csv(caminho_csv, skiprows=skiprows)


def carregar_concursos_do_csv(caminho_csv: str, limite: int | None = None) -> list[list[int]]:
    if not os.path.exists(caminho_csv):
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho_csv}")

    total_linhas = contar_linhas_arquivo(caminho_csv)
    total_concursos_csv = max(0, total_linhas - 1)
    df = carregar_csv_ultimas_linhas(caminho_csv, ultimas_linhas=limite)

    cols = [f"d{i}" for i in range(1, 16)]
    for c in cols:
        if c not in df.columns:
            raise ValueError(f"CSV inválido. Coluna ausente: {c}")
    concursos = []
    for _, row in df.iterrows():
        jogo = sorted(int(row[c]) for c in cols)
        if len(set(jogo)) == _cfg.TAMANHO_JOGO and all(1 <= n <= 25 for n in jogo):
            concursos.append(jogo)
    if len(concursos) < MIN_HIST:
        raise ValueError(f"Histórico insuficiente: {len(concursos)} concursos válidos. Use ao menos {MIN_HIST}.")
    return concursos, df, total_concursos_csv


# =========================================================
# ANÁLISE HISTÓRICA
# =========================================================

def detectar_ciclo_historico(hist: list, janela_curta: int = 20, janela_base: int = 80) -> dict:
    """
    Detecta o regime recente do histórico: repetição, dispersão, soma e paridade.
    Não prevê sorteio; apenas orienta o comportamento do robô.
    """
    hist = hist or []
    if len(hist) < 12:
        return {
            "ciclo_principal": "indefinido",
            "descricao": "Histórico insuficiente para leitura de ciclo.",
        }
    curta = hist[-min(janela_curta, len(hist)):]
    base = hist[-min(janela_base, len(hist)):]

    def medias(seq: list) -> dict:
        somas = [sum(j) for j in seq]
        pares = [contar_pares(j) for j in seq]
        inters = [intersecao(seq[i-1], seq[i]) for i in range(1, len(seq))]
        return {
            "soma": mean(somas) if somas else 195.0,
            "pares": mean(pares) if pares else 7.5,
            "inter": mean(inters) if inters else 9.0,
        }

    m_curta = medias(curta)
    m_base = medias(base)
    delta_inter = m_curta["inter"] - m_base["inter"]
    delta_soma = m_curta["soma"] - m_base["soma"]
    delta_pares = m_curta["pares"] - m_base["pares"]

    if delta_inter >= 0.55:
        ciclo = "alta_repeticao"
        desc = "Ciclo recente com maior repetição entre concursos; favorece Markov/tendência com cautela."
    elif delta_inter <= -0.55:
        ciclo = "alta_dispersao"
        desc = "Ciclo recente mais disperso; favorece cobertura, diversidade e menor concentração."
    elif delta_soma >= 8:
        ciclo = "soma_alta"
        desc = "Ciclo recente com soma média acima da base."
    elif delta_soma <= -8:
        ciclo = "soma_baixa"
        desc = "Ciclo recente com soma média abaixo da base."
    else:
        ciclo = "estavel"
        desc = "Ciclo recente próximo da média histórica usada."

    return {
        "ciclo_principal": ciclo,
        "descricao": desc,
        "media_curta_intersecao": round(m_curta["inter"], 3),
        "media_base_intersecao": round(m_base["inter"], 3),
        "delta_intersecao": round(delta_inter, 3),
        "media_curta_soma": round(m_curta["soma"], 3),
        "media_base_soma": round(m_base["soma"], 3),
        "delta_soma": round(delta_soma, 3),
        "media_curta_pares": round(m_curta["pares"], 3),
        "media_base_pares": round(m_base["pares"], 3),
        "delta_pares": round(delta_pares, 3),
    }

def analisar_historico(concursos: list, janela: int = 120) -> dict:
    hist = concursos[-janela:] if len(concursos) >= janela else concursos[:]

    freq = Counter()
    recentes = Counter()
    atrasos = {}
    pares_hist = []
    somas_hist = []
    intersecoes = []

    for i, concurso in enumerate(hist):
        freq.update(concurso)
        pares_hist.append(contar_pares(concurso))
        somas_hist.append(sum(concurso))
        if i >= max(0, len(hist) - 20):
            recentes.update(concurso)

    # Calcula atrasos em passagem única O(n) em vez de O(numeros * hist)
    ultima_vez = {}
    for i, concurso in enumerate(hist):
        for n in concurso:
            ultima_vez[n] = i
    for n in NUMEROS:
        atrasos[n] = len(hist) - 1 - ultima_vez[n] if n in ultima_vez else len(hist)

    for i in range(1, len(hist)):
        intersecoes.append(intersecao(hist[i - 1], hist[i]))

    # Métricas adicionais para o Motor Estratégico Inteligente
    soma_media = mean(somas_hist) if somas_hist else 195.0
    pares_media = mean(pares_hist) if pares_hist else 7.5
    inter_media = mean(intersecoes) if intersecoes else 9.0
    desvio_soma = math.sqrt(mean([(x - soma_media) ** 2 for x in somas_hist])) if somas_hist else 0.0
    desvio_pares = math.sqrt(mean([(x - pares_media) ** 2 for x in pares_hist])) if pares_hist else 0.0
    desvio_inter = math.sqrt(mean([(x - inter_media) ** 2 for x in intersecoes])) if intersecoes else 0.0

    return {
        "hist_usado": hist,
        "freq": freq,
        "recentes": recentes,
        "atrasos": atrasos,
        "pares_media": pares_media,
        "soma_media": soma_media,
        "intersecao_media": inter_media,
        "desvio_soma": desvio_soma,
        "desvio_pares": desvio_pares,
        "desvio_intersecao": desvio_inter,
        "ciclo": detectar_ciclo_historico(hist),
    }


