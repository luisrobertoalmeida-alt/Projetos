"""
lotofacil_pkg/config.py
-----------------------
Constantes globais do RoboLotofacilPro.
Centralizadas aqui para facilitar ajustes sem mexer na lógica.
"""
import os

API_BASE = "https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil"
NUMEROS = list(range(1, 26))
TAMANHO_JOGO = 15  # Lotofácil padrão: 15 | Aceita 15–18 para testes
MIN_HIST = 60

BASE_APP_DIR  = os.path.join(os.path.expanduser("~"), "Documents", "RoboLotofacilPro")
PASTA_DADOS   = os.path.join(BASE_APP_DIR, "dados")
PASTA_BACKUP  = os.path.join(BASE_APP_DIR, "backup")
PASTA_EXPORT  = os.path.join(BASE_APP_DIR, "exportacoes")
PASTA_LOG     = os.path.join(BASE_APP_DIR, "logs")

ARQUIVO_CSV_PADRAO            = os.path.join(PASTA_DADOS, "lotofacil_resultados_reais.csv")
ARQUIVO_CACHE                 = os.path.join(PASTA_DADOS, "lotofacil_cache_estado.json")
ARQUIVO_APRENDIZADO           = os.path.join(PASTA_DADOS, "lotofacil_aprendizado_permanente.json")
ARQUIVO_ULTIMOS_JOGOS         = os.path.join(PASTA_DADOS, "lotofacil_ultimos_jogos_gerados.json")
ARQUIVO_AUTO_AVALIACOES       = os.path.join(PASTA_DADOS, "lotofacil_auto_avaliacoes.json")
ARQUIVO_AUTO_APRENDIZADO      = os.path.join(PASTA_DADOS, "lotofacil_auto_aprendizado.json")
ARQUIVO_PERFORMANCE_ESTRATEGIA = os.path.join(PASTA_DADOS, "lotofacil_performance_estrategias.json")
ARQUIVO_DESEMPENHO_HISTORICO  = os.path.join(PASTA_DADOS, "lotofacil_desempenho_historico.json")
ARQUIVO_CONHECIMENTO_CIENTIFICO = os.path.join(PASTA_DADOS, "lotofacil_conhecimento_cientifico_v11.json")

HTTP_TIMEOUT       = 25
HTTP_MAX_RETRIES   = 3
HTTP_BACKOFF_FACTOR = 0.8

MODO_TURBO_PADRAO = True
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36"
)
SEED = None
VERSAO_ROBO = "V22.0 · Dashboard Científico · Pipeline Automático · Sistema de Plugins · Config YAML · Relatório Automático"

_PASTAS_APP = (BASE_APP_DIR, PASTA_DADOS, PASTA_BACKUP, PASTA_EXPORT, PASTA_LOG)


# ── Tema visual ──────────────────────────────────────────────────────────────
TEMA = {
    "bg":            "#050a12",   # fundo principal — quase preto azulado
    "bg2":           "#090f1a",   # painéis internos
    "bg3":           "#0d1520",   # bordas / separadores
    "bg4":           "#111d2e",   # hover / destaques suaves
    "fg":            "#d0e8ff",   # texto principal — branco frio
    "fg2":           "#4a7fa8",   # texto secundário
    "accent":        "#00c8ff",   # ciano neon principal
    "accent2":       "#7b2fff",   # roxo neon secundário
    "verde":         "#00ff9f",   # neon verde
    "amarelo":       "#ffdd00",   # neon amarelo
    "vermelho":      "#ff3860",   # neon vermelho
    "laranja":       "#ff7300",   # neon laranja
    "roxo":          "#c444ff",   # neon roxo
    "ciano":         "#00e5ff",   # ciano claro
    "rosa":          "#ff2d78",   # rosa neon
    # botões
    "btn_atualizar": "#004d20",
    "btn_carregar":  "#003580",
    "btn_gerar":     "#7a2800",
    "btn_lab":       "#3d006a",
    "btn_backtest":  "#004d40",
    "btn_backauto":  "#1a0066",
    "btn_aprender":  "#3d006a",
    "btn_parar":     "#6a0000",
    "btn_dash":      "#003366",
    "btn_conferir":  "#660033",
    "btn_salvar":    "#1a4d00",
    "btn_excel":     "#00402e",
    "btn_limpar":    "#1a2a35",
    "btn_encerrar":  "#550000",
    "btn_csv":       "#1a2530",
    "btn_atalho":    "#0d1a26",
    "btn_comparar":  "#004d55",
    "btn_simulador": "#002244",
    "btn_relatorio": "#1a1a40",
    "btn_pdf":       "#330022",
    "btn_pacote":    "#1a3300",
}
