#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verifica el contraste AA de la demo Selene midiendo el PEOR PIXEL REAL bajo
cada texto, no un color plano teorico.

Que hace:
  1. Recompone en Python los mismos gradientes que pinta el CSS
     (.hero-card::after y .tr-card::after) sobre las fotos reales del repo.
  2. Recorre la banda donde cae cada texto y se queda con el pixel mas oscuro.
  3. Calcula el ratio WCAG contra --text (#2b2028) y --rose-text (#9c3a63).
  4. Comprueba ademas los pares de color planos de la paleta.

Uso:  python scripts/verifica-contraste.py
Sale con codigo 1 si algo baja de 4.5:1.
"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, 'assets', 'img')

TEXT = '#2b2028'
ROSE_TEXT = '#9c3a63'
MUTED = '#74656c'
WHITE = '#ffffff'
BLUSH = '#fdf6f9'
TINT = '#fbeef4'
ROSE_DEEP = '#b5567e'
AA = 4.5

fallos = []


# ----------------------------------------------------------------- WCAG ----
def _lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def lum_rgb(rgb):
    r, g, b = rgb
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def hex_rgb(hx):
    hx = hx.lstrip('#')
    return tuple(int(hx[i:i + 2], 16) for i in (0, 2, 4))


def ratio_rgb(a, b):
    la, lb = lum_rgb(a), lum_rgb(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


def ratio_hex(a, b):
    return ratio_rgb(hex_rgb(a), hex_rgb(b))


# ------------------------------------------------------------ gradientes ---
def _stop(stops, t):
    """Interpola una lista [(pos, (r,g,b,a)), ...] en t (0..1)."""
    if t <= stops[0][0]:
        return stops[0][1]
    if t >= stops[-1][0]:
        return stops[-1][1]
    for i in range(1, len(stops)):
        p0, c0 = stops[i - 1]
        p1, c1 = stops[i]
        if t <= p1:
            k = 0.0 if p1 == p0 else (t - p0) / (p1 - p0)
            return tuple(c0[j] + (c1[j] - c0[j]) * k for j in range(4))
    return stops[-1][1]


def _over(src, dst):
    """src (r,g,b,a con a 0..1) sobre dst (r,g,b opaco)."""
    a = src[3]
    return tuple(src[j] * a + dst[j] * (1 - a) for j in range(3))


def linear180(stops):
    """linear-gradient(180deg, ...) — t = y."""
    return lambda fx, fy: _stop(stops, fy)


def radial(rx, ry, cx, cy, stops):
    """radial-gradient(rx% ry% at cx% cy%, ...) en fracciones de caja."""
    def f(fx, fy):
        dx = (fx - cx) / rx
        dy = (fy - cy) / ry
        return _stop(stops, min(1.0, (dx * dx + dy * dy) ** 0.5))
    return f


def w(a):
    return (255.0, 255.0, 255.0, a)


def bl(a):
    r, g, b = hex_rgb(BLUSH)
    return (float(r), float(g), float(b), a)


# ---------------------------------------------------------------- checks ---
def peor_en(im, layers, box, step=3):
    W, H = im.size
    px = im.load()
    x0, y0, x1, y1 = box
    worst, wl = None, 10.0
    for y in range(int(y0 * H), int(y1 * H), step):
        for x in range(int(x0 * W), int(x1 * W), step):
            base = px[x, y]
            for layer in reversed(layers):
                base = _over(layer(x / W, y / H), base)
            l = lum_rgb(base)
            if l < wl:
                wl, worst = l, base
    return worst


def report(nombre, rgb, colores):
    global fallos
    print(f"  fondo peor pixel: rgb({int(rgb[0])},{int(rgb[1])},{int(rgb[2])})")
    for etiqueta, hx in colores:
        r = ratio_rgb(hex_rgb(hx), rgb)
        ok = r >= AA
        if not ok:
            fallos.append(f"{nombre} · {etiqueta}: {r:.2f}")
        print(f"    {etiqueta:<24} {hx}  {r:6.2f}:1  {'OK' if ok else 'FALLA'}")


# ---- 1. HERO ---------------------------------------------------------------
HERO_DESKTOP = [
    radial(0.76, 0.60, 0.50, 0.34, [(0.0, w(.92)), (0.58, w(.74)), (0.92, w(.32))]),
    linear180([(0.0, w(.86)), (0.32, w(.52)), (0.58, bl(.52)), (0.86, bl(.88)), (1.0, bl(.98))]),
]
HERO_MOBILE = [
    radial(1.04, 0.50, 0.50, 0.38, [(0.0, w(.92)), (0.62, w(.74)), (0.94, w(.38))]),
    linear180([(0.0, w(.86)), (0.28, w(.54)), (0.54, bl(.56)), (0.84, bl(.90)), (1.0, bl(.99))]),
]

# .tr-card::after (velo suave) + chip blanco .96 de .tr-cap.
# El chip cubre toda la banda del rotulo, asi que el peor caso es
# independiente de la foto: se comprueba tambien contra negro puro.
TR_SCRIM = [
    linear180([(0.0, w(.96)), (1.0, w(.96))]),          # chip .tr-cap
    linear180([(0.52, w(0.0)), (1.0, w(.26))]),         # .tr-card::after
]

print("\n=== 1 · HERO · texto sobre foto con velo claro ===")
print("\n[hero-spa.jpg · escritorio] banda del badge + h1 + subtitulo")
im = Image.open(os.path.join(IMG, 'hero-spa.jpg')).convert('RGB')
report('hero escritorio', peor_en(im, HERO_DESKTOP, (0.15, 0.17, 0.85, 0.58)),
       [('titular --text', TEXT), ('em/badge --rose-text', ROSE_TEXT)])

print("\n[hero-spa-900.jpg · movil] banda del badge + h1 + subtitulo")
im = Image.open(os.path.join(IMG, 'hero-spa-900.jpg')).convert('RGB')
report('hero movil', peor_en(im, HERO_MOBILE, (0.05, 0.13, 0.95, 0.62)),
       [('titular --text', TEXT), ('em/badge --rose-text', ROSE_TEXT)])

print("\n[hero-spa.jpg] zona de la stat-card (fondo blanco .88 encima del velo)")
im = Image.open(os.path.join(IMG, 'hero-spa.jpg')).convert('RGB')
peor_hero_bottom = peor_en(im, HERO_DESKTOP + [linear180([(0.0, w(.88)), (1.0, w(.88))])],
                           (0.02, 0.72, 0.35, 0.96))
report('stat-card', peor_hero_bottom, [('--text', TEXT), ('--muted', MUTED)])

# ---- 2. GALERIA ------------------------------------------------------------
print("\n=== 2 · GALERIA · rotulo en chip blanco sobre la foto ===")
GALERIA = ['tr-limpieza', 'tr-antiedad', 'tr-presoterapia', 'tr-masaje', 'tr-manicura', 'tr-pestanas']
for nombre in GALERIA:
    im = Image.open(os.path.join(IMG, nombre + '.jpg')).convert('RGB')
    print(f"\n[{nombre}.jpg] banda del titulo + precio")
    report(nombre, peor_en(im, TR_SCRIM, (0.06, 0.62, 0.94, 0.97)),
           [('titulo --text', TEXT), ('precio --rose-text', ROSE_TEXT)])

print("\n[peor caso absoluto] chip .96 sobre una foto negra")
negra = Image.new('RGB', (200, 200), (0, 0, 0))
report('chip sobre negro', peor_en(negra, TR_SCRIM, (0.0, 0.62, 1.0, 1.0)),
       [('titulo --text', TEXT), ('precio --rose-text', ROSE_TEXT)])

# ---- 3. ROTULO DE LAS TARJETAS DE SERVICIO --------------------------------
print("\n=== 3 · .sv-tag sobre foto (fondo #ffffff OPACO: independiente de la foto) ===")
print(f"    --rose-text sobre #ffffff        {ratio_hex(ROSE_TEXT, WHITE):6.2f}:1  "
      f"{'OK' if ratio_hex(ROSE_TEXT, WHITE) >= AA else 'FALLA'}")
if ratio_hex(ROSE_TEXT, WHITE) < AA:
    fallos.append('sv-tag')

# ---- 4. PARES PLANOS DE LA PALETA -----------------------------------------
print("\n=== 4 · Paleta plana ===")
PARES = [
    ('--text sobre #ffffff', TEXT, WHITE),
    ('--text sobre --blush', TEXT, BLUSH),
    ('--text sobre --tint', TEXT, TINT),
    ('--muted sobre #ffffff', MUTED, WHITE),
    ('--muted sobre --blush', MUTED, BLUSH),
    ('--muted sobre --tint', MUTED, TINT),
    ('--rose-text sobre #ffffff', ROSE_TEXT, WHITE),
    ('--rose-text sobre --blush', ROSE_TEXT, BLUSH),
    ('--rose-text sobre --tint', ROSE_TEXT, TINT),
    ('#ffffff sobre --rose-deep', WHITE, ROSE_DEEP),
]
for etiqueta, a, b in PARES:
    r = ratio_hex(a, b)
    ok = r >= AA
    if not ok:
        fallos.append(etiqueta)
    print(f"    {etiqueta:<32} {r:6.2f}:1  {'OK' if ok else 'FALLA'}")

# ---------------------------------------------------------------------------
print()
if fallos:
    print("RESULTADO: " + str(len(fallos)) + " comprobacion(es) por debajo de 4.5:1")
    for f in fallos:
        print("  - " + f)
    sys.exit(1)
print("RESULTADO: todo por encima de 4.5:1 (AA)")
