"""
main.py — RoboLotofacilPro V16
================================
Execute este arquivo para abrir o robô:
    python main.py

Requisitos:
    pip install pandas requests
"""
import sys
import os

# Garante que o pacote seja encontrado
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lotofacil_pkg.ui import RoboLotofacilUltraApp, main

if __name__ == "__main__":
    main()
