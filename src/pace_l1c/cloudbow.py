"""Optional stored-coefficient visualization; never fit new microphysics.

Reference interpolation is log-radius/log-variance from the supplied unweighted
script. This is explicitly experimental until the operational LUT identity,
spectral response, normalization and branch are independently established.
"""
from pathlib import Path
import numpy as np
import xarray as xr
from .reader import ROW,COL,sha256,jsonable


def bracket(coordinates,value):
    a=np.asarray(coordinates,dtype=np.float64)
    if not np.isfinite(value) or value<a[0] or value>a[-1] or not np.all(np.diff(a)>0):
        raise ValueError("Microphysics outside strictly increasing LUT coordinates")
    i=int(np.clip(np.searchsorted(a,value,side='right')-1,0,len(a)-2))
    return i,(value-a[i])/(a[i+1]-a[i])


def interpolate(table,radii,variances,radius,variance):
    if radius<=0 or variance<=0:
        raise ValueError("Invalid cloudbow microphysics")
    ri,rw=bracket(np.log(np.asarray(radii,dtype=np.float64)),np.log(float(radius)))
    vi,vw=bracket(np.log(np.asarray(variances,dtype=np.float64)),np.log(float(variance)))
    corners=np.asarray(table[:,vi:vi+2,ri:ri+2],dtype=np.float64)
    if not np.isfinite(corners).all():
        raise ValueError("Missing LUT interpolation corner")
    return (1-vw)*((1-rw)*corners[:,0,0]+rw*corners[:,0,1])+vw*((1-rw)*corners[:,1,0]+rw*corners[:,1,1])


def forward(theta,phase,coefficients):
    theta=np.asarray(theta,dtype=np.float64)
    phase=np.asarray(phase,dtype=np.float64)
    c,b,a=np.asarray(coefficients,dtype=np.float64)
    canonical=a*phase+b*(np.cos(np.deg2rad(theta))**2-1)+c
    return canonical,-canonical


class Cloudbow:
    def __init__(self,gpc_path,lut_path,harp):
        self.groups=[]
        try:
            root=xr.open_dataset(gpc_path,engine='h5netcdf');self.groups.append(root)
            geo=xr.open_dataset(gpc_path,group='geolocation_data',engine='h5netcdf');self.groups.append(geo)
            self.data=xr.open_dataset(gpc_path,group='geophysical_data',engine='h5netcdf');self.groups.append(self.data)
            for name in ('time_coverage_start','time_coverage_end','l1cgrid_source','nadir_bin'):
                if root.attrs.get(name)!=harp.attrs.get(name):
                    raise ValueError(f"GPC/L1C registration mismatch: {name}")
            lat=geo.latitude.transpose(ROW,COL).values;lon=geo.longitude.transpose(ROW,COL).values
            if lat.shape!=harp.shape:
                raise ValueError("GPC has different original-bin grid")
            valid=np.isfinite(lat)&np.isfinite(lon)&np.isfinite(harp.lat)&np.isfinite(harp.lon)
            distance=np.hypot((lat-harp.lat)[valid],(((lon-harp.lon+180)%360-180)*np.cos(np.deg2rad(lat)))[valid])*111195
            if not valid.any() or distance.max()>20:
                raise ValueError("GPC geolocation differs from L1C")
            coef=self.data['cloud_bow_auxiliary_fit']
            if 'C, B, A' not in coef.attrs.get('long_name',''):
                raise ValueError("GPC coefficient order not established by metadata")
            self.lower=float(root.attrs['cloud_bow_scatt_angle_to_use_lo'])
            self.upper=float(root.attrs['cloud_bow_scatt_angle_to_use_hi'])
            self.rft_lower=float(root.attrs.get('cloud_rft_scatt_angle_to_use_lo', self.lower))
            self.rft_upper=float(root.attrs.get('cloud_rft_scatt_angle_to_use_hi', self.upper))
            self.rft_required=[float(root.attrs.get('cloud_rft_scatt_angle_required_min', self.rft_lower)),
                               float(root.attrs.get('cloud_rft_scatt_angle_required_max', self.rft_upper))]
            with open(lut_path,'rb') as f:
                magic=f.read(8)
            lut=xr.open_dataset(lut_path,engine='h5netcdf' if magic.startswith(b'\x89HDF') else 'scipy');self.groups.append(lut)
            wave=lut.wavelength
            unit=str(wave.attrs.get('units','')).strip()
            if unit not in ('µm','um','nm'):
                raise ValueError("Unknown LUT wavelength units")
            wavelengths=wave.values*(1000 if unit!='nm' else 1)
            target=max({c['wavelength'] for c in harp.channels},key=lambda w:(sum(c['wavelength']==w for c in harp.channels),-abs(w-665)))
            self.wave=float(wavelengths[np.argmin(abs(wavelengths-target))])
            self.theta=lut.scattering_angle.values
            if not np.isfinite(self.theta).all() or not np.all(np.diff(self.theta)>0):
                raise ValueError('LUT scattering-angle coordinates must be finite and strictly increasing')
            self.radii=lut.reff.values;self.variances=lut.veff.values
            self.table=lut.p21.isel({wave.dims[0]:int(np.argmin(abs(wavelengths-target)))}).transpose(lut.scattering_angle.dims[0],lut.veff.dims[0],lut.reff.dims[0]).values
            self.optics={name:lut[name].isel({wave.dims[0]:int(np.argmin(abs(wavelengths-target)))}).transpose(lut.veff.dims[0],lut.reff.dims[0]).values
                         for name in ('csca','cext','qsca','qext') if name in lut}
            lut_hash=sha256(lut_path)
            audited_dimensionless=lut_hash=='d4577f972d3de0023782e6444d8ab358a1bccaac20dd6a01d5d1ea23532548e6'
            self.provenance={'gpc':{'product_name':root.attrs.get('product_name'), 'sha256':sha256(gpc_path),'processing_version':root.attrs.get('processing_version')},
                'lut':{'name':Path(lut_path).name,'sha256':lut_hash,'wavelength_nm':self.wave,'units':lut.p21.attrs.get('units'),
                    'phase_normalization_units':'dimensionless' if audited_dimensionless else lut.p21.attrs.get('units'),
                    'phase_normalization_evidence':'Hash-specific independent Mie audit: red-band P21 agrees within 0.3%, backscatter P11 within 0.1%, Csca within 0.02%; sr^-1 label inconsistent; see examples/check_mie_normalization.py and docs/RFT.md' if audited_dimensionless else 'Declared LUT units; no independent audit for this table',
                    'phase_normalization_limit':'Independent check at one red-band size-distribution point; full P11 integral unavailable in source LUT'},
                'alignment_max_error_m':float(distance.max()),'coefficient_order':['C','B','A'],
                'interpolation':'bilinear in log radius/log variance; native LUT angle sampling',
                'model':'A*P21 + B*(cos(theta)^2-1) + C; display negative of entire model',
                'status':'experimental stored-coefficient reconstruction',
                'limitations':['Operational cloudbow LUT identity/spectral response not established for supplied LUT',
                              'GPC ATBD Eq. 4 writes B*cos(theta)^2+C; supplied fitting script uses B*(cos(theta)^2-1)+C. Stored offset basis remains unresolved; supplied-script basis retained',
                              'Operational irradiance/distance normalization and selected angular branch not independently verified',
                              'Current public GPC differs from the notebook development L2CLD product']}
        except Exception:
            self.close();raise

    def close(self):
        for ds in self.groups:ds.close()

    def diagnostics(self,row,col):
        """Reported scalar retrievals; retain failures, fill values and metadata."""
        fields={}
        for name,var in self.data.data_vars.items():
            if set(var.dims)!={ROW,COL}:
                continue
            value=float(var.isel({ROW:row,COL:col}).values)
            item={'value':jsonable(value),'units':var.attrs.get('units',''),
                  'description':var.attrs.get('long_name',name),
                  'status':'reported' if np.isfinite(value) else 'missing'}
            bits={int(k.split('_')[1]):str(v) for k,v in var.attrs.items() if k.startswith('bit_') and k.split('_')[1].isdigit()}
            if bits:
                item['flag_definitions']={str(bit):text for bit,text in bits.items()}
                item['flags']=[text for bit,text in sorted(bits.items()) if np.isfinite(value) and int(value)&(1<<bit)]
                item['status']='missing' if not np.isfinite(value) else ('flagged' if value else 'OK')
            fields[name]=item
        return jsonable({'status':'available','source':self.provenance['gpc'],'registration_max_error_m':self.provenance['alignment_max_error_m'],
                'fields':fields,'policy':'Native registered GPC bin; reported values retained even when flagged; no fill or neighbor substitution'})

    def solution(self,row,col):
        index={ROW:row,COL:col}
        qa=float(self.data.cloud_bow_quality_retrieval_fail.isel(index).values)
        if not np.isfinite(qa) or qa!=0:
            return {'status':'missing','reason':'Cloudbow retrieval is missing or quality flags indicate failure','quality':jsonable(qa),'provenance':self.provenance}
        radius=float(self.data.cloud_bow_droplet_effective_radius.isel(index).values)
        variance=float(self.data.cloud_bow_droplet_effective_variance.isel(index).values)
        coef=self.data.cloud_bow_auxiliary_fit.isel(index).values.ravel()
        if len(coef)!=3 or not np.isfinite(coef).all():
            return {'status':'missing','reason':'Missing or unsupported auxiliary fit coefficients'}
        try:
            phase=interpolate(self.table,self.radii,self.variances,radius,variance)
        except ValueError as e:
            return {'status':'missing','reason':str(e),'provenance':self.provenance}
        use=(self.theta>=self.lower)&(self.theta<=self.upper)
        canonical,display=forward(self.theta[use],phase[use],coef)
        return jsonable({'status':'experimental','theta':self.theta[use],'canonical':canonical,'signed_q':display,
                         'phase':phase[use],'radius_um':radius,'variance':variance,'coefficients_cba':coef,
                         'quality':qa,'provenance':self.provenance})
