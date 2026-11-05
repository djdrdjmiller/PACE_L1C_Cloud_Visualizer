# Observed liquid-index diagnostics

Implemented at the user's request on 2026-10-27. This is an independently calculated **TOA rainbow-contrast diagnostic**, compared with the reported GPC `cloud_liquid_index`; it is not a replacement operational retrieval or a liquid-water fraction.

The liquid-index workspace sits beside the cloudbow/RFT workspace. OCI spectra are below both. The workspace has independent −Q scattering-plane / polarized-magnitude selector. LI calculations use **branch 1 only**, as clarified by the user; branch 2 remains an observation check in the separate polarization panel. Rayleigh map settings never change these observations or indices.

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

## Middle-map options

- **GPC liquid index**: reported registered `cloud_liquid_index` on its original L1C-compatible grid. CF fill values are missing; finite values are retained independently of cloudbow/RFT success flags. Current GPC loading uses the existing optional GPC+Mie wrapper, although the index field itself does not scientifically require a Mie table.
- **Calculated LI · discrete** and **Calculated LI · trapezoidal**: calculations above for every original HARP2 bin, using the liquid-index workspace's quantity and branch. These maps need L1C observations only, not GPC, Mie or an atmospheric cache. They are not masked to the operational cloud/retrieval selection, so coverage differs from GPC.

All three use the same **blue–white–red** display scale, **clipped to 0–4 with white at LI=0.3**, as requested by the user. Scaling is piecewise linear on either side of 0.3, with that threshold at the center of the colorbar. Values below zero saturate blue and above four saturate red. Only display colors are clipped: scientific values and diagnostic comparisons remain unchanged. Provenance records the scale and counts below/above it; exports indicate extended endpoints. Changing the map anchor or atmospheric correction does not change any LI field. HARP2 scattering-angle contours are excluded from these middle-map modes. Map hit IDs and marker identity remain the original source bins, including selections where LI is missing.

Calculated maps read at most 16 source rows at a time (public helper permits 1–64), then evaluate each source bin using the same function as selected-bin diagnostics. Both methods are cached together per quantity/branch for the current service process. First calculation costs tens of seconds for the benchmark; changing between integration methods reuses that cache. No new downloads or on-disk science cache is required. Restarting the service clears the derived in-memory cache.

## API, recipes and exports

`GET /api/bin/ROW/COL` includes `liquid_index`: operational source/value, method provenance, branch 1, both quantities, and both integration estimates. It also records masks, source views, fitted line, normalization, excesses, counts, and difference from GPC. No new query arguments are needed.

Recipes add `liquid_index_quantity` (`signed_q` default or `polarized`), `liquid_index_branch` (`1` default or `2`) and `liquid_index_trapezoidal` (false default). `middle_mode` additionally accepts `liquid_index`, `liquid_index_discrete`, `liquid_index_trapezoidal`. The checkbox controls the selected-bin plot/export, while the two distinct map choices explicitly select their own integration estimator. Older recipes restore the new defaults.

PNG/PDF diagnostics compositions include the LI observation/baseline panel, cumulative integration and OCI spectrum below the polarization panels. JSON preserves all numerical LI results and method/recipe provenance. A taller figure (e.g. 250 × 260 mm) is useful for the expanded composition; the browser height default is 240 mm. Requested physical dimensions remain honored, with typography reduced for short diagnostic figures.

Sources: [GPC ATBD V1, 2026-09-01, §2.1.1/Eq. 3](https://oceandata.sci.gsfc.nasa.gov/files/atbd/atbd-obdaac-cloud-GPC.pdf), [van Diedenhoven et al. 2012, §4b/Eq. 1/Figure 4](https://www.giss.nasa.gov/pubs/docs/2012/2012_VanDiedenhoven_va04100j.pdf). Real comparison results and scientific gaps are recorded in [STATUS.md](../STATUS.md); numerical consistency is not proof of exact operational reproduction.

## Experimental wider and adaptive windows (2026-10-27)

Two mutually exclusive checkboxes select either the fixed **130–150° wider window** or **adaptive crossings / 130–150° edges**. Both always use trapezoidal integration. The original 135–145° window retains the discrete/trapezoidal choice; its preference is restored when both extended checkboxes are off. The trapezoidal checkbox is checked and disabled while an extended window is selected. There is no wider or adaptive discrete dashboard/map option. The low-level `calculate(wide=True)` legacy discrete result remains for numerical reproducibility, not as a selectable product.

All variants retain the same inclusive baseline windows, L(135°) reference and fixed **10° angular denominator**:

```
LI = integral_lower^upper [observed(theta)-L(theta)] dtheta / (10° * L(135°))
```

Fixed-wide bounds are 130°/150°; observations at those exact boundaries may also constrain the baseline. The adaptive algorithm, confirmed by the user, uses the **horizontal reference L(135°)** to choose bounds, not the sloping L(theta). It selects the strongest valid observed sample within 135–145°, requires that sample to exceed the horizontal reference, and follows the contiguous above-reference lobe to the nearest crossing on each side. Crossings are piecewise-linear between neighboring valid original observations (exact reference hits accepted). Equal-height seed ties choose the lower-angle sample. Differences within 1e-10 of the largest absolute observed reflectance are treated as exact reference hits. Search/integration is bounded to **130–150°**, following the user’s clarification. A crossing inside that window sets the endpoint; when it is outside or absent, the endpoint is the corresponding 130°/150° edge. Endpoints still require bracketing observations; no extrapolation, smoothing or assumed droplet size is used. Detached lobes beyond an intervening crossing are excluded.

Crossings choose **bounds only**: integrated excess still subtracts the sloping baseline L(theta). Signed/negative contributions inside the adaptive window remain. The panel marks crossings with x symbols and capped window edges with open squares, and shows actual bounds. JSON records boundary kinds, crossing angles, bracket angles/source-view IDs, seed, quadrature arrays, largest segment and support reasons. Missing a crossing now uses the approved window edge. If valid main-bow samples exist but none exceeds the horizontal reference, use the signed fixed-wide 130–150° trapezoidal result, with an explicit fallback reason. No valid main-bow observations, unsupported baseline, unbracketed endpoint, unstable denominator or duplicate angles still yield missing adaptive LI. Interpolation across gaps is declared rather than treated as resolved measurements.

API/JSON `series[quantity].wide` and `.adaptive` preserve extensions alongside original estimates, with independent differences from GPC. Adaptive `.discrete` is explicitly unavailable. Recipe `liquid_index_adaptive` and `liquid_index_wide` default false; adaptive takes precedence if an API recipe enables both. Middle maps are explicit and independent of inspector checkboxes: `liquid_index_wide_trapezoidal` and `liquid_index_adaptive_trapezoidal`. Quantity/branch remain shared. Removed `liquid_index_wide_discrete` requests are rejected by Python/API; browser saved/imported selections migrate to wide trapezoidal.

Bounded row batches cache original discrete/trapezoidal plus fixed-wide/adaptive trapezoidal maps per quantity/branch. All use native sampling and unchanged TOA data. The common clipped 0–4 display and white 0.3 reference remain; **classification performance at 0.3 for extended indices is unvalidated**. Baseline sensitivity, noise-driven early crossings, unresolved features, gaps and capped boundaries can affect adaptive results. Operational GPC is retained independently and never tunes the adaptive window.

## Angular-sampling interpretation

The original van Diedenhoven et al. (2012) study explicitly required at least two bow measurements and four baseline measurements. Section 5a also discusses aggregation into 176 km blocks to improve POLDER angular sampling; this is historical study context, not a spatial aggregation applied here. NASA's RSP product inventory cites that study for its cloud-top phase index. The GPC ATBD describes HARP2's approximately 2° sampling and retains the 135–145° equal-view estimator and 0.3 threshold. These sources do not establish a controlled POLDER-to-RSP-to-HARP2 LI sampling/threshold equivalence test; exact implementation history remains unverified.

Dividing by view count removes simple growth with sample count, but not uneven-density weighting, peak undersampling, endpoint placement, baseline-fit leverage or finite angular response. Trapezoids use angular spacing and reduce equal-view density weighting; they cannot reconstruct missed narrow structure. Adaptive crossing locations additionally respond to noise, gaps and angular sampling. No new resampling or cross-instrument calibration was introduced in this experiment.

RSP inventory: https://data.giss.nasa.gov/rsp_air/ . Original paper and GPC ATBD linked above.

Branch policy clarification: LI diagnostics return only branch 1 (`branch=0` internally). Native map helper rejects branch 2, and recipes require `liquid_index_branch=1`. Browser old LI branch selections migrate to 1. This does not change branch-2 observation display in the separate polarization panel.

No-peak fallback (user-approved): with valid main-bow samples but none above L(135°), adaptive LI defaults to the fixed 130–150° trapezoidal calculation. API/plots/exports label this fallback explicitly. Negative values are retained. This never bypasses baseline, normalization, duplicate-angle or endpoint-bracketing requirements.

## Baseline-versus-reference angle map (2026-10-27)

The middle-map option **Baseline vs reference · angle** (`middle_mode=liquid_index_baseline_angle`) uses the user-selected **raw numeric angle** between the fitted line L(theta)=a*theta+c and the horizontal reference L(135°):

```
alpha_degrees = degrees(atan(a - 0))
a = dL / dtheta, in reflectance per degree of scattering angle
```

The explicit numeric-axis convention is one reflectance unit per one scattering degree. This is not an angle read off the browser's pixel aspect ratio, and **does not divide by L(135°)** or apply a 10° multiplier. The reference height does not affect its horizontal orientation. Positive means rising with increasing scattering angle; negative means falling. Radiometric multiplication changes this raw numeric angle, while an additive reflectance offset does not. Values will often be small. It is not a physical scattering angle, an independently retrieved constituent, or an attribution to ice/aerosol/Rayleigh.

Reuse the same unweighted 120–130/150–160° branch-1 hyperangular TOA baseline and selected LI quantity. A supported baseline is sufficient: no bow peak, integration coverage or nonzero L(135°) requirement is imposed. Unsupported baseline remains missing. Source bins/selection and the TOA fields are unchanged; nominal imagery anchor, atmospheric map correction and LI integration checkboxes do not change this angle. API diagnostics expose `baseline_angle` with value/units, raw slope, zero reference slope and definition, before LI support checks. Its native map uses the same scalar result; a baseline-only bounded path avoids calculating all integrations on first use. Cache upgrades preserve availability when subsequently switching to LI maps.

Display uses **Turbo**, without a classification midpoint. The default range is the full native field’s **1st–99th percentiles**; a dedicated **Angle range → Full scene** option uses the actual finite minimum/maximum. Both ranges are independent of display crop. Color saturation affects display only; raw scientific angles and selected-bin values remain unchanged. Provenance records limits, range mode, valid count and clipped-tail counts. Degenerate/missing fields get a small finite display span. Preview/export/provenance share the scale; JSON preserves raw slope and angle. This supersedes the initial symmetric zero-centered blue–white–red display. The selected-bin LI readout also reports alpha, including bins where LI itself is missing. Interpret spatial structure as exploratory baseline behavior; separating molecular, aerosol, ice, surface/glint and angular-sampling influences would require additional analysis.
