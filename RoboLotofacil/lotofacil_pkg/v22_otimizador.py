"""
lotofacil_pkg/v22_otimizador.py
--------------------------------
Otimizador de pacotes por simulação V22.

Em vez de ajustar G/P e esperar que os jogos sejam bons,
gera múltiplos pacotes candidatos e seleciona o melhor
com base na simulação de 1000 sorteios artificiais.

Critério de aceite (gate de sanidade): % de pacotes com pelo menos 11
pontos (pct_11_mais) — evento quase saturado no aleatório, serve só
para descartar erro grosseiro, não para escolher entre bons candidatos.
Critério de ranking entre candidatos (score): pesa mais média do melhor
jogo, 12+ e 13+ (pct_12_mais/pct_13_mais) — eventos mais raros, que de
fato diferenciam um candidato do outro (ver 2026-07-19 no ARQUITETURA.md).

Uso:
    from .v22_otimizador import otimizar_pacote
    jogos, analise, pesos, relatorio = otimizar_pacote(
        concursos, fn_gerar,
        limiar_11=0.93,
        max_tentativas=10,
        status_cb=print,
    )
"""

from __future__ import annotations
import random
import math
from typing import Callable, Any

from .config import NUMEROS, TAMANHO_JOGO


# ─────────────────────────────────────────────────────────────────────────────
# Simulador interno (versão leve — sem o auditor completo)
# ─────────────────────────────────────────────────────────────────────────────

def _simular_pacote(jogos: list, n_simulacoes: int = 500) -> dict:
    """
    Simula n_simulacoes sorteios e retorna métricas do pacote.
    Versão leve para uso em loop de otimização.
    """
    jogos_sets = [frozenset(int(d) for d in jogo) for jogo in jogos]
    numeros = list(NUMEROS)

    melhores = []
    eventos_11 = 0
    eventos_12 = 0
    eventos_13 = 0

    for _ in range(n_simulacoes):
        sorteio = frozenset(random.sample(numeros, TAMANHO_JOGO))
        acertos = [len(jogo & sorteio) for jogo in jogos_sets]
        melhor = max(acertos)
        melhores.append(melhor)
        if melhor >= 11: eventos_11 += 1
        if melhor >= 12: eventos_12 += 1
        if melhor >= 13: eventos_13 += 1

    total = max(len(melhores), 1)
    media = sum(melhores) / total

    return {
        "pct_11_mais":  round(100 * eventos_11 / total, 1),
        "pct_12_mais":  round(100 * eventos_12 / total, 1),
        "pct_13_mais":  round(100 * eventos_13 / total, 1),
        "media_melhor": round(media, 3),
        "max_melhor":   max(melhores) if melhores else 0,
        "n_simulacoes": n_simulacoes,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Otimizador principal
# ─────────────────────────────────────────────────────────────────────────────

def otimizar_pacote(
    concursos: list,
    fn_gerar: Callable,
    limiar_11: float = 93.0,        # % mínimo de 11+ para aceitar
    limiar_media: float = 11.20,    # média mínima do melhor jogo
    max_tentativas: int = 10,       # máximo de pacotes gerados
    n_simulacoes: int = 1000,       # simulações por candidato
    status_cb: Callable | None = None,
) -> tuple[list, dict | None, dict | None, dict]:
    """
    Gera até max_tentativas pacotes e retorna o melhor.

    Aceita imediatamente se o pacote atingir limiar_11 E limiar_media.
    Caso contrário, continua gerando e ao final retorna o melhor encontrado.

    Returns:
        (jogos, analise, pesos, relatorio) — `analise`/`pesos` são os do
        pacote vencedor (2º/3º item de `fn_gerar`, quando presentes),
        necessários para exibir o pacote na aba "Jogos Gerados"
        (`avaliar_jogos` exige análise/pesos, não só a lista de jogos).
        `relatorio` contém métricas e histórico das tentativas.
    """
    def log(msg: str) -> None:
        if status_cb:
            status_cb(msg)

    log(f"🔄 Otimizador V22 — até {max_tentativas} tentativas")
    log(f"   Limiar 11+: {limiar_11}% | Limiar média: {limiar_media}")
    log(f"   Simulações por candidato: {n_simulacoes}")
    log("-" * 60)

    melhor_jogos = None
    melhor_analise = None
    melhor_pesos = None
    melhor_score = -1.0
    melhor_metricas = {}
    historico = []

    for tentativa in range(1, max_tentativas + 1):
        # Gerar pacote candidato
        analise = None
        pesos = None
        try:
            resultado = fn_gerar(concursos)
            if isinstance(resultado, tuple):
                jogos = resultado[0]
                if len(resultado) > 1:
                    analise = resultado[1]
                if len(resultado) > 2:
                    pesos = resultado[2]
            else:
                jogos = resultado
        except Exception as e:
            log(f"  Tentativa {tentativa}: ❌ erro na geração — {e}")
            continue

        if not jogos:
            continue

        # Simular
        metricas = _simular_pacote(jogos, n_simulacoes)
        pct_11  = metricas["pct_11_mais"]
        media   = metricas["media_melhor"]
        pct_12  = metricas["pct_12_mais"]
        pct_13  = metricas["pct_13_mais"]

        # Score composto para comparar candidatos.
        # 11+ já fica perto do teto no aleatório (~85-98% com 20-30 jogos
        # por pacote, só por volume) — pesar forte nele mal diferencia um
        # candidato do outro. 12+/13+ são mais raros e por isso separam
        # melhor os candidatos; ganharam mais peso aqui (13+ não entrava
        # no score antes). Compensado por n_simulacoes maior (500→1000),
        # já que eventos raros têm mais ruído por rodada de simulação.
        score = pct_11 * 0.2 + media * 3.5 + pct_12 * 0.8 + pct_13 * 1.5

        log(
            f"  Tentativa {tentativa}/{max_tentativas} | "
            f"11+={pct_11}% | 12+={pct_12}% | 13+={pct_13}% | "
            f"média={media} | score={score:.2f}"
        )

        historico.append({
            "tentativa": tentativa,
            "score":     round(score, 2),
            **metricas,
        })

        # Atualiza melhor
        if score > melhor_score:
            melhor_score  = score
            melhor_jogos  = jogos
            melhor_analise = analise
            melhor_pesos = pesos
            melhor_metricas = metricas

        # Aceita imediatamente se atingiu os dois limiares
        if pct_11 >= limiar_11 and media >= limiar_media:
            log(f"  ✅ Limiar atingido na tentativa {tentativa}!")
            break
    else:
        log(f"  ⚠️ Limiar não atingido em {max_tentativas} tentativas — usando melhor encontrado")

    log("-" * 60)
    log(f"🏆 Pacote selecionado | 11+={melhor_metricas.get('pct_11_mais')}% | "
        f"12+={melhor_metricas.get('pct_12_mais')}% | 13+={melhor_metricas.get('pct_13_mais')}% | "
        f"média={melhor_metricas.get('media_melhor')}")

    relatorio = {
        "tentativas_realizadas": len(historico),
        "limiar_11":    limiar_11,
        "limiar_media": limiar_media,
        "melhor_score": round(melhor_score, 2),
        "metricas":     melhor_metricas,
        "historico":    historico,
        "limiar_atingido": melhor_metricas.get("pct_11_mais", 0) >= limiar_11,
    }

    return melhor_jogos or [], melhor_analise, melhor_pesos, relatorio
