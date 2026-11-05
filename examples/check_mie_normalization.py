"""Independent spherical-Mie/gamma-DSD normalization check, not a retrieval.

Compares the smallest re/ve red-band table point using declared refractive index.
A gamma number distribution is an explicit audit hypothesis, not a metadata claim
about how the source LUT was generated. Small residual differences remain.
Uses SciPy Bessel functions, standard Mie amplitudes, and 4*pi*dSigma/Csca.
No supplied reference scripts are imported or executed. Run from repository root:
  .venv-clean/bin/python examples/check_mie_normalization.py PATH_TO_LUT
This is a one-point normalization/sign sanity check, not full LUT validation.
"""
import numpy as np,xarray as xr
from scipy.special import spherical_jn,spherical_yn,gammaln
from scipy.integrate import trapezoid
import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('lut',help='Local MiedBase file; never downloaded or modified')
args=parser.parse_args()
x=xr.open_dataset(args.lut);w=int(np.argmin(abs(x.wavelength.values-.6646)));re=float(x.reff[0]);v=float(x.veff[0]);wave=float(x.wavelength[w]);m=complex(x.real_index[w],x.imag_index[w]);k=2*np.pi/wave
r=np.linspace(re*.65,re*1.35,1201);shape=1/v-2;scale=re*v
pdf=np.exp((shape-1)*np.log(r)-r/scale-gammaln(shape)-shape*np.log(scale));pdf/=trapezoid(pdf,r)
angles=np.array([140.,150.,180.]);mu=np.cos(np.deg2rad(angles));csc=[];p11=[];p21=[]
for radius in r:
 z=k*radius;n=np.arange(1,int(z+4*z**(1/3)+3)+1)
 j=spherical_jn(n,z);dj=spherical_jn(n,z,True);y=spherical_yn(n,z);dy=spherical_yn(n,z,True)
 psi=z*j;dpsi=j+z*dj;xi=z*(j+1j*y);dxi=j+1j*y+z*(dj+1j*dy)
 jm=spherical_jn(n,m*z);djm=spherical_jn(n,m*z,True);psim=m*z*jm;dpsim=jm+m*z*djm
 a=(m*psim*dpsi-psi*dpsim)/(m*psim*dxi-xi*dpsim);b=(psim*dpsi-m*psi*dpsim)/(psim*dxi-m*xi*dpsim)
 csc.append(2*np.pi/k**2*np.sum((2*n+1)*(abs(a)**2+abs(b)**2)))
 s1=np.zeros(3,complex);s2=s1.copy();prev=np.zeros(3);pn=np.ones(3)
 for idx,nn in enumerate(n):
  tn=nn*mu*pn-(nn+1)*prev;f=(2*nn+1)/(nn*(nn+1));s1+=f*(a[idx]*pn+b[idx]*tn);s2+=f*(a[idx]*tn+b[idx]*pn)
  nxt=((2*nn+1)*mu*pn-(nn+1)*prev)/nn;prev,pn=pn,nxt
 p11.append((abs(s2)**2+abs(s1)**2)/(2*k*k));p21.append((abs(s2)**2-abs(s1)**2)/(2*k*k))
c=trapezoid(pdf*np.array(csc),r)
phase11=4*np.pi*trapezoid(pdf[:,None]*p11,r,axis=0)/c
phase21=4*np.pi*trapezoid(pdf[:,None]*p21,r,axis=0)/c
native=x.p21.isel(spectral_bands=w,effective_radii=0,effective_variance=0).values
print('Csca independent/LUT',c,float(x.csca[0,0,w]))
print('dimensionless P11(180), LUT p180',phase11[-1],float(x.p180[0,0,w]))
print('dimensionless P21',phase21,'LUT',np.interp(angles,x.scattering_angle,native))
print('LUT / independent dimensionless P21',np.interp(angles[:2],x.scattering_angle,native)/phase21[:2])
