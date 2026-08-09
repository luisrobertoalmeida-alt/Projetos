"""
tests/test_v21_5_auto_poda_full.py
------------------------------------
Testes para v21_5_auto_poda_full: transição de estados da poda 4-estados.

Cobre a correção de 2026-07-21 (ver ARQUITETURA.md): os limiares eram
absolutos (observação<9.10, suspenso<8.90, recuperação>=9.20) numa escala
onde a média real de qualquer modelo em Lotofácil gira em torno de 9.0
(empatada com o acaso) — isso fazia TODO modelo ratchetar
ATIVO→OBSERVAÇÃO→QUARENTENA→SUSPENSO com passos suficientes, sem nunca
recuperar. Corrigido comparando cada modelo à média do próprio grupo
(dos 7 modelos) naquele mesmo passo, não a um valor absoluto fixo.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from lotofacil_pkg.v21_5_auto_poda_full import (
    _transicao,
    _estado_inicial,
    avaliar_estados_modelos,
    relatorio_poda_full,
    ESTADO_ATIVO,
    ESTADO_OBSERVACAO,
    ESTADO_QUARENTENA,
    ESTADO_SUSPENSO,
    DELTA_OBSERVACAO,
    DELTA_RECUPERACAO,
)
import lotofacil_pkg.v21_5_auto_poda_full as poda_full


class TestTransicaoRelativaAoGrupo(unittest.TestCase):
    """Regressão do bug: modelo na média do grupo não pode degradar para sempre."""

    def test_modelo_empatado_com_grupo_fica_ativo(self):
        # Delta = 0 (média do passo == média do grupo) em toda rodada real
        # de Lotofácil (~9.0). Antes da correção, 9.0 < LIMIAR_OBSERVACAO
        # (9.10) fazia isso contar como "abaixo" sempre; agora delta=0 cai
        # na zona neutra e o modelo nunca degrada.
        info = _estado_inicial()
        for _ in range(20):
            info = _transicao(info, media_recente=9.0, media_grupo=9.0)
        self.assertEqual(info["estado"], ESTADO_ATIVO)

    def test_modelo_consistentemente_pior_que_grupo_degrada(self):
        info = _estado_inicial()
        # Delta bem abaixo do limiar de observação em toda rodada
        for _ in range(poda_full.RODADAS_DEGRADAR):
            info = _transicao(info, media_recente=8.8, media_grupo=9.0)
        self.assertNotEqual(info["estado"], ESTADO_ATIVO)

    def test_modelo_consistentemente_melhor_que_grupo_nao_degrada(self):
        info = _estado_inicial()
        for _ in range(10):
            info = _transicao(info, media_recente=9.2, media_grupo=9.0)
        self.assertEqual(info["estado"], ESTADO_ATIVO)

    def test_recuperacao_apos_degradar(self):
        info = _estado_inicial()
        # Degrada até OBSERVAÇÃO (RODADAS_DEGRADAR rodadas seguidas abaixo)
        for _ in range(poda_full.RODADAS_DEGRADAR):
            info = _transicao(info, media_recente=8.8, media_grupo=9.0)
        self.assertEqual(info["estado"], ESTADO_OBSERVACAO)
        # Recupera com desempenho acima do grupo por RODADAS_RECUPERAR rodadas seguidas
        for _ in range(poda_full.RODADAS_RECUPERAR):
            info = _transicao(info, media_recente=9.1, media_grupo=9.0)
        self.assertEqual(info["estado"], ESTADO_ATIVO)

    def test_delta_dentro_da_zona_neutra_nao_muda_contadores(self):
        info = _estado_inicial()
        # delta pequeno, entre DELTA_OBSERVACAO e DELTA_RECUPERACAO
        delta_neutro = (DELTA_OBSERVACAO + DELTA_RECUPERACAO) / 2
        info = _transicao(info, media_recente=9.0 + delta_neutro, media_grupo=9.0)
        self.assertEqual(info["rodadas_abaixo"], 0)
        self.assertEqual(info["rodadas_acima"], 0)
        self.assertEqual(info["estado"], ESTADO_ATIVO)

    def test_duas_rodadas_seguidas_nao_bastam_mais_para_degradar(self):
        """
        Regressão do achado do usuário (2026-08-09, log de "Eventos" com
        dezenas de transições em poucos segundos): RODADAS_DEGRADAR subiu
        de 2 para 3 justamente pra que ruído de curto prazo (2 rodadas
        abaixo por acaso) não seja mais suficiente sozinho pra degradar.
        """
        self.assertGreater(poda_full.RODADAS_DEGRADAR, 2)
        info = _estado_inicial()
        for _ in range(2):
            info = _transicao(info, media_recente=8.8, media_grupo=9.0)
        self.assertEqual(info["estado"], ESTADO_ATIVO)


class TestAvaliarEstadosModelos(unittest.TestCase):
    """Testa a função pública, isolando o arquivo de estados em disco."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="robolotofacil_poda_full_")
        self._arq_original = poda_full._ARQ_ESTADOS
        poda_full._ARQ_ESTADOS = Path(self._tmpdir) / "estados_modelos_v21.json"

    def tearDown(self):
        poda_full._ARQ_ESTADOS = self._arq_original

    def test_media_grupo_calculada_corretamente(self):
        # 7 modelos todos empatados na própria média do grupo devem
        # permanecer ATIVOS após várias rodadas idênticas.
        acertos = {"a": 9.0, "b": 9.0, "c": 9.0, "d": 9.0,
                   "e": 9.0, "f": 9.0, "g": 9.0}
        for _ in range(15):
            resultado = avaliar_estados_modelos(acertos)
        for info in resultado.values():
            self.assertEqual(info["estado"], ESTADO_ATIVO)

    def test_modelo_pior_que_os_outros_seis_degrada_sozinho(self):
        # 6 modelos empatados em 9.0, 1 modelo (fraco) sistematicamente
        # abaixo — só o fraco deve degradar, os outros seis não.
        for _ in range(5):
            acertos = {"bom1": 9.0, "bom2": 9.0, "bom3": 9.0,
                       "bom4": 9.0, "bom5": 9.0, "bom6": 9.0,
                       "fraco": 8.7}
            resultado = avaliar_estados_modelos(acertos)
        for nome, info in resultado.items():
            if nome == "fraco":
                self.assertNotEqual(info["estado"], ESTADO_ATIVO)
            else:
                self.assertEqual(info["estado"], ESTADO_ATIVO)

    def test_relatorio_poda_full_tem_estrutura_esperada(self):
        avaliar_estados_modelos({"x": 9.0, "y": 9.0})
        rel = relatorio_poda_full()
        self.assertIn("modelos", rel)
        self.assertIn("contagem", rel)
        self.assertIn("limiares", rel)
        self.assertIn("observacao", rel["limiares"])
        self.assertIn("suspenso", rel["limiares"])
        self.assertIn("recuperacao", rel["limiares"])
        self.assertNotIn("quarentena", rel["limiares"])


if __name__ == "__main__":
    unittest.main()
