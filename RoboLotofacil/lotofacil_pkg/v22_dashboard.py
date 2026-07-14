"""
lotofacil_pkg/v22_dashboard.py
-------------------------------
Dashboard científico V22.
Agrega e estrutura dados históricos para exibição na UI.

Fornece:
  - evolução por versão
  - ranking histórico de configurações
  - estabilidade por janela
  - comparação entre modelos
  - tendência de acertos

Uso:
    from .v22_dashboard import DashboardV22
    dash = DashboardV22()
    dados = dash.carregar()
    print(dados["ranking_configs"])
"""

from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any

from .v22_config import cfg


class DashboardV22:
    """Agrega e fornece dados para o dashboard científico."""

    def __init__(self):
        self._base = os.path.expanduser("~/Documents/RoboLotofacilPro")
        self._pasta_relatorios = os.path.join(
            self._base, "exportacoes", "relatorios_v22"
        )
        self._arq_historico_modelos = os.path.join(
            self._base, "dados", "historico_modelos.json"
        )
        self._arq_desempenho = os.path.join(
            self._base, "dados", "lotofacil_desempenho_historico.json"
        )
        self._arq_conhecimento = os.path.join(
            self._base, "dados", "lotofacil_conhecimento_cientifico_v11.json"
        )

    # ── API pública ──────────────────────────────────────────

    def carregar(self) -> dict:
        """Retorna todos os dados do dashboard em um único dict."""
        return {
            "versao": cfg.versao,
            "config_ativa": self._config_ativa(),
            "evolucao_versoes": self._evolucao_versoes(),
            "ranking_configs": self._ranking_configs(),
            "ranking_modelos": self._ranking_modelos(),
            "tendencia_acertos": self._tendencia_acertos(),
            "estabilidade": self._estabilidade(),
            "historico_calibracoes": self._historico_calibracoes(),
        }

    def resumo_texto(self) -> str:
        """Retorna resumo compacto para exibição no log da UI."""
        dados = self.carregar()
        linhas = [
            "=" * 60,
            "📊 DASHBOARD CIENTÍFICO V22",
            "=" * 60,
        ]

        cfg_ativa = dados["config_ativa"]
        linhas.append(
            f"Config ativa: G={cfg_ativa.get('geracoes')} | "
            f"P={cfg_ativa.get('populacao')} | "
            f"Janela={cfg_ativa.get('janela')}"
        )

        tendencia = dados["tendencia_acertos"]
        if tendencia:
            linhas.append(
                f"Média do melhor (últimos {len(tendencia)} concursos): "
                f"{sum(tendencia)/len(tendencia):.2f}"
            )
            linhas.append(f"Melhor registrado: {max(tendencia)}")

        ranking = dados["ranking_modelos"]
        if ranking:
            linhas.append("\n🏆 Ranking de modelos:")
            for i, m in enumerate(ranking[:5], 1):
                linhas.append(
                    f"  {i}. {m['modelo']}: média={m['media']:.3f} | "
                    f"concursos={m['concursos']}"
                )

        cal_hist = dados["historico_calibracoes"]
        if cal_hist:
            linhas.append(f"\n📈 Calibrações registradas: {len(cal_hist)}")
            ultima = cal_hist[-1]
            linhas.append(
                f"  Última: taxa={ultima.get('taxa_vitoria', '?')}% | "
                f"{'✅' if ultima.get('aprovado') else '❌'}"
            )

        linhas.append("=" * 60)
        return "\n".join(linhas)

    # ── Dados internos ───────────────────────────────────────

    def _config_ativa(self) -> dict:
        return {
            "geracoes": cfg.geracoes,
            "populacao": cfg.populacao,
            "janela": cfg.janela,
            "jogos": cfg.jogos,
            "modo_turbo": cfg.modo_turbo,
            "limiar_vitoria": cfg.limiar_vitoria,
        }

    def _evolucao_versoes(self) -> list[dict]:
        """Lê histórico de relatórios V22 e extrai evolução por versão."""
        arq = os.path.join(self._pasta_relatorios, "historico_relatorios.json")
        if not os.path.exists(arq):
            return []
        try:
            with open(arq, "r", encoding="utf-8") as f:
                historico = json.load(f)
            versoes = []
            for r in historico:
                cal = r.get("resultados", {}).get("calibracao", {})
                versoes.append({
                    "data": r.get("gerado_em", "?")[:10],
                    "versao": r.get("versao", "?"),
                    "taxa_vitoria": cal.get("taxa_vitoria"),
                    "aprovado": cal.get("aprovado"),
                })
            return versoes[-cfg.dashboard("max_historico_versoes", 20):]
        except Exception:
            return []

    def _ranking_configs(self) -> list[dict]:
        """Ranking de configurações G/P do banco de conhecimento V11."""
        if not os.path.exists(self._arq_conhecimento):
            return []
        try:
            with open(self._arq_conhecimento, "r", encoding="utf-8") as f:
                conhecimento = json.load(f)
            configs = conhecimento.get("configuracoes", [])
            return sorted(configs, key=lambda x: x.get("score", 0), reverse=True)[:10]
        except Exception:
            return []

    def _ranking_modelos(self) -> list[dict]:
        """Ranking de modelos pelo histórico_modelos.json."""
        if not os.path.exists(self._arq_historico_modelos):
            return []
        try:
            with open(self._arq_historico_modelos, "r", encoding="utf-8") as f:
                historico = json.load(f)
            ranking = []
            for modelo, dados in historico.items():
                ranking.append({
                    "modelo": modelo,
                    "media": round(dados.get("media", 0), 4),
                    "concursos": dados.get("concursos", 0),
                })
            return sorted(ranking, key=lambda x: x["media"], reverse=True)
        except Exception:
            return []

    def _tendencia_acertos(self) -> list[float]:
        """Série histórica de melhor acerto por concurso."""
        if not os.path.exists(self._arq_desempenho):
            return []
        try:
            with open(self._arq_desempenho, "r", encoding="utf-8") as f:
                dados = json.load(f)
            registros = dados.get("registros", dados if isinstance(dados, list) else [])
            janela = cfg.dashboard("janela_tendencia", 30)
            serie = [r.get("melhor", r.get("melhor_acerto", 0)) for r in registros]
            return serie[-janela:]
        except Exception:
            return []

    def _estabilidade(self) -> dict:
        """Calcula estabilidade da série de acertos."""
        serie = self._tendencia_acertos()
        if len(serie) < 2:
            return {}
        media = sum(serie) / len(serie)
        variancia = sum((x - media) ** 2 for x in serie) / (len(serie) - 1)
        desvio = variancia ** 0.5
        return {
            "media": round(media, 3),
            "desvio": round(desvio, 3),
            "minimo": min(serie),
            "maximo": max(serie),
            "n_concursos": len(serie),
        }

    def _historico_calibracoes(self) -> list[dict]:
        """Lê histórico de relatórios e extrai dados de calibração."""
        arq = os.path.join(self._pasta_relatorios, "historico_relatorios.json")
        if not os.path.exists(arq):
            return []
        try:
            with open(arq, "r", encoding="utf-8") as f:
                historico = json.load(f)
            cals = []
            for r in historico:
                cal = r.get("resultados", {}).get("calibracao", {})
                if cal:
                    cals.append({
                        "data": r.get("gerado_em", "?")[:10],
                        "taxa_vitoria": cal.get("taxa_vitoria"),
                        "aprovado": cal.get("aprovado"),
                        "geracoes": r.get("configuracao", {}).get("geracoes"),
                    })
            return cals
        except Exception:
            return []
