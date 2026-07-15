"""
tests/test_v20_5_validacao_cientifica.py
-----------------------------------------
Testes unitários para v20_5_validacao_cientifica.

Cobertura:
  - benchmark_vs_aleatorio   : delta, veredito, caso sem dados
  - benchmark_vs_base        : comparação com estratégia externa
  - estabilidade_por_janela  : janelas padrão, janela maior que histórico, janelas customizadas
  - ganho_estatistico        : z-score, interpretação, sem dados
  - ranking_versoes          : ordenação, desempate, campo posicao
  - relatorio_validacao      : estrutura completa, sem base, sem versoes
  - gerar_relatorio_validacao: persistência JSON válido

Execute com:
  python -m unittest discover -s lotofacil_pkg/tests -p "test_*.py" -v
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

from lotofacil_pkg.v20_5_validacao_cientifica import (
    benchmark_vs_aleatorio,
    benchmark_vs_base,
    estabilidade_por_janela,
    ganho_estatistico,
    ranking_versoes,
    relatorio_validacao,
    gerar_relatorio_validacao,
    _simular_aleatório,
)


# ── fixtures ──────────────────────────────────────────────────────────────────

def _resultados(n: int, acertos: float = 9.5) -> list[dict]:
    """Gera n registros com acertos fixo — útil para testes determinísticos."""
    return [{"acertos": acertos} for _ in range(n)]


def _resultados_variados(valores: list[float]) -> list[dict]:
    return [{"acertos": v} for v in valores]


# ── _simular_aleatório ────────────────────────────────────────────────────────

class TestSimularAleatorio(unittest.TestCase):

    def test_retorna_n_registros(self):
        r = _simular_aleatório(5, 30, seed=0)
        self.assertEqual(len(r), 30)

    def test_cada_registro_tem_chave_acertos(self):
        r = _simular_aleatório(5, 10, seed=1)
        for item in r:
            self.assertIn("acertos", item)

    def test_acertos_em_range_valido(self):
        # média de 15 números vs 15 aleatórios deve ficar em torno de 9
        r = _simular_aleatório(20, 200, seed=42)
        medias = [item["acertos"] for item in r]
        self.assertTrue(all(0 <= m <= 15 for m in medias))

    def test_reproducibilidade_com_seed(self):
        r1 = _simular_aleatório(10, 50, seed=7)
        r2 = _simular_aleatório(10, 50, seed=7)
        self.assertEqual(r1, r2)

    def test_seed_diferente_gera_resultado_diferente(self):
        r1 = _simular_aleatório(10, 50, seed=1)
        r2 = _simular_aleatório(10, 50, seed=2)
        # Probabilidade astronomicamente baixa de serem iguais
        self.assertNotEqual(r1, r2)


# ── benchmark_vs_aleatorio ────────────────────────────────────────────────────

class TestBenchmarkVsAleatorio(unittest.TestCase):

    def test_sem_dados_retorna_sem_dados(self):
        r = benchmark_vs_aleatorio([])
        self.assertEqual(r["veredito"], "SEM_DADOS")
        self.assertEqual(r["delta"], 0.0)

    def test_robo_claramente_superior(self):
        # acertos muito acima do esperado (~9) para forçar SUPERIOR
        resultados = _resultados(100, acertos=12.0)
        r = benchmark_vs_aleatorio(resultados, seed=42)
        self.assertEqual(r["veredito"], "SUPERIOR")
        self.assertGreater(r["delta"], 0)

    def test_robo_claramente_inferior(self):
        resultados = _resultados(100, acertos=5.0)
        r = benchmark_vs_aleatorio(resultados, seed=42)
        self.assertEqual(r["veredito"], "INFERIOR")
        self.assertLess(r["delta"], 0)

    def test_campos_presentes(self):
        r = benchmark_vs_aleatorio(_resultados(20), seed=42)
        for campo in ("media_robo", "media_aleatorio", "delta", "ganho_relativo", "veredito"):
            self.assertIn(campo, r)

    def test_aceita_campo_media_acertos(self):
        # campo alternativo usado em alguns registros do projeto
        resultados = [{"media_acertos": 10.0} for _ in range(30)]
        r = benchmark_vs_aleatorio(resultados, seed=42)
        self.assertAlmostEqual(r["media_robo"], 10.0)

    def test_reproducibilidade_seed(self):
        dados = _resultados(50, acertos=9.8)
        r1 = benchmark_vs_aleatorio(dados, seed=0)
        r2 = benchmark_vs_aleatorio(dados, seed=0)
        self.assertEqual(r1, r2)


# ── benchmark_vs_base ─────────────────────────────────────────────────────────

class TestBenchmarkVsBase(unittest.TestCase):

    def test_superior_quando_delta_positivo(self):
        robo = _resultados(50, acertos=10.0)
        base = _resultados(50, acertos=9.0)
        r = benchmark_vs_base(robo, base)
        self.assertEqual(r["veredito"], "SUPERIOR")
        self.assertAlmostEqual(r["delta"], 1.0)

    def test_inferior_quando_delta_negativo(self):
        robo = _resultados(50, acertos=8.0)
        base = _resultados(50, acertos=9.5)
        r = benchmark_vs_base(robo, base)
        self.assertEqual(r["veredito"], "INFERIOR")

    def test_equivalente_na_fronteira(self):
        robo = _resultados(50, acertos=9.0)
        base = _resultados(50, acertos=9.03)  # delta ~0.03, < 0.05
        r = benchmark_vs_base(robo, base)
        self.assertEqual(r["veredito"], "EQUIVALENTE")

    def test_tamanhos_diferentes_permitidos(self):
        robo = _resultados(30, acertos=10.0)
        base = _resultados(100, acertos=9.0)
        r = benchmark_vs_base(robo, base)
        self.assertIn("veredito", r)

    def test_campos_presentes(self):
        r = benchmark_vs_base(_resultados(10), _resultados(10))
        for campo in ("media_robo", "media_base", "delta", "veredito"):
            self.assertIn(campo, r)

    def test_listas_vazias(self):
        r = benchmark_vs_base([], [])
        self.assertEqual(r["media_robo"], 0.0)
        self.assertEqual(r["media_base"], 0.0)
        self.assertEqual(r["delta"], 0.0)


# ── estabilidade_por_janela ───────────────────────────────────────────────────

class TestEstabilidadePorJanela(unittest.TestCase):

    def test_janelas_padrao_presentes(self):
        dados = _resultados(100)
        r = estabilidade_por_janela(dados)
        for j in ("30", "60", "90"):
            self.assertIn(j, r)

    def test_n_correto_por_janela(self):
        dados = _resultados(100)
        r = estabilidade_por_janela(dados)
        self.assertEqual(r["30"]["n"], 30)
        self.assertEqual(r["60"]["n"], 60)
        self.assertEqual(r["90"]["n"], 90)

    def test_janela_maior_que_historico_usa_tudo(self):
        dados = _resultados(20)
        r = estabilidade_por_janela(dados, janelas={"90": 90})
        self.assertEqual(r["90"]["n"], 20)

    def test_media_correta(self):
        dados = _resultados_variados([8.0, 10.0, 12.0])
        r = estabilidade_por_janela(dados, janelas={"3": 3})
        self.assertAlmostEqual(r["3"]["media"], 10.0)

    def test_desvio_zero_para_valores_iguais(self):
        dados = _resultados(10, acertos=9.0)
        r = estabilidade_por_janela(dados, janelas={"10": 10})
        self.assertAlmostEqual(r["10"]["desvio"], 0.0)

    def test_janelas_customizadas(self):
        dados = _resultados(200)
        janelas = {"ultimas_50": 50, "ultimas_100": 100}
        r = estabilidade_por_janela(dados, janelas=janelas)
        self.assertIn("ultimas_50", r)
        self.assertIn("ultimas_100", r)

    def test_historico_vazio(self):
        r = estabilidade_por_janela([])
        for v in r.values():
            self.assertEqual(v["n"], 0)
            self.assertEqual(v["media"], 0.0)


# ── ganho_estatistico ─────────────────────────────────────────────────────────

class TestGanhoEstatistico(unittest.TestCase):

    def test_sem_dados_retorna_sem_dados(self):
        r = ganho_estatistico([])
        self.assertEqual(r["interpretacao"], "SEM_DADOS")
        self.assertEqual(r["z_score"], 0.0)

    def test_z_positivo_para_robo_superior(self):
        dados = _resultados(100, acertos=13.0)
        r = ganho_estatistico(dados, seed=42)
        self.assertGreater(r["z_score"], 0)

    def test_z_negativo_para_robo_inferior(self):
        dados = _resultados(100, acertos=5.0)
        r = ganho_estatistico(dados, seed=42)
        self.assertLess(r["z_score"], 0)

    def test_interpretacao_ganho_relevante(self):
        # forçar z alto com acertos muito acima do baseline (~9)
        dados = _resultados(200, acertos=13.5)
        r = ganho_estatistico(dados, seed=42)
        self.assertEqual(r["interpretacao"], "GANHO_RELEVANTE")

    def test_interpretacao_abaixo_do_aleatorio(self):
        dados = _resultados(200, acertos=4.0)
        r = ganho_estatistico(dados, seed=42)
        self.assertEqual(r["interpretacao"], "ABAIXO_DO_ALEATORIO")

    def test_campos_presentes(self):
        r = ganho_estatistico(_resultados(30), seed=0)
        for campo in ("z_score", "interpretacao", "media_robo", "media_aleatorio", "desvio_aleatorio"):
            self.assertIn(campo, r)

    def test_reproducibilidade_seed(self):
        dados = _resultados(60, acertos=9.8)
        r1 = ganho_estatistico(dados, seed=5)
        r2 = ganho_estatistico(dados, seed=5)
        self.assertEqual(r1, r2)


# ── ranking_versoes ───────────────────────────────────────────────────────────

class TestRankingVersoes(unittest.TestCase):

    def _versoes(self):
        return [
            {"nome": "V19",   "score": 0.65, "z_score": 0.8, "estabilidade": 0.7},
            {"nome": "V20.1", "score": 0.72, "z_score": 1.2, "estabilidade": 0.6},
            {"nome": "V20.4", "score": 0.72, "z_score": 1.5, "estabilidade": 0.8},
            {"nome": "V20.2", "score": 0.60, "z_score": 0.5, "estabilidade": 0.5},
        ]

    def test_ordenado_por_score_decrescente(self):
        r = ranking_versoes(self._versoes())
        scores = [v["score"] for v in r]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_desempate_por_z_score(self):
        # V20.4 e V20.1 têm mesmo score; V20.4 tem z maior → deve ser 1°
        r = ranking_versoes(self._versoes())
        self.assertEqual(r[0]["nome"], "V20.4")
        self.assertEqual(r[1]["nome"], "V20.1")

    def test_campo_posicao_adicionado(self):
        r = ranking_versoes(self._versoes())
        for i, v in enumerate(r, start=1):
            self.assertEqual(v["posicao"], i)

    def test_lista_vazia(self):
        r = ranking_versoes([])
        self.assertEqual(r, [])

    def test_nao_modifica_original_in_place(self):
        # A função faz list(versoes) internamente — não deve corromper a ordem original
        versoes = self._versoes()
        nomes_antes = [v["nome"] for v in versoes]
        ranking_versoes(versoes)
        # A lista original não deve ter "posicao" antes de chamar a função
        # (só checamos que não crashou e o original ficou íntegro em termos de nomes)
        self.assertEqual([v["nome"] for v in versoes], nomes_antes)

    def test_versao_sem_z_score_e_estabilidade(self):
        versoes = [
            {"nome": "A", "score": 0.8},
            {"nome": "B", "score": 0.6},
        ]
        r = ranking_versoes(versoes)
        self.assertEqual(r[0]["nome"], "A")


# ── relatorio_validacao ───────────────────────────────────────────────────────

class TestRelatorioValidacao(unittest.TestCase):

    def test_estrutura_completa(self):
        dados = _resultados(60, acertos=10.0)
        base = _resultados(60, acertos=9.0)
        versoes = [
            {"nome": "V19", "score": 0.60},
            {"nome": "V20", "score": 0.70},
        ]
        r = relatorio_validacao(dados, resultados_base=base, versoes=versoes, seed=0)
        for secao in ("vs_aleatorio", "vs_base", "estabilidade", "ganho", "ranking_versoes", "resumo"):
            self.assertIn(secao, r)

    def test_sem_base_vs_base_e_none(self):
        r = relatorio_validacao(_resultados(30), seed=0)
        self.assertIsNone(r["vs_base"])
        self.assertEqual(r["resumo"]["veredito_vs_base"], "N/A")

    def test_sem_versoes_ranking_vazio(self):
        r = relatorio_validacao(_resultados(30), seed=0)
        self.assertEqual(r["ranking_versoes"], [])
        self.assertEqual(r["resumo"]["versao_lider"], "N/A")

    def test_resumo_total_concursos(self):
        dados = _resultados(45)
        r = relatorio_validacao(dados, seed=0)
        self.assertEqual(r["resumo"]["total_concursos_avaliados"], 45)

    def test_dados_vazios_nao_crasha(self):
        try:
            relatorio_validacao([])
        except Exception as e:
            self.fail(f"relatorio_validacao([]) lançou exceção: {e}")


# ── gerar_relatorio_validacao ─────────────────────────────────────────────────

class TestGerarRelatorioValidacao(unittest.TestCase):

    def test_cria_arquivo_json_valido(self):
        dados = _resultados(40, acertos=10.0)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            caminho = f.name
        try:
            resultado = gerar_relatorio_validacao(dados, arquivo=caminho, seed=0)
            self.assertIn("resumo", resultado)
            with open(caminho, encoding="utf-8") as f:
                carregado = json.load(f)
            self.assertIn("resumo", carregado)
            self.assertEqual(
                resultado["resumo"]["total_concursos_avaliados"],
                carregado["resumo"]["total_concursos_avaliados"],
            )
        finally:
            os.unlink(caminho)

    def test_json_serializavel_sem_erros(self):
        dados = _resultados(20)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            caminho = f.name
        try:
            gerar_relatorio_validacao(dados, arquivo=caminho, seed=1)
            with open(caminho, encoding="utf-8") as f:
                conteudo = f.read()
            self.assertTrue(len(conteudo) > 0)
            json.loads(conteudo)  # não deve lançar exceção
        finally:
            os.unlink(caminho)


if __name__ == "__main__":
    unittest.main(verbosity=2)
