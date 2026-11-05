# Observed liquid-index diagnostics

Implemented at the user's request on 2026-10-27. This is an independently calculated **TOA rainbow-contrast diagnostic**, compared with the reported GPC `cloud_liquid_index`; it is not a replacement operational retrieval or a liquid-water fraction.

The liquid-index workspace sits beside the cloudbow/RFT workspace. OCI spectra are below both. The workspace has an independent −Q scattering-plane / polarized-magnitude / DoLP selector. DoLP is observation-only: it disables the integration checkbox, hides LI baselines/cumulative integration and does not calculate a DoLP LI. Calculated LI maps retain the last reflectance quantity when the inspector shows DoLP. LI calculations use **branch 1 only**, as clarified by the user; branch 2 remains an observation check in the separate polarization panel. Rayleigh map settings never change these observations or indices.

## Calculation

Use the metadata-derived red hyperangular wavelength (664.564 nm in the benchmark), original observed views and per-bin scattering angles. No view/sector substitution, angular binning or spatial regridding is performed. The linear baseline is the only new fit; it is not a microphysical fit and never changes cloudbow/RFT coefficients.

1. Fit `L(theta)=a*(theta−140)+c` by unweighted least squares using all valid selected-branch observations in the inclusive **120–130° and 150–160°** windows. Both windows must have support and their combined count must be at least four. Centering the independent variable at 140° improves numerical conditioning and does not change the fitted line.
2. Select valid original measurements in inclusive **135–145°**. Require at least two distinct peak angles. These minimum counts follow the original paper's POLDER sampling checks; requiring both baseline windows is a declared conservative dashboard support rule, not independently verified operational HARP2 logic.
3. Normalize by the fitted baseline at **135°**, the lower-window reference illustrated by the dotted line in van Diedenhoven et al. Figure 4. In the centered representation this is `a*(135−140)+c`; it is not the ordinary y-intercept at zero scattering angle. The panel and provenance expose the reference angle/value. The GPC ATBD writes `Theta_S0` without explicitly defining that symbol; agreement with the production reference-angle and sample-selection conventions is not established.

The default discrete estimator is:

```
LI_discrete = sum_i [observed(theta_i) − L(theta_i)] / (N * L(135°))
```

Each peak view has equal weight, even if angular spacing is uneven. This is the ATBD-style discrete mean, not an area integral. Thin excess bars identify those measured contributions; the lower plot shows their normalized cumulative sum. Observations themselves remain discrete markers. The baseline and its 135° reference height are plotted separately, and both baseline windows are shaded.

The **Trapezoidal integration** checkbox selects:

```
LI_trap = integral_135^145 [observed(theta) − L(theta)] dtheta / (10° * L(135°))
```

The angular mean (division by 10°) makes this dimensionless and comparable to the discrete mean. Observed reflectance is piecewise linear between valid selected-branch measurements; the endpoints are interpolated using bracketing observations, never extrapolated. This explicitly assumes linear behavior across the gaps between valid measurements. The polygon shows that quadrature assumption, not additional observations. Duplicate angles disable unambiguous trapezoidal interpolation. Its largest integration segment is recorded in JSON. The lower plot accumulates the actual trapezoid areas with the same normalization; its final value equals the displayed LI. This alternative was requested by the user and is not claimed to be the operational GPC estimator.

Neither estimator clips negative excess or negative LI. A zero or numerically unstable normalization yields missing LI with a reason; a negative baseline is retained with a warning in the detailed support. Missing windows or inadequate samples never become zero. The magnitude calculation uses `hypot(Q,U)` with polarization irradiance normalization and is labeled an alternative to the ATBD signed-Q calculation. It can differ because it includes U and loses the sign of Q. No glint model/removal is introduced.

## Left-map options

- **GPC liquid index**: reported registered `cloud_liquid_index` on its original L1C-compatible grid. CF fill values are missing; finite values are retained independently of cloudbow/RFT success flags. Current GPC loading uses the existing optional GPC+Mie wrapper, although the index field itself does not scientifically require a Mie table.
- **Calculated LI · discrete** and **Calculated LI · trapezoidal**: calculations above for every original HARP2 bin, using the liquid-index workspace's quantity and branch. These maps need L1C observations only, not GPC, Mie or an atmospheric cache. They are not masked to the operational cloud/retrieval selection, so coverage differs from GPC.

All three use the same **blue–white–red** display scale, **clipped to 0–4 with white at LI=0.3**, as requested by the user. Scaling is piecewise linear on either side of 0.3, with that threshold at the center of the colorbar. Values below zero saturate blue and above four saturate red. Only display colors are clipped: scientific values and diagnostic comparisons remain unchanged. Provenance records the scale and counts below/above it; exports indicate extended endpoints. Changing the map anchor or atmospheric correction does not change any LI field. HARP2 scattering-angle contours are excluded from these left-map modes. Map hit IDs and marker identity remain the original source bins, including selections where LI is missing.

Calculated maps read at most 16 source rows at a time (public helper permits 1–64), then evaluate each source bin using the same function as selected-bin diagnostics. Both methods are cached together per quantity/branch for the current service process. First calculation costs tens of seconds for the benchmark; changing between integration methods reuses that cache. No new downloads or on-disk science cache is required. Restarting the service clears the derived in-memory cache.

## API, recipes and exports

`GET /api/bin/ROW/COL` includes `liquid_index`: operational source/value, method provenance, branch 1, both quantities, and both integration estimates. It also records masks, source views, fitted line, normalization, excesses, counts, and difference from GPC. No new query arguments are needed.

Recipes add `liquid_index_quantity` (`signed_q` default or `polarized`), `liquid_index_branch` (`1` only) and `liquid_index_trapezoidal` (false default). `left_mode` accepts `liquid_index`, `liquid_index_discrete`, `liquid_index_trapezoidal`. The checkbox controls the selected-bin plot/export, while the two distinct map choices explicitly select their own integration estimator. Older recipes restore the new defaults.

PNG/PDF diagnostics compositions include the LI observation/baseline panel, cumulative integration and OCI spectrum below the polarization panels. JSON preserves all numerical LI results and method/recipe provenance. A taller figure (e.g. 250 × 260 mm) is useful for the expanded composition; the browser height default is 240 mm. Requested physical dimensions remain honored, with typography reduced for short diagnostic figures.

Sources: [GPC ATBD V1, 2026-09-01, §2.1.1/Eq. 3](https://oceandata.sci.gsfc.nasa.gov/files/atbd/atbd-obdaac-cloud-GPC.pdf), [van Diedenhoven et al. 2012, §4b/Eq. 1/Figure 4](https://www.giss.nasa.gov/pubs/docs/2012/2012_VanDiedenhoven_va04100j.pdf). Real comparison results and scientific gaps are recorded in [STATUS.md](STATUS.md); numerical consistency is not proof of exact operational reproduction.


## Current quicklook scope — 2026-11-05

The wider-window, adaptive-window and baseline-angle diagnostics/controls/maps were retired from this dashboard at the user's request. Quicklook selected-bin/map calculations use `extended=False`; they calculate only the original discrete and trapezoidal 135–145° estimators and omit the angle calculation. Independent legacy helper defaults remain available to the separate statistics project and historical analyses. Their previous specifications are archived in [history](history/LIQUID_INDEX-2026-10-27.md); do not restore them to quicklook.

Map order is now selectable left field / HARP2 total / HARP2 polarimetry. `left_mode` is `oci_total` by default, or `oci_phase`, `liquid_index`, `liquid_index_discrete`, `liquid_index_trapezoidal`. Contours remain on both HARP2 maps only. The two HARP2 maps always share the selected source sectors. OCI RGB controls hide while the left panel displays another field. All three maps select original bins, including missing values.

`liquid_plot_dolp` controls the observation-only DoLP inspector/export independently of `liquid_index_quantity`. `Recipe.from_dict` migrates legacy `middle_mode` to `left_mode` (`harp_total` becomes `oci_total`); retired map selections reset to OCI total, and retired wide/adaptive/range fields are dropped. Browser restore follows the same policy. No scientific LI values are rescaled or tuned during migration. Direct new recipes with unsupported left modes fail validation.
