
import os, pickle

from .config import PASTA_DADOS


class CacheBacktest:
    def __init__(self, pasta=None):
        # Usa a mesma pasta de dados do resto do app (~/Documents/RoboLotofacilPro/dados)
        # em vez de um caminho relativo ao diretório de trabalho atual, que mudava
        # conforme de onde o programa era executado e fazia o cache "sumir".
        self.pasta = pasta or os.path.join(PASTA_DADOS, "cache_backtests")
        os.makedirs(self.pasta, exist_ok=True)

    def carregar(self, chave):
        arq = os.path.join(self.pasta, f"{chave}.pkl")
        if os.path.exists(arq):
            with open(arq, "rb") as f:
                return pickle.load(f)
        return None

    def salvar(self, chave, dados):
        arq = os.path.join(self.pasta, f"{chave}.pkl")
        with open(arq, "wb") as f:
            pickle.dump(dados, f)
