"""
setup.py — RoboLotofacilPro V13
================================
Instalação local:
  pip install -e .

Dependências obrigatórias: pandas, requests
Dependências opcionais:    reportlab (exportação PDF)
"""
from setuptools import setup, find_packages

setup(
    name="lotofacil-pkg",
    version="13.0.0",
    description="RoboLotofacilPro — gerador inteligente de apostas com ensemble multi-IA",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "pandas>=1.3",
        "requests>=2.28",
    ],
    extras_require={
        "pdf": ["reportlab>=3.6"],
        "dev": ["pytest>=7.0"],
    },
    entry_points={
        "console_scripts": [
            "lotofacil=lotofacil_pkg.ui:main",
        ],
    },
)
