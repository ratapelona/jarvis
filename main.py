"""
main.py — Punto de entrada de Reaxy$

Ejecutar: python main.py
"""
import sys
import codecs
if sys.stdout is not None and sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

import flet as ft
from ui.app import interfaz_principal

if __name__ == "__main__":
    ft.run(interfaz_principal, assets_dir="assets")
