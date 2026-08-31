"""
lotofacil_pkg/v18_1b_ia_adaptativa.py
---------------------------------------
Leitura de pesos adaptativos por modelo.

Só `carregar_pesos_modelos()` é usado de fato (por analise.py, no
ensemble multi-IA). As demais funções que existiam aqui
(registrar_resultado_modelo, calcular_rating_modelo,
recalcular_pesos_adaptativos, gerar_hall_da_fama, salvar_pesos_modelos)
foram removidas em 2026-07-19: nunca tinham nenhum chamador real —
quem de fato grava `pesos_modelos.json`/`historico_modelos.json` é
`v20_2_poda_inteligente.py` (via backtest.py), que por coincidência usa
os mesmos nomes de arquivo. Ver ARQUITETURA.md.
"""
import json
import os
from pathlib import Path

# ROBOLOTOFACIL_DADOS_DIR: override usado pela suíte de testes (ver
# lotofacil_pkg/tests/__init__.py) para isolar os testes do dados/ real
# do repositório -- checado no momento do import, não depende de qual
# "cópia" do módulo está em memória (mais robusto que monkeypatch de
# atributo, que falhou em alguns cenários de setUpClass).
_DIR_OVERRIDE = os.environ.get("ROBOLOTOFACIL_DADOS_DIR")
BASE = Path(_DIR_OVERRIDE) if _DIR_OVERRIDE else Path(__file__).resolve().parent.parent / "dados"
BASE.mkdir(parents=True, exist_ok=True)

ARQ_PESOS = BASE / "pesos_modelos.json"


def carregar_pesos_modelos():
    if not ARQ_PESOS.exists():
        return {}
    return json.loads(ARQ_PESOS.read_text(encoding="utf-8"))
