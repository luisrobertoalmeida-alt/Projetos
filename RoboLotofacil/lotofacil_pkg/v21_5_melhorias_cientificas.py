"""
lotofacil_pkg/v21_5_melhorias_cientificas.py
---------------------------------------------
V21.5 — Melhorias Científicas

Três aprimoramentos baseados na análise dos experimentos de calibração,
walk-forward e laboratório histórico:

  1. teste_significancia_calibracao()
     Teste binomial exato sobre as vitórias robô vs aleatório.
     Indica se a vantagem observada é estatisticamente significativa
     ou pode ser explicada por acaso (p-value, IC 95%).

  2. score_robustez_walkforward_v2()
     Substitui a referência fixa (9.0 = média de UM jogo aleatório)
     pela referência correta para o modo "melhor de N jogos".
     Usa melhor_por_janela em vez de media_por_janela, alinhando
     o score de robustez ao que o robô realmente entrega na prática.

  3. mapear_vale_gp()
     Varre o espaço G×P em passos finos entre os perfis conhecidos
     para identificar a curva real de retorno e detectar se o "vale"
     observado entre G80 e G300 é estrutural ou variância estatística.

Todas as funções são puras (sem I/O, sem estado global).
I/O fica em salvar_analise_melhorias().
"""

from __future__ import annotations

import math
import random
from statistics import mean, stdev
from typing import Any, Callable


# ─── helpers internos ────────────────────────────────────────────────────────

def _clip(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _acertos(jogo: list[int], sorteio: list[int]) -> int:
    return len(set(jogo) & set(sorteio))


def _beta_cdf_approx(k: int, n: int, p: float) -> float:
    """
    Aproximação normal para a CDF binomial (válida para n >= 20).
    Retorna P(X <= k) onde X ~ Binomial(n, p).
    """
    if n == 0:
        return 1.0
    mu = n * p
    sigma = math.sqrt(n * p * (1 - p))
    if sigma == 0:
        return 1.0 if k >= mu else 0.0
    # correção de continuidade
    z = (k + 0.5 - mu) / sigma
    # aproximação de Abramowitz & Stegun para erfc
    t = 1.0 / (1.0 + 0.2316419 * abs(z))
    poly = t * (0.319381530
                + t * (-0.356563782
                       + t * (1.781477937
                              + t * (-1.821255978
                                     + t * 1.330274429))))
    phi = math.exp(-0.5 * z * z) / math.sqrt(2 * math.pi)
    cdf_pos = 1.0 - phi * poly
    return cdf_pos if z >= 0 else 1.0 - cdf_pos


# ─── 1. TESTE DE SIGNIFICÂNCIA BINOMIAL ──────────────────────────────────────

def teste_significancia_calibracao(
    vitorias_robo: int,
    vitorias_aleatorio: int,
    empates: int = 0,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """
    Teste binomial exato (aproximação normal) para avaliar se a vantagem
    do robô sobre o aleatório é estatisticamente significativa.

    Hipótese nula (H0): robô e aleatório têm probabilidade igual de vencer (p=0.5).
    Hipótese alternativa (H1): robô vence mais que o aleatório (unilateral).

    Args:
        vitorias_robo:      número de passos em que o robô teve score maior.
        vitorias_aleatorio: número de passos em que o aleatório teve score maior.
        empates:            passos com vantagem zero (descartados do teste).
        alpha:              nível de significância (padrão 5%).

    Returns:
        Dict com:
          - n_efetivo:        total de comparações não-empatadas
          - vitorias_robo:    contagem original
          - vitorias_aleatorio: contagem original
          - proporcao_robo:   vitorias_robo / n_efetivo
          - p_value:          probabilidade de observar esse resultado por acaso (H0 verdadeira)
          - significativo:    True se p_value < alpha
          - alpha:            nível usado
          - n_minimo_95:      quantas vitórias adicionais seriam necessárias para p<0.05
          - interpretacao:    string descritiva em português
          - ic_95_inferior:   limite inferior do IC 95% da proporção real
          - ic_95_superior:   limite superior do IC 95% da proporção real
    """
    n = vitorias_robo + vitorias_aleatorio  # empates descartados
    if n == 0:
        return {
            "n_efetivo": 0,
            "vitorias_robo": vitorias_robo,
            "vitorias_aleatorio": vitorias_aleatorio,
            "proporcao_robo": 0.0,
            "p_value": 1.0,
            "significativo": False,
            "alpha": alpha,
            "n_minimo_95": None,
            "interpretacao": "Dados insuficientes para teste.",
            "ic_95_inferior": 0.0,
            "ic_95_superior": 0.0,
        }

    prop = vitorias_robo / n

    # p-value unilateral: P(X >= vitorias_robo | H0: p=0.5)
    # = 1 - P(X <= vitorias_robo - 1)
    p_value = 1.0 - _beta_cdf_approx(vitorias_robo - 1, n, 0.5)
    p_value = round(max(0.0, min(1.0, p_value)), 6)

    significativo = p_value < alpha

    # Intervalo de confiança de Wilson (95%)
    z95 = 1.96
    centro = (vitorias_robo + z95 ** 2 / 2) / (n + z95 ** 2)
    margem = (z95 * math.sqrt(prop * (1 - prop) / n + z95 ** 2 / (4 * n ** 2))) / (1 + z95 ** 2 / n)
    ic_inf = round(_clip(centro - margem), 4)
    ic_sup = round(_clip(centro + margem), 4)

    # Quantas vitórias adicionais para atingir p < 0.05 com o mesmo n?
    n_minimo_95 = None
    for k in range(vitorias_robo, n + 1):
        pv = 1.0 - _beta_cdf_approx(k - 1, n, 0.5)
        if pv < 0.05:
            n_minimo_95 = k
            break

    # Quantos passos adicionais (mantendo proporção) para ser significativo?
    passos_extras = None
    if not significativo:
        for extra in range(1, 5001):
            n_proj = n + extra
            v_proj = round(prop * n_proj)
            pv_proj = 1.0 - _beta_cdf_approx(v_proj - 1, n_proj, 0.5)
            if pv_proj < 0.05:
                passos_extras = extra
                break

    # Interpretação
    if significativo:
        interpretacao = (
            f"✅ SIGNIFICATIVO (p={p_value:.4f} < {alpha}). "
            f"Com {n} comparações e {vitorias_robo} vitórias ({prop:.1%}), "
            f"a vantagem do robô é improvável de ser acaso. "
            f"IC 95%: [{ic_inf:.1%}, {ic_sup:.1%}]."
        )
    else:
        extra_str = (
            f" Para significância, seriam necessários ~{passos_extras} passos adicionais "
            f"mantendo a proporção atual."
            if passos_extras else ""
        )
        interpretacao = (
            f"⚠️ NÃO SIGNIFICATIVO (p={p_value:.4f} >= {alpha}). "
            f"Com {n} comparações e {vitorias_robo} vitórias ({prop:.1%}), "
            f"a vantagem pode ser atribuída ao acaso.{extra_str} "
            f"IC 95%: [{ic_inf:.1%}, {ic_sup:.1%}]."
        )

    return {
        "n_efetivo": n,
        "vitorias_robo": vitorias_robo,
        "vitorias_aleatorio": vitorias_aleatorio,
        "empates": empates,
        "proporcao_robo": round(prop, 4),
        "p_value": p_value,
        "significativo": significativo,
        "alpha": alpha,
        "n_minimo_95": n_minimo_95,
        "passos_extras_para_significancia": passos_extras,
        "interpretacao": interpretacao,
        "ic_95_inferior": ic_inf,
        "ic_95_superior": ic_sup,
    }


# ─── 2. WALK-FORWARD COM MÉTRICA CORRIGIDA ───────────────────────────────────

def score_robustez_walkforward_v2(
    melhores_por_janela: list[float],
    medias_por_janela: list[float],
    referencia_melhor_aleatorio: float = 10.8,
    referencia_media_aleatoria: float = 9.0,
) -> dict[str, Any]:
    """
    Score de robustez V2 — usa o melhor jogo do pacote por janela como
    métrica principal, alinhando o score ao que o robô entrega na prática.

    O score V1 original usa media_por_janela (~8.99) contra referência 9.0,
    zerando o componente de ganho mesmo quando o robô entrega 11.26 de
    melhor por pacote. Esta versão corrige isso.

    Referências calibradas empiricamente para 20 jogos:
      - referencia_melhor_aleatorio: média do melhor de 20 jogos aleatórios
        na Lotofácil ≈ 10.8 (calculável via simulação)
      - referencia_media_aleatoria: média de UM jogo aleatório ≈ 9.0

    Args:
        melhores_por_janela:        melhor acerto do pacote em cada janela WF.
        medias_por_janela:          média geral de acertos em cada janela WF.
        referencia_melhor_aleatorio: média esperada do melhor de N jogos aleatórios.
        referencia_media_aleatoria:  média esperada de um jogo aleatório.

    Returns:
        Dict com score_v2, componentes, interpretação e comparação com V1.
    """
    if not melhores_por_janela:
        return {"score_v2": 0.0, "erro": "Sem dados."}

    media_melhor = mean(melhores_por_janela)
    desvio_melhor = stdev(melhores_por_janela) if len(melhores_por_janela) >= 2 else 0.0
    media_geral = mean(medias_por_janela) if medias_por_janela else 0.0

    # Componente ganho: usando melhor do pacote (escala 10.8–15)
    escala_melhor = 15.0 - referencia_melhor_aleatorio
    ganho_melhor = _clip((media_melhor - referencia_melhor_aleatorio) / escala_melhor)

    # Componente ganho legado: usando média geral (para comparação)
    escala_media = 15.0 - referencia_media_aleatoria
    ganho_legado = _clip((media_geral - referencia_media_aleatoria) / escala_media)

    # Componente consistência: desvio do melhor (desvio de 1.5 = penalidade total)
    consistencia = _clip(1.0 - desvio_melhor / 1.5)

    # Score V2 (mesmos pesos do V1: 60% ganho + 40% consistência)
    score_v2 = round(ganho_melhor * 0.6 + consistencia * 0.4, 6)

    # Score V1 para comparação
    score_v1 = round(ganho_legado * 0.6 + consistencia * 0.4, 6)

    # Veredito V2
    if score_v2 >= 0.6:
        veredito = "ROBUSTO"
    elif score_v2 >= 0.35:
        veredito = "ACEITAVEL"
    else:
        veredito = "INSTAVEL"

    return {
        "score_v2": score_v2,
        "score_v1_legado": score_v1,
        "delta_score": round(score_v2 - score_v1, 6),
        "media_melhor_por_janela": round(media_melhor, 4),
        "desvio_melhor_por_janela": round(desvio_melhor, 4),
        "media_geral_por_janela": round(media_geral, 4),
        "componente_ganho_v2": round(ganho_melhor, 6),
        "componente_ganho_v1": round(ganho_legado, 6),
        "componente_consistencia": round(consistencia, 6),
        "referencia_melhor_aleatorio": referencia_melhor_aleatorio,
        "referencia_media_aleatoria": referencia_media_aleatoria,
        "veredito_v2": veredito,
        "interpretacao": (
            f"Score V2={score_v2:.4f} ({veredito}) vs V1={score_v1:.4f}. "
            f"Média do melhor/janela={media_melhor:.2f} "
            f"(ref. aleatório={referencia_melhor_aleatorio}). "
            f"Ganho V2={ganho_melhor:.4f} vs Ganho V1={ganho_legado:.4f}."
        ),
    }


def estimar_referencia_melhor_aleatorio(
    qtd_jogos: int = 20,
    n_simulacoes: int = 10_000,
    seed: int | None = 42,
) -> float:
    """
    Estima empiricamente a média do melhor jogo de um pacote aleatório
    de `qtd_jogos` jogos na Lotofácil.

    Usado para calibrar `referencia_melhor_aleatorio` no score V2.

    Args:
        qtd_jogos:    tamanho do pacote.
        n_simulacoes: número de sorteios simulados.
        seed:         seed para reprodutibilidade.

    Returns:
        Média estimada do melhor acerto em pacotes aleatórios.
    """
    numeros = list(range(1, 26))
    rng = random.Random(seed)

    melhores = []
    for _ in range(n_simulacoes):
        sorteio = rng.sample(numeros, 15)
        pacote = [rng.sample(numeros, 15) for _ in range(qtd_jogos)]
        melhor = max(len(set(j) & set(sorteio)) for j in pacote)
        melhores.append(melhor)

    return round(mean(melhores), 4)


# ─── 3. MAPEAMENTO DO VALE G×P ───────────────────────────────────────────────

def mapear_vale_gp(
    concursos: list[list[int]],
    fn_gerar: Callable,
    janela: int = 150,
    passos: int = 30,
    qtd_jogos: int = 20,
    pontos_g: list[int] | None = None,
    margem_equivalencia: float = 0.3,
    status_cb: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """
    Mapeia o espaço G×P para identificar se o 'vale' observado entre G
    baixo/alto e G intermediário é estrutural ou variância estatística.

    Roda cada configuração de G/P em `passos` backtest steps (mesmos
    sorteios reais para todas as configurações — walk-forward sem
    vazamento) e testa estatisticamente os extremos contra cada
    intermediário com estatística PAREADA (Cohen's d pareado, teste de
    permutação sign-flip, bootstrap pareado, TOST) — as mesmas funções
    de `v20_6_bootstrap.py` usadas em `reanalise_pareada.py` para validar
    a decisão de configuração de produção (ver
    VALIDACAO_MAPA_GP_2026-07-14.md).

    `vale_confirmado` só é True se pelo menos um intermediário mostrar
    uma diferença estatisticamente significativa (p<0.05, sign-flip),
    não-equivalente ao extremo de referência dentro de `margem_equivalencia`
    (TOST) e com tamanho de efeito pareado de pelo menos "pequeno"
    (|d_z|>=0.2). Configurações que não atingem esse padrão, mas também
    não passam no TOST, ficam marcadas como "INCONCLUSIVO" — não force
    uma conclusão binária quando a amostra não tem poder suficiente para
    nenhuma das duas alternativas.

    Args:
        concursos:  histórico completo de concursos.
        fn_gerar:   função(hist, ger, pop, qtd) -> list[list[int]]
                    que gera jogos com os parâmetros dados.
        janela:     tamanho da janela de histórico para cada passo.
        passos:     número de concursos de teste por configuração.
        qtd_jogos:  jogos por pacote.
        pontos_g:   lista de valores de G a testar. Padrão: grade fina
                    entre 80 e 300. P é calculado proporcionalmente.
        margem_equivalencia: margem do TOST (mesma unidade de "melhor
                    jogo do pacote", ex.: pontos de acerto). Deve ser
                    definida a priori — não ajuste depois de ver o
                    resultado. Padrão 0.3, mesma usada em
                    reanalise_pareada.py.
        status_cb:  callback de progresso (opcional).

    Returns:
        Dict com:
          - resultados: lista de dicts por configuração G/P (inclui o
            "score" heurístico de triagem, mantido só para ranking rápido)
          - melhor_config: configuração com maior score heurístico
          - referencia_extremo: qual extremo (G mínimo ou máximo) foi
            usado como referência nas comparações pareadas
          - comparacoes_pareadas: lista de comparações estatísticas
            (referência vs. cada outra configuração), cada uma com
            cohen_d_pareado, p_value, tost_equivalente, ic_90 e veredito
            em {"POSSIVEL_VALE", "EQUIVALENTE", "INCONCLUSIVO"}
          - vale_confirmado: bool — True apenas se alguma comparação
            tiver veredito "POSSIVEL_VALE" (teste estatístico real, não
            heurística)
          - analise: texto descritivo
    """
    from .v20_6_bootstrap import cohen_d_pareado, teste_significancia_pareado, tost_equivalencia

    numeros = list(range(1, 26))

    if pontos_g is None:
        # Grade: G=80,100,120,140,160,200,250 com P proporcional (ratio ~0.77),
        # mais G=16 no lugar do antigo extremo G=300/P=230 — G=16/P=40 é a
        # configuração real e fixa do sistema desde 2026-07-18, então o Mapa
        # passou a comparar diretamente a config de produção contra a grade,
        # em vez de um extremo teórico que ninguém roda de verdade (a pedido
        # do usuário, ver 2026-07-27 no ARQUITETURA.md).
        pontos_g = [80, 100, 120, 140, 160, 200, 250, 16]

    total = len(concursos)
    inicio = max(janela, total - passos)

    resultados = []
    linhas_por_g = {}  # g -> {concurso_idx: melhor_robo}, para as comparacoes pareadas

    for idx_g, g in enumerate(pontos_g):
        if g == 16:
            # Configuração real fixa do sistema (G=16/P=40) — não a
            # proporcional (round(16*0.767)=12, valor que o robô nunca usa).
            p = 40
            nome = "G=16/P=40 (configuração real do sistema)"
        else:
            # P proporcional ao G com o mesmo ratio de G300/P230 ≈ 0.767
            p = max(20, round(g * 0.767))
            nome = f"G={g}/P={p}"

        if status_cb:
            status_cb(f"[{idx_g+1}/{len(pontos_g)}] Mapeando {nome}...")

        linhas_cfg = []
        por_concurso = {}
        for i in range(inicio, total):
            base = concursos[:i]
            real = sorted(concursos[i])

            try:
                jogos_robo = fn_gerar(base, g, p, qtd_jogos)
            except Exception:
                continue

            jogos_ale = [sorted(random.sample(numeros, 15)) for _ in range(qtd_jogos)]

            acertos_robo = [_acertos(j, real) for j in jogos_robo]
            acertos_ale = [_acertos(j, real) for j in jogos_ale]

            melhor_robo = max(acertos_robo) if acertos_robo else 0
            melhor_ale = max(acertos_ale) if acertos_ale else 0
            qtd_12_robo = sum(1 for a in acertos_robo if a >= 12)
            qtd_12_ale = sum(1 for a in acertos_ale if a >= 12)

            linhas_cfg.append({
                "melhor_robo": melhor_robo,
                "melhor_ale": melhor_ale,
                "qtd_12_robo": qtd_12_robo,
                "qtd_12_ale": qtd_12_ale,
                "vantagem": melhor_robo - melhor_ale,
            })
            por_concurso[i] = melhor_robo

        if not linhas_cfg:
            continue

        linhas_por_g[g] = por_concurso

        n = len(linhas_cfg)
        media_melhor = round(mean(r["melhor_robo"] for r in linhas_cfg), 4)
        pct_12 = round(100 * sum(1 for r in linhas_cfg if r["melhor_robo"] >= 12) / n, 2)
        pct_13 = round(100 * sum(1 for r in linhas_cfg if r["melhor_robo"] >= 13) / n, 2)
        vit_robo = sum(1 for r in linhas_cfg if r["vantagem"] > 0)
        vit_ale = sum(1 for r in linhas_cfg if r["vantagem"] < 0)
        vantagem_pct = round(100 * vit_robo / n, 2)

        resultados.append({
            "nome": nome,
            "g": g,
            "p": p,
            "passos_executados": n,
            "media_melhor": media_melhor,
            "pct_12_mais": pct_12,
            "pct_13_mais": pct_13,
            "vit_robo": vit_robo,
            "vit_ale": vit_ale,
            "vantagem_pct": vantagem_pct,
            # score composto heurístico — só para ranking/triagem rápida,
            # não usado para decidir vale_confirmado (ver comparacoes_pareadas)
            "score": round(
                media_melhor * 1.0
                + pct_12 * 0.10
                + pct_13 * 0.25
                + vantagem_pct * 0.05,
                4
            ),
        })

        if status_cb:
            status_cb(
                f"  {nome}: média_melhor={media_melhor} | 12+={pct_12}% "
                f"| vantagem={vantagem_pct}%"
            )

    if not resultados:
        return {"resultados": [], "erro": "Nenhuma configuração executada."}

    # Ordenar por score heurístico (só para triagem/ranking rápido)
    resultados_ord = sorted(resultados, key=lambda r: r["score"], reverse=True)
    melhor = resultados_ord[0]

    # ── Comparações estatísticas PAREADAS: extremo de referência vs. demais ──
    g_vals = sorted(linhas_por_g.keys())
    comparacoes_pareadas = []
    referencia_extremo = None

    if len(g_vals) >= 2:
        g_min, g_max = g_vals[0], g_vals[-1]
        media_por_g = {r["g"]: r["media_melhor"] for r in resultados}
        # referência = o extremo com maior média observada (o "candidato a vencer")
        referencia_extremo = g_max if media_por_g[g_max] >= media_por_g[g_min] else g_min

        ref_por_concurso = linhas_por_g[referencia_extremo]
        for g in g_vals:
            if g == referencia_extremo:
                continue
            outro_por_concurso = linhas_por_g[g]
            indices_comuns = sorted(set(ref_por_concurso) & set(outro_por_concurso))
            if len(indices_comuns) < 10:
                comparacoes_pareadas.append({
                    "g": g, "referencia": referencia_extremo, "n": len(indices_comuns),
                    "veredito": "INCONCLUSIVO",
                    "motivo": "menos de 10 passos em comum entre as duas configurações",
                })
                continue

            ref_dados = [{"acertos": ref_por_concurso[i]} for i in indices_comuns]
            outro_dados = [{"acertos": outro_por_concurso[i]} for i in indices_comuns]

            cohen = cohen_d_pareado(ref_dados, outro_dados)
            sig = teste_significancia_pareado(ref_dados, outro_dados, n_reamostras=3000)
            tost = tost_equivalencia(ref_dados, outro_dados, margem=margem_equivalencia, n_reamostras=3000)

            if tost["equivalente"]:
                veredito = "EQUIVALENTE"
            elif sig["rejeita_h0"] and abs(cohen["cohen_d_pareado"]) >= 0.2 and sig["delta_obs"] > 0:
                veredito = "POSSIVEL_VALE"
            else:
                veredito = "INCONCLUSIVO"

            comparacoes_pareadas.append({
                "g": g,
                "referencia": referencia_extremo,
                "n": len(indices_comuns),
                "cohen_d_pareado": cohen["cohen_d_pareado"],
                "magnitude": cohen["magnitude"],
                "p_value": sig["p_value"],
                "delta_obs": sig["delta_obs"],
                "tost_equivalente": tost["equivalente"],
                "ic_90": tost["ic_90"],
                "veredito": veredito,
            })

    vale_confirmado = any(c.get("veredito") == "POSSIVEL_VALE" for c in comparacoes_pareadas)
    todas_equivalentes = bool(comparacoes_pareadas) and all(
        c.get("veredito") == "EQUIVALENTE" for c in comparacoes_pareadas
    )

    # Análise textual
    if vale_confirmado:
        candidatos = [c["g"] for c in comparacoes_pareadas if c["veredito"] == "POSSIVEL_VALE"]
        analise = (
            f"Vale G×P POSSÍVEL: G={referencia_extremo} supera estatisticamente "
            f"(p<0.05, TOST rejeita equivalência, efeito >= pequeno) as configurações "
            f"G={candidatos} num teste pareado (mesmos {passos} sorteios reais em todas). "
            f"Recomenda-se validar essa comparação específica com mais passos antes de mudar "
            f"a configuração de produção — ver reanalise_pareada.py."
        )
    elif todas_equivalentes:
        analise = (
            f"Vale G×P NÃO CONFIRMADO: TOST (margem=±{margem_equivalencia}) confirma "
            f"equivalência prática entre G={referencia_extremo} e todas as demais "
            f"configurações testadas — não apenas ausência de significância. "
            f"Melhor configuração por score heurístico: {melhor['nome']}, mas qualquer "
            f"configuração testada tem desempenho estatisticamente equivalente."
        )
    else:
        analise = (
            f"Vale G×P INCONCLUSIVO com {passos} passos: nem significância nem "
            f"equivalência (TOST) foram estabelecidas para todas as comparações — "
            f"amostra insuficiente para concluir nessa escala. Aumentar `passos` "
            f"(ideal n>=300, ver VALIDACAO_MAPA_GP_2026-07-14.md) antes de decidir. "
            f"Melhor configuração por score heurístico nesta triagem: {melhor['nome']} "
            f"(score={melhor['score']:.3f})."
        )

    return {
        "resultados": resultados_ord,
        "melhor_config": melhor,
        "referencia_extremo": referencia_extremo,
        "comparacoes_pareadas": comparacoes_pareadas,
        "vale_confirmado": vale_confirmado,
        "todas_equivalentes": todas_equivalentes,
        "analise": analise,
        "parametros": {
            "janela": janela,
            "passos": passos,
            "qtd_jogos": qtd_jogos,
            "pontos_g_testados": pontos_g,
            "margem_equivalencia": margem_equivalencia,
        },
    }


# ─── RELATÓRIO CONSOLIDADO ────────────────────────────────────────────────────

def relatorio_melhorias_cientificas(
    vitorias_robo: int,
    vitorias_aleatorio: int,
    empates: int,
    melhores_por_janela: list[float],
    medias_por_janela: list[float],
    qtd_jogos: int = 20,
) -> dict[str, Any]:
    """
    Gera o relatório consolidado das três melhorias científicas a partir
    dos dados já coletados (sem re-executar o robô).

    Args:
        vitorias_robo:        vitórias por score na calibração.
        vitorias_aleatorio:   vitórias do aleatório na calibração.
        empates:              empates na calibração.
        melhores_por_janela:  melhor acerto do pacote em cada janela WF.
        medias_por_janela:    média geral de acertos em cada janela WF.
        qtd_jogos:            jogos por pacote (para estimar referência do aleatório).

    Returns:
        Dict com seções: significancia, walkforward_v2, resumo_geral.
    """
    # 1. Significância
    sig = teste_significancia_calibracao(vitorias_robo, vitorias_aleatorio, empates)

    # 2. Walk-forward V2
    ref_melhor = estimar_referencia_melhor_aleatorio(qtd_jogos=qtd_jogos, n_simulacoes=5_000)
    wf_v2 = score_robustez_walkforward_v2(
        melhores_por_janela,
        medias_por_janela,
        referencia_melhor_aleatorio=ref_melhor,
    )

    # 3. Resumo geral
    pontos_fortes = []
    pontos_atencao = []

    if sig["significativo"]:
        pontos_fortes.append(f"Vantagem estatisticamente significativa (p={sig['p_value']:.4f})")
    else:
        pontos_atencao.append(
            f"Vantagem ainda não significativa (p={sig['p_value']:.4f}). "
            f"Necessário ~{sig.get('passos_extras_para_significancia', '?')} passos adicionais."
        )

    if wf_v2["score_v2"] >= 0.6:
        pontos_fortes.append(f"Walk-forward V2 ROBUSTO (score={wf_v2['score_v2']:.4f})")
    elif wf_v2["score_v2"] >= 0.35:
        pontos_fortes.append(f"Walk-forward V2 ACEITÁVEL (score={wf_v2['score_v2']:.4f})")
    else:
        pontos_atencao.append(f"Walk-forward V2 INSTÁVEL (score={wf_v2['score_v2']:.4f})")

    delta = wf_v2["delta_score"]
    if delta > 0:
        pontos_fortes.append(
            f"Score V2 corrigido {delta:+.4f} vs V1 — "
            f"o V1 subestimava o desempenho real do robô."
        )

    return {
        "significancia": sig,
        "walkforward_v2": wf_v2,
        "referencia_melhor_estimada": ref_melhor,
        "resumo_geral": {
            "pontos_fortes": pontos_fortes,
            "pontos_atencao": pontos_atencao,
        },
    }
