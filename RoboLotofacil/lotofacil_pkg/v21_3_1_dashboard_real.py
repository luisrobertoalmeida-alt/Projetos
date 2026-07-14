from .v21_0_sqlite import db_ultimos_pesos

def dados_dashboard(pesos=None, ranking=None, metricas=None):
    return {
        "pesos": pesos or db_ultimos_pesos(),
        "ranking": ranking or [],
        "metricas": metricas or {},
        "confianca_modelos": {},
        "ranking_historico": [],
        "versao": "V21.4"
    }
