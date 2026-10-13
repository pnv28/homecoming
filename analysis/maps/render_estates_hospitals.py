"""Add numbered, coordinate-accurate locations to the existing precise SVG."""
import csv
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
from pyproj import Transformer
from housing_districts import load_regions, save_crosswalk, install_overlay, COLORS

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent.parent
NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)
ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
def node(parent, tag, **attrs):
    return ET.SubElement(parent, f'{{{NS}}}{tag}', {k.replace('_', '-'): str(v) for k,v in attrs.items()})
def text(parent, x, y, label, size=16, color='#233845', **attrs):
    el = node(parent, 'text', x=x, y=y, fill=color, font_size=size, font_family='Arial, sans-serif', **attrs)
    el.text = label
    return el

source = ET.parse(OUT / 'hong_kong_paths_precise.svg').getroot()
axes = source.find(f'.//{{{NS}}}g[@id="axes_1"]')
for el in list(axes):
    if el.get('id','') in {f'text_{i}' for i in range(3,21)}:
        axes.remove(el)
# Preserve every original path vertex; mute the network to distinguish red hospitals.
network = axes.find(f'.//{{{NS}}}g[@id="pedestrian-path-overlay"]')
for el in network.iter():
    if el.get('style'):
        el.set('style',el.get('style').replace('#c04b23','#87969c').replace('opacity: 0.8','opacity: 0.45'))
clip = source.find(f'.//{{{NS}}}clipPath/{{{NS}}}rect')
mx,my,mw,mh = [float(clip.get(k)) for k in ['x','y','width','height']]
# Same district-derived extent and HK1980 projection used by render_maps.py.
project = Transformer.from_crs('EPSG:4326','EPSG:2326',always_xy=True)
from shapely.geometry import shape
from shapely.ops import transform
bounds=[transform(project.transform,shape(f['geometry'])).bounds for f in json.loads((OUT/'district_boundaries.json').read_text())['features']]
x0=min(b[0] for b in bounds)-1600; y0=min(b[1] for b in bounds)-1600
x1=max(b[2] for b in bounds)+1600; y1=max(b[3] for b in bounds)+1600
districts, housing_regions, outside, land = load_regions()
estate_crosswalk = save_crosswalk(housing_regions)
clip_id = source.find(f'.//{{{NS}}}clipPath').get('id')
install_overlay(axes, clip_id, (mx,my,mw,mh), (x0,y0,x1,y1), housing_regions, outside, land)
scale=2.7
left,top=55,160
width=2460
map_bottom=top+mh*scale
legend_top=map_bottom+100
height=legend_top+1360
svg=ET.Element(f'{{{NS}}}svg',width=str(width),height=str(round(height)),viewBox=f'0 0 {width} {height:.2f}',version='1.1')
node(svg,'rect',width=width,height=height,fill='#f7f6f2')
for defs in source.findall(f'{{{NS}}}defs'): svg.append(defs)
text(svg,55,62,'HONG KONG / ESTATES & HOSPITALS',38,font_weight='bold')
text(svg,55,98,'Green: estates 1–244    ·    Red: hospitals 1–44    ·    Names indexed below',22)
text(svg,55,130,'Housing districts: HD300 Part 5 · merged HAD districts; Tung Chung / Tseung Kwan O use EAC 2019 area proxies',17,color='#526875')
base=node(svg,'g',id='precise-base-map',transform=f'translate({left-mx*scale} {top-my*scale}) scale({scale})')
base.append(axes)
def housing_legend(parent):
    for i, (name, color) in enumerate(COLORS.items()):
        x = 55 + i*570
        node(parent,'rect',x=x,y=map_bottom+20,width=25,height=20,fill=color,stroke='#354c5c',stroke_width=.8)
        text(parent,x+35,map_bottom+37,name,20,font_weight='bold')
    text(parent,55,map_bottom+67,'Grey: areas outside the named allocation areas (rural Sai Kung) · Derived geography, not HA-issued boundary polygons',16,color='#526875')
housing_legend(svg)
rows=[]
for kind,file,name,lat,lon,color in [
 ('estate','data/organized/core/estates/prh-estates.json','Estate Name','Estate Map Latitude','Estate Map Longitude','#16834b'),
 ('hospital','data/organized/supplementary/hospitals/facility-hosp.json','institution_eng','latitude','longitude','#d7353f')]:
    records=json.loads((ROOT/file).read_text())
    records.sort(key=lambda r:(r[name]['en'] if kind=='estate' else r[name]).casefold())
    for i,r in enumerate(records,1):
        label=r[name]['en'] if kind=='estate' else r[name]
        latitude,longitude=float(r[lat]),float(r[lon])
        assert math.isfinite(latitude) and math.isfinite(longitude)
        x,y=project.transform(longitude,latitude)
        assert x0<=x<=x1 and y0<=y<=y1,(kind,label,x,y)
        px=left+(x-x0)/(x1-x0)*mw*scale
        py=top+(y1-y)/(y1-y0)*mh*scale
        rows.append(dict(kind=kind,number=i,name=label,latitude=latitude,longitude=longitude,x=px,y=py,color=color))
# Each numbered circle is centered on its original coordinate.
dots=node(svg,'g',id='exact-location-points')
for r in rows:
    x,y=r['x'],r['y']
    g=node(dots,'g',id=f"{r['kind']}-{r['number']}")
    node(g,'title').text=f"{r['kind'].title()} {r['number']}: {r['name']} ({r['latitude']}, {r['longitude']})"
    node(g,'circle',cx=x,cy=y,r=6,fill=r['color'],stroke='white',stroke_width=.6)
    text(g,x,y,str(r['number']),5.5 if r['number']>=100 else 6.5,color='white',text_anchor='middle',dominant_baseline='central',font_weight='bold')
legend=node(svg,'g',id='location-name-legend')
for kind,color,cols,start_y in [('estate','#16834b',5,legend_top),('hospital','#d7353f',4,legend_top+990)]:
    items=[r for r in rows if r['kind']==kind]
    text(legend,55,start_y,f"{'ESTATES' if kind=='estate' else 'HOSPITALS'} / {len(items)}",25,color=color,font_weight='bold')
    per_col=math.ceil(len(items)/cols); colw=(width-110)/cols
    import textwrap
    for j,r in enumerate(items):
        col,row=divmod(j,per_col); xx=55+col*colw; yy=start_y+38+row*(19 if kind=='estate' else 25)
        text(legend,xx,yy,str(r['number']),14,color=color,font_weight='bold')
        lines=textwrap.wrap(r['name'],width=48 if kind=='hospital' else 44)
        assert len(lines)<=2
        for k,line in enumerate(lines): text(legend,xx+38,yy+k*11,line,13 if len(lines)>1 else 14)
text(svg,55,height-58,'SOURCES  Local estate / hospital JSON · pedestrian FGDB · HAD districts · EAC 2019 constituencies · HD300 · © OpenStreetMap contributors',15,color='#526875')
text(svg,55,height-32,'CRS  WGS84 locations transformed to Hong Kong 1980 Grid (EPSG:2326). Numbers are centered inside the location circles.',15,color='#526875')
path=OUT/'hong_kong_estates_hospitals_numbered.svg'
ET.ElementTree(svg).write(path,encoding='utf-8',xml_declaration=True)
with (OUT/'hong_kong_estates_hospitals_index.csv').open('w') as f:
    writer=csv.DictWriter(f,fieldnames=['kind','number','name','latitude','longitude'])
    writer.writeheader(); writer.writerows({k:r[k] for k in writer.fieldnames} for r in rows)
print(f'Created {path}: {len(rows)} exact points and indexed names; numbers inside coordinate circles.')

# A separate housing-only map uses the same extent and boundary geometry.
housing_svg=ET.Element(f'{{{NS}}}svg',width=str(width),height=str(round(map_bottom+105)),
                      viewBox=f'0 0 {width} {map_bottom+105:.2f}',version='1.1')
node(housing_svg,'rect',width=width,height=map_bottom+105,fill='#f7f6f2')
for defs in source.findall(f'{{{NS}}}defs'): housing_svg.append(defs)
text(housing_svg,55,62,'HONG KONG / HOUSING DISTRICTS',38,font_weight='bold')
text(housing_svg,55,98,'Public rental housing allocation districts · HD300 Part 5',22)
text(housing_svg,55,130,'Merged official HAD districts · Tung Chung / Tseung Kwan O: EAC 2019 smaller-area proxies',17,color='#526875')
housing_base=node(housing_svg,'g',transform=base.get('transform'))
housing_axes=node(housing_base,'g',id='housing-map')
for el in axes:
    if el.get('id')!='pedestrian-path-overlay': housing_axes.append(el)
housing_legend(housing_svg)
ET.ElementTree(housing_svg).write(OUT/'hong_kong_housing_districts.svg',encoding='utf-8',xml_declaration=True)
