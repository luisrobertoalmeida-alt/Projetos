"""
lotofacil_pkg/v22_config.py
-----------------------------
Leitor de configuração central V22.
Carrega config_v22.yaml e expõe os valores para o restante do projeto.
Fallback automático para os defaults do config.py se o YAML não existir.

Uso:
    from .v22_config import cfg
    geracoes = cfg.genetico("geracoes", 35)
    limiar   = cfg.validacao("limiar_vitoria", 0.55)
"""

from __future__ import annotations
import os
import json
from pathlib import Path
from typing import Any

# Tenta importar yaml; se não tiver, usa fallback JSON
try:
    import yaml
    _YAML_OK = True
except ImportError:
    _YAML_OK = False

_CONFIG_FILE_YAML = Path(__file__).parent.parent / "config_v22.yaml"
_CONFIG_FILE_JSON = Path(__file__).parent.parent / "config_v22.json"


def _carregar_yaml(path: Path) -> dict:
    if not _YAML_OK:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _carregar_json(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _carregar() -> dict:
    if _CONFIG_FILE_YAML.exists():
        data = _carregar_yaml(_CONFIG_FILE_YAML)
        if data:
            return data
    if _CONFIG_FILE_JSON.exists():
        data = _carregar_json(_CONFIG_FILE_JSON)
        if data:
            return data
    return {}


class ConfigV22:
    """Acesso tipado à configuração central V22."""

    def __init__(self):
        self._data = _carregar()

    def reload(self) -> None:
        """Recarrega o arquivo de configuração em tempo de execução."""
        self._data = _carregar()

    def get(self, secao: str, chave: str, default: Any = None) -> Any:
        return self._data.get(secao, {}).get(chave, default)

    # ── Atalhos por seção ────────────────────────────────────

    def genetico(self, chave: str, default: Any = None) -> Any:
        return self.get("genetico", chave, default)

    def validacao(self, chave: str, default: Any = None) -> Any:
        return self.get("validacao", chave, default)

    def pipeline(self, chave: str, default: Any = None) -> Any:
        return self.get("pipeline", chave, default)

    def dashboard(self, chave: str, default: Any = None) -> Any:
        return self.get("dashboard", chave, default)

    def relatorio(self, chave: str, default: Any = None) -> Any:
        return self.get("relatorio", chave, default)

    def plugins(self, chave: str, default: Any = None) -> Any:
        return self.get("plugins", chave, default)

    def caminho(self, chave: str, default: Any = None) -> Any:
        valor = self.get("caminhos", chave, default)
        if isinstance(valor, str):
            return os.path.expanduser(valor)
        return valor

    # ── Propriedades convenientes ────────────────────────────

    @property
    def versao(self) -> str:
        return self._data.get("versao", "V22.0")

    @property
    def geracoes(self) -> int:
        return int(self.genetico("geracoes", 35))

    @property
    def populacao(self) -> int:
        return int(self.genetico("populacao", 27))

    @property
    def janela(self) -> int:
        return int(self.genetico("janela", 188))

    @property
    def jogos(self) -> int:
        return int(self.genetico("jogos", 20))

    @property
    def modo_turbo(self) -> bool:
        return bool(self.genetico("modo_turbo", False))

    @property
    def limiar_vitoria(self) -> float:
        return float(self.validacao("limiar_vitoria", 0.55))

    @property
    def plugins_ativos(self) -> list[str]:
        return self.plugins("ativos", [])

    def __repr__(self) -> str:
        return (
            f"ConfigV22(versao={self.versao}, "
            f"G={self.geracoes}, P={self.populacao}, "
            f"janela={self.janela}, jogos={self.jogos})"
        )


# Instância global — importar de qualquer módulo
cfg = ConfigV22()
