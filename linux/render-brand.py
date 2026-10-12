#!/usr/bin/env python3
"""Render canonical SVG branding at high resolution, then generate Windows icon frames."""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PIL import Image
assets = Path(__file__).resolve().parent.parent / 'assets'
for name, size in [('Culvert-mark', 512), ('Culvert', 1024)]:
    renderer = QSvgRenderer(str(assets / (name + '.svg')))
    if not renderer.isValid(): raise SystemExit('Invalid brand SVG: ' + name)
    bitmap = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    bitmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(bitmap); renderer.render(painter); painter.end()
    if not bitmap.save(str(assets / (name + '.png'))): raise SystemExit('Cannot save logo')
with Image.open(assets / 'Culvert.png') as source:
    source.save(assets / 'Culvert.ico', sizes=[(n,n) for n in (16,20,24,32,40,48,64,128,256)])
print('Rendered original Culvert mascot, 1024px icon and Windows icon frames.')
