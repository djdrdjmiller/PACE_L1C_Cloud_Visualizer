"""Independent Rayleigh boundary caches and legacy transmission. TOA stays intact.

Source conventions: NASA OCSSW libcloud/profile_management.c and
ancillary_module.f90; strict LUT interpolation differs from operational repair.
Cloud/surface boundary estimates are identified, never operational retrievals.
"""
from pathlib import Path
import json
import time
import numpy as np
import xarray as xr
from scipy.interpolate import RegularGridInterpolator
from scipy.spatial import cKDTree
from scipy.ndimage import convolve, generic_filter
from .reader import ROW,COL,VIEW,sha256,jsonable
from .ancillary import input_names

TRANSMISSION_VARIABLES=('Cloud_Top_Pressure','View_Angle_Cosine','Precipitable_Water','Wavelengths','Transmittance','counts','Standard_Deviation')

SOURCE='https://git.smce.nasa.gov/oel/ocssw/-/tree/8e8615cbca5becf542f2ef30fe89418baf33faac/src/libcloud'


def pressure_grid():
    l=np.arange(101,0,-1,dtype=float)
    return (-1.550789414500298e-4*l*l-.05593654380586063*l+7.451622227151780)**3.5


def water_column(p,q,boundary,ps,q_surface,clear):
    """Cloud: original 101-level rule. Clear: measured QV10M surface endpoint.

    No use of below-ground QV or humidity extrapolation. Cloud integration that
    needs repaired surface levels is rejected. Clear integration terminates at PS.
    Surface QV10M approximates surface humidity, explicitly not a 0 m measurement.
    """
    order=np.argsort(p);p=np.asarray(p)[order];q=np.asarray(q)[:,order]
    pp=pressure_grid();out=np.full(len(boundary),np.nan)
    for i,b in enumerate(boundary):
        if not np.isfinite(b+ps[i]) or b<pp[0] or b>ps[i]:continue
        if clear[i]:
            keep=p<ps[i]
            qs=q_surface[i]
            if not np.isfinite(qs) or not 0<=qs<1 or not keep.any():continue
            nodes=np.r_[p[keep],ps[i]];values=np.r_[q[i,keep],qs]
            if not np.all(np.isfinite(values)&(values>=0)&(values<1)):continue
            mixing=1000*values/(1-values)
            grid=np.r_[pp[pp<b],b]
            humidity=np.interp(np.log(grid),np.log(nodes),mixing,left=.003)
        else:
            end=min(np.searchsorted(pp,b),100)
            upper=p[min(np.searchsorted(p,pp[end]),len(p)-1)]
            if upper>=ps[i] or pp[end]>p[-1] or end<1:continue
            keep=p<=upper;values=q[i,keep]
            if not np.all(np.isfinite(values)&(values>=0)&(values<1)):continue
            humidity=np.interp(np.log(pp[:end+1]),np.log(p[keep]),1000*values/(1-values),left=.003)
            last=np.interp(b,pp[end-1:end+1],humidity[end-1:end+1])
            grid=np.r_[pp[:end],b];humidity=np.r_[humidity[:end],last]
        out[i]=np.trapezoid(humidity,x=grid)/980.616
    return out


def sample(path,var,lat,lon):
    with xr.open_dataset(path,engine='h5netcdf') as ds:
        a=ds[var].sortby('lat').sortby('lon')
        expected={'QV':('kg kg-1','kg/kg'),'QV10M':('kg kg-1','kg/kg'),'PS':('Pa',)}[var]
        if a.attrs.get('units') not in expected:raise ValueError(f'Unexpected {var} units')
        a=a.transpose('lat','lon',*(['lev'] if 'lev' in a.dims else []))
        v=a.values;lats=a.lat.values;lons=a.lon.values
        v=np.concatenate((v[:,-1:],v,v[:,:1]),axis=1)
        longitudes=np.r_[lons[-1]-360,lons,lons[0]+360]
        points=np.column_stack((lat,lons[0]+(lon-lons[0])%360))
        value=RegularGridInterpolator((lats,longitudes),v,bounds_error=False,fill_value=np.nan)(points)
        p=ds.lev.values.copy() if 'lev' in a.dims else None
        if p is not None and ds.lev.attrs.get('units')!='hPa':raise ValueError('Unexpected profile pressure units')
        seconds=float(np.datetime64(ds.attrs['time_coverage_start'].replace('Z',''),'ns').astype('int64'))/1e9
    return value,p,seconds


def sample_times(paths,var,lat,lon,seconds):
    records=[sample(p,var,lat,lon) for p in paths];records.sort(key=lambda r:r[2])
    result=np.full_like(records[0][0],np.nan,dtype=float)
    for left,right in zip(records,records[1:]):
        if not np.array_equal(left[1],right[1]):raise ValueError('Ancillary pressure grids differ')
        good=(seconds>=left[2])&(seconds<=right[2]);w=(seconds[good]-left[2])/(right[2]-left[2])
        if result.ndim>1:w=w[:,None]
        result[good]=(1-w)*left[0][good]+w*right[0][good]
    if len(records)==1:
        good=np.abs(seconds-records[0][2])<1;result[good]=records[0][0][good]
    return result,records[0][1]


def xyz(lat,lon):
    lat,lon=np.deg2rad(lat),np.deg2rad(lon)
    return np.column_stack((np.cos(lat)*np.cos(lon),np.cos(lat)*np.sin(lon),np.sin(lat)))


def cloud_fallback(phase,ctp,ps,radius=3):
    """Visualization heuristic: bounded neighborhood votes, no iterative propagation."""
    clear=phase==1;cloud=np.isin(phase,[2,3,4])
    direct=cloud&np.isfinite(ctp)&(ctp>0)&(ctp<=ps)
    kernel=np.ones((radius*2+1,)*2);kernel[radius,radius]=0
    nc=convolve(cloud.astype(float),kernel,mode='constant',cval=0)
    ns=convolve(clear.astype(float),kernel,mode='constant',cval=0)
    need=~clear&~direct
    enough=(nc+ns)>=3
    infer_cloud=need&enough&(nc>=2*ns)&(nc>0)
    infer_clear=need&~cloud&enough&(ns>=2*nc)&(ns>0)
    def median(v):
        finite=v[np.isfinite(v)]
        return np.median(finite) if len(finite)>=3 else np.nan
    nearest=generic_filter(np.where(direct,ctp,np.nan),median,size=radius*2+1,mode='constant',cval=np.nan)
    boundary=np.where(clear,ps,np.where(direct,ctp,np.nan))
    use=infer_cloud&np.isfinite(nearest)&(nearest<=ps)
    boundary[use]=nearest[use];boundary[infer_clear]=ps[infer_clear]
    state=np.zeros(phase.shape,dtype=np.int8)
    state[direct]=1;state[clear]=2;state[use]=3;state[infer_clear]=4
    return boundary,state


class TransmissionLUT:
    def __init__(self,path):
        from pyhdf.SD import SD,SDC
        f=SD(str(path),SDC.READ)
        try:
            self.d={}
            for name in ['Cloud_Top_Pressure','View_Angle_Cosine','Precipitable_Water','Wavelengths','Transmittance','counts','Standard_Deviation']:
                s=f.select(name)
                try:self.d[name]=np.asarray(s.get(),float)
                finally:s.endaccess()
        finally:f.end()
        self.validate()

    def validate(self):
        self.p=self.d['Cloud_Top_Pressure'];self.u=self.d['View_Angle_Cosine'];self.w=self.d['Precipitable_Water']
        if not np.allclose(self.p,np.arange(100,1001,100)) or not np.allclose(self.d['Wavelengths'],[.64,.86,.94,1.2,1.38,1.6,2.1,2.23],atol=.005):raise ValueError('Unexpected transmission LUT axes/order')
        if not all(np.all(np.diff(a)>0) for a in (self.p,self.u,self.w)):raise ValueError('Nonincreasing LUT axis')
        for name in ['Transmittance','counts','Standard_Deviation']:
            if self.d[name].shape!=(8,len(self.u),len(self.w),len(self.p)):raise ValueError('Unexpected transmission LUT dimensions')

    def evaluate(self,sza,vza,p,w,band=0,extend_surface=None):
        sza,vza,p,w=np.broadcast_arrays(*map(lambda a:np.asarray(a,float),(sza,vza,p,w)))
        mu0=np.cos(np.deg2rad(sza));mu=np.cos(np.deg2rad(vza))
        with np.errstate(invalid='ignore',divide='ignore'):u=mu0*mu/(mu0+mu)
        valid=np.isfinite(p+w+u)&(sza>=0)&(sza<90)&(vza>=0)&(vza<90)&(p>=100)&(p<=1000)&(w>=self.w[0])&(w<=self.w[-1])&(u>=self.u[0])&(u<=self.u[-1])
        pi=np.clip(np.floor((np.nan_to_num(p,nan=100)-100)/100+.5).astype(int),0,9)
        def bracket(a,x):
            low=np.clip(np.searchsorted(a,x,side='right')-1,0,len(a)-2)
            return low,(x-a[low])/(a[low+1]-a[low])
        ui,uw=bracket(self.u,u);wi,ww=bracket(self.w,w)
        out=np.zeros(p.shape)
        for du,wu in [(0,1-uw),(1,uw)]:
            for dw,wt in [(0,1-ww),(1,ww)]:
                value=self.d['Transmittance'][band,ui+du,wi+dw,pi];count=self.d['counts'][band,ui+du,wi+dw,pi]
                weight=wu*wt;needed=weight>1e-12
                valid&=~needed|((count>0)&np.isfinite(value)&(value>0)&(value<=1))
                out+=np.where(needed,value*weight,0)
        out=np.where(valid,out,np.nan)
        if extend_surface is not None:
            eligible=np.asarray(extend_surface,bool)&(p>1000)&(p<=1050)
            if eligible.any():
                top=self.evaluate(sza,vza,np.full(p.shape,1000.),w,band)
                lower=self.evaluate(sza,vza,np.full(p.shape,900.),w,band)
                with np.errstate(invalid='ignore',divide='ignore'):
                    tau=-np.log(top);slope=(-np.log(top)+np.log(lower))/100
                    extended=np.exp(-(tau+(p-1000)*slope))
                supported=np.isfinite(top+lower)&(slope>=-1e-12)&(extended>0)&(extended<=1)
                out=np.where(eligible&supported,extended,out)
        return out


def observation_times(product):
    ba=product.groups.get('bin_attributes')
    if ba is None:raise ValueError('Correction needs original bin/view observation times')
    t=ba.nadir_view_time.values
    if not np.issubdtype(t.dtype,np.datetime64):raise ValueError('Nadir time not decoded as CF datetime')
    t=t.astype('datetime64[ns]').astype('int64')/1e9
    offsets=ba.view_time_offsets.transpose(ROW,COL,VIEW).values
    if np.issubdtype(offsets.dtype,np.timedelta64):offsets=offsets/np.timedelta64(1,'s')
    count=product.read('number_of_observations');good=np.isfinite(count)&(count>0)
    chosen=np.argmax(good,axis=2)
    seconds=t[:,None]-np.take_along_axis(offsets,chosen[...,None],axis=2)[...,0]
    return np.where(good.sum(axis=2)==1,seconds,np.nan)


def prepare(scene,cloud,ancillary,lut_path,output,max_distance_km=3,max_time_s=10,*,mode=None):
    mode=mode or ('transmission' if lut_path is not None else 'rayleigh')
    if mode not in ('rayleigh','transmission'):raise ValueError('Unsupported atmospheric preparation mode')
    if mode=='rayleigh' and lut_path is not None:raise ValueError('Rayleigh preparation does not use --lut')
    if mode=='transmission' and lut_path is None:raise ValueError('Transmission preparation requires --lut')
    start=time.perf_counter();clouds=[cloud] if isinstance(cloud,(str,Path)) else cloud
    inputs=[input_names(c) for c in clouds];names=sorted({n for names,_ in inputs for n in names if mode=='transmission' or '.MET.' in n});paths=[Path(ancillary)/n for n in names]
    if not paths:raise ValueError('Cloud product lacks declared MET inputs')
    if not any('.MET.' in p.name for p in paths):raise ValueError('Cloud product lacks declared MET inputs')
    if mode=='transmission' and not any('.PROFILE.' in p.name for p in paths):raise ValueError('Transmission preparation needs declared PROFILE inputs')
    if any(not p.is_file() for p in paths):raise ValueError('Missing declared ancillary files; run atmosphere-acquire')
    times=observation_times(scene.oci);lat=scene.oci.lat.ravel();lon=scene.oci.lon.ravel();seconds=times.ravel()
    n=len(lat);ctp=np.full(n,np.nan);phase=ctp.copy();source_index=np.full(n,-1);owner=np.full(n,-1)
    match_distance=np.full(n,np.inf);match_dt=np.full(n,np.nan)
    for cloud_id,cloud in enumerate(clouds):
        with xr.open_dataset(cloud,group='navigation_data',engine='h5netcdf') as nav, xr.open_dataset(cloud,group='geophysical_data',engine='h5netcdf') as geo, xr.open_dataset(cloud,group='scan_line_attributes',engine='h5netcdf',decode_times=False) as scan:
            if geo.ctp.attrs.get('units') not in ('hPa','mbar'):raise ValueError('Unexpected cloud pressure units')
            phase_description=geo.cld_phase_21.attrs.get('long_name','')
            if not all(s in phase_description for s in ('1 - clear','2 - water cloud','3 - ice cloud')):raise ValueError('Unverified cloud phase codes')
            source_lat=nav.latitude.values;source_lon=nav.longitude.values
            valid=np.isfinite(source_lat+source_lon)&(np.abs(source_lat)<=90)&(np.abs(source_lon)<=180)
            flat=np.flatnonzero(valid);tree=cKDTree(xyz(source_lat.ravel()[flat],source_lon.ravel()[flat]))
            valid_target=np.isfinite(lat+lon+seconds)&(np.abs(lat)<=90)
            safe_lat=np.where(valid_target,lat,0);safe_lon=np.where(valid_target,lon,0)
            distance,index=tree.query(xyz(safe_lat,safe_lon),k=min(8,len(flat)))
            if distance.ndim==1:distance=distance[:,None];index=index[:,None]
            native=flat[index];rows=native//source_lat.shape[1]
            if not str(scan.time.attrs.get('units','')).startswith('seconds since 1970-1-1'):raise ValueError('Unverified native scan time units')
            native_time=scan.time.values[rows];dt=native_time-seconds[:,None]
            km=2*6371.0088*np.arcsin(np.clip(distance/2,0,1))
            compatible=(km<=max_distance_km)&(np.abs(dt)<=max_time_s)&valid_target[:,None]
            rank=np.where(compatible,km,np.inf);best=rank.argmin(axis=1);ii=np.arange(len(lat))
            matched=np.isfinite(rank[ii,best]);selected=native[ii,best]
            take=matched & (km[ii,best]<match_distance)
            ctp[take]=geo.ctp.values.ravel()[selected][take]
            phase[take]=geo.cld_phase_21.values.ravel()[selected][take]
            source_index[take]=selected[take];owner[take]=cloud_id
            match_distance[take]=km[ii,best][take];match_dt[take]=dt[ii,best][take]
    matched=owner>=0
    ctp=ctp.reshape(scene.shape);phase=phase.reshape(scene.shape)
    source_index=source_index.reshape(scene.shape);owner=owner.reshape(scene.shape)
    match_distance=np.where(matched,match_distance,np.nan).reshape(scene.shape);match_dt=match_dt.reshape(scene.shape)
    profiles=[p for p in paths if '.PROFILE.' in p.name];met=[p for p in paths if '.MET.' in p.name]
    ps,_=sample_times(met,'PS',lat,lon,seconds);ps/=100
    boundary,state=cloud_fallback(phase,ctp,ps.reshape(scene.shape))
    water=None;lut=None
    if mode=='transmission':
        q,p=sample_times(profiles,'QV',lat,lon,seconds)
        qs,_=sample_times(met,'QV10M',lat,lon,seconds)
        clear=np.isin(state,[2,4]);water=water_column(p,q,boundary.ravel(),ps,qs,clear.ravel()).reshape(scene.shape)
        lut=TransmissionLUT(lut_path)
    provenance={'method':'OCI cloud/MERRA-2 pressure boundaries for experimental Rayleigh' if mode=='rayleigh' else 'approximate transmission only; no Rayleigh/aerosol removal','cache_schema_version':1,'cache_kind':'rayleigh_boundary' if mode=='rayleigh' else 'transmission_boundary','inputs':[scene.oci.identity,scene.harp.identity],
        'clouds':[{'name':Path(c).name,'sha256':sha256(c),'input_parameters':inputs[i][1]} for i,c in enumerate(clouds)],
        'ancillary':[{'name':path.name,'sha256':sha256(path)} for path in paths],
        'source':SOURCE,
        'collocation':{'max_distance_km':max_distance_km,'max_time_s':max_time_s,'policy':'nearest time-compatible native OCI L2 center, no footprint averaging or parallax adjustment'},
        'fallback':{'radius_bins':3,'minimum_classified_neighbors':3,'majority_ratio':2,'minimum_cloud_pressures':3,'policy':'noniterative median cloud pressure or clear-surface vote; unknown stays missing'},
        'surface':'spatial/time-interpolated MET PS with QV10M boundary; model terrain, not fine-scale terrain adjustment',
        'humidity':'101-level log-pressure mixing ratio; 0.003 g/kg upper floor; trapezoid /980.616; clear boundary uses measured QV10M; no below-ground samples or extrapolation',
        'harp2_approximation':'same OCI-time collocated atmospheric column; each HARP2 view uses its own actual zenith geometry; visible-band 0.64 proxy',
        'state_codes':{'0':'unavailable','1':'direct cloud','2':'direct clear surface','3':'estimated cloud','4':'estimated clear surface'},
        'counts':{'matched':int(matched.sum()),'water_valid':int(np.isfinite(water).sum()) if water is not None else None,'boundary_missing':int((~np.isfinite(boundary)).sum()),'boundary_pressure_outside_lut':int((np.isfinite(boundary)&((boundary<100)|(boundary>1000))).sum()),**{f'state_{i}':int((state==i).sum()) for i in range(5)}}}
    if mode=='transmission':provenance['lut']={'name':Path(lut_path).name,'sha256':sha256(lut_path)}
    else:
        provenance.pop('humidity',None)
        provenance['surface']='Spatial/time-interpolated MERRA-2 MET PS; model terrain, not fine-scale terrain adjustment'
        provenance['harp2_approximation']='same OCI-time collocated boundary pressure; each HARP2 view uses its own actual geometry'
        provenance['counts'].pop('water_valid');provenance['counts'].pop('boundary_pressure_outside_lut')
    ds=xr.Dataset({'boundary_pressure':((ROW,COL),boundary),'boundary_state':((ROW,COL),state),
        'cloud_source_product':((ROW,COL),owner),'cloud_source_index':((ROW,COL),source_index),'match_distance_km':((ROW,COL),match_distance),'match_time_s':((ROW,COL),match_dt)},attrs={'provenance':json.dumps(provenance,sort_keys=True)})
    ds.boundary_pressure.attrs['units']='hPa'
    if water is not None:ds['water_column']=((ROW,COL),water,{'units':'g cm-2'})
    ds.boundary_state.attrs.update(flag_values=np.arange(5,dtype=np.int8),flag_meanings='unavailable direct_cloud direct_clear estimated_cloud estimated_clear')
    ds.match_distance_km.attrs['units']='km';ds.match_time_s.attrs['units']='s'
    for name,a in (lut.d.items() if lut is not None else []):
        dims={'Cloud_Top_Pressure':['pressure'],'View_Angle_Cosine':['cosine'],'Precipitable_Water':['water'],'Wavelengths':['band']}.get(name,['band','cosine','water','pressure'])
        ds[name]=(dims,a)
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);temp=output.with_suffix('.nc.part')
    ds.to_netcdf(temp,engine='h5netcdf');temp.replace(output)
    add_surface_class(output,clouds)
    with xr.open_dataset(output,engine='h5netcdf') as prepared:provenance=json.loads(prepared.attrs['provenance'])
    provenance['prepare_seconds']=round(time.perf_counter()-start,3)
    output.with_suffix('.json').write_text(json.dumps(provenance,indent=2))
    return provenance


class Atmosphere:
    def __init__(self,path,scene):
        with xr.open_dataset(path,engine='h5netcdf') as ds:
            self.provenance=json.loads(ds.attrs['provenance'])
            if self.provenance['inputs']!=[scene.oci.identity,scene.harp.identity]:raise ValueError('Atmosphere cache belongs to different L1C inputs')
            kind=self.provenance.get('cache_kind')
            if kind is not None and (self.provenance.get('cache_schema_version')!=1 or kind not in ('rayleigh_boundary','transmission_boundary')):
                raise ValueError('Unsupported atmospheric cache schema/kind')
            for name in ('boundary_pressure','boundary_state'):
                if name not in ds or ds[name].dims!=(ROW,COL) or ds[name].shape!=scene.shape:
                    raise ValueError(f'Atmosphere cache source shape/dimensions mismatch: {name}')
            if kind and ds.boundary_pressure.attrs.get('units')!='hPa':raise ValueError('Boundary pressure must use hPa')
            self.p=ds.boundary_pressure.values;self.state=ds.boundary_state.values
            self.w=ds.water_column.values if 'water_column' in ds else None
            self.surface_class=ds.surface_class.values if 'surface_class' in ds else None
            self.phase=ds.oci_phase.values if 'oci_phase' in ds else None
            for name in ('water_column','surface_class','oci_phase'):
                if name in ds and (ds[name].dims!=(ROW,COL) or ds[name].shape!=scene.shape):
                    raise ValueError(f'Atmosphere cache source shape/dimensions mismatch: {name}')
            if not np.isin(self.state,[0,1,2,3,4]).all():raise ValueError('Unsupported boundary state')
            if self.surface_class is not None and not np.isin(self.surface_class,[-1,0,1]).all():raise ValueError('Unsupported surface classification')
            if kind=='rayleigh_boundary' and (self.w is not None or any(n in ds for n in TRANSMISSION_VARIABLES)):
                raise ValueError('Rayleigh-only cache must not contain transmission/humidity arrays')
            if kind=='rayleigh_boundary' and self.surface_class is None:raise ValueError('Rayleigh-only cache needs surface_class')
            present=[name in ds for name in TRANSMISSION_VARIABLES]
            if any(present) and (not all(present) or self.w is None):raise ValueError('Incomplete transmission cache')
            self.lut=None
            if all(present):
                self.lut=TransmissionLUT.__new__(TransmissionLUT)
                self.lut.d={name:ds[name].values for name in TRANSMISSION_VARIABLES};self.lut.validate()
            if kind=='transmission_boundary' and self.lut is None:raise ValueError('Incomplete transmission cache')
        self.provenance['cache_sha256']=sha256(path)
        self.cache={}

    @property
    def capabilities(self):
        return {'rayleigh':self.surface_class is not None,'transmission':self.surface_class is not None and self.lut is not None}

    def transmission(self,product,channel,extrapolate=False):
        if not self.capabilities['transmission']:raise ValueError('Transmission unavailable: loaded cache supports Rayleigh only')
        key=(product.instrument,channel['view'],channel['band'],extrapolate)
        if key not in self.cache:
            wave=channel['wavelength']
            if 400<=wave<=700:band=0
            elif product.instrument=='OCI':
                targets={865:1,940:2,1615:5,2130:6,2260:7};target=min(targets,key=lambda t:abs(t-wave))
                if abs(target-wave)>12:raise ValueError(f'No verified transmission mapping for {wave:.1f} nm')
                band=targets[target]
            else:raise ValueError('HARP2 transmission correction currently supports visible RGB only')
            result=self.lut.evaluate(product.read('solar_zenith_angle',channel),product.read('sensor_zenith_angle',channel),self.p,self.w,band,extend_surface=np.isin(self.state,[2,4]) if extrapolate else None)
            count=product.read('number_of_observations',channel)
            if len(self.cache)>=24:self.cache.pop(next(iter(self.cache)))
            self.cache[key]=np.where(count>0,result,np.nan)
        return self.cache[key]

    def corrected_values(self,product,channel,recipe):
        if self.surface_class is None:
            raise ValueError('Correction cache lacks a land mask; prepare a new cache or add the native OCI LAND classification')
        raw=product.values(channel)
        ray=recipe.correction in ('rayleigh','rayleigh_transmission') or recipe.polar_rayleigh
        if ray:
            from .rayleigh import subtract
            molecular=subtract(product,channel,self.p,raw=raw)
        total=molecular['total'] if recipe.correction in ('rayleigh','rayleigh_transmission') else raw['total']
        if recipe.correction in ('transmission','rayleigh_transmission'):
            total=total/self.transmission(product,channel,recipe.extrapolate_surface)
        # Land uses the same molecular-only subtraction as the evaluated trial.
        # Legacy transmission remains water-only, including combined mode.
        if recipe.corrects_land_total:
            total=np.where(self.surface_class==1,molecular['total'],total)
        total_bypass=self.surface_class==-1 if recipe.corrects_land_total else self.surface_class!=0
        out={**raw,'_toa_total':raw['total'],'total':np.where(total_bypass,raw['total'],total)}
        if product.instrument=='HARP2' and recipe.polar_rayleigh:
            polar_bypass=self.surface_class==-1 if recipe.corrects_land_polarization else self.surface_class!=0
            for key in ('q','u','q_scattering','u_scattering','signed_q','signed_u','polarized','dolp'):
                out[key]=np.where(polar_bypass,raw[key],molecular[key])
        return out

    def correct(self,scene,recipe,arrays):
        if recipe.correction in ('transmission','rayleigh_transmission') and not self.capabilities['transmission']:
            raise ValueError('Transmission unavailable: loaded cache supports Rayleigh only')
        oc,hc=scene.channels(recipe)
        corrected=[];values_cache={}
        def get(product,channel):
            key=(product.instrument,channel['view'],channel['band'])
            if key not in values_cache:values_cache[key]=self.corrected_values(product,channel,recipe)
            return values_cache[key]
        for product,channels,array in [(scene.oci,oc,arrays[0]),(scene.harp,hc,arrays[1])]:
            values=[]
            for c in channels[:1] if array.ndim==2 else channels:
                if product.instrument=='OCI':
                    source=[c2 for c2 in product.channels if c2['band']==c['band']]
                    rho=np.stack([get(product,v)['total'] for v in source])
                    raw=np.stack([get(product,v)['_toa_total'] for v in source])
                    value=np.where((np.isfinite(raw).sum(axis=0)==1)&(np.isfinite(rho).sum(axis=0)==1),np.nansum(rho,axis=0),np.nan)
                else:value=get(product,c)['total']
                values.append(value)
            corrected.append(values[0] if array.ndim==2 else np.stack(values,axis=-1))
        if recipe.polar_rayleigh:
            hv=[get(scene.harp,c) for c in hc]
            third=hv[0][recipe.third_quantity] if recipe.third_quantity.startswith('signed') else np.stack([v[recipe.third_quantity] for v in hv],axis=-1)
        else:third=arrays[2]
        return [*corrected,third]


def add_surface_class(cache,cloud_paths,output=None):
    """Attach native OCI LAND flags using stored, hash-verified collocation indices."""
    output=Path(output or cache)
    with xr.open_dataset(cache,engine='h5netcdf') as original:ds=original.load()
    provenance=json.loads(ds.attrs['provenance'])
    paths={Path(p).name:Path(p) for p in cloud_paths}
    surface=np.full(ds.boundary_pressure.shape,-1,dtype=np.int8)
    phase=np.full(ds.boundary_pressure.shape,np.nan)
    for i,source in enumerate(provenance['clouds']):
        path=paths.get(source['name'])
        if path is None or sha256(path)!=source['sha256']:raise ValueError('Missing or changed native cloud source for LAND mask')
        with xr.open_dataset(path,group='geophysical_data',engine='h5netcdf') as geo:
            meanings=geo.l2_flags.attrs['flag_meanings'].split()
            mask=int(np.atleast_1d(geo.l2_flags.attrs['flag_masks'])[meanings.index('LAND')])
            flags=geo.l2_flags.values
            take=(ds.cloud_source_product.values==i)&(ds.cloud_source_index.values>=0)
            selected=flags.ravel()[ds.cloud_source_index.values[take]].astype('uint32')
            surface[take]=((selected&mask)!=0).astype(np.int8)
            phase[take]=geo.cld_phase_21.values.ravel()[ds.cloud_source_index.values[take]]
    ds['oci_phase']=((ROW,COL),phase)
    ds.oci_phase.attrs.update(long_name='Native OCI L2 cld_phase_21 transferred to original L1C centers',flag_values=np.arange(5,dtype=np.int8),flag_meanings='no_mask clear liquid ice unknown_cloud_assume_water')
    ds['surface_class']=((ROW,COL),surface)
    ds.surface_class.attrs.update(flag_values=np.array([-1,0,1],dtype=np.int8),flag_meanings='unknown water land')
    provenance['phase_policy']='Native OCI cld_phase_21 (2.1 µm retrieval), same audited nearest-center/time collocation; no neighborhood phase imputation'
    provenance['land_policy']='Native OCI L2 LAND classification at collocated center; actual correction domain is recorded per recipe; mixed coastal footprints unresolved'
    provenance['surface_counts']={'land':int((surface==1).sum()),'water':int((surface==0).sum()),'unknown':int((surface==-1).sum())}
    ds.attrs['provenance']=json.dumps(provenance,sort_keys=True)
    temporary=output.with_suffix('.nc.part');ds.to_netcdf(temporary,engine='h5netcdf');temporary.replace(output)
    return provenance['surface_counts']


def extract_rayleigh(cache,output):
    """Preserve audited boundaries exactly, dropping legacy humidity/transmission."""
    cache,output=Path(cache),Path(output)
    if cache.resolve()==output.resolve() or output.exists():
        raise ValueError('Choose a new output path; existing caches are preserved')
    fields=('boundary_pressure','boundary_state','surface_class','oci_phase','cloud_source_product',
            'cloud_source_index','match_distance_km','match_time_s')
    with xr.open_dataset(cache,engine='h5netcdf') as original:
        if not all(n in original for n in fields[:3]):raise ValueError('Source cache needs pressure, boundary state and surface_class')
        old=json.loads(original.attrs['provenance'])
        ds=original[[n for n in fields if n in original]].load()
    keys=('inputs','clouds','ancillary','source','collocation','fallback','state_codes','phase_policy','land_policy','surface_counts')
    provenance={k:old[k] for k in keys if k in old}
    # Only MET contributes to the pressure boundary; retain all parent evidence by hash.
    if 'ancillary' in provenance:provenance['ancillary']=[a for a in provenance['ancillary'] if '.MET.' in a['name']]
    provenance.update(cache_schema_version=1,cache_kind='rayleigh_boundary',
        method='Audited OCI cloud/MERRA-2 boundaries extracted unchanged for experimental Rayleigh',
        land_policy='Native OCI L2 LAND classification at collocated center; actual correction domain is recorded per recipe; mixed coastal footprints unresolved',
        surface='Spatial/time-interpolated MERRA-2 MET PS; model terrain, not fine-scale terrain adjustment',
        harp2_approximation='same OCI-time collocated boundary pressure; each HARP2 view uses its own actual geometry',
        derived_from={'cache_sha256':sha256(cache),'policy':'exact source boundary/classification arrays; no recalculation or gap filling'})
    ds.attrs={'provenance':json.dumps(provenance,sort_keys=True)}
    ds.boundary_pressure.attrs['units']='hPa'
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_suffix('.nc.part');ds.to_netcdf(temporary,engine='h5netcdf');temporary.replace(output)
    output.with_suffix('.json').write_text(json.dumps(provenance,indent=2))
    return provenance
