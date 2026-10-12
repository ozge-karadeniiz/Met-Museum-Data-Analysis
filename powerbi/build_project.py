"""Generate the local MET Atlas Desktop project. No credentials or source data are embedded."""
import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / 'MET Atlas'
REPORT = PROJECT / 'MET Atlas.Report'
MODEL = PROJECT / 'MET Atlas.SemanticModel'
BASE = 'https://developer.microsoft.com/json-schemas/fabric/item/'

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def schema(kind, version):
    return BASE + f'report/definition/{kind}/{version}/schema.json'

def literal(value):
    if isinstance(value, bool): value = 'true' if value else 'false'
    elif isinstance(value, (int, float)): value = str(value) + 'D'
    else: value = "'" + str(value).replace("'", "''") + "'"
    return {'expr': {'Literal': {'Value': value}}}

def color(value):
    return {'solid': {'color': literal(value)}}

def field(name, measure=False, entity='Artwork'):
    return {'Measure' if measure else 'Column': {'Expression': {'SourceRef': {'Entity': entity}}, 'Property': name}}

def projection(name, measure=False, entity='Artwork', label=None):
    result = {'field': field(name, measure, entity), 'queryRef': entity + '.' + name, 'nativeQueryRef': name}
    if label: result['displayName'] = label
    return result

def textbox(page, name, text, x, y, width, height, size=12, ink='#252525', font='Segoe UI'):
    visual(page, name, 'textbox', x, y, width, height, objects={'general': [{'properties': {
        'paragraphs': [{'textRuns': [{'value': text, 'textStyle': {'fontFamily': font, 'fontSize': str(size) + 'pt', 'color': ink}}]}]
    }}]}, background=False)

def visual(page, name, kind, x, y, width, height, roles=None, title=None, objects=None, sort=None, background=True):
    config = {'visualType': kind, 'drillFilterOtherVisuals': True}
    if roles:
        config['query'] = {'queryState': {role: {'projections': items} for role, items in roles.items()}}
        if sort:
            config['query']['sortDefinition'] = {'sort': [{'field': sort[0], 'direction': sort[1]}], 'isDefaultSort': False}
    if objects: config['objects'] = objects
    container = {'background': [{'properties': {'show': literal(background), 'color': color('#FFFFFF'), 'transparency': literal(0)}}],
                 'border': [{'properties': {'show': literal(False)}}]}
    if title:
        container['title'] = [{'properties': {'show': literal(True), 'text': literal(title), 'fontSize': literal(13), 'fontFamily': literal('Segoe UI'), 'fontColor': color('#252525')}}]
    else:
        container['title'] = [{'properties': {'show': literal(False)}}]
    config['visualContainerObjects'] = container
    write(REPORT / 'definition' / 'pages' / page / 'visuals' / name / 'visual.json', {
        '$schema': schema('visualContainer', '2.1.0'), 'name': name,
        'position': {'x': x, 'y': y, 'z': 0, 'height': height, 'width': width, 'tabOrder': 0}, 'visual': config
    })

def card(page, name, measure, label, x, width=320):
    visual(page, name, 'card', x, 176, width, 120, {'Values': [projection(measure, True)]}, label,
           objects={'labels': [{'properties': {'fontSize': literal(30), 'color': color('#B5121B'), 'labelDisplayUnits': literal(1)}}],
                    'categoryLabels': [{'properties': {'show': literal(False)}}]})

def slicer(page, name, column, label, x, width=320, entity='Artwork'):
    visual(page, name, 'slicer', x, 100, width, 60, {'Values': [projection(column, entity=entity)]}, label,
           objects={'data': [{'properties': {'mode': literal('Dropdown')}}]})

def page(name, title, subtitle):
    write(REPORT / 'definition' / 'pages' / name / 'page.json', {
        '$schema': schema('page', '2.0.0'), 'name': name, 'displayName': title, 'displayOption': 'FitToPage',
        'height': 900, 'width': 1440,
        'objects': {'background': [{'properties': {'color': color('#FAF8F4'), 'transparency': literal(0)}}]}
    })
    textbox(name, 'masthead', 'MET ATLAS', 40, 12, 300, 25, 12, '#B5121B')
    textbox(name, 'heading', title, 40, 37, 950, 45, 27, font='Georgia')
    textbox(name, 'subtitle', subtitle, 930, 24, 465, 55, 11, '#6B6258')
    textbox(name, 'footer', 'The Metropolitan Museum of Art • Açık erişim koleksiyonu | Galeri bilgisi, güncel sergilenme durumunu kanıtlamaz.', 40, 865, 1350, 25, 10, '#6B6258')

metadata = json.loads((ROOT.parent / 'work' / 'met-mart-metadata.json').read_text(encoding='utf-8-sig'))
columns = []
for c in metadata['schema']['fields']:
    col = {'name': c['name'], 'dataType': {'INTEGER': 'int64', 'STRING': 'string', 'BOOLEAN': 'boolean'}[c['type']],
           'sourceColumn': c['name'], 'summarizeBy': 'none'}
    if c['type'] == 'INTEGER': col['formatString'] = '0'
    if c['name'] == 'timeline_period': col['sortByColumn'] = 'timeline_period_order'
    if c['name'] == 'link_resource': col['dataCategory'] = 'WebUrl'
    if c['name'] in ('timeline_period_order', 'rights_and_reproduction', 'artist_wikidata_url'): col['isHidden'] = True
    columns.append(col)

measure_specs = [
    ('Artwork Count', 'DISTINCTCOUNT(Artwork[object_id])', '#,0', 'Koleksiyon'),
    ('Department Count', 'DISTINCTCOUNT(Artwork[department])', '#,0', 'Koleksiyon'),
    ('Highlight Artwork Count', 'CALCULATE([Artwork Count], KEEPFILTERS(Artwork[is_highlight] = TRUE()))', '#,0', 'Koleksiyon'),
    ('Highlight Share', 'DIVIDE([Highlight Artwork Count], [Artwork Count])', '0.0%', 'Koleksiyon'),
    ('Public Domain Artwork Count', 'CALCULATE([Artwork Count], KEEPFILTERS(Artwork[is_public_domain] = TRUE()))', '#,0', 'Koleksiyon'),
    ('Public Domain Share', 'DIVIDE([Public Domain Artwork Count], [Artwork Count])', '0.0%', 'Koleksiyon'),
    ('Artwork With Gallery Information', 'CALCULATE([Artwork Count], KEEPFILTERS(Artwork[is_on_view] = TRUE()))', '#,0', 'Galeri bilgisi'),
    ('Gallery Information Share', 'DIVIDE([Artwork With Gallery Information], [Artwork Count])', '0.0%', 'Galeri bilgisi'),
    ('Department Share', 'DIVIDE([Artwork Count], CALCULATE([Artwork Count], REMOVEFILTERS(Artwork[department])))', '0.0%', 'Koleksiyon'),
    ('Reversed Date Count', 'CALCULATE([Artwork Count], FILTER(Artwork, NOT ISBLANK(Artwork[object_begin_date]) && NOT ISBLANK(Artwork[object_end_date]) && Artwork[object_begin_date] > Artwork[object_end_date]))', '#,0', 'Veri kalitesi'),
    ('Zero Year Count', 'CALCULATE([Artwork Count], FILTER(Artwork, (NOT ISBLANK(Artwork[object_begin_date]) && Artwork[object_begin_date] == 0) || (NOT ISBLANK(Artwork[object_end_date]) && Artwork[object_end_date] == 0)))', '#,0', 'Veri kalitesi'),
    ('Missing Accession Year Count', 'CALCULATE([Artwork Count], FILTER(Artwork, ISBLANK(Artwork[accession_year])))', '#,0', 'Veri kalitesi'),
    ('Missing Culture Count', 'CALCULATE([Artwork Count], FILTER(Artwork, ISBLANK(Artwork[culture]) || TRIM(Artwork[culture]) IN {"", "Unknown"}))', '#,0', 'Veri kalitesi'),
    ('Missing Country Count', 'CALCULATE([Artwork Count], FILTER(Artwork, ISBLANK(Artwork[country]) || TRIM(Artwork[country]) IN {"", "Unknown"}))', '#,0', 'Veri kalitesi'),
    ('Missing Medium Count', 'CALCULATE([Artwork Count], FILTER(Artwork, ISBLANK(Artwork[medium]) || TRIM(Artwork[medium]) IN {"", "Unknown"}))', '#,0', 'Veri kalitesi'),
    ('Missing Artist Attribution Count', 'CALCULATE([Artwork Count], FILTER(Artwork, ISBLANK(Artwork[artist_display_name]) || TRIM(Artwork[artist_display_name]) IN {"", "Unknown", "Anonymous / Unknown"}))', '#,0', 'Veri kalitesi'),
    ('Missing Field Count', 'SWITCH(SELECTEDVALUE(QualityField[Field]), "Kültür", [Missing Culture Count], "Ülke", [Missing Country Count], "Malzeme", [Missing Medium Count], "Sanatçı atfı", [Missing Artist Attribution Count], "Edinim yılı", [Missing Accession Year Count], BLANK())', '#,0', 'Veri kalitesi'),
    ('Missing Field Share', 'DIVIDE([Missing Field Count], [Artwork Count])', '0.0%', 'Veri kalitesi'),
]
measures = [{'name': n, 'expression': e, 'formatString': f, 'displayFolder': d} for n,e,f,d in measure_specs]
typed = ', '.join('{"' + c['name'] + '", ' + {'INTEGER':'Int64.Type','STRING':'type text','BOOLEAN':'type logical'}[c['type']] + '}' for c in metadata['schema']['fields'])
m_source = [
    'let',
    '    Source = GoogleBigQuery.Database([BillingProject="the-met-open-access", UseStorageApi=false]),',
    '    Project = Source{[Name="the-met-open-access"]}[Data],',
    '    Dataset = Project{[Name="met_data", Kind="Schema"]}[Data],',
    '    Mart = Dataset{[Name="mart_met_objects", Kind="Table"]}[Data],',
    '    Typed = Table.TransformColumnTypes(Mart, {' + typed + '})',
    'in', '    Typed'
]
write(MODEL / 'definition.pbism', {'$schema': BASE + 'semanticModel/definitionProperties/1.0.0/schema.json', 'version':'4.0', 'settings':{'qnaEnabled':False}})
write(MODEL / 'model.bim', {
    'name':'MET Atlas', 'compatibilityLevel':1601,
    'model': {'culture':'tr-TR', 'sourceQueryCulture':'en-US', 'defaultPowerBIDataSourceVersion':'powerBI_V3',
        'dataAccessOptions': {'legacyRedirects':True, 'returnErrorValuesAsNull':True},
        'tables': [
            {'name':'Artwork', 'columns':columns, 'measures':measures,
             'partitions':[{'name':'Artwork', 'mode':'import', 'source':{'type':'m', 'expression':m_source}}]},
            {'name':'QualityField', 'columns':[
                {'type':'calculatedTableColumn','name':'Field','dataType':'string','sourceColumn':'[Field]','summarizeBy':'none','sortByColumn':'Order'},
                {'type':'calculatedTableColumn','name':'Order','dataType':'int64','sourceColumn':'[Order]','summarizeBy':'none','isHidden':True}],
             'partitions':[{'name':'QualityField','mode':'import','source':{'type':'calculated','expression':'DATATABLE("Field", STRING, "Order", INTEGER, {{"Kültür", 1}, {"Ülke", 2}, {"Malzeme", 3}, {"Sanatçı atfı", 4}, {"Edinim yılı", 5}})'}}]}
        ], 'annotations':[{'name':'PBI_QueryOrder','value':'["Artwork"]'},{'name':'PBI_ProTooling','value':'["DevMode"]'}]
    }
})
write(PROJECT / 'MET Atlas.pbip', {'$schema':'https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json', 'version':'1.0', 'artifacts':[{'report':{'path':'MET Atlas.Report'}}], 'settings':{'enableAutoRecovery':True}})
write(REPORT / 'definition.pbir', {'$schema':BASE+'report/definitionProperties/2.0.0/schema.json','version':'4.0','datasetReference':{'byPath':{'path':'../MET Atlas.SemanticModel'}}})
write(REPORT / 'definition' / 'version.json', {'$schema':schema('versionMetadata','1.0.0'),'version':'2.0.0'})
theme = json.loads((ROOT / 'met-inspired.theme.json').read_text(encoding='utf-8'))
write(REPORT / 'StaticResources' / 'RegisteredResources' / 'MetMuseum.json', theme)
write(REPORT / 'definition' / 'report.json', {'$schema':schema('report','2.0.0'),
    'themeCollection':{'customTheme':{'name':'MetMuseum','reportVersionAtImport':'5.59','type':'RegisteredResources'}},
    'resourcePackages':[{'name':'RegisteredResources','type':'RegisteredResources','items':[{'name':'MetMuseum','path':'MetMuseum.json','type':'CustomTheme'}]}]})
pages = [('overview','Koleksiyona genel bakış','Sanatın veriyle keşfi\nBigQuery • met_data.mart_met_objects'),
         ('departments','Departmanlar','Koleksiyon dağılımı ve galeri bilgisi'),
         ('periods','Dönemler ve malzemeler','MÖ yılları korunur • Başlangıç yılına göre dönem'),
         ('quality','Veri kalitesi','Eksiklikler ve tarih kontrolleri')]
write(REPORT / 'definition' / 'pages' / 'pages.json', {'$schema':schema('pagesMetadata','1.0.0'),'pageOrder':[p[0] for p in pages],'activePageName':'overview'})
for name,title,subtitle in pages:
    page(name,title,subtitle)
    slicer(name,'department_filter','department','Departman',40)
    slicer(name,'period_filter','timeline_period','Dönem',384)
    slicer(name,'type_filter','object_type_material','Eser türü / malzeme',728)
    slicer(name,'domain_filter','is_public_domain','Kamu malı',1072)

card('overview','total_card','Artwork Count','Toplam eser',40)
card('overview','department_card','Department Count','Departman',384)
card('overview','public_card','Public Domain Share','Kamu malı payı',728)
card('overview','highlight_card','Highlight Artwork Count','Öne çıkan eser',1072)
visual('overview','department_chart','barChart',40,320,664,510,{'Category':[projection('department')],'Y':[projection('Artwork Count',True)]},'Departmanlara göre eser sayısı',sort=(field('Artwork Count',True),'Descending'))
visual('overview','period_chart','clusteredColumnChart',728,320,664,270,{'Category':[projection('timeline_period')],'Y':[projection('Artwork Count',True)]},'Dönemlere göre koleksiyon',sort=(field('timeline_period'),'Ascending'))
visual('overview','material_chart','barChart',728,610,664,220,{'Category':[projection('object_type_material')],'Y':[projection('Artwork Count',True)]},'Tür ve malzeme dağılımı',sort=(field('Artwork Count',True),'Descending'))

card('departments','total_card','Artwork Count','Filtrelenen eser',40)
card('departments','gallery_card','Artwork With Gallery Information','Galeri bilgisi olan eser',384)
card('departments','gallery_share_card','Gallery Information Share','Galeri bilgisi payı',728)
card('departments','highlight_share_card','Highlight Share','Öne çıkan eser payı',1072)
visual('departments','share_chart','barChart',40,320,664,510,{'Category':[projection('department')],'Y':[projection('Department Share',True)]},'Tüm departmanlar içindeki pay',sort=(field('Department Share',True),'Descending'))
visual('departments','department_table','tableEx',728,320,664,510,{'Values':[projection('department',label='Departman'),projection('Artwork Count',True,label='Eser'),projection('Public Domain Share',True,label='Kamu malı'),projection('Gallery Information Share',True,label='Galeri bilgisi'),projection('Highlight Share',True,label='Öne çıkan')]},'Departman karşılaştırması')

card('periods','total_card','Artwork Count','Filtrelenen eser',40)
card('periods','public_card','Public Domain Share','Kamu malı payı',384)
card('periods','reversed_card','Reversed Date Count','Ters tarih aralığı',728)
card('periods','zero_card','Zero Year Count','Sıfır yıl içeren eser',1072)
visual('periods','timeline_chart','clusteredColumnChart',40,320,1352,260,{'Category':[projection('timeline_period')],'Y':[projection('Artwork Count',True)]},'Başlangıç tarihine göre koleksiyon',sort=(field('timeline_period'),'Ascending'))
visual('periods','period_table','tableEx',40,604,664,226,{'Values':[projection('timeline_period',label='Dönem'),projection('Artwork Count',True,label='Eser'),projection('Public Domain Share',True,label='Kamu malı')]},'Dönem karşılaştırması',sort=(field('timeline_period'),'Ascending'))
visual('periods','material_chart','barChart',728,604,664,226,{'Category':[projection('object_type_material')],'Y':[projection('Artwork Count',True)]},'Seçili dönemlerde tür ve malzeme',sort=(field('Artwork Count',True),'Descending'))

card('quality','total_card','Artwork Count','İncelenen eser',40)
card('quality','reversed_card','Reversed Date Count','Ters tarih aralığı',384)
card('quality','zero_card','Zero Year Count','Sıfır yıl içeren eser',728)
card('quality','accession_card','Missing Accession Year Count','Edinim yılı eksik',1072)
visual('quality','missing_chart','barChart',40,320,664,510,{'Category':[projection('Field',entity='QualityField')],'Y':[projection('Missing Field Share',True)]},'Alanlara göre eksik bilgi payı',sort=(field('Missing Field Share',True),'Descending'))
visual('quality','quality_table','tableEx',728,320,664,320,{'Values':[projection('Field',entity='QualityField',label='Alan'),projection('Missing Field Count',True,label='Eksik eser'),projection('Missing Field Share',True,label='Eksik payı')]},'Eksiklik kontrolü')
textbox('quality','quality_note','Unknown ve Anonymous / Unknown etiketleri eksik kabul edilir.\nEdinim yılı eksikliği mevcut staging dönüşümünden etkilenebilir.\nTarih sorunları sayılır; bu rapor kaynak kayıtları değiştirmez.',748,666,624,150,12)

(ROOT / 'Artwork.pq').write_text('\n'.join(m_source)+'\n',encoding='utf-8')
print(f'Created: {PROJECT / "MET Atlas.pbip"}')
print(f'{len(columns)} source columns, {len(measures)} measures, {len(pages)} pages, {len(list(REPORT.rglob("visual.json")))} visuals')
