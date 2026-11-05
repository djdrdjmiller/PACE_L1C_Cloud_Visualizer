"""Bounded acquisition of the exact PROFILE/MET inputs declared by OCI CLD."""
from pathlib import Path
import json
import re
import xarray as xr
from .reader import sha256


def input_names(cloud):
    with xr.open_dataset(cloud,group='processing_control/input_parameters',engine='h5netcdf') as ds:
        pars={k:str(v) for k,v in ds.attrs.items() if re.fullmatch(r'(anc_profile|met)[123]',k)}
    names=sorted({Path(v).name for v in pars.values() if v})
    if not names or not all(re.fullmatch(r'GMAO_[\w.-]+\.(PROFILE|MET)\.nc',n) for n in names):
        raise ValueError('Cloud product lacks supported exact PROFILE/MET input names')
    return names,pars


def acquire(cloud, directory, budget_mib=512, session=None, *, kind='all', cancelled=None, progress=None):
    """Independent budget; failed bytes count. No automatic eviction or substitution."""
    if budget_mib<=0:raise ValueError('Positive ancillary budget required')
    if kind not in ('all','met'):raise ValueError('Ancillary kind must be all or met')
    cancelled=cancelled or (lambda:False)
    progress=progress or (lambda value:None)
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    record=directory/'acquisition.json'
    m=json.loads(record.read_text()) if record.exists() else {'attempted_bytes':0,'files':{}}
    names,pars=input_names(cloud)
    if kind=='met':names=[n for n in names if '.MET.' in n]
    if not names:raise ValueError('Cloud product lacks requested ancillary kind')
    m['cloud']={'name':Path(cloud).name,'sha256':sha256(cloud),'input_parameters':pars}
    def save():
        temp=record.with_suffix('.tmp');temp.write_text(json.dumps(m,indent=2));temp.replace(record)
    complete=all((directory/n).is_file() and m['files'].get(n,{}).get('status')=='complete' and sha256(directory/n)==m['files'][n].get('sha256') for n in names)
    if complete:save();return record
    if session is None:
        import earthaccess
        auth=earthaccess.login(strategy='netrc',persist=False)
        if not auth.authenticated:raise RuntimeError('Earthdata login required')
        session=earthaccess.get_requests_https_session()
    limit=int(budget_mib*2**20)
    for name in names:
        _check_cancelled(cancelled)
        target=directory/name
        previous=m['files'].get(name,{})
        if target.exists():
            digest=sha256(target)
            if previous.get('status')=='complete' and digest==previous.get('sha256'):continue
            raise ValueError(f'Unverified cache file {name}; choose another cache directory')
        part=target.with_suffix('.nc.part');entry={'status':'pending','bytes':0};m['files'][name]=entry;save()
        try:
            with session.get('https://oceandata.sci.gsfc.nasa.gov/ob/getfile/'+name,stream=True,timeout=(30,120)) as response:
                response.raise_for_status()
                if 'text/html' in response.headers.get('Content-Type',''):raise RuntimeError('Earthdata returned HTML; login may be needed')
                size=int(response.headers.get('Content-Length',0))
                if m['attempted_bytes']+size>limit:raise ValueError('Ancillary acquisition budget exceeded')
                with part.open('wb') as f:
                    for chunk in response.iter_content(2**20):
                        _check_cancelled(cancelled)
                        m['attempted_bytes']+=len(chunk);entry['bytes']+=len(chunk);save()
                        if m['attempted_bytes']>limit:raise ValueError('Ancillary acquisition budget exceeded during transfer')
                        f.write(chunk)
                        progress({'file':name,'status':'transferring','bytes':entry['bytes'],'attempted_bytes':m['attempted_bytes']})
                if size and entry['bytes']!=size:raise ValueError('Incomplete ancillary transfer')
                with xr.open_dataset(part,engine='h5netcdf') as ds:
                    if ds.attrs.get('product_name')!=name:raise ValueError('Ancillary product identity mismatch')
                entry.update(status='complete',sha256=sha256(part));part.replace(target)
        except Exception as error:
            reason=str(error) if isinstance(error,(ValueError,RuntimeError)) else 'Transfer failed; HTTP status '+str(getattr(getattr(error,'response',None),'status_code','unavailable'))
            entry.update(status='failed',reason=f'{type(error).__name__}: {reason}')
            part.unlink(missing_ok=True);save();raise
        save()
    return record


def acquire_clouds(product,directory,budget_mib=256,max_granules=3,local_clouds=(),*,session=None,cancelled=None,progress=None):
    """Discover CLD across actual OCI view times; bound candidates and new transfers."""
    import earthaccess
    import numpy as np
    from .atmosphere import observation_times
    from .acquisition import catalog_record
    if budget_mib<=0 or not 1<=max_granules<=20:raise ValueError('Positive cloud budget and 1–20 candidate bound required')
    cancelled=cancelled or (lambda:False)
    progress=progress or (lambda value:None)
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    record=directory/'cloud-acquisition.json'
    m=json.loads(record.read_text()) if record.exists() else {'attempted_bytes':0,'files':{}}
    def save():
        temp=record.with_suffix('.tmp');temp.write_text(json.dumps(m,indent=2));temp.replace(record)
    times=observation_times(product)
    start=str(np.datetime64(int(np.nanmin(times)*1e9),'ns'));end=str(np.datetime64(int(np.nanmax(times)*1e9),'ns'))
    m['search']={'collection':'PACE_OCI_L2_CLOUD','version':'3.1','start':start,'end':end,'max_granules':max_granules};save()
    try:
        entries=[catalog_record(g,'oci_cloud') for g in earthaccess.search_data(short_name='PACE_OCI_L2_CLOUD',version='3.1',temporal=(start,end),count=max_granules+1)]
        m['search']={'collection':'PACE_OCI_L2_CLOUD','version':'3.1','start':start,'end':end,'returned':len(entries)}
        if not entries:raise ValueError('No matching OCI L2 cloud products found in the supported collection/time window')
        if len(entries)>max_granules:raise ValueError('OCI cloud candidates exceed the configured granule bound; narrow the acquisition or raise the explicit bound')
        m['candidates']=[{k:v for k,v in e.items() if k!='catalog'} for e in entries];save()
    except Exception as error:
        m['search_failure']=type(error).__name__;save();raise
    limit=int(budget_mib*2**20)
    local={Path(p).name:Path(p) for p in local_clouds}
    result=[]
    for e in entries:
        _check_cancelled(cancelled)
        name=e['name'];target=local.get(name,directory/name)
        previous=m['files'].get(name,{})
        if target.exists():
            digest=sha256(target)
            if name not in local and digest!=previous.get('sha256'):raise ValueError('Unverified cloud cache file')
            with xr.open_dataset(target,engine='h5netcdf') as ds:
                if ds.attrs.get('product_name')!=name:raise ValueError('Cloud product identity mismatch')
            m['files'][name]={'status':'complete','sha256':digest,'local_reuse':name in local};result.append(target);save();continue
        if session is None:
            auth=earthaccess.login(strategy='netrc',persist=False)
            if not auth.authenticated:raise RuntimeError('Earthdata login required')
            session=earthaccess.get_requests_https_session()
        size=e['size_bytes'];part=target.with_suffix('.nc.part');entry={'status':'pending','bytes':0};m['files'][name]=entry;save()
        try:
            if size<=0 or m['attempted_bytes']+size>limit:raise ValueError('Cloud acquisition budget exceeded or catalog size unavailable')
            with session.get('https://oceandata.sci.gsfc.nasa.gov/ob/getfile/'+name,stream=True,timeout=(30,120)) as response:
                response.raise_for_status()
                with part.open('wb') as f:
                    for chunk in response.iter_content(2**20):
                        _check_cancelled(cancelled)
                        m['attempted_bytes']+=len(chunk);entry['bytes']+=len(chunk);save()
                        if m['attempted_bytes']>limit:raise ValueError('Cloud transfer budget exceeded')
                        f.write(chunk)
                        progress({'file':name,'status':'transferring','bytes':entry['bytes'],'attempted_bytes':m['attempted_bytes']})
            if entry['bytes']!=size:raise ValueError('Cloud transfer size differs from catalog')
            with xr.open_dataset(part,engine='h5netcdf') as ds:
                if ds.attrs.get('product_name')!=name:raise ValueError('Cloud product identity mismatch')
            entry.update(status='complete',sha256=sha256(part));part.replace(target);result.append(target)
        except Exception as error:
            entry.update(status='failed',reason=type(error).__name__);part.unlink(missing_ok=True);save();raise
        save()
    return result


def _check_cancelled(cancelled):
    if cancelled():
        from .acquisition import DownloadCancelled
        raise DownloadCancelled('Ancillary acquisition cancelled')
