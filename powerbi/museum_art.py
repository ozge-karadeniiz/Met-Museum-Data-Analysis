"""Procedural museum backgrounds for the MET Atlas report.

Every page background is drawn from the same layout boxes that position the Power BI
visuals, so gilded frames, brass plaques and slicer pedestals line up with the report.
Only decoration is baked in; all data and meaningful text stay in Power BI visuals.
"""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1440, 900          # report canvas in px
S = 2                     # render scale for crisp output on large screens
FONTS = 'C:/Windows/Fonts/'


def rgb(h):
    if isinstance(h, tuple):
        return h[:3]
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def font(name, size):
    return ImageFont.truetype(FONTS + name, int(size * S))


def sbox(box, grow=0):
    x, y, w, h = box
    return [(x - grow) * S, (y - grow) * S, (x + w + grow) * S, (y + h + grow) * S]


# Moulding profile of a gilded frame, from the outer edge (0) to the sight edge (1).
GOLD = [(0.00, '#5C4319'), (0.05, '#E8CD8A'), (0.14, '#B88F43'), (0.28, '#73541F'), (0.40, '#D2AE63'),
        (0.48, '#F5E3A8'), (0.56, '#BE974C'), (0.72, '#A07C34'), (0.84, '#E3C67E'), (0.93, '#6A4D1C'), (1.00, '#33240C')]
STEEL = [(0.00, '#2E3338'), (0.20, '#8D959C'), (0.45, '#D7DCE0'), (0.70, '#9AA2A9'), (1.00, '#3A4046')]
NIGHT = [(0.00, '#3B2E14'), (0.30, '#C9A45C'), (0.55, '#F0D894'), (0.80, '#9C7A36'), (1.00, '#2A200C')]


def profile(stops, t):
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t <= t1:
            return mix(rgb(c0), rgb(c1), (t - t0) / max(t1 - t0, 1e-6))
    return rgb(stops[-1][1])


class Wall:
    """A lit, textured wall that frames and plaques are hung on."""

    def __init__(self, base, seed=7, top_gain=0.08, bottom_gain=-0.22, vignette=0.16):
        rng = np.random.default_rng(seed)
        h, w = H * S, W * S
        y = np.linspace(0, 1, h)[:, None]
        x = np.linspace(-1, 1, w)[None, :]
        gain = 1 + top_gain * (1 - y) + bottom_gain * y ** 1.6 - vignette * x ** 4
        low = np.array(Image.fromarray((rng.random((18, 30)) * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), np.float32) / 255 - 0.5
        fine = np.array(Image.fromarray((rng.random((h, w)) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7)), np.float32) / 255 - 0.5
        texture = 1 + 0.045 * low + 0.05 * fine
        self.light = np.zeros((h, w), np.float32)
        self.base = np.array(rgb(base), np.float32)
        self.gain = (gain * texture).astype(np.float32)
        self.overlays = []

    def spotlight(self, cx, cy, rx, ry, strength=0.55):
        """Soft elliptical pool of light, as from a ceiling track spot."""
        h, w = self.light.shape
        y = (np.arange(h, dtype=np.float32)[:, None] / S - cy) / ry
        x = (np.arange(w, dtype=np.float32)[None, :] / S - cx) / rx
        self.light += strength * np.exp(-(x * x + y * y) * 1.6)

    def beam(self, x_top, y_top, box, strength=0.10):
        """Faint cone of light from a fixture down to the top of a frame."""
        x, y, w, h = box
        layer = Image.new('L', (W * S, H * S), 0)
        ImageDraw.Draw(layer).polygon([((x_top - 8) * S, y_top * S), ((x_top + 8) * S, y_top * S),
                                       ((x + w + 30) * S, (y + h * 0.6) * S), ((x - 30) * S, (y + h * 0.6) * S)], fill=255)
        layer = layer.filter(ImageFilter.GaussianBlur(40 * S))
        self.light += strength * np.array(layer, np.float32) / 255

    def render(self, warm='#FFE2AE'):
        tint = np.array(rgb(warm), np.float32)
        light = self.light[..., None]
        img = self.base * self.gain[..., None] * (1 + 0.85 * light) + tint * 0.10 * light
        return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert('RGBA')


def shadow(img, box, grow=0, blur=16, offset=10, alpha=150, radius=0):
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    x0, y0, x1, y1 = sbox(box, grow)
    ImageDraw.Draw(layer).rounded_rectangle([x0, y0 + offset * S, x1, y1 + offset * S], radius=radius * S, fill=(0, 0, 0, alpha))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur * S)))


def moulding(draw, outer, width, stops):
    """Concentric strokes following a profile give mitred, carved-looking corners."""
    x0, y0, x1, y1 = outer
    n = int(width * S)
    for i in range(n):
        draw.rectangle([x0 + i, y0 + i, x1 - i, y1 - i], outline=profile(stops, i / max(n - 1, 1)))


def side_light(img, outer, width, top=0.16, bottom=0.30, right=0.14):
    """Light from above: brighten the top rail, darken the bottom and right rails."""
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0, y0, x1, y1 = outer
    f = width * S
    d.polygon([(x0, y0), (x1, y0), (x1 - f, y0 + f), (x0 + f, y0 + f)], fill=(255, 246, 220, int(255 * top)))
    d.polygon([(x0, y1), (x1, y1), (x1 - f, y1 - f), (x0 + f, y1 - f)], fill=(20, 10, 0, int(255 * bottom)))
    d.polygon([(x1, y0), (x1, y1), (x1 - f, y1 - f), (x1 - f, y0 + f)], fill=(20, 10, 0, int(255 * right)))
    img.alpha_composite(layer)


def framed(img, box, mat='#F7F2E8', frame=11, margin=14, stops=GOLD, mat_line=True, shadow_alpha=170):
    """Hang a framed, matted panel. `box` is the visual's content rectangle."""
    m, f = margin, frame
    shadow(img, box, grow=m + f, blur=18, offset=12, alpha=shadow_alpha)
    d = ImageDraw.Draw(img)
    outer = sbox(box, m + f)
    moulding(d, outer, f, stops)
    side_light(img, outer, f)
    d = ImageDraw.Draw(img)
    d.rectangle(sbox(box, m), fill=rgb(mat))
    if mat_line:  # bevel cut of the mat window
        x0, y0, x1, y1 = sbox(box, 6)
        d.line([(x0, y1), (x0, y0), (x1, y0)], fill=mix(rgb(mat), (255, 255, 255), 0.7), width=S)
        d.line([(x0, y1), (x1, y1), (x1, y0)], fill=mix(rgb(mat), (90, 70, 40), 0.22), width=S)


def brass(img, box, kind='brass'):
    """Engraved plaque with brushed metal and two screws."""
    tones = {'brass': ('#E6CD8E', '#C7A55C', '#9C7A38', '#F7E9BE', '#5E4518'),
             'steel': ('#F1F3F4', '#CDD2D6', '#A9B0B6', '#FFFFFF', '#5B636A'),
             'glass': ('#1C2630', '#141C24', '#0F151C', '#C9A45C', '#C9A45C')}[kind]
    top, mid, low, hi, lo = (rgb(t) for t in tones)
    shadow(img, box, blur=8, offset=5, alpha=150, radius=4)
    x0, y0, x1, y1 = sbox(box)
    w, h = x1 - x0, y1 - y0
    t = np.linspace(0, 1, h)[:, None, None]
    grad = np.where(t < 0.5, np.array(top) + (np.array(mid) - np.array(top)) * t * 2,
                    np.array(mid) + (np.array(low) - np.array(mid)) * (t - 0.5) * 2) * np.ones((1, w, 1))
    if kind != 'glass':
        rng = np.random.default_rng(int(x0 + y0))
        streak = np.array(Image.fromarray((rng.random((h, w)) * 255).astype(np.uint8)).filter(ImageFilter.BoxBlur(0)).resize((w // 40 + 1, h)).resize((w, h), Image.BILINEAR), np.float32) / 255 - 0.5
        grad = grad * (1 + 0.07 * streak[..., None])
    plate = Image.fromarray(np.clip(grad, 0, 255).astype(np.uint8)).convert('RGBA')
    mask = Image.new('L', (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=4 * S, fill=255)
    img.paste(plate, (x0, y0), mask)
    d = ImageDraw.Draw(img)
    if kind == 'glass':
        d.rounded_rectangle([x0, y0, x1, y1], radius=4 * S, outline=hi, width=S)
        d.line([(x0 + 14 * S, y0 + 3 * S), (x1 - 14 * S, y0 + 3 * S)], fill=mix(hi, top, 0.5), width=S)
        return
    d.rounded_rectangle([x0, y0, x1, y1], radius=4 * S, outline=lo, width=S)
    d.line([(x0 + 4 * S, y0 + S), (x1 - 4 * S, y0 + S)], fill=hi, width=S)
    d.rounded_rectangle([x0 + 5 * S, y0 + 5 * S, x1 - 5 * S, y1 - 5 * S], radius=2 * S, outline=mix(lo, mid, 0.55), width=S)
    for cx in (x0 + 13 * S, x1 - 13 * S):
        cy, r = (y0 + y1) // 2, int(3.6 * S)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=mix(low, lo, 0.3), outline=lo)
        d.ellipse([cx - r + S, cy - r + S, cx, cy], fill=mix(hi, mid, 0.3))
        d.line([(cx - r + S, cy + r - S), (cx + r - S, cy - r + S)], fill=lo, width=S)


def pedestal(img, box, fill='#000000', alpha=95, line='#C9A45C'):
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0, y0, x1, y1 = sbox(box)
    d.rounded_rectangle([x0, y0, x1, y1], radius=4 * S, fill=rgb(fill) + (alpha,))
    d.line([(x0 + 4 * S, y1), (x1 - 4 * S, y1)], fill=rgb(line) + (210,), width=S)
    img.alpha_composite(layer)


def panel(img, box, fill, edge=None, shadow_alpha=120, radius=2):
    if shadow_alpha:
        shadow(img, box, blur=12, offset=8, alpha=shadow_alpha, radius=radius)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(sbox(box), radius=radius * S, fill=rgb(fill), outline=rgb(edge) if edge else None, width=S)


def spaced(img, xy, text, size, color, name='georgia.ttf', spacing=0.28, alpha=255, anchor='l'):
    """Letter-spaced caps (Power BI text boxes cannot track letters)."""
    f = font(name, size)
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    widths = [d.textlength(ch, font=f) for ch in text]
    total = sum(widths) + spacing * size * S * (len(text) - 1)
    x = xy[0] * S - (total if anchor == 'r' else total / 2 if anchor == 'm' else 0)
    for ch, w in zip(text, widths):
        d.text((x, xy[1] * S), ch, font=f, fill=rgb(color) + (alpha,))
        x += w + spacing * size * S
    img.alpha_composite(layer)
    return total / S


def watermark(img, xy, text, size, color, alpha=16):
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((xy[0] * S, xy[1] * S), text, font=font('georgia.ttf', size), fill=rgb(color) + (alpha,))
    img.alpha_composite(layer)


def rule(img, x0, x1, y, color='#C9A45C', alpha=200, width=1):
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).line([(x0 * S, y * S), (x1 * S, y * S)], fill=rgb(color) + (alpha,), width=width * S)
    img.alpha_composite(layer)


def diamond(img, cx, cy, r, color='#C9A45C'):
    ImageDraw.Draw(img).polygon([(cx * S, (cy - r) * S), ((cx + r) * S, cy * S), (cx * S, (cy + r) * S), ((cx - r) * S, cy * S)], fill=rgb(color))


def nav_band(img, items, active, wordmark_color='#F3ECDF'):
    """Dark top band with the MET ATLAS wordmark and an underline under the active room."""
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rectangle([0, 0, W * S, 60 * S], fill=(12, 9, 8, 236))
    img.alpha_composite(layer)
    rule(img, 0, W, 60, alpha=170)
    rule(img, 0, W, 62, color='#000000', alpha=90)
    diamond(img, 52, 30, 6)
    spaced(img, (68, 17), 'MET ATLAS', 17, wordmark_color, spacing=0.34)
    spaced(img, (232, 24), 'SANATIN VERİYLE KEŞFİ', 8.5, '#B9AC98', name='segoeui.ttf', spacing=0.30)
    for page, (x, w) in items.items():
        if page == active:
            rule(img, x + 18, x + w - 18, 55, width=2, alpha=255)
            diamond(img, x + w / 2, 55, 3.2)


def baseboard(img, color):
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rectangle([0, 866 * S, W * S, H * S], fill=rgb(color) + (255,))
    img.alpha_composite(layer)
    rule(img, 0, W, 866, color='#C9A45C', alpha=120)
    rule(img, 0, W, 868, color='#000000', alpha=120)


def blueprint(img, step=24, color='#9FB2C2', alpha=40):
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i, x in enumerate(range(0, W, step)):
        d.line([(x * S, 64 * S), (x * S, 866 * S)], fill=rgb(color) + (alpha * (2 if i % 5 == 0 else 1),), width=1)
    for i, y in enumerate(range(64, 866, step)):
        d.line([(0, y * S), (W * S, y * S)], fill=rgb(color) + (alpha * (2 if i % 5 == 0 else 1),), width=1)
    img.alpha_composite(layer)


def index_card(img, box):
    """Conservator's lined index card."""
    shadow(img, box, blur=10, offset=7, alpha=110)
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = sbox(box)
    d.rectangle([x0, y0, x1, y1], fill=rgb('#FFFDF6'))
    d.line([(x0, y0 + 40 * S), (x1, y0 + 40 * S)], fill=rgb('#D46A6A'), width=S)
    for y in range(y0 + 66 * S, y1 - 8 * S, 24 * S):
        d.line([(x0, y), (x1, y)], fill=rgb('#BCD3E6'), width=S)
    d.line([(x0 + 34 * S, y0), (x0 + 34 * S, y1)], fill=rgb('#E9A6A6'), width=S)


def floor_plan(img, rooms, hall, color='#C9A45C'):
    """Gallery floor plan: double-line walls, doorways into the great hall, 'you are here'."""
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for box in list(rooms) + [hall]:
        x0, y0, x1, y1 = sbox(box)
        d.rectangle([x0, y0, x1, y1], fill=(255, 238, 200, 12))
        for inset, a in ((0, 210), (4 * S, 80)):
            d.rectangle([x0 + inset, y0 + inset, x1 - inset, y1 - inset], outline=rgb(color) + (a,), width=S)
    hx0, hy0, hx1, hy1 = sbox(hall)
    for box in rooms:  # erase wall segments to open a doorway, then draw door jambs
        x0, y0, x1, y1 = sbox(box)
        cx = (x0 + x1) // 2
        top, bottom = (y1, hy0) if y1 <= hy0 else (hy1, y0)
        d.rectangle([cx - 15 * S, top - 6 * S, cx + 15 * S, bottom + 6 * S], fill=(255, 238, 200, 12))
        for jx in (cx - 15 * S, cx + 15 * S):
            d.line([(jx, top - 5 * S), (jx, bottom + 5 * S)], fill=rgb(color) + (200,), width=S)
    img.alpha_composite(layer)


def save(img, path):
    img.convert('RGB').save(path, 'JPEG', quality=88, optimize=True, progressive=True, subsampling=0)
