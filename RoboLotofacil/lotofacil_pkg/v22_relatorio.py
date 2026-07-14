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
            taxa = cal.get("taxa_vitoria", "?")
            linhas.append(f"Calibração: {taxa}% de vitória")
        if wf:
            veredito = wf.get("veredito", "?")
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

        # Calibração
        cal = self.resultados.get("calibracao", {})
        if cal:
            linhas += [
                "── CALIBRAÇÃO VS ALEATÓRIO ─────────────────────────────────────",
                f"Vitórias: {cal.get('vitorias_robo', '?')}/{cal.get('passos', '?')}",
                f"Taxa: {cal.get('taxa_vitoria', '?')}%",
                f"11+%: {cal.get('pct_11_mais', '?')}%",
                f"12+%: {cal.get('pct_12_mais', '?')}%",
                f"p-valor: {cal.get('p_valor', '?')}",
                f"Cohen d: {cal.get('cohen_d', '?')} ({cal.get('interpretacao', '?')})",
                f"IC 95% vitórias: {cal.get('ic95', '?')}",
                f"Status: {'✅ APROVADO' if cal.get('aprovado') else '❌ REPROVADO'}",
                "",
            ]

        # Walk-Forward
        wf = self.resultados.get("walkforward", {})
        if wf:
            linhas += [
                "── WALK-FORWARD ────────────────────────────────────────────────",
                f"Janelas avaliadas: {wf.get('n_janelas', '?')}",
                f"Média de acertos: {wf.get('media_acertos', '?')}",
                f"Desvio: {wf.get('desvio', '?')}",
                f"Score robustez: {wf.get('score_robustez', '?')}",
                f"Overfitting: {wf.get('severidade_overfitting', '?')} (razão={wf.get('razao', '?')})",
                f"Veredito: {wf.get('veredito', '?')}",
                "",
            ]

        # Backtest V11
        v11 = self.resultados.get("backtest_v11", {})
        if v11:
            linhas += [
                "── BACKTEST CIENTÍFICO V11 ──────────────────────────────────────",
                f"Campeão: {v11.get('config_campea', '?')}",
                f"Score: {v11.get('score_campea', '?')}",
                f"Modelo: {v11.get('modelo_campea', '?')}",
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

    def _conclusao(self) -> str:
        cal = self.resultados.get("calibracao", {})
        wf = self.resultados.get("walkforward", {})

        aprovado_cal = cal.get("aprovado", None)
        aprovado_wf = wf.get("veredito", "") == "ACEITAVEL"

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
