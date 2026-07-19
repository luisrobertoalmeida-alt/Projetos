# RoboLotofacilPro V20.8 — Pacote Modular

> **AVISO:** Loteria é jogo de azar. Este software não prevê sorteios; ele
> otimiza métricas de qualidade estrutural do pacote (cobertura, entropia,
> diversidade). Use com responsabilidade.

## Estrutura do pacote

```
lotofacil_pkg/
├── config.py                    Constantes globais e tema visual
├── utils.py                     Funções puras (math, string, JSON, I/O)
├── aprendizado.py               Memória adaptativa permanente
├── persistencia.py              Download API CAIXA, CSV, Excel, backup
├── historico.py                 Carregamento e análise do histórico
├── analise.py                   Motor Estratégico + Ensemble Multi-IA (7 modelos)
├── genetico.py                  Algoritmo genético, scoring estrutural, cobertura
├── apostas.py                   Orquestração do pipeline de geração
├── backtest.py                  Backtesting, calibração, laboratório, relatórios
├── ui.py                        Interface gráfica tkinter (Neon Dark)
├── v17_4_features.py            Split temporal, redundância, cobertura de pares/trios
├── v18_1b_ia_adaptativa.py      Leitura de pesos adaptativos por modelo
├── v20_2_poda_inteligente.py    Score de sobrevivência e quarentena de modelos
├── v20_5_validacao_cientifica.py  Benchmarks, z-score e ganho estatístico vs aleatório
├── v20_6_bootstrap.py           IC bootstrap, Cohen's d, p-value por permutação
├── v20_8_walkforward.py         Walk-forward validation, robustez e detecção de overfitting
└── tests/
    ├── test_utils.py              Funções puras
    ├── test_analise_genetico.py   Modelos IA e algoritmo genético
    ├── test_apostas_pipeline.py   Pipeline completo e aprendizado
    ├── test_backtest.py           Backtesting e laboratório
    ├── test_v17_4_features.py     Split temporal, redundância, cobertura de pares/trios
    ├── test_v20_2_poda_inteligente.py  Score de sobrevivência e quarentena de modelos
    ├── test_v20_5_validacao_cientifica.py  Validação científica V20.5
    └── test_v20_novos_modulos.py  Bootstrap V20.6 e Walk-Forward V20.8
```

> Nota (2026-07-19): v18_meta_otimizador.py, v18_1c_meta_ensemble.py,
> v18_2_montecarlo.py, v18_2b_auditor_cientifico.py, v19_1_benchmark.py,
> v19_1_cache_inteligente.py, v19_1_estabilidade.py, v19_1_telemetria.py,
> v20_3_ablation.py, v20_4_backtest_massivo.py e execucao_paralela.py
> foram removidos por serem código órfão (nunca chamados fora de si
> mesmos e de seus próprios testes) — ver ARQUITETURA.md.
> `v18_3_parallel.py`/`v19_0_arquitetura_cientifica.py`, citados em
> versões anteriores deste README, já não existiam no repositório antes
> dessa limpeza.

## Instalação

```bash
pip install pandas requests          # obrigatórias
pip install reportlab                # opcional — exportação PDF
pip install -e .                     # instala o pacote em modo editável
```

## Uso como aplicativo desktop

```bash
python main.py
# ou, após instalar com setup.py:
lotofacil
```

## Uso programático

```python
import random
from lotofacil_pkg.apostas import gerar_apostas
from lotofacil_pkg.config import NUMEROS

# Histórico sintético para exemplo — use carregar_concursos_do_csv() na prática
historico = [sorted(random.sample(NUMEROS, 15)) for _ in range(200)]

jogos, analise, pesos = gerar_apostas(
    historico,
    qtd_jogos=10,
    janela_analise=120,
    geracoes=35,
    pop_size=70,
)

for i, jogo in enumerate(jogos, 1):
    print(f"Jogo {i:2d}: {' '.join(f'{n:02d}' for n in jogo)}")
```

## Rodando os testes

```bash
python -m unittest discover -s lotofacil_pkg/tests -p "test_*.py" -v
```

## Walk-Forward Validation V20.8

```python
from lotofacil_pkg.apostas import gerar_apostas
from lotofacil_pkg.v20_8_walkforward import relatorio_walkforward, salvar_relatorio_walkforward

def fn_gerar(historico_treino):
    jogos, _, _ = gerar_apostas(historico_treino, qtd_jogos=10)
    return jogos

rel = relatorio_walkforward(
    concursos,           # lista de sorteios completa (mais antigo → mais recente)
    fn_gerar,
    tamanho_treino=100,
    tamanho_teste=20,
    passo=20,
)

print(rel["resumo"]["veredito"])         # "ROBUSTO" | "ACEITAVEL" | "INSTAVEL"
print(rel["resumo"]["score_robustez"])   # float [0, 1]
print(rel["overfitting"]["severidade"])  # "NORMAL" | "MODERADO" | "ALTO"

salvar_relatorio_walkforward(rel, "walkforward.json")
```

## Bootstrap IC V20.6

```python
from lotofacil_pkg.v20_6_bootstrap import relatorio_inferencial, salvar_relatorio_inferencial

# resultados: lista de dicts com chave "acertos" ou "media_acertos"
resultados_robo     = [{"acertos": a} for a in acertos_backtest]
resultados_baseline = [{"acertos": a} for a in acertos_aleatorio]

rel = relatorio_inferencial(resultados_robo, resultados_baseline, n_reamostras=2000)

ic95 = rel["ic_media"]["intervalos"]["95%"]
print(f"Média: {rel['ic_media']['media_observada']:.4f}  IC 95%: [{ic95['inferior']} – {ic95['superior']}]")
print(f"p-value: {rel['significancia']['p_value']}  Cohen's d: {rel['cohen_d']['cohen_d']:.4f} [{rel['cohen_d']['magnitude']}]")

salvar_relatorio_inferencial(rel, "bootstrap_ic.json")
```

## Validação Científica V20.5

```python
from lotofacil_pkg.v20_5_validacao_cientifica import relatorio_validacao

rel = relatorio_validacao(resultados_robo)
print(rel["resumo"]["veredito_vs_aleatorio"])   # "SUPERIOR" | "EQUIVALENTE" | "INFERIOR"
print(rel["resumo"]["z_score"])
print(rel["resumo"]["interpretacao_ganho"])     # "GANHO_RELEVANTE" | "GANHO_MODERADO" | …
```

## Histórico de versões

| Versão | Principais mudanças |
|--------|---------------------|
| V12 | Monolito original — 1 arquivo, 7.200 linhas, sem testes |
| V13 | Refatoração em 10 módulos, 117 testes unitários |
| V14 | Type hints a 97%, heap lazy O(n·k·log n), 167 testes |
| V17.4 | Decay de aprendizado, split temporal, ranking ensemble, diversidade genética |
| V18.x | IA adaptativa, Meta-Ensemble, Monte Carlo, Auditor Científico, processamento paralelo |
| V19.0 | `pipeline_v19` unificado centralizando todos os módulos V18+ |
| V19.1 | Telemetria, cache inteligente de backtest, benchmark de modelos, score de estabilidade |
| V20.2 | Poda inteligente: score de sobrevivência e quarentena de modelos fracos |
| V20.3 | Ablation study: contribuição marginal de cada modelo no ensemble |
| V20.4 | Backtest massivo multi-janela com execução paralela (pickle-safe) |
| V20.5 | Validação científica automática: z-score e benchmarks vs aleatório |
| V20.6 | Inferência bootstrap: IC 95%/99%, p-value por permutação, Cohen's d |
| V20.8 | Walk-Forward validation deslizante: score de robustez + detecção de overfitting; integração completa na UI (botões 🔀 Walk-Forward e 📐 Bootstrap IC) |
