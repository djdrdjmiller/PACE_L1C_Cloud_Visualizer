"""Independently generated, explicitly synthetic portable grouped products."""
from pathlib import Path
import numpy as np
import xarray as xr
from .reader import ROW,COL,VIEW,IB,PB


def create_pair(destination, shape=(18,24), dateline=False, high_latitude=False, permuted=False, oci_row_tilt=False):
    destination=Path(destination); destination.mkdir(parents=True,exist_ok=True)
    r,c=np.indices(shape)
    lat=(68 if high_latitude else -28)+r*.047
    lon=(179.5 if dateline else -76)+c*.053
    lon=(lon+180)%360-180
    paths=[]
    for instrument in ("OCI","HARP2"):
        path=destination/(instrument+".nc")
        attrs={"instrument":instrument,"processing_level":"L1C","product_name":f"SYNTHETIC_{instrument}",
               "sun_earth_distance":1.01,"l1cgrid_source":"SYNTHETIC_GRID","processing_version":"synthetic-1",
               "time_coverage_start":"2025-10-02T18:26:35Z","time_coverage_end":"2025-10-02T18:31:35Z","nadir_bin":shape[1]//2}
        xr.Dataset(attrs=attrs).to_netcdf(path,engine="h5netcdf")
        if instrument=="OCI":
            nview=1 if oci_row_tilt else 2
            angles=np.array([0.]) if oci_row_tilt else np.array([-20,20]); waves=np.array([443.,555.,645.,865.])
            wavelengths=np.broadcast_to(waves,(nview,4))
        else:
            waves=np.array([440.,550.,670.,865.])
            wavelengths=np.repeat(waves,5).reshape(20,1)
            angles=np.tile(np.linspace(-50,50,5),4); nview=20
            if permuted:
                order=np.random.default_rng(42).permutation(nview)
                wavelengths=wavelengths[order]; angles=angles[order]
        sensor=xr.Dataset({"intensity_wavelength":((VIEW,IB),wavelengths,{"units":"nm"}),
                           "intensity_f0":((VIEW,IB),np.full(wavelengths.shape,1800.)),
                           "sensor_view_angle":((VIEW,),angles)})
        if instrument=="OCI" and oci_row_tilt:
            sensor["sensor_view_angle"]=((ROW,),np.linspace(-20,20,shape[0]),{"long_name":"Tilt angle along track","units":"degrees"})
        if instrument=="HARP2":
            sensor["polarization_f0"]=((VIEW,PB),np.full((nview,1),1700.))
        sensor.to_netcdf(path,group="sensor_views_bands",mode="a",engine="h5netcdf")
        sza=np.full((*shape,nview),30.)
        scattering=np.broadcast_to(160-np.abs(angles)*.65,(*shape,nview)).copy()
        geo=xr.Dataset({"latitude":((ROW,COL),lat),"longitude":((ROW,COL),lon),
                        "solar_zenith_angle":((ROW,COL,VIEW),sza),"sensor_zenith_angle":((ROW,COL,VIEW),np.broadcast_to(np.abs(angles),sza.shape)),
                        "scattering_angle":((ROW,COL,VIEW),scattering),"rotation_angle":((ROW,COL,VIEW),np.full(sza.shape,30.))})
        geo.to_netcdf(path,group="geolocation_data",mode="a",engine="h5netcdf")
        count=np.ones((*shape,nview))
        base=100+150*np.exp(-((r-shape[0]/2)**2+(c-shape[1]/2)**2)/30)
        i=np.broadcast_to(base[...,None,None],(*shape,nview,wavelengths.shape[1])).copy()
        if instrument=="OCI":
            if not oci_row_tilt:
                count[:shape[0]//2,:,1]=0; count[shape[0]//2:,:,0]=0
            else:count[0,0,0]=0
            i[count==0]=np.nan
        else:
            count[:,0,:]=0; i[:,0]=np.nan
        obs=xr.Dataset({"i":((ROW,COL,VIEW,IB),i,{"units":"W m^-2 sr^-1 um^-1"}),
                        "number_of_observations":((ROW,COL,VIEW),count)})
        if instrument=="HARP2":
            q=i*.03; u=i*.04
            obs["q"]=((ROW,COL,VIEW,PB),q); obs["u"]=((ROW,COL,VIEW,PB),u)
        if permuted:
            obs=obs.transpose(...,COL,ROW)
        obs.to_netcdf(path,group="observation_data",mode="a",engine="h5netcdf",
                      encoding={"i":{"dtype":"int16","scale_factor":.02,"_FillValue":-32768,"zlib":True}})
        paths.append(str(path))
    return paths
