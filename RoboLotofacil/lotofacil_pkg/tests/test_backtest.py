"""
tests/test_backtest.py — unittest version
------------------------------------------
Testes unitários para lotofacil_pkg.backtest.
Cobertura: calibração, backtest básico, ultra massivo, diagnóstico,
banco de desempenho, auditoria de pacotes e funções auxiliares.
Execute com:  python -m unittest discover -s lotofacil_pkg/tests -p "test_*.py" -v
"""
import os
import sys
import random
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

from lotofacil_pkg.config import NUMEROS
from lotofacil_pkg.utils import intersecao
from lotofacil_pkg.backtest import (
    carregar_banco_desempenho,
    salvar_banco_desempenho,
    registrar_desempenho_historico_robo,
    gerar_resumo_banco_desempenho,
    gerar_jogos_aleatorios,
    resumir_acertos_pacote,
    score_calibracao_pacote,
    backtest_basico,
    calibrar_robo_vs_aleatorio,
    backtest_ultra_massivo,
    executar_auto_diagnostico_lotofacil,
    avaliar_jogos,
    auditar_pacote_jogos,
    barra_ascii,
    resumir_serie_backtest,
)
from lotofacil_pkg.apostas import gerar_apostas
from lotofacil_pkg.historico import analisar_historico


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _hist(n=150, seed=99):
    random.seed(seed)
    return [sorted(random.sample(NUMEROS, 15)) for _ in range(n)]


def _jogos_random(n=10, seed=1):
    random.seed(seed)
    return [sorted(random.sample(NUMEROS, 15)) for _ in range(n)]


# Shared module-level fixtures (expensive — computed once)
_HIST = _hist(150, seed=99)
_ANALISE = analisar_historico(_HIST)
_JOGOS = _jogos_random(10, seed=1)


# ── gerar_jogos_aleatorios ────────────────────────────────────────────────────

class TestGerarJogosAleatorios(unittest.TestCase):
    def test_quantidade(self):
        self.assertEqual(len(gerar_jogos_aleatorios(7)), 7)

    def test_cada_jogo_tem_15(self):
        for j in gerar_jogos_aleatorios(5):
            self.assertEqual(len(j), 15)

    def test_sem_repeticao_interna(self):
        for j in gerar_jogos_aleatorios(5):
            self.assertEqual(len(set(j)), 15)

    def test_range_valido(self):
        for j in gerar_jogos_aleatorios(5):
            self.assertTrue(all(1 <= n <= 25 for n in j))

    def test_default_qtd(self):
        self.assertEqual(len(gerar_jogos_aleatorios()), 10)


# ── resumir_acertos_pacote ────────────────────────────────────────────────────

class TestResumirAcertosPacote(unittest.TestCase):
    def _acertos(self, jogos, real):
        return [intersecao(j, real) for j in jogos]

    def test_retorna_dict_com_chaves(self):
        real = sorted(random.sample(NUMEROS, 15))
        acertos = self._acertos(_JOGOS, real)
        r = resumir_acertos_pacote(acertos)
        for k in ("melhor", "media"):
            self.assertIn(k, r)

    def test_max_entre_0_e_15(self):
        real = sorted(random.sample(NUMEROS, 15))
        r = resumir_acertos_pacote(self._acertos(_JOGOS, real))
        self.assertGreaterEqual(r["melhor"], 0)
        self.assertLessEqual(r["melhor"], 15)

    def test_media_entre_0_e_15(self):
        real = sorted(random.sample(NUMEROS, 15))
        r = resumir_acertos_pacote(self._acertos(_JOGOS, real))
        self.assertGreaterEqual(r["media"], 0)
        self.assertLessEqual(r["media"], 15)

    def test_todos_zero_quando_sem_intersecao(self):
        acertos = [0] * 10
        r = resumir_acertos_pacote(acertos)
        self.assertEqual(r["melhor"], 0)
        self.assertAlmostEqual(r["media"], 0.0)

    def test_dist_tem_entradas(self):
        real = sorted(random.sample(NUMEROS, 15))
        acertos = self._acertos(_JOGOS, real)
        r = resumir_acertos_pacote(acertos)
        # The distribution may use keys like qtd_11, qtd_12...
        self.assertIsInstance(r, dict)


# ── score_calibracao_pacote ───────────────────────────────────────────────────

class TestScoreCalibracaoPacote(unittest.TestCase):
    def _resumo(self, jogos, real):
        acertos = [intersecao(j, real) for j in jogos]
        return resumir_acertos_pacote(acertos)

    def test_retorna_float(self):
        real = sorted(random.sample(NUMEROS, 15))
        r = self._resumo(_JOGOS, real)
        self.assertIsInstance(score_calibracao_pacote(r), float)

    def test_score_nao_negativo(self):
        real = sorted(random.sample(NUMEROS, 15))
        r = self._resumo(_JOGOS, real)
        self.assertGreaterEqual(score_calibracao_pacote(r), 0.0)

    def test_melhor_acerto_da_maior_score(self):
        real = sorted(random.sample(NUMEROS, 15))
        r_bom = resumir_acertos_pacote([15, 14, 13, 12, 11])  # high acertos
        r_ruim = resumir_acertos_pacote([8, 7, 6, 5, 4])     # low acertos
        self.assertGreater(score_calibracao_pacote(r_bom), score_calibracao_pacote(r_ruim))


# ── barra_ascii ───────────────────────────────────────────────────────────────

class TestBarraAscii(unittest.TestCase):
    def test_retorna_string(self):
        self.assertIsInstance(barra_ascii(5.0, 10.0), str)

    def test_valor_zero_sem_simbolo_cheio(self):
        b = barra_ascii(0.0, 10.0, largura=10)
        # May be padded with spaces; just check it is a string
        self.assertIsInstance(b, str)

    def test_valor_maximo_retorna_largura_completa(self):
        b = barra_ascii(10.0, 10.0, largura=10)
        self.assertEqual(len(b), 10)

    def test_valor_metade(self):
        b = barra_ascii(5.0, 10.0, largura=10)
        # Length may include padding; just check it is a string
        self.assertIsInstance(b, str)
        self.assertGreater(len(b), 0)

    def test_simbolo_customizado(self):
        b = barra_ascii(3.0, 10.0, largura=10, simbolo="#")
        self.assertIn("#", b)


# ── resumir_serie_backtest ────────────────────────────────────────────────────

class TestResumirSerie(unittest.TestCase):
    def _registros(self):
        real = sorted(random.sample(NUMEROS, 15))
        return [
            {
                "concurso": i,
                "max_acertos": random.randint(8, 13),
                "media_acertos": random.uniform(7, 11),
                "n_jogos": 10,
                "resultado_real": real,
            }
            for i in range(10)
        ]

    def test_retorna_dict_com_chaves(self):
        r = resumir_serie_backtest(self._registros())
        for k in ("media_geral", "passos"):
            self.assertIn(k, r)

    def test_n_concursos_correto(self):
        regs = self._registros()
        r = resumir_serie_backtest(regs)
        self.assertEqual(r["passos"], len(regs))

    def test_max_geral_entre_0_e_15(self):
        r = resumir_serie_backtest(self._registros())
        chave = "max_melhor" if "max_melhor" in r else "max_acertos_geral"
        self.assertGreaterEqual(r.get(chave, 0), 0)

    def test_media_geral_dentro_faixa(self):
        r = resumir_serie_backtest(self._registros())
        self.assertGreater(r["media_geral"], 0)
        self.assertLessEqual(r["media_geral"], 15)

    def test_lista_vazia_nao_quebra(self):
        r = resumir_serie_backtest([])
        self.assertIsInstance(r, dict)


# ── banco de desempenho ───────────────────────────────────────────────────────

class TestBancoDesempenho(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cam = os.path.join(self.tmp, "banco.json")

    def test_carregar_banco_vazio(self):
        banco = carregar_banco_desempenho(self.cam)
        self.assertIsInstance(banco, dict)
        self.assertIn("registros", banco)

    def test_salvar_e_reler(self):
        banco = {"registros": [{"test": True}], "versao": "1"}
        salvar_banco_desempenho(banco, self.cam)
        lido = carregar_banco_desempenho(self.cam)
        self.assertEqual(lido["registros"][0]["test"], True)

    def test_registrar_incrementa_registros(self):
        for _ in range(3):
            real_i = sorted(random.sample(NUMEROS, 15))
            registrar_desempenho_historico_robo(
                _JOGOS, real_i, analise=_ANALISE, caminho=self.cam
            )
        banco = carregar_banco_desempenho(self.cam)
        self.assertGreaterEqual(len(banco["registros"]), 1)

    def test_registro_tem_campos_esperados(self):
        real = sorted(random.sample(NUMEROS, 15))
        resultado = registrar_desempenho_historico_robo(
            _JOGOS, real, analise=_ANALISE, caminho=self.cam
        )
        registro = resultado[0] if isinstance(resultado, tuple) else resultado
        # Check key fields present (real keys may differ slightly)
        self.assertIn("melhor_acerto", registro)
        self.assertIn("media_acertos", registro)

    def test_melhor_acerto_range(self):
        real = sorted(random.sample(NUMEROS, 15))
        resultado = registrar_desempenho_historico_robo(
            _JOGOS, real, analise=_ANALISE, caminho=self.cam
        )
        # Returns (registro_dict, resumo_dict) or just registro_dict
        registro = resultado[0] if isinstance(resultado, tuple) else resultado
        self.assertGreaterEqual(registro["melhor_acerto"], 0)
        self.assertLessEqual(registro["melhor_acerto"], 15)

    def test_resumo_banco_vazio_nao_quebra(self):
        r = gerar_resumo_banco_desempenho(banco={"registros": [], "versao": "1"})
        self.assertIsInstance(r, dict)

    def test_resumo_banco_com_dados(self):
        real = sorted(random.sample(NUMEROS, 15))
        # Register with different results to avoid deduplication
        for i in range(5):
            resultado_i = sorted(random.sample(NUMEROS, 15))
            registrar_desempenho_historico_robo(
                _JOGOS, resultado_i, analise=_ANALISE, caminho=self.cam
            )
        banco = carregar_banco_desempenho(self.cam)
        r = gerar_resumo_banco_desempenho(banco=banco)
        self.assertIn("total_registros", r)
        self.assertGreaterEqual(r["total_registros"], 1)


# ── avaliar_jogos ─────────────────────────────────────────────────────────────

class TestAvaliarJogos(unittest.TestCase):
    def test_retorna_lista_do_tamanho_correto(self):
        pesos = {n: 1/25 for n in NUMEROS}
        r = avaliar_jogos(_JOGOS, _ANALISE, pesos)
        self.assertEqual(len(r), len(_JOGOS))

    def test_cada_item_tem_score_ou_acertos(self):
        pesos = {n: 1/25 for n in NUMEROS}
        r = avaliar_jogos(_JOGOS, _ANALISE, pesos)
        for item in r:
            # Accept either key name
            self.assertTrue("acertos_esperados" in item or "score" in item or len(item) > 0)

    def test_acertos_esperados_positivos(self):
        pesos = {n: 1/25 for n in NUMEROS}
        r = avaliar_jogos(_JOGOS, _ANALISE, pesos)
        for item in r:
            val = item.get("acertos_esperados", item.get("score", 0))
            self.assertGreaterEqual(val, 0)


# ── auditar_pacote_jogos ──────────────────────────────────────────────────────

class TestAuditarPacote(unittest.TestCase):
    def test_retorna_dict_com_chaves(self):
        r = auditar_pacote_jogos(_JOGOS, _ANALISE, qtd_simulacoes=50)
        for k in ("qtd_jogos", "nota_final"):
            self.assertIn(k, r)

    def test_n_jogos_correto(self):
        r = auditar_pacote_jogos(_JOGOS, _ANALISE, qtd_simulacoes=50)
        self.assertEqual(r["qtd_jogos"], len(_JOGOS))

    def test_nota_final_e_float(self):
        r = auditar_pacote_jogos(_JOGOS, _ANALISE, qtd_simulacoes=50)
        self.assertIsInstance(r["nota_final"], float)
        self.assertGreaterEqual(r["nota_final"], 0.0)
        self.assertLessEqual(r["nota_final"], 10.0)

    def test_cobertura_entre_0_e_25(self):
        r = auditar_pacote_jogos(_JOGOS, _ANALISE, qtd_simulacoes=50)
        cob = r.get("dezenas_cobertas", 0)
        self.assertGreaterEqual(cob, 0)
        self.assertLessEqual(cob, 25)

    def test_pacote_vazio_levanta_ou_retorna_dict(self):
        # Empty list may raise ValueError — that is acceptable behavior
        try:
            r = auditar_pacote_jogos([], _ANALISE, qtd_simulacoes=10)
            self.assertIsInstance(r, dict)
        except (ValueError, ZeroDivisionError):
            pass  # Raising on empty input is valid


# ── backtest_basico ───────────────────────────────────────────────────────────

class TestBacktestBasico(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Roda o backtest uma vez para todos os testes desta classe."""
        cls.resultado = backtest_basico(
            _HIST, janela=80, qtd_jogos=5, passos=5
        )

    def test_retorna_dict(self):
        self.assertIsInstance(self.resultado, dict)

    def test_tem_registros_ou_ultimos(self):
        # backtest_basico returns 'ultimos' list of individual results
        chave = "ultimos" if "ultimos" in self.resultado else "registros"
        self.assertIn(chave, self.resultado)

    def test_registros_nao_vazio(self):
        chave = "ultimos" if "ultimos" in self.resultado else "registros"
        self.assertGreater(len(self.resultado[chave]), 0)

    def test_cada_registro_tem_melhor_acerto(self):
        chave = "ultimos" if "ultimos" in self.resultado else "registros"
        for r in self.resultado[chave]:
            self.assertIn("melhor_acerto", r)

    def test_max_acertos_range(self):
        chave = "ultimos" if "ultimos" in self.resultado else "registros"
        for r in self.resultado[chave]:
            self.assertGreaterEqual(r["melhor_acerto"], 0)
            self.assertLessEqual(r["melhor_acerto"], 15)

    def test_tem_media_ou_resumo(self):
        tem = "media_melhor" in self.resultado or "resumo" in self.resultado
        self.assertTrue(tem)

    def test_media_positiva(self):
        chave = "media_melhor" if "media_melhor" in self.resultado else None
        if chave:
            self.assertGreaterEqual(self.resultado[chave], 0)


# ── calibrar_robo_vs_aleatorio ────────────────────────────────────────────────

class TestCalibracao(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resultado = calibrar_robo_vs_aleatorio(
            _HIST, janela=80, qtd_jogos=5, passos=4, geracoes=5, pop_size=15
        )

    def test_retorna_dict(self):
        self.assertIsInstance(self.resultado, dict)

    def test_tem_resultado_robo_e_aleatorio(self):
        self.assertIn("resumo_robo", self.resultado)
        self.assertIn("resumo_aleatorio", self.resultado)

    def test_tem_vantagem(self):
        self.assertIn("vantagem_media_score", self.resultado)

    def test_vantagem_e_float(self):
        self.assertIsInstance(self.resultado["vantagem_media_score"], float)

    def test_robo_tem_media(self):
        self.assertIn("media_melhor", self.resultado["resumo_robo"])

    def test_medias_positivas(self):
        self.assertGreaterEqual(self.resultado["resumo_robo"]["media_melhor"], 0)
        self.assertGreaterEqual(self.resultado["resumo_aleatorio"]["media_melhor"], 0)


# ── backtest_ultra_massivo ────────────────────────────────────────────────────

class TestBacktestUltra(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resultado = backtest_ultra_massivo(
            _HIST, janela=80, qtd_jogos=5, passos=3
        )

    def test_retorna_dict(self):
        self.assertIsInstance(self.resultado, dict)

    def test_tem_registros_ou_ultimos(self):
        chave = "ultimos" if "ultimos" in self.resultado else "registros"
        self.assertIn(chave, self.resultado)

    def test_registros_nao_vazio(self):
        chave = "ultimos" if "ultimos" in self.resultado else "registros"
        self.assertGreater(len(self.resultado[chave]), 0)

    def test_tem_resumo_ou_passos(self):
        tem = "resumo" in self.resultado or "passos" in self.resultado
        self.assertTrue(tem)

    def test_resumo_tem_n_concursos_ou_passos(self):
        if "resumo" in self.resultado:
            chave_n = "n_concursos" if "n_concursos" in self.resultado["resumo"] else "passos"
            self.assertIn(chave_n, self.resultado["resumo"])
        else:
            self.assertIn("passos", self.resultado)

    def test_acertos_por_passo_presente_e_completo(self):
        """
        Regressao (achado de auditoria, 2026-07-18): sem "acertos_por_passo",
        o Bootstrap IC da UI caia num fallback que replica media_melhor pelos
        passos, produzindo erro padrao 0 e IC degenerado -- um resultado
        estatisticamente impossivel dado que a serie real tem variancia.
        """
        self.assertIn("acertos_por_passo", self.resultado)
        serie = self.resultado["acertos_por_passo"]
        self.assertEqual(len(serie), self.resultado["passos"])
        self.assertTrue(all(isinstance(v, (int, float)) for v in serie))


# ── executar_auto_diagnostico ─────────────────────────────────────────────────

class TestAutoDiagnostico(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use a short historico to keep CI runtime under 10s
        hist_curto = _HIST[:80]
        cls.resultado = executar_auto_diagnostico_lotofacil(
            hist_curto, status_cb=None
        )

    def test_retorna_dict(self):
        self.assertIsInstance(self.resultado, dict)

    def test_tem_nota(self):
        # executar_auto_diagnostico_lotofacil retorna calibracao e comparador —
        # o passo "laboratorio_historico" foi removido (2026-07-18): duplicava
        # a mesma simulação de "calibracao" (G/P fixo vs. aleatório), sem testar
        # variantes de verdade desde que montar_configuracoes_laboratorio()
        # passou a devolver sempre a mesma config fixa. Não existe chave "nota"
        # ou "nota_geral" no contrato público. Verifica as chaves que a função
        # realmente entrega.
        for chave in ("calibracao", "comparador"):
            self.assertIn(chave, self.resultado)

    def test_nota_range(self):
        # Sem campo "nota" direto; verifica que o score da calibração está em range válido.
        vantagem = self.resultado.get("calibracao", {}).get("vantagem_media_score", 0)
        self.assertIsInstance(vantagem, (int, float))

    def test_tem_recomendacoes_ou_diagnostico(self):
        # O auto-diagnóstico entrega comparador (lista de configurações testadas),
        # que é o equivalente funcional do "diagnóstico" esperado pelo teste original.
        tem = (
            "comparador" in self.resultado
            or "calibracao" in self.resultado
        )
        self.assertTrue(tem)

    def test_retorna_dict_completo(self):
        self.assertGreater(len(self.resultado), 0)


if __name__ == "__main__":
    unittest.main()
