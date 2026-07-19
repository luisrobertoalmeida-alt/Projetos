"""
tests/test_v20_2_poda_inteligente.py
--------------------------------------
Testes unitários para v20_2_poda_inteligente: score de sobrevivência,
classificação de modelos, quarentena.

Antes vivia em test_v20_modulos.py junto com os testes de
v20_4_backtest_massivo e v20_3_ablation — ambos código órfão (nunca
chamados fora de si mesmos e de seus próprios testes) e removidos em
2026-07-19 (ver ARQUITETURA.md). Este arquivo mantém apenas os testes
do que continua em uso real (registrar_resultado_modelo_backtest e
avaliar_e_podar_modelos são chamados por backtest.py).

Execute com:  python -m unittest discover -s lotofacil_pkg/tests -p "test_*.py" -v
"""
import os
import sys
import json
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Isola v18_1b_ia_adaptativa/v20_2_poda_inteligente do dados/ real do
# repositorio durante os testes (ver lotofacil_pkg/tests/__init__.py e
# ARQUITETURA.md -- 'unittest discover' com caminho de arquivo nao
# executa esse __init__.py de forma confiavel, entao o isolamento
# tambem precisa estar aqui, no proprio arquivo de teste).
import tempfile as _tempfile
os.environ.setdefault("ROBOLOTOFACIL_DADOS_DIR", _tempfile.mkdtemp(prefix="robolotofacil_testes_"))

from lotofacil_pkg.v20_2_poda_inteligente import (
    score_sobrevivencia,
    classificar_modelo,
    salvar_quarentena,
    ESTADO_ATIVO,
    ESTADO_OBSERVACAO,
    ESTADO_SUSPENSO,
)


class TestScoreSobrevivencia(unittest.TestCase):

    def test_pesos_somam_um(self):
        # 0.5 + 0.3 + 0.2 = 1.0
        s = score_sobrevivencia(1.0, 1.0, 1.0)
        self.assertAlmostEqual(s, 1.0)

    def test_score_zero_quando_tudo_zero(self):
        s = score_sobrevivencia(0.0, 0.0, 0.0)
        self.assertAlmostEqual(s, 0.0)

    def test_pesos_individuais(self):
        # só score_global=1, resto 0 → deve retornar 0.5
        self.assertAlmostEqual(score_sobrevivencia(1.0, 0.0, 0.0), 0.5)
        # só desempenho_recente=1 → deve retornar 0.3
        self.assertAlmostEqual(score_sobrevivencia(0.0, 1.0, 0.0), 0.3)
        # só estabilidade=1 → deve retornar 0.2
        self.assertAlmostEqual(score_sobrevivencia(0.0, 0.0, 1.0), 0.2)


class TestClassificarModelo(unittest.TestCase):

    def test_ativo_acima_de_070(self):
        self.assertEqual(classificar_modelo(0.70), ESTADO_ATIVO)
        self.assertEqual(classificar_modelo(0.99), ESTADO_ATIVO)

    def test_observacao_entre_050_e_070(self):
        # Limiares reais: ATIVO >= 0.08, OBSERVACAO >= 0.03, SUSPENSO < 0.03
        self.assertEqual(classificar_modelo(0.05), ESTADO_OBSERVACAO)
        self.assertEqual(classificar_modelo(0.07), ESTADO_OBSERVACAO)

    def test_suspenso_abaixo_de_050(self):
        self.assertEqual(classificar_modelo(0.02), ESTADO_SUSPENSO)
        self.assertEqual(classificar_modelo(0.0), ESTADO_SUSPENSO)

    def test_fronteiras_exatas(self):
        self.assertEqual(classificar_modelo(0.08), ESTADO_ATIVO)
        self.assertEqual(classificar_modelo(0.03), ESTADO_OBSERVACAO)


class TestSalvarQuarentena(unittest.TestCase):

    def test_salva_apenas_suspensos(self):
        modelos = [
            {"nome": "A", "estado": ESTADO_ATIVO},
            {"nome": "B", "estado": ESTADO_SUSPENSO},
            {"nome": "C", "estado": ESTADO_OBSERVACAO},
            {"nome": "D", "estado": ESTADO_SUSPENSO},
        ]
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            caminho = f.name
        try:
            suspensos = salvar_quarentena(modelos, arquivo=caminho)
            self.assertEqual(len(suspensos), 2)
            nomes = {m["nome"] for m in suspensos}
            self.assertEqual(nomes, {"B", "D"})
            with open(caminho, encoding="utf-8") as f:
                dados = json.load(f)
            self.assertEqual(len(dados), 2)
        finally:
            os.unlink(caminho)

    def test_nenhum_suspenso(self):
        modelos = [{"nome": "X", "estado": ESTADO_ATIVO}]
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            caminho = f.name
        try:
            suspensos = salvar_quarentena(modelos, arquivo=caminho)
            self.assertEqual(suspensos, [])
        finally:
            os.unlink(caminho)


if __name__ == "__main__":
    unittest.main(verbosity=2)
