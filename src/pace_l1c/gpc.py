"""Registered native-bin GPC scalar fields, independent of phase-function access."""
import numpy as np
import xarray as xr
from .reader import ROW, COL, sha256, jsonable


class RegisteredGPC:
    def __init__(self, gpc_path, harp):
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
            self.provenance={'gpc':{'product_name':root.attrs.get('product_name'),'sha256':sha256(gpc_path),'processing_version':root.attrs.get('processing_version')},'alignment_max_error_m':float(distance.max())}
        except Exception:
            self.close()
            raise

    def close(self):
        for ds in self.groups: ds.close()

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

