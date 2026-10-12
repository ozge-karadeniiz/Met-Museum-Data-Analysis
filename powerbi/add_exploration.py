"""Add two exploratory pages without regenerating the existing report pages."""
import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / 'MET Atlas'
REPORT = PROJECT / 'MET Atlas.Report'
MODEL = PROJECT / 'MET Atlas.SemanticModel'
BASE = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/'
BACKUP = ROOT.parent / 'work' / ('powerbi-before-exploration-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
BACKUP.mkdir(parents=True, exist_ok=True)
for path in [MODEL/'model.bim', REPORT/'definition/pages/pages.json']:
    shutil.copy2(path, BACKUP/path.name)
cache = MODEL/'.pbi/cache.abf'
if cache.exists(): shutil.move(str(cache), str(BACKUP/'cache.abf'))

def load(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
def literal(value):
    if isinstance(value,bool): value = 'true' if value else 'false'
    elif isinstance(value,(int,float)): value = str(value)+'D'
    else: value = "'"+str(value).replace("'","''")+"'"
    return {'expr':{'Literal':{'Value':value}}}
def color(value): return {'solid':{'color':literal(value)}}
def field(entity,name,measure=False): return {'Measure' if measure else 'Column':{'Expression':{'SourceRef':{'Entity':entity}},'Property':name}}
def projection(entity,name,measure=False,label=None):
    value = {'field':field(entity,name,measure),'queryRef':entity+'.'+name,'nativeQueryRef':name}
    if label: value['displayName']=label
    return value
def vis(page,name,kind,box,roles=None,title=None,objects=None,dark=False,sort=None):
    ink = '#F5EFE6' if dark else '#252525'
    cfg={'visualType':kind,'drillFilterOtherVisuals':True,
         'visualContainerObjects':{
             'background':[{'properties':{'show':literal(True),'color':color('#22272B' if dark else '#FFFFFF'),'transparency':literal(0)}}],
             'border':[{'properties':{'show':literal(False)}}],
             'title':[{'properties':{'show':literal(bool(title)), 'text':literal(title or ''),'fontSize':literal(13),'fontFamily':literal('Segoe UI'),'fontColor':color(ink)}}]}}
    if objects: cfg['objects']=objects
    if roles:
        cfg['query']={'queryState':{role:{'projections':p} for role,p in roles.items()}}
        if sort: cfg['query']['sortDefinition']={'sort':[{'field':sort[0],'direction':sort[1]}],'isDefaultSort':False}
    x,y,w,h=box
    write(REPORT/f'definition/pages/{page}/visuals/{name}/visual.json',{'$schema':BASE+'visualContainer/2.1.0/schema.json','name':name,
        'position':{'x':x,'y':y,'width':w,'height':h,'z':0,'tabOrder':0},'visual':cfg})
def text(page,name,value,box,size=12,ink='#252525',font='Segoe UI',dark=False):
    vis(page,name,'textbox',box,objects={'general':[{'properties':{'paragraphs':[{'textRuns':[{'value':value,'textStyle':{'fontFamily':font,'fontSize':str(size)+'pt','color':ink}}]}]}}]},dark=dark)
    path=REPORT/f'definition/pages/{page}/visuals/{name}/visual.json'
    cfg=load(path);cfg['visual']['visualContainerObjects']['background'][0]['properties']['show']=literal(False);write(path,cfg)
def card(page,name,entity,measure,label,box,size=24,dark=False):
    vis(page,name,'card',box,{'Values':[projection(entity,measure,True)]},label,{'labels':[{'properties':{'fontSize':literal(size),'color':color('#E5BC78' if dark else '#B5121B'),'labelDisplayUnits':literal(1)}}], 'categoryLabels':[{'properties':{'show':literal(False)}}]},dark)
def page(name,title,bg):
    write(REPORT/f'definition/pages/{name}/page.json',{'$schema':BASE+'page/2.0.0/schema.json','name':name,'displayName':title,'displayOption':'FitToPage','width':1440,'height':900,
         'objects':{'background':[{'properties':{'color':color(bg),'transparency':literal(0)}}]}})
def m_quote(value): return '"'+str(value).replace('"','""').replace('\r',' ').replace('\n',' ')+'"'

catalog=load(ROOT/'gallery-catalog.json')['artworks']
if not catalog: raise RuntimeError('No verified public-domain images available.')
model=load(MODEL/'model.bim')
model['model']['tables']=[t for t in model['model']['tables'] if t['name']!='Gallery']
names=['object_id','title','artist','date','department','medium','image_url','met_url','artist_wiki_url','object_wiki_url']
columns=[]
for name in names:
    col={'name':name,'dataType':'int64' if name=='object_id' else 'string','sourceColumn':name,'summarizeBy':'none'}
    if name=='image_url': col['dataCategory']='ImageUrl'
    if name.endswith('wiki_url') or name=='met_url': col['dataCategory']='WebUrl'
    columns.append(col)
rows=['{'+', '.join(str(row[name]) if name=='object_id' else m_quote(row[name].replace('http://www.wikidata.org/','https://www.wikidata.org/')) for name in names)+'}' for row in catalog]
m = 'let\n    Catalog = #table(type table ['+', '.join(name+' = '+('Int64.Type' if name=='object_id' else 'text') for name in names)+'], {\n        '+',\n        '.join(rows)+'\n    })\nin\n    Catalog'
measures=[{'name':'Gallery Artwork Count','expression':'DISTINCTCOUNT(Gallery[object_id])','formatString':'0'},
          {'name':'Selected Gallery ID','expression':'MIN(Gallery[object_id])','isHidden':True}]
for name,column in [('Selected Gallery Image','image_url'),('Selected Gallery Title','title'),('Selected Gallery Artist','artist'),('Selected Gallery Date','date'),('Selected Gallery Medium','medium'),('Selected Met URL','met_url'),('Selected Artist Wiki URL','artist_wiki_url'),('Selected Object Wiki URL','object_wiki_url')]:
    measure={'name':name,'expression':f'VAR SelectedID = [Selected Gallery ID] RETURN MAXX(FILTER(Gallery, Gallery[object_id] = SelectedID), Gallery[{column}])'}
    if column=='image_url':measure['dataCategory']='ImageUrl'
    elif column.endswith('_url'):measure['dataCategory']='WebUrl'
    measures.append(measure)
model['model']['tables'].append({'name':'Gallery','columns':columns,'measures':measures,
    'partitions':[{'name':'Gallery','mode':'import','source':{'type':'m','expression':m.splitlines()}}],
    'description':'Small curated public-domain selection from official Met API. Independent of full-collection totals; metadata snapshot 2026-10-09.'})
write(MODEL/'model.bim',model)

# Bright editorial gallery with a large responsive artwork image.
page('digital_gallery','Dijital galeri','#F4EFE6')
text('digital_gallery','eyebrow','MET ATLAS / DİJİTAL GALERİ',(40,20,800,25),12,'#B5121B')
text('digital_gallery','heading','Bir eserin içine gir.',(40,48,1000,60),34,font='Georgia')
text('digital_gallery','instructions',f'{len(catalog)} kamu malı eserlik seçki • Soldan bir eser seç; görsel, künye ve kaynaklar değişsin.',(40,116,1350,30),12,'#6B6258')
vis('digital_gallery','artwork_selector','slicer',(40,166,342,565),{'Values':[projection('Gallery','title',label='Eser')]},'Eser seç',{
    'data':[{'properties':{'mode':literal('List')}}],
    'selection':[{'properties':{'singleSelect':literal(True),'strictSingleSelect':literal(True)}}],
    'header':[{'properties':{'show':literal(False)}}],
    'items':[{'properties':{'fontSize':literal(12),'fontFamily':literal('Segoe UI'),'fontColor':color('#252525')}}]})
vis('digital_gallery','hero_image','tableEx',(406,166,620,565),{'Values':[projection('Gallery','Selected Gallery Image',True,label='')]},None,{
    'grid':[{'properties':{'imageHeight':literal(510),'imageWidth':literal(590),'rowPadding':literal(0),'outlineColor':color('#FFFFFF')}}],
    'columnHeaders':[{'properties':{'show':literal(False),'fontColor':color('#FFFFFF'),'backColor':color('#FFFFFF'),'fontSize':literal(1)}}],
    'values':[{'properties':{'fontSize':literal(1)}}],
    'total':[{'properties':{'show':literal(False)}}]})
vis('digital_gallery','selected_title','tableEx',(1050,166,350,145),{'Values':[projection('Gallery','Selected Gallery Title',True,label='')]},'ESER',{
    'values':[{'properties':{'fontSize':literal(17),'wordWrap':literal(True),'fontColor':color('#252525')}}],
    'columnHeaders':[{'properties':{'show':literal(False),'fontSize':literal(1),'fontColor':color('#FFFFFF')}}],
    'grid':[{'properties':{'rowPadding':literal(5)}}], 'total':[{'properties':{'show':literal(False)}}]})
card('digital_gallery','selected_artist','Gallery','Selected Gallery Artist','SANATÇI',(1050,328,350,95),17)
card('digital_gallery','selected_date','Gallery','Selected Gallery Date','TARİH',(1050,441,350,80),17)
vis('digital_gallery','selected_medium','multiRowCard',(1050,539,350,192),{'Values':[projection('Gallery','Selected Gallery Medium',True,label='Malzeme / teknik')]},'Malzeme ve teknik',{'dataLabels':[{'properties':{'fontSize':literal(13)}}]})
vis('digital_gallery','source_links','tableEx',(406,744,994,110),{'Values':[projection('Gallery','Selected Met URL',True,label='Met eser sayfası ↗'),projection('Gallery','Selected Artist Wiki URL',True,label='Sanatçı • Wikidata ↗'),projection('Gallery','Selected Object Wiki URL',True,label='Eser • Wikidata ↗')]},'Kaynakları aç',{
    'values':[{'properties':{'urlIcon':literal(True),'fontColor':color('#B5121B'),'fontSize':literal(12)}}],
    'columnHeaders':[{'properties':{'fontSize':literal(11)}}],
    'grid':[{'properties':{'rowPadding':literal(2)}}], 'total':[{'properties':{'show':literal(False)}}]})
links_path=REPORT/'definition/pages/digital_gallery/visuals/source_links/visual.json'
links_visual=load(links_path)
links_visual['visual']['visualContainerObjects']['title'][0]['properties']['show']=literal(False)
write(links_path,links_visual)
card('digital_gallery','selection_count','Gallery','Gallery Artwork Count','SEÇKİDEKİ ESER',(40,750,342,88),22)
text('digital_gallery','source_note','Görseller: The Met Collection API • Kamu malı / açık erişim • Bu seçki tüm koleksiyonu temsil etmez.',(40,856,1360,26),10,'#6B6258')
gallerypage=load(REPORT/'definition/pages/digital_gallery/page.json')
gallerypage['visualInteractions']=[{'source':'artwork_selector','target':name,'type':'DataFilter'} for name in ['hero_image','selected_title','selected_artist','selected_date','selected_medium','source_links','selection_count']]
write(REPORT/'definition/pages/digital_gallery/page.json',gallerypage)

# Dark bubble explorer: genuine collection metrics, selectable department bubbles.
page('collection_explorer','Koleksiyon pusulası','#141A20')
text('collection_explorer','eyebrow','MET ATLAS / KOLEKSİYON PUSULASI',(40,20,950,25),12,'#E5BC78',dark=True)
text('collection_explorer','heading','Her balon, farklı bir dünya.',(40,48,1300,60),32,'#F5EFE6','Georgia',True)
text('collection_explorer','instructions','Bir departman balonuna tıkla: sağdaki kültür dağılımı ve kartlar seçime göre değişir. Balon büyüklüğü = eser sayısı.',(40,112,1360,35),12,'#BFC8CF',dark=True)
for name,column,label,x in [('period_filter','timeline_period','Dönem',40),('material_filter','object_type_material','Tür / malzeme',500),('culture_filter','culture','Kültür',960)]:
    vis('collection_explorer',name,'slicer',(x,166,440,70),{'Values':[projection('Artwork',column)]},label,{
        'data':[{'properties':{'mode':literal('Dropdown')}}], 'header':[{'properties':{'show':literal(False)}}],
        'items':[{'properties':{'fontColor':color('#F5EFE6'),'background':color('#22272B'),'fontSize':literal(12)}}]},dark=True)
axis={'labelColor':color('#BFC8CF'),'showAxisTitle':literal(True),'fontSize':literal(11),'gridlineShow':literal(True),'gridlineColor':color('#38434A')}
vis('collection_explorer','department_bubbles','scatterChart',(40,260,870,565),{
    'Category':[projection('Artwork','department')],
    'X':[projection('Artwork','Public Domain Share',True,label='Kamu malı payı')],
    'Y':[projection('Artwork','Gallery Information Share',True,label='Galeri bilgisi payı')],
    'Size':[projection('Artwork','Artwork Count',True,label='Eser sayısı')],
    'Tooltips':[projection('Artwork','Highlight Share',True,label='Öne çıkan eser payı')]},'Departmanların erişim ve galeri profili',{
        'categoryAxis':[{'properties':dict(axis,start=literal(-0.08),end=literal(1.08))}], 'valueAxis':[{'properties':dict(axis,start=literal(-0.06),end=literal(0.78))}],
        'dataPoint':[{'properties':{'fill':color('#E5BC78')}}],
        'categoryLabels':[{'properties':{'show':literal(True),'color':color('#F5EFE6'),'fontSize':literal(10)}}],
        'legend':[{'properties':{'show':literal(False)}}]},dark=True)
card('collection_explorer','selected_count','Artwork','Artwork Count','SEÇİLİ ESERLER',(934,260,466,110),29,True)
card('collection_explorer','selected_public','Artwork','Public Domain Share','KAMU MALI PAYI',(934,390,222,100),25,True)
card('collection_explorer','selected_gallery','Artwork','Gallery Information Share','GALERİ BİLGİSİ',(1178,390,222,100),25,True)
vis('collection_explorer','culture_ranking','barChart',(934,510,466,315),{'Category':[projection('Artwork','culture')],'Y':[projection('Artwork','Artwork Count',True)]},'Seçili departmanda kültürler',{
    'categoryAxis':[{'properties':{'labelColor':color('#F5EFE6'),'fontSize':literal(10)}}],
    'valueAxis':[{'properties':{'labelColor':color('#BFC8CF'),'gridlineShow':literal(False)}}],
    'dataPoint':[{'properties':{'fill':color('#75B8B0')}}]},True,sort=(field('Artwork','Artwork Count',True),'Descending'))
text('collection_explorer','footnote','Kamu malı ve galeri bilgisi payları aynı filtrede hesaplanır. Galeri numarası, güncel sergilenme durumunu kanıtlamaz.',(40,852,1360,30),10,'#BFC8CF',dark=True)
explorer=load(REPORT/'definition/pages/collection_explorer/page.json')
explorer['visualInteractions']=[{'source':'department_bubbles','target':name,'type':'DataFilter'} for name in ['selected_count','selected_public','selected_gallery','culture_ranking']]
write(REPORT/'definition/pages/collection_explorer/page.json',explorer)

pages=load(REPORT/'definition/pages/pages.json')
for newpage in ['digital_gallery','collection_explorer']:
    if newpage not in pages['pageOrder']: pages['pageOrder'].append(newpage)
pages['activePageName']='digital_gallery'
write(REPORT/'definition/pages/pages.json',pages)
print(f'Added 2 pages, {len(catalog)} curated artworks, {len(measures)} gallery measures. Backup: {BACKUP}')
