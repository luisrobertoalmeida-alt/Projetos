"""
lotofacil_pkg/analise.py
-------------------------
Análise histórica, Motor Estratégico Inteligente e Ensemble Multi-IA.

Sete modelos independentes combinados por pesos dinâmicos:
  1. Estatístico   — frequência / recência / atraso
  2. Markov        — transições entre concursos consecutivos
  3. Bayesiano     — suavização beta-binomial
  4. Tendência     — comparação metade antiga vs. recente
  5. Neural leve   — sigmoide sobre sinais normalizados (sem dependências externas)
  6. Cobertura     — equilíbrio de linhas e colunas na grade 5×5
  7. Pares/trios   — combinações estatisticamente acima do esperado
"""
import math
from collections import Counter
from itertools import combinations
from statistics import mean

from .config import NUMEROS
from .utils import (
    contar_pares, soma_jogo, intersecao, limitar,
    normalizar_scores,
)
from .v21_0_meta_aprendizado import MetaAprendizadoModelos
from .v21_0_auto_poda import decidir_poda_adaptativa
from .v18_1b_ia_adaptativa import carregar_pesos_modelos

# V21.5-FULL: ELO competitivo + Poda 4-estados
try:
    from .v21_5_meta_competitivo import fatores_elo_todos, carregar_elo
    from .v21_5_auto_poda_full import fatores_poda_todos
    _V21_5_FULL_OK = True
except Exception:
    _V21_5_FULL_OK = False

from .aprendizado import (
    calcular_bonus_aprendizado, aplicar_aprendizado_nos_modelos,
    calcular_memoria_ranking, aplicar_memoria_de_ranking_aos_pesos,
    carregar_memoria_aprendizado,
)


def limitar(valor: float, minimo: float, maximo: float) -> float:
    """Clipa `valor` no intervalo [minimo, maximo]."""
    return max(minimo, min(maximo, valor))


def calcular_motor_estrategico(analise: dict, qtd_jogos: int = 20, janela: int = 120) -> dict:
    """
    Motor Estratégico Inteligente.
    Ele não tenta prever o sorteio; ele decide como o robô deve se comportar
    conforme estabilidade, volatilidade, concentração de dezenas e repetição recente.
    """
    freq = analise["freq"]
    atrasos = analise["atrasos"]
    hist = analise["hist_usado"]

    valores_freq = [freq.get(n, 0) for n in NUMEROS]
    media_freq = mean(valores_freq) if valores_freq else 1.0
    desvio_freq = math.sqrt(mean([(x - media_freq) ** 2 for x in valores_freq])) if valores_freq else 0.0
    concentracao = limitar(desvio_freq / max(1.0, media_freq), 0.0, 1.0)

    volatilidade_soma = limitar(analise.get("desvio_soma", 0.0) / 22.0, 0.0, 1.0)
    volatilidade_inter = limitar(analise.get("desvio_intersecao", 0.0) / 2.6, 0.0, 1.0)
    repeticao_media = limitar((analise.get("intersecao_media", 9.0) - 7.0) / 5.0, 0.0, 1.0)

    atrasos_vals = list(atrasos.values()) or [0]
    atraso_medio = mean(atrasos_vals)
    atraso_max = max(atrasos_vals) if atrasos_vals else 1
    pressao_atrasados = limitar((atraso_max - atraso_medio) / max(1.0, len(hist) * 0.35), 0.0, 1.0)

    estabilidade = limitar(1.0 - (0.55 * volatilidade_soma + 0.45 * volatilidade_inter), 0.0, 1.0)
    indice_confianca = limitar(0.45 * estabilidade + 0.30 * concentracao + 0.25 * repeticao_media, 0.0, 1.0)

    if indice_confianca >= 0.68:
        modo = "agressivo"
    elif indice_confianca <= 0.38:
        modo = "conservador"
    else:
        modo = "equilibrado"

    peso_freq = limitar(0.38 + 0.20 * concentracao + 0.08 * indice_confianca, 0.34, 0.62)
    peso_recente = limitar(0.22 + 0.18 * repeticao_media, 0.18, 0.42)
    peso_atraso = limitar(1.0 - peso_freq - peso_recente, 0.16, 0.38)
    soma_pesos = peso_freq + peso_recente + peso_atraso
    peso_freq, peso_recente, peso_atraso = peso_freq / soma_pesos, peso_recente / soma_pesos, peso_atraso / soma_pesos

    diversidade = limitar(0.62 + 0.28 * (1.0 - indice_confianca) + 0.10 * (qtd_jogos / 50.0), 0.58, 0.92)
    taxa_mutacao = limitar(0.24 + 0.30 * (1.0 - indice_confianca) + 0.10 * pressao_atrasados, 0.22, 0.62)
    elite_fracao = limitar(0.30 - 0.12 * (1.0 - indice_confianca), 0.14, 0.32)
    limite_intersecao = 11 if diversidade >= 0.78 else 12

    ciclo = analise.get("ciclo") or {}
    ciclo_principal = ciclo.get("ciclo_principal", "estavel")
    if ciclo_principal == "alta_repeticao":
        peso_recente *= 1.06
        peso_freq *= 1.02
        diversidade = limitar(diversidade - 0.025, 0.56, 0.92)
    elif ciclo_principal == "alta_dispersao":
        peso_atraso *= 1.05
        diversidade = limitar(diversidade + 0.04, 0.58, 0.94)
        taxa_mutacao = limitar(taxa_mutacao + 0.035, 0.22, 0.66)
        limite_intersecao = min(limite_intersecao, 11)
    elif ciclo_principal == "soma_alta":
        indice_confianca = limitar(indice_confianca - 0.015, 0.0, 1.0)
    elif ciclo_principal == "soma_baixa":
        indice_confianca = limitar(indice_confianca - 0.015, 0.0, 1.0)

    soma_pesos_ciclo = peso_freq + peso_recente + peso_atraso
    peso_freq, peso_recente, peso_atraso = peso_freq / soma_pesos_ciclo, peso_recente / soma_pesos_ciclo, peso_atraso / soma_pesos_ciclo

    return {
        "modo": modo,
        "indice_confianca": round(indice_confianca, 3),
        "estabilidade": round(estabilidade, 3),
        "concentracao": round(concentracao, 3),
        "repeticao_media": round(repeticao_media, 3),
        "pressao_atrasados": round(pressao_atrasados, 3),
        "peso_freq": peso_freq,
        "peso_recente": peso_recente,
        "peso_atraso": peso_atraso,
        "diversidade": round(diversidade, 3),
        "taxa_mutacao": round(taxa_mutacao, 3),
        "elite_fracao": round(elite_fracao, 3),
        "limite_intersecao": limite_intersecao,
        "peso_refinamento_matematico": 0.55,
        "peso_impopularidade": 0.30,  # V21.6: valor esperado por impopularidade (0=desligado)
        "ciclo_principal": ciclo_principal,
        "ciclo_descricao": ciclo.get("descricao", ""),
    }


def calcular_pesos_dinamicos(analise: dict, estrategia: dict | None = None) -> dict:
    freq = analise["freq"]
    recentes = analise["recentes"]
    atrasos = analise["atrasos"]

    max_freq = max(freq.values()) if freq else 1
    max_rec = max(recentes.values()) if recentes else 1
    max_atr = max(atrasos.values()) if atrasos else 1
    pesos = {}
    for n in NUMEROS:
        f = freq.get(n, 0) / max_freq
        r = recentes.get(n, 0) / max_rec if max_rec > 0 else 0
        a = atrasos.get(n, 0) / max_atr if max_atr > 0 else 0
        if estrategia:
            pf = estrategia.get("peso_freq", 0.46)
            pr = estrategia.get("peso_recente", 0.29)
            pa = estrategia.get("peso_atraso", 0.25)
        else:
            pf, pr, pa = 0.46, 0.29, 0.25
        pesos[n] = max(0.03, pf * f + pr * r + pa * a)
    total = sum(pesos.values())
    return {k: v / total for k, v in pesos.items()}




# =========================================================
# ENSEMBLE MULTI-IA ADAPTATIVO
# Sete modelos independentes combinados por pesos dinâmicos.
# Cada modelo recebe um peso proporcional ao histórico de desempenho
# registrado pelo próprio usuário (aprendizado permanente).
# =========================================================
def normalizar_scores(scores, piso: float = 0.001) -> dict:
    """Normaliza {dezena: score} para soma=1 com piso mínimo de segurança."""
    vals = {n: max(piso, float(scores.get(n, 0.0))) for n in NUMEROS}
    total = sum(vals.values()) or 1.0
    inv_total = 1.0 / total
    return {n: vals[n] * inv_total for n in NUMEROS}



def calcular_consenso_modelos(modelos: dict, top_n: int = 15) -> dict:
    """
    Mede concordância entre os modelos do ensemble.
    Uma dezena ganha consenso quando aparece no Top N de vários modelos.
    """
    votos = Counter()
    pontos_rank = Counter()
    total_modelos = max(1, len(modelos or {}))
    detalhes = {}
    for nome, scores in (modelos or {}).items():
        ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top = ranking[:top_n]
        detalhes[nome] = [n for n, _ in top]
        for pos, (n, _) in enumerate(top, start=1):
            votos[n] += 1
            pontos_rank[n] += (top_n - pos + 1) / top_n
    consenso = {}
    for n in NUMEROS:
        taxa_votos = votos[n] / total_modelos
        rank_score = pontos_rank[n] / total_modelos
        consenso[n] = 0.65 * taxa_votos + 0.35 * rank_score
    ranking_consenso = sorted(consenso.items(), key=lambda x: x[1], reverse=True)
    return {
        "score_consenso": consenso,
        "votos": dict(votos),
        "ranking_consenso": ranking_consenso,
        "top_consenso": ranking_consenso[:10],
        "detalhes_por_modelo": detalhes,
        "top_n": top_n,
    }

def calcular_scores_estatistico(analise: dict, estrategia: dict | None = None) -> dict:
    """Modelo 1: estatístico clássico, baseado em frequência, recentes e atraso."""
    return calcular_pesos_dinamicos(analise, estrategia=estrategia)


def calcular_scores_markov(hist: list) -> dict:
    """
    Modelo 2: Markov leve.
    Mede quais dezenas costumam aparecer depois das dezenas presentes no último concurso.
    """
    if len(hist) < 2:
        return normalizar_scores({n: 1.0 for n in NUMEROS})

    ultimo = set(hist[-1])
    transicoes = Counter()
    base = 0
    for i in range(len(hist) - 1):
        atual = set(hist[i])
        prox = hist[i + 1]
        inter = len(atual & ultimo)
        if inter >= 5:
            peso = 1.0 + inter / 15.0
            for n in prox:
                transicoes[n] += peso
            base += 1

    if base == 0:
        return normalizar_scores({n: 1.0 for n in NUMEROS})
    return normalizar_scores({n: transicoes.get(n, 0.0) for n in NUMEROS})


def calcular_scores_bayesiano(analise: dict) -> dict:
    """Modelo 3: Bayesiano simples com suavização beta-binomial."""
    hist = analise["hist_usado"]
    freq = analise["freq"]
    total = max(1, len(hist))
    # Na Lotofácil, cada dezena tem probabilidade base aproximada de 15/25.
    alpha_prior = 6.0
    beta_prior = 4.0
    scores = {}
    for n in NUMEROS:
        sucesso = freq.get(n, 0)
        posterior = (sucesso + alpha_prior) / (total + alpha_prior + beta_prior)
        scores[n] = posterior
    return normalizar_scores(scores)


def calcular_scores_tendencia(analise: dict) -> dict:
    """
    Modelo 4: tendência recente.
    Compara metade recente contra metade anterior da janela.
    """
    hist = analise["hist_usado"]
    if len(hist) < 20:
        return normalizar_scores({n: 1.0 for n in NUMEROS})
    meio = len(hist) // 2
    antiga = hist[:meio]
    recente = hist[meio:]
    f_antiga = Counter(n for jogo in antiga for n in jogo)
    f_recente = Counter(n for jogo in recente for n in jogo)
    scores = {}
    for n in NUMEROS:
        taxa_antiga = f_antiga.get(n, 0) / max(1, len(antiga))
        taxa_recente = f_recente.get(n, 0) / max(1, len(recente))
        tendencia = taxa_recente - taxa_antiga
        scores[n] = 0.60 + tendencia
    return normalizar_scores(scores)


def calcular_scores_neural_leve(analise: dict) -> dict:
    """
    Modelo 5: mini rede neural heurística, sem dependência externa.
    Usa uma função sigmoide sobre sinais normalizados de frequência, recente, atraso e repetição.
    """
    freq = analise["freq"]
    recentes = analise["recentes"]
    atrasos = analise["atrasos"]
    max_freq = max(freq.values()) if freq else 1
    max_rec = max(recentes.values()) if recentes else 1
    max_atr = max(atrasos.values()) if atrasos else 1
    scores = {}
    for n in NUMEROS:
        x1 = freq.get(n, 0) / max_freq
        x2 = recentes.get(n, 0) / max_rec if max_rec else 0
        x3 = atrasos.get(n, 0) / max_atr if max_atr else 0
        x4 = 1.0 if n in analise["hist_usado"][-1] else 0.0
        z = -0.35 + 1.10 * x1 + 0.85 * x2 + 0.55 * x3 + 0.25 * x4
        scores[n] = 1.0 / (1.0 + math.exp(-z))
    return normalizar_scores(scores)


def calcular_scores_pares_trios(analise: dict) -> dict:
    """
    Modelo 7: pares e trios frequentes.
    Identifica dezenas que aparecem juntas com frequência acima do esperado
    pela probabilidade pura — combinações estatisticamente relevantes no histórico.
    """
    hist = analise["hist_usado"]
    n_concursos = len(hist)
    if n_concursos < 20:
        return {n: 1.0 / 25 for n in NUMEROS}

    # Conta frequência de cada par com itertools.combinations.
    # Mantém a mesma lógica, mas reduz código manual e evita custo extra em loops aninhados Python puro.
    freq_pares = Counter()
    freq_dezena = Counter()
    for jogo in hist:
        jogo_ordenado = tuple(sorted(set(jogo)))
        freq_dezena.update(jogo_ordenado)
        freq_pares.update(combinations(jogo_ordenado, 2))

    # Probabilidade esperada de um par por sorteio: C(15,2)/C(25,2) = 105/300 ≈ 0.35
    p_par_esperado = 105.0 / 300.0
    scores = {n: 0.0 for n in NUMEROS}

    participacao_pares = Counter()
    for (a, b), cnt in freq_pares.items():
        # Frequência observada vs esperada
        p_obs = cnt / n_concursos
        excesso = max(0.0, p_obs - p_par_esperado)
        bonus = math.log1p(excesso * 10)  # log suaviza extremos
        scores[a] += bonus
        scores[b] += bonus
        participacao_pares[a] += cnt
        participacao_pares[b] += cnt

    # Adiciona bônus para trios — dezenas que participam de muitos pares acima do esperado.
    # Antes isso varria todos os pares para cada dezena; agora usa contador acumulado.
    for n in NUMEROS:
        pares_do_n = participacao_pares.get(n, 0)
        scores[n] += math.log1p(pares_do_n / max(1, n_concursos) * 2)

    return normalizar_scores(scores)


def calcular_scores_cobertura(analise: dict) -> dict:
    """
    Modelo 6: cobertura estrutural.
    Favorece dezenas que ajudam a equilibrar linhas/colunas e reduzir concentração extrema.
    """
    hist = analise["hist_usado"]
    freq_linhas = Counter()
    freq_colunas = Counter()
    for jogo in hist:
        for n in jogo:
            freq_linhas[(n - 1) // 5] += 1
            freq_colunas[(n - 1) % 5] += 1
    media_linha = mean(freq_linhas.values()) if freq_linhas else 1.0
    media_coluna = mean(freq_colunas.values()) if freq_colunas else 1.0
    scores = {}
    for n in NUMEROS:
        linha = (n - 1) // 5
        coluna = (n - 1) % 5
        equilibrio_linha = 1.0 / (1.0 + abs(freq_linhas.get(linha, 0) - media_linha) / max(1.0, media_linha))
        equilibrio_coluna = 1.0 / (1.0 + abs(freq_colunas.get(coluna, 0) - media_coluna) / max(1.0, media_coluna))
        scores[n] = 0.5 * equilibrio_linha + 0.5 * equilibrio_coluna
    return normalizar_scores(scores)


def pesos_modelos_por_estrategia(estrategia: dict) -> dict:
    """Define quanto cada modelo pesa conforme a decisão do Motor Estratégico."""
    modo = (estrategia or {}).get("modo", "equilibrado")
    confianca = float((estrategia or {}).get("indice_confianca", 0.50))

    if modo == "agressivo":
        pesos = {
            "estatistico":  0.24,
            "markov":       0.20,
            "bayesiano":    0.11,
            "tendencia":    0.17,
            "neural_leve":  0.15,
            "cobertura":    0.05,
            "pares_trios":  0.08,
        }
    elif modo == "conservador":
        pesos = {
            "estatistico":  0.22,
            "markov":       0.09,
            "bayesiano":    0.20,
            "tendencia":    0.09,
            "neural_leve":  0.11,
            "cobertura":    0.19,
            "pares_trios":  0.10,
        }
    else:
        pesos = {
            "estatistico":  0.22,
            "markov":       0.14,
            "bayesiano":    0.15,
            "tendencia":    0.13,
            "neural_leve":  0.13,
            "cobertura":    0.13,
            "pares_trios":  0.10,
        }

    ajuste = limitar(confianca - 0.50, -0.30, 0.30)
    pesos["markov"]      = max(0.04, pesos["markov"]      + 0.10 * ajuste)
    pesos["tendencia"]   = max(0.04, pesos["tendencia"]   + 0.08 * ajuste)
    pesos["cobertura"]   = max(0.04, pesos["cobertura"]   - 0.12 * ajuste)
    pesos["pares_trios"] = max(0.04, pesos["pares_trios"] + 0.04 * ajuste)

    total = sum(pesos.values()) or 1.0
    return {k: v / total for k, v in pesos.items()}


def calcular_ensemble_multi_ia(concursos: list, analise: dict, estrategia: dict | None = None) -> dict:
    """
    Combina sete modelos independentes em um peso final por dezena.
    Modelo 7 (pares_trios) detecta combinações estatisticamente acima do esperado.
    """
    hist = analise["hist_usado"]
    modelos = {
        "estatistico":  calcular_scores_estatistico(analise, estrategia=estrategia),
        "markov":       calcular_scores_markov(hist),
        "bayesiano":    calcular_scores_bayesiano(analise),
        "tendencia":    calcular_scores_tendencia(analise),
        "neural_leve":  calcular_scores_neural_leve(analise),
        "cobertura":    calcular_scores_cobertura(analise),
        "pares_trios":  calcular_scores_pares_trios(analise),
    }
    confianca_modelos = pesos_modelos_por_estrategia(estrategia or {})
    aprendizado = (estrategia or {}).get("aprendizado_permanente") or {}
    confianca_modelos = aplicar_aprendizado_nos_modelos(confianca_modelos, aprendizado)

    try:
        pesos_adaptativos = carregar_pesos_modelos()
        for nome in list(confianca_modelos.keys()):
            confianca_modelos[nome] *= float(pesos_adaptativos.get(nome, 1.0))
        total = sum(confianca_modelos.values()) or 1.0
        confianca_modelos = {k:v/total for k,v in confianca_modelos.items()}
    except Exception:
        pass

    # Modo campeonato científico: permite testar um modelo isolado no backtest
    # sem alterar o funcionamento normal do robô.
    modelo_forcado = (estrategia or {}).get("forcar_modelo")
    if modelo_forcado in modelos:
        confianca_modelos = {nome: (1.0 if nome == modelo_forcado else 0.0) for nome in modelos}


    # ===== V21.1-E Integração Operacional =====
    try:
        meta = MetaAprendizadoModelos()

        for nome in list(confianca_modelos.keys()):

            prob = meta.probabilidade_recuperacao(
                [],
                model_id=nome
            )

            decisao = decidir_poda_adaptativa(
                nome,
                confianca_modelos[nome]
            )

            if decisao.get("decisao") == "PODAR":
                confianca_modelos[nome] = 0.0
                continue

            if prob >= 0.80:
                confianca_modelos[nome] *= 1.15
            elif prob >= 0.65:
                confianca_modelos[nome] *= 1.05
            elif prob < 0.40:
                confianca_modelos[nome] *= 0.85

        total = sum(confianca_modelos.values()) or 1.0

        confianca_modelos = {
            k: v / total
            for k, v in confianca_modelos.items()
        }

    except Exception:
        pass

    # ===== V21.5-FULL: ELO Competitivo + Poda 4-Estados =====
    # peso_final = peso_base * fator_elo * fator_estado
    # Aplicado DEPOIS de todos os ajustes anteriores, como camada final
    # de modulação. Nunca zera um modelo completamente (mínimo 0.05).
    if _V21_5_FULL_OK:
        try:
            elos_atuais = carregar_elo()
            fatores_elo = fatores_elo_todos(elos_atuais)
            fatores_poda = fatores_poda_todos(elos=elos_atuais)

            for nome in list(confianca_modelos.keys()):
                fe = fatores_elo.get(nome, 1.0)
                fp = fatores_poda.get(nome, 1.0)
                # Combina: 60% ELO, 40% poda-4-estados
                fator_combinado = 0.60 * fe + 0.40 * fp
                confianca_modelos[nome] = max(
                    0.05,
                    confianca_modelos[nome] * fator_combinado
                )

            total = sum(confianca_modelos.values()) or 1.0
            confianca_modelos = {k: v / total for k, v in confianca_modelos.items()}
        except Exception:
            pass

    combinado = {n: 0.0 for n in NUMEROS}
    for nome, scores in modelos.items():
        peso_modelo = confianca_modelos.get(nome, 0.0)
        for n in NUMEROS:
            combinado[n] += peso_modelo * scores.get(n, 0.0)

    consenso = calcular_consenso_modelos(modelos, top_n=15)
    score_consenso = normalizar_scores(consenso.get("score_consenso", {}), piso=0.002)
    peso_consenso = 0.10
    if (estrategia or {}).get("modo") == "agressivo":
        peso_consenso = 0.13
    elif (estrategia or {}).get("modo") == "conservador":
        peso_consenso = 0.08
    for n in NUMEROS:
        combinado[n] = (1.0 - peso_consenso) * combinado[n] + peso_consenso * score_consenso.get(n, 0.0)

    memoria_ranking = (aprendizado or {}).get("memoria_ranking") or {}
    pesos_finais = aplicar_memoria_de_ranking_aos_pesos(normalizar_scores(combinado, piso=0.002), memoria_ranking)
    pesos_finais = aplicar_auto_otimizacao(pesos_finais)
    ranking = sorted(pesos_finais.items(), key=lambda x: x[1], reverse=True)
    return {
        "modelos": modelos,
        "confianca_modelos": confianca_modelos,
        "consenso": consenso,
        "peso_consenso": peso_consenso,
        "memoria_ranking": memoria_ranking,
        "pesos_finais": pesos_finais,
        "ranking": ranking,
    }




# =========================================================
# AUTO-OTIMIZADOR DE ESTRATÉGIAS (UPGRADE V10)
# =========================================================
def analisar_padroes_vencedores(memoria: dict | None = None) -> dict:
    """
    Analisa padrões dos jogos que mais acertaram no histórico do próprio robô.
    """
    memoria = memoria or carregar_memoria_aprendizado()
    registros = memoria.get("registros", [])[-300:]

    fortes = [r for r in registros if int(r.get("melhor_acerto", 0)) >= 11]

    if not fortes:
        return {
            "ativo": False,
            "mensagem": "Sem registros suficientes de 11+ pontos."
        }

    pares = []
    somas = []
    modos = []
    repeticoes = []

    for r in fortes:
        pares.append(float(r.get("pares_medios", 7)))
        somas.append(float(r.get("soma_media", 195)))
        modos.append(str(r.get("modo", "equilibrado")))
        repeticoes.append(float(r.get("media_sobreposicao", 9)))

    modo_forte = Counter(modos).most_common(1)[0][0] if modos else "equilibrado"

    return {
        "ativo": True,
        "media_pares": round(mean(pares), 2) if pares else 7.0,
        "media_soma": round(mean(somas), 2) if somas else 195.0,
        "media_repeticao": round(mean(repeticoes), 2) if repeticoes else 9.0,
        "modo_forte": modo_forte,
        "total_registros_fortes": len(fortes),
    }


def aplicar_auto_otimizacao(pesos: dict, memoria: dict | None = None) -> dict:
    """
    Recalibra pesos conforme os padrões vencedores do próprio robô.
    """
    if not pesos:
        return pesos

    memoria = memoria or carregar_memoria_aprendizado()
    padroes = analisar_padroes_vencedores(memoria)

    if not padroes.get("ativo"):
        return pesos

    ajustados = dict(pesos)

    media_soma = padroes.get("media_soma", 195)

    for dezena in ajustados:
        if media_soma >= 198 and dezena >= 13:
            ajustados[dezena] *= 1.015

        if media_soma <= 192 and dezena <= 13:
            ajustados[dezena] *= 1.015

    return normalizar_scores(ajustados, piso=0.002)


# =========================================================
# SCORE / GERAÇÃO
# =========================================================


# V17.4

def ranking_modelos(modelos):
    return sorted(((k,sum(v.values()) if isinstance(v,dict) else 0) for k,v in modelos.items()), key=lambda x:x[1], reverse=True)
