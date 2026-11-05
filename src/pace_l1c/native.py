"""Reconstruct the product's row-dependent SOCEA transverse transform.

NASA OCSSW src/l1cgen/hawkeye_methods.cpp, orb_to_latlon defines
sin(transverse angle) = column_offset * 5.2 km / row radius and converts
geocentric vectors to latitude using a radius-dependent flattening factor.
We recover row bases from source nadir and endpoint geolocation, then validate
every other original bin independently. No orbit/terrain data are invented.
"""
import numpy as np

RE, REM, FE, STEP = 6378.137, 6371., 1/298.257, 5.2


def unit(a):
    return a / np.linalg.norm(a,axis=-1,keepdims=True)


def vectors(lat,lon,factor):
    phi=np.arctan2(np.sin(np.deg2rad(lat))*factor,np.cos(np.deg2rad(lat)))
    lam=np.deg2rad(lon)
    return np.stack((np.cos(phi)*np.cos(lam),np.cos(phi)*np.sin(lam),np.sin(phi)),axis=-1)


def latitude(v,factor):
    return np.rad2deg(np.arctan2(v[...,2],factor*np.hypot(v[...,0],v[...,1])))


def reconstruct(product):
    lat,lon=product.lat,product.lon
    nrow,ncol=lat.shape
    mid=int(product.attrs.get('nadir_bin',-1))
    if mid != (ncol-1)//2 or nrow<2 or ncol<3 or not np.isfinite(lat).all() or not np.isfinite(lon).all():
        raise ValueError("SOCEA reconstruction needs complete symmetric source geolocation")
    radius=np.full(nrow,REM)
    for _ in range(8):
        factor=((1-FE)**2*REM+radius-REM)/radius
        center=vectors(lat[:,mid],lon[:,mid],factor)
        radius=RE*(1-FE)/np.sqrt(1-(2-FE)*FE*(1-center[:,2]**2))
    factor=((1-FE)**2*REM+radius-REM)/radius
    center=vectors(lat[:,mid],lon[:,mid],factor)
    endpoint=vectors(lat[:,-1],lon[:,-1],factor)
    across=unit(endpoint-center*np.sum(endpoint*center,axis=-1)[:,None])
    cross=(np.arange(ncol)-mid)*STEP
    fraction=cross[None,:]/radius[:,None]
    predicted=center[:,None,:]*np.sqrt(1-fraction[...,None]**2)+across[:,None,:]*fraction[...,None]
    plat=latitude(predicted,factor[:,None]);plon=np.rad2deg(np.arctan2(predicted[...,1],predicted[...,0]))
    dlon=(plon-lon+180)%360-180
    errors=np.hypot(plat-lat,dlon*np.cos(np.deg2rad(lat)))*111195
    # Row separation is validated independently in geocentric space.
    row_step=np.arctan2(np.linalg.norm(np.cross(center[:-1],center[1:]),axis=-1),np.sum(center[:-1]*center[1:],axis=-1))*(radius[:-1]+radius[1:])/2
    if errors.max()>20 or np.max(np.abs(row_step-STEP))*1000>100:
        raise ValueError(f"Source SOCEA reconstruction failed: max {errors.max():.1f} m; row-spacing deviation {np.max(np.abs(row_step-STEP))*1000:.1f} m")
    # Half-row bases and half-column edges; extrapolation only at granule edges.
    def half(a):
        p=np.concatenate((2*a[:1]-a[1:2],a,2*a[-1:]-a[-2:-1]),axis=0)
        return (p[:-1]+p[1:])/2
    hc,ha=unit(half(center)),unit(half(across))
    ha=unit(ha-hc*np.sum(ha*hc,axis=-1)[:,None])
    hr=half(radius)
    hf=((1-FE)**2*REM+hr-REM)/hr
    edge_fraction=(np.arange(ncol+1)-mid-.5)[None,:]*STEP/hr[:,None]
    edge=hc[:,None,:]*np.sqrt(1-edge_fraction[...,None]**2)+ha[:,None,:]*edge_fraction[...,None]
    edge_lat=latitude(edge,hf[:,None]);edge_lon=np.rad2deg(np.arctan2(edge[...,1],edge[...,0]))
    evidence={"label":"native SOCEA source grid; row bases recovered from file geolocation",
              "official_transform_verified":True,"verification":"NASA transverse sin-angle/radius-dependent geocentric latitude equations; every original center checked",
              "max_center_error_m":float(errors.max()),"rms_center_error_m":float(np.sqrt(np.mean(errors**2))),
              "max_row_spacing_deviation_m":float(np.max(np.abs(row_step-STEP))*1000),
              "validation_tolerances_m":{"center":20,"row_spacing":100},"bin_spacing_km":STEP,
              "source":"https://git.smce.nasa.gov/oel/ocssw/-/blob/develop/src/l1cgen/hawkeye_methods.cpp",
              "limitations":"row bases inferred from published grid, not an independent HKT orbit regeneration; half-row edges interpolated"}
    return edge_lat,edge_lon,evidence
