"""Validate generated PBIR against official Microsoft schemas and field references."""
import hashlib
import json
import sys
import urllib.request
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / 'work' / 'pbi-validation'))
with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    from jsonschema import Draft7Validator, RefResolver

CACHE = ROOT.parent / 'work' / 'pbi-schema-cache'
CACHE.mkdir(parents=True, exist_ok=True)

def fetch(url):
    path = CACHE / (hashlib.sha256(url.encode()).hexdigest() + '.json')
    if path.exists(): return json.loads(path.read_text(encoding='utf-8'))
    mirror = url.replace('https://developer.microsoft.com/json-schemas/', 'https://raw.githubusercontent.com/microsoft/json-schemas/main/')
    errors = []
    # Microsoft's published refs use both embedded filename spellings.
    for candidate in dict.fromkeys([mirror, mirror.replace('schema.embedded.json', 'schema-embedded.json'), url, url.replace('schema.embedded.json', 'schema-embedded.json')]):
        try:
            with urllib.request.urlopen(candidate, timeout=20) as response:
                data = json.load(response)
            path.write_text(json.dumps(data), encoding='utf-8')
            return data
        except Exception as e: errors.append(str(e))
    raise RuntimeError(url + ': ' + '; '.join(errors))

errors = []
checked = 0
project = ROOT / 'MET Atlas'
for path in project.rglob('*'):
    if not path.is_file() or path.suffix not in ('.json', '.pbip', '.pbir', '.pbism', '.bim'): continue
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    url = data.get('$schema')
    if not url: continue
    definition = fetch(url)
    resolver = RefResolver(base_uri=url, referrer=definition, handlers={'https': fetch})
    validator = Draft7Validator(definition, resolver=resolver)
    for error in validator.iter_errors(data):
        errors.append(f'{path.relative_to(project)}: {list(error.path)}: {error.message}')
    checked += 1

model = json.loads((project / 'MET Atlas.SemanticModel' / 'model.bim').read_text(encoding='utf-8'))
entities = {t['name']: {'Column': {c['name'] for c in t['columns']}, 'Measure': {m['name'] for m in t.get('measures', [])}} for t in model['model']['tables']}
def check_fields(obj, path):
    if isinstance(obj, dict):
        for kind in ('Column', 'Measure'):
            if kind in obj and isinstance(obj[kind], dict):
                expr = obj[kind]
                entity = expr.get('Expression', {}).get('SourceRef', {}).get('Entity')
                name = expr.get('Property')
                if entity is not None and name not in entities.get(entity, {}).get(kind, set()):
                    errors.append(f'{path}: unresolved {kind} {entity}.{name}')
        for value in obj.values(): check_fields(value, path)
    elif isinstance(obj, list):
        for value in obj: check_fields(value, path)
for path in project.rglob('visual.json'):
    check_fields(json.loads(path.read_text(encoding='utf-8')), path.relative_to(project))
print(f'Checked {checked} schema-bearing files and all visual field references.')
for error in errors: print(error)
if errors: raise SystemExit(1)
print('PASS: official schema validation and model field references.')
