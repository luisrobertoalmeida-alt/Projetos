"""
lotofacil_pkg/v20_2_poda_inteligente.py
-----------------------------------------
Poda Inteligente de Modelos -- V20.2

Classifica cada modelo do ensemble em ATIVO, OBSERVACAO ou SUSPENSO
com base no historico de desempenho, e aplica a decisao diretamente em
pesos_modelos.json para que a proxima geracao de apostas use pesos
corrigidos.

Estados:
  ATIVO      (score >= 0.08) -- modelo contribui normalmente
  OBSERVACAO (score >= 0.03) -- modelo recebe penalidade de peso leve
  SUSPENSO   (score  < 0.03) -- modelo tem peso reduzido ao minimo

Fatores de penalidade:
  FATOR_OBSERVACAO  = 0.70   -- 70% do peso natural
  FATOR_SUSPENSO    = 0.25   -- 25% do peso natural
  PESO_MIN_ABSOLUTO = 0.05   -- nunca zera um modelo completamente
"""
import json
import os
import threading
from pathlib import Path
from statistics import mean, stdev

# -- Caminhos ------------------------------------------------------------------
# ROBOLOTOFACIL_DADOS_DIR: override usado pela suíte de testes (ver
# lotofacil_pkg/tests/__init__.py) para isolar os testes do dados/ real
# do repositório -- checado no momento do import.
_DIR_OVERRIDE = os.environ.get("ROBOLOTOFACIL_DADOS_DIR")
_BASE = Path(_DIR_OVERRIDE) if _DIR_OVERRIDE else Path(__file__).resolve().parent.parent / "dados"
_BASE.mkdir(parents=True, exist_ok=True)
_ARQ_PESOS = _BASE / "pesos_modelos.json"
_ARQ_HIST  = _BASE / "historico_modelos.json"

# -- Lock global para acesso thread-safe ao historico -------------------------
_LOCK_HIST = threading.Lock()

# -- Estados ------------------------------------------------------------------
ESTADO_ATIVO      = "ATIVO"
ESTADO_OBSERVACAO = "OBSERVACAO"
ESTADO_SUSPENSO   = "SUSPENSO"

# -- Fatores de penalidade ----------------------------------------------------
FATOR_OBSERVACAO  = 0.70
FATOR_SUSPENSO    = 0.25
PESO_MIN_ABSOLUTO = 0.05


# -- Funcoes publicas basicas (mantidas para compatibilidade) -----------------

def score_sobrevivencia(score_global, desempenho_recente, estabilidade):
    """Score ponderado [0, 1]: 50% global + 30% recente + 20% estabilidade."""
    return round(
        (score_global * 0.5) + (desempenho_recente * 0.3) + (estabilidade * 0.2),
        4,
    )


def classificar_modelo(score):
    """Classifica usando limiares compatíveis com os scores reais do projeto."""
    if score >= 0.08:
        return ESTADO_ATIVO
    if score >= 0.03:
        return ESTADO_OBSERVACAO
    return ESTADO_SUSPENSO


def salvar_quarentena(modelos, arquivo="modelos_quarentena.json"):
    """Persiste apenas os modelos SUSPENSOS em JSON."""
    suspensos = [m for m in modelos if m.get("estado") == ESTADO_SUSPENSO]
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(suspensos, f, indent=2, ensure_ascii=False)
    return suspensos


# -- Funcoes de leitura/escrita do historico ----------------------------------

def _carregar_historico():
    if not _ARQ_HIST.exists():
        return {}
    try:
        return json.loads(_ARQ_HIST.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _salvar_historico(hist):
    _ARQ_HIST.write_text(
        json.dumps(hist, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _carregar_pesos():
    if not _ARQ_PESOS.exists():
        return {}
    try:
        return json.loads(_ARQ_PESOS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _salvar_pesos(pesos):
    _ARQ_PESOS.write_text(
        json.dumps(pesos, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# -- Registro de resultado por modelo (thread-safe) ---------------------------

def registrar_resultado_modelo_backtest(acertos_por_modelo):
    """
    Registra os acertos medios de cada modelo em um passo do backtest.

    Recebe um dict {nome_modelo: media_acertos} e atualiza o historico
    persistente em historico_modelos.json. Thread-safe via lock global.

    Args:
        acertos_por_modelo: dict mapeando nome do modelo para media de
                            acertos obtida no sorteio simulado do passo.
    """
    with _LOCK_HIST:
        hist = _carregar_historico()
        for nome, media in acertos_por_modelo.items():
            if nome not in hist:
                hist[nome] = {"concursos": 0, "media": 0.0, "ultimos": []}
            info = hist[nome]
            info["concursos"] += 1
            info["ultimos"].append(float(media))
            info["ultimos"] = info["ultimos"][-30:]
            n = info["concursos"]
            info["media"] = round(
                (info["media"] * (n - 1) + float(media)) / n, 6
            )

        _salvar_historico(hist)

        # Recalcula pesos adaptativos a partir das médias históricas
        medias = {
            nome: max(0.0001, float(info.get("media", 0.0)))
            for nome, info in hist.items()
        }
        soma = sum(medias.values()) or 1.0
        pesos = {
            nome: round(valor / soma, 6)
            for nome, valor in medias.items()
        }
        _salvar_pesos(pesos)


# -- Funcao principal: fecha o loop -------------------------------------------

def avaliar_e_podar_modelos(modelos_ativos=None, min_concursos=5):
    """
    Le o historico de desempenho de cada modelo, calcula o score de
    sobrevivencia e ajusta os pesos em pesos_modelos.json.

    Args:
        modelos_ativos: lista dos nomes de modelo do ensemble. Se None,
                        usa todos os modelos presentes no historico_modelos.json.
        min_concursos:  minimo de concursos registrados para classificar um
                        modelo. Modelos com menos dados ficam como ATIVO.

    Returns:
        Lista de dicts, um por modelo:
          nome, concursos, media_global, media_recente, estabilidade,
          score_sobrevivencia, estado, fator_aplicado, peso_novo
    """
    hist = _carregar_historico()
    pesos_atuais = _carregar_pesos()

    nomes = modelos_ativos or list(hist.keys())
    if not nomes:
        return []

    resultados = []
    pesos_novos = dict(pesos_atuais)

    for nome in nomes:
        info = hist.get(nome)

        # Modelo sem historico suficiente: mantém peso sem penalidade
        if info is None or info.get("concursos", 0) < min_concursos:
            resultados.append({
                "nome": nome,
                "concursos": (info or {}).get("concursos", 0),
                "media_global": 0.0,
                "media_recente": 0.0,
                "estabilidade": 0.0,
                "score_sobrevivencia": 0.0,
                "estado": ESTADO_ATIVO,
                "fator_aplicado": 1.0,
                "peso_novo": pesos_atuais.get(nome, 1.0),
                "obs": "dados_insuficientes",
            })
            continue

        ultimos = info.get("ultimos", [])

        # score_global: media historica normalizada de [9, 13] para [0, 1]
        # 9 = esperado do aleatorio; 13 = desempenho muito bom
        media_global_raw = float(info.get("media", 0.0))
        score_global = max(0.0, min(1.0, (media_global_raw - 9.0) / 4.0))

        # desempenho_recente: media dos ultimos N registros, mesma escala
        media_recente_raw = mean(ultimos) if ultimos else media_global_raw
        desempenho_recente = max(0.0, min(1.0, (media_recente_raw - 9.0) / 4.0))

        # estabilidade: 1 - desvio normalizado
        # desvio de 2 pontos na escala de acertos e considerado alto
        if len(ultimos) >= 2:
            dp = stdev(ultimos)
            estabilidade = max(0.0, min(1.0, 1.0 - dp / 2.0))
        else:
            estabilidade = 0.5

        sv = score_sobrevivencia(score_global, desempenho_recente, estabilidade)
        estado = classificar_modelo(sv)

        # aplica fator de penalidade ao peso atual
        peso_base = pesos_atuais.get(nome, 1.0)
        if estado == ESTADO_SUSPENSO:
            fator = FATOR_SUSPENSO
        elif estado == ESTADO_OBSERVACAO:
            fator = FATOR_OBSERVACAO
        else:
            fator = 1.0

        peso_novo = max(PESO_MIN_ABSOLUTO, peso_base * fator)
        pesos_novos[nome] = round(peso_novo, 6)

        resultados.append({
            "nome": nome,
            "concursos": info["concursos"],
            "media_global": round(media_global_raw, 4),
            "media_recente": round(media_recente_raw, 4),
            "estabilidade": round(estabilidade, 4),
            "score_sobrevivencia": sv,
            "estado": estado,
            "fator_aplicado": fator,
            "peso_novo": round(peso_novo, 6),
        })

    # Renormaliza so se a soma ficar muito fora dos limites esperados
    soma = sum(pesos_novos.values()) or 1.0
    n_modelos = max(1, len(pesos_novos))
    if soma < n_modelos * 0.3 or soma > n_modelos * 3.0:
        pesos_novos = {k: round(v / soma, 6) for k, v in pesos_novos.items()}

    _salvar_pesos(pesos_novos)
    return resultados
