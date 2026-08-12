"""
lotofacil_pkg/tests/test_v22_otimizador.py
-------------------------------------------------------
Testes para v22_otimizador.py (Otimizador V22 por simulação), módulo
confirmado ativo -- `otimizar_pacote` é chamado de `ui.py` (linha
~4291). Não tinha nenhum teste antes.

Cobre a regressão de 2026-08-10 (achado do usuário): `_simular_pacote`
usava `TAMANHO_JOGO` (tamanho da APOSTA, configurável 15-20) pra gerar
o SORTEIO simulado, quando o sorteio real da Lotofácil é sempre 15
dezenas (`TAMANHO_SORTEIO`, fixo) -- mesma confusão conceitual já
corrigida uma vez em fechamento.py (garantia_minima(), 2026-08-03).
Com "Dezenas por jogo" != 15, isso invalidava as métricas de
pct_11_mais/pct_12_mais/pct_13_mais/media_melhor usadas pra escolher o
"melhor" pacote no otimizador.
"""
import os
import random as random_module
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import tempfile as _tempfile
os.environ.setdefault("ROBOLOTOFACIL_DADOS_DIR", _tempfile.mkdtemp(prefix="robolotofacil_testes_"))

from lotofacil_pkg.config import NUMEROS, TAMANHO_SORTEIO
from lotofacil_pkg.v22_otimizador import _simular_pacote, otimizar_pacote


class TestSimularPacote(unittest.TestCase):
    def test_sorteio_simulado_sempre_tem_tamanho_sorteio_dezenas(self):
        tamanhos_usados = []
        real_sample = random_module.sample

        def fake_sample(population, k):
            tamanhos_usados.append(k)
            return real_sample(population, k)

        # Jogos "estendidos" de 20 dezenas -- o sorteio simulado precisa
        # continuar do tamanho real (15), não do tamanho da aposta.
        jogos = [sorted(random_module.sample(NUMEROS, 20)) for _ in range(3)]
        with patch("lotofacil_pkg.v22_otimizador.random.sample", side_effect=fake_sample):
            _simular_pacote(jogos, n_simulacoes=10)

        self.assertTrue(tamanhos_usados)
        self.assertTrue(all(k == TAMANHO_SORTEIO for k in tamanhos_usados))

    def test_mudar_tamanho_jogo_na_config_nao_afeta_tamanho_do_sorteio_simulado(self):
        import lotofacil_pkg.config as config_module
        original = config_module.TAMANHO_JOGO
        tamanhos_usados = []
        real_sample = random_module.sample

        def fake_sample(population, k):
            tamanhos_usados.append(k)
            return real_sample(population, k)

        try:
            config_module.TAMANHO_JOGO = 18
            jogos = [sorted(random_module.sample(NUMEROS, 18)) for _ in range(3)]
            with patch("lotofacil_pkg.v22_otimizador.random.sample", side_effect=fake_sample):
                _simular_pacote(jogos, n_simulacoes=10)
        finally:
            config_module.TAMANHO_JOGO = original

        self.assertTrue(all(k == 15 for k in tamanhos_usados))

    def test_retorna_dict_com_chaves_esperadas(self):
        jogos = [sorted(random_module.sample(NUMEROS, 15)) for _ in range(10)]
        resultado = _simular_pacote(jogos, n_simulacoes=20)
        for chave in ("pct_11_mais", "pct_12_mais", "pct_13_mais",
                      "media_melhor", "max_melhor", "n_simulacoes"):
            self.assertIn(chave, resultado)

    def test_percentuais_dentro_de_0_100(self):
        jogos = [sorted(random_module.sample(NUMEROS, 15)) for _ in range(10)]
        resultado = _simular_pacote(jogos, n_simulacoes=30)
        for chave in ("pct_11_mais", "pct_12_mais", "pct_13_mais"):
            self.assertGreaterEqual(resultado[chave], 0.0)
            self.assertLessEqual(resultado[chave], 100.0)

    def test_pct_13_menor_ou_igual_pct_12_menor_ou_igual_pct_11(self):
        # 13+ é subconjunto de 12+ que é subconjunto de 11+.
        jogos = [sorted(random_module.sample(NUMEROS, 15)) for _ in range(15)]
        resultado = _simular_pacote(jogos, n_simulacoes=50)
        self.assertLessEqual(resultado["pct_13_mais"], resultado["pct_12_mais"])
        self.assertLessEqual(resultado["pct_12_mais"], resultado["pct_11_mais"])

    def test_pacote_vazio_nao_quebra(self):
        resultado = _simular_pacote([], n_simulacoes=10)
        self.assertEqual(resultado["max_melhor"], 0)


class TestOtimizarPacote(unittest.TestCase):
    def _fn_gerar_fixo(self, concursos):
        jogos = [sorted(random_module.sample(NUMEROS, 15)) for _ in range(15)]
        return jogos, {"analise": True}, {"pesos": True}

    def test_retorna_tupla_de_4_elementos(self):
        resultado = otimizar_pacote(
            concursos=[], fn_gerar=self._fn_gerar_fixo, max_tentativas=2, n_simulacoes=20
        )
        self.assertEqual(len(resultado), 4)

    def test_jogos_analise_pesos_do_vencedor_sao_propagados(self):
        jogos, analise, pesos, relatorio = otimizar_pacote(
            concursos=[], fn_gerar=self._fn_gerar_fixo, max_tentativas=2, n_simulacoes=20
        )
        self.assertEqual(len(jogos), 15)
        self.assertEqual(analise, {"analise": True})
        self.assertEqual(pesos, {"pesos": True})

    def test_relatorio_tem_estrutura_esperada(self):
        _, _, _, relatorio = otimizar_pacote(
            concursos=[], fn_gerar=self._fn_gerar_fixo, max_tentativas=3, n_simulacoes=20
        )
        for chave in ("tentativas_realizadas", "limiar_11", "limiar_media",
                      "melhor_score", "metricas", "historico", "limiar_atingido"):
            self.assertIn(chave, relatorio)
        self.assertLessEqual(relatorio["tentativas_realizadas"], 3)
        self.assertEqual(len(relatorio["historico"]), relatorio["tentativas_realizadas"])

    def test_fn_gerar_com_erro_e_ignorada_sem_quebrar(self):
        chamadas = {"n": 0}

        def fn_gerar_com_falha(concursos):
            chamadas["n"] += 1
            if chamadas["n"] == 1:
                raise RuntimeError("falha simulada")
            return self._fn_gerar_fixo(concursos)

        jogos, _, _, relatorio = otimizar_pacote(
            concursos=[], fn_gerar=fn_gerar_com_falha, max_tentativas=3, n_simulacoes=20
        )
        self.assertTrue(len(jogos) > 0)

    def test_fn_gerar_retorna_lista_vazia_em_todas_tentativas(self):
        jogos, analise, pesos, relatorio = otimizar_pacote(
            concursos=[], fn_gerar=lambda c: [], max_tentativas=2, n_simulacoes=10
        )
        self.assertEqual(jogos, [])
        self.assertIsNone(analise)
        self.assertIsNone(pesos)

    def test_fn_gerar_retorna_lista_sem_tupla_tambem_funciona(self):
        def fn_gerar_lista_pura(concursos):
            return [sorted(random_module.sample(NUMEROS, 15)) for _ in range(10)]

        jogos, analise, pesos, relatorio = otimizar_pacote(
            concursos=[], fn_gerar=fn_gerar_lista_pura, max_tentativas=2, n_simulacoes=20
        )
        self.assertEqual(len(jogos), 10)
        self.assertIsNone(analise)
        self.assertIsNone(pesos)


if __name__ == "__main__":
    unittest.main(verbosity=2)
