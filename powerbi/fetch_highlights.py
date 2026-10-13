"""Build the masterpiece catalogue for the Başyapıtlar room: every highlight artwork in the mart.

Rows come from the mart (`is_highlight = TRUE`). By default the script reads them with `bq`;
`--source FILE` takes the same rows as a JSON list instead (for example a DAX export of
the Desktop model when bq has no credentials). Each artwork is then looked up in the official
Met Collection API for its image, artist bio, Wikidata link and overall size. Open-access
images are downloaded once to measure their pixel size and the thin black border many Met
photos carry, so the report can hang a frame that hugs the photo.

Artworks without an open-access image stay in the catalogue with `image_url` empty; the
report shows a placeholder and the link to the Met page.

    python fetch_highlights.py [--source rows.json] [--workers 4]

API calls are paced to three per second. Responses and image measurements are cached under
work/highlight-cache/, so an interrupted run resumes where it stopped.
"""
import argparse
import concurrent.futures
import hashlib
import html
import io
import json
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
CACHE = ROOT.parent / 'work' / 'highlight-cache'
OUT = ROOT / 'highlights-catalog.json'
API = 'https://collectionapi.metmuseum.org/public/collection/v1/objects/{}'
HEADERS = {'User-Agent': 'MET-Atlas-student-project/1.0 (open-access research)'}

SQL = """
SELECT object_id, object_number, title, artist_display_name, artist_nationality, object_date,
       object_begin_date, timeline_period, timeline_period_order, department, classification,
       object_name, medium, dimensions, credit_line, gallery_number, is_public_domain, culture,
       artist_wikidata_url, link_resource
FROM `the-met-open-access.met_data.mart_met_objects`
WHERE is_highlight
ORDER BY object_id
"""

# Mart timeline periods as Turkish tab labels. Unknown labels pass through unchanged.
ERAS = {'8000–2000 B.C.': 'MÖ 8000–2000', '2000–1000 B.C.': 'MÖ 2000–1000', '1000 B.C.–1 A.D.': 'MÖ 1000–MS 1',
        '1–500 A.D.': 'MS 1–500', '500–1000 A.D.': '500–1000', '1000–1400 A.D.': '1000–1400',
        '1400–1600 A.D.': '1400–1600', '1600–1800 A.D.': '1600–1800', '1800–1900 A.D.': '1800–1900',
        '1900 A.D.–present': '1900–günümüz'}
PLACEHOLDERS = {'', 'unknown', 'anonymous / unknown', 'anonymous', 'untitled', 'in storage'}


def mart_rows(source):
    if source:
        return json.loads(Path(source).read_text(encoding='utf-8-sig'))
    out = subprocess.run(['bq', '--headless=true', '--project_id=the-met-open-access', '--location=EU', 'query',
                          '--use_legacy_sql=false', '--maximum_bytes_billed=200000000', '--format=json', '--max_rows=10000', SQL],
                         capture_output=True, text=True, encoding='utf-8', check=True)
    return json.loads(out.stdout)


class Pace:
    """Space out API calls: the Met API answers 403 for a while after a burst of parallel requests."""

    def __init__(self, per_second):
        self.gap, self.next, self.lock = 1 / per_second, 0.0, threading.Lock()

    def hold(self, seconds):
        """Pause every worker, not just the one that was refused."""
        with self.lock:
            self.next = max(self.next, time.monotonic() + seconds)

    def wait(self):
        with self.lock:
            now = time.monotonic()
            delay = max(0.0, self.next - now)
            self.next = max(now, self.next) + self.gap
        time.sleep(delay)


PACE = Pace(3)


def get_json(url, tries=12):
    for attempt in range(tries):
        PACE.wait()
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {}
            if e.code in (403, 429):
                PACE.hold(20)
            else:
                time.sleep(2)
        except Exception:
            time.sleep(3)
    return None  # still blocked: leave it uncached and try again on the next run


def measure(url, tries=4):
    """(width, height, black border left, right, top, bottom) of the web-large photo."""
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=40) as r:
                img = Image.open(io.BytesIO(r.read())).convert('L')
            break
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    else:
        return None
    a = np.asarray(img, np.float32)
    h, w = a.shape

    def run(lines, limit):
        n = 0
        for line in lines[:limit]:
            if line.mean() < 40 and line.std() < 14:
                n += 1
            else:
                break
        if n >= limit:
            return 0  # an all-dark edge is the artwork, not a border
        return n + 2 if n else 0  # cover the anti-aliased transition into the paint

    lw, lh = max(2, int(w * 0.06)), max(2, int(h * 0.06))
    return [w, h, run(a.T, lw), run(a.T[::-1], lw), run(a, lh), run(a[::-1], lh)]


def lookup(object_id):
    path = CACHE / f'{object_id}.json'
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    obj = get_json(API.format(object_id))
    if obj is None:
        return None
    image = obj.get('primaryImageSmall') or ''
    info = {'api': {k: obj.get(k) for k in ('primaryImageSmall', 'artistDisplayBio', 'artistWikidata_URL', 'objectWikidata_URL',
                                            'objectURL', 'GalleryNumber', 'isPublicDomain', 'classification', 'measurements')},
            'pixels': measure(image) if image else None}
    path.write_text(json.dumps(info, ensure_ascii=False), encoding='utf-8')
    return info


def first(value, sep='|'):
    parts = [p.strip() for p in str(value or '').split(sep)]
    return next((p for p in parts if p and p.lower() not in PLACEHOLDERS), '')


def artists(value):
    names = []
    for p in str(value or '').split('|'):
        p = p.strip()
        if p and p.lower() not in PLACEHOLDERS and p not in names:
            names.append(p)
    return ', '.join(names)


def tidy(text):
    """Plain text: some mart titles carry HTML-escaped markup such as &lt;i&gt;Spangenhelm&lt;/i&gt;."""
    return ' '.join(re.sub(r'<[^>]+>', '', html.unescape(str(text or ''))).split())


def clip(text, n):
    text = tidy(text)
    return text if len(text) <= n else text[:n - 1].rstrip(' ,;') + '…'


def size_cm(api):
    for m in api.get('measurements') or []:
        e = m.get('elementMeasurements') or {}
        if m.get('elementName') == 'Overall' and e.get('Height') and e.get('Width'):
            return f"{e['Height']:.1f} × {e['Width']:.1f} cm".replace('.', ',')
    return ''


def row(src, info):
    api = info['api']
    pixels = info['pixels']
    image = api.get('primaryImageSmall') or ''
    if not pixels:
        image = ''
    classification = first(src.get('classification')) or first(api.get('classification'))
    kind = 'painting' if 'painting' in f"{classification} {src.get('object_name', '')}".lower() else 'object'
    period = src.get('timeline_period') or ''
    title = tidy(src.get('title'))
    if title.lower() in PLACEHOLDERS:  # untitled objects: use the object name, as the Met site does
        title = tidy(src.get('object_name'))
    if title.lower() in PLACEHOLDERS:
        title = 'Adsız eser'
    # The API holds the current gallery; an empty value there means not on view. The mart's
    # 'In Storage' is a default label for an empty gallery number, not a location.
    gallery = (api.get('GalleryNumber') if api.get('objectURL') else src.get('gallery_number')) or ''
    gallery = '' if str(gallery).strip().lower() in PLACEHOLDERS else str(gallery).strip()
    return {
        'object_id': int(src['object_id']),
        'title': clip(title, 140),
        'artist': clip(artists(src.get('artist_display_name')) or 'Sanatçı bilinmiyor', 90),
        'artist_bio': clip(first(api.get('artistDisplayBio')) or first(src.get('artist_nationality')), 90),
        'culture': first(src.get('culture')),
        'date': clip(src.get('object_date') or '', 60),
        'begin_year': int(src['object_begin_date']) if src.get('object_begin_date') is not None else None,
        'era': ERAS.get(period, period or 'Tarih bilinmiyor'),
        'era_order': int(src.get('timeline_period_order') or 99),
        'department': src.get('department') or '',
        'kind': kind,
        'medium': clip(src.get('medium'), 150),
        'size_cm': size_cm(api),
        'credit_line': clip(src.get('credit_line'), 130),
        'accession_number': src.get('object_number') or '',
        'gallery_number': gallery,
        'is_public_domain': bool(api.get('isPublicDomain') if api else src.get('is_public_domain')),
        'image_url': image,
        'met_url': api.get('objectURL') or src.get('link_resource') or f'https://www.metmuseum.org/art/collection/search/{src["object_id"]}',
        'artist_wiki_url': (first(api.get('artistWikidata_URL')) or first(src.get('artist_wikidata_url'))).replace('http://', 'https://'),
        'object_wiki_url': (api.get('objectWikidata_URL') or '').replace('http://', 'https://'),
        'pixels': pixels,
    }


WIKIDATA = 'https://www.wikidata.org/w/api.php?action=wbgetentities&props=sitelinks&format=json&ids={}'
NOT_WIKIPEDIA = {'commonswiki', 'specieswiki', 'metawiki', 'mediawikiwiki', 'wikidatawiki', 'sourceswiki', 'outreachwiki', 'wikimaniawiki'}
TOP_PER_ERA = 50


def qid(url):
    m = re.search(r'(Q\d+)', url or '')
    return m.group(1) if m else None


def wikipedia_languages(qids):
    """Number of Wikipedia language editions with an article on each Wikidata item (cached)."""
    path = CACHE / 'wikipedia-languages.json'
    known = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    todo = sorted({q for q in qids if q and q not in known})
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        data = get_json(WIKIDATA.format('|'.join(batch))) or {}
        for q, entity in (data.get('entities') or {}).items():
            links = entity.get('sitelinks') or {}
            known[q] = sum(1 for k in links if k.endswith('wiki') and k not in NOT_WIKIPEDIA)
        path.write_text(json.dumps(known), encoding='utf-8')
    return known


def rank_eras(catalog):
    """Rank artworks with an open-access image inside each era by fame: Wikipedia languages of the
    artwork, then of its artist, then a fixed pseudo-random order (an md5 of the object id)."""
    langs = wikipedia_languages([qid(a['object_wiki_url']) for a in catalog] + [qid(a['artist_wiki_url']) for a in catalog])
    for a in catalog:
        a['wikipedia_languages'] = langs.get(qid(a['object_wiki_url']), 0)
        a['artist_wikipedia_languages'] = langs.get(qid(a['artist_wiki_url']), 0)
        a['era_rank'] = None
    eras = {}
    for a in catalog:
        if a['image_url']:
            eras.setdefault(a['era'], []).append(a)
    for items in eras.values():
        items.sort(key=lambda a: (-a['wikipedia_languages'], -a['artist_wikipedia_languages'],
                                  hashlib.md5(str(a['object_id']).encode()).hexdigest()))
        for i, a in enumerate(items, 1):
            a['era_rank'] = i


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source')
    ap.add_argument('--workers', type=int, default=4)
    args = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    rows = mart_rows(args.source)
    done = 0
    out, missing = {}, []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(lookup, int(r['object_id'])): r for r in rows}
        for f in concurrent.futures.as_completed(futures):
            src = futures[f]
            info = f.result()
            if info is None:
                missing.append(int(src['object_id']))
                continue
            out[int(src['object_id'])] = row(src, info)
            done += 1
            if done % 250 == 0:
                print(f'{done}/{len(rows)}', flush=True)
    if missing:
        raise SystemExit(f'{len(missing)} artworks could not be read from the API (blocked or offline); '
                         'run the script again later to finish. Cached results are kept.')
    catalog = [out[k] for k in sorted(out)]
    rank_eras(catalog)
    with_image = sum(1 for a in catalog if a['image_url'])
    OUT.write_text(json.dumps({'source': 'mart_met_objects (is_highlight) + Met Collection API + Wikidata sitelinks',
                               'retrieved': time.strftime('%Y-%m-%d'),
                               'ranking': 'era_rank: within each era, artworks with an open-access image ordered by the number of '
                                          'Wikipedia languages about the artwork, then about its artist, then md5(object_id)',
                               'artworks': catalog}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f'{len(catalog)} highlight artworks, {with_image} with an open-access image -> {OUT.name}')


if __name__ == '__main__':
    main()
