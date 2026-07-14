"""
lotofacil_pkg/v22_pipeline.py
------------------------------
Pipeline automático V22.
Executa todas as etapas de análise em sequência com um clique.

Etapas configuráveis via config_v22.yaml:
    atualizar_historico → aprendizado_continuo → calibracao →
    walkforward → backtest_v11 → relatorio_cientifico → gerar_jogos

Uso na UI:
    from .v22_pipeline import PipelineV22
    pipeline = PipelineV22(app=self, status_cb=self.log_async)
    pipeline.executar()
"""

from __future__ import annotations
import threading
import time
from threading import Event
from datetime import datetime
from typing import Callable, Any

from .v22_config import cfg
from .v22_relatorio import RelatorioV22


# Etapas disponíveis — mapeadas para métodos da UI
ETAPAS_DISPONIVEIS = [
    "atualizar_historico",
    "aprendizado_continuo",
    "calibracao",
    "walkforward",
    "backtest_v11",
    "relatorio_cientifico",
    "gerar_jogos",
]

# Mapeamento: nome da etapa → método real na UI
_MAPA_METODOS_UI = {
    "atualizar_historico":  "iniciar_atualizar_resultados",
    "aprendizado_continuo": "iniciar_aprendizado_continuo",
    "calibracao":           "iniciar_calibracao_vs_aleatorio",
    "walkforward":          "iniciar_walkforward",
    "backtest_v11":         "iniciar_backtest_cientifico_v11",
    "gerar_jogos":          "iniciar_gerar_jogos",
}

# Flags de conclusão — atributos reais da UI monitorados para sincronização
# O pipeline aguarda esses flags ficarem False (etapa concluída) antes de prosseguir
_FLAGS_CONCLUSAO = {
    "atualizar_historico":  "_atualizando",
    "aprendizado_continuo": "aprendizado_continuo_ativo",
    "calibracao":           "laboratorio_historico_ativo",  # calibração usa o mesmo padrão
    "walkforward":          "_walkforward_ativo",
    "backtest_v11":         "backtest_cientifico_ativo",
    "gerar_jogos":          "_geracao_ativa",
}

# Timeout máximo por etapa em segundos
_TIMEOUTS = {
    "atualizar_historico":  60,
    "aprendizado_continuo": 300,
    "calibracao":           600,
    "walkforward":          600,
    "backtest_v11":         900,
    "gerar_jogos":          120,
    "relatorio_cientifico": 30,
}


class PipelineV22:
    """
    Executa o pipeline completo de análise e geração.
    Integra com a UI via callbacks de status e log.
    """

    def __init__(
        self,
        app: Any = None,
        status_cb: Callable[[str], None] | None = None,
        log_cb: Callable[[str], None] | None = None,
        etapas: list[str] | None = None,
    ):
        self.app = app
        self._status_cb = status_cb or (lambda m: None)
        self._log_cb = log_cb or (lambda m: print(m))
        self.etapas = etapas or cfg.pipeline("etapas", ETAPAS_DISPONIVEIS)
        self._ativo = False
        self._resultados: dict[str, Any] = {}
        self._inicio: float = 0.0

    # ── API pública ──────────────────────────────────────────

    def executar(self, em_thread: bool = True) -> None:
        """Dispara o pipeline (em thread separada por padrão)."""
        if self._ativo:
            self._log("⚠️ Pipeline já está em execução.")
            return
        if em_thread:
            th = threading.Thread(target=self._run, daemon=True)
            th.start()
        else:
            self._run()

    def cancelar(self) -> None:
        self._ativo = False

    @property
    def resultados(self) -> dict:
        return dict(self._resultados)

    # ── Execução interna ─────────────────────────────────────

    def _run(self) -> None:
        self._ativo = True
        self._inicio = time.time()
        self._resultados = {}

        self._log("=" * 70)
        self._log(f"🚀 PIPELINE V22 INICIADO — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        self._log(f"Etapas: {' → '.join(self.etapas)}")
        self._log("=" * 70)

        try:
            for etapa in self.etapas:
                if not self._ativo:
                    self._log("⚠️ Pipeline cancelado.")
                    break
                self._executar_etapa(etapa)
        except Exception as e:
            self._log(f"❌ Erro no pipeline: {e}")
        finally:
            self._ativo = False
            elapsed = time.time() - self._inicio
            self._log("=" * 70)
            self._log(f"✅ Pipeline concluído em {elapsed:.1f}s")
            self._gerar_relatorio_final()

    def _executar_etapa(self, etapa: str) -> None:
        self._log(f"\n▶ {etapa.upper().replace('_', ' ')}")
        t0 = time.time()

        try:
            # 1. Verifica se há implementação local
            metodo = getattr(self, f"_etapa_{etapa}", None)
            if metodo:
                resultado = metodo()
                self._resultados[etapa] = resultado
            elif self.app:
                # 2. Busca pelo mapeamento explícito primeiro
                nome_ui = _MAPA_METODOS_UI.get(etapa)
                metodo_ui = getattr(self.app, nome_ui, None) if nome_ui else None
                # 3. Fallback: tenta iniciar_{etapa}
                if metodo_ui is None:
                    metodo_ui = getattr(self.app, f"iniciar_{etapa}", None)
                if metodo_ui:
                    self._log(f"  → {nome_ui or f'iniciar_{etapa}'}")
                    metodo_ui()
                    # 4. Aguarda a etapa terminar antes de prosseguir
                    self._aguardar_conclusao(etapa, t0)
                    self._resultados[etapa] = {"delegado": True}
                else:
                    self._log(f"  ⚠️ Etapa '{etapa}' não implementada — pulando")
                    self._resultados[etapa] = {"pulado": True}
            else:
                self._log(f"  ⚠️ Sem app vinculado para '{etapa}' — pulando")

        except Exception as e:
            self._log(f"  ❌ Erro em '{etapa}': {e}")
            self._resultados[etapa] = {"erro": str(e)}

        elapsed = time.time() - t0
        self._log(f"  ✓ Concluído em {elapsed:.1f}s")

    def _aguardar_conclusao(self, etapa: str, t0: float) -> None:
        """Aguarda a etapa da UI terminar monitorando o flag de atividade."""
        flag = _FLAGS_CONCLUSAO.get(etapa)
        timeout = _TIMEOUTS.get(etapa, 300)

        if not flag or not self.app:
            # Sem flag para monitorar — aguarda 2s mínimo para a thread iniciar
            time.sleep(2)
            return

        # Aguarda o flag ficar True (etapa iniciou)
        inicio_espera = time.time()
        while time.time() - inicio_espera < 5:
            if getattr(self.app, flag, False):
                break
            time.sleep(0.3)

        # Aguarda o flag ficar False (etapa concluiu)
        self._log(f"  ⏳ Aguardando conclusão...")
        while time.time() - t0 < timeout:
            if not self._ativo:
                return
            ativo = getattr(self.app, flag, False)
            if not ativo:
                break
            elapsed = time.time() - t0
            if int(elapsed) % 30 == 0 and elapsed > 1:
                self._log(f"  ⏳ {int(elapsed)}s...")
            time.sleep(1)
        else:
            self._log(f"  ⚠️ Timeout de {timeout}s atingido para '{etapa}'")

    # ── Etapas implementadas diretamente ────────────────────

    def _etapa_relatorio_cientifico(self) -> dict:
        """Gera relatório científico com os resultados acumulados."""
        rel = RelatorioV22(self._resultados)
        caminho = rel.salvar()
        self._log(f"  📄 Relatório salvo em: {caminho}")
        return {"caminho": caminho}

    # ── Helpers ──────────────────────────────────────────────

    def _log(self, msg: str) -> None:
        self._log_cb(msg)

    def _gerar_relatorio_final(self) -> None:
        if not cfg.relatorio("gerar_automatico", True):
            return
        try:
            rel = RelatorioV22(self._resultados)
            rel.salvar()
        except Exception:
            pass
