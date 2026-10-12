"""Turn MET Atlas into a museum walk-through.

Run after build_project.py, add_exploration.py and fetch_highlights.py. The script
- renders one museum-wall background per page (museum_art.py) from the same layout
  boxes that position the visuals,
- registers a museum theme and the backgrounds,
- adds presentation measures (narratives, heat-map colours, SVG wall labels and frames),
- replaces the Gallery table with every highlight artwork (highlights-catalog.json),
- rewrites the report pages: a lobby with a clickable floor plan, four galleries,
  a department tooltip page, wayfinding navigation and synced slicers. The earlier
  night-tour and conservation pages are removed.

Analytical measures and the Artwork table are left untouched. The previous report and
model files are copied under work/ before anything is written.
"""
import base64
import json
import shutil
import zlib
from datetime import datetime
from pathlib import Path

import museum_art as art

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / 'MET Atlas'
REPORT = PROJECT / 'MET Atlas.Report'
MODEL = PROJECT / 'MET Atlas.SemanticModel'
RESOURCES = REPORT / 'StaticResources' / 'RegisteredResources'
BASE = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/'

IVORY, MUTED, GOLD, GOLD_LIGHT = '#F4EDE1', '#CFC2AE', '#C9A45C', '#E2C47E'
INK, INK_SOFT, OXBLOOD, MAT = '#2A211B', '#6E6052', '#8E2A2F', '#F7F2E8'
FOLDER = 'Müze sunumu'

# ----------------------------------------------------------------------------- helpers

def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def L(value):
    if isinstance(value, bool):
        value = 'true' if value else 'false'
    elif isinstance(value, (int, float)):
        value = f'{value}D'
    else:
        value = "'" + str(value).replace("'", "''") + "'"
    return {'expr': {'Literal': {'Value': value}}}


def C(value):
    return {'solid': {'color': L(value)}}


def ref(name, entity='Artwork', measure=False):
    return {'Measure' if measure else 'Column': {'Expression': {'SourceRef': {'Entity': entity}}, 'Property': name}}


def proj(name, entity='Artwork', measure=False, label=None):
    p = {'field': ref(name, entity, measure), 'queryRef': f'{entity}.{name}', 'nativeQueryRef': name}
    if label is not None:
        p['displayName'] = label
    return p


def props(**kw):
    return [{'properties': {k: v for k, v in kw.items()}}]


def inset(box, d):
    x, y, w, h = box
    return (x + d, y + d, w - 2 * d, h - 2 * d)


# ----------------------------------------------------------------------------- DAX for SVG

def enc(text):
    """Percent-encode static SVG text for a utf8 data URI."""
    out = []
    for ch in text:
        if ch in '%#' or ord(ch) > 126 or ch in '\n\r\t':
            out.append(''.join(f'%{b:02X}' for b in ch.encode('utf-8')) if ch not in '\n\r\t' else ' ')
        else:
            out.append(ch)
    return ''.join(out)


def dax_str(text):
    return '"' + text.replace('"', '""') + '"'


def dyn(expr):
    """Escape a dynamic DAX text value for XHTML inside a data URI."""
    xml = f'SUBSTITUTE(SUBSTITUTE(SUBSTITUTE({expr}, "&", "&amp;"), "<", "&lt;"), ">", "&gt;")'
    return f'SUBSTITUTE(SUBSTITUTE({xml}, "%", "%25"), "#", "%23")'


def svg_measure(width, height, html, style, prelude=''):
    """`html` is a list of static strings and ('dax', expression) parts."""
    head = (f"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>"
            f"<foreignObject x='0' y='0' width='{width}' height='{height}'><div xmlns='http://www.w3.org/1999/xhtml' style='{style}'>")
    parts = [dax_str(enc(head))]
    for part in html:
        parts.append(dyn(part[1]) if isinstance(part, tuple) else dax_str(enc(part)))
    parts.append(dax_str('</div></foreignObject></svg>'))
    return prelude + 'RETURN\n    ' + '\n    & '.join(parts)


def em(expr, color=GOLD_LIGHT):
    return [f"<b style='color:{color};font-family:Georgia;font-weight:normal;font-size:1.12em'>", ('dax', expr), '</b>']


def pct(expr):
    return f'IF(ISBLANK({expr}), "hesaplanamıyor", FORMAT({expr}, "0.0%"))'


def num(expr):
    return f'FORMAT({expr}, "#,0")'


NARRATIVE_STYLE = 'font-family:Segoe UI;font-size:14px;line-height:1.55;color:{c};margin:0'


def narrative(html, prelude, color=MUTED, width=760, height=58):
    return svg_measure(width, height, html, NARRATIVE_STYLE.format(c=color), prelude)


# ----------------------------------------------------------------------------- gallery SVGs

GOLD_SVG = art.GOLD
BRONZE_SVG = [(0.00, '#17120E'), (0.25, '#5E4B36'), (0.50, '#A48A62'), (0.75, '#4E3F2E'), (1.00, '#110D0A')]


class X:
    """A coordinate DAX computes at query time: a sum of measure variables plus a constant."""

    def __init__(self, terms=(), c=0.0):
        self.terms, self.c = tuple(terms), float(c)

    def __add__(self, o):
        return X(self.terms + o.terms, self.c + o.c) if isinstance(o, X) else X(self.terms, self.c + o)

    __radd__ = __add__

    def __sub__(self, o):
        return self + (-o)

    def __rsub__(self, o):
        return (-self) + o

    def __neg__(self):
        return X(tuple(t[1:] if t.startswith('-') else '-' + t for t in self.terms), -self.c)

    def dax(self):
        e = ''.join((' - ' + t[1:]) if t.startswith('-') else (' + ' + t) for t in self.terms)
        e = ('-' + e[3:]) if e.startswith(' - ') else e[3:]
        return f'FORMAT({e} + ({self.c:.2f}), "0.0", "en-US")'


def P(*items):
    """SVG source as static text and ('num', DAX) parts; plain numbers are written directly."""
    out = []
    for it in items:
        if isinstance(it, list):
            out.extend(it)
        elif isinstance(it, str):
            out.append(it)
        elif isinstance(it, X):
            out.append(('num', it.dax()))
        else:
            out.append(f'{it:.2f}')
    return out


def static(parts):
    return ''.join(parts)


def dax_concat(parts, escape=dyn):
    """Join SVG parts into one DAX text expression. Static text is percent-encoded."""
    merged = []
    for part in parts:
        if isinstance(part, str) and merged and isinstance(merged[-1], str):
            merged[-1] += part
        else:
            merged.append(part)
    out = []
    for part in merged:
        if isinstance(part, str):
            out.append(dax_str(enc(part)))
        elif part[0] == 'num':
            out.append(part[1])
        else:
            out.append(escape(part[1]))
    return '\n    & '.join(out)


def rect(x, y, w, h, attrs):
    return P("<rect x='", x, "' y='", y, "' width='", w, "' height='", h, f"' {attrs}/>")


def ring(outer, inner):
    (ox, oy, ow, oh), (ix, iy, iw, ih) = outer, inner
    return P('M', ox, ',', oy, 'h', ow, 'v', oh, 'h', -ow, 'Z M', ix, ',', iy, 'h', iw, 'v', ih, 'h', -iw, 'Z')


def gold_strokes(x, y, w, h, band, stops, n=16):
    out = []
    for i in range(n):
        c = '#%02X%02X%02X' % art.profile(stops, i / (n - 1))
        d = band * (i + 0.5) / n
        out += rect(x + d, y + d, w - 2 * d, h - 2 * d, f"fill='none' stroke='{c}' stroke-width='{band / n + 0.7:.2f}'")
    f = band
    poly = lambda pts, attrs: P("<polygon points='", *[q for a, b in pts for q in (a, ',', b, ' ')], f"' {attrs}/>")
    out += poly([(x, y), (x + w, y), (x + w - f, y + f), (x + f, y + f)], "fill='#FFF6DC' fill-opacity='0.16'")
    out += poly([(x, y + h), (x + w, y + h), (x + w - f, y + h - f), (x + f, y + h - f)], "fill='#140A00' fill-opacity='0.30'")
    out += poly([(x + w, y), (x + w, y + h), (x + w - f, y + h - f), (x + w - f, y + f)], "fill='#140A00' fill-opacity='0.14'")
    return out


def sight_rect(box_w, box_h, pad, info):
    """Where the photo's paint starts inside a frame box: the image visual fits the photo
    into the box inset by `pad`, keeping the aspect ratio; the photo's black border is skipped."""
    px_w, px_h, bl, br, bt, bb = info
    aspect = px_w / px_h
    iw, ih = box_w - 2 * pad, box_h - 2 * pad
    w = min(iw, ih * aspect)
    h = w / aspect
    x, y = (box_w - w) / 2, (box_h - h) / 2
    s = w / px_w
    return (x + bl * s + 1, y + bt * s + 1, w - (bl + br) * s - 2, h - (bt + bb) * s - 2)


FRAMES = {  # gilded frame for paintings, a bronze shadow-box vitrine for objects
    'painting': dict(band=30, liner=9, stops=GOLD_SVG, liner_fill='#E6DCC4', edge='#9C8B66'),
    'object': dict(band=13, liner=24, stops=BRONZE_SVG, liner_fill='#1A1512', edge='#000000'),
}


def frame_parts(box_w, box_h, sight, band, liner, stops, liner_fill, edge):
    """A frame hung *over* the artwork image visual; its centre stays transparent."""
    grow = lambda r, d: (r[0] - d, r[1] - d, r[2] + 2 * d, r[3] + 2 * d)
    lin = grow(sight, liner)
    fx, fy, fw, fh = grow(lin, band)
    sx, sy, sw, sh = sight
    return P(f"<svg xmlns='http://www.w3.org/2000/svg' width='{box_w}' height='{box_h}' viewBox='0 0 {box_w} {box_h}'>"
             "<defs><filter id='s' x='-20%' y='-20%' width='140%' height='140%'><feGaussianBlur stdDeviation='10'/></filter>"
             "<filter id='i' x='-5%' y='-5%' width='110%' height='110%'><feGaussianBlur stdDeviation='3'/></filter></defs>",
             "<path d='", ring((fx + 4, fy + 14, fw - 8, fh - 4), sight), "' fill='#000' fill-opacity='0.6' fill-rule='evenodd' filter='url(#s)'/>",
             "<path d='", ring(grow(sight, 2), (sx + 2, sy + 5, sw - 4, sh - 7)), "' fill='#000' fill-opacity='0.55' fill-rule='evenodd' filter='url(#i)'/>",
             "<path d='", ring(lin, sight), f"' fill='{liner_fill}' fill-rule='evenodd'/>",
             rect(sx - 0.5, sy - 0.5, sw + 1, sh + 1, f"fill='none' stroke='{edge}' stroke-width='1'"),
             gold_strokes(fx, fy, fw, fh, band, stops),
             '</svg>')


def frame_svg(box_w, box_h, pad, info, kind='painting'):
    return 'data:image/svg+xml;utf8,' + enc(static(frame_parts(box_w, box_h, sight_rect(box_w, box_h, pad, info), **FRAMES[kind])))


def frame_dax(box_w, box_h, kind):
    sight = tuple(X([v]) for v in ('sx', 'sy', 'sw', 'sh'))
    return dax_concat(P('data:image/svg+xml;utf8,', frame_parts(box_w, box_h, sight, **FRAMES[kind])))


def esc(text):
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace("'", '&#39;')


def label_parts(width, height, html):
    """A cream museum wall label; `html` mixes static strings and ('dax', expression) parts."""
    head = (f"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>"
            "<defs><filter id='s' x='-20%' y='-20%' width='140%' height='140%'><feGaussianBlur stdDeviation='6'/></filter>"
            "<linearGradient id='p' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='#FBF7EE'/><stop offset='1' stop-color='#EFE7D7'/></linearGradient></defs>"
            f"<rect x='10' y='12' width='{width - 20}' height='{height - 20}' fill='#000' fill-opacity='0.55' filter='url(#s)'/>"
            f"<rect x='6' y='4' width='{width - 12}' height='{height - 16}' fill='url(#p)'/>"
            f"<foreignObject x='6' y='4' width='{width - 12}' height='{height - 16}'><div xmlns='http://www.w3.org/1999/xhtml'>")
    return [head] + list(html) + ['</div></foreignObject></svg>']


def wall_label_html():
    clip = 'overflow:hidden;text-overflow:ellipsis'
    return [f"<div style='font-family:Segoe UI;color:{INK};padding:20px 22px'>",
            f"<div style='font-size:9.5px;letter-spacing:2.2px;color:{OXBLOOD};font-weight:600'>", ('dax', 'flags'), '</div>',
            f"<div style='font-size:8.5px;letter-spacing:1.6px;color:{INK_SOFT};margin-top:4px'>", ('dax', 'fame'), '</div>',
            f"<div style='font-family:Georgia;font-size:19px;line-height:1.2;margin-top:9px;max-height:46px;{clip}'>", ('dax', 'artist'), '</div>',
            f"<div style='font-family:Georgia;font-style:italic;font-size:11.5px;color:{INK_SOFT};margin-top:3px;max-height:30px;{clip}'>", ('dax', 'bio'), '</div>',
            f"<div style='height:1px;background:{GOLD};margin:13px 0 12px'></div>",
            "<div style='font-family:Georgia;font-style:italic;line-height:1.25;max-height:98px;" + clip + ";font-size:", ('dax', 'ts'), "px'>",
            ('dax', 'title'), "<span style='font-style:normal'>", ('dax', 'dateText'), '</span></div>',
            f"<div style='font-size:11.5px;margin-top:10px;max-height:58px;{clip}'>", ('dax', 'medium'), '</div>',
            f"<div style='font-size:11.5px;color:{INK_SOFT};margin-top:2px;max-height:30px;{clip}'>", ('dax', 'dept'), '</div>',
            f"<div style='font-size:10px;color:{INK_SOFT};margin-top:12px;line-height:1.45;max-height:60px;{clip}'>", ('dax', 'credit'), '<br/>', ('dax', 'acc'), '</div>',
            '</div>']


# ----------------------------------------------------------------------------- report writer

class Page:
    def __init__(self, name, display, background=None, color='#0B0908', width=1440, height=900, **extra):
        self.name, self.display, self.width, self.height = name, display, width, height
        self.background, self.color, self.extra = background, color, extra
        self.visuals, self.interactions = [], []

    def add(self, name, kind, box, objects=None, vco=None, query=None, sort=None, sync=None, filters=None, header=False):
        x, y, w, h = box
        cfg = {'visualType': kind, 'drillFilterOtherVisuals': True}
        if query:
            cfg['query'] = {'queryState': {role: {'projections': items} for role, items in query.items()}}
            if sort:
                cfg['query']['sortDefinition'] = {'sort': [{'field': sort[0], 'direction': sort[1]}], 'isDefaultSort': False}
        if objects:
            cfg['objects'] = objects
        container = {'background': props(show=L(False)), 'border': props(show=L(False)),
                     'dropShadow': props(show=L(False)), 'title': props(show=L(False))}
        if not header:
            container['visualHeader'] = props(show=L(False))
        container.update(vco or {})
        cfg['visualContainerObjects'] = container
        if sync:
            cfg['syncGroup'] = {'groupName': sync, 'fieldChanges': True, 'filterChanges': True}
        z = len(self.visuals) * 1000
        visual = {'$schema': BASE + 'visualContainer/2.1.0/schema.json', 'name': name,
                  'position': {'x': x, 'y': y, 'z': z, 'height': h, 'width': w, 'tabOrder': z}, 'visual': cfg}
        if filters:
            visual['filterConfig'] = {'filters': filters}
        self.visuals.append(visual)
        return visual

    def save(self):
        folder = REPORT / 'definition' / 'pages' / self.name
        if folder.exists():
            shutil.rmtree(folder)
        objects = {'outspace': props(color=C('#0B0908'), transparency=L(0))}
        bg = {'color': C(self.color), 'transparency': L(0)}
        if self.background:
            bg['image'] = {'image': {'name': L(self.background), 'scaling': L('Fit'),
                                     'url': {'expr': {'ResourcePackageItem': {'PackageName': 'RegisteredResources', 'PackageType': 1, 'ItemName': self.background}}}}}
        objects['background'] = [{'properties': bg}]
        page = {'$schema': BASE + 'page/2.0.0/schema.json', 'name': self.name, 'displayName': self.display,
                'displayOption': 'FitToPage', 'height': self.height, 'width': self.width, 'objects': objects}
        page.update(self.extra)
        if self.interactions:
            page['visualInteractions'] = [{'source': i[0], 'target': i[1], 'type': i[2] if len(i) > 2 else 'DataFilter'} for i in self.interactions]
        write(folder / 'page.json', page)
        for v in self.visuals:
            write(folder / 'visuals' / v['name'] / 'visual.json', v)


def paragraph(runs, align='left'):
    return {'textRuns': [{'value': text, 'textStyle': style} for text, style in runs], 'horizontalTextAlignment': align}


def style(font='Segoe UI', size=12, color=IVORY, bold=False, italic=False):
    s = {'fontFamily': font, 'fontSize': f'{size}pt', 'color': color}
    if bold:
        s['fontWeight'] = 'bold'
    if italic:
        s['fontStyle'] = 'italic'
    return s


def text(page, name, box, paragraphs):
    page.add(name, 'textbox', box, {'general': [{'properties': {'paragraphs': paragraphs}}]},
             {'padding': props(top=L(0), bottom=L(0), left=L(0), right=L(0))})


def svg(page, name, box, measure, entity='Artwork'):
    page.add(name, 'image', box, {
        # No imageScaling: the legacy 'Fit' value maps to stretch; the default fit keeps the aspect ratio.
        'image': [{'properties': {'sourceType': L('imageData'), 'sourceField': {'expr': ref(measure, entity, True)}}}]},
        {'padding': props(top=L(0), bottom=L(0), left=L(0), right=L(0))})


def card(page, name, box, measure, color=INK, size=24, entity='Artwork', units=1):
    page.add(name, 'card', box, {
        'labels': props(fontSize=L(size), fontFamily=L('Georgia'), color=C(color), labelDisplayUnits=L(units)),
        'categoryLabels': props(show=L(False))},
        {'padding': props(top=L(0), bottom=L(0), left=L(0), right=L(0))}, query={'Values': [proj(measure, entity, True)]})


def plaque(page, name, box, label, measure, kind='brass', units=1):
    x, y, w, h = box
    ink = {'brass': ('#4A3718', '#24190C'), 'steel': ('#47515A', '#1E252B'), 'glass': (GOLD, GOLD_LIGHT)}[kind]
    text(page, name + '_label', (x + 24, y + 10, w - 48, 18), [paragraph([(label, style('Segoe UI Semibold', 8.5, ink[0]))], 'center')])
    card(page, name, (x + 24, y + 25, w - 48, h - 31), measure, ink[1], 21 if h < 80 else 25, units=units)


def button(page, name, box, label, action, target=None, color=MUTED, hover=GOLD_LIGHT, fill=None, fill_alpha=100,
           hover_fill=GOLD, hover_alpha=86, size=10.5, outline=None, font='Segoe UI Semibold', align='center', url_measure=None, tooltip=None):
    link = {'show': L(True), 'type': L(action)}
    if target:
        link['navigationSection'] = L(target)
    if url_measure:
        link['webUrl'] = {'expr': ref(url_measure[1], url_measure[0], True)}
    if tooltip:
        link['tooltip'] = L(tooltip)
    objects = {
        'text': [{'properties': {'show': L(True)}},
                 {'properties': {'text': L(label), 'fontSize': L(size), 'fontFamily': L(font), 'fontColor': C(color), 'horizontalAlignment': L(align)}, 'selector': {'id': 'default'}},
                 {'properties': {'fontColor': C(hover)}, 'selector': {'id': 'hover'}},
                 {'properties': {'fontColor': C(hover)}, 'selector': {'id': 'selected'}}],
        'icon': [{'properties': {'show': L(False)}},
                 {'properties': {'shapeType': L('blank'), 'placement': L('left')}, 'selector': {'id': 'default'}}],
        'fill': [{'properties': {'show': L(True)}},
                 {'properties': {'fillColor': C(fill or '#000000'), 'transparency': L(fill_alpha)}, 'selector': {'id': 'default'}},
                 {'properties': {'fillColor': C(hover_fill), 'transparency': L(hover_alpha)}, 'selector': {'id': 'hover'}}],
        'shape': [{'properties': {'tileShape': L('rectangleRounded'), 'roundEdge': {'expr': {'Literal': {'Value': '3L'}}}}},
                  {'properties': {'tileShape': L('rectangleRounded')}, 'selector': {'id': 'default'}}],
    }
    if outline:
        objects['outline'] = [{'properties': {'show': L(True)}},
                              {'properties': {'lineColor': C(outline), 'weight': L(1), 'transparency': L(0)}, 'selector': {'id': 'default'}},
                              {'properties': {'lineColor': C(hover)}, 'selector': {'id': 'hover'}}]
    else:
        objects['outline'] = props(show=L(False))
    v = page.add(name, 'actionButton', box, objects, {'visualLink': [{'properties': link}]})
    v['howCreated'] = 'InsertVisualButton'


def chart_vco(title, subtitle, dark=False, tooltip_page=None):
    vco = {'title': props(show=L(True), text=L(title), fontFamily=L('Georgia'), fontSize=L(14), fontColor=C(IVORY if dark else INK)),
           'subTitle': props(show=L(True), text=L(subtitle), fontFamily=L('Segoe UI'), fontSize=L(9.5), fontColor=C(MUTED if dark else '#7A6B5C')),
           'padding': props(top=L(4), bottom=L(2), left=L(6), right=L(10))}
    if tooltip_page:
        vco['visualTooltip'] = props(show=L(True), type=L('Canvas'), section=L(tooltip_page))
    return vco


def axis_objects(fill, ink=INK, units=0, label_color=None, value_labels=True, size=9):
    o = {'dataPoint': props(fill=C(fill)),
         'categoryAxis': props(show=L(True), labelColor=C(ink), fontSize=L(size), fontFamily=L('Segoe UI'), showAxisTitle=L(False), gridlineShow=L(False)),
         'valueAxis': props(show=L(False), gridlineShow=L(False)),
         'legend': props(show=L(False))}
    if value_labels:
        o['labels'] = props(show=L(True), color=C(label_color or ink), fontSize=L(8), fontFamily=L('Segoe UI'), labelDisplayUnits=L(units))
    return o


def slicer(page, name, box, column, label, sync, light=False, entity='Artwork', search=False):
    head, item_ink, item_bg = (('#47515A', '#1E252B', '#FFFFFF') if light else (GOLD, IVORY, '#1C1512'))
    objects = {
        'data': props(mode=L('Dropdown')),
        'header': props(show=L(True), text=L(label), fontColor=C(head), fontFamily=L('Segoe UI Semibold'), textSize=L(8.5)),
        'items': props(fontColor=C(item_ink), background=C(item_bg), fontFamily=L('Segoe UI'), textSize=L(10)),
        'selection': props(selectAllCheckboxEnabled=L(True))}
    if search:  # a find-as-you-type picker for one artwork or artist
        objects['selection'] = props(singleSelect=L(True))
        objects['general'] = props(selfFilterEnabled=L(True))
    page.add(name, 'slicer', box, objects, {'padding': props(top=L(4), bottom=L(2), left=L(8), right=L(8))},
             query={'Values': [proj(column, entity, label=label)]}, sync=sync)


def Li(value):
    return {'expr': {'Literal': {'Value': f'{value}L'}}}


def tabs(page, name, box, column, label_measure, entity='Gallery', count=10):
    """Gallery wing tabs: a button slicer with rounded-top tiles and the artwork count under each era."""
    state = lambda sid, **kw: {'properties': kw, 'selector': {'id': sid}}
    objects = {
        'layout': props(orientation=Li(2), maxTiles=Li(count), rowCount=Li(1), columnCount=Li(count), autoGrid=L(False), cellPadding=Li(6)),
        'shapeCustomRectangle': props(tileShape=L('tabRoundTopCorners'), rectangleRoundedCurve=Li(12)),
        'selection': props(singleSelect=L(True), strictSingleSelect=L(False), selectAllCheckboxEnabled=L(False)),
        'selectionIcon': props(show=L(False)),
        'padding': [state('default', paddingSelection=L('Custom'), leftMargin=Li(3), rightMargin=Li(3), topMargin=Li(6), bottomMargin=Li(4))],
        'value': [state('default', show=L(True), fontColor=C('#E9DFCE'), fontFamily=L('Georgia'), fontSize=L(10.5), horizontalAlignment=L('center')),
                  state('interaction:hover', fontColor=C(GOLD_LIGHT)),
                  state('selection:selected', fontColor=C(INK))],
        'label': [state('default', show=L(True), fontColor=C('#A99B86'), fontFamily=L('Segoe UI'), fontSize=L(8.5), position=L('belowValue'), horizontalAlignment=L('center')),
                  state('selection:selected', fontColor=C(OXBLOOD))],
        'fillCustom': [state('default', show=L(True), fillColor=C('#120D0B'), transparency=L(25)),
                       state('interaction:hover', fillColor=C('#3A2A1E'), transparency=L(10)),
                       state('selection:selected', fillColor=C('#FBF7EE'), transparency=L(0))],
        'outline': [state('default', show=L(True), lineColor=C('#6A5236'), weight=L(1), transparency=L(0)),
                    state('selection:selected', lineColor=C(GOLD))],
        'accentBar': [state('default', show=L(False)),
                      state('selection:selected', show=L(True), position=L('Top'), color=C(GOLD), width=L(4))],
    }
    page.add(name, 'advancedSlicerVisual', box, objects, {'padding': props(top=L(0), bottom=L(0), left=L(0), right=L(0))},
             query={'Values': [proj(column, entity, label='Dönem')], 'Label': [proj(label_measure, 'Gallery', True)]})


def table_style(mat=MAT, alt='#F1EADC', grid='#E3D8C5', size=10, pad=5, header=True, header_color='#7A6B5C'):
    return {
        'columnHeaders': props(show=L(header), fontColor=C(header_color), backColor=C(mat), fontFamily=L('Segoe UI Semibold'), fontSize=L(9), wordWrap=L(True)),
        'values': props(fontColorPrimary=C(INK), backColorPrimary=C(mat), fontColorSecondary=C(INK), backColorSecondary=C(alt),
                        fontSize=L(size), fontFamily=L('Segoe UI'), wordWrap=L(True)),
        'grid': props(gridVertical=L(False), gridHorizontal=L(True), gridHorizontalColor=C(grid), outlineColor=C(mat), rowPadding=L(pad)),
        'total': props(totals=L(False))}


def data_bar(query_ref, color):
    return {'properties': {'dataBars': {'positiveColor': C(color), 'negativeColor': C(OXBLOOD), 'axisColor': C('#B9AA88'),
                                        'reverseDirection': L(False), 'hideText': L(False)}}, 'selector': {'metadata': query_ref}}


def not_in(name, column, values):
    return {'name': name, 'field': ref(column), 'type': 'Categorical',
            'filter': {'Version': 2, 'From': [{'Name': 'a', 'Entity': 'Artwork', 'Type': 0}],
                       'Where': [{'Condition': {'Not': {'Expression': {'In': {
                           'Expressions': [{'Column': {'Expression': {'SourceRef': {'Source': 'a'}}, 'Property': column}}],
                           'Values': [[{'Literal': {'Value': "'" + v + "'"}}] for v in values]}}}}}]}}


# ----------------------------------------------------------------------------- layout

ROOMS = [  # page id, nav label, eyebrow, wall colour, numeral
    ('lobby', 'Büyük Salon', None, '#1A1411', ''),
    ('overview', 'I · Koleksiyon', 'GALERİ I  ·  KOLEKSİYONUN HARİTASI', '#5A1B1F', 'I'),
    ('departments', 'II · Departmanlar', 'GALERİ II  ·  KANATLAR VE DEPARTMANLAR', '#1C3244', 'II'),
    ('periods', 'III · Zaman', 'GALERİ III  ·  ZAMANIN KORİDORU', '#2F3B2C', 'III'),
    ('digital_gallery', 'IV · Başyapıtlar', 'GALERİ IV  ·  BAŞYAPITLAR SALONU', '#251B20', 'IV'),
]
REMOVED_PAGES = ['collection_explorer', 'quality']  # night tour and conservation lab, retired 2026-10-12
NAV_W = 168
NAV_X = 1392 - len(ROOMS) * NAV_W
NAV = {r[0]: (NAV_X + i * NAV_W, NAV_W) for i, r in enumerate(ROOMS)}
ORDER = [r[0] for r in ROOMS]
LABEL = {r[0]: r[1] for r in ROOMS}

SLICER_BOXES = [(840, 74, 268, 56), (1124, 74, 268, 56), (840, 136, 268, 56), (1124, 136, 268, 56)]
PLAQUES = [(48 + i * 342, 210, 318, 86) for i in range(4)]
FRAME = 25  # mat margin 14 + frame 11


def common(page, room, wall, light=False):
    """Navigation band, room header and baseboard navigation shared by gallery pages."""
    for pid, label, *_ in ROOMS:
        x, w = NAV[pid]
        active = pid == page.name
        button(page, f'nav_{pid}', (x, 2, w, 40), label, 'PageNavigation', pid,
               color=GOLD_LIGHT if active else '#E2D8C7', size=10, tooltip=f'{label} salonuna git')
    i = ORDER.index(page.name)
    if room:
        prev_id, next_id = ORDER[i - 1], ORDER[(i + 1) % len(ORDER)]
        ink = '#C9CED3' if light else MUTED  # the baseboard is dark on every page
        button(page, 'reset_filters', (838, 860, 196, 38), '↺  Filtreleri temizle', 'ClearAllSlicers', color=ink, size=9.5, font='Segoe UI')
        button(page, 'prev_room', (1040, 860, 172, 38), '‹  ' + LABEL[prev_id], 'PageNavigation', prev_id, color=ink, size=9.5, font='Segoe UI')
        button(page, 'next_room', (1218, 860, 176, 38), LABEL[next_id] + '  ›', 'PageNavigation', next_id, color=ink, size=9.5, font='Segoe UI')


def footer(page, note, light=False):
    text(page, 'footer_note', (48, 871, 780, 20), [paragraph([(note, style('Segoe UI', 8.5, '#AEB5BC' if light else '#A99B86'))])])


def header(page, title, narrative_measure, light=False, entity='Artwork'):
    text(page, 'title', (44, 90, 780, 52), [paragraph([(title, style('Georgia', 29, '#1F2328' if light else IVORY))])])
    svg(page, 'narrative', (48, 144, 770, 58), narrative_measure, entity)


def wall_base(room, numeral, wall, spots, light=False, warm='#FFE2AE', nav=True):
    w = art.Wall(wall, seed=sum(map(ord, room)), top_gain=0.05 if light else 0.08,
                 bottom_gain=-0.08 if light else -0.24, vignette=0.06 if light else 0.18)
    for s in spots:
        w.spotlight(*s)
    return w


def finish(img, room, eyebrow, numeral, wall, light=False):
    if numeral:
        art.watermark(img, (1250 - 60 * len(numeral), 18), numeral, 300, '#FFFFFF' if not light else '#1F2328', alpha=10 if not light else 9)
    art.nav_band(img, NAV, room)
    if eyebrow:
        x = 48
        art.diamond(img, x + 3, 81, 3.2, GOLD if not light else '#8C6A2E')
        art.spaced(img, (x + 14, 74), eyebrow, 9.5, GOLD if not light else '#8C6A2E', name='segoeuib.ttf', spacing=0.22)
    art.baseboard(img, art.mix(art.rgb(wall), (0, 0, 0), 0.55) if not light else (52, 58, 64))
    return img


def frame_spots(boxes, strength=0.42):
    return [(x + w / 2, y - 10, w * 0.62, h * 0.55, strength) for x, y, w, h in boxes]


# ----------------------------------------------------------------------------- model

def add_measures(model, catalog, shown):
    gallery = gallery_table(shown)
    dims = gallery_dimensions(shown)
    names = {'Gallery'} | {d['name'] for d in dims}
    model['model']['tables'] = [t for t in model['model']['tables'] if t['name'] not in names] + [gallery] + dims
    rels = [r for r in model['model'].get('relationships', []) if r['fromTable'] != 'Gallery']
    model['model']['relationships'] = rels + [
        {'name': f'Gallery_{d["columns"][0]["name"]}', 'fromTable': 'Gallery', 'fromColumn': d['columns'][0]['name'],
         'toTable': d['name'], 'toColumn': d['columns'][0]['name']} for d in dims]
    artwork = next(t for t in model['model']['tables'] if t['name'] == 'Artwork')
    new = {}

    def m(table, name, expr, fmt=None, category=None, hidden=False):
        d = {'name': name, 'expression': expr.strip().splitlines(), 'displayFolder': FOLDER}
        if fmt:
            d['formatString'] = fmt
        if category:
            d['dataCategory'] = category
        if hidden:
            d['isHidden'] = True
        new.setdefault(table['name'], []).append(d)

    top = lambda col, measure='[Artwork Count]': f'TOPN(1, VALUES({col}), {measure}, DESC, {col}, ASC)'
    m(artwork, 'Narrative Overview', narrative(
        ['Bu rotada '] + em(num('n')) + [' eser var; kamu malı payı '] + em(pct('pd')) +
        ['. En kalabalık kanat '] + em('topName') + [' — tüm departmanlar içindeki payı '] + em(pct('topShare')) + ['.'],
        f"""VAR n = [Artwork Count]
VAR pd = [Public Domain Share]
VAR topD = {top('Artwork[department]')}
VAR topName = COALESCE(MAXX(topD, Artwork[department]), "—")
VAR topShare = CALCULATE([Department Share], topD)
"""), category='ImageUrl')
    m(artwork, 'Narrative Departments', narrative(
        ['Galeri numarası en sık kayıtlı kanat '] + em('hiName') + [' ('] + em(pct('hiShare')) + ['), en seyrek '] + em('loName') +
        [' ('] + em(pct('loShare')) + ['). Galeri numarası, eserin şu an sergilendiğini kanıtlamaz.'],
        """VAR t = FILTER(ADDCOLUMNS(VALUES(Artwork[department]), "@g", [Gallery Information Share]), NOT ISBLANK([@g]))
VAR hi = TOPN(1, t, [@g], DESC, Artwork[department], ASC)
VAR lo = TOPN(1, t, [@g], ASC, Artwork[department], ASC)
VAR hiName = COALESCE(MAXX(hi, Artwork[department]), "—")
VAR loName = COALESCE(MAXX(lo, Artwork[department]), "—")
VAR hiShare = MAXX(hi, [@g])
VAR loShare = MAXX(lo, [@g])
"""), category='ImageUrl')
    m(artwork, 'Narrative Periods', narrative(
        ['En kalabalık dönem '] + em('topName') + [' ('] + em(num('busiestCount')) + [' eser). Başlangıç yılı 1900 öncesi eserlerde kamu malı payı '] +
        em(pct('oldPD')) + [', 1900 ve sonrasında '] + em(pct('newPD')) + ['.'],
        f"""VAR topP = {top('Artwork[timeline_period]')}
VAR topName = COALESCE(MAXX(topP, Artwork[timeline_period]), "—")
VAR busiestCount = CALCULATE([Artwork Count], topP)
VAR oldPD = CALCULATE([Public Domain Share], KEEPFILTERS(Artwork[object_begin_date] < 1900))
VAR newPD = CALCULATE([Public Domain Share], KEEPFILTERS(Artwork[object_begin_date] >= 1900))
"""), category='ImageUrl')
    m(artwork, 'Top Culture', """
VAR t = FILTER(VALUES(Artwork[culture]), NOT ISBLANK(Artwork[culture]) && NOT (TRIM(Artwork[culture]) IN {"", "Unknown"}))
RETURN MAXX(TOPN(1, t, [Artwork Count], DESC, Artwork[culture], ASC), Artwork[culture])""")
    tooltip_html = (["<div style='padding:16px 20px;font-family:Segoe UI;color:#2A211B'>",
                     f"<div style='font-size:9px;letter-spacing:2.2px;color:{OXBLOOD};font-weight:600'>DEPARTMAN · MÜZE ETİKETİ</div>",
                     "<div style='font-family:Georgia;font-size:19px;line-height:1.2;margin-top:6px;height:46px;overflow:hidden'>", ('dax', 'd'), '</div>',
                     f"<div style='height:1px;background:{GOLD};margin:8px 0 10px'></div>",
                     "<table style='width:100%;border-collapse:collapse;font-size:10px;color:#6E6052'><tr>"])
    for i, (lab, v) in enumerate([('Eser', num('n')), ('Kamu malı payı', pct('pd')), ('Galeri bilgisi payı', pct('gi')), ('Öne çıkan eser', num('hl'))]):
        tooltip_html += [f"<td style='width:50%;padding:0 0 9px'>{lab}<br/><span style='font-family:Georgia;font-size:19px;color:#2A211B'>",
                         ('dax', v), '</span></td>' + ('</tr><tr>' if i == 1 else '')]
    tooltip_html += ["</tr></table><div style='font-size:10px;color:#6E6052'>En yaygın kültür: <i style='color:#2A211B;font-family:Georgia'>", ('dax', 'cult'), '</i></div></div>']
    m(artwork, 'Tooltip Label SVG', svg_measure(360, 230, tooltip_html, 'margin:0;background:#FBF7EE;height:226px;border:2px solid #C9A45C;box-sizing:border-box',
        """VAR d = IF(HASONEVALUE(Artwork[department]), VALUES(Artwork[department]), "Seçili departmanlar")
VAR n = [Artwork Count]
VAR pd = [Public Domain Share]
VAR gi = [Gallery Information Share]
VAR hl = COALESCE([Highlight Artwork Count], 0)
VAR cult = COALESCE([Top Culture], "kayıtlı değil")
"""), category='ImageUrl')

    m(artwork, 'Period Material Share', """
DIVIDE([Artwork Count], CALCULATE([Artwork Count], REMOVEFILTERS(Artwork[object_type_material])))""", '0.0%')
    m(artwork, 'Heat Fill', """
VAR s = [Period Material Share]
RETURN SWITCH(TRUE(), ISBLANK(s), "#F7F2E8", s < 0.01, "#F2EADB", s < 0.025, "#EADBC0", s < 0.05, "#E0C796",
    s < 0.10, "#D3AC68", s < 0.15, "#C08A48", s < 0.25, "#A2603A", s < 0.35, "#83402F", "#5A1B1F")""", hidden=True)
    m(artwork, 'Heat Ink', 'IF([Period Material Share] >= 0.15, "#FBF6EC", "#2A211B")', hidden=True)

    # Gallery: the best-known highlight artworks with an image in each era. With nothing selected,
    # the wall shows the best-known artwork in view (first ranks first, then most Wikipedia languages).
    m(gallery, 'Gallery Artwork Count', 'COUNTROWS(Gallery)', '#,0')
    m(gallery, 'Gallery Image Count', 'CALCULATE(COUNTROWS(Gallery), Gallery[image_url] <> "")', '#,0')
    m(gallery, 'Gallery Tab Label', 'FORMAT(COALESCE(COUNTROWS(Gallery), 0), "#,0") & " eser"', hidden=True)
    m(gallery, 'Gallery Default ID', """
VAR best = MINX(TOPN(1, FILTER(Gallery, Gallery[image_url] <> ""), Gallery[era_rank], ASC, Gallery[wikipedia_languages], DESC, Gallery[object_id], ASC), Gallery[object_id])
RETURN COALESCE(best, MIN(Gallery[object_id]))""", hidden=True)
    # A row picked in one era stays selected when another tab is chosen; the selection then leaves
    # nothing in view, so fall back to the era's default instead of an empty wall.
    # Tabs and the department and type pickers filter Gallery through their own small tables, so removing
    # every Gallery filter keeps the room's era and department (auto-exist would otherwise merge
    # a stale row selection with them into an empty filter).
    m(gallery, 'Selected Gallery ID', """
VAR one = IF(HASONEVALUE(Gallery[object_id]), VALUES(Gallery[object_id]))
VAR picked = COALESCE(one, [Gallery Default ID])
VAR withoutPick = CALCULATE([Gallery Default ID], REMOVEFILTERS(Gallery[era_rank], Gallery[thumb_url], Gallery[title], Gallery[begin_year]))
VAR roomDefault = CALCULATE([Gallery Default ID], REMOVEFILTERS(Gallery))
RETURN COALESCE(picked, withoutPick, roomDefault)""", hidden=True)
    m(gallery, 'Selected Gallery Image', f"""
VAR selId = [Selected Gallery ID]
VAR link = MAXX(FILTER(ALL(Gallery), Gallery[object_id] = selId), Gallery[image_url])
RETURN IF(ISBLANK(selId), BLANK(), IF(link = "", {dax_str(PLACEHOLDER)}, link))""", category='ImageUrl')
    for name, col in [('Selected Met URL', 'met_url'), ('Selected Artist Wiki URL', 'artist_wiki_url'), ('Selected Object Wiki URL', 'object_wiki_url')]:
        m(gallery, name, f"""
VAR selId = [Selected Gallery ID]
VAR link = MAXX(FILTER(ALL(Gallery), Gallery[object_id] = selId), Gallery[{col}])
RETURN IF(link = "", BLANK(), link)""", category='WebUrl')
    pick = 'VAR selId = [Selected Gallery ID]\nVAR r = FILTER(ALL(Gallery), Gallery[object_id] = selId)\n'
    m(gallery, 'Gallery Frame SVG', pick + f"""VAR sx = MAXX(r, Gallery[sight_x])
VAR sy = MAXX(r, Gallery[sight_y])
VAR sw = MAXX(r, Gallery[sight_w])
VAR sh = MAXX(r, Gallery[sight_h])
RETURN IF(ISBLANK(selId), BLANK(), IF(MAXX(r, Gallery[kind]) = "painting",
    {frame_dax(*HERO_BOX[2:], 'painting')},
    {frame_dax(*HERO_BOX[2:], 'object')}))""", category='ImageUrl')
    m(gallery, 'Gallery Wall Label SVG', pick + """VAR title = MAXX(r, Gallery[title])
VAR dateValue = MAXX(r, Gallery[date])
VAR dateText = IF(dateValue = "", "", ", " & dateValue)
VAR artist = MAXX(r, Gallery[artist])
VAR bio = MAXX(r, Gallery[artist_bio])
VAR galleryNo = MAXX(r, Gallery[gallery_number])
VAR flags = IF(galleryNo = "", "GALERİ BİLGİSİ YOK", "GALERİ " & galleryNo) & " · " & UPPER(MAXX(r, Gallery[era]))
    & IF(MAXX(r, Gallery[image_url]) = "", " · GÖRSEL PAYLAŞILAMIYOR", "")
VAR langs = MAXX(r, Gallery[wikipedia_languages])
VAR fame = "DÖNEMİNDE " & MAXX(r, Gallery[era_rank]) & ". SIRA · "
    & IF(langs > 0, langs & " DİLDE WIKIPEDIA MADDESİ", "WIKIPEDIA MADDESİ YOK")
VAR sizeText = MAXX(r, Gallery[size_cm])
VAR medium = MAXX(r, Gallery[medium]) & IF(sizeText = "", "", " · " & sizeText)
VAR cultureText = MAXX(r, Gallery[culture])
VAR dept = MAXX(r, Gallery[department]) & IF(cultureText = "", "", " · " & cultureText)
VAR credit = MAXX(r, Gallery[credit_line])
VAR acc = MAXX(r, Gallery[accession_number])
VAR ts = IF(LEN(title) < 40, "20", IF(LEN(title) < 75, "17", "14.5"))
RETURN IF(ISBLANK(selId), BLANK(),
    """ + dax_concat(label_parts(*LABEL_SIZE, wall_label_html())) + ')', category='ImageUrl')
    m(gallery, 'Narrative Gallery', narrative(
        em('scopeName') + ['  ·  en bilinen '] + em(num('n')) + [' başyapıt, Wikipedia dil sayısına göre. Bir esere tıkla.'],
        """VAR scopeName = IF(HASONEVALUE('Gallery Era'[era]), VALUES('Gallery Era'[era]), "Tüm dönemler")
VAR n = COALESCE(COUNTROWS(Gallery), 0)
"""), category='ImageUrl')
    lobby = next(a for a in catalog if a['object_id'] == LOBBY_ARTWORK)
    m(gallery, 'Lobby Artwork Image', dax_str(lobby['image_url']), category='ImageUrl')
    m(gallery, 'Lobby Frame SVG', dax_str(frame_svg(*LOBBY_BOX[2:], LOBBY_PAD, lobby['pixels'])), category='ImageUrl')

    for table in (artwork, gallery):
        names = {d['name'] for d in new.get(table['name'], [])} | set(RETIRED_MEASURES)
        table['measures'] = [x for x in table.get('measures', []) if x['name'] not in names] + new.get(table['name'], [])
    return sum(len(v) for v in new.values())


RETIRED_MEASURES = ['Narrative Quality', 'Narrative Explorer']  # their pages were removed
TOP_PER_ERA = 50  # artworks per era in the Masterpieces room (ranked by fetch_highlights.py)
HERO_BOX, HERO_PAD = (436, 284, 584, 562), 46
LABEL_BOX = (1044, 284, 348, 392)
LABEL_SIZE = LABEL_BOX[2:]
LOBBY_BOX, LOBBY_PAD = (676, 78, 716, 704), 52
LOBBY_ARTWORK = 436535  # Wheat Field with Cypresses

PLACEHOLDER_INFO = (480, 600, 0, 0, 0, 0)
PLACEHOLDER = 'data:image/svg+xml;utf8,' + enc(
    "<svg xmlns='http://www.w3.org/2000/svg' width='480' height='600' viewBox='0 0 480 600'>"
    "<defs><radialGradient id='g' cx='50%' cy='38%' r='75%'><stop offset='0' stop-color='#F4EDE0'/><stop offset='1' stop-color='#D9CDB8'/></radialGradient></defs>"
    "<rect width='480' height='600' fill='url(#g)'/>"
    "<rect x='170' y='170' width='140' height='110' fill='none' stroke='#A7967B' stroke-width='3'/>"
    "<path d='M182 266 L222 222 L248 248 L268 230 L298 266 Z' fill='#BFAF93'/><circle cx='280' cy='198' r='11' fill='#BFAF93'/>"
    "<text x='240' y='336' text-anchor='middle' font-family='Georgia' font-size='25' fill='#4A3F35'>Görsel açık erişimde değil</text>"
    "<text x='240' y='372' text-anchor='middle' font-family='Segoe UI' font-size='14.5' fill='#6E6052'>The Met bu eser için açık erişim görseli yayımlamıyor.</text>"
    "<text x='240' y='394' text-anchor='middle' font-family='Segoe UI' font-size='14.5' fill='#6E6052'>Eseri sağdaki “The Met eser sayfası” bağlantısında görün.</text>"
    "</svg>")
THUMB_PLACEHOLDER = 'data:image/svg+xml;utf8,' + enc(
    "<svg xmlns='http://www.w3.org/2000/svg' width='64' height='52' viewBox='0 0 64 52'>"
    "<rect width='64' height='52' fill='#E9E1D2'/><rect x='19' y='13' width='26' height='20' fill='none' stroke='#A7967B' stroke-width='1.5'/>"
    "<path d='M21 31 L28 23 L33 28 L37 25 L43 31 Z' fill='#BFAF93'/><text x='32' y='45' text-anchor='middle' font-family='Segoe UI' font-size='7' fill='#7A6B5C'>görsel yok</text></svg>")

# Gallery table columns: name, model data type, extra column properties.
GALLERY_COLUMNS = [
    ('object_id', 'int64', {}), ('title', 'string', {}), ('artist', 'string', {}), ('artist_bio', 'string', {}),
    ('culture', 'string', {}), ('date', 'string', {}), ('begin_year', 'int64', {'formatString': '0;"MÖ "0'}),
    ('era', 'string', {'sortByColumn': 'era_order'}), ('era_order', 'int64', {'isHidden': True}),
    ('department', 'string', {}), ('kind', 'string', {'isHidden': True}), ('medium', 'string', {}), ('size_cm', 'string', {}),
    ('credit_line', 'string', {}), ('accession_number', 'string', {}), ('gallery_number', 'string', {}),
    ('kind_label', 'string', {}), ('era_rank', 'int64', {}), ('wikipedia_languages', 'int64', {}),
    ('artist_wikipedia_languages', 'int64', {'isHidden': True}), ('image_url', 'string', {'dataCategory': 'ImageUrl'}),
    ('thumb_url', 'string', {'dataCategory': 'ImageUrl'}), ('met_url', 'string', {'dataCategory': 'WebUrl'}),
    ('artist_wiki_url', 'string', {'dataCategory': 'WebUrl'}), ('object_wiki_url', 'string', {'dataCategory': 'WebUrl'}),
    ('sight_x', 'double', {'isHidden': True}), ('sight_y', 'double', {'isHidden': True}),
    ('sight_w', 'double', {'isHidden': True}), ('sight_h', 'double', {'isHidden': True}),
]


M_TYPES = {'int64': 'Int64.Type', 'double': 'type number', 'string': 'type text'}
KIND_LABELS = {'painting': 'Resim', 'object': 'Obje'}


def m_literal(value):
    return str(value) if isinstance(value, int) else '"' + str(value).replace('"', '""') + '"'


def m_table(name, cols, rows, description):
    """A small import table written out as an M #table literal."""
    names = '{' + ', '.join(f'"{c}"' for c, *_ in cols) + '}'
    body = '{' + ', '.join('{' + ', '.join(m_literal(v) for v in row) + '}' for row in rows) + '}'
    types = '{' + ', '.join(f'{{"{c}", {M_TYPES[t]}}}' for c, t, _ in cols) + '}'
    columns = [{'name': c, 'dataType': t, 'sourceColumn': c, 'summarizeBy': 'none', **extra} for c, t, extra in cols]
    expr = ['let', f'    Rows = #table({names}, {body}),', f'    Typed = Table.TransformColumnTypes(Rows, {types})', 'in', '    Typed']
    return {'name': name, 'columns': columns, 'description': description,
            'partitions': [{'name': name, 'mode': 'import', 'source': {'type': 'm', 'expression': expr}}]}


def gallery_dimensions(shown):
    """Lookup tables for the era tabs and the department and type pickers. Filtering Gallery through
    them keeps the tabs from merging with a stale artwork selection (auto-exist) into an empty page."""
    eras = sorted({(a['era'], a['era_order']) for a in shown}, key=lambda e: e[1])
    return [m_table('Gallery Era', [('era', 'string', {'sortByColumn': 'era_order'}), ('era_order', 'int64', {'isHidden': True})],
                    eras, 'Era tabs of the Masterpieces room.'),
            m_table('Gallery Department', [('department', 'string', {})], [[d] for d in sorted({a['department'] for a in shown})],
                    'Department picker of the Masterpieces room.'),
            m_table('Gallery Type', [('kind_label', 'string', {})], [[k] for k in sorted({KIND_LABELS[a['kind']] for a in shown})],
                    'Painting/object picker of the Masterpieces room.')]


def gallery_table(catalog):
    """The masterpiece catalogue as a self-contained import table (compressed JSON inside M, like
    Power BI's own Enter data), so the report needs no file path and no API call to refresh it."""
    rows = []
    for a in catalog:
        info = a['pixels'] if a['image_url'] and a.get('pixels') else PLACEHOLDER_INFO
        sight = sight_rect(*HERO_BOX[2:], HERO_PAD, info)
        row = {k: a.get(k) for k, *_ in GALLERY_COLUMNS if k in a}
        row.update({'kind_label': KIND_LABELS[a['kind']],
                    # a comment keeps each placeholder unique, so table rows never merge
                    'thumb_url': a['image_url'] or THUMB_PLACEHOLDER + enc(f"<!--{a['object_id']}-->"),
                    'sight_x': round(sight[0], 2), 'sight_y': round(sight[1], 2), 'sight_w': round(sight[2], 2), 'sight_h': round(sight[3], 2)})
        rows.append([row.get(k) for k, *_ in GALLERY_COLUMNS])
    packer = zlib.compressobj(9, zlib.DEFLATED, -15)
    raw = packer.compress(json.dumps(rows, ensure_ascii=False, separators=(',', ':')).encode('utf-8')) + packer.flush()
    blob = base64.b64encode(raw).decode('ascii')
    names = '{' + ', '.join(f'"{k}"' for k, *_ in GALLERY_COLUMNS) + '}'
    types = '{' + ', '.join(f'{{"{k}", {M_TYPES[t]}}}' for k, t, _ in GALLERY_COLUMNS) + '}'
    m = ['let',
         f'    Source = Json.Document(Binary.Decompress(Binary.FromText("{blob}", BinaryEncoding.Base64), Compression.Deflate)),',
         f'    Rows = Table.FromRows(Source, {names}),',
         f'    Typed = Table.TransformColumnTypes(Rows, {types})',
         'in',
         '    Typed']
    columns = []
    for name, dtype, extra in GALLERY_COLUMNS:
        col = {'name': name, 'dataType': dtype, 'sourceColumn': name, 'summarizeBy': 'none'}
        col.update(extra)
        columns.append(col)
    return {'name': 'Gallery', 'columns': columns, 'measures': [],
            'partitions': [{'name': 'Gallery', 'mode': 'import', 'source': {'type': 'm', 'expression': m}}],
            'description': f'The {TOP_PER_ERA} best-known highlight artworks with an open-access image in each era ({len(rows)} rows), '
                           'ranked by the number of Wikipedia languages about the artwork, then its artist (Wikidata). '
                           'Met Collection API images and wall-label details. Independent of full-collection totals; '
                           'see highlights-catalog.json for the snapshot date.'}


# ----------------------------------------------------------------------------- pages

def build_lobby(bgs):
    room, wall = 'lobby', '#1A1411'
    hero_frame = (LOBBY_BOX[0] + LOBBY_BOX[2] / 2, LOBBY_BOX[1] + 40, LOBBY_BOX[2] * 0.62, LOBBY_BOX[3] * 0.58, 0.95)
    w = wall_base(room, '', wall, [hero_frame, (330, 150, 420, 260, 0.20)])
    w.beam(LOBBY_BOX[0] + LOBBY_BOX[2] / 2, 64, inset(LOBBY_BOX, 60), 0.12)
    img = w.render()
    art.nav_band(img, NAV, room)
    art.diamond(img, 51, 97, 3.2)
    art.spaced(img, (62, 90), 'THE METROPOLITAN MUSEUM OF ART  ·  AÇIK ERİŞİM KOLEKSİYONU', 8.8, GOLD, name='segoeuib.ttf', spacing=0.2)
    art.rule(img, 48, 632, 300, alpha=120)
    plaques = [(48, 318, 284, 76), (348, 318, 284, 76), (48, 406, 284, 76), (348, 406, 284, 76)]
    for p in plaques:
        art.brass(img, p)
    art.spaced(img, (48, 554), 'KAT PLANI  ·  BİR SALONA TIKLAYIN', 8.8, GOLD, name='segoeuib.ttf', spacing=0.22)
    rooms = [(48 + i * 300, 576, 284, 76) for i in range(2)] + [(48 + i * 300, 750, 284, 76) for i in range(2)]
    hall = (48, 664, 584, 74)
    art.floor_plan(img, rooms, hall)
    art.spaced(img, (340, 690), 'BÜYÜK SALON', 10, IVORY, spacing=0.3, anchor='m')
    d = art.ImageDraw.Draw(img)
    cx, cy = 340 * art.S, 716 * art.S
    d.ellipse([cx - 9 * art.S, cy - 9 * art.S, cx + 9 * art.S, cy + 9 * art.S], outline=art.rgb('#D9474F'), width=art.S)
    d.ellipse([cx - 4 * art.S, cy - 4 * art.S, cx + 4 * art.S, cy + 4 * art.S], fill=art.rgb('#D9474F'))
    art.spaced(img, (356, 710), 'BURADASINIZ', 7.5, '#E9A0A4', name='segoeuib.ttf', spacing=0.25)
    art.baseboard(img, (14, 10, 9))
    art.save(img, RESOURCES / bgs['lobby'])

    p = Page('lobby', 'Büyük Salon', bgs['lobby'], wall)
    common(p, False, wall)
    text(p, 'title', (42, 104, 600, 92), [paragraph([('MET Atlas', style('Georgia', 54, IVORY))])])
    text(p, 'subtitle', (48, 194, 590, 32), [paragraph([('Sanatın veriyle keşfi', style('Georgia', 17, GOLD_LIGHT, italic=True))])])
    text(p, 'intro', (48, 232, 584, 62), [paragraph([(
        "The Met'in açık erişim koleksiyonunda bir veri turu. Her salon bir soruya ayrılmış; grafikler duvara asılı eserler gibi "
        'okunur, filtreler salondan salona sizinle gelir.', style('Segoe UI', 11, MUTED))])])
    for (name, label, measure), box in zip([('lobby_total', 'TOPLAM ESER', 'Artwork Count'), ('lobby_departments', 'DEPARTMAN', 'Department Count'),
                                            ('lobby_public', 'KAMU MALI PAYI', 'Public Domain Share'), ('lobby_highlight', 'ÖNE ÇIKAN ESER', 'Highlight Artwork Count')], plaques):
        plaque(p, name, box, label, measure)
    button(p, 'start_tour', (48, 496, 244, 44), 'Turu başlat   →', 'PageNavigation', 'overview', color='#1E150B', hover='#1E150B',
           fill=GOLD, fill_alpha=0, hover_fill=GOLD_LIGHT, hover_alpha=0, size=11.5)
    button(p, 'open_masterpieces', (304, 496, 244, 44), 'Başyapıtlara git', 'PageNavigation', 'digital_gallery', color=GOLD_LIGHT,
           outline=GOLD, size=11, font='Segoe UI')
    for box, pid in zip(rooms, ORDER[1:]):
        button(p, f'room_{pid}', box, LABEL[pid], 'PageNavigation', pid, color='#EDE3D2', hover=GOLD_LIGHT, hover_fill=GOLD,
               hover_alpha=80, size=10.5, font='Georgia', tooltip=f'{LABEL[pid]} salonuna gir')
    svg(p, 'lobby_artwork', inset(LOBBY_BOX, LOBBY_PAD), 'Lobby Artwork Image', 'Gallery')
    svg(p, 'lobby_frame', LOBBY_BOX, 'Lobby Frame SVG', 'Gallery')  # hangs over the photo's border
    text(p, 'lobby_label', (676, 790, 716, 56), [
        paragraph([('Vincent van Gogh  ·  ', style('Segoe UI Semibold', 10, IVORY)), ('Wheat Field with Cypresses', style('Georgia', 12, IVORY, italic=True)),
                   (', 1889', style('Georgia', 12, IVORY))], 'center'),
        paragraph([('Tuval üzerine yağlı boya · European Paintings · Kamu malı görsel: The Met Collection API', style('Segoe UI', 8.5, '#A99B86'))], 'center')])
    footer(p, 'The Metropolitan Museum of Art açık erişim verisi · BigQuery met_data.mart_met_objects · Bu sunum The Met tarafından hazırlanmamıştır.')
    return p


def room_background(room, bgs, wall, frames, plaques=PLAQUES, slicers=SLICER_BOXES, light=False, frame_kw=None, plaque_kind='brass', extra=None):
    eyebrow = next(r[2] for r in ROOMS if r[0] == room)
    numeral = next(r[4] for r in ROOMS if r[0] == room)
    spots = frame_spots([inset(f, -FRAME) for f in frames], 0.32 if light else 0.48)
    spots += [(x + w / 2, y - 6, w * 0.7, h * 1.2, 0.18 if not light else 0.06) for x, y, w, h in plaques]
    w = wall_base(room, numeral, wall, spots, light)
    img = w.render('#FFFFFF' if light else '#FFE2AE')
    if light:
        art.blueprint(img)
    finish(img, room, eyebrow, numeral, wall, light)
    for box in slicers:
        art.pedestal(img, box, fill='#FFFFFF' if light else '#000000', alpha=150 if light else 95, line='#8C6A2E' if light else GOLD)
    for box in plaques:
        art.brass(img, box, plaque_kind)
    for box in frames:
        art.framed(img, box, **(frame_kw or {}))
    if extra:
        extra(img)
    art.save(img, RESOURCES / bgs[room])


def build_overview(bgs):
    wall = '#5A1B1F'
    A, B, Cc = (73, 339, 614, 482), (761, 339, 606, 206), (761, 615, 606, 206)
    room_background('overview', bgs, wall, [A, B, Cc])
    p = Page('overview', LABEL['overview'], bgs['overview'], wall)
    common(p, True, wall)
    header(p, 'Koleksiyonun haritası', 'Narrative Overview')
    slicers(p)
    for (name, label, measure), box in zip([('total_card', 'TOPLAM ESER', 'Artwork Count'), ('department_card', 'DEPARTMAN', 'Department Count'),
                                            ('public_card', 'KAMU MALI PAYI', 'Public Domain Share'), ('highlight_card', 'ÖNE ÇIKAN ESER', 'Highlight Artwork Count')], PLAQUES):
        plaque(p, name, box, label, measure)
    p.add('department_chart', 'barChart', A, axis_objects(OXBLOOD, units=1000), chart_vco('Departmanlara göre eser', 'Eser sayısı · çubuğa gelince müze etiketi açılır', tooltip_page='tooltip_department'),
          {'Category': [proj('department')], 'Y': [proj('Artwork Count', measure=True, label='Eser')]}, sort=(ref('Artwork Count', measure=True), 'Descending'), header=True)
    p.add('period_chart', 'clusteredColumnChart', B, axis_objects('#B8893A', units=1000, size=8), chart_vco('Zaman çizgisi', 'Başlangıç yılına göre dönem'),
          {'Category': [proj('timeline_period')], 'Y': [proj('Artwork Count', measure=True, label='Eser')]}, sort=(ref('timeline_period'), 'Ascending'), header=True)
    p.add('material_chart', 'treemap', Cc, {'labels': props(show=L(True), color=C('#FBF6EC'), fontSize=L(9), labelDisplayUnits=L(1000)),
                                            'categoryLabels': props(show=L(True), color=C('#FBF6EC'), fontSize=L(9)), 'legend': props(show=L(False))},
          chart_vco('Tür ve malzeme mozaiği', 'Alan = eser sayısı'), {'Group': [proj('object_type_material', label='Tür / malzeme')], 'Values': [proj('Artwork Count', measure=True, label='Eser')]}, header=True)
    footer(p, 'Sayımlar eser kimliğine (object_id) göre tekildir. Galeri bilgisi güncel sergilenme durumunu kanıtlamaz.')
    return p


def slicers(p, light=False):
    for box, (name, column, label, group) in zip(SLICER_BOXES, [
            ('department_filter', 'department', 'DEPARTMAN', 'sync_department'), ('period_filter', 'timeline_period', 'DÖNEM', 'sync_period'),
            ('type_filter', 'object_type_material', 'TÜR / MALZEME', 'sync_material'), ('domain_filter', 'is_public_domain', 'KAMU MALI', 'sync_public_domain')]):
        slicer(p, name, box, column, label, group, light)


def build_departments(bgs):
    wall = '#1C3244'
    A, B = (73, 339, 542, 482), (689, 339, 678, 482)
    room_background('departments', bgs, wall, [A, B])
    p = Page('departments', LABEL['departments'], bgs['departments'], wall)
    common(p, True, wall)
    header(p, 'Kanatlar ve departmanlar', 'Narrative Departments')
    slicers(p)
    for (name, label, measure), box in zip([('total_card', 'FİLTRELENEN ESER', 'Artwork Count'), ('gallery_card', 'GALERİ BİLGİSİ OLAN', 'Artwork With Gallery Information'),
                                            ('gallery_share_card', 'GALERİ BİLGİSİ PAYI', 'Gallery Information Share'), ('highlight_share_card', 'ÖNE ÇIKAN PAYI', 'Highlight Share')], PLAQUES):
        plaque(p, name, box, label, measure)
    p.add('share_chart', 'barChart', A, axis_objects('#2F5266'), chart_vco('Koleksiyondaki pay', 'Payda: departman filtresi dışındaki aynı filtreler', tooltip_page='tooltip_department'),
          {'Category': [proj('department')], 'Y': [proj('Department Share', measure=True, label='Pay')]}, sort=(ref('Department Share', measure=True), 'Descending'), header=True)
    objects = table_style()
    objects['columnFormatting'] = [data_bar('Artwork.Artwork Count', '#D9C39A'), data_bar('Artwork.Public Domain Share', '#C9D3C2'),
                                   data_bar('Artwork.Gallery Information Share', '#C7D3DE'), data_bar('Artwork.Highlight Share', '#E6C9C4')]
    p.add('department_table', 'tableEx', B, objects, chart_vco('Departman karşılaştırması', 'Hücre çubukları aynı sütundaki değerlere göre ölçeklenir'),
          {'Values': [proj('department', label='Departman'), proj('Artwork Count', measure=True, label='Eser'), proj('Public Domain Share', measure=True, label='Kamu malı'),
                      proj('Gallery Information Share', measure=True, label='Galeri bilgisi'), proj('Highlight Share', measure=True, label='Öne çıkan')]},
          sort=(ref('Artwork Count', measure=True), 'Descending'), header=True)
    footer(p, 'Galeri bilgisi = galeri numarası dolu. Boş galeri numarası eserin depoda olduğunu kanıtlamaz.')
    return p


def build_periods(bgs):
    wall = '#2F3B2C'
    A, B = (73, 339, 1294, 130), (73, 539, 1294, 282)
    room_background('periods', bgs, wall, [A, B])
    p = Page('periods', LABEL['periods'], bgs['periods'], wall)
    common(p, True, wall)
    header(p, 'Zamanın koridoru', 'Narrative Periods')
    slicers(p)
    for (name, label, measure), box in zip([('total_card', 'FİLTRELENEN ESER', 'Artwork Count'), ('public_card', 'KAMU MALI PAYI', 'Public Domain Share'),
                                            ('reversed_card', 'TERS TARİH ARALIĞI', 'Reversed Date Count'), ('zero_card', 'SIFIR YIL İÇEREN', 'Zero Year Count')], PLAQUES):
        plaque(p, name, box, label, measure)
    p.add('timeline_chart', 'clusteredColumnChart', A, axis_objects('#5E7A63', units=1000, size=8.5), chart_vco('Başlangıç yılına göre koleksiyon', 'MÖ yılları korunur · dönemler eşit uzunlukta değildir'),
          {'Category': [proj('timeline_period')], 'Y': [proj('Artwork Count', measure=True, label='Eser')]}, sort=(ref('timeline_period'), 'Ascending'), header=True)
    sel = {'data': [{'dataViewWildcard': {'matchingOption': 1}}], 'metadata': 'Artwork.Period Material Share'}
    matrix = {
        'rowHeaders': props(fontColor=C(INK), backColor=C(MAT), fontFamily=L('Segoe UI Semibold'), fontSize=L(8.5), wordWrap=L(False)),
        'columnHeaders': props(fontColor=C('#5B4E40'), backColor=C(MAT), fontFamily=L('Segoe UI Semibold'), fontSize=L(7.5), wordWrap=L(True), alignment=L('Center')),
        'values': [{'properties': {'fontColorPrimary': C(INK), 'backColorPrimary': C(MAT), 'backColorSecondary': C(MAT), 'fontSize': L(7.5), 'fontFamily': L('Segoe UI')}},
                   {'properties': {'backColor': {'solid': {'color': {'expr': ref('Heat Fill', measure=True)}}},
                                   'fontColor': {'solid': {'color': {'expr': ref('Heat Ink', measure=True)}}}}, 'selector': sel}],
        'grid': props(gridVertical=L(True), gridVerticalColor=C(MAT), gridVerticalWeight=L(2), gridHorizontal=L(True), gridHorizontalColor=C(MAT), gridHorizontalWeight=L(2),
                      outlineColor=C(MAT), rowPadding=L(1)),
        'subTotals': props(rowSubtotals=L(False), columnSubtotals=L(False)),
    }
    p.add('material_heatmap', 'pivotTable', B, matrix, chart_vco('Dönem × malzeme ısı haritası', 'Hücre = dönem içindeki malzeme payı · koyu ton daha yüksek pay'),
          {'Rows': [proj('timeline_period', label='Dönem')], 'Columns': [proj('object_type_material', label='Tür / malzeme')],
           'Values': [proj('Period Material Share', measure=True, label='Dönem içi pay')]}, header=True)
    footer(p, 'Dönem, eserin başlangıç yılına göre atanır. Ters aralık ve sıfır yıl kayıtları düzeltilmeden sayılır.')
    return p


def build_gallery(bgs, shown, total, retrieved):
    wall = '#251B20'
    tab_box = (48, 206, 1344, 60)
    panel_box = (48, 284, 360, 562)
    link_y = LABEL_BOX[1] + LABEL_BOX[3] + 14

    hero_spot = (HERO_BOX[0] + HERO_BOX[2] / 2, HERO_BOX[1] + 30, HERO_BOX[2] * 0.66, HERO_BOX[3] * 0.62, 1.0)
    w = wall_base('digital_gallery', 'IV', wall, [hero_spot, (1218, 360, 260, 300, 0.30), (228, 380, 260, 340, 0.22)])
    w.beam(HERO_BOX[0] + HERO_BOX[2] / 2, 64, inset(HERO_BOX, 70), 0.14)
    img = w.render()
    finish(img, 'digital_gallery', ROOMS[4][2], 'IV', wall)
    for box in SLICER_BOXES:
        art.pedestal(img, box)
    art.rule(img, tab_box[0], tab_box[0] + tab_box[2], tab_box[1] + tab_box[3] + 1, alpha=230, width=2)
    art.panel(img, panel_box, '#FBF7EE', edge='#C9A45C', shadow_alpha=150)
    art.rule(img, 66, 390, 328, color='#C9A45C', alpha=200)
    art.save(img, RESOURCES / bgs['digital_gallery'])

    p = Page('digital_gallery', LABEL['digital_gallery'], bgs['digital_gallery'], wall)
    common(p, True, wall)
    header(p, 'Bir eserin içine gir.', 'Narrative Gallery', entity='Gallery')
    for box, (name, entity, column, label, search) in zip(SLICER_BOXES, [
            ('department_filter', 'Gallery Department', 'department', 'DEPARTMAN', False), ('title_search', 'Gallery', 'title', 'ESER ARA', True),
            ('type_filter', 'Gallery Type', 'kind_label', 'TÜR', False), ('artist_search', 'Gallery', 'artist', 'SANATÇI ARA', True)]):
        slicer(p, name, box, column, label, None, entity=entity, search=search)
    tabs(p, 'era_tabs', tab_box, 'era', 'Gallery Tab Label', entity='Gallery Era')
    text(p, 'guide_heading', (66, 294, 330, 30), [paragraph([('Eser rehberi', style('Georgia', 16, INK)),
                                                             ('   ·  en bilinenden başlar, bir satıra tıkla', style('Segoe UI', 9, INK_SOFT))])])
    thumbs = table_style(mat='#FBF7EE', alt='#FBF7EE', grid='#E8DEC9', size=9.5, pad=3, header=True)
    thumbs['grid'][0]['properties']['imageHeight'] = L(48)
    thumbs['columnWidth'] = [{'properties': {'value': L(30)}, 'selector': {'metadata': 'Gallery.era_rank'}},
                             {'properties': {'value': L(152)}, 'selector': {'metadata': 'Gallery.title'}},
                             {'properties': {'value': L(58)}, 'selector': {'metadata': 'Gallery.begin_year'}}]
    p.add('artwork_selector', 'tableEx', (60, 336, 336, 500), thumbs,
          {'padding': props(top=L(0), bottom=L(0), left=L(0), right=L(0))},
          {'Values': [proj('era_rank', 'Gallery', label='#'), proj('thumb_url', 'Gallery', label='Görsel'), proj('title', 'Gallery', label='Eser'),
                      proj('begin_year', 'Gallery', label='Yıl')]},
          sort=(ref('era_rank', 'Gallery'), 'Ascending'))
    svg(p, 'hero_image', inset(HERO_BOX, HERO_PAD), 'Selected Gallery Image', 'Gallery')
    svg(p, 'hero_frame', HERO_BOX, 'Gallery Frame SVG', 'Gallery')  # hangs over the photo's border
    svg(p, 'wall_label', LABEL_BOX, 'Gallery Wall Label SVG', 'Gallery')
    for i, (name, label, measure) in enumerate([('link_met', 'The Met eser sayfası  ↗', 'Selected Met URL'),
                                                ('link_artist', 'Sanatçı · Wikidata  ↗', 'Selected Artist Wiki URL'),
                                                ('link_object', 'Eser · Wikidata  ↗', 'Selected Object Wiki URL')]):
        button(p, name, (LABEL_BOX[0] + 4, link_y + i * 48, LABEL_BOX[2] - 8, 40), label, 'WebUrl', color=GOLD_LIGHT, outline='#8C6A2E',
               size=10, font='Segoe UI', align='left', url_measure=('Gallery', measure), tooltip='Kaynağı tarayıcıda aç')
    for target in ['hero_frame', 'hero_image', 'wall_label', 'link_met', 'link_artist', 'link_object']:
        p.interactions.append(('artwork_selector', target))
    # Picking an artwork must not narrow the tabs, the pickers or the room's sentence.
    for target in ['era_tabs', 'department_filter', 'title_search', 'type_filter', 'artist_search', 'narrative']:
        p.interactions.append(('artwork_selector', target, 'NoFilter'))
    footer(p, f'Dönem başına görselli en bilinen {TOP_PER_ERA} öne çıkan eser ({len(shown)}/{total:,}) · sıra: Wikipedia dil sayısı · '
              f'Met API, {retrieved} · galeri no. sergilenmeyi kanıtlamaz'.replace(',', '.'))
    return p


def build_tooltip():
    p = Page('tooltip_department', 'İpucu · Departman etiketi', None, '#FBF7EE', width=360, height=230,
             type='Tooltip', visibility='HiddenInViewMode', pageBinding={'name': 'tooltip_department_binding', 'type': 'Tooltip'})
    svg(p, 'label', (0, 0, 360, 230), 'Tooltip Label SVG')
    return p


def theme():
    s = lambda c: {'solid': {'color': c}}
    return {
        'name': 'MET Atlas Museum',
        'dataColors': ['#8E2A2F', '#B8893A', '#2F5266', '#5E7A63', '#B4643C', '#6B4E71', '#3F6F73', '#A88B5E', '#7D2E4A', '#4A5A6A', '#C9A45C', '#55402F'],
        'foreground': INK, 'foregroundNeutralSecondary': INK_SOFT, 'foregroundNeutralTertiary': '#A39787',
        'background': MAT, 'backgroundLight': '#EFE8DC', 'backgroundNeutral': '#D8CDBD',
        'tableAccent': GOLD, 'hyperlink': OXBLOOD, 'visitedHyperlink': '#6B4E71',
        'good': '#5E7A63', 'neutral': GOLD, 'bad': OXBLOOD, 'maximum': '#5A1B1F', 'center': '#D3AC68', 'minimum': '#F2EADB',
        'textClasses': {
            'callout': {'fontSize': 26, 'fontFace': 'Georgia', 'color': INK},
            'title': {'fontSize': 14, 'fontFace': 'Georgia', 'color': INK},
            'header': {'fontSize': 11, 'fontFace': 'Segoe UI Semibold', 'color': INK},
            'label': {'fontSize': 10, 'fontFace': 'Segoe UI', 'color': '#4A3F35'}},
        'visualStyles': {
            '*': {'*': {
                'background': [{'show': False}], 'border': [{'show': False}], 'dropShadow': [{'show': False}],
                'visualHeader': [{'background': s(MAT), 'foreground': s(INK_SOFT), 'border': s(GOLD), 'transparency': 0}],
                'visualTooltip': [{'background': s('#1B1512'), 'titleFontColor': s(GOLD_LIGHT), 'valueFontColor': s(IVORY), 'fontFamily': 'Segoe UI', 'fontSize': 10}],
                'categoryAxis': [{'labelColor': s('#4A3F35'), 'fontFamily': 'Segoe UI', 'showAxisTitle': False, 'gridlineShow': False}],
                'valueAxis': [{'labelColor': s('#8A7B6B'), 'showAxisTitle': False, 'gridlineColor': s('#E4DACA'), 'gridlineStyle': 'dotted'}],
                'outspacePane': [{'backgroundColor': s(MAT), 'foregroundColor': s(INK), 'border': True, 'borderColor': s(GOLD), 'fontFamily': 'Segoe UI'}],
            }},
            'page': {'*': {'outspace': [{'color': s('#0B0908'), 'transparency': 0}]}},
        }}


# ----------------------------------------------------------------------------- main

def main():
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    backup = ROOT.parent / 'work' / f'powerbi-before-polish-{stamp}'
    shutil.copytree(PROJECT, backup / 'MET Atlas', ignore=shutil.ignore_patterns('cache.abf', '*.pbix'))

    highlights = load(ROOT / 'highlights-catalog.json')
    catalog = highlights['artworks']
    shown = [a for a in catalog if a['image_url'] and a.get('era_rank') and a['era_rank'] <= TOP_PER_ERA]
    model = load(MODEL / 'model.bim')
    added = add_measures(model, catalog, shown)
    write(MODEL / 'model.bim', model)

    RESOURCES.mkdir(parents=True, exist_ok=True)
    for old in RESOURCES.glob('bg_*.jpg'):
        old.unlink()
    for name in REMOVED_PAGES:
        shutil.rmtree(REPORT / 'definition' / 'pages' / name, ignore_errors=True)
    bgs = {room: f'bg_{room}_{stamp.replace("-", "")}.jpg' for room in ORDER}
    pages = [build_lobby(bgs), build_overview(bgs), build_departments(bgs), build_periods(bgs),
             build_gallery(bgs, shown, len(catalog), highlights['retrieved']), build_tooltip()]
    for page in pages:
        page.save()

    write(RESOURCES / 'MetAtlasMuseum.json', theme())
    old_theme = RESOURCES / 'MetMuseum.json'
    if old_theme.exists():
        old_theme.unlink()
    report = load(REPORT / 'definition' / 'report.json')
    report['themeCollection']['customTheme']['name'] = 'MetAtlasMuseum'
    items = [{'name': 'MetAtlasMuseum', 'path': 'MetAtlasMuseum.json', 'type': 'CustomTheme'}]
    items += [{'name': f, 'path': f, 'type': 'Image'} for f in bgs.values()]
    report['resourcePackages'] = [{'name': 'RegisteredResources', 'type': 'RegisteredResources', 'items': items}]
    write(REPORT / 'definition' / 'report.json', report)
    pages_meta = load(REPORT / 'definition' / 'pages' / 'pages.json')
    pages_meta['pageOrder'] = [p.name for p in pages]
    pages_meta['activePageName'] = 'lobby'
    write(REPORT / 'definition' / 'pages' / 'pages.json', pages_meta)
    print(f'{len(pages)} pages, {sum(len(p.visuals) for p in pages)} visuals, {added} presentation measures, '
          f'{len(bgs)} backgrounds, {len(shown)} of {len(catalog)} highlight artworks in the gallery.')
    print(f'Backup: {backup}')


if __name__ == '__main__':
    main()
