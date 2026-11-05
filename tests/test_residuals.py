import numpy as np
from pace_l1c.residuals import compare
from pace_l1c.cloudbow import forward


def test_named_residuals_share_branch1_views_sign_and_support():
    theta=np.linspace(134,166,321)
    phase=np.sin(theta/5)
    cba=[.01,.02,.3]
    samples=[]
    for branch in [0,1]:
        for view,t in enumerate([133,140,150,160,167]):
            samples.append({'branch':branch,'view':branch*10+view,'wavelength':665.,'scattering_angle':t,'q_scattering':.1+branch})
    observations={'hyperangular_wavelength':665.,'samples':samples}
    cloud={'status':'experimental','theta':theta,'phase':phase,'coefficients_cba':cba}
    rft={'branches':[{'status':'experimental','branch':0,'theta':theta,'phase_mixture':phase*.8,'coefficients_cba':cba}]}
    residuals=compare(observations,cloud,rft,(136,165))
    assert residuals['branch']==0
    assert residuals['source_views']==[1,2,3]
    assert residuals['theta']==[140,150,160]
    for name,factor in [('cloudbow',1),('rft',.8)]:
        _,prediction=forward(np.array([140,150,160]),np.interp([140,150,160],theta,phase*factor),cba)
        np.testing.assert_allclose(residuals['series'][name]['predicted_signed_q'],prediction)
        np.testing.assert_allclose(residuals['series'][name]['residual_signed_q'],prediction+.1)
    # Sanity-check branch 2 values cannot alter either residual series.
    for sample in samples:
        if sample['branch']==1:sample['q_scattering']=999
    assert compare(observations,cloud,rft,(136,165))==residuals


def test_available_model_residual_survives_missing_other_model():
    obs={'hyperangular_wavelength':665.,'samples':[{'branch':0,'view':5,'wavelength':665.,'scattering_angle':145.,'q_scattering':.1}]}
    cloud={'status':'experimental','theta':[140,150],'phase':[.2,.3],'coefficients_cba':[.01,.02,.3]}
    missing={'status':'missing','reason':'RFT quality failed'}
    result=compare(obs,cloud,missing,(136,165))
    assert result['series']['cloudbow']['status']=='available'
    assert result['series']['rft']['reason']=='RFT quality failed'
    assert result['sample_count']==1
