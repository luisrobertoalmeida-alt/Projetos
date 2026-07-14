
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "dados"
BASE.mkdir(exist_ok=True)

ARQ_PESOS = BASE / "pesos_modelos.json"
ARQ_HIST = BASE / "historico_modelos.json"

PESO_MIN = 0.10
PESO_MAX = 0.40

def _media(v):
    return sum(v)/len(v) if v else 0.0

def carregar_historico():
    if not ARQ_HIST.exists():
        return {}
    return json.loads(ARQ_HIST.read_text(encoding="utf-8"))

def salvar_historico(hist):
    ARQ_HIST.write_text(json.dumps(hist, indent=2), encoding="utf-8")

def carregar_pesos_modelos():
    if not ARQ_PESOS.exists():
        return {}
    return json.loads(ARQ_PESOS.read_text(encoding="utf-8"))

def salvar_pesos_modelos(pesos):
    ARQ_PESOS.write_text(json.dumps(pesos, indent=2), encoding="utf-8")

def registrar_resultado_modelo(nome_modelo, pontos):
    hist = carregar_historico()

    if nome_modelo not in hist:
        hist[nome_modelo] = {
            "concursos": 0,
            "media": 0.0,
            "ultimos": []
        }

    info = hist[nome_modelo]
    info["concursos"] += 1
    info["ultimos"].append(float(pontos))
    info["ultimos"] = info["ultimos"][-20:]

    total_antigo = info["media"] * (info["concursos"] - 1)
    info["media"] = (total_antigo + pontos) / info["concursos"]

    salvar_historico(hist)
    return info

def calcular_rating_modelo(info):
    media_geral = info.get("media", 0.0)
    media_recente = _media(info.get("ultimos", []))
    return media_geral * 0.6 + media_recente * 0.4

def recalcular_pesos_adaptativos():
    hist = carregar_historico()

    ratings = {
        nome: calcular_rating_modelo(info)
        for nome, info in hist.items()
    }

    soma = sum(ratings.values()) or 1.0

    pesos = {}
    for nome, rating in ratings.items():
        p = rating / soma
        p = max(PESO_MIN, p)
        p = min(PESO_MAX, p)
        pesos[nome] = round(p, 6)

    salvar_pesos_modelos(pesos)
    return pesos

def gerar_hall_da_fama():
    hist = carregar_historico()
    ranking = sorted(
        hist.items(),
        key=lambda x: calcular_rating_modelo(x[1]),
        reverse=True
    )
    return ranking
