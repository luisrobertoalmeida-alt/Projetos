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
  v18_1b_ia_adaptativa      — leitura de pesos adaptativos por modelo (escrita real é v20_2_poda_inteligente)
  v20_2_poda_inteligente    — poda inteligente de modelos (score/estado/quarentena)
  v20_5_validacao_cientifica — benchmarks e ganho estatístico (z-score)
  v20_6_bootstrap           — IC bootstrap, Cohen's d, p-value por permutação, estatística pareada, TOST
  v20_8_walkforward         — walk-forward validation, robustez e overfitting
  fechamento                — fechamento combinatório de garantia total
  auditoria_cientifica      — auditoria estatística contínua para validações

  Nota (2026-07-19): v18_meta_otimizador, v18_1c_meta_ensemble,
  v18_2_montecarlo, v18_2b_auditor_cientifico, v19_1_benchmark,
  v19_1_cache_inteligente, v19_1_estabilidade, v19_1_telemetria,
  v20_3_ablation, v20_4_backtest_massivo e execucao_paralela foram
  removidos por serem código órfão (nunca chamados fora de si mesmos e
  de seus próprios testes) — ver auditoria completa no ARQUITETURA.md.

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
