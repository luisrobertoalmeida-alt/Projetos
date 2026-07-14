
from concurrent.futures import ProcessPoolExecutor
import os

def cpu_disponiveis():
    total = os.cpu_count() or 1
    return max(1, total - 2)

def executar_em_paralelo(funcao, itens):
    workers = cpu_disponiveis()
    with ProcessPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(funcao, itens))

def processar_modelos(funcao_modelo, modelos):
    return executar_em_paralelo(funcao_modelo, modelos)

def processar_backtest(funcao_backtest, lotes):
    return executar_em_paralelo(funcao_backtest, lotes)

def processar_montecarlo(funcao_mc, cargas):
    return executar_em_paralelo(funcao_mc, cargas)
