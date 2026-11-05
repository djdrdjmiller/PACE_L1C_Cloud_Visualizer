# Offline land Rayleigh trial — 19 October 2026

The existing analytical Rayleigh correction was evaluated over classified land in the real 20251002T182635 OCI/HARP2 scene. The result is promising for visualization: the side-by-side total-reflectance images appear less blue/hazy and no negative total RGB values were introduced in the tested sources. This is an internal plausibility/coverage check, **not independent validation of land surface reflectance or corrected polarization**. This record describes the initial trial. The user subsequently approved this exact method for production: Rayleigh now includes classified land and water, while unclassified bins stay TOA. See ATMOSPHERE.md for the current policy.

## Exact scope

Used the unchanged `rayleigh.subtract` calculation and `data/atmosphere/scene-rayleigh-only.nc` pressure/state/classification fields. Cloudy land uses the existing cloud boundary; clear land uses the existing interpolated MERRA-2 surface pressure. No new terrain adjustment, pressure model, humidity/transmission, aerosol correction, gap filling or Mie input was introduced. Q/U components are removed before deriving magnitude/DoLP, exactly as in the production water calculation.

The offline helper substitutes these existing molecular-subtracted quantities on `surface_class==1` only. Water and unknown-classification values are asserted production-identical. Unsupported land becomes missing; it is not silently replaced by TOA. Neither input arrays/cache nor source observations are modified. PNG/PDF comparisons use identical transfer settings (total 0–0.8/gamma 1.6, polarized 0–0.12/gamma 1.4), not separately optimized stretches. Difference maps show only land; all calculations use original bins.

The primary HARP2 anchor is the dashboard's 33.22° setting, with actual RGB angles approximately 34.2°/33.2°/35.0°. OCI actual centers are 644.716/555.044/449.795 nm; HARP2 centers 664.564/549.465/440.159 nm. Additional sparse-band anchors at 6.6° and −33.7° were evaluated numerically, each using its actual metadata-selected channels. Counts below refer to all classified land in the granule with usable source observations, not only the displayed crop; HARP2 coverage changes with view. The figure crops the existing HARP2 footprint to rows [0,395), columns [184,438) for comparison, without changing statistics.

## Measured coverage and plausibility

The original shared grid has 41,458 classified land bins. Only 30 have missing boundary pressure; 41,428/41,458 (99.93%) support the OCI RGB trial. Existing land boundary states: 36,572 direct clear, 4,641 direct cloud, 153 estimated clear, 62 estimated cloud and 30 unavailable. Finite boundary pressures span 51.47–1019.66 hPa (these include cloud-top boundaries, not only surface pressure).

| Source/anchor | Observed land RGB bins | Trial valid | Newly missing | Any negative total RGB component |
|---|---:|---:|---:|---:|
| OCI | 41,458 | 41,428 | 30 | 0 |
| HARP2 +33.2° | 16,373 | 16,373 | 0 | 0 |
| HARP2 +6.6° | 13,626 | 13,626 | 0 | 0 |
| HARP2 −33.7° | 14,563 | 14,563 | 0 | 0 |

No corrected DoLP values exceeded one in any tested HARP2 RGB channel at these anchors. Corrected intensity remained positive in those valid observations. These are useful rejection checks, not proof of accuracy. Polarized magnitude is nonnegative by construction and is not itself an independent quality test.

Median modeled subtraction from total reflectance (median of paired TOA−trial values, in absolute reflectance units):

| Instrument | Red | Green | Blue |
|---|---:|---:|---:|
| OCI | 0.0318 | 0.0553 | 0.1117 |
| HARP2, current +33.2° anchor | 0.0190 | 0.0387 | 0.0834 |

At the current HARP2 blue source, median polarized reflectance changes from 0.07555 to 0.01182 and median DoLP from 0.4441 to 0.1275 on the same valid land samples. The effect is substantial and strongly geometry-dependent. Displayed −Q changes sign in 1,445/19,804 blue observations; signed Q can physically have either sign, so a sign crossing alone does not establish an error. The ideal model's scattering-plane U changes only by numerical roundoff (maximum paired change about 4.92e−9 in this source).

High terrain is represented: OCI land height median is 1,725.5 m and 95th percentile 4,629 m. No negative corrected blue total values occurred in the tested below-1-km, 1–3-km or above-3-km height strata. Heights were inspected only; they did not change the pressure fields. This does not establish that coarse model pressure is correct at each L1C elevation, and OCI/HARP2 source heights differ slightly.

## Interpretation and remaining limits

Visual inspection of the real comparison shows reduced land blue haze and more distinct brown/green terrain, with no broad missing-coverage problem analogous to the earlier transmission experiment. Land polarized RGB becomes much darker because the removed blue molecular contribution is large. The output remains a molecular path-subtraction quicklook, not a retrieved surface-reflectance/BRDF product.

The earlier transmission failure over land depended strongly on missing humidity columns/table support; the present model does not use those inputs. Its 30 missing-pressure land bins remain explicit. However, no external vector-RT/surface reference, aerosol information or independent polarization truth was used. Multiple scattering, surface–atmosphere coupling, reflected-signal attenuation and fine-terrain pressure adjustments remain outside the existing model. Bright clouds/snow and low residual polarization merit particular care. Only three HARP2 sparse-band RGB anchors were checked; this is not an all-view/all-scene validation.

Initial recommendation was to consider a land-enabled experimental quicklook. The user then explicitly approved full integration of the tested method, now implemented. That approval changes the application domain, not the scientific accuracy evidence or model limits. Current production matches the trial and no longer preserves TOA on classified land when Rayleigh is enabled.

## Reproduce and inspect

Run from the repository root in the pinned Python environment:

```bash
MPLCONFIGDIR=cache/matplotlib python examples/land_rayleigh_trial.py \
  --oci data/raw/PACE_OCI.20251002T182635.L1C.V3.5km.nc \
  --harp2 data/raw/PACE_HARP2.20251002T182635.L1C.V4.5km.nc \
  --atmosphere data/atmosphere/scene-rayleigh-only.nc \
  --recipe outputs/land-trial-current-recipe.json \
  --output outputs/land-rayleigh-trial
```

The run-specific JSON recipe is ignored; use a saved dashboard recipe to reproduce another setting or omit `--recipe` for metadata/default selection and the comparison stretch. The recorded recipe uses OCI targets 645/555/450 nm, HARP2 670/550/440 nm, anchor 33.220001220703125°, crop [0,395,124,438], and the beauty transfer above. The generated JSON is an offline analysis report, not a normal dashboard export recipe. It embeds exact baseline recipe, sources/hashes, atmospheric provenance, explicit land-trial policy, selected channels and all statistics. Reproduce the land result with this example; the example explicitly sets `rayleigh_land=false` for its historical water-only reference column; ordinary current land-enabled exports already apply the trial result. Explicit legacy false remains available for old-recipe replay. The example rejects mismatched source/cache provenance in an input saved export.

Local artifacts (ignored, not redistributed): `outputs/land-rayleigh-trial.png`, `.pdf`, `.json`. The PNG was visually inspected. Original measured run time was 7.404 s; rerun timings vary with OS cache. Automated checks: 71 tests pass, including trial isolation, unsupported pressure behavior, component-derived polarization and summary denominators. No browser/production correction behavior was changed during the initial trial; its later promotion is documented in STATUS.md and ATMOSPHERE.md.
