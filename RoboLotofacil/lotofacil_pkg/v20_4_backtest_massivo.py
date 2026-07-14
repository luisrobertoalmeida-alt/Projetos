"""
lotofacil_pkg/v20_4_backtest_massivo.py
----------------------------------------
Backtest massivo multi-janela com suporte a execução paralela.

Correção V20.4: substituída lambda não-serializável no ProcessPoolExecutor
por função nomeada no nível de módulo (_avaliar_item), compatível com pickle.
"""
import json
from concurrent.futures import ProcessPoolExecutor


def avaliar_janela(nome: str, resultados: list) -> dict:
    """Calcula a média dos resultados de uma janela temporal."""
    if not resultados:
        return {"janela": nome, "media": 0}
    return {"janela": nome, "media": round(sum(resultados) / len(resultados), 4)}


def _avaliar_item(item: tuple) -> dict:
    """
    Wrapper serializável (pickle-safe) para uso com ProcessPoolExecutor.
    Lambdas não são serializáveis pelo pickle — função nomeada é obrigatória.
    """
    nome, dados = item
    return avaliar_janela(nome, dados)


def backtest_multijanela(janelas: dict) -> list:
    """Executa backtest sequencial em múltiplas janelas temporais."""
    return [avaliar_janela(nome, dados) for nome, dados in janelas.items()]


def backtest_paralelo(janelas: dict) -> list:
    """
    Executa backtest em paralelo via ProcessPoolExecutor.
    Usa _avaliar_item (função nomeada) em vez de lambda para garantir
    compatibilidade com pickle em todos os sistemas operacionais.
    """
    with ProcessPoolExecutor() as ex:
        return list(ex.map(_avaliar_item, janelas.items()))


def gerar_relatorio_backtest(resultados: list, arquivo: str = "backtest_massivo.json") -> dict:
    """Persiste os resultados do backtest em JSON."""
    dados = {"resultados": resultados}
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)
    return dados
