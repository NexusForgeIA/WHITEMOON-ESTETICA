#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verifica el contraste AA de la demo Selene (negro + dorado + rosa) midiendo
el PEOR PIXEL REAL bajo cada texto, no un color plano teorico.

Que hace:
  1. Recompone en Python los mismos gradientes OSCUROS que pinta el CSS
     (.hero-card::after y .tr-card::after) sobre las fotos reales del repo.
  2. Recorre la banda donde cae cada texto y se queda con el pixel mas CLARO
     (el texto es claro: el peor fondo es el mas luminoso).
  3. Calcula el ratio WCAG contra --text, --rose-text, --gold y --muted.
  4. Comprueba ademas los pares de color planos de la paleta.

Uso:  python scripts/verifica-contraste.py
Sale con codigo 1 si algo baja de 4.5:1.
"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, 'assets', 'img')

TEXT = '#f3eaee'
ROSE_TEXT = '#e7a6bd'
GOLD = '#d4af6a'
GOLD_SOFT = '#e0bf7a'
MUTED = '#b9a9b0'
BG = '#0b0a0b'
BLUSH = '#121012'
SURFACE = '#17141a'
TINT = '#1d1619'
ROSE_DEEP = '#e7a6bd'
ROSE_DEEPER = '#f0b8cc'
ON_ACCENT = '#0b0a0b'
ALERT_BG = '#211a10'
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


def _rgba(hx, a):
    r, g, b = hex_rgb(hx)
    return (float(r), float(g), float(b), a)


def k(a):
    """rgba(11,10,11,a) — --bg"""
    return _rgba(BG, a)


def bl(a):
    """rgba(18,16,18,a) — --blush"""
    return _rgba(BLUSH, a)


def sf(a):
    """rgba(23,20,26,a) — --surface"""
    return _rgba(SURFACE, a)


def flat(c):
    return linear180([(0.0, c), (1.0, c)])


# ---------------------------------------------------------------- checks ---
def peor_en(im, layers, box, step=3):
    """Pixel MAS CLARO de la banda tras componer las capas (la primera, arriba)."""
    W, H = im.size
    px = im.load()
    x0, y0, x1, y1 = box
    worst, wl = None, -1.0
    for y in range(int(y0 * H), int(y1 * H), step):
        for x in range(int(x0 * W), int(x1 * W), step):
            base = px[x, y]
            for layer in reversed(layers):
                base = _over(layer(x / W, y / H), base)
            l = lum_rgb(base)
            if l > wl:
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
    radial(0.76, 0.60, 0.50, 0.34, [(0.0, k(.92)), (0.58, k(.74)), (0.92, k(.32))]),
    linear180([(0.0, k(.86)), (0.32, k(.52)), (0.58, bl(.52)), (0.86, bl(.88)), (1.0, bl(.98))]),
]
HERO_MOBILE = [
    radial(1.04, 0.50, 0.50, 0.38, [(0.0, k(.92)), (0.62, k(.74)), (0.94, k(.38))]),
    linear180([(0.0, k(.86)), (0.28, k(.54)), (0.54, bl(.56)), (0.84, bl(.90)), (1.0, bl(.99))]),
]

# .tr-card::after (velo suave) + chip --surface .94 de .tr-cap.
# El chip cubre toda la banda del rotulo, asi que el peor caso es
# independiente de la foto: se comprueba tambien contra blanco puro.
TR_SCRIM = [
    flat(sf(.94)),                                      # chip .tr-cap
    linear180([(0.52, k(0.0)), (1.0, k(.35))]),         # .tr-card::after
]

HERO_TXT = [('titular --gold', GOLD), ('em/badge --rose-text', ROSE_TEXT), ('subtitulo --text', TEXT)]
NAV_TXT = [('logo --gold', GOLD), ('enlaces --text', TEXT), ('logo small --muted', MUTED)]
STAT_TXT = [('numero --gold', GOLD), ('etiqueta --muted', MUTED)]

print("\n=== 1 · HERO · texto sobre foto con velo oscuro ===")
print("\n[hero-spa.jpg · escritorio] banda del navbar")
im = Image.open(os.path.join(IMG, 'hero-spa.jpg')).convert('RGB')
report('nav escritorio', peor_en(im, HERO_DESKTOP, (0.0, 0.0, 1.0, 0.14)), NAV_TXT)

print("\n[hero-spa.jpg · escritorio] banda del badge + h1 + subtitulo")
report('hero escritorio', peor_en(im, HERO_DESKTOP, (0.15, 0.14, 0.85, 0.62)), HERO_TXT)

print("\n[hero-spa.jpg · escritorio] zona de la stat-card (--surface .88 sobre el velo)")
report('stat-card', peor_en(im, [flat(sf(.88))] + HERO_DESKTOP, (0.0, 0.66, 0.40, 1.0)), STAT_TXT)

print("\n[hero-spa-900.jpg · movil] banda del navbar")
im = Image.open(os.path.join(IMG, 'hero-spa-900.jpg')).convert('RGB')
report('nav movil', peor_en(im, HERO_MOBILE, (0.0, 0.0, 1.0, 0.12)), NAV_TXT)

print("\n[hero-spa-900.jpg · movil] banda del badge + h1 + subtitulo")
report('hero movil', peor_en(im, HERO_MOBILE, (0.03, 0.10, 0.97, 0.66)), HERO_TXT)

print("\n[hero-spa-900.jpg · movil] zona de la stat-card (--surface .88 sobre el velo)")
report('stat-card movil', peor_en(im, [flat(sf(.88))] + HERO_MOBILE, (0.0, 0.60, 1.0, 1.0)), STAT_TXT)

print("\n[peor caso absoluto] hero completo sobre una foto blanca")
blanca = Image.new('RGB', (200, 200), (255, 255, 255))
report('hero sobre blanco · escritorio', peor_en(blanca, HERO_DESKTOP, (0.15, 0.14, 0.85, 0.62), step=1), HERO_TXT)
report('hero sobre blanco · movil', peor_en(blanca, HERO_MOBILE, (0.03, 0.10, 0.97, 0.66), step=1), HERO_TXT)

# ---- 2. GALERIA ------------------------------------------------------------
print("\n=== 2 · GALERIA · rotulo en chip oscuro sobre la foto ===")
GALERIA = ['tr-limpieza', 'tr-antiedad', 'tr-presoterapia', 'tr-masaje', 'tr-manicura', 'tr-pestanas']
TR_TXT = [('titulo --text', TEXT), ('precio --rose-text', ROSE_TEXT)]
for nombre in GALERIA:
    im = Image.open(os.path.join(IMG, nombre + '.jpg')).convert('RGB')
    print(f"\n[{nombre}.jpg] banda del titulo + precio")
    report(nombre, peor_en(im, TR_SCRIM, (0.06, 0.62, 0.94, 0.97)), TR_TXT)

print("\n[peor caso absoluto] chip .94 sobre una foto blanca")
report('chip sobre blanco', peor_en(blanca, TR_SCRIM, (0.0, 0.62, 1.0, 1.0)), TR_TXT)

# ---- 3. FOOTER: halo rosa --------------------------------------------------
print("\n=== 3 · FOOTER · pico del halo rosa (.07) sobre --blush, y .ft-glass (.72) encima ===")
fondo = Image.new('RGB', (50, 50), hex_rgb(BLUSH))
HALO = flat(_rgba(ROSE_TEXT, .07))
report('footer halo', peor_en(fondo, [HALO], (0, 0, 1, 1)),
       [('titular --gold', GOLD), ('parrafo --muted', MUTED), ('em --rose-text', ROSE_TEXT)])
report('ft-glass', peor_en(fondo, [flat(sf(.72)), HALO], (0, 0, 1, 1)),
       [('marca --gold', GOLD), ('enlaces --muted', MUTED), ('rotulos --rose-text', ROSE_TEXT)])

# ---- 4. PARES PLANOS DE LA PALETA -----------------------------------------
print("\n=== 4 · Paleta plana ===")
PARES = []
for tn, tx in (('--text', TEXT), ('--muted', MUTED), ('--rose-text', ROSE_TEXT), ('--gold', GOLD)):
    for fn, fx in (('--bg', BG), ('--blush', BLUSH), ('--surface', SURFACE), ('--tint', TINT)):
        PARES.append((f'{tn} sobre {fn}', tx, fx))
PARES += [
    ('--on-accent sobre --rose-deep', ON_ACCENT, ROSE_DEEP),
    ('--on-accent sobre --rose-deeper', ON_ACCENT, ROSE_DEEPER),
    ('--gold-soft sobre aviso #211a10', GOLD_SOFT, ALERT_BG),
]
for etiqueta, a, b in PARES:
    r = ratio_hex(a, b)
    ok = r >= AA
    if not ok:
        fallos.append(etiqueta)
    print(f"    {etiqueta:<34} {r:6.2f}:1  {'OK' if ok else 'FALLA'}")

# ---------------------------------------------------------------------------
print()
if fallos:
    print("RESULTADO: " + str(len(fallos)) + " comprobacion(es) por debajo de 4.5:1")
    for f in fallos:
        print("  - " + f)
    sys.exit(1)
print("RESULTADO: todo por encima de 4.5:1 (AA)")
