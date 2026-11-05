"""Compare current molecular physics with the retired ideal model on local data.

No fitting or downloads. Run from the repository root; files remain read-only.
The old formula below is an audit baseline, never used by the dashboard.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from pace_l1c.scene import Scene, Recipe
from pace_l1c import rayleigh


def ideal_path(wave, pressure, sza, vza, angle):
    lam=wave/1000
    tau=.008569*lam**-4*(1+.0113*lam**-2+.00013*lam**-4)*pressure/1013.25
    tau=np.where(np.isfinite(pressure)&(pressure>0)&(pressure<=1050),tau,np.nan)
    mu0=np.cos(np.deg2rad(sza));mu=np.cos(np.deg2rad(vza))
    with np.errstate(invalid='ignore',divide='ignore',over='ignore'):
        factor=-np.expm1(-tau*(1/mu0+1/mu))/(4*(mu0+mu))
    valid=(sza>=0)&(sza<90)&(vza>=0)&(vza<90)&(angle>=0)&(angle<=180)
    return (np.where(valid,factor*.75*(1+np.cos(np.deg2rad(angle))**2),np.nan),
            np.where(valid,-factor*.75*np.sin(np.deg2rad(angle))**2,np.nan))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('oci','harp2','gpc','mie','atmosphere','output'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--bin',type=int,nargs=2,default=[351,307],metavar=('ROW','COL'))
    args=parser.parse_args()
    scene=Scene(args.oci,args.harp2,gpc_path=args.gpc,mie_path=args.mie,atmosphere_path=args.atmosphere)
    try:
        selected=scene.diagnostics(args.bin,rft=True)
        before=json.dumps({k:selected[k] for k in ('oci','harp2','cloudbow','cloud')},sort_keys=True)
        branch=selected['rft']['thick_branches'][0]
        samples={s['view']:s for s in selected['harp2']['samples']}
        points=[samples[v] for v in branch['source_views']]
        geometry=[np.array([p[key] for p in points]) for key in ('solar_zenith_angle','sensor_zenith_angle','scattering_angle')]
        wave=selected['harp2']['hyperangular_wavelength'];pressure=scene.atmosphere.p[tuple(args.bin)]
        old_q=ideal_path(wave,pressure,*geometry)[1]
        views=branch['source_views'];ratio=scene.harp.read('intensity_f0')[views]/scene.harp.read('polarization_f0')[views]
        old_ray=-old_q*ratio;new_ray=np.array(branch['predicted_rayleigh_signed_q'])
        cloud=np.array(branch['predicted_cloud_only_signed_q']);observed=np.array(branch['observed_signed_q'])
        np.testing.assert_allclose(cloud+new_ray,branch['predicted_signed_q'])
        np.testing.assert_allclose(np.sum(branch['signed_full_contributions'],axis=0)+branch['signed_rayleigh'],branch['signed_q'])
        angle=geometry[2];order=np.argsort(angle)
        curves={str(t):{'old':float(np.interp(t,angle[order],old_ray[order])),
                        'new':float(np.interp(t,angle[order],new_ray[order]))} for t in (140,150,160)}
        maps=[]
        for product,channels in zip((scene.oci,scene.harp),scene.channels(Recipe())):
            for channel in channels:
                geom=[product.read(key,channel) for key in ('solar_zenith_angle','sensor_zenith_angle','scattering_angle')]
                oi,oq=ideal_path(channel['wavelength'],scene.atmosphere.p,*geom)
                ni,nq,_=rayleigh.path_reflectance(channel['wavelength'],scene.atmosphere.p,*geom)
                np.testing.assert_array_equal(np.isfinite(oi),np.isfinite(ni))
                np.testing.assert_array_equal(np.isfinite(oq),np.isfinite(nq))
                good=np.isfinite(ni)&(oi>0)
                maps.append({'instrument':product.instrument,'wavelength_nm':channel['wavelength'],
                    'finite_bins':int(good.sum()),'median_molecular_I_ratio':float(np.median(ni[good]/oi[good])),
                    'max_abs_molecular_I_change':float(np.max(np.abs(ni[good]-oi[good])))})
        after=scene.diagnostics(args.bin,rft=True)
        assert before==json.dumps({k:after[k] for k in ('oci','harp2','cloudbow','cloud')},sort_keys=True)
        report={'bin':args.bin,'pressure_hpa':float(pressure),'wavelength_nm':wave,
            'molecular_depolarization':float(rayleigh.depolarization_ratio(wave)),
            'new_tau':float(rayleigh.optical_depth(wave,pressure)),
            'molecular_minus_q':curves,'median_rayleigh_ratio':float(np.median(new_ray/old_ray)),
            'branch1_rmse':{'old':float(np.sqrt(np.mean((cloud+old_ray-observed)**2))),
                            'new':float(np.sqrt(np.mean((cloud+new_ray-observed)**2)))},
            'maps':maps,'source_diagnostics_unchanged':True,'component_sum_verified':True,
            'model':rayleigh.MODEL,'scene_provenance':scene.provenance(Recipe(selected=args.bin))}
        Path(args.output).write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({k:v for k,v in report.items() if k not in ('model','scene_provenance')},indent=2))
    finally:
        scene.close()


if __name__=='__main__':main()
