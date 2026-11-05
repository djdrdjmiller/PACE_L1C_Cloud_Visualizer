import numpy as np
import pytest
from pace_l1c.land_trial import apply_land_trial,field_summary
from pace_l1c.rayleigh import subtract


def test_land_trial_changes_only_land_and_keeps_component_polarization_and_missing():
    # A pure scattering-plane molecular signal plus an orthogonal surface signal:
    # subtracting scalar magnitudes would give a different result from 0.03.
    class Product:
        instrument='HARP2'
        def read(self,name,*args):
            return {'solar_zenith_angle':30.,'sensor_zenith_angle':20.,'scattering_angle':90.,
                    'rotation_angle':0.,'intensity_f0':1000.,'polarization_f0':1000.}[name]
        def values(self,*args):
            return {'total':np.full((2,3),.4),'q':np.zeros((2,3)),'u':np.full((2,3),.03)}
    raw=Product().values()
    current={**raw,'polarized':np.hypot(raw['q'],raw['u'])}
    p=np.full((2,3),900.);p[1,1]=np.nan
    molecular=subtract(Product(),{'wavelength':440.},p)
    for key in molecular:
        if key not in current:current[key]=np.full((2,3),.03)
    surface=np.array([[0,1,-1],[0,1,-1]])
    trial=apply_land_trial(current,molecular,surface)
    for field in trial:
        np.testing.assert_array_equal(trial[field][surface!=1],current[field][surface!=1])
    assert trial['total'][0,1]<raw['total'][0,1]
    assert trial['polarized'][0,1]>current['polarized'][0,1]  # not magnitude subtraction
    assert trial['polarized'][0,1]==pytest.approx(np.hypot(trial['q'][0,1],trial['u'][0,1]))
    assert np.isnan(trial['total'][1,1]) and np.isnan(trial['polarized'][1,1])
    np.testing.assert_array_equal(raw['total'],.4)


def test_trial_summary_exposes_unsupported_and_overcorrected_observations():
    stats=field_summary(np.array([.02,.4,.5,np.nan]),np.array([-.01,.3,np.nan,.2]),np.ones(4,bool))
    assert stats['observed_bins']==3 and stats['corrected_bins']==2 and stats['lost_bins']==1
    assert stats['newly_negative']==1 and stats['negative_before']==0
    assert stats['trial_minus_toa']['median']==pytest.approx(-.065)
    assert field_summary([np.nan],[np.nan],[True])['trial'] is None
