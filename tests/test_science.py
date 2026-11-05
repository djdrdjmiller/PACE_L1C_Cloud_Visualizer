import numpy as np
from pace_l1c.science import reflectance,rotate,dolp,branches


def test_independent_radiometry_and_night_mask():
    np.testing.assert_allclose(reflectance(np.array([2.,-2.]),4.,60.,1.2),[1.44*np.pi,-1.44*np.pi])
    assert np.isnan(reflectance(2.,4.,100.,1.))
    assert np.isnan(reflectance(2.,0.,20.,1.))


def test_rotation_sign_and_invariants():
    q,u=rotate(3.,4.,45.)
    np.testing.assert_allclose([q,u],[4.,-3.],atol=1e-12)
    assert np.hypot(q,u)==5.
    assert dolp(10.,q,u)==.5
    assert np.isnan(dolp(-1.,q,u))
    assert -q == -4.  # Explicit display transform, not canonical mutation.


def test_branches_preserve_shuffled_view_identity():
    np.testing.assert_array_equal(branches([130,160,140,150],[-30,0,30,-15]),[1,0,0,1])


def test_single_oci_view_with_along_track_tilt_preserves_geometry_and_sampling(tmp_path):
    from pace_l1c.fixtures import create_pair
    from pace_l1c.scene import Scene,Recipe
    from pace_l1c.reader import VIEW
    import pytest
    pair=create_pair(tmp_path/'row-tilt',oci_row_tilt=True,permuted=True)
    scene=Scene(*pair)
    try:
        assert scene.oci.obs.sizes[VIEW]==1
        assert all(c['angle'] is None for c in scene.oci.channels)
        channel=scene.oci.channels[2]
        i=scene.oci.read('i',channel)
        counts=scene.oci.read('number_of_observations',channel)
        expected=np.where(counts>0,np.pi*1.01**2*i/(1800*np.cos(np.deg2rad(30))),np.nan)
        np.testing.assert_allclose(scene.oci.oci_band(channel['band']),expected,equal_nan=True)
        diag=scene.diagnostics([5,6])['oci']
        assert diag['valid_source_views']==[0]
        assert diag['sensor_view_angle_deg']==pytest.approx(np.linspace(-20,20,18)[5])
        assert len(diag['total'])==4
        assert np.isnan(scene.layers(Recipe())[0][0,0]).all()
        assert scene.evidence['compared_bins']==18*24
    finally:scene.close()
