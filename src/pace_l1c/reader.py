"""Lazy grouped NetCDF adapters retaining original spatial/view indices."""
from pathlib import Path
import hashlib
import numpy as np
import xarray as xr
from .science import reflectance, rotate, dolp, branches

ROW, COL, VIEW = "bins_along_track", "bins_across_track", "number_of_views"
IB, PB = "intensity_bands_per_view", "polarization_bands_per_view"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8 * 1024**2), b""):
            h.update(block)
    return h.hexdigest()


def jsonable(value):
    if isinstance(value, np.ndarray) and value.ndim == 0:
        return jsonable(value.item())
    if isinstance(value, dict):
        return {jsonable(str(k)): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [jsonable(v) for v in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, str):
        # h5netcdf may expose raw UTF-8 attribute bytes as surrogate escapes.
        # Recover valid text; preserve genuinely invalid bytes as visible escapes.
        try:
            return value.encode('utf8', 'surrogateescape').decode('utf8', 'backslashreplace')
        except UnicodeEncodeError:
            return value.encode('utf8', 'backslashreplace').decode('utf8')
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


class Product:
    def __init__(self, path):
        self.path = Path(path)
        self.groups = {}
        try:
            for group in (None, "sensor_views_bands", "geolocation_data", "observation_data", "bin_attributes"):
                try:
                    self.groups[group] = xr.open_dataset(path, group=group, engine="h5netcdf", mask_and_scale=True)
                except (OSError, ValueError):
                    if group != "bin_attributes":
                        raise
            self.attrs = dict(self.groups[None].attrs)
            self.sensor = self.groups["sensor_views_bands"]
            self.geo = self.groups["geolocation_data"]
            self.obs = self.groups["observation_data"]
            self.instrument = str(self.attrs.get("instrument", "")).upper()
            if self.instrument not in ("OCI", "HARP2") or str(self.attrs.get("processing_level", "")) != "L1C":
                raise ValueError("Expected an OCI or HARP2 L1C product")
            if self.instrument=="HARP2" and self.attrs.get("stokes_reference_plane", "View meridian").lower() not in ("view meridian","meridional","view meridional plane"):
                raise ValueError("Unsupported Stokes reference plane; scattering rotation requires view meridian")
            self.distance = float(self.attrs["sun_earth_distance"])
            self.lat = self.geo.latitude.transpose(ROW, COL).values
            self.lon = self.geo.longitude.transpose(ROW, COL).values
            self.shape = self.lat.shape
            self.channels = self._channels()
            self.identity = {"product_name": self.attrs.get("product_name", self.path.name),
                             "sha256": sha256(path), "processing_version": self.attrs.get("processing_version"),
                             "grid_source": self.attrs.get("l1cgrid_source"),
                             "time_start": self.attrs.get("time_coverage_start"), "time_end": self.attrs.get("time_coverage_end")}
        except Exception:
            self.close()
            raise

    def close(self):
        for group in self.groups.values():
            group.close()

    def _channels(self):
        w = self.sensor["intensity_wavelength"]
        units = str(w.attrs.get("units", "")).lower()
        if units not in ("nm", "nanometers", "nanometer", "um", "µm", "micrometers", "micrometer"):
            raise ValueError(f"Unsupported wavelength units {units!r}")
        factor = 1000 if units in ("um", "µm", "micrometers", "micrometer") else 1
        result = []
        for view in range(self.obs.sizes[VIEW]):
            wave = w.isel({VIEW: view}) if VIEW in w.dims else w
            for band, nm in enumerate(np.atleast_1d(wave.values).ravel() * factor):
                angles=self.sensor.sensor_view_angle
                if angles.dims==(ROW,) and self.instrument=='OCI' and self.obs.sizes[VIEW]==1:
                    # Newer OCI files retain one observation slot and an actual
                    # along-track tilt profile. There is no global sector angle.
                    if angles.sizes[ROW]!=self.shape[0]:raise ValueError('OCI along-track tilt does not match source rows')
                    angle=None
                    source='sensor_view_angle[bins_along_track]; inspect selected source row'
                elif VIEW in angles.dims and angles.size==self.obs.sizes[VIEW]:
                    angle=float(np.asarray(angles.isel({VIEW:view}).values).ravel()[0])
                    source='sensor_view_angle[number_of_views]'
                else:
                    raise ValueError('Unsupported sensor_view_angle dimensions; source correspondence cannot be established')
                result.append({"view":view,"band":band,"wavelength":float(nm),"angle":angle,"angle_source":source})
        return result

    def read(self, name, channel=None, row=None, col=None):
        ds = self.obs if name in self.obs else self.geo if name in self.geo else self.sensor
        if name not in ds:
            raise ValueError(f"Missing required field {name} in {self.path.name}")
        a = ds[name]
        index = {}
        if channel is not None:
            if VIEW in a.dims:
                index[VIEW] = channel["view"]
            for dim in (IB, PB):
                if dim in a.dims:
                    index[dim] = channel["band"] if self.instrument == "OCI" else 0
        if row is not None and ROW in a.dims:
            index[ROW] = row
        if col is not None and COL in a.dims:
            index[COL] = col
        a = a.isel(index)
        # Drop only explicitly known singleton spectral axes, never spatial axes.
        for dim in (IB, PB):
            if dim in a.dims and a.sizes[dim] == 1 and self.instrument == "HARP2":
                a = a.isel({dim: 0})
        dims = [d for d in (ROW, COL, VIEW, IB, PB) if d in a.dims]
        if set(dims) != set(a.dims):
            raise ValueError(f"Unsupported dimensions for {name}: {a.dims}")
        return a.transpose(*dims).values

    def values(self, channel, row=None, col=None):
        i = self.read("i", channel, row, col)
        count = self.read("number_of_observations", channel, row, col)
        i = np.where(count > 0, i, np.nan)
        sza = self.read("solar_zenith_angle", channel, row, col)
        f0 = self.read("intensity_f0", channel)
        result = {"radiance": i, "total": reflectance(i, f0, sza, self.distance)}
        if self.instrument == "HARP2":
            q = np.where(count > 0, self.read("q", channel, row, col), np.nan)
            u = np.where(count > 0, self.read("u", channel, row, col), np.nan)
            pf0 = self.read("polarization_f0", channel)
            rq, ru = reflectance(q, pf0, sza, self.distance), reflectance(u, pf0, sza, self.distance)
            qs, us = rotate(rq, ru, self.read("rotation_angle", channel, row, col))
            result.update(q=rq, u=ru, q_scattering=qs, u_scattering=us,
                          signed_q=-qs, signed_u=-us, polarized=np.hypot(rq, ru), dolp=dolp(i, q, u))
        return result

    def oci_band(self, band, quantity="total", row=None, col=None):
        channels = [c for c in self.channels if c["band"] == band]
        values = [self.values(c, row, col)[quantity] for c in channels]
        stack = np.stack(values)
        valid = np.isfinite(stack)
        # Ambiguous multiple observations are never averaged or silently chosen.
        return np.where(valid.sum(axis=0) == 1, np.nansum(stack, axis=0), np.nan)

    def inventory(self):
        return jsonable({"identity": self.identity, "instrument": self.instrument, "shape": self.shape,
                         "channels": self.channels, "attributes": self.attrs,
                         "storage": {g or "root": {n: {"dims": a.dims, "shape": a.shape,
                            "units": a.attrs.get("units"), "chunks": a.encoding.get("chunksizes")}
                            for n, a in ds.variables.items()} for g, ds in self.groups.items()}})

    def diagnostics(self, row, col):
        if not (0 <= row < self.shape[0] and 0 <= col < self.shape[1]):
            raise ValueError("Source bin outside granule")
        if self.instrument == "OCI":
            counts = self.read("number_of_observations", row=row, col=col)
            valid = np.flatnonzero(np.isfinite(counts) & (counts > 0))
            view = int(valid[0]) if len(valid) == 1 else 0
            channels = [c for c in self.channels if c["view"] == view]
            i = self.read("i", row=row, col=col)
            f0 = self.read("intensity_f0")
            sza = self.read("solar_zenith_angle", row=row, col=col)
            refl = reflectance(i, f0, np.asarray(sza)[...,None], self.distance)
            chosen = i[view] if len(valid)==1 else np.full(len(channels), np.nan)
            chosen_refl = refl[view] if len(valid)==1 else np.full(len(channels), np.nan)
            result={"wavelength": [c["wavelength"] for c in channels],
                    "total": chosen_refl, "radiance": chosen, "valid_source_views": valid,
                    "view_status": "single observation" if len(valid)==1 else "missing or ambiguous view slots"}
            if self.sensor.sensor_view_angle.dims==(ROW,):
                result['sensor_view_angle_deg']=self.read('sensor_view_angle',row=row)
                result['sensor_view_angle_source']='original along-track row; not a global nominal sector'
            for name in ('qc','i_stdev'):
                if name in self.obs:
                    a=self.read(name,row=row,col=col)
                    result['product_'+name]=a[view] if len(valid)==1 else np.full(len(channels),np.nan)
            return result
        fields = {}
        for name in ("i", "q", "u", "number_of_observations", "solar_zenith_angle", "solar_azimuth_angle", "sensor_azimuth_angle", "rotation_angle", "scattering_angle", "sensor_zenith_angle", "qc", "i_stdev", "q_stdev", "u_stdev", "dolp"):
            if name in self.obs or name in self.geo:
                fields[name] = self.read(name, row=row, col=col)
        i,q,u = [np.where(fields["number_of_observations"]>0,fields[n],np.nan) for n in ("i","q","u")]
        rq = reflectance(q,self.read("polarization_f0"),fields["solar_zenith_angle"],self.distance)
        ru = reflectance(u,self.read("polarization_f0"),fields["solar_zenith_angle"],self.distance)
        qs,us = rotate(rq,ru,fields["rotation_angle"])
        values = {"radiance":i,"total":reflectance(i,self.read("intensity_f0"),fields["solar_zenith_angle"],self.distance),
                  "q":rq,"u":ru,"q_scattering":qs,"u_scattering":us,"signed_q":-qs,"signed_u":-us,"polarized":np.hypot(rq,ru),"dolp":dolp(i,q,u)}
        samples = []
        for c in self.channels:
            sample = dict(c, **{n:a[c["view"]] for n,a in values.items()})
            for name in ("scattering_angle", "sensor_zenith_angle", "solar_zenith_angle", "rotation_angle"):
                sample[name] = fields[name][c["view"]]
            for name in ("solar_azimuth_angle","sensor_azimuth_angle","number_of_observations"):
                if name in fields:
                    sample[name]=fields[name][c["view"]]
            for name in ("qc", "i_stdev", "q_stdev", "u_stdev", "dolp"):
                if name in self.obs:
                    sample["product_"+name] = fields[name][c["view"]]
            samples.append(sample)
        for wave in sorted(set(c["wavelength"] for c in self.channels)):
            subset = [s for s in samples if s["wavelength"] == wave]
            labels = branches([s["scattering_angle"] for s in subset], [s["angle"] for s in subset])
            for s, branch in zip(subset, labels):
                s["branch"] = int(branch)
        counts={w:sum(c['wavelength']==w for c in self.channels) for w in {c['wavelength'] for c in self.channels}}
        hyper=max(counts,key=lambda w:(counts[w],-abs(w-665)))
        return {"samples": samples, "hyperangular_wavelength":hyper,
                "branch_policy": "exploratory source-view turning point; nominal-descending fallback for shuffled metadata",
                "signed_convention": "negative of canonical scattering-plane reflectance"}
