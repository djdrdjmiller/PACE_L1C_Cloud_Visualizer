"""Projected source-cell footprints; screen hits never use nearest preview pixels."""
import numpy as np
from pyproj import Transformer, Geod


def corners(a):
    """Linear half-bin edges, with explicit edge extrapolation; no filling holes."""
    if min(a.shape) < 2:
        raise ValueError("Geographic footprints require at least two rows and columns")
    p = np.pad(a.astype(float), 1, mode="edge")
    p[0, 1:-1] = 2*a[0] - a[1]
    p[-1, 1:-1] = 2*a[-1] - a[-2]
    p[:, 0] = 2*p[:, 1] - p[:, 2]
    p[:, -1] = 2*p[:, -2] - p[:, -3]
    return (p[:-1, :-1]+p[1:, :-1]+p[:-1, 1:]+p[1:, 1:])/4


class Grid:
    def __init__(self, product, recipe):
        lat, lon = product.lat, product.lon
        self.center_lon = float(np.rad2deg(np.arctan2(np.nanmean(np.sin(np.deg2rad(lon))), np.nanmean(np.cos(np.deg2rad(lon))))))
        self.center_lat = float(np.nanmedian(lat))
        unwrapped = self.center_lon + (lon-self.center_lon+180) % 360 - 180
        lc,bc=corners(unwrapped),corners(lat)
        try:
            from .native import reconstruct
            if recipe.projection=="native":
                _, _, verified = reconstruct(product)
            else:
                verified=None
        except ValueError as e:
            verified=native_metrics(product)
            verified["rejection_reason"]=str(e)
        r0, r1, c0, c1 = recipe.crop or [0, lat.shape[0], 0, lat.shape[1]]
        self.crop = [r0, r1, c0, c1]
        self.native_evidence = None
        if recipe.projection == "plate_carree":
            x, y = lc, bc
            self.centers = np.stack((unwrapped, lat), axis=-1)
            self.labels = ["Longitude (°; continuous across dateline)", "Latitude (°)"]
        elif recipe.projection == "laea":
            proj = f"+proj=laea +lat_0={self.center_lat} +lon_0={self.center_lon} +datum=WGS84 +units=m"
            self.transformer = Transformer.from_crs("EPSG:4326", proj, always_xy=True)
            x, y = self.transformer.transform(lc, bc)
            cx, cy = self.transformer.transform(lon, lat)
            x, y = np.asarray(x)/1000, np.asarray(y)/1000
            self.centers = np.stack((np.asarray(cx)/1000, np.asarray(cy)/1000), axis=-1)
            self.labels = ["Regional equal-area easting (km)", "Northing (km)"]
        else:
            # Native physical grid with geolocation contours. Label conservatively until
            # the orbit-dependent NASA SOCEA transform is independently reconstructed.
            x, y = np.meshgrid((np.arange(lat.shape[1]+1)-.5)*5.2, (np.arange(lat.shape[0]+1)-.5)*5.2)
            cx, cy = np.meshgrid(np.arange(lat.shape[1])*5.2, np.arange(lat.shape[0])*5.2)
            self.centers = np.stack((cx, cy), axis=-1)
            self.labels = ["Original across-track distance (nominal km)", "Original along-track distance (nominal km)"]
            self.native_evidence = verified
        self.xcorners, self.ycorners = x, y
        vertices = np.stack((np.stack((x[:-1,:-1], y[:-1,:-1]), -1),
                             np.stack((x[:-1,1:], y[:-1,1:]), -1),
                             np.stack((x[1:,1:], y[1:,1:]), -1),
                             np.stack((x[1:,:-1], y[1:,:-1]), -1)), axis=-2)
        lengths = np.linalg.norm(vertices-np.roll(vertices, 1, axis=-2), axis=-1)
        typical = np.nanmedian(lengths)
        # Reject disconnected/invalid projected cells, including seam-spanning edges.
        self.valid = np.isfinite(vertices).all(axis=(-2,-1)) & (lengths.max(axis=-1) < 4*typical)
        self.vertices = vertices[r0:r1, c0:c1]
        self.valid = self.valid[r0:r1, c0:c1]
        self.ids = np.arange(lat.size).reshape(lat.shape)[r0:r1,c0:c1]
        good = self.vertices[self.valid]
        if not len(good):
            raise ValueError("Crop contains no valid projected source cells")
        self.bounds = [float(good[...,0].min()), float(good[...,0].max()), float(good[...,1].min()), float(good[...,1].max())]
        self.lat, self.lon = lat, unwrapped

    def screen(self, points, width, height):
        xmin, xmax, ymin, ymax = self.bounds
        p = np.asarray(points).copy()
        p[...,0] = (p[...,0]-xmin)/(xmax-xmin)*(width-1)
        p[...,1] = (ymax-p[...,1])/(ymax-ymin)*(height-1)
        return p


def native_metrics(product):
    geod = Geod(ellps="WGS84")
    lon, lat = product.lon, product.lat
    _, _, across = geod.inv(lon[:,:-1], lat[:,:-1], lon[:,1:], lat[:,1:])
    _, _, along = geod.inv(lon[:-1], lat[:-1], lon[1:], lat[1:])
    return {"label": "native source swath (SOCEA reconstruction unverified)",
            "across_spacing_median_m": float(np.nanmedian(across)),
            "along_spacing_median_m": float(np.nanmedian(along)),
            "geolocation_contours": True, "official_transform_verified": False}
