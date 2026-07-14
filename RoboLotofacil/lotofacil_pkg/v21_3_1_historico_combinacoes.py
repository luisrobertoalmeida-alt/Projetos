
from itertools import combinations

class HistoricoCombinacoes:
    def __init__(self):
        self.registros = []

    def registrar(self, modelos, score):
        self.registros.append(
            {"combo":"+".join(modelos),"score":score}
        )

    def top(self, n=10):
        return sorted(
            self.registros,
            key=lambda x: x["score"],
            reverse=True
        )[:n]
