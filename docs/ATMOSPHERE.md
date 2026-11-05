# Experimental correction of quicklook imagery

Current policy, 2026-10-19: atmospheric-model research remains parked. The surface-transmission extension is retired. Rayleigh-only cache preparation/loading is now independent of transmission tables, water columns, PROFILE humidity and pyhdf. Legacy transmission code/preparation remains available only with a combined cache; both new delivery variants can use the independent Rayleigh path.

The user authorized total-reflectance transmission correction on 2026-10-14 and a bounded neighborhood estimate for missing cloud retrievals. This is an optional **approximation for visualization**, not an operational atmospheric-correction product. It does not complete the outstanding release-1 dateline/high-latitude acceptance tests.

## Implemented correction

The single **Atmospheric Correction** dropdown offers **Uncorrected TOA** or **Rayleigh · experimental**, applying to OCI/HARP2 total and HARP2 polarized imagery together. Rayleigh writes `correction=rayleigh`, `polar_rayleigh=true` and `rayleigh_land=true`; TOA writes TOA/false. Molecular Q/U removal affects the third map before forming magnitude/DoLP. Saved/imported independent Rayleigh settings become the shared Rayleigh option when available. Transmission controls are absent from the dashboard; legacy independent/transmission recipes remain supported through the Python/API, with explicit rejection when cache capability is absent. Rayleigh corrects classified land and water. Unclassified surface bins retain original TOA. Unsupported classified corrections remain missing; they are never silently replaced by TOA. The selected-bin spectrum, multiangular observations and cloudbow fit remain source TOA and are labeled accordingly; corrected map values are separately exposed in render/export provenance. Scientific values are never clipped before display enhancement. Unsupported correction over classified land or water remains transparent.

The **Middle map** selector can show either HARP2 total reflectance or **OCI cloud phase**. The latter displays the native OCI L2 `cld_phase_21` (2.1 µm retrieval) at the same audited nearest-center/time matches: no mask, clear, liquid, ice, and unknown cloud (assumed water by the source product). Missing phase is transparent. This is native L2 collocated to L1C centers, not an original L1C measurement or an imputed/averaged phase product. It preserves original-bin selection and recipe replay. HARP2 scattering-angle contours are omitted from this OCI map.

The supplied HDF4 table uses nearest 100–1000 hPa pressure, with halfway pressures rounded toward larger pressure, and bilinear interpolation on the actual effective-cosine and nonuniform water coordinates. Effective cosine is `mu0*mu/(mu0+mu)` using actual per-bin/view solar and sensor zenith angles. Only contributing interpolation corners need finite positive transmission ≤1 and positive support counts. Unsupported corners, missing geometry and missing observations are rejected. Current validated recipes bound transmission pressure to 100–1000 hPa; the retired clear-water extension is recorded below for history. Counts and standard deviations are retained in the prepared cache.

Visible imagery (400–700 nm) uses the documented temporary 0.64 µm proxy for every RGB channel. This does **not** model the wavelength dependence of molecular scattering. OCI additionally supports measured centers within 12 nm of 865/940/1615/2130/2260 nm at fixed table indices 1/2/5/6/7. Other channels reject rather than use an invented mapping. HARP2 correction currently supports visible channels; its NIR mapping remains unverified. Unsupported false-color settings should be used with the TOA mode.

## Classified land and water: current production policy

After reviewing the [offline land trial](LAND_RAYLEIGH_TRIAL.md), the user approved the same land-enabled calculation for production. Rayleigh subtracts the existing molecular I/Q/U term over both classified land and water. It uses exactly the existing cached OCI cloud-top boundary for cloudy bins or interpolated MERRA-2 MET surface pressure for clear bins, including the already documented fallback states. No terrain correction, pressure model, new data source, humidity/transmission or additional gap filling was added. Components are subtracted before magnitude/DoLP; spectra and all fitting/model-comparison diagnostics stay TOA.

Unclassified surface bins retain original TOA. Unsupported land/water pressure, geometry or observations remain missing and appear transparent, including the trial's 30 OCI land gaps. Never silently substitute TOA for an unsupported classified correction. The old land bypass was a user policy inherited from transmission trouble, not a physical restriction; it is no longer the current dashboard policy.

The shared dropdown always enables land for Rayleigh (`rayleigh_land=true`), including startup and imported recipes. New library recipes also default true. For compatibility, `Recipe.from_dict` sets false on older saved Rayleigh/polar-Rayleigh recipes that omit this field; Python/API/export can explicitly retain false. Raw API requests lacking the field follow that same old-recipe rule. To migrate an older saved recipe intentionally, set true and create a new export. Do not claim its scientific land arrays match the earlier water-only export.

Legacy transmission-only remains water-only. In legacy combined Rayleigh+transmission mode, land receives molecular subtraction only, while water can use the table; no transmission factor is applied to land. Independent total/polar flags remain available through Python/API, and exports label actual land total/polar behavior separately. `rayleigh_land_policy` and correction coverage (`water_corrected_bins`, `land_corrected_bins`, `land_toa_bins`, `unknown_toa_bins`) make scope explicit. Cache/source identity and the land policy are separate: caches hold the same physical boundaries, recipes select application. Historical cache land-policy strings describe the old stage, not current correction behavior; new preparation/extraction stores classification-only language.

The model remains experimental: coarse MET pressure is not adjusted to L1C height, and single scattering omits reflected-signal attenuation, surface/atmosphere coupling, aerosols and multiple scattering. These limits apply to land, bright clouds and glint. The land trial establishes scene-specific plausibility/coverage, not independent surface-reflectance or polarization accuracy. Any new terrain-pressure/model assumptions still require discussion. Established land processing can use elevation-adjusted pressure, e.g. [NASA HLS/LaSRC](https://hls.gsfc.nasa.gov/algorithms/), but no such additional model is introduced here.

## Cloud and surface boundary

OCI L2 CLD uses a different, finer sampling than L1C. Each original L1C bin uses the nearest of eight native centers satisfying both **3 km** and **10 seconds**. Actual OCI observation time is nadir time **minus** view offset; this convention was checked in NASA's L1C writer. Adjacent native CLD files are needed near tilted-view granule edges. Native source-product/index, distance and time difference are cached. This is center-point collocation, not footprint averaging or a cloud-parallax correction.

Phase codes are checked against file descriptions: 1 is clear, 2/3 cloud, and 4 assumes cloud of unknown phase. Finite cloud-top pressure supplies the direct cloudy boundary. Clear pixels use spatial/time-interpolated **MET PS** and a measured **QV10M** humidity endpoint. This surface is the coarse meteorological model surface, not a fine-scale adjustment to L1C terrain height.

Missing cloud-top pressure can use the median of at least three valid cloudy pressures in a noniteratively evaluated 7×7-bin neighborhood, when cloudy classifications outnumber clear classifications by at least 2:1. Unclassified pixels can use the surface when clear classifications have the corresponding majority. A known cloudy pixel is never changed to clear. Sparse/mixed neighborhoods remain unavailable. Direct cloud, direct clear, estimated cloud, estimated clear and unavailable have separate state codes in the inspector/cache/export provenance. Approximately 15.6 km axial neighborhood radius is a visualization choice, not a validated retrieval interpolation length.

Humidity is sampled bilinearly on periodic-longitude meteorological grids, then linearly in time without temporal extrapolation. PROFILE QV converts to g/kg mixing ratio and interpolates in log pressure to NASA's 101-level grid. Cloud-column water uses its trapezoidal pressure integral divided by 980.616 and upper-profile floor of 0.003 g/kg. Cloud calculations needing surface-level repairs are rejected. Clear integration uses valid above-ground profile levels plus the measured QV10M endpoint at PS; no below-ground humidity or downward extrapolation is used. This clear-surface extension is an explicit approximation and is not a complete reproduction of the operational surface-repair algorithm.

HARP2 shares the OCI-time collocated cloud/surface column; transmission is evaluated independently using each selected HARP2 view's zenith angles. Atmospheric evolution between the OCI and HARP2 observation times is not resolved. Source polarimetric fields/diagnostics stay TOA; the separately named Rayleigh map fields can be molecular-subtracted.

## Rayleigh setup without a transmission table

No HDF4/pyhdf, transmission values, water column, PROFILE QV or MET QV10M is used. Preparation reads only declared MERRA-2 **MET PS**, native OCI CLD pressure/phase/LAND, source times/geolocation and the existing unchanged boundary fallback. Cloud acquisition and MET interpolation retain their budgets and time/space bounds.

For the existing scene, extract audited arrays without recomputing or downloading:

```bash
pace-l1c atmosphere-extract-rayleigh \
  --atmosphere data/atmosphere/scene-rayleigh.nc \
  --output data/atmosphere/scene-rayleigh-land.nc

pace-l1c serve --manifest data/manifests/development.json --case science_scene \
  --mie data/reference/MiedBaseE4_Parm_HARP2_LR.nc \
  --atmosphere data/atmosphere/scene-rayleigh-land.nc
```

The current active cache `scene-rayleigh-land.nc` is an unchanged-array extraction of `scene-rayleigh-only.nc`, with classification-only provenance. It can be produced by the same extraction command with those input/output names; both boundary caches support land-enabled recipes. No new acquisition is needed.

The extraction refuses an existing/same output path and preserves the original cache. It copies only boundary pressure/state, surface class, optional OCI phase and collocation indices/distance/time; provenance records original source hashes and parent-cache hash. It does not copy humidity/transmission arrays. The local Mie option remains solely for cloudbow/RFT and can be omitted when those overlays are not needed.

For new scenes, set `CLOUD0`/`CLOUD1` to the matching/adjacent local OCI CLD files:

```bash
pace-l1c atmosphere-acquire --cloud "$CLOUD0" --kind met --budget-mib 512
pace-l1c atmosphere-acquire --cloud "$CLOUD1" --kind met --budget-mib 512
pace-l1c atmosphere-prepare --mode rayleigh \
  --manifest data/manifests/development.json --case science_scene \
  --cloud "$CLOUD0" "$CLOUD1" --ancillary data/atmosphere/ancillary \
  --output data/atmosphere/scene-rayleigh-prepared.nc
```

Omitting both `--mode` and `--lut` selects Rayleigh preparation. Supplying `--lut` without `--mode` preserves legacy transmission preparation; explicit `--mode rayleigh --lut ...` is rejected. `atmosphere-acquire --kind met` filters declared MET files, reuses verified entries and never logs in for a complete verified cache; default `--kind all` preserves legacy ancillary acquisition.

New caches carry `cache_schema_version=1` and `cache_kind=rayleigh_boundary` (or `transmission_boundary` for new combined caches). Loader checks source hashes/identity, spatial dimensions, hPa units, state/classification codes and declared schema. Rayleigh-only caches reject embedded water/transmission variables. Old unversioned combined caches remain supported, without changing old export provenance. `/api/scene` reports separate `correction_capabilities.rayleigh` and `.transmission`; frontend startup and recipe restores disable unavailable Rayleigh and synchronize total/polar choices. Selected-bin water column is null when absent, and Rayleigh-only export provenance has no transmission mapping.

Cache content/identity changes create a new provenance hash. Old exports tied to the combined cache intentionally reject replay against the new file: use the preserved old cache for exact old-provenance replay or create a new Rayleigh-only export. Scientific equality does not imply identical JSON/PDF hashes across different cache identities.

## Legacy transmission setup and commands

HDF4 reading is needed only during preparation; serving/exporting the prepared NetCDF needs the standard environment. Install `pyhdf==0.11.7` (optional `.[atmosphere]` extra). A wheel was verified with Python 3.14 on this machine. If a platform has no wheel, use conda-forge's pyhdf/HDF4 runtime; do not assume a pip source build has the native HDF4 headers.

Supply local cloud paths without committing them. `CLOUD0` and `CLOUD1` below denote the matching and adjacent OCI CLD files, and `TRANSMISSION_LUT` the supplied HDF4 table.

```bash
# Discover cloud files across actual OCI observation times; maximum three.
# Existing explicitly supplied CLD can be reused without downloading it.
pace-l1c atmosphere-clouds --manifest data/manifests/development.json \
  --case science_scene --local-cloud "$CLOUD0" --budget-mib 256

# Read each cloud product's exact ancillary input filenames; bounded new bytes.
pace-l1c atmosphere-acquire --cloud "$CLOUD0" --budget-mib 512
pace-l1c atmosphere-acquire --cloud "$CLOUD1" --budget-mib 512

# Build a reusable original-bin cache. No atmospheric calculation in the browser.
pace-l1c atmosphere-prepare --manifest data/manifests/development.json \
  --case science_scene --cloud "$CLOUD0" "$CLOUD1" \
  --lut "$TRANSMISSION_LUT" --output data/atmosphere/scene.nc

# Enrich an existing cache without recomputing atmospheric columns.
# Normal atmosphere-prepare now includes LAND and OCI phase automatically.
pace-l1c atmosphere-landmask --atmosphere data/atmosphere/scene.nc \
  --cloud "$CLOUD0" "$CLOUD1" --output data/atmosphere/scene-rayleigh.nc

pace-l1c serve --manifest data/manifests/development.json --case science_scene \
  --mie data/reference/MiedBaseE4_Parm_HARP2_LR.nc \
  --atmosphere data/atmosphere/scene-rayleigh.nc

pace-l1c export --manifest data/manifests/development.json --case science_scene \
  --atmosphere data/atmosphere/scene-rayleigh.nc \
  --recipe outputs/transmission-corrected.json --output outputs/replayed
```

Cloud and ancillary transfers have independent, persistent budgets (256 and 512 MiB by default); failed received bytes count and incomplete files never become verified cache entries. These are separate from the existing release-1 L1C development acquisition budget. Catalog search outcomes and failures are recorded. Cache reuse verifies hashes. Exact filenames, hashes, cloud products, source conventions, approximations, state counts, selected channels and correction coverage are preserved in exports. Export replay rejects a different atmospheric cache.

## Implemented analytical Rayleigh prototype

The user explicitly authorized this prototype after reviewing analytical approaches, and authorized molecular depolarization on 2026-10-26, leaving multiple scattering separate. `rayleigh.py` now uses the Bates/Bodhaine dry-air formulation below at the actual channel center. The molecular layer still ends at OCI cloud-top pressure or the MERRA-2 clear-surface pressure used by PACE; classified land and water use the same calculation. Actual per-view zenith and scattering angles drive the plane-parallel single-scattering integral. Scattering-plane molecular U is zero for unpolarized sunlight even with molecular anisotropy. Model Q/U is inverse-rotated into the L1C meridional plane, converted from intensity to polarization irradiance normalization, then subtracted from canonical observed components. Magnitude and signed scattering-plane quantities are derived afterward. DoLP is derived from molecular-subtracted I/Q/U in consistent radiance units; nonpositive corrected I produces missing DoLP. The OCI transmission LUT is **not** applied to polarized components. Signed scattering-plane U remains unchanged apart from roundoff.

Assumptions remain monochromatic band centers, standard dry-air composition, no multiple scattering, no aerosol, no attenuation of the molecular path by absorbing gas, and no cloud/surface coupling. The legacy combined total mode subtracts molecular reflectance then divides by the supplied effective transmission; it is not a dashboard option. That combination has not been validated against a vector-RT reference. At short wavelengths or oblique views the omissions can matter. Depth integration, F0 conversion, frame rotations and molecular phase normalization have independent synthetic checks; these establish implementation consistency, not atmospheric-correction accuracy.

### Molecular depolarization and consistent optical depth — 26 October 2026

This is molecular anisotropy within **single scattering**, not depolarization caused by multiple scattering. For wavelength `l` in micrometers, Bates' factors are `FN2=1.034+3.17e-4/l²`, `FO2=1.096+1.385e-3/l²+1.448e-4/l⁴`, `FAr=1`, `FCO2=1.15`. Bodhaine eq. 23 averages them with normalized amounts `78.084:20.946:0.934:0.030` (standard dry air, fixed 300 ppm CO2 reference, not a measured contemporary composition). Define `rho=6*(FK−1)/(7*FK+3)` and `Delta=(1−rho)/(1+rho/2)`. The first-column elements are:

```
P11 = 3/4 * Delta * (1 + cos²(theta)) + 1 − Delta
P21 = −3/4 * Delta * sin²(theta)
U_scattering = 0
```

The sphere mean of P11 is one; the polarization fraction at 90° is `(1−rho)/(1+rho)`, approximately 0.945 at 550 nm. This does not multiply the entire observed Stokes vector by that fraction.

The same `FK` enters `sigma_R=24*pi³/(lambda_m⁴*Ns²)*((n²−1)/(n²+2))²*FK`. Refractivity is Bodhaine eq. 18 (Peck–Reeder), with `Ns=2.546899e25 m⁻³` at the same 288.15 K/1013.25 hPa reference. Hydrostatic `tau_R=sigma_R*N_A*p_Pa/(M*g)` uses `N_A=6.02214076e23 mol⁻¹`, `M=0.02896401668 kg/mol` (Bodhaine's 300 ppm expression) and fixed standard `g=9.80665 m/s²`; latitude/height-dependent gravity is not modeled. The old Hansen–Travis polynomial is replaced, **not multiplied by FK**, to avoid double counting. The existing pressure support `0<p<=1050 hPa` and all cached boundary fields remain unchanged.

The shared map-removal and above-cloud RFT addition call this same implementation. The RFT droplet proxy, gain 1.61, phase normalization and A/B/C-based comparison curves are unchanged; the molecular contribution is added once with no droplet gain. TOA observations remain unchanged. Export provenance records model version `dry-air-bates-bodhaine-2026-10-26`, constants and sources. Recipes replay with the current model; older Rayleigh exports are not bit-identical under this update even with the same cache. Their saved provenance identifies the earlier model.

The API retains 350–2500 nm support. Peck–Reeder's refractivity data extend to about 1690 nm; its use beyond that range is an explicit **unverified SWIR extrapolation**, not established accuracy. The visible HARP2 and default OCI RGB channels lie within the measured range. Bandpass averaging, humidity/composition variation, vector multiple scattering and cloud/surface coupling remain unimplemented.

Sources: [Bodhaine et al. (1999), eqs. 5–6, 18, 22–25](https://doi.org/10.1175/1520-0426%281999%29016%3C1854:ORODC%3E2.0.CO;2), [Bates (1984)](https://doi.org/10.1016/0032-0633%2884%2990102-8), [Peck and Reeder (1972), wavelength range](https://doi.org/10.1364/JOSA.62.000958), and [Trees et al. (2026), Appendix A molecular matrix](https://gmd.copernicus.org/articles/19/9677/2026/).

The former **Extend surface T to 1050 hPa** UI option was removed at the user's request on 2026-10-19. Recipe default is false; browser settings/imports force false, and validated API/export recipes with true fail explicitly. Internal legacy LUT-evaluation support and its independent tests remain for historical research, but current validated recipes cannot enable it. No larger-pressure or negative-slope fallback was introduced.

The experiment had extended -ln(T) from supported 900/1000 hPa anchors to at most 1050 hPa for clear water only, requiring nonnegative optical-depth slope. Benchmark clear-water PS never exceeded 1020.7865 hPa: most remaining above-1000 gaps failed the slope guard rather than the upper cap. Raising that cap would not resolve them (see the archived STATUS evidence). Removing this transmission extension does not lower the separate analytical Rayleigh pressure cap of 1050 hPa; that is an evaluation-domain bound, not transmission extrapolation. The original `scene.nc` and enriched `scene-rayleigh.nc` caches remain preserved.

Rayleigh-only caches now omit transmission/water arrays entirely; legacy combined caches still load and advertise transmission support. Tests enforce that boundary-only preparation/loading does not call the transmission reader/validator. This is dependency separation, with no changes to the Rayleigh equations, source geometry or pressure fallback.

Rayleigh path reflectance must be **subtracted**, whereas the supplied transmission correction divides by attenuation. A consistent simplified model is `rho_boundary = (rho_TOA - rho_molecular_TOA) / T_boundary`. The modeled molecular term must already have the matching gas attenuation; confirm what the supplied transmission table includes before combining models to avoid double correction. Cloud/surface coupling and aerosols mean this approximation does not by itself recover a surface or cloud-only reflectance.

The [HelpHub/Hackweek tutorial](https://pacehackweek.github.io/pace-2025/presentations/notebooks/rayleigh_correction.html) demonstrates a FastMAPOL-derived intensity neural network with 13 wavelengths, geometry, pressure and ozone inputs. Its model file is referred to in a shared workshop directory, not supplied with this repository. Training bounds, spectral response and normalization must be obtained with the weights. The displayed workflow uses a near-black surface and very low aerosol input and does not validate replacing surface pressure with cloud-top pressure for bright clouds. HARP2 code is commented in the example; an adapter needs actual per-view metadata rather than OCI-shaped band indexing. The tutorial's global lambda^-4 fit is useful for a demo but should be checked against wavelength-specific predictions/bandpass integration for a scientific quicklook.

A practical implementation is a cached, band-integrated **vector molecular radiative-transfer LUT** at OCI/HARP2 wavelengths, sampled by actual solar/view geometry and cloud-top/surface pressure. Above-cloud gas columns should follow the truncated profile. Include a bright-cloud boundary sensitivity check, especially for broken/thin clouds. Test against independent vector-RT calculations and compare results across blue, green and red; use the existing bin/cache/provenance/export architecture. The benchmark CLD product already provides bandpass Rayleigh optical thickness (`Tau_r`) for OCI, but optical thickness alone is not the view-dependent path reflectance. [NASA atmospheric-correction overview](https://pace.oceansciences.org/docs/sci2015_franz.pdf) describes pressure/geometry-dependent I/Q/U Rayleigh LUTs; [libRadtran](https://libradtran.org/doku.php?id=user_area%3Amulti-angle_polarization_simulations_polder) provides polarized molecular/cloud simulation examples.

## Polarimetric correction and remaining verification

Predict molecular **I/Q/U**, normalize consistently with the measured Stokes fields and irradiances, and rotate modeled Q/U into the same reference plane as the observations. Remove molecular components from canonical Q/U before forming polarized magnitude. Apply any gas transmission consistently with that modeled path, then derive polarization and DoLP from corrected components in common physical units. Do not subtract a modeled polarized magnitude from an observed magnitude, or divide observed polarized reflectance by the OCI scalar table and call it a Rayleigh correction.

Maintain separately named corrected fields, preserve TOA observations and canonical fitting values, and apply the user's negative display sign only after component correction. Automatic use in cloudbow fitting requires a separately validated model. Full atmospheric removal also needs an aerosol model and treatment of atmosphere–cloud/surface multiple scattering; molecular-only removal must be named accordingly. The experimental molecular-only map correction is implemented as described above; transmission-only mode itself does not alter polarization. It is not used in cloudbow fitting or source diagnostics.

## Sources and verification boundaries

NASA source was read at commit `8e8615cbca5becf542f2ef30fe89418baf33faac`: [pressure-grid/humidity interpolation](https://git.smce.nasa.gov/oel/ocssw/-/blob/8e8615cbca5becf542f2ef30fe89418baf33faac/src/libcloud/profile_management.c), [water integration](https://git.smce.nasa.gov/oel/ocssw/-/blob/8e8615cbca5becf542f2ef30fe89418baf33faac/src/libcloud/ancillary_module.f90), [pressure rounding/effective-path transmission](https://git.smce.nasa.gov/oel/ocssw/-/blob/8e8615cbca5becf542f2ef30fe89418baf33faac/src/libcloud/atmospheric_correction.f90). Cached upstream source and all supplied reference assets remain ignored; no supplied reference script or notebook was executed. The companion project's source was inspected for context, with independently tested implementation here.

See STATUS.md for measured real-data coverage/performance and outstanding verification. Source scientific products and TOA polarization are unchanged; imputation, surface boundary and cross-instrument transmission are explicitly approximate.
