"""Render PNG previews of the housing maps with the existing plotting stack."""
import os
os.environ.setdefault('MPLCONFIGDIR', '/tmp/hk-pedestrian-matplotlib')
import csv
import xml.etree.ElementTree as ET

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.path import Path
from matplotlib.patches import PathPatch
from pyogrio.raw import read
import shapely
from housing_districts import OUT, ROOT, NS, COLORS, load_regions, polygons, PROJECT


def polygon_path(geometry):
    vertices, codes = [], []
    for p in polygons(geometry):
        for ring in [p.exterior, *p.interiors]:
            coords = list(ring.coords)
            vertices.extend(coords)
            codes.extend([Path.MOVETO] + [Path.LINETO]*(len(coords)-2) + [Path.CLOSEPOLY])
    return Path(np.array(vertices), np.array(codes, dtype=np.uint8))


districts, regions, outside, land = load_regions()
bb = np.array([g.bounds for g in districts.values()])
x0, y0 = bb[:, :2].min(axis=0)-1600
x1, y1 = bb[:, 2:].max(axis=0)+1600
map_width, map_height = 869.76*2.7, 600.167364*2.7
network_path = None
for stem in ['hong_kong_housing_districts', 'hong_kong_estates_hospitals_numbered']:
    root = ET.parse(OUT / (stem+'.svg')).getroot()
    width, height = map(float, root.get('viewBox').split()[2:])
    fig = plt.figure(figsize=(width/100, height/100), dpi=100, facecolor='#f7f6f2')
    ax = fig.add_axes([55/width, 1-(160+map_height)/height, map_width/width, map_height/height])
    ax.set_facecolor('#f7f6f2')
    ax.add_patch(PathPatch(polygon_path(land), facecolor='#e8e6df', edgecolor='none'))
    for name, g in regions.items():
        ax.add_patch(PathPatch(polygon_path(g.intersection(land)), facecolor=COLORS[name], edgecolor='none'))
    combined = 'estates' in stem
    if combined:
        source = '/vsizip/' + str(ROOT / 'data/organized/core/pedestrian/3D_Pedestrian_Network_FGDB.zip') + '/3DPN_P2.gdb'
        _, _, wkb, _ = read(source, layer='PedestrianRoute', columns=[])
        geoms = shapely.get_parts(shapely.from_wkb(wkb))
        coords = shapely.get_coordinates(geoms)
        counts = shapely.get_num_coordinates(geoms)
        codes = np.full(len(coords), Path.LINETO, dtype=np.uint8)
        codes[np.r_[0, np.cumsum(counts)[:-1]]] = Path.MOVETO
        network_path = Path(coords, codes)
        ax.add_patch(PathPatch(network_path, fill=False, edgecolor='#87969c', linewidth=.105*2.7*.72, alpha=.45))
    for p in polygons(land):
        xy = np.asarray(p.exterior.coords)
        ax.plot(xy[:, 0], xy[:, 1], color='#809299', lw=.35*2.7*.72)
    for name, g in regions.items():
        ax.add_patch(PathPatch(polygon_path(g), fill=False, edgecolor='#354c5c', linewidth=.85*2.7*.72))
    sx, sy = x0+2700, y0+2200
    ax.plot([sx, sx+10000], [sy, sy], color='#233845', lw=2*2.7*.72)
    for x in [sx, sx+5000, sx+10000]: ax.plot([x,x],[sy-250,sy+250],color='#233845',lw=2.7*.72)
    ax.text(sx+5000,sy+650,'10 km',ha='center',fontsize=9*2.7*.72)
    ax.annotate('N',xy=(x1-2400,y1-5500),xytext=(x1-2400,y1-8500),ha='center',
                fontsize=12*2.7*.72,fontweight='bold',arrowprops=dict(arrowstyle='-|>',color='#233845'))
    if combined:
        for row in csv.DictReader((OUT/'hong_kong_estates_hospitals_index.csv').open()):
            x,y = PROJECT.transform(float(row['longitude']),float(row['latitude']))
            color = '#16834b' if row['kind']=='estate' else '#d7353f'
            ax.plot(x,y,'o',markersize=12*.72,color=color,markeredgecolor='white',markeredgewidth=.6*.72)
            ax.text(x,y,row['number'],ha='center',va='center',color='white',fontweight='bold',
                    fontsize=(5.5 if int(row['number'])>=100 else 6.5)*.72)
    ax.set_xlim(x0,x1); ax.set_ylim(y0,y1); ax.set_aspect('equal'); ax.set_axis_off()
    # Copy the SVG's page headings, housing key, and full estate/hospital legend.
    text_elements = list(root.findall(f'{{{NS}}}text'))
    legend = root.find(f'{{{NS}}}g[@id="location-name-legend"]')
    if legend is not None: text_elements.extend(legend.findall(f'{{{NS}}}text'))
    for el in text_elements:
        fig.text(float(el.get('x'))/width,1-float(el.get('y'))/height,el.text or '',
                 fontsize=float(el.get('font-size','16'))*.72,color=el.get('fill','#233845'),
                 fontweight=el.get('font-weight','normal'),va='baseline')
    for el in root.findall(f'{{{NS}}}rect')[1:]:
        from matplotlib.patches import Rectangle
        x,y,w,h = [float(el.get(k)) for k in ['x','y','width','height']]
        fig.add_artist(Rectangle((x/width,1-(y+h)/height),w/width,h/height,
                                transform=fig.transFigure,facecolor=el.get('fill'),edgecolor='#354c5c',linewidth=.6))
    fig.savefig(OUT/(stem+'_preview.png'),dpi=100,facecolor=fig.get_facecolor())
    plt.close(fig)
    print('Rendered',stem,flush=True)
