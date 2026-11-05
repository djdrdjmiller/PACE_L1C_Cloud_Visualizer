"""Strict shared-source correspondence and versioned scene recipes."""
from dataclasses import dataclass, field, asdict
from datetime import datetime
import numpy as np
from .reader import Product, jsonable
from . import __version__


@dataclass
class Recipe:
    schema_version: int = 1
    projection: str = "plate_carree"
    crop: list | None = None  # original row start/stop, column start/stop
    selected: list = field(default_factory=lambda: [0, 0])
    oci_targets: list = field(default_factory=lambda: [645., 555., 443.])
    harp_targets: list = field(default_factory=lambda: [670., 550., 440.])
    anchor_angle: float = 0.
    manual_views: list | None = None
    harp_mode: str = "rgb"
    left_mode: str = "oci_total"
    liquid_index_quantity: str = 'signed_q'
    liquid_index_branch: str = '1'
    liquid_index_trapezoidal: bool = False
    liquid_plot_dolp: bool = False
    third_quantity: str = "polarized"
    stretch: dict = field(default_factory=lambda: {"total": [0., 1., 1.], "polarized": [0., .15, 1.], "dolp": [0., 1., 1.], "signed_q": [-.15, .15, 1.], "signed_u": [-.15, .15, 1.]})
    preset: str = "comparison"
    mismatch_warning_degrees: float = 5.
    diagnostic_quantity: str = "polarized"
    diagnostic_axis: str = "scattering_angle"
    diagnostic_branch: str = "both"
    cloudbow_overlay: bool = False
    rft_overlay: bool = False
    rft_components: bool = False
    rft_p12: bool = False  # full per-mode A/B/C response before fraction weighting
    rft_scaling: str = 'stored'
    rft_weighting: str = 'number'
    scattering_contours: bool = False
    correction: str = "toa"
    polar_rayleigh: bool = False
    rayleigh_land: bool = True
    extrapolate_surface: bool = False  # retired experiment; false retained for recipe compatibility
    spectrum_quantity: str = "total"
    title: str = "PACE L1C"
    font: str = "DejaVu Sans"

    @classmethod
    def from_dict(cls, values):
        """Preserve historical weighting and water-only Rayleigh on old recipes."""
        values=dict(values)
        legacy=values.pop('middle_mode',None)
        if 'left_mode' not in values and legacy is not None:
            values['left_mode']='oci_total' if legacy=='harp_total' else legacy
        retired=('liquid_index_wide','liquid_index_adaptive','baseline_angle_range')
        for key in retired:values.pop(key,None)
        if values.get('left_mode') in ('liquid_index_wide_discrete','liquid_index_wide_trapezoidal','liquid_index_adaptive_trapezoidal','liquid_index_baseline_angle'):
            values['left_mode']='oci_total'
        if values.get('rft_overlay') and 'rft_weighting' not in values:
            values['rft_weighting']='literal'
        if 'rayleigh_land' not in values and (values.get('correction') in ('rayleigh','rayleigh_transmission') or values.get('polar_rayleigh')):
            values['rayleigh_land']=False
        return cls(**values)

    @property
    def corrects_land_total(self):
        return self.rayleigh_land and self.correction in ('rayleigh','rayleigh_transmission')

    @property
    def corrects_land_polarization(self):
        return self.rayleigh_land and self.polar_rayleigh

    def validate(self, shape):
        if self.correction not in ("toa","transmission","rayleigh","rayleigh_transmission"):
            raise ValueError("Unsupported total-reflectance correction")
        if self.schema_version != 1:
            raise ValueError("Unsupported recipe schema")
        if self.projection not in ("plate_carree", "laea", "native"):
            raise ValueError("Unsupported projection")
        if self.third_quantity not in ("polarized", "dolp", "signed_q", "signed_u"):
            raise ValueError("Unsupported third-map quantity")
        if self.left_mode not in ('oci_total','oci_phase','liquid_index','liquid_index_discrete','liquid_index_trapezoidal'):
            raise ValueError('Unsupported left-map mode')
        if self.liquid_index_quantity not in ('signed_q','polarized') or self.liquid_index_branch != '1':
            raise ValueError('Unsupported liquid-index quantity or branch')
        if type(self.liquid_index_trapezoidal) is not bool or type(self.liquid_plot_dolp) is not bool:
            raise ValueError('Liquid-index display options must be boolean')
        if self.harp_mode not in ("rgb", "single"):
            raise ValueError("Unsupported HARP2 total-map mode")
        if self.diagnostic_quantity not in ("polarized", "dolp", "signed_q", "signed_u") or self.diagnostic_axis not in ("scattering_angle", "angle") or self.spectrum_quantity not in ("total", "radiance"):
            raise ValueError("Unsupported diagnostic settings")
        if self.diagnostic_branch not in ("both","1","2"):
            raise ValueError("Unsupported angular branch")
        if self.rft_scaling != 'stored':
            raise ValueError('RFT coefficient refitting was removed; use original stored cloudbow coefficients')
        if self.rft_weighting not in ('literal','number','area'):
            raise ValueError('RFT weighting must be literal, number or area')
        if any(type(v) is not bool for v in (self.scattering_contours,self.polar_rayleigh,self.rayleigh_land,self.extrapolate_surface,self.cloudbow_overlay,self.rft_overlay,self.rft_components,self.rft_p12)):
            raise ValueError("Scattering contours must be enabled or disabled")
        if self.extrapolate_surface:
            raise ValueError('Surface transmission extrapolation was retired; set extrapolate_surface=false')
        if len(self.selected) != 2 or any(type(v) is not int for v in self.selected) or not (0 <= self.selected[0] < shape[0] and 0 <= self.selected[1] < shape[1]):
            raise ValueError("Invalid selected original bin")
        if self.crop is not None:
            if len(self.crop) != 4 or any(type(v) is not int for v in self.crop):
                raise ValueError("Crop requires four integer source indices")
            r0, r1, c0, c1 = self.crop
            if not (0 <= r0 < r1 <= shape[0] and 0 <= c0 < c1 <= shape[1]):
                raise ValueError("Crop outside source grid")
        for key, limits in self.stretch.items():
            if len(limits) != 3 or not np.all(np.isfinite(limits)) or limits[0] >= limits[1] or limits[2] <= 0:
                raise ValueError(f"Invalid enhancement for {key}")
        for targets in (self.oci_targets, self.harp_targets):
            if len(targets) != 3 or not np.all(np.isfinite(targets)):
                raise ValueError("RGB requires three finite wavelength targets")
        if not np.isfinite(self.anchor_angle):
            raise ValueError("Invalid anchor angle")
        return self


class Scene:
    def __init__(self, oci_path, harp_path, gpc_path=None, mie_path=None, atmosphere_path=None):
        self.oci = Product(oci_path)
        try:
            self.harp = Product(harp_path)
            if self.oci.instrument != "OCI" or self.harp.instrument != "HARP2":
                raise ValueError("Load OCI followed by HARP2")
            o, h = self.oci, self.harp
            if o.shape != h.shape:
                raise ValueError("Different source grid dimensions; direct shared-bin mapping unavailable")
            for attr in ("time_coverage_start", "time_coverage_end", "nadir_bin"):
                if attr not in o.attrs or attr not in h.attrs or o.attrs[attr] != h.attrs[attr]:
                    raise ValueError(f"Pair mismatch/missing {attr}; choose products on the same source grid")
            og, hg = o.attrs.get("l1cgrid_source"), h.attrs.get("l1cgrid_source")
            if og and hg and og != hg:
                raise ValueError("Different declared L1C source grids")
            valid = np.isfinite(o.lat) & np.isfinite(o.lon) & np.isfinite(h.lat) & np.isfinite(h.lon)
            if not valid.any():
                raise ValueError("No common finite geolocation")
            dlon = (o.lon - h.lon + 180) % 360 - 180
            error = np.hypot((o.lat-h.lat)[valid], (dlon*np.cos(np.deg2rad(o.lat)))[valid]) * 111195
            if error.max() > 20:
                raise ValueError(f"Geolocation mismatch {error.max():.1f} m exceeds 20 m tolerance")
            self.evidence = {"common_grid": hg or og, "grid_metadata": "both declared" if og and hg else "one declaration absent; full geolocation verified",
                             "time_start": o.attrs["time_coverage_start"],
                             "compared_bins": int(valid.sum()), "max_geolocation_error_m": float(error.max()), "tolerance_m": 20}
            self.shape = o.shape
            self._layers = {}
            self._liquid_maps = {}
            self._grids = {}
            from .coastline import load
            self.coastline=load()
            self.atmosphere=None
            if atmosphere_path:
                from .atmosphere import Atmosphere
                self.atmosphere=Atmosphere(atmosphere_path,self)
            self.cloudbow=None
            self.gpc=None
            if gpc_path and mie_path:
                from .cloudbow import Cloudbow
                self.cloudbow=Cloudbow(gpc_path,mie_path,self.harp)
                self.gpc=self.cloudbow
            elif gpc_path:
                from .gpc import RegisteredGPC
                self.gpc=RegisteredGPC(gpc_path,self.harp)
            elif mie_path:
                raise ValueError("A local Mie library requires a matching GPC product for model overlays")
        except Exception:
            self.close()
            raise

    def close(self):
        self.oci.close()
        if hasattr(self, "harp"):
            self.harp.close()
        if getattr(self,"gpc",None):
            self.gpc.close()

    def channels(self, recipe):
        recipe.validate(self.shape)
        for targets,product in ((recipe.oci_targets,self.oci),(recipe.harp_targets,self.harp)):
            wavelengths=[c["wavelength"] for c in product.channels]
            if any(t<min(wavelengths)-10 or t>max(wavelengths)+10 for t in targets):
                raise ValueError(f"Requested {product.instrument} wavelength outside available channel range")
        oc = [min((c for c in self.oci.channels if c["view"] == 0), key=lambda c: abs(c["wavelength"]-t)) for t in recipe.oci_targets]
        h = self.harp.channels
        if recipe.manual_views is not None:
            if len(recipe.manual_views) != 3:
                raise ValueError("Manual HARP RGB requires three source views")
            hc = []
            for v in recipe.manual_views:
                if type(v) is not int or not 0 <= v < len(h):
                    raise ValueError("Invalid HARP source view")
                hc.append(next(c for c in h if c["view"] == v))
        else:
            hc = []
            anchor_target = 550 if any(abs(t-550)<20 for t in recipe.harp_targets) else min(recipe.harp_targets)
            anchor_wave = min({c["wavelength"] for c in h},key=lambda w:abs(w-anchor_target))
            anchor = min((c for c in h if c["wavelength"]==anchor_wave),key=lambda c:abs(c["angle"]-recipe.anchor_angle))["angle"]
            for t in recipe.harp_targets:
                wave = min({c["wavelength"] for c in h}, key=lambda w: abs(w-t))
                hc.append(min((c for c in h if c["wavelength"] == wave), key=lambda c: abs(c["angle"]-anchor)))
        return oc, hc

    def layers(self, recipe, *, cancelled=None):
        oc, hc = self.channels(recipe)
        key = (tuple(c["band"] for c in oc), tuple(c["view"] for c in hc), recipe.third_quantity,recipe.harp_mode,recipe.correction,recipe.polar_rayleigh,recipe.rayleigh_land,recipe.extrapolate_surface,recipe.left_mode,recipe.liquid_index_quantity,recipe.liquid_index_branch)
        if key not in self._layers:
            oci = np.stack([self.oci.oci_band(c["band"]) for c in oc], axis=-1)
            hv = [self.harp.values(c) for c in hc]
            harp = hv[0]["total"] if recipe.harp_mode=="single" else np.stack([v["total"] for v in hv], axis=-1)
            third = hv[0][recipe.third_quantity] if recipe.third_quantity.startswith("signed") else np.stack([v[recipe.third_quantity] for v in hv], axis=-1)
            if len(self._layers) >= 8:
                self._layers.pop(next(iter(self._layers)))
            arrays=[oci,harp,third]
            if recipe.correction!='toa' or recipe.polar_rayleigh:
                if not self.atmosphere:raise ValueError('No prepared atmospheric cache loaded; launch with --atmosphere')
                arrays=self.atmosphere.correct(self,recipe,arrays)
            if recipe.left_mode=='oci_phase':
                if not self.atmosphere or self.atmosphere.phase is None:raise ValueError('OCI phase map needs a cache with native OCI cloud phase')
                arrays[0]=self.atmosphere.phase
            elif recipe.left_mode=='liquid_index':
                if not self.gpc or 'cloud_liquid_index' not in self.gpc.data:
                    raise ValueError('Liquid-index map requires a registered GPC product with cloud_liquid_index')
                from .reader import ROW,COL
                arrays[0]=self.gpc.data.cloud_liquid_index.transpose(ROW,COL).values.copy()
            elif recipe.left_mode.startswith('liquid_index_'):
                from .liquid_index import map_layers
                liquid_key=(recipe.liquid_index_quantity,recipe.liquid_index_branch)
                method=recipe.left_mode.removeprefix('liquid_index_')
                cached=self._liquid_maps.setdefault(liquid_key,{})
                if method not in cached:
                    cached.update(map_layers(self.harp,recipe.liquid_index_quantity,0,extended=False,cancelled=cancelled))
                arrays[0]=cached[method]
            self._layers[key] = arrays
        return self._layers[key]

    def scattering_grid(self, recipe):
        """Actual red-view scattering geometry; shared context for the two HARP2 maps."""
        _, hc = self.channels(recipe)
        red_wave = min({c['wavelength'] for c in self.harp.channels}, key=lambda w: abs(w-670))
        channel = min((c for c in self.harp.channels if c['wavelength']==red_wave),
                      key=lambda c: abs(c['angle']-hc[0]['angle']))
        angle = self.harp.read('scattering_angle', channel)
        count = self.harp.read('number_of_observations', channel)
        return np.where((count>0)&(angle>=0)&(angle<=180), angle, np.nan), channel

    def diagnostics(self, selected, rft=False, rft_weighting='number'):
        r, c = selected
        if not(0<=r<self.shape[0] and 0<=c<self.shape[1]):
            raise ValueError('Source bin outside granule')
        harp=self.harp.diagnostics(r,c)
        comparison={'status':'disabled','reason':'Enable RFT reflectance comparison'}
        if rft:
            if self.cloudbow:
                from .rft import comparison as evaluate, add_rayleigh, approximate_scattering_orders
                comparison=evaluate(self.cloudbow,r,c,harp,weighting=rft_weighting)
                comparison=approximate_scattering_orders(comparison)
                comparison=add_rayleigh(comparison,self.harp,harp,r,c,self.atmosphere)
            else:
                comparison={'status':'unavailable','reason':'RFT requires registered GPC and Mie LUT'}
        cloudbow=self.cloudbow.solution(r,c) if self.cloudbow else {"status":"unavailable","reason":"Launch with --gpc and --mie to load the registered product and phase-function LUT"}
        from .residuals import compare
        interval=(max(self.cloudbow.lower,self.cloudbow.rft_lower),min(self.cloudbow.upper,self.cloudbow.rft_upper)) if self.cloudbow else (0,180)
        residuals=compare(harp,cloudbow,comparison,interval)
        from .liquid_index import diagnostics as liquid_diagnostics
        cloud=self.gpc.diagnostics(r,c) if self.gpc else {'status':'unavailable','reason':'No registered GPC product loaded'}
        operational=cloud.get('fields',{}).get('cloud_liquid_index',{}).get('value')
        liquid=liquid_diagnostics(harp,operational,cloud.get('source'),extended=False)
        return jsonable({"selected": selected, "latitude": self.oci.lat[r, c], "longitude": self.oci.lon[r, c],
                         "oci": self.oci.diagnostics(r, c), "harp2": harp,
                         "cloud":cloud,"liquid_index":liquid,
                         "rft":comparison,
                         "residuals":residuals,
                         "atmosphere":jsonable({'boundary_pressure_hpa':self.atmosphere.p[r,c],'water_g_cm2':self.atmosphere.w[r,c] if self.atmosphere.w is not None else None,'boundary_state':self.atmosphere.state[r,c],'surface_class':int(self.atmosphere.surface_class[r,c]) if self.atmosphere.surface_class is not None else -1,'oci_phase':self.atmosphere.phase[r,c] if self.atmosphere.phase is not None else None,'state_codes':self.atmosphere.provenance['state_codes']}) if self.atmosphere else None,
                         "cloudbow":cloudbow})

    def provenance(self, recipe):
        oc, hc = self.channels(recipe)
        liquid_scale=None
        if recipe.left_mode.startswith('liquid_index'):
            from .liquid_index import display_scale
            liquid_scale=display_scale(self.layers(recipe)[0])
        coverage=None
        if recipe.correction!='toa' or recipe.polar_rayleigh:
            arrays=self.layers(recipe);state=self.atmosphere.state
            coverage={}
            for name,array in zip(['oci','harp2'],arrays[:2]):
                if name=='oci' and recipe.left_mode!='oci_total':
                    coverage[name]={'valid_bins':0,'total_bins':int(array.size),'land_toa_bins':0,'land_corrected_bins':0,'water_corrected_bins':0,'unknown_toa_bins':0,'estimated_boundary_bins':0,'extended_surface_eligible_bins':0,'negative_components':0};continue
                valid=np.isfinite(array).all(axis=-1) if array.ndim==3 else np.isfinite(array)
                water=valid&(self.atmosphere.surface_class==0)&(recipe.correction!='toa')
                land=valid&(self.atmosphere.surface_class==1)&recipe.corrects_land_total
                coverage[name]={'valid_bins':int((water|land).sum()),'total_bins':int(valid.size),
                    'water_corrected_bins':int(water.sum()),'land_corrected_bins':int(land.sum()),
                    'land_toa_bins':int((valid&(self.atmosphere.surface_class==1)&(not recipe.corrects_land_total)).sum()),
                    'unknown_toa_bins':int((valid&(self.atmosphere.surface_class==-1)).sum()),'extended_surface_eligible_bins':0,
                    'negative_components':int((np.isfinite(array)&(array<0)).sum()),'estimated_boundary_bins':int(((water|land)&np.isin(state,[3,4])).sum())}
        span = float(np.ptp([c["angle"] for c in hc]))
        return jsonable({"schema_version": 1, "software_version": __version__, "recipe": asdict(recipe),
                         "inputs": [self.oci.identity, self.harp.identity], "alignment": self.evidence,
                         "oci_channels": oc, "harp_channels": hc, "maximum_angle_span": span,
                         "oci_view_channels":[[c for c in self.oci.channels if c['band']==chosen['band']] for chosen in oc],
                         "angle_warning": span > recipe.mismatch_warning_degrees,
                         "correction": f"Total maps: {recipe.correction}; polarimetry maps: {'Rayleigh single-scattering path removal' if recipe.polar_rayleigh else 'TOA'}; land total: {'Rayleigh' if recipe.corrects_land_total else 'TOA'}; land polar: {'Rayleigh' if recipe.corrects_land_polarization else 'TOA'}; unclassified and selected-bin diagnostics: TOA",
                         "rayleigh_land_policy":{"enabled":recipe.corrects_land_total or recipe.corrects_land_polarization,"recipe_enabled":recipe.rayleigh_land,
                             "total":'Rayleigh only' if recipe.corrects_land_total else 'TOA',
                             "polarization":'Rayleigh component subtraction' if recipe.corrects_land_polarization else 'TOA',
                             "unsupported_land":"missing when Rayleigh is enabled; no TOA fallback",
                             "unclassified":"original TOA", "transmission":"water only; never applied to land"},
                         "phase_source":self.atmosphere.provenance.get('phase_policy') if self.atmosphere and recipe.left_mode=='oci_phase' else None,
                         "liquid_index_scale":liquid_scale,
                         "liquid_index_map":({'source':self.gpc.provenance['gpc'],'variable':'cloud_liquid_index','policy':'Registered native GPC bins; CF fills missing; reported values retained independently of fit quality; blue-white-red display clipped to 0–4; white at 0.3; science unclipped'} if self.gpc else None) if recipe.left_mode=='liquid_index' else ({'source':self.harp.identity,'method':__import__('pace_l1c.liquid_index',fromlist=['METHOD']).METHOD,'integration':recipe.left_mode.removeprefix('liquid_index_'),'quantity':recipe.liquid_index_quantity,'branch':recipe.liquid_index_branch,'display_scale':liquid_scale,'scope':'original TOA; independent of atmospheric correction and nominal map anchor'} if recipe.left_mode.startswith('liquid_index_') else None),
                         "rayleigh_model":__import__('pace_l1c.rayleigh',fromlist=['MODEL']).MODEL if recipe.polar_rayleigh or recipe.correction in ('rayleigh','rayleigh_transmission') else None,
                         "surface_extrapolation":"clear-water surface only, 1000<p<=1050 hPa; extend -ln(T) using supported 900/1000 hPa slope >=0; no water/cosine extrapolation" if recipe.extrapolate_surface and recipe.correction in ('transmission','rayleigh_transmission') else None,
                         "selected_map_values":{name:array[tuple(recipe.selected)] for name,array in zip([recipe.left_mode,'harp2_total',recipe.third_quantity],self.layers(recipe))} if coverage or recipe.left_mode.startswith('liquid_index') else None,
                         "correction_coverage":coverage, "transmission_mapping":"visible 400–700 nm: LUT band 0 proxy; OCI 865/940/1615/2130/2260: indices 1/2/5/6/7 within 12 nm; HARP2 visible only" if coverage and recipe.correction in ('transmission','rayleigh_transmission') else None,
                         "atmosphere":self.atmosphere.provenance if self.atmosphere and (coverage is not None or recipe.left_mode=='oci_phase') else None, "masks": "CF fill/scale; count > 0; daylight; finite positive F0; exactly one OCI view",
                         "dolp": "map: molecular-subtracted I/Q/U in consistent radiance units; unclassified bypass; diagnostics: original radiance Q/U and positive I" if recipe.polar_rayleigh else "derived from original radiance Q/U and positive I", "signed_display": "negative scattering-plane Q/U",
                         "branch_policy": "exploratory source-view turning-point heuristic; operational identity unverified",
                         "gpc":self.gpc.provenance["gpc"] if self.gpc else None,
                         "cloudbow":self.cloudbow.provenance if self.cloudbow and recipe.cloudbow_overlay else None,
                         "rft":self.diagnostics(recipe.selected,rft=True,rft_weighting=recipe.rft_weighting)['rft'] if recipe.rft_overlay else None,
                         "scattering_contours": {"channel":self.scattering_grid(recipe)[1], "interval_degrees":10, "style":"per-panel median display luminance chooses ink/halo; matching lines; regular upright labels aligned with contours",
                             "geometry":"HARP2 red view on both HARP2 maps; actual per-bin scattering angle", "missing":"count <= 0 or invalid geometry masked"} if recipe.scattering_contours else None})

    def qualify(self, case, bbox):
        lon, lat = self.oci.lon, self.oci.lat
        w, s, e, n = bbox
        region = (lat >= s) & (lat <= n) & (((lon >= w) & (lon <= e)) if w <= e else ((lon >= w) | (lon <= e)))
        if not region.any():
            return False, "No source-bin center inside requested region"
        if case == "dateline":
            yes = bool(np.any(np.abs(np.diff(lon, axis=1)) > 180) or np.any(np.abs(np.diff(lon, axis=0)) > 180))
            return yes, "Actual adjacent source longitudes cross antimeridian" if yes else "No actual dateline crossing"
        if case == "tilt_transition":
            counts = self.oci.read("number_of_observations")
            yes = bool(np.any(counts[..., 0] > 0) and np.any(counts[..., 1] > 0))
            return yes, "Both OCI slots have positive observation counts" if yes else "Only one OCI view slot observed"
        if case == "high_latitude":
            valid = np.isfinite(self.layers(Recipe())[0]).all(axis=-1) & region & (np.abs(lat) >= 60)
            return bool(valid.any()), f"{valid.sum()} daytime RGB bins at |latitude| >= 60 inside region"
        if case == "multi_angle_coverage":
            anchors = self.anchors()
            counts = []
            masks = []
            for a in (anchors[0], anchors[len(anchors)//2], anchors[-1]):
                mask=np.isfinite(self.layers(Recipe(anchor_angle=a))[1]).all(axis=-1) & region
                masks.append(mask);counts.append(int(mask.sum()))
            common=int(np.logical_and.reduce(masks).sum())
            contrast=int(np.logical_xor(masks[0],masks[-1]).sum())
            return all(c > 0 for c in counts) and common>0 and contrast>0, {"three_anchor_valid_rgb_bins": counts, "common_rgb_bins":common,"contrasting_footprint_bins":contrast}
        return False, "Aligned regional candidate; mixed cloud/ocean/coast qualification requires visual inspection"

    def anchors(self):
        wave = min({c["wavelength"] for c in self.harp.channels}, key=lambda w: abs(w-550))
        return sorted(c["angle"] for c in self.harp.channels if c["wavelength"] == wave)

    def default_recipe(self):
        # Startup display policy only; explicit Recipe/from_dict replay is unchanged.
        recipe=Recipe(preset="beauty")
        recipe.stretch["total"]=[0.,.8,1.6]
        recipe.stretch["polarized"]=[0.,.12,1.4]
        recipe.anchor_angle=min(self.anchors(),key=abs)
        h=self.layers(recipe)[1]
        valid=np.isfinite(h).all(axis=-1)
        rows,cols=np.nonzero(valid)
        if len(rows):
            recipe.crop=[int(rows.min()),int(rows.max()+1),int(cols.min()),int(cols.max()+1)]
            recipe.selected=[int((rows.min()+rows.max())//2),int((cols.min()+cols.max())//2)]
        else:
            recipe.selected=[self.shape[0]//2,self.shape[1]//2]
        return recipe
