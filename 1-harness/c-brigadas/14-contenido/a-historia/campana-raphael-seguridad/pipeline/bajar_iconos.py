# -*- coding: utf-8 -*-
"""Baja los personajes e iconos de OpenMoji (CC BY-SA 4.0, https://openmoji.org) que usan las escenas.
Uso: python3 bajar_iconos.py [carpeta]   (por defecto ./iconos junto a este archivo)"""
import os, sys, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from escenas import codigos
URL = "https://raw.githubusercontent.com/hfg-gmuend/openmoji/master/color/618x618/{}.png"
dst = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "iconos")
os.makedirs(dst, exist_ok=True)
for c in codigos():
    p = os.path.join(dst, c + ".png")
    if not os.path.exists(p):
        urllib.request.urlretrieve(URL.format(c), p); print("bajado", c)
print("listo:", len(codigos()), "iconos en", dst)
