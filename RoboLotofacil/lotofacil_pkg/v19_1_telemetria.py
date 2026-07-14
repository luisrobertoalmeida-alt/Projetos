
import json, time

class Telemetria:
    def __init__(self):
        self.dados = {}

    def iniciar(self, nome):
        self.dados[nome] = time.time()

    def finalizar(self, nome):
        self.dados[nome] = time.time() - self.dados[nome]
        return self.dados[nome]
