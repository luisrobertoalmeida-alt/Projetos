"""
lotofacil_pkg/v22_plugins.py
------------------------------
Sistema de plugins V22.
Carrega módulos da pasta plugins/ sem alterar o núcleo.

Cada plugin deve exportar:
    NOME: str           — identificador único
    DESCRICAO: str      — descrição curta
    aplicar(jogos, historico, config) -> list  — transforma/filtra o pacote

Uso:
    from .v22_plugins import PluginManager
    pm = PluginManager()
    jogos = pm.aplicar_todos(jogos, historico)
"""

from __future__ import annotations
import importlib.util
import os
from pathlib import Path
from typing import Callable, Any

_PASTA_PLUGINS = Path(__file__).parent.parent / "plugins"


class Plugin:
    def __init__(self, nome: str, descricao: str, fn: Callable):
        self.nome = nome
        self.descricao = descricao
        self._fn = fn

    def aplicar(self, jogos: list, historico: list, config: dict) -> list:
        try:
            return self._fn(jogos, historico, config) or jogos
        except Exception as e:
            print(f"⚠️ Plugin '{self.nome}' falhou: {e}")
            return jogos

    def __repr__(self) -> str:
        return f"Plugin({self.nome})"


class PluginManager:
    """Gerencia carregamento e execução de plugins."""

    def __init__(self, ativos: list[str] | None = None):
        self._plugins: dict[str, Plugin] = {}
        self._ativos = ativos or []
        self._carregar_todos()

    def _carregar_todos(self) -> None:
        if not _PASTA_PLUGINS.exists():
            return
        for arquivo in sorted(_PASTA_PLUGINS.glob("*.py")):
            if arquivo.name.startswith("_"):
                continue
            nome = arquivo.stem
            if self._ativos and nome not in self._ativos:
                continue
            plugin = self._carregar(arquivo)
            if plugin:
                self._plugins[nome] = plugin

    def _carregar(self, path: Path) -> Plugin | None:
        try:
            spec = importlib.util.spec_from_file_location(path.stem, path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            nome = getattr(mod, "NOME", path.stem)
            descricao = getattr(mod, "DESCRICAO", "")
            fn = getattr(mod, "aplicar", None)
            if fn is None:
                return None
            return Plugin(nome, descricao, fn)
        except Exception as e:
            print(f"⚠️ Erro ao carregar plugin '{path.name}': {e}")
            return None

    def aplicar_todos(self, jogos: list, historico: list, config: dict | None = None) -> list:
        """Aplica todos os plugins ativos em sequência."""
        config = config or {}
        for plugin in self._plugins.values():
            jogos = plugin.aplicar(jogos, historico, config)
        return jogos

    def listar(self) -> list[dict]:
        return [{"nome": p.nome, "descricao": p.descricao} for p in self._plugins.values()]

    def __len__(self) -> int:
        return len(self._plugins)

    def __repr__(self) -> str:
        return f"PluginManager({list(self._plugins.keys())})"
