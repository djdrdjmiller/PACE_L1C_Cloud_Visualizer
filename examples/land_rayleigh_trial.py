"""Reproducible offline land trial; compares historical water-only with current land-enabled Rayleigh; never changes caches.

Run with explicit paired L1C paths and a Rayleigh boundary cache. Outputs are
PNG/PDF, machine-readable statistics, and the exact recipe/source provenance.
No Mie table or transmission table is used.
"""
import argparse
from dataclasses import asdict,replace
import json
from pathlib import Path
import time
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from pace_l1c.scene import Scene,Recipe
from pace_l1c.rayleigh import subtract,MODEL
from pace_l1c.land_trial import apply_land_trial,field_summary,distribution
from pace_l1c.render import colors
from pace_l1c.reader import jsonable


def evaluate(scene,recipe):
    atmosphere=scene.atmosphere;land=atmosphere.surface_class==1
    oc,hc=scene.channels(recipe)
    channels={};summaries={};arrays={'current':[[],[],[]],'trial':[[],[],[]]}
    for instrument,product,selected in [('OCI',scene.oci,oc),('HARP2',scene.harp,hc)]:
        per_band=[];channels[instrument]=selected
        for c in selected:
            sources=[v for v in product.channels if v['band']==c['band']] if instrument=='OCI' else [c]
            items=[]
            for source in sources:
                raw=product.values(source)
                current=atmosphere.corrected_values(product,source,recipe)
                molecular=subtract(product,source,atmosphere.p,raw=raw)
                trial=apply_land_trial(current,molecular,atmosphere.surface_class)
                items.append((raw,current,trial))
                # On water and unknown bins, the trial must be production-identical.
                for key in trial:
                    np.testing.assert_array_equal(trial[key][~land],current[key][~land])
            combined=[]
            if instrument=='OCI':
                observed=np.isfinite(np.stack([x[0]['total'] for x in items])).sum(axis=0)==1
                for i in range(3):
                    fields=np.stack([x[i]['total'] for x in items]);valid=observed&(np.isfinite(fields).sum(axis=0)==1)
                    combined.append({'total':np.where(valid,np.nansum(fields,axis=0),np.nan)})
            else:combined=list(items[0])
            raw,current,trial=combined
            label=f'{instrument} {c["wavelength"]:.3f} nm'
            summaries[label]={name:field_summary(raw[name],trial[name],land) for name in ('total','polarized','dolp','signed_q','signed_u') if name in trial}
            arrays['current'][0 if instrument=='OCI' else 1].append(current['total'])
            arrays['trial'][0 if instrument=='OCI' else 1].append(trial['total'])
            if instrument=='HARP2':
                arrays['current'][2].append(current['polarized']);arrays['trial'][2].append(trial['polarized'])
            per_band.append((raw,trial))
        summaries[instrument+' RGB']={}
        observed=np.isfinite(np.stack([x[0]['total'] for x in per_band],axis=-1)).all(axis=-1)&land
        valid=np.isfinite(np.stack([x[1]['total'] for x in per_band],axis=-1)).all(axis=-1)&observed
        summaries[instrument+' RGB']={'observed_land_bins':int(observed.sum()),'corrected_land_bins':int(valid.sum()),'lost_land_bins':int((observed&~valid).sum()),'any_new_negative_component_bins':int((valid&np.any(np.stack([x[1]['total']<0 for x in per_band]),axis=0)).sum())}
    return {k:[np.stack(a,axis=-1) for a in panels] for k,panels in arrays.items()},summaries,channels


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('oci','harp2','atmosphere'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--recipe');parser.add_argument('--output',default='outputs/land-rayleigh-trial')
    args=parser.parse_args();start=time.perf_counter()
    scene=Scene(args.oci,args.harp2,atmosphere_path=args.atmosphere)
    try:
        if args.recipe:
            saved=json.loads(Path(args.recipe).read_text())
            if saved.get('inputs') and saved['inputs']!=[scene.oci.identity,scene.harp.identity]:raise ValueError('Recipe belongs to different L1C products')
            if saved.get('atmosphere') and saved['atmosphere']!=scene.atmosphere.provenance:raise ValueError('Recipe belongs to a different atmospheric cache')
            recipe=Recipe.from_dict(saved.get('recipe',saved))
        else:recipe=scene.default_recipe()
        # Same existing model and pressure fields, with a land-only display policy experiment.
        recipe=replace(recipe,correction='rayleigh',polar_rayleigh=True,rayleigh_land=False,middle_mode='harp_total',harp_mode='rgb',third_quantity='polarized',cloudbow_overlay=False,rft_overlay=False,rft_components=False)
        recipe.validate(scene.shape)
        atmosphere=scene.atmosphere
        if atmosphere.surface_class is None:raise ValueError('Land trial needs classified land/water/unknown fields')
        land=atmosphere.surface_class==1
        arrays,stats,channels=evaluate(scene,recipe)
        r0,r1,c0,c1=recipe.crop or [0,scene.shape[0],0,scene.shape[1]]
        visible=land[r0:r1,c0:c1]&np.isfinite(arrays['current'][1][r0:r1,c0:c1]).all(axis=-1)
        rr,cc=np.where(visible)
        if len(rr):
            crop=[max(r0,r0+int(rr.min())-8),min(r1,r0+int(rr.max())+9),max(c0,c0+int(cc.min())-8),min(c1,c0+int(cc.max())+9)]
        else:crop=[r0,r1,c0,c1]
        r0,r1,c0,c1=crop;sl=np.s_[r0:r1,c0:c1];land_view=land[sl]
        report={'status':'offline experimental land trial, not atmospheric accuracy validation','inputs':[scene.oci.identity,scene.harp.identity],
                'atmosphere':atmosphere.provenance,'recipe':asdict(recipe),'rayleigh_model':MODEL,
                'policy':'Classified land uses exactly the existing Rayleigh component subtraction and cached cloud/surface boundary. Water/unknown remain production-identical. Unsupported land is missing; no TOA fallback or new pressure model.',
                'surface_counts':{str(code):int((atmosphere.surface_class==code).sum()) for code in [-1,0,1]},
                'land_pressure':distribution(atmosphere.p[land]),'land_missing_pressure':int((land&~np.isfinite(atmosphere.p)).sum()),
                'land_state_counts':{str(code):int((land&(atmosphere.state==code)).sum()) for code in range(5)},
                'land_phase_counts':{str(code):int((land&(atmosphere.phase==code)).sum()) for code in range(5)} if atmosphere.phase is not None else None,
                'current_view_statistics':stats,'current_view_channels':channels,'display_crop':crop,
                'display':'same saved beauty/comparison transfer for both columns; gray missing, dotted line is classified-land boundary. Difference colors are visualization only; no scientific clipping.',
                'additional_harp_sectors':{}}
        for anchor in [6.6,-33.7]:
            _,other,other_channels=evaluate(scene,replace(recipe,anchor_angle=anchor,manual_views=None))
            report['additional_harp_sectors'][str(anchor)]={'channels':other_channels['HARP2'],'statistics':{k:v for k,v in other.items() if k.startswith('HARP2')}}
        for product in [scene.oci,scene.harp]:
            if 'height' in product.geo:
                height=product.read('height');unit=product.geo.height.attrs.get('units','unknown')
                report[product.instrument+'_land_height']={'units':unit,'distribution':distribution(height[land])}
                if height.shape==land.shape and unit in ('m','meters','meter'):
                    blue=arrays['trial'][0 if product.instrument=='OCI' else 1][...,2]
                    report[product.instrument+'_blue_by_height']={}
                    for lo,hi in [(-1000,1000),(1000,3000),(3000,10000)]:
                        m=land&(height>=lo)&(height<hi)&np.isfinite(blue)
                        report[product.instrument+'_blue_by_height'][f'{lo}:{hi} m']={'valid':int(m.sum()),'negative':int((m&(blue<0)).sum())}
        output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
        fig=Figure(figsize=(13,12),layout='constrained');FigureCanvasAgg(fig);axes=fig.subplots(3,3)
        names=['OCI total RGB','HARP2 total RGB','HARP2 polarized RGB']
        for row,name in enumerate(names):
            before=arrays['current'][row][sl];after=arrays['trial'][row][sl]
            for col,(label,value) in enumerate([('Reference: water corrected, land TOA',before),('Trial: water + land corrected',after)]):
                ax=axes[row,col];ax.set_facecolor('#d9d9d9');ax.imshow(colors(value,'total' if row<2 else 'polarized',recipe),origin='lower',interpolation='none',extent=[c0,c1,r0,r1]);ax.set_title(name+'\n'+label,fontsize=10)
                if land_view.any() and (~land_view).any():ax.contour(np.arange(c0,c1)+.5,np.arange(r0,r1)+.5,land_view,levels=[.5],colors='#f0c96a',linewidths=.45)
                ax.set_xlabel('Original column');ax.set_ylabel('Original row')
            delta=after[...,2]-before[...,2];delta=np.where(land_view,delta,np.nan)
            finite=np.abs(delta[np.isfinite(delta)]);limit=max(float(np.percentile(finite,98)) if len(finite) else .01,1e-5)
            ax=axes[row,2];ax.set_facecolor('#d9d9d9');im=ax.imshow(delta,origin='lower',interpolation='none',extent=[c0,c1,r0,r1],cmap='RdBu_r',vmin=-limit,vmax=limit)
            ax.set_title('Land only: land-enabled − water-only\nblue-channel '+('total' if row<2 else 'polarized')+' reflectance',fontsize=10);ax.set_xlabel('Original column');ax.set_ylabel('Original row');fig.colorbar(im,ax=ax,shrink=.7,label='Reflectance change')
        fig.suptitle('Offline land trial · existing analytical Rayleigh / existing pressure\nSame image stretch · original L1C bins · gray = missing or outside land in difference maps',fontsize=13)
        fig.savefig(output.with_suffix('.png'),dpi=160)
        fig.savefig(output.with_suffix('.pdf'),metadata={'CreationDate':None,'ModDate':None})
        report['elapsed_seconds']=round(time.perf_counter()-start,3)
        output.with_suffix('.json').write_text(json.dumps(jsonable(report),indent=2))
        print(json.dumps({'output':str(output),'land_bins':int(land.sum()),'missing_land_pressure':report['land_missing_pressure'],'rgb_statistics':{k:v for k,v in stats.items() if k.endswith(' RGB')},'elapsed_seconds':report['elapsed_seconds']},indent=2))
    finally:scene.close()


if __name__=='__main__':main()
