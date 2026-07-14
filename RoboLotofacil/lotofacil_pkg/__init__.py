"""
lotofacil_pkg
=============
RoboLotofacilPro V19 — pacote modular.

Estrutura:
  config      — constantes globais e tema visual
  utils       — funções puras (math, string, JSON, I/O)
  aprendizado — memória adaptativa permanente
  persistencia — download API CAIXA, CSV, Excel
  historico   — carregamento e normalização do histórico
  analise     — análise estatística + Motor Estratégico + Ensemble Multi-IA (7 modelos)
  genetico    — algoritmo genético, scoring estrutural, cobertura
  apostas     — orquestração do pipeline de geração
  backtest    — backtesting, calibração, laboratório, relatórios
  ui          — interface gráfica tkinter (Neon Dark)
  v17_4_features            — split temporal, redundância, cobertura de pares/trios
  v18_meta_otimizador       — pesos adaptativos por modelo
  v18_1b_ia_adaptativa      — detecção de cenário e ajuste de pesos
  v18_1c_meta_ensemble      — meta-ensemble por cenário
  v18_2_montecarlo          — simulação Monte Carlo e heatmap
  v18_2b_auditor_cientifico — auditoria de overfitting e pesos
  v18_3_parallel            — execução paralela
  v19_0_arquitetura_cientifica — pipeline V19 unificado
  v19_1_benchmark           — comparação e ranking de modelos
  v19_1_cache_inteligente   — cache persistente de backtest
  v19_1_estabilidade        — score composto de estabilidade
  v19_1_telemetria          — medição de tempo por etapa
  v20_5_validacao_cientifica — benchmarks e ganho estatístico (z-score)
  v20_6_bootstrap           — IC bootstrap, Cohen's d, p-value por permutação
  v20_8_walkforward         — walk-forward validation, robustez e overfitting

Uso rápido:
  from lotofacil_pkg.apostas import gerar_apostas
  from lotofacil_pkg.ui import RoboLotofacilUltraApp, main

  # Estatística inferencial
  from lotofacil_pkg.v20_6_bootstrap import relatorio_inferencial
  from lotofacil_pkg.v20_8_walkforward import relatorio_walkforward
"""
from .config import VERSAO_ROBO
from .utils import seed_global, garantir_estrutura_pastas

__version__ = "21.5.0"
__all__ = ["VERSAO_ROBO", "seed_global", "garantir_estrutura_pastas"]
