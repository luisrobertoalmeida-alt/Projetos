"""
lotofacil_pkg/v21_0_meta_aprendizado.py
-----------------------------------------
V21.1-B — Meta-Aprendizado integrado ao histórico SQLite.

Usa o histórico real de suspensões/recuperações registrado pelo
v21_0_sqlite para calcular probabilidade de recuperação por modelo.

Reduzido em 2026-07-23 (ver ARQUITETURA.md) a só
`probabilidade_recuperacao()` — a única função de fato usada (por
`analise.py`). `recomendar_status()`, `avaliar_todos()`,
`score_estabilidade()` e `calcular_peso_contextual()` nunca tinham
nenhum chamador real fora deste próprio arquivo.
"""

from .v21_0_sqlite import db_prob_recuperacao


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
