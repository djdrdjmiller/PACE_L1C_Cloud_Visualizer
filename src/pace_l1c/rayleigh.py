"""Experimental monochromatic single-scattering molecular path reflectance.

Bates/Bodhaine dry-air molecular anisotropy in both cross section and phase matrix.
Plane-parallel
layer, unpolarized incident Sun, no surface/cloud coupling or multiple scattering.
Returns path removal, not a retrieved surface/cloud reflectance.
"""
import numpy as np
from .science import rotate,dolp

MODEL={
    'name':'analytical single-scattering Rayleigh path removal',
    'version':'dry-air-bates-bodhaine-2026-10-26',
    'optical_depth':'Bodhaine 1999 eqs 18,22–25: sigma_R*N_A*pressure/(molar_mass*g); same King factor as phase matrix',
    'reference':'https://doi.org/10.1175/1520-0426(1999)016<1854:ORODC>2.0.CO;2',
    'phase_reference':'https://gmd.copernicus.org/articles/19/9677/2026/#section6',
    'king_reference':'https://doi.org/10.1016/0032-0633(84)90102-8',
    'king_factor':'Bates N2/O2 wavelength functions, Ar=1 and CO2=1.15; Bodhaine eq.23 normalized 78.084:20.946:0.934:0.030 mixture',
    'phase_matrix':'rho=6*(F_K-1)/(7*F_K+3); Delta=(1-rho)/(1+rho/2); P11=3/4*Delta*(1+cos²theta)+1-Delta; P21=-3/4*Delta*sin²theta; U_scattering=0',
    'dry_air':{'co2_ppm':300,'number_density_m-3':2.546899e25,'reference_temperature_K':288.15,'reference_pressure_hPa':1013.25,'molar_mass_kg_mol':.02896401668,'gravity_m_s-2':9.80665,'avogadro_mol-1':6.02214076e23},
    'spectral_support':'350–2500 nm; Peck–Reeder refractivity extrapolated beyond its 1690 nm data range; SWIR accuracy unverified',
    'assumptions':'plane parallel; unpolarized sunlight; monochromatic centers; fixed standard dry-air composition and gravity; molecular anisotropy included; multiple scattering neglected; no aerosol, gas attenuation of molecular path, or surface/cloud coupling',
    'normalization':'I uses intensity F0; modeled Q/U converted to polarization F0 by intensity_f0/polarization_f0',
    'polarimetry':'molecular components subtracted only; no OCI transmission LUT applied to Q/U; DoLP uses consistently molecular-subtracted I/Q/U in radiance units',
}


def _wavelength_um(wavelength_nm):
    wave=np.asarray(wavelength_nm,float)/1000
    if np.any(~np.isfinite(wave)) or np.any((wave<.35)|(wave>2.5)):
        raise ValueError('Experimental Rayleigh model supports band centers 350–2500 nm')
    return wave


def king_factor(wavelength_nm):
    """Dry air, 300 ppm CO2; Bates factors and Bodhaine eq. 23 (um)."""
    wave=_wavelength_um(wavelength_nm)
    nitrogen=1.034+3.17e-4/wave**2
    oxygen=1.096+1.385e-3/wave**2+1.448e-4/wave**4
    return (78.084*nitrogen+20.946*oxygen+.934+.030*1.15)/(78.084+20.946+.934+.030)


def depolarization_ratio(wavelength_nm):
    """Natural-light molecular depolarization rho, not multiple scattering."""
    king=king_factor(wavelength_nm)
    return 6*(king-1)/(7*king+3)


def phase_elements(wavelength_nm,scattering_angle):
    """First-column P11/P21 for unpolarized sunlight; sphere-mean P11=1."""
    rho=depolarization_ratio(wavelength_nm)
    delta=(1-rho)/(1+rho/2)
    theta=np.deg2rad(scattering_angle)
    return .75*delta*(1+np.cos(theta)**2)+1-delta,-.75*delta*np.sin(theta)**2


def scattering_cross_section(wavelength_nm):
    """m² per molecule; refractivity and density share 288.15 K/1013.25 hPa.

    Bodhaine eq. 18 uses the Peck–Reeder three-term expression for 300 ppm
    CO2. Beyond 1690 nm this retains the prior API domain as an explicitly
    unverified extrapolation, not a new spectroscopic accuracy claim.
    """
    wave=_wavelength_um(wavelength_nm)
    n=1+1e-8*(8060.51+2480990/(132.274-wave**-2)+17455.7/(39.32957-wave**-2))
    return 24*np.pi**3/((wave*1e-6)**4*MODEL['dry_air']['number_density_m-3']**2)*((n*n-1)/(n*n+2))**2*king_factor(wavelength_nm)


def optical_depth(wavelength_nm,pressure_hpa):
    """Hydrostatic pressure column; pressure support/boundaries unchanged."""
    p=np.asarray(pressure_hpa,float)
    air=MODEL['dry_air']
    tau=scattering_cross_section(wavelength_nm)*air['avogadro_mol-1']*p*100/(air['molar_mass_kg_mol']*air['gravity_m_s-2'])
    return np.where(np.isfinite(p)&(p>0)&(p<=1050),tau,np.nan)


def path_reflectance(wavelength_nm,pressure_hpa,solar_zenith,sensor_zenith,scattering_angle):
    tau=optical_depth(wavelength_nm,pressure_hpa)
    mu0=np.cos(np.deg2rad(solar_zenith));mu=np.cos(np.deg2rad(sensor_zenith))
    p11,p21=phase_elements(wavelength_nm,scattering_angle)
    with np.errstate(invalid='ignore',divide='ignore',over='ignore'):
        c=-np.expm1(-tau*(1/mu0+1/mu))/(4*(mu0+mu))
    valid=(np.asarray(solar_zenith)>=0)&(np.asarray(solar_zenith)<90)&(np.asarray(sensor_zenith)>=0)&(np.asarray(sensor_zenith)<90)&(np.asarray(scattering_angle)>=0)&(np.asarray(scattering_angle)<=180)
    i=np.where(valid,c*p11,np.nan)
    q=np.where(valid,c*p21,np.nan)
    return i,q,np.zeros_like(q)


def subtract(product,channel,pressure,row=None,col=None,raw=None):
    """Independent corrected fields. Never alter product or fitting observations."""
    raw=product.values(channel,row,col) if raw is None else raw
    ir,qr,ur=path_reflectance(channel['wavelength'],pressure,
        product.read('solar_zenith_angle',channel,row,col),
        product.read('sensor_zenith_angle',channel,row,col),
        product.read('scattering_angle',channel,row,col))
    out={'total':raw['total']-ir,'molecular_total':ir}
    if product.instrument=='HARP2':
        f0=product.read('intensity_f0',channel,row,col);pf0=product.read('polarization_f0',channel,row,col)
        with np.errstate(invalid='ignore',divide='ignore'):ratio=np.where((f0>0)&(pf0>0),f0/pf0,np.nan)
        angle=product.read('rotation_angle',channel,row,col)
        qm,um=rotate(qr*ratio,ur*ratio,-angle)  # inverse of meridional -> scattering
        q=raw['q']-qm;u=raw['u']-um
        qs,us=rotate(q,u,angle)
        out.update(q=q,u=u,q_scattering=qs,u_scattering=us,signed_q=-qs,signed_u=-us,
                   polarized=np.hypot(q,u),dolp=dolp(out['total'],q/ratio,u/ratio),
                   molecular_q=qm,molecular_u=um)
    return out
