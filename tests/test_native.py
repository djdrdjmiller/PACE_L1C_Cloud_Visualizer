import numpy as np
import h5py
import pytest
from pace_l1c.fixtures import create_pair
from pace_l1c.reader import Product
from pace_l1c.native import reconstruct


def test_known_equatorial_socea_geometry_and_corruption(tmp_path):
    paths=create_pair(tmp_path,shape=(12,25))
    # Equatorial great-circle orbit; analytic transverse equal-area coordinates.
    radius=6378.137
    row=np.arange(12)*5.2/radius
    cross=(np.arange(25)-12)*5.2/radius
    center=np.stack((np.cos(row),np.zeros(12),np.sin(row)),axis=-1)
    across=np.array([0.,1.,0.])
    v=center[:,None,:]*np.sqrt(1-cross[None,:,None]**2)+across*cross[None,:,None]
    factor=((1-1/298.257)**2*6371+radius-6371)/radius
    lon=np.rad2deg(np.arctan2(v[...,1],v[...,0]))
    lat=np.rad2deg(np.arctan2(v[...,2],factor*np.hypot(v[...,0],v[...,1])))
    with h5py.File(paths[0],'a') as f:
        f['geolocation_data/latitude'][:]=lat;f['geolocation_data/longitude'][:]=lon
    p=Product(paths[0])
    try:
        edges_lat,edges_lon,evidence=reconstruct(p)
        assert evidence['official_transform_verified']
        assert evidence['max_center_error_m']<1
        assert edges_lat.shape==(13,26)
    finally:p.close()
    with h5py.File(paths[0],'a') as f:
        f['geolocation_data/latitude'][3,5]+=.01
    p=Product(paths[0])
    try:
        with pytest.raises(ValueError,match='reconstruction failed'):
            reconstruct(p)
    finally:p.close()
