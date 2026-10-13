"""Read a small public-domain selection from the official Met Collection API."""
import concurrent.futures
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IDS = [436535, 436532, 436528, 437133, 436105, 437853, 437881, 436965, 436175, 436106, 459055, 435882]
def fetch(object_id):
    url = f'https://collectionapi.metmuseum.org/public/collection/v1/objects/{object_id}'
    try:
        with urllib.request.urlopen(url, timeout=25) as response:
            obj = json.load(response)
        if not obj.get('isPublicDomain') or not obj.get('primaryImageSmall'):
            return None
        return {'object_id': object_id, 'title': obj['title'], 'artist': obj.get('artistDisplayName') or 'Anonymous / Unknown',
                'date': obj.get('objectDate', ''), 'department': obj.get('department', ''), 'medium': obj.get('medium', ''),
                'image_url': obj['primaryImageSmall'], 'met_url': obj['objectURL'],
                'artist_wiki_url': obj.get('artistWikidata_URL', ''), 'object_wiki_url': obj.get('objectWikidata_URL', ''),
                'api_url': url, 'is_public_domain': True,
                # Wall-label and frame details for the polished gallery page.
                'artist_bio': obj.get('artistDisplayBio', ''), 'artist_nationality': obj.get('artistNationality', ''),
                'credit_line': obj.get('creditLine', ''), 'accession_number': obj.get('accessionNumber', ''),
                'is_highlight': bool(obj.get('isHighlight')), 'gallery_number': obj.get('GalleryNumber', ''),
                'overall_cm': next(({k: v for k, v in m['elementMeasurements'].items() if k in ('Height', 'Width')}
                                    for m in obj.get('measurements') or [] if 'Height' in m.get('elementMeasurements', {}) and 'Width' in m.get('elementMeasurements', {})), {})}
    except Exception as e:
        print(f'Object {object_id}: {e}')
        return None

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    rows = [row for row in pool.map(fetch, IDS) if row]
(ROOT / 'gallery-catalog.json').write_text(json.dumps({'source': 'Met Collection API', 'retrieved': '2026-10-09', 'selection': 'curated public-domain selection; not the full collection', 'artworks': rows}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
for row in rows: print(f'{row["object_id"]}: {row["title"]} — {row["artist"]}')
print(f'{len(rows)} public-domain artworks with images.')
