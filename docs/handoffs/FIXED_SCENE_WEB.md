# Agent handoff 1 — fixed-scene web demonstration

Science update, 2026-10-26: reuse the current versioned Bates/Bodhaine wavelength-dependent molecular depolarization consistently in Rayleigh optical depth and phase elements, for both map removal and RFT above-cloud addition. Existing cloud/surface pressure, land policy and Stokes/F0 conversions remain. Do not restore the ideal phase matrix or add Rayleigh multiple scattering. Preserve model/constants provenance and unverified SWIR extrapolation above 1690 nm; see ../ATMOSPHERE.md.

Status: implementation brief prepared 2026-10-19; no hosted application exists yet. Read AGENTS.md, ../HANDOFF.md, ../SCIENCE.md, ../RFT.md, ../ATMOSPHERE.md and ../REMOTE_MIE.md first. Paths below are repository-relative unless stated otherwise.

## Objective and fixed inputs

Make the implemented Quicklook Dashboard usable in a web environment for the specific scene already under review. Preserve the three maps, original-bin linking, spectra, red hyperangular polarimetry, stored cloudbow/RFT comparison, named residuals and export behavior. Do not build a general catalog browser in this track.

Fixed science pair (timestamp 20251002T182635):

- `PACE_OCI.20251002T182635.L1C.V3.5km.nc`
- `PACE_HARP2.20251002T182635.L1C.V4.5km.nc`
- Optional diagnostics source: `PACE_HARP2.20251002T182635.L2.CLOUD_GPC.V4_0.nc`
- Existing selection: any valid original bin in the 395 × 519 shared grid; do not hard-code the user's last clicked bin as a scientific default.
- Existing default HARP2 crop: rows [0,395), columns [124,438), with full-scene option retained.
- Local source manifest: `data/manifests/development.json`, case `science_scene`; files reside under ignored `data/raw`. Resolve identities/hashes from that manifest rather than copying them into deployment secrets or assuming shape means alignment.

The raw pair plus GPC is about 1.66 GB. Do not ship it to browsers or put it in Git. Current Mie input is the ignored `data/reference/MiedBaseE4_Parm_HARP2_LR.nc`; no redistribution rights or public URL are established. Use the independent `data/atmosphere/scene-rayleigh-land.nc` cache (or freshly prepared equivalent); it omits transmission/humidity arrays. The preserved legacy `scene-rayleigh.nc` embeds transmission and must not be redistributed unchanged.

## Recommended implementation

Start with a containerized Python service plus the built frontend, with fixed science assets mounted read-only outside the image/repository. This preserves existing algorithms and arbitrary channel/sector/bin inspection. Keep raw NetCDF and all LUT access on the server; cache projected imagery/diagnostics using immutable source identities and complete recipe keys. A server runtime needs provisioned storage/memory and persistent assets; this is not a drop-in static GitHub Pages app.

If the target is static-only hosting, explicitly inventory every retained channel, anchor, projection, enhancement and bin interaction before proposing precomputed assets. Precomputation is acceptable only if the retained controls and original-bin mappings are complete and measurements remain traceable. Do not flatten to screenshots, silently remove diagnostics or distribute the Mie grid. Obtain agreement on capability reductions rather than calling a partial image demo the full dashboard.

Correction UI for this example should offer TOA and **Rayleigh · experimental** only, including molecular Q/U removal for HARP2. A visually enhanced default with the shared Atmospheric Correction dropdown set to Rayleigh is appropriate for this requested demonstration, with the correction badge and unclassified-only bypass plainly labeled. Rayleigh must apply to classified land and water using the approved existing boundaries/component subtraction, with unsupported classified bins missing rather than TOA fallback. Keep TOA accessible. Exclude transmission, Rayleigh+transmission and the retired surface extension. Do not change the already authorized correction science. Corrections affect maps; selected-bin observations/fits/residuals stay TOA and must say so.

Rayleigh/cache separation has already been implemented on 2026-10-19. Reuse `Atmosphere` with the versioned `rayleigh_boundary` cache, `atmosphere-prepare --mode rayleigh`, or `atmosphere-extract-rayleigh` for existing caches. No transmission table, PROFILE/QV10M or pyhdf is required. The frontend uses a single Atmospheric Correction dropdown for total and polar imagery and `/api/scene` capability flags to disable unavailable Rayleigh. Legacy transmission controls are absent. Preserve this interface and the exact existing boundary/land/phase/provenance checks; do not repeat the separation or change the model. See ATMOSPHERE.md and STATUS.md for verification and replay behavior.

Use the shared Mie provider contract in REMOTE_MIE.md for cloudbow/RFT. The private table stays in a protected backend or query service; browser bundles and public artifacts must not contain it. For a self-contained fixed demo, precomputed per-bin model results may be considered only after permission to distribute those derived values and a finite asset/coverage audit. Do not expose unrestricted LUT-grid extraction endpoints.

## Land policy to preserve

The user approved promotion of the land trial to production on 2026-10-19. Do not build the hosted demo with the former land bypass. The shared dropdown sets `rayleigh_land=true` along with total/polar Rayleigh; new defaults do the same. Only legacy Python/API recipe replay can retain explicit false (old recipes lacking the field load as false via `Recipe.from_dict`). Source spectra, observed angular points, cloudbow/RFT and residuals remain TOA. No new surface-pressure adjustment or terrain model is authorized/needed for this promotion. Preserve the current missing-data policy, labels, separate corrected-land/water counts and `rayleigh_land_policy` export provenance. See ATMOSPHERE.md for full migration details and LAND_RAYLEIGH_TRIAL.md for evidence/limits.

## Web deployment changes required

The current service binds loopback and rejects non-local Host headers. Do not simply remove that middleware and expose the existing development server. Add explicit deployment configuration for allowed host/origin, trusted proxy behavior, HTTPS termination and service access. Validate the actual intended audience before choosing public versus authenticated access.

All web requests need bounded preview dimensions, export sizes/DPI, timeouts, bounded caches/output retention, and concurrency control. Current HDF5/Matplotlib operations share a lock; measure serialized latency and memory before selecting workers. Fixed server-side asset paths only: no client-supplied filesystem paths, credential upload or arbitrary download URLs. Prevent cross-user export leakage and avoid leaking private filesystem paths/provenance credentials. Disable/remove acquisition commands/routes from the deployed service runtime. Keep Earthdata authentication in offline provisioning; web visitors should not need Earthdata credentials for the fixed scene.

Host secrets stay server-side. Data/LUT permissions, intended audience, hosting account/domain/provider, storage and cost budget are user decisions before external deployment. No permission to upload/publish or purchase resources is granted by this handoff. Prepare a runnable local container/config and concrete reviewable deployment plan first.

## Acceptance and deliverables

- Reproduce benchmark source channels, registration, three-map selection, crop/projection, missing-data behavior and all retained angular controls.
- Match TOA and experimental Rayleigh map arrays to the local reference with recorded numeric tolerances. Classified land/water receive Rayleigh; unclassified cells remain original and unsupported classified corrections stay missing; source diagnostics remain TOA. No transmission table/pyhdf required in Rayleigh-only path.
- Same RFT number/Csca weights and original C/B/A; no refit/phase-only features. Identical branch-1 residual support/predictions before/after provider changes. Label unresolved operational science as experimental.
- Mobile/desktop visual checks: checkbox row under dropdowns, stable axes on toggles, readable legends/contours, hover toolbar contained; no OCI HARP2 contours.
- PNG/PDF/JSON exports preserve recipe/provenance and agree with displayed scientific settings. Check actual dimensions and reject unsupported/stale cache identities. Avoid stale TOA titles on corrected figures.
- Test concurrent sessions, bounded resource failures, unauthorized Host/origin/access, no private LUT download route and secret-free frontend assets. Report cold/warm latency, memory and asset sizes honestly.
- Deliver reproducible build/container files, fixed-scene asset manifest without private paths/secrets, deployment/runbook and measured acceptance notes. Hosted testing/deployment remains a separate authorized final step.

Coordinate any further shared interface changes to the boundary cache/MieProvider with agent 2; work in an isolated branch/worktree and document the contract. Do not remove local-only capabilities or overwrite the second track. Real dateline/high-latitude acceptance remains last and is not required to pretend this fixed scene covers those cases.

Current RFT display update (2026-10-26): RFT refl. and RFT component use the authorized optically thick single-scattering model without A/B/C, actual source geometry and omega=1; RFT P12/cloudbow retain stored A/B/C. Residuals are model minus observed in displayed −Q. Preserve explicit LUT phase-unit normalization and its unresolved P11-integral verification; see [RFT.md](../RFT.md). This supersedes earlier all-RFT-A/B/C wording.

The subsequently authorized RFT forward-model update adds above-cloud Rayleigh from the existing boundary cache. Droplet components plus a separate molecular contribution sum to RFT refl.; observations stay TOA. Preserve explicit cloud-only/no-cache labeling and unsupported cloud-boundary failures. See RFT.md for current details and STATUS.md for real verification.

Latest user-authorized RFT trial uses fixed proxy scattering-order weights [1,.5,.1,.01], multiplying droplet responses by 1.61 while keeping Rayleigh separate and unscaled. Preserve first-order/proxy-order provenance and experimental labels; these coefficients are not a Cornet-derived calibration. RFT P12/cloudbow A/B/C are unchanged. Current real-sample checks are in RFT.md/STATUS.md.


## Current quicklook product contract — 2026-11-05

Preserve the cleaned dashboard, not the historical research controls: left map selects OCI total / OCI phase / operational GPC LI / calculated narrow discrete or trapezoidal LI; middle is always HARP2 total; right is HARP2 polarimetry. Both HARP2 maps retain shared source sectors and actual-geometry contours. Left auxiliary fields preserve native-bin identity. The left angular inspector offers −Q, polarized magnitude and observation-only DoLP; DoLP disables LI integration and has no LI baseline/model. Original 135–145° LI, 135° reference and TOA diagnostics remain unchanged. Wider/adaptive LI and baseline-angle options were retired; do not restore them. Legacy routines remain for the independent statistics project, which is outside this delivery. The statistics header link has been removed. See ../LIQUID_INDEX.md for new `left_mode` recipe/migration and DoLP export behavior.
