"""Prepare the point selector's complete offline terrain/path overview."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))

from homecoming.app import overview_frame
from homecoming.services.basemap import basemap


if __name__=='__main__':
    _,xmin,ymax,scale=overview_frame()
    bounds=[xmin,ymax-650/scale,xmin+1000/scale,ymax]
    image=basemap().image(bounds,(1600,1040))
    path=ROOT/'assets/maps/selection-background.webp'
    image.save(path,'WEBP',quality=85,method=0)
    image.close()
    print(path,path.stat().st_size,'bytes')
