"""
lotofacil_pkg/v21_0_meta_aprendizado.py
-----------------------------------------
V21.1-B — Meta-Aprendizado integrado ao histórico SQLite.

Usa o histórico real de suspensões/recuperações registrado pelo
v21_0_sqlite para calcular probabilidade de recuperação por modelo.
Compatível com a interface anterior (MetaAprendizadoModelos).
"""

from statistics import mean, pstdev
from .v21_0_sqlite import get_db, db_prob_recuperacao


class MetaAprendizadoModelos:
    """
    Interface compatível com V20. Internamente usa SQLite quando disponível,
    com fallback para o cálculo por série temporal (comportamento original).
    """

    def probabilidade_recuperacao(self, historico_scores: list, model_id: str = None) -> float:
        """
        Se model_id fornecido, usa o histórico real do SQLite.
        Caso contrário, usa série temporal (comportamento legado).
        """
        # Tenta usar o SQLite primeiro
        if model_id:
            try:
                prob_db = db_prob_recuperacao(model_id)
                if prob_db != 0.5:   # 0.5 = sem histórico, usa série temporal
                    return prob_db
            except Exception:
                pass

        # Fallback: cálculo por série temporal (comportamento original V20)
        if not historico_scores or len(historico_scores) < 5:
            return 0.50
        recuperacoes = 0
        quedas = 0
        for i in range(1, len(historico_scores)):
            if historico_scores[i - 1] < 0.50:
                quedas += 1
                if historico_scores[i] > historico_scores[i - 1]:
                    recuperacoes += 1
        return recuperacoes / max(quedas, 1)

    def recomendar_status(self, score_atual: float, historico_scores: list,
                          model_id: str = None) -> str:
        """
        Classifica modelo em ATIVO, OBSERVACAO ou SUSPENSO.
        Usa probabilidade de recuperação enriquecida com histórico SQLite.
        """
        prob = self.probabilidade_recuperacao(historico_scores, model_id=model_id)
        if score_atual < 0.50 and prob >= 0.70:
            return "OBSERVACAO"
        if score_atual < 0.50:
            return "SUSPENSO"
        return "ATIVO"

    def avaliar_todos(self, modelos_com_scores: dict) -> list:
        """
        Avalia uma lista de modelos e retorna status + probabilidade.
        modelos_com_scores: {nome: {"score": float, "historico": [float, ...]}}
        """
        resultados = []
        for nome, dados in modelos_com_scores.items():
            score    = float(dados.get("score", 0.0))
            historico = dados.get("historico", [])
            prob     = self.probabilidade_recuperacao(historico, model_id=nome)
            status   = self.recomendar_status(score, historico, model_id=nome)
            resultados.append({
                "nome":              nome,
                "score":             round(score, 4),
                "prob_recuperacao":  round(prob, 4),
                "status":            status,
            })
        return sorted(resultados, key=lambda x: x["score"], reverse=True)


def score_estabilidade(historico:list)->float:
    if len(historico)<2:
        return 0.0
    media=mean(historico)
    desvio=pstdev(historico)
    return round(media/(1+desvio),4)


def calcular_peso_contextual(score, prob_recuperacao, confianca):
    return round(
        score*0.50 + prob_recuperacao*0.30 + confianca*0.20,
        4
    )
