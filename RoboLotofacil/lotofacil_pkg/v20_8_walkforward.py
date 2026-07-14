"""
lotofacil_pkg/v20_8_walkforward.py
------------------------------------
Walk-Forward Validation — V20.8

Objetivo: substituir o split temporal fixo (70/15/15) por uma validação
deslizante que avalia o robô em múltiplas janelas consecutivas, eliminando
o viés de "sorte de split" e tornando o score de robustez muito mais confiável.

Como funciona:
  - O histórico é percorrido com uma janela de treino de tamanho fixo.
  - A cada passo, o modelo é avaliado na janela de teste imediatamente seguinte.
  - O processo se repete deslocando ambas as janelas para frente.
  - O resultado é a distribuição de scores ao longo de todos os passos.

Funções exportadas:
  gerar_janelas_walkforward   — gera os índices de treino/teste para cada passo
  score_janela                — calcula acertos médios de um lote de jogos vs sorteio
  executar_walkforward        — executa a validação completa e retorna métricas
  score_robustez_walkforward  — score escalar [0, 1] derivado da distribuição
  detectar_overfitting_wf     — detecção de overfitting baseada na degradação
  relatorio_walkforward       — relatório consolidado com todas as métricas

Notas de design:
  - Todas as funções são puras (sem I/O, sem estado global).
  - A função `gerar_apostas` do pipeline principal NÃO é chamada aqui para
    manter o módulo independente; o caller injeta a função de geração via
    parâmetro `fn_gerar`.
  - I/O (salvar JSON) fica em `salvar_relatorio_walkforward()`, separado.
"""
import json
import math
import random
from statistics import mean, stdev
from typing import Any, Callable


# ── helpers internos ─────────────────────────────────────────────────────────

def _clip(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _acertos(jogo: list[int], sorteio: list[int]) -> int:
    return len(set(jogo) & set(sorteio))


# ── funções públicas ──────────────────────────────────────────────────────────

def gerar_janelas_walkforward(
    n_concursos: int,
    tamanho_treino: int = 100,
    tamanho_teste: int = 20,
    passo: int = 20,
) -> list[dict[str, Any]]:
    """
    Gera os índices de treino e teste para cada janela walk-forward.

    Args:
        n_concursos:    total de concursos disponíveis no histórico.
        tamanho_treino: número de concursos usados para treino em cada janela.
        tamanho_teste:  número de concursos usados para teste em cada janela.
        passo:          deslocamento entre janelas consecutivas.

    Returns:
        Lista de dicts com chaves:
          - janela:        índice da janela (1-based)
          - treino_inicio: índice inicial do treino (inclusivo)
          - treino_fim:    índice final do treino (exclusivo)
          - teste_inicio:  índice inicial do teste (inclusivo)
          - teste_fim:     índice final do teste (exclusivo)
    """
    if n_concursos < tamanho_treino + tamanho_teste:
        return []

    janelas = []
    inicio = 0
    idx = 1
    while True:
        treino_fim = inicio + tamanho_treino
        teste_fim = treino_fim + tamanho_teste
        if teste_fim > n_concursos:
            break
        janelas.append({
            "janela": idx,
            "treino_inicio": inicio,
            "treino_fim": treino_fim,
            "teste_inicio": treino_fim,
            "teste_fim": teste_fim,
        })
        inicio += passo
        idx += 1

    return janelas


def score_janela(
    jogos: list[list[int]],
    sorteios_teste: list[list[int]],
) -> dict[str, float]:
    """
    Calcula métricas de acertos de um lote de jogos contra sorteios de teste.

    Args:
        jogos:          lista de jogos gerados pelo robô (cada um com 15 dezenas).
        sorteios_teste: lista de sorteios reais do período de teste.

    Returns:
        Dict com:
          - media_acertos:  média de acertos por (jogo × sorteio)
          - melhor_acerto:  máximo de acertos em qualquer combinação
          - taxa_11_mais:   fração de combinações com 11+ acertos
          - n_combinacoes:  total de pares (jogo, sorteio) avaliados
    """
    if not jogos or not sorteios_teste:
        return {
            "media_acertos": 0.0,
            "melhor_acerto": 0,
            "taxa_11_mais": 0.0,
            "n_combinacoes": 0,
        }

    acertos_lista = []
    for sorteio in sorteios_teste:
        for jogo in jogos:
            acertos_lista.append(_acertos(jogo, sorteio))

    total = len(acertos_lista)
    media = mean(acertos_lista)
    melhor = max(acertos_lista)
    taxa11 = sum(1 for a in acertos_lista if a >= 11) / total

    return {
        "media_acertos": round(media, 4),
        "melhor_acerto": melhor,
        "taxa_11_mais": round(taxa11, 4),
        "n_combinacoes": total,
    }


def executar_walkforward(
    concursos: list[list[int]],
    fn_gerar: Callable[[list[list[int]]], list[list[int]]],
    tamanho_treino: int = 100,
    tamanho_teste: int = 20,
    passo: int = 20,
) -> dict[str, Any]:
    """
    Executa a validação walk-forward completa.

    Args:
        concursos:      histórico completo, do mais antigo para o mais recente.
        fn_gerar:       função que recebe o histórico de treino e retorna
                        uma lista de jogos gerados. Assinatura:
                        ``fn_gerar(historico_treino) -> list[list[int]]``
        tamanho_treino: concursos por janela de treino.
        tamanho_teste:  concursos por janela de teste.
        passo:          deslocamento entre janelas.

    Returns:
        Dict com:
          - janelas:          lista de resultados por janela (cada uma com
                              índices + métricas de score_janela)
          - medias_por_janela: lista de média de acertos por janela
          - media_geral:      média sobre todas as janelas
          - desvio_geral:     desvio padrão das médias por janela
          - n_janelas:        quantidade de janelas avaliadas
          - parametros:       dict com tamanho_treino, tamanho_teste, passo
    """
    janelas_idx = gerar_janelas_walkforward(
        len(concursos), tamanho_treino, tamanho_teste, passo
    )

    if not janelas_idx:
        return {
            "janelas": [],
            "medias_por_janela": [],
            "media_geral": 0.0,
            "desvio_geral": 0.0,
            "n_janelas": 0,
            "parametros": {
                "tamanho_treino": tamanho_treino,
                "tamanho_teste": tamanho_teste,
                "passo": passo,
            },
        }

    resultados_janelas = []
    medias = []

    for jd in janelas_idx:
        treino = concursos[jd["treino_inicio"]: jd["treino_fim"]]
        teste = concursos[jd["teste_inicio"]: jd["teste_fim"]]

        try:
            jogos = fn_gerar(treino)
        except Exception:
            jogos = []

        score = score_janela(jogos, teste)
        medias.append(score["media_acertos"])

        resultados_janelas.append({
            **jd,
            **score,
        })

    media_geral = round(mean(medias), 4) if medias else 0.0
    desvio_geral = round(stdev(medias), 4) if len(medias) >= 2 else 0.0

    return {
        "janelas": resultados_janelas,
        "medias_por_janela": medias,
        "media_geral": media_geral,
        "desvio_geral": desvio_geral,
        "n_janelas": len(resultados_janelas),
        "parametros": {
            "tamanho_treino": tamanho_treino,
            "tamanho_teste": tamanho_teste,
            "passo": passo,
        },
    }


def score_robustez_walkforward(
    medias_por_janela: list[float],
    referencia_aleatoria: float = 9.0,
) -> float:
    """
    Calcula um score escalar [0, 1] de robustez a partir da distribuição
    de médias walk-forward.

    O score penaliza tanto a distância da média geral até o aleatório
    quanto a variância entre janelas (robô instável = score menor).

    Args:
        medias_por_janela:    lista de médias de acertos por janela.
        referencia_aleatoria: média esperada de um apostador aleatório
                              na Lotofácil (≈ 9.0 acertos em 15).

    Returns:
        Score [0.0, 1.0].
    """
    if not medias_por_janela:
        return 0.0

    media = mean(medias_por_janela)
    desvio = stdev(medias_por_janela) if len(medias_por_janela) >= 2 else 0.0

    # componente de ganho sobre o aleatório (normalizado para [0,1] em escala de 15)
    ganho = (media - referencia_aleatoria) / (15.0 - referencia_aleatoria)
    ganho = _clip(ganho)

    # componente de consistência: penaliza desvio padrão alto
    # desvio de 1.0 em escala 0–15 é considerado alto
    consistencia = _clip(1.0 - desvio / 1.5)

    score = ganho * 0.6 + consistencia * 0.4
    return round(_clip(score), 6)


def detectar_overfitting_wf(
    medias_por_janela: list[float],
    limiar_degradacao: float = 0.85,
) -> dict[str, Any]:
    """
    Detecta overfitting comparando o desempenho nas janelas iniciais (treino
    visto muito) vs janelas finais (dados mais recentes e menos vistos).

    Args:
        medias_por_janela:  lista de médias por janela, em ordem cronológica.
        limiar_degradacao:  fração mínima aceitável (janelas_finais / janelas_iniciais).
                            Padrão 0.85 = queda de até 15% é tolerada.

    Returns:
        Dict com:
          - overfitting_detectado: bool
          - media_janelas_iniciais: média do primeiro terço
          - media_janelas_finais:   média do último terço
          - razao:                  media_finais / media_iniciais
          - limiar:                 limiar usado
          - severidade:             "ALTO", "MODERADO" ou "NORMAL"
    """
    n = len(medias_por_janela)
    if n < 3:
        return {
            "overfitting_detectado": False,
            "media_janelas_iniciais": 0.0,
            "media_janelas_finais": 0.0,
            "razao": 1.0,
            "limiar": limiar_degradacao,
            "severidade": "INSUFICIENTE",
        }

    corte = max(1, n // 3)
    media_ini = mean(medias_por_janela[:corte])
    media_fim = mean(medias_por_janela[-corte:])

    razao = round(media_fim / media_ini, 4) if media_ini > 0 else 1.0
    detectado = razao < limiar_degradacao

    if razao < 0.70:
        severidade = "ALTO"
    elif razao < limiar_degradacao:
        severidade = "MODERADO"
    else:
        severidade = "NORMAL"

    return {
        "overfitting_detectado": detectado,
        "media_janelas_iniciais": round(media_ini, 4),
        "media_janelas_finais": round(media_fim, 4),
        "razao": razao,
        "limiar": limiar_degradacao,
        "severidade": severidade,
    }


def relatorio_walkforward(
    concursos: list[list[int]],
    fn_gerar: Callable[[list[list[int]]], list[list[int]]],
    tamanho_treino: int = 100,
    tamanho_teste: int = 20,
    passo: int = 20,
    referencia_aleatoria: float = 9.0,
    limiar_degradacao: float = 0.85,
) -> dict[str, Any]:
    """
    Gera o relatório consolidado de walk-forward validation.

    Args:
        (ver executar_walkforward e detectar_overfitting_wf para demais params)

    Returns:
        Dict com seções:
          - walkforward:   resultado de executar_walkforward()
          - robustez:      score escalar [0, 1]
          - overfitting:   resultado de detectar_overfitting_wf()
          - resumo:        dict de alto nível para exibição rápida
    """
    wf = executar_walkforward(
        concursos, fn_gerar, tamanho_treino, tamanho_teste, passo
    )
    medias = wf["medias_por_janela"]
    robustez = score_robustez_walkforward(medias, referencia_aleatoria)
    overfitting = detectar_overfitting_wf(medias, limiar_degradacao)

    resumo = {
        "n_janelas_avaliadas": wf["n_janelas"],
        "media_geral_acertos": wf["media_geral"],
        "desvio_entre_janelas": wf["desvio_geral"],
        "score_robustez": robustez,
        "overfitting_detectado": overfitting["overfitting_detectado"],
        "severidade_overfitting": overfitting["severidade"],
        "veredito": (
            "ROBUSTO" if robustez >= 0.6 and not overfitting["overfitting_detectado"]
            else "INSTAVEL" if overfitting["severidade"] == "ALTO"
            else "ACEITAVEL"
        ),
    }

    return {
        "walkforward": wf,
        "robustez": robustez,
        "overfitting": overfitting,
        "resumo": resumo,
    }


def salvar_relatorio_walkforward(
    relatorio: dict[str, Any],
    arquivo: str = "walkforward_validation.json",
) -> None:
    """
    Persiste o relatório walk-forward em JSON. Única função com I/O neste módulo.

    Args:
        relatorio: dict retornado por relatorio_walkforward().
        arquivo:   caminho de saída.
    """
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(relatorio, f, indent=2, ensure_ascii=False)
