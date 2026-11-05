import numpy as np
import xarray as xr
from pace_l1c.cloudbow import interpolate,forward,Cloudbow
from pace_l1c.fixtures import create_pair
from pace_l1c.reader import Product,ROW,COL


def test_log_interpolation_and_whole_model_sign():
    radii=np.array([3.,12.]);variances=np.array([.01,.16])
    table=np.log(radii)[None,None,:]+2*np.log(variances)[None,:,None]+np.array([0.,1.])[:,None,None]
    result=interpolate(table,radii,variances,6.,.04)
    np.testing.assert_allclose(result,np.log(6)+2*np.log(.04)+np.array([0,1]))
    canonical,display=forward(np.array([0.,90.]),np.array([2.,-2.]),[1.,2.,3.])
    np.testing.assert_allclose(canonical,[7.,-7.]);np.testing.assert_allclose(display,[-7.,7.])


def test_registered_gpc_quality_coefficients_and_dense_lut(tmp_path):
    paths=create_pair(tmp_path/'pair')
    h=Product(paths[1]);gpc=tmp_path/'gpc.nc';lut=tmp_path/'mie.nc'
    try:
        xr.Dataset(attrs=dict(h.attrs,product_name='SYNTHETIC_GPC',cloud_bow_scatt_angle_to_use_lo=134.,cloud_bow_scatt_angle_to_use_hi=166.)).to_netcdf(gpc,engine='h5netcdf')
        xr.Dataset({'latitude':((ROW,COL),h.lat),'longitude':((ROW,COL),h.lon)}).to_netcdf(gpc,group='geolocation_data',mode='a',engine='h5netcdf')
        shape=h.shape
        qa=np.zeros(shape);qa[0,0]=256
        data=xr.Dataset({'cloud_bow_quality_retrieval_fail':((ROW,COL),qa),
            'cloud_bow_droplet_effective_radius':((ROW,COL),np.full(shape,6.)),
            'cloud_bow_droplet_effective_variance':((ROW,COL),np.full(shape,.04)),
            'cloud_bow_auxiliary_fit':((ROW,COL,'coeff'),np.broadcast_to([1.,2.,3.],(*shape,3)),{'long_name':'Fit parameters C, B, A'})})
        data.to_netcdf(gpc,group='geophysical_data',mode='a',engine='h5netcdf')
        theta=np.linspace(130,170,201)
        xr.Dataset({'scattering_angle':(('theta',),theta),'reff':(('radius',),[3.,12.]),'veff':(('variance',),[.01,.16]),
            'wavelength':(('wave',),[.6646],{'units':'um'}),
            'p21':(('theta','variance','radius','wave'),np.broadcast_to(np.cos(np.deg2rad(theta))[:,None,None,None],(201,2,2,1)),{'units':'steradian^-1'})}).to_netcdf(lut,engine='h5netcdf')
        b=Cloudbow(gpc,lut,h)
        try:
            assert b.solution(0,0)['status']=='missing'
            result=b.solution(5,6)
            assert result['status']=='experimental'
            assert len(result['theta'])==161
            assert result['coefficients_cba']==[1.,2.,3.]
            np.testing.assert_allclose(np.asarray(result['signed_q']),-np.asarray(result['canonical']))
        finally:b.close()
    finally:h.close()


def test_float32_lut_endpoints_are_supported_without_log_rounding_rejection():
    radii=np.array([3.,12.],dtype=np.float32)
    variances=np.array([.001504,.497512],dtype=np.float32)
    table=np.arange(8,dtype=np.float32).reshape(2,2,2)
    np.testing.assert_array_equal(interpolate(table,radii,variances,float(radii[0]),float(variances[0])),table[:,0,0])
    np.testing.assert_array_equal(interpolate(table,radii,variances,float(radii[-1]),float(variances[-1])),table[:,-1,-1])
