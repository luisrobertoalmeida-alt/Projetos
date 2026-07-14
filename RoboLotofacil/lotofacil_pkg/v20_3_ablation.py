
import json

def avaliar_contribuicao(score_completo, score_sem_modelo):
    return round(score_completo - score_sem_modelo, 4)

def ranking_contribuicao(contribuicoes):
    return sorted(contribuicoes.items(), key=lambda x: x[1], reverse=True)

def gerar_relatorio_ablation(contribuicoes, arquivo="ablation_history.json"):
    ranking = ranking_contribuicao(contribuicoes)
    dados = {
        "ranking": ranking,
        "modelos_negativos": [m for m,v in contribuicoes.items() if v < 0]
    }
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)
    return dados
