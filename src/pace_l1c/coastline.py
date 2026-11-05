"""Optional offline Natural Earth coastline annotation, fetched explicitly."""
from io import BytesIO
from pathlib import Path
import json
import hashlib
import zipfile
import numpy as np

URL="https://naturalearth.s3.amazonaws.com/110m_physical/ne_110m_coastline.zip"


def acquire(destination="data/coastlines.json"):
    import requests
    import shapefile
    r=requests.get(URL,timeout=60);r.raise_for_status()
    with zipfile.ZipFile(BytesIO(r.content)) as z:
        reader=shapefile.Reader(shp=BytesIO(z.read('ne_110m_coastline.shp')),shx=BytesIO(z.read('ne_110m_coastline.shx')),dbf=BytesIO(z.read('ne_110m_coastline.dbf')))
        lines=[]
        for shape in reader.shapes():
            stops=list(shape.parts)+[len(shape.points)]
            lines.extend([shape.points[a:b] for a,b in zip(stops[:-1],stops[1:])])
    value={"source":URL,"download_sha256":hashlib.sha256(r.content).hexdigest(),"scale":"1:110m","license":"Natural Earth public domain","lines":lines}
    path=Path(destination);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value))
    return path


def load(path="data/coastlines.json"):
    path=Path(path)
    if not path.is_file():
        return None
    return json.loads(path.read_text())


def projected_lines(coast,grid,projection):
    if not coast or projection=="native":
        return []
    output=[]
    for line in coast["lines"]:
        a=np.asarray(line)
        if len(a)<2:
            continue
        lon=grid.center_lon+(a[:,0]-grid.center_lon+180)%360-180
        lat=a[:,1]
        if projection=="laea":
            x,y=grid.transformer.transform(lon,lat)
            points=np.stack((np.asarray(x)/1000,np.asarray(y)/1000),axis=-1)
        else:
            points=np.stack((lon,lat),axis=-1)
        cuts=np.flatnonzero((np.abs(np.diff(lon))>180)|~np.isfinite(points[:-1]).all(axis=-1)|~np.isfinite(points[1:]).all(axis=-1))+1
        for chunk in np.split(points,cuts):
            if len(chunk)<2:
                continue
            xmin,xmax,ymin,ymax=grid.bounds
            if chunk[:,0].min()<=xmax and chunk[:,0].max()>=xmin and chunk[:,1].min()<=ymax and chunk[:,1].max()>=ymin:
                output.append(chunk)
    return output
