"""
lotofacil_pkg/v22_relatorio.py
-------------------------------
Relatório científico automático V22.
Gerado ao final de cada pipeline ou execução de análise.

Formato de saída:
    exportacoes/relatorios_v22/relatorio_v22_YYYYMMDD_HHMMSS.txt
    exportacoes/relatorios_v22/relatorio_v22_YYYYMMDD_HHMMSS.json (opcional)

Uso:
    from .v22_relatorio import RelatorioV22
    rel = RelatorioV22(resultados_pipeline)
    rel.salvar()
    print(rel.resumo())
"""

from __future__ import annotations
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .v22_config import cfg


class RelatorioV22:
    """Gera e persiste relatório científico estruturado."""

    def __init__(self, resultados: dict[str, Any] | None = None):
        self.resultados = resultados or {}
        self.gerado_em = datetime.now()
        self._pasta = self._resolver_pasta()

    # ── API pública ──────────────────────────────────────────

    def salvar(self) -> str:
        """Salva o relatório e retorna o caminho do arquivo."""
        os.makedirs(self._pasta, exist_ok=True)
        ts = self.gerado_em.strftime("%Y%m%d_%H%M%S")

        # TXT sempre
        caminho_txt = os.path.join(self._pasta, f"relatorio_v22_{ts}.txt")
        with open(caminho_txt, "w", encoding="utf-8") as f:
            f.write(self._gerar_txt())

        # JSON se configurado
        if cfg.relatorio("formato", "txt") in ("json", "ambos"):
            caminho_json = os.path.join(self._pasta, f"relatorio_v22_{ts}.json")
            with open(caminho_json, "w", encoding="utf-8") as f:
                json.dump(self._gerar_json(), f, indent=2, ensure_ascii=False)

        # Histórico acumulado
        if cfg.relatorio("salvar_historico", True):
            self._atualizar_historico()

        return caminho_txt

    def resumo(self) -> str:
        """Retorna resumo compacto para exibição na UI."""
        linhas = []
        cal = self.resultados.get("calibracao", {})
        wf = self.resultados.get("walkforward", {})

        if cal:
            taxa = (cal.get("resumo_robo") or {}).get("pct_pacotes_11_mais", "?")
            linhas.append(f"Calibração: {taxa}% de pacotes com 11+")
        if wf:
            veredito = (wf.get("resumo") or {}).get("veredito", "?")
            linhas.append(f"Walk-Forward: {veredito}")

        return " | ".join(linhas) if linhas else "Sem dados suficientes"

    # ── Geração de conteúdo ──────────────────────────────────

    def _gerar_txt(self) -> str:
        ts = self.gerado_em.strftime("%d/%m/%Y %H:%M:%S")
        linhas = [
            "=" * 70,
            f"RELATÓRIO CIENTÍFICO V22 — RoboLotofacilPro",
            f"Gerado em: {ts}",
            f"Versão: {cfg.versao}",
            "=" * 70,
            "",
            "── CONFIGURAÇÃO ATIVA ──────────────────────────────────────────",
            f"G={cfg.geracoes} | P={cfg.populacao} | Janela={cfg.janela} | Jogos={cfg.jogos}",
            f"Modo Turbo: {'ligado' if cfg.modo_turbo else 'desligado'}",
            f"Limiar de aprovação: {cfg.limiar_vitoria*100:.0f}%",
            "",
        ]

        # Calibração (schema real: backtest.calibrar_robo_vs_aleatorio())
        cal = self.resultados.get("calibracao", {})
        if cal:
            robo = cal.get("resumo_robo") or {}
            estat = cal.get("estatistica") or {}
            linhas += [
                "── CALIBRAÇÃO VS ALEATÓRIO ─────────────────────────────────────",
                f"Vitórias por score: robô={cal.get('robo_venceu_score', '?')} | "
                f"aleatório={cal.get('aleatorio_venceu_score', '?')} | "
                f"empates={cal.get('empates_score', '?')}",
                f"11+%: {robo.get('pct_pacotes_11_mais', '?')}%",
                f"12+%: {robo.get('pct_pacotes_12_mais', '?')}%",
                f"p-valor: {estat.get('p_valor', '?')}",
                f"Cohen d: {estat.get('cohen_d', '?')} ({estat.get('interpretacao', '?')})",
                f"IC 95% vitórias: {estat.get('ic95_vitoria', '?')}",
                f"Status: {'✅ APROVADO' if self._calibracao_aprovada(cal) else '❌ REPROVADO'}",
                "",
            ]

        # Walk-Forward (schema real: backtest.relatorio_walkforward())
        wf = self.resultados.get("walkforward", {})
        if wf:
            wf_dados = wf.get("walkforward") or {}
            ovf = wf.get("overfitting") or {}
            resumo_wf = wf.get("resumo") or {}
            linhas += [
                "── WALK-FORWARD ────────────────────────────────────────────────",
                f"Janelas avaliadas: {wf_dados.get('n_janelas', '?')}",
                f"Média de acertos: {wf_dados.get('media_geral', '?')}",
                f"Desvio: {wf_dados.get('desvio_geral', '?')}",
                f"Score robustez: {wf.get('robustez', '?')}",
                f"Overfitting: {ovf.get('severidade', '?')} (razão={ovf.get('razao', '?')})",
                f"Veredito: {resumo_wf.get('veredito', '?')}",
                "",
            ]

        # Backtest V11 (schema real: backtest.executar_backtest_cientifico_massivo())
        v11 = self.resultados.get("backtest_v11", {})
        if v11:
            rec = v11.get("recomendacao") or {}
            linhas += [
                "── BACKTEST CIENTÍFICO V11 ──────────────────────────────────────",
                f"Campeão: {rec.get('estrategia_base', '?')} (G={rec.get('geracoes', '?')} P={rec.get('pop_size', '?')})",
                f"Score: {rec.get('score_configuracao', '?')}",
                f"Modelo: {rec.get('modelo_campeao', '?')}",
                "",
            ]

        # Conclusão
        linhas += [
            "── CONCLUSÃO ───────────────────────────────────────────────────",
            self._conclusao(),
            "",
            "Observação: relatório mede desempenho histórico. Não é previsão.",
            "=" * 70,
        ]

        return "\n".join(linhas)

    def _gerar_json(self) -> dict:
        return {
            "versao": cfg.versao,
            "gerado_em": self.gerado_em.isoformat(),
            "configuracao": {
                "geracoes": cfg.geracoes,
                "populacao": cfg.populacao,
                "janela": cfg.janela,
                "jogos": cfg.jogos,
                "modo_turbo": cfg.modo_turbo,
                "limiar_vitoria": cfg.limiar_vitoria,
            },
            "resultados": self.resultados,
            "conclusao": self._conclusao(),
        }

    @staticmethod
    def _calibracao_aprovada(cal: dict) -> bool | None:
        """calibrar_robo_vs_aleatorio() não devolve um booleano 'aprovado'
        pronto -- deriva daqui: robô precisa ter vencido mais pacotes por
        score que o aleatório E, quando o teste estatístico rodou, ele
        precisa ter dado significativo (evita aprovar por ruído amostral)."""
        if not cal:
            return None
        venceu = cal.get("robo_venceu_score", 0) > cal.get("aleatorio_venceu_score", 0)
        estat = cal.get("estatistica") or {}
        if "significativo" in estat:
            return venceu and bool(estat.get("significativo"))
        return venceu

    def _conclusao(self) -> str:
        cal = self.resultados.get("calibracao", {})
        wf = self.resultados.get("walkforward", {})

        aprovado_cal = self._calibracao_aprovada(cal)
        # Vereditos do Walk-Forward (v20_8_walkforward): "ROBUSTO" (melhor
        # caso) e "ACEITAVEL" contam como aprovados; só "INSTAVEL" reprova.
        veredito_wf = ((wf.get("resumo") or {}).get("veredito", ""))
        aprovado_wf = veredito_wf in ("ROBUSTO", "ACEITAVEL")

        if aprovado_cal is True and aprovado_wf:
            return "✅ Configuração validada — aprovada na calibração e no Walk-Forward."
        elif aprovado_cal is False:
            return "❌ Configuração reprovada na calibração — manter configuração anterior."
        elif aprovado_cal is None:
            return "⚠️ Dados insuficientes — rode calibração e Walk-Forward para validar."
        else:
            return "⚠️ Calibração aprovada mas Walk-Forward pendente."

    def _atualizar_historico(self) -> None:
        """Acumula relatórios em um histórico JSON."""
        arq = os.path.join(self._pasta, "historico_relatorios.json")
        historico = []
        if os.path.exists(arq):
            try:
                with open(arq, "r", encoding="utf-8") as f:
                    historico = json.load(f)
            except Exception:
                historico = []

        historico.append(self._gerar_json())

        # Mantém só os últimos 50
        historico = historico[-50:]

        with open(arq, "w", encoding="utf-8") as f:
            json.dump(historico, f, indent=2, ensure_ascii=False)

    def _resolver_pasta(self) -> str:
        base = os.path.expanduser("~/Documents/RoboLotofacilPro")
        return os.path.join(base, "exportacoes", "relatorios_v22")
