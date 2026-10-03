#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verifica el contraste AA de la demo Selene (negro + dorado + rosa) midiendo
el PEOR PIXEL REAL bajo cada texto, no un color plano teorico.

Que hace:
  1. Recompone en Python la HERO PARTIDA tal y como la pinta el CSS (foto
     nitida a la derecha en >=901px, arriba en <=900px, con su fundido) y
     el velo de .tr-card::after, sobre las fotos reales del repo.
  2. Recorre la banda donde cae cada texto y se queda con el pixel mas CLARO
     (el texto es claro: el peor fondo es el mas luminoso).
  3. Calcula el ratio WCAG contra --text, --rose-text, --gold y --muted.
  4. Comprueba que la columna de texto de la hero no pisa la foto.
  5. Comprueba ademas los pares de color planos de la paleta.

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


def linear90(stops):
    """linear-gradient(90deg, ...) — t = x."""
    return lambda fx, fy: _stop(stops, fx)


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


# ---- 1. HERO PARTIDA ------------------------------------------------------
# Espejo de las constantes del CSS de la hero en index.html.
PHOTO_LEFT = 0.46            # .hero-bg{left:46%}
TEXT_MAX = 0.44              # .hero-text{max-width:44%}
OBJ_DESKTOP = (0.60, 0.55)   # object-position en >=901px
OBJ_MOBILE = (0.50, 0.68)    # object-position en <=900px
NAV_BP = 1120                # desde aqui se ven los enlaces (pill); antes, hamburguesa
FADE_DESKTOP = linear90([(PHOTO_LEFT, k(1.0)), (0.58, k(0.0))])   # .hero-card::after
FADE_MOBILE = linear180([(0.82, k(0.0)), (1.0, k(1.0))])
PILL = flat(sf(.88))         # .nav-links / .hero-nav en <=900px / .stat-card
TOGGLE = flat(sf(.82))       # .nav-toggle

HERO_TXT = [('titular --gold', GOLD), ('em/badge --rose-text', ROSE_TEXT),
            ('subtitulo --text', TEXT), ('etiqueta --muted', MUTED)]
PILL_TXT = [('enlaces --text', TEXT)]
NAV_TXT = [('logo --gold', GOLD), ('logo small --muted', MUTED), ('icono --text', TEXT)]


def cover(im, bw, bh, pos):
    """object-fit:cover con object-position (px, py) en una caja bw x bh."""
    W, H = im.size
    sc = max(bw / W, bh / H)
    sw, sh = max(bw, round(W * sc)), max(bh, round(H * sc))
    im = im.resize((sw, sh), Image.BILINEAR)
    x, y = round((sw - bw) * pos[0]), round((sh - bh) * pos[1])
    return im.crop((x, y, x + bw, y + bh))


def hero_desktop(im, vw, vh):
    """La .hero-card en >=901px: --bg solido + foto desde el 46%."""
    w, h = min(1536, vw - 40), vh - 40
    card = Image.new('RGB', (w, h), hex_rgb(BG))
    x0 = round(w * PHOTO_LEFT)
    card.paste(cover(im, w - x0, h, OBJ_DESKTOP), (x0, 0))
    return card


print("\n=== 1 · HERO PARTIDA · el texto va sobre --bg, la foto sin velo ===")
im = Image.open(os.path.join(IMG, 'hero-spa.jpg')).convert('RGB')
for vw, vh in ((901, 700), (1024, 768), (1280, 800), (1440, 900), (1920, 1080)):
    card = hero_desktop(im, vw, vh)
    w = card.size[0]
    print(f"\n[{vw}px · escritorio] columna de texto 0-{TEXT_MAX:.0%} (logo, badge, h1, sub, stat-card)")
    pisa = TEXT_MAX * w > PHOTO_LEFT * w
    print(f"    texto hasta x={TEXT_MAX * w:.0f}px · foto desde x={PHOTO_LEFT * w:.0f}px  "
          f"{'PISA LA FOTO' if pisa else 'no pisa'}")
    if pisa:
        fallos.append(f'hero {vw}: el texto pisa la foto')
    report(f'hero {vw}', peor_en(card, [FADE_DESKTOP], (0.0, 0.0, TEXT_MAX, 1.0)), HERO_TXT)
    if vw >= NAV_BP:
        print(f"[{vw}px] pill de enlaces (.88) sobre la foto + fundido")
        report(f'nav pill {vw}', peor_en(card, [PILL, FADE_DESKTOP], (0.18, 0.0, 0.82, 0.16)), PILL_TXT)
    else:
        print(f"[{vw}px] boton hamburguesa (.82) sobre la foto")
        report(f'nav toggle {vw}', peor_en(card, [TOGGLE, FADE_DESKTOP], (0.80, 0.0, 1.0, 0.16)), PILL_TXT)

im = Image.open(os.path.join(IMG, 'hero-spa-900.jpg')).convert('RGB')
for vw, vh in ((390, 844), (768, 1024)):
    w = vw - (24 if vw < 768 else 40)
    ph = round(max(280, 0.44 * vh))
    foto = cover(im, w, ph, OBJ_MOBILE)
    print(f"\n[{vw}px · movil] foto arriba ({w}x{ph}) · pill de la nav (.88) sobre la foto")
    report(f'nav pill {vw}', peor_en(foto, [PILL, FADE_MOBILE], (0.0, 0.0, 1.0, 84 / ph)), NAV_TXT)
    print(f"[{vw}px · movil] ultima fila del fundido (donde empieza el texto, ya sobre --bg)")
    report(f'fundido {vw}', peor_en(foto, [FADE_MOBILE], (0.0, (ph - 1) / ph, 1.0, 1.0), step=1), HERO_TXT)

print("\n[peor caso absoluto] pills sobre una foto blanca (cubre tambien el zoom lento)")
blanca = Image.new('RGB', (200, 200), (255, 255, 255))
report('pill .88 sobre blanco', peor_en(blanca, [PILL], (0, 0, 1, 1)), NAV_TXT)
report('toggle .82 sobre blanco', peor_en(blanca, [TOGGLE], (0, 0, 1, 1)), PILL_TXT)

print("\n[stat-card] --surface .88 sobre --bg")
negro = Image.new('RGB', (50, 50), hex_rgb(BG))
report('stat-card', peor_en(negro, [PILL], (0, 0, 1, 1)), [('numero --gold', GOLD), ('etiqueta --muted', MUTED)])

# ---- 2. GALERIA ------------------------------------------------------------
print("\n=== 2 · GALERIA · rotulo en chip oscuro sobre la foto ===")
# .tr-card::after (velo suave) + chip --surface .94 de .tr-cap.
# El chip cubre toda la banda del rotulo, asi que el peor caso es
# independiente de la foto: se comprueba tambien contra blanco puro.
TR_SCRIM = [
    flat(sf(.94)),                                      # chip .tr-cap
    linear180([(0.52, k(0.0)), (1.0, k(.35))]),         # .tr-card::after
]
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
