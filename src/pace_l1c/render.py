"""Same source cells and transfer functions for browser preview and figures."""
from pathlib import Path
from dataclasses import asdict
from io import BytesIO
import base64
import json
import numpy as np
from PIL import Image, ImageDraw
import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.collections import PolyCollection
from matplotlib.colors import Normalize,ListedColormap,BoundaryNorm,TwoSlopeNorm
from matplotlib.cm import ScalarMappable
import matplotlib.patheffects as pe
from .geometry import Grid
from .reader import jsonable
from .coastline import projected_lines

PLOT_COLORS={'observations':['#0072B2','#E69F00'],'rft':'#CC007A',
             'modes':['#00A6A6','#7B4DFF'],'cloudbow':'#303030'}

def contour_palette(rgba):
    """Choose annotation contrast from displayed pixels, excluding missing data."""
    visible=rgba[...,3]>0
    luminance=rgba[...,:3] @ np.array([.2126,.7152,.0722])
    dark=not visible.any() or np.median(luminance[visible])<.45
    return ('#fff3b0','#172e36') if dark else ('#173b42','#fffefa')


def scattering_contours(ax, scene, recipe, grid, fontsize=7, palette=('#fff3b0','#172e36')):
    """Display-only isolines; mask invalid cells and never fill source gaps."""
    field, channel = scene.scattering_grid(recipe)
    r0,r1,c0,c1 = grid.crop
    centers = grid.centers[r0:r1,c0:c1]
    field = np.ma.masked_invalid(np.where(grid.valid & np.isfinite(centers).all(axis=-1),field[r0:r1,c0:c1],np.nan))
    centers = np.nan_to_num(centers)
    if min(field.shape)<2 or field.count()==0:
        return
    levels = np.arange(10,180,10)
    levels = levels[(levels>field.min()) & (levels<field.max())]
    if not len(levels):
        return
    ink,halo=palette
    cs = ax.contour(centers[...,0],centers[...,1],field,levels=levels,
                    colors=ink,linewidths=.55,corner_mask=False)
    cs.set_path_effects([pe.Stroke(linewidth=1.1,foreground=halo,alpha=.8),pe.Normal()])
    labels = ax.clabel(cs,fmt=lambda v:f'{v:.0f}°',fontsize=fontsize,inline=True,inline_spacing=3)
    for label in labels:
        label.set_color(ink)
        label.set_fontweight('normal')
        label.set_fontstyle('normal')
        label.set_fontfamily('DejaVu Sans')
        label.set_path_effects([pe.Stroke(linewidth=1.5,foreground=halo),pe.Normal()])


PHASE_COLORS=['#a6aaa8','#88c5eb','#2da58a','#956bc2','#e2a44c']
PHASE_LABELS=['No mask','Clear','Liquid','Ice','Unknown cloud']

def colors(array, quantity, recipe):
    if quantity=='baseline_angle':
        from .liquid_index import baseline_angle_scale
        scale=baseline_angle_scale(array,getattr(recipe,'baseline_angle_range','percentile'))
        rgba=matplotlib.colormaps['turbo'](Normalize(scale['minimum'],scale['maximum'],clip=True)(np.nan_to_num(array)))
        rgba[...,3]=np.isfinite(array)
        return rgba
    if quantity=='liquid_index':
        from .liquid_index import display_scale
        scale=display_scale(array)
        rgba=matplotlib.colormaps['bwr'].resampled(257)(TwoSlopeNorm(vmin=scale['minimum'],vcenter=.3,vmax=scale['maximum'])(np.clip(np.nan_to_num(array),scale['minimum'],scale['maximum'])))
        rgba[...,3]=np.isfinite(array)
        return rgba
    if quantity=='phase':
        rgba=ListedColormap(PHASE_COLORS)(BoundaryNorm(np.arange(-.5,5.5),5)(np.nan_to_num(array)))
        rgba[...,3]=np.isin(array,np.arange(5))
        return rgba
    lo, hi, gamma = recipe.stretch[quantity]
    if array.ndim == 2:
        maximum = max(abs(lo), abs(hi))
        norm = Normalize(-maximum, maximum) if quantity.startswith("signed") else Normalize(lo,hi)
        rgba = matplotlib.colormaps["RdBu_r" if quantity.startswith("signed") else "viridis"](norm(array))
        rgba[...,3] = np.isfinite(array)
    else:
        rgb = np.clip((array-lo)/(hi-lo), 0, 1)**(1/gamma)
        rgba = np.concatenate((np.nan_to_num(rgb), np.isfinite(array).all(axis=-1)[...,None]), axis=-1)
    return rgba


def preview(scene, recipe, width=560, height=420, *, cancelled=None):
    recipe.validate(scene.shape)
    if not (32 <= width <= 2048 and 32 <= height <= 2048):
        raise ValueError("Preview dimensions must be 32–2048 pixels")
    key = (recipe.projection,tuple(recipe.crop or []),width,height)
    if key not in scene._grids:
        grid = Grid(scene.oci, recipe)
        polygons = grid.screen(grid.vertices, width, height)
        ids_image = Image.new("I", (width,height), -1)
        ids_draw = ImageDraw.Draw(ids_image)
        for poly, id_ in zip(polygons[grid.valid], grid.ids[grid.valid]):
            ids_draw.polygon([tuple(p) for p in poly], fill=int(id_))
        if len(scene._grids)>=8:
            scene._grids.pop(next(iter(scene._grids)))
        scene._grids[key] = (grid,np.array(ids_image))
    grid, ids = scene._grids[key]
    layers = []
    for i, (array, quantity) in enumerate(zip(scene.layers(recipe,cancelled=cancelled), ("phase" if recipe.left_mode=="oci_phase" else "liquid_index" if recipe.left_mode.startswith("liquid_index") else "total", "total", recipe.third_quantity))):
        display_rgba = colors(array,quantity,recipe)
        rgba = (display_rgba*255).astype(np.uint8)
        pixels = rgba.reshape(-1,4)[np.maximum(ids,0)].copy()
        pixels[ids<0] = [232,239,236,255]
        image = Image.fromarray(pixels)
        draw=ImageDraw.Draw(image)
        for line in projected_lines(scene.coastline,grid,recipe.projection):
            draw.line([tuple(p) for p in grid.screen(line,width,height)],fill=(160,175,168,255),width=1)
        if recipe.projection=="native":
            overlay_key=("graticule",key)
            if overlay_key not in scene._grids:
                fig=Figure(figsize=(width/100,height/100),dpi=100)
                FigureCanvasAgg(fig)
                ax=fig.add_axes([0,0,1,1])
                cx,cy=grid.centers[...,0],grid.centers[...,1]
                for field in (grid.lat,grid.lon):
                    contours=ax.contour(cx,cy,field,levels=5,colors="white",linewidths=.5,alpha=.7)
                    ax.clabel(contours,fontsize=7,colors="white")
                xmin,xmax,ymin,ymax=grid.bounds
                ax.set(xlim=(xmin,xmax),ylim=(ymin,ymax));ax.axis("off")
                buf=BytesIO();fig.savefig(buf,format="png",transparent=True)
                buf.seek(0);scene._grids[overlay_key]=Image.open(buf).convert("RGBA")
            image=Image.alpha_composite(image,scene._grids[overlay_key])
        if recipe.scattering_contours and i>0:
            fig=Figure(figsize=(width/100,height/100),dpi=100)
            FigureCanvasAgg(fig)
            ax=fig.add_axes([0,0,1,1])
            r0,r1,c0,c1=grid.crop
            palette=contour_palette(display_rgba[r0:r1,c0:c1])
            scattering_contours(ax,scene,recipe,grid,fontsize=14,palette=palette)
            xmin,xmax,ymin,ymax=grid.bounds
            ax.set(xlim=(xmin,xmax),ylim=(ymin,ymax));ax.axis('off')
            buf=BytesIO();fig.savefig(buf,format='png',transparent=True)
            buf.seek(0)
            image=Image.alpha_composite(image,Image.open(buf).convert('RGBA'))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        layers.append("data:image/png;base64,"+base64.b64encode(buffer.getvalue()).decode())
    marker = grid.screen(grid.centers[tuple(recipe.selected)],width,height)
    return {"layers": layers, "width": width, "height": height, "marker": jsonable(marker),
            "bounds": grid.bounds, "labels": grid.labels, "provenance": scene.provenance(recipe),
            "aspect_ratio": (grid.bounds[1]-grid.bounds[0])/(grid.bounds[3]-grid.bounds[2])*(max(.1,np.cos(np.deg2rad(grid.center_lat))) if recipe.projection=="plate_carree" else 1),
            "native_evidence": grid.native_evidence}, ids


def liquid_index_axes(ax,integration,data,recipe,observations=None):
    """Same calculated arrays as the browser; no second science calculation."""
    if recipe.liquid_plot_dolp:
        wave=observations['hyperangular_wavelength']
        samples=[v for v in observations['samples'] if v['branch']==0 and v['wavelength']==wave]
        ax.plot([v['scattering_angle'] for v in samples],[v['dolp'] for v in samples],'o',ms=2.5,color=PLOT_COLORS['observations'][0])
        ax.set(xlabel='Scattering angle (°)',ylabel='DoLP',xlim=(115,165))
        ax.set_title('DoLP · branch 1 · TOA',fontsize=7)
        integration.axis('off')
        return
    branch=int(recipe.liquid_index_branch)-1
    curve=data['branches'][branch]['series'][recipe.liquid_index_quantity]
    lo,hi=curve['window_degrees'] or [130,150]
    trapezoidal=recipe.liquid_index_trapezoidal
    method=curve['trapezoidal' if trapezoidal else 'discrete']
    x=np.asarray(curve['theta']);y=np.asarray(curve['observed'])
    ax.plot(x,y,'o',ms=2.5,color=PLOT_COLORS['observations'][branch],label='TOA observations',zorder=4)
    for a,z in ((120,130),(150,160)):ax.axvspan(a,z,color='#00745c',alpha=.07)
    if curve['window_degrees']:ax.axvspan(lo,hi,color='#00a6a6',alpha=.07)
    if curve['baseline'] is not None:
        b=np.asarray(curve['baseline']);mask=np.asarray(curve['baseline_mask'])
        ax.plot(x,b,'--',color='#303030',lw=.8,label='Linear baseline')
        if 'normalization_baseline' in curve:
            ax.plot([min(115,lo),max(165,hi)],[curve['normalization_baseline']]*2,':',color='#98642d',lw=.6,label='Reference b(135°)')
            if curve.get('boundaries'):
                for bound in curve['boundaries']:
                    at=bound['angle'];cross=bound['kind']=='crossing'
                    height=curve['normalization_baseline'] if cross else np.interp(at,curve['trapezoidal']['theta'],curve['trapezoidal']['observed'])
                    ax.plot(at,height,'x' if cross else 's',mfc='none',color='#98642d',ms=4,label='Crossing' if cross else 'Window edge')
        ax.plot(x[mask],y[mask],'o',mfc='none',mec='#00745c',ms=4,label='Baseline samples')
        if trapezoidal and method['status']=='available':
            ax.fill_between(method['theta'],method['baseline'],method['observed'],color='#00a6a6',alpha=.25,label='Trapezoidal excess')
        elif not trapezoidal:
            peak=np.asarray(curve['peak_mask'])
            ax.vlines(x[peak],b[peak],y[peak],color='#00a6a6',lw=2,label='Discrete excess')
    fmt=lambda v:'missing' if v is None else f'{v:.4g}'
    ax.set_title(f"Liquid index · {lo:g}–{hi:g}° · {'trapezoidal' if trapezoidal else 'ATBD discrete'}\nCalculated {fmt(method['value'])} · GPC {fmt(data['operational_value'])}",fontsize=7)
    ax.set(xlim=(min(115,lo-2),max(165,hi+2)),xlabel='Scattering angle (°)',ylabel='TOA −Q' if recipe.liquid_index_quantity=='signed_q' else 'TOA polarized magnitude')
    ax.legend(fontsize=5,loc='upper left')
    if method['status']=='available':
        if trapezoidal:
            tx=np.asarray(method['theta']);e=np.asarray(method['excess'])
            cumulative=np.r_[0,np.cumsum((e[:-1]+e[1:])*.5*np.diff(tx))]/(10*curve['normalization_baseline'])
        else:
            tx=curve['peak_theta'];cumulative=curve['discrete_width_factor']*np.cumsum(curve['peak_excess'])/(curve['peak_count']*curve['normalization_baseline'])
        integration.plot(tx,cumulative,'o-',ms=2,lw=.8,color='#00745c',drawstyle='default' if trapezoidal else 'steps-post')
        integration.set_title(f"Cumulative LI · reference {curve['reference_angle']:.2f}°",fontsize=6)
    else:
        integration.text(.02,.7,curve.get('reason') or method.get('reason','Integration unavailable'),transform=integration.transAxes,fontsize=5,wrap=True)
    integration.set(xlim=(lo-.5,hi+.5),xlabel='Scattering angle (°)',ylabel='Cumulative LI')
    integration.axhline(0,color='#52655b',lw=.4)


def export(scene, recipe, destination, layout="diagnostics", width_mm=180, height_mm=150, dpi=300):
    if layout not in ("one", "maps", "diagnostics"):
        raise ValueError("Unknown figure layout")
    if not (30 <= width_mm <= 1000 and 30 <= height_mm <= 1000 and 50 <= dpi <= 1200):
        raise ValueError("Invalid physical dimensions or DPI")
    recipe.validate(scene.shape)
    grid = Grid(scene.oci,recipe)
    r0,r1,c0,c1 = grid.crop
    count = 1 if layout == "one" else 3
    fig = Figure(figsize=(width_mm/25.4,height_mm/25.4), dpi=dpi, layout="constrained")
    FigureCanvasAgg(fig)
    matplotlib.rcParams["font.family"] = recipe.font
    rft_layout=layout=='diagnostics' and (recipe.rft_overlay or recipe.cloudbow_overlay)
    axes = fig.subplots(4 if layout == "diagnostics" else 1, count, squeeze=False,
                        gridspec_kw={"height_ratios": [1.5,1,.55,.8]} if layout == "diagnostics" else None)
    if layout=='diagnostics':
        gs=axes[3,0].get_gridspec()
        for a in axes[3]:a.remove()
        axes[3,0]=fig.add_subplot(gs[3,:])
        axes[2,1].axis('off');axes[2,2].axis('off')
    scope=(f"Land total: {'Rayleigh' if recipe.corrects_land_total else 'TOA'} · land polar: {'Rayleigh' if recipe.corrects_land_polarization else 'TOA'} · unclassified/diagnostics: TOA"
           if recipe.corrects_land_total or recipe.corrects_land_polarization else "Land/unclassified: original TOA · diagnostics: TOA")
    fig.suptitle(recipe.title+("\n"+scope if recipe.correction!="toa" or recipe.polar_rayleigh else "")+(f"\nExperimental RFT comparison · fixed modes · RFT: 4-order approx ×1.61, ω=1 · cloudbow/P12: stored A/B/C" if rft_layout else ""), fontsize=10)
    provenance = scene.provenance(recipe)
    arrays = scene.layers(recipe)
    tag=" · "+recipe.correction.replace("_"," + ")+" approx" if recipe.correction!="toa" else ""
    titles = ["OCI total"+tag, "HARP2 total"+tag, "HARP2 "+recipe.third_quantity+(" · Rayleigh approx" if recipe.polar_rayleigh else " · TOA")]
    quantities = ['phase' if recipe.left_mode=='oci_phase' else 'liquid_index' if recipe.left_mode.startswith('liquid_index') else 'total','total',recipe.third_quantity]
    if recipe.left_mode=='oci_phase':titles[0]='OCI cloud phase · collocated L2'
    if recipe.left_mode.startswith('liquid_index'):titles[0]='GPC liquid index · operational' if recipe.left_mode=='liquid_index' else f'Calculated LI · {recipe.left_mode.removeprefix("liquid_index_")}'
    for i in range(count):
        ax=axes[0,i]
        rgba=colors(arrays[i],quantities[i],recipe)[r0:r1,c0:c1]
        collection=PolyCollection(grid.vertices[grid.valid],facecolors=rgba[grid.valid],edgecolors="none",antialiased=False,rasterized=True)
        ax.add_collection(collection)
        for line in projected_lines(scene.coastline,grid,recipe.projection):
            ax.plot(line[:,0],line[:,1],color="#9dabaa",linewidth=.4)
        xmin,xmax,ymin,ymax=grid.bounds
        ax.set(xlim=(xmin,xmax),ylim=(ymin,ymax),xlabel=grid.labels[0],ylabel=grid.labels[1] if i==0 else "")
        ax.tick_params(labelsize=6)
        if recipe.scattering_contours and i>0:
            scattering_contours(ax,scene,recipe,grid,fontsize=7,palette=contour_palette(rgba))
        ax.grid(color="gray",alpha=.25,linewidth=.4,linestyle="--")
        ax.xaxis.label.set_size(6); ax.yaxis.label.set_size(6)
        channels = provenance['oci_channels'] if i==0 else provenance['harp_channels']
        if arrays[i].ndim==2:
            channels=channels[:1]
        label = " / ".join(f"{c['wavelength']:.1f}" for c in channels)
        if i>0:
            label += " nm\n"+" / ".join(f"{c['angle']:.1f}°" for c in channels)
        else:
            label += " nm"
        if quantities[i]=='baseline_angle':
            titles[i]='Baseline vs reference · raw numeric angle'
            label=f"atan(dR/dθ) · degrees · {recipe.liquid_index_quantity} · branch 1 · TOA"
        if quantities[i]=='phase':label='cld_phase_21 · 2.1 µm retrieval'
        if quantities[i]=='liquid_index':label='cloud_liquid_index · native GPC bins' if recipe.left_mode=='liquid_index' else f'{recipe.liquid_index_quantity} · branch {recipe.liquid_index_branch} · TOA'
        ax.set_title(titles[i]+"\n"+label,fontsize=8)
        x,y=grid.centers[tuple(recipe.selected)]
        ax.plot(x,y,"+",color="black",markersize=9,markeredgewidth=2)
        ax.plot(x,y,"+",color="white",markersize=7,markeredgewidth=1)
        ax.set_aspect("equal" if recipe.projection!="plate_carree" else 1/max(.1,np.cos(np.deg2rad(grid.center_lat))))
        if recipe.projection == "native":
            xx,yy=np.meshgrid(np.arange(scene.shape[1])*5.2,np.arange(scene.shape[0])*5.2)
            for data in (grid.lat,grid.lon):
                cs=ax.contour(xx,yy,data,levels=5,colors="gray",linewidths=.4)
                ax.clabel(cs,fontsize=5)
        if quantities[i]=='phase':
            bar=fig.colorbar(ScalarMappable(norm=BoundaryNorm(np.arange(-.5,5.5),5),cmap=ListedColormap(PHASE_COLORS)),ax=ax,shrink=.6,ticks=np.arange(5))
            bar.ax.set_yticklabels(PHASE_LABELS);bar.ax.tick_params(labelsize=5)
        elif quantities[i]=='baseline_angle':
            from .liquid_index import baseline_angle_scale
            scale=baseline_angle_scale(arrays[i],getattr(recipe,'baseline_angle_range','percentile'))
            bar=fig.colorbar(ScalarMappable(norm=Normalize(scale['minimum'],scale['maximum']),cmap=matplotlib.colormaps['turbo']),ax=ax,shrink=.6,extend='both' if getattr(recipe,'baseline_angle_range','percentile')=='percentile' else 'neither',label='Raw baseline angle α (°) · '+('1–99% display' if getattr(recipe,'baseline_angle_range','percentile')=='percentile' else 'full range'))
            bar.ax.tick_params(labelsize=5);bar.ax.yaxis.label.set_size(6)
        elif quantities[i]=='liquid_index':
            from .liquid_index import display_scale
            scale=display_scale(arrays[i])
            bar=fig.colorbar(ScalarMappable(norm=TwoSlopeNorm(vmin=scale['minimum'],vcenter=.3,vmax=scale['maximum']),cmap=matplotlib.colormaps['bwr'].resampled(257)),ax=ax,shrink=.6,extend='both',ticks=[scale['minimum'],.3,scale['maximum']],label='Liquid index · white=0.3')
            bar.ax.tick_params(labelsize=5);bar.ax.yaxis.label.set_size(6)
        elif arrays[i].ndim==2:
            maximum=max(abs(v) for v in recipe.stretch[quantities[i]][:2])
            signed=quantities[i].startswith("signed")
            lo,hi,_=recipe.stretch[quantities[i]]
            bar=fig.colorbar(ScalarMappable(norm=Normalize(-maximum,maximum) if signed else Normalize(lo,hi),cmap="RdBu_r" if signed else "viridis"),ax=ax,shrink=.6,label="− scattering-plane reflectance" if signed else "TOA reflectance")
            bar.ax.tick_params(labelsize=5);bar.ax.yaxis.label.set_size(6)
    if layout=="diagnostics":
        diag=scene.diagnostics(recipe.selected,rft=recipe.rft_overlay,rft_weighting=recipe.rft_weighting)
        provenance['selected_cloud_diagnostics']=diag['cloud']
        provenance['liquid_index']=diag['liquid_index']
        liquid_index_axes(axes[1,0],axes[2,0],diag['liquid_index'],recipe,diag['harp2'])
        ax=axes[3,0]
        ax.plot(diag["oci"]["wavelength"],diag["oci"][recipe.spectrum_quantity],linewidth=.8,color=PLOT_COLORS['observations'][0])
        ax.set(xlabel="Wavelength (nm)",ylabel="TOA "+recipe.spectrum_quantity)
        ax.set_title(f"Original bin {recipe.selected} • {diag['latitude']:.3f}°, {diag['longitude']:.3f}°",fontsize=7)
        branches=(0,1) if recipe.diagnostic_branch=="both" else (int(recipe.diagnostic_branch)-1,)
        for column,(ax,branch) in enumerate(zip(axes[1,1:],branches),start=1):
            samples=diag["harp2"]["samples"]
            for wave in [diag["harp2"]["hyperangular_wavelength"]]:
                subset=[s for s in samples if s["wavelength"]==wave and s["branch"]==branch]
                ax.plot([s[recipe.diagnostic_axis] for s in subset],[s[recipe.diagnostic_quantity] for s in subset],"o",markersize=2.5,color=PLOT_COLORS['observations'][branch],mec='white',mew=.25,zorder=6,label=f"{wave:.1f} nm observations")
                target=provenance['harp_channels'][0]['angle']
                active=min((s for s in samples if s['wavelength']==wave),key=lambda s:abs(s['angle']-target))
                if active in subset and active[recipe.diagnostic_axis] is not None and active[recipe.diagnostic_quantity] is not None:
                    x,y=active[recipe.diagnostic_axis],active[recipe.diagnostic_quantity]
                    ax.plot(x,y,'o',mfc='none',mec='#253632',markersize=5,zorder=7)
                    ax.annotate(f"Sector {active['angle']:.1f}°",(x,y),xytext=(0,12),textcoords='offset points',ha='center',fontsize=5,
                                bbox={'facecolor':'white','alpha':.8,'edgecolor':'none','pad':1},arrowprops={'arrowstyle':'-','linewidth':.4})
            model=diag['cloudbow']
            if recipe.cloudbow_overlay and model['status']=='experimental' and recipe.diagnostic_quantity=='signed_q' and recipe.diagnostic_axis=='scattering_angle':
                ax.plot(model['theta'],model['signed_q'],color=PLOT_COLORS['cloudbow'],linewidth=.9,zorder=2,label='Cloudbow · stored A/B/C')
            if recipe.rft_overlay and recipe.diagnostic_quantity=='signed_q' and recipe.diagnostic_axis=='scattering_angle':
                fit=next((b for b in diag['rft'].get('thick_branches',[]) if b['branch']==branch),None)
                if fit and fit['status']=='experimental':
                    ax.plot(fit['theta'],fit['signed_q'],color=PLOT_COLORS['rft'],linewidth=1.6,zorder=3,label='RFT refl. · 4-order + Rayleigh' if fit.get('rayleigh_status')=='included' else 'RFT refl. · 4-order cloud only')
                    if recipe.rft_components and 'signed_rayleigh' in fit:
                        ax.plot(fit['theta'],fit['signed_rayleigh'],color='#b56b00',linestyle='--',linewidth=1.1,label='Rayleigh contribution')
                    for enabled,key,kind in [(recipe.rft_components,'signed_full_contributions','contribution')]:
                        if enabled:
                            for mode,values in zip(fit['mode_ids'],fit[key]):
                                ax.plot(fit['theta'],values,color=PLOT_COLORS['modes'][mode],linewidth=1.2,
                                        linestyle=':' if key=='signed_full_modes' else ((0,(7,4)) if mode==0 else (0,(6,3,1,3))),zorder=4,
                                        path_effects=[pe.Stroke(linewidth=2.5,foreground='white'),pe.Normal()],label=f'Mode {mode} {kind}')
                else:
                    ax.text(.03,.97,fit['reason'] if fit else diag['rft'].get('reason','RFT unavailable'),
                            transform=ax.transAxes,va='top',fontsize=5,wrap=True)
            if recipe.rft_overlay and recipe.rft_p12 and recipe.diagnostic_quantity=='signed_q' and recipe.diagnostic_axis=='scattering_angle':
                stored=next((b for b in diag['rft'].get('branches',[]) if b['branch']==branch),None)
                if stored and stored['status']=='experimental':
                    for mode,values in zip(stored['mode_ids'],stored['signed_full_modes']):
                        ax.plot(stored['theta'],values,color=PLOT_COLORS['modes'][mode],linestyle=':',linewidth=1.2,
                                label=f'Mode {mode} P12 · A/B/C',zorder=4)
            ax.set(xlabel="Scattering angle (°)" if recipe.diagnostic_axis=="scattering_angle" else "Nominal angle (°)",ylabel=recipe.diagnostic_quantity)
            ax.set_title(f"Exploratory branch {branch+1}",fontsize=7)
            ax.legend(fontsize=5,loc='lower left')
        if len(branches)==1:
            axes[1,2].axis('off')
            message='Observations are discrete source views.\nCloudbow curve uses stored coefficients.\nOperational branch and normalization unverified.' if recipe.cloudbow_overlay else 'Observations are discrete source views.'
            axes[1,2].text(.05,.5,message,fontsize=6,wrap=True)
            if rft_layout:axes[2,2].axis('off')
        if rft_layout:
            provenance['polarimetric_residuals']=diag['residuals']
            axes[2,1].axis('off');axes[2,2].axis('off')
            if 0 in branches and recipe.diagnostic_quantity=='signed_q' and recipe.diagnostic_axis=='scattering_angle':
                residual=axes[2,1];residual.axis('on')
                series=diag['residuals']['series']
                for name,label,color,enabled,symbol in [('cloudbow','Cloudbow − observed',PLOT_COLORS['cloudbow'],recipe.cloudbow_overlay,'o'),('rft','RFT refl. − observed',PLOT_COLORS['rft'],recipe.rft_overlay,'D')]:
                    if enabled and series[name]['status']=='available':
                        residual.plot(diag['residuals']['theta'],series[name]['residual_signed_q'],symbol,
                                      markersize=2,color=color,mfc='none' if name=='cloudbow' else color,label=label)
                residual.axhline(0,color='#52655b',linewidth=.4)
                residual.set(xlabel='Scattering angle (°)',ylabel='Model − observed (−Q)')
                residual.set_title(f"Branch 1 · n={diag['residuals']['sample_count']} shared observations",fontsize=6)
                residual.legend(fontsize=5)
        if rft_layout:
            axes[2,2].axis('off')
            fields=diag['cloud'].get('fields',{})
            lines=['Reported GPC · selected bin']
            for name,label in [('cloud_top_altitude','Top altitude'),('cloud_top_pressure','Top pressure'),('cloud_top_temperature','Top temperature')]:
                item=fields.get(name,{})
                value=item.get('value')
                lines.append(f"{label}: {value:.4g} {item.get('units','')}" if value is not None else label+': missing')
            lines.append({'number':'Number fractions × LUT Csca; normalized.',
                          'area':'Area fractions × LUT Qsca; normalized.',
                          'literal':'Published fractions used directly.'}[recipe.rft_weighting])
            modes=diag['rft'].get('modes',[])
            applied=[f"mode {m['mode']}: {m['scattering_weight']:.4f}" for m in modes if 'scattering_weight' in m]
            if applied:lines.append('Scattering weights · '+', '.join(applied))
            axes[2,2].text(0,1,'\n'.join(lines),va='top',fontsize=6,wrap=True)
        for ax in [*axes[1:3].flat,axes[3,0]]:
            ax.minorticks_on()
            ax.tick_params(labelsize=6,direction='out',which='both')
            ax.grid(which='major',color='#e3e9e3',linewidth=.5)
            ax.grid(which='minor',color='#f0f3ed',linewidth=.3)
            for spine in ax.spines.values():
                spine.set_visible(True);spine.set_linewidth(.6);spine.set_color('#52655b')
            ax.xaxis.label.set_size(7); ax.yaxis.label.set_size(7)
    if layout=="diagnostics" and height_mm<230:
        # Preserve requested physical dimensions; scale typography for dense layouts.
        from matplotlib.text import Text
        for text in fig.findobj(Text):text.set_fontsize(text.get_fontsize()*max(.5,height_mm/230))
    destination=Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    artifacts=[]
    for suffix in ("png","pdf"):
        path=destination.with_suffix("."+suffix)
        fig.savefig(path,dpi=dpi,metadata={"Title":recipe.title,"Creator":"PACE L1C visualization","CreationDate":None,"ModDate":None} if suffix=="pdf" else None)
        artifacts.append(path)
    provenance.update(geometry={"bounds":grid.bounds,"native_evidence":grid.native_evidence,
                    "cell_policy":"half-bin edges from original geolocation; invalid/disconnected polygons excluded"},
                      export={"layout":layout,"width_mm":width_mm,"height_mm":height_mm,"dpi":dpi})
    provenance["coastline"]={k:v for k,v in scene.coastline.items() if k!="lines"} if scene.coastline else None
    path=destination.with_suffix(".json")
    path.write_text(json.dumps(jsonable(provenance),indent=2,allow_nan=False))
    artifacts.append(path)
    return artifacts
