# RFT reflectance comparison

Molecular refinement (user approved, 2026-10-26): the separate above-cloud Rayleigh term now uses wavelength-dependent dry-air molecular depolarization and consistent Bates/Bodhaine optical depth, shared with map correction. This changes the molecular term only; cloud/mode responses, gain 1.61, weights, A/B/C and TOA observations are retained. Rayleigh multiple scattering remains excluded. See [ATMOSPHERE.md](ATMOSPHERE.md) for equations, constants and limitations.

The dashboard offers an independent optically thick RFT reflectance approximation and a separate stored-cloudbow-A/B/C mode comparison. It does not retrieve microphysics or fit new coefficients. Shared-A/B/C refitting was removed at the user's request on 2026-10-16.

## Current four-order trial (authorized 2026-10-26)

RFT refl./component now apply the user's explicit experimental relative order weights **[1, 0.5, 0.1, 0.01]**, giving a droplet gain **1.61** before the separate above-cloud Rayleigh addition. These are individual-order proxy contributions relative to first order, not cumulative weights. They are not normalized to sum to one. Within each order, the existing normalized number-fraction*Csca mode weights remain unchanged. Every order repeats the same signed phase/angular/geometry shape; both droplet modes receive the same gain. This is a phase-preserving proxy, not a resolved second-/third-/fourth-order vector-RT calculation, and the numerical coefficients are user prescribed, not inferred from Cornet Fig. 9.

The displayed prediction is `1.61 * (D0_single + D1_single) + Rayleigh`. Component curves include the four-order enhancement; their sum plus the separate amber Rayleigh curve equals the total. RFT P12/cloudbow keep their original A/B/C and are unchanged. Residuals/export use the new total. JSON retains signed_single_scattering, predicted_single_scattering_signed_q, single_scattering_contributions and signed_order_contributions, plus the explicit order weights and assumptions, so the prior first-order baseline can be reconstructed without rerunning retrievals. No amplitudes were fit to observations. Existing recipes intentionally adopt the new experimental model on reload.

## Current thick-cloud comparison (authorized 2026-10-26)

**RFT refl.** and **RFT component** now use optically thick, homogeneous, plane-parallel single scattering with omega=1, without cloudbow A/B/C. The stored RFT radii, variances and normalized number-fraction × Csca weights remain fixed. No new fit or observation-derived amplitude is applied.

For dimensionless phase matrices with angular-mean P11=1:

`rho_-Q,i = -P21_i / [4*(mu0+mu)]`.

The supplied Mie table declares P21 units `steradian^-1`, but an independent red-band spherical-Mie/gamma-DSD check supports **dimensionless** values instead. For LUT SHA256 `d4577f972d3de0023782e6444d8ab358a1bccaac20dd6a01d5d1ea23532548e6`, the reader records a hash-specific dimensionless interpretation while preserving the original units. At its smallest re/ve point, independent Csca=62.77375 versus LUT 62.76730 µm²; P11(180)=0.4898308 versus 0.4893797; dimensionless P21(140/150°)=−0.1097529/−0.1617214 versus LUT −0.1094670/−0.1620090. Differences are <0.3%, inconsistent with a 4*pi normalization difference. A gamma DSD is an explicit audit hypothesis; exact LUT generation remains unverified. Reproduce with `python examples/check_mie_normalization.py PATH_TO_LUT`. This standalone SciPy calculation neither imports nor executes supplied references.

The current supplied LUT therefore uses the **1/[4*(mu0+mu)]** formula. Applying its sr^-1 label literally would increase amplitude by 4*pi; that interpretation was rejected based on this numerical evidence, not based on fitting observations. Other table identities use their declared normalization and carry an unaudited-convention warning; do not assume this override applies universally. A genuine unit-integral phase density would use `rho_-Q=-pi*p21/(mu0+mu)`.

Here mu0 and mu come from the selected bin's actual per-view solar and sensor zenith angles. No P12 integral/peak normalization is performed. Omega=1 is the previously user-authorized visible-water approximation; the small absorption difference from LUT optics is not applied here. Full P11 integral validation is still unavailable from this source file (only backscatter P11 is present), and the independent check covers one red-band distribution point, not the entire table.

The mixture is `sum(alpha_i * rho_-Q,i)`; **RFT component** draws these weighted contributions. **RFT P12** remains the separate dotted per-mode A/B/C-transformed response described below. Cloudbow remains its original stored-coefficient reconstruction. The overlay heading/key distinguish these models. New API `rft.thick_branches` contains thick curves, exact source predictions, weights via the shared mode records, units/conversion, geometry and limitations (with the hash-specific normalization evidence in shared LUT provenance); `rft.branches` retains historical A/B/C arrays for analysis and RFT P12.

Dense curves interpolate the geometry denominator only within each branch's measured scattering-angle extent, on the native LUT angular nodes plus endpoints. They do not extrapolate geometry or substitute nominal angles. Residuals use exact original source-view geometry and phase interpolation, not interpolation of the rendered curve. Missing geometry, horizon/downward/invalid views and unsupported angles are excluded explicitly; fewer than two supported views or repeated ambiguous scattering angles disable that branch's thick curve. Missing cloudbow coefficients do not disable thick RFT. Branch-1 residuals now compare this thick model minus TOA observed −Q on shared valid source samples. Figures/JSON and browser use the same result.

This approximation omits finite optical thickness, multiple scattering, cloud fraction, surface/3-D effects and overlying atmosphere. It predicts a cloud single-scattering contribution, not the complete observed TOA signal. A/B/C fitting absorbs some effects that are absent here, so systematic amplitude/background disagreement is expected and must not be hidden by rescaling. See the [AirHARP cloudbow study](https://amt.copernicus.org/articles/13/1777/2020/amt-13-1777-2020.html) for the geometry relationship. Existing saved recipes retain the same checkbox names but RFT refl./component now intentionally use the new thick model; historical A/B/C arrays remain available, not a bit-identical dashboard replay.

## Above-cloud Rayleigh addition (authorized 2026-10-26)

With the existing atmospheric boundary cache loaded, RFT refl. adds the experimental molecular single-scattering path to the thick-cloud prediction, in signed scattering-plane −Q. RFT component now shows droplet contributions **and a separate amber Rayleigh curve**: their sum is the displayed total. Molecular scattering is counted once, not once per droplet mode. Cloudbow, RFT P12 and all observed measurements remain unchanged. Main-map atmospheric correction does not control this forward-model addition: diagnostic observations stay TOA in either map mode.

The calculation reuses `rayleigh.path_reflectance` with actual wavelength and source solar/view/scattering angles, pressure to the cached direct/estimated OCI cloud top (states 1/3), and the existing intensity_f0/polarization_f0 conversion. Exact source-view Rayleigh predictions feed residuals. Dense molecular curves use interpolated geometry only within the same measured branch support. Source arrays and original phase weights remain unchanged. JSON includes signed_cloud_only, signed_rayleigh, their exact source predictions, rayleigh_status, boundary pressure/state and atmospheric provenance. No transmission LUT, new pressure model or attenuation of cloud reflectance is introduced; coupling, cloud-path attenuation and molecular/cloud multiple scattering remain omitted.

Without an atmospheric cache, cloud-only curves remain explicitly labeled "RFT refl. · cloud only" and warn that Rayleigh is unavailable. With a cache but missing/unsupported pressure or clear-surface boundary instead of cloud top, the total curve is disabled with an explicit reason; there is no assumed cloud pressure or clear-surface substitution. Invalid irradiances also disable it. Rayleigh addition is experimental and is not expected to remove the entire documented low bias.

## Stored A/B/C comparison retained for RFT P12 and analysis

## Fixed modes, scattering weights and full responses

The user confirmed the mode fractions are particle-number fractions. The default scattering weights are

`alpha_i = fraction_i * Csca_i / sum(fraction_j * Csca_j)`.

Interpolate bulk Csca and P21 from the supplied Mie LUT at the metadata-selected red wavelength, bilinearly in log radius/log variance. Preserve reported radii, variances and number fractions unchanged; record the normalized scattering weights separately. Missing/out-of-range optical properties, failed RFT quality or invalid fractions produce an explicit reason. No LUT extrapolation, peak normalization or independent P12-integral normalization is applied.

For each mode, the full displayed response is

`F_i(theta) = -[A*P21_i(theta) + B*(cos(theta)^2-1) + C]`.

The RFT mixture is `sum(alpha_i * F_i)`. The common B/C background is therefore counted once. With one mode its scattering weight is exactly one and the full mode response equals the mixture. Original coefficients are read in metadata-verified C/B/A order from a quality-passing cloudbow retrieval. Missing stored coefficients never trigger a new fit or substituted coefficients.

The supplied red LUT center is 664.604 nm versus the L1C hyperangular center 664.564 nm. At benchmark bin [260,303], Csca is 445.084/97.5903 µm², Qext is 2.10898/2.18092, and omega is 0.99999665/0.99999826. Number fractions 0.910278/0.089722 give scattering weights 0.978845/0.021155. At [254,261], fractions 0.550646/0.449354 give weights 0.813385/0.186615. Actual LUT optics are used rather than the user's permitted visible omega=1/Qext=2 approximation. Efficiency values are dimensionless despite erroneous µm² efficiency-unit attributes in this LUT.

The public product encodes an absent second mode as all three mode-1 fields missing with mode-0 fraction exactly one. Handle that case explicitly. Other incomplete modes and non-unit active fraction sums (tolerance 1e-5) are rejected without repair. Raw retrieval values and metadata-derived quality flags remain inspectable.

## Dashboard and exports

Enable **RFT refl.** for the thick-cloud mixture and **RFT component** for its additive contributions. **RFT P12** shows the unweighted full A/B/C mode responses as a separate dotted comparison. These dotted curves do not sum to the thick-cloud curve. Enabling either mode display also enables RFT refl. and selects −Q/scattering-angle axes. Number/Csca weighting is fixed in the dashboard, including imported recipes.

The palette separates blue/orange branch-1/2 observations, charcoal cloudbow, magenta RFT mixture, teal dashed mode 0 and violet dash-dot mode 1. Mode curves draw above the solid mixture with a white outline, making nearly coincident curves distinguishable without changing their values. Observation markers draw last. PNG/PDF exports use the same palette, line styles and layer order.

The residual panel shows **Cloudbow − observed** and **RFT refl. − observed** on the same branch-1 source views and actual scattering angles, in the displayed −Q convention. Support is the intersection of model angular domains and configured cloudbow/RFT intervals. Cloudbow predictions use stored coefficients; RFT predictions use the thick-cloud formula and exact source geometry at the observation angles. No residual retrieval is performed on branch 2; it is a sanity-check observation view. Residuals are hidden when branch 2 alone is selected. Missing one model does not suppress the other's residuals. Export JSON records the common support, source views, predictions, residuals and RMS in `polarimetric_residuals`.

API: `GET /api/bin/254/261?rft=true`. Library: `scene.diagnostics([254,261], rft=True)`. `thick_branches` supplies the dashboard mixture/contributions and residual predictions; `branches` supplies the unchanged A/B/C-transformed modes. Both expose scientific arrays without display clipping. Export JSON includes both and records the thick model in its provenance.

Launch:

```bash
pace-l1c serve --manifest data/manifests/development.json --case science_scene \
  --mie data/reference/MiedBaseE4_Parm_HARP2_LR.nc
```

The cached registered GPC is supplied automatically by the manifest. The existing optional atmospheric cache can be retained at launch; all source observations and these model comparisons remain TOA.

Save a dashboard recipe and export with:

```bash
pace-l1c export --manifest data/manifests/development.json --case science_scene \
  --mie data/reference/MiedBaseE4_Parm_HARP2_LR.nc \
  --recipe outputs/rft-number-recipe.json --output outputs/rft-contrast
```

Python/CLI retains explicit literal and area fraction interpretations for legacy analysis, outside the dashboard. Older saved RFT recipes lacking the weighting field restore/export as literal through `Recipe.from_dict`. Recipes explicitly requesting removed coefficient refitting are rejected with an actionable error; they are not silently replayed using different coefficients. Dashboard imports use the user's fixed current policy of number weighting and original coefficients.

## Scientific limits and audit evidence

[GPC ATBD V1](https://oceandata.sci.gsfc.nasa.gov/files/atbd/atbd-obdaac-cloud-GPC.pdf), pp. 5–6, Eq. 2 specifies scattering-cross-section-weighted normalized phase matrices. Section 2.1.3 describes an RFT area distribution, but the output modal fraction conversion is not explicit; the user subsequently confirmed number fractions as the intended interpretation. The ATBD confirms selection of the longest continuous cloudbow angular stretch. Branch-1 residuals follow the user's requested evaluation convention; source-view branch mapping is still the documented heuristic.

Exact operational LUT/spectral response and phase-matrix normalization remain unverified. The supplied LUT has P21 but no full P11 phase function for a complete normalization audit. The reference and ATBD also differ in background basis: the supplied script uses B*(cos²−1)+C, while ATBD Eq. 4 writes B*cos²+C. Their offsets differ by B. The existing supplied-script basis is retained, without silently modifying stored C. These curves are experimental reconstructions from reported mode re/ve using the supplied gamma-distribution LUT, not validated reproduction of the operational nonparametric RFT distribution.

The 2026-10-16 single-mode audit ruled out an extra multiplicative factor: substituting identical microphysics yields exactly identical full RFT/cloudbow curves. At [201,391], RFT re/ve=9.802734 µm/0.0512759 versus cloudbow 9.565864 µm/0.0437933. The full RFT main-bow peak is ~0.472% higher; differences change sign with angle. Phase-only components were lower because they omitted the shared background. Among all 11,640 quality-passing single-mode bins, RFT variance is larger in 89.97%; median variance ratio is 1.4867. In a deterministic 500-bin sample, phase main-bow peak ratios p10/median/p90 are 0.98870/1.00038/1.00774, with 46.2% below one. This does not establish agreement at all angles or operational distribution reproduction.

Float64 interpolation/forward arithmetic fixes float32 log-coordinate boundary rejection and ~1e-8 rounding inconsistencies without changing scientific normalization or extending LUT support. Tests cover exact endpoints, single-mode identity, weighted full-response closure, missing quality/coefficients/optics, old recipe behavior, refit rejection, named branch-1 residual support/sign, and API/export consistency. Current generated artifacts remain under ignored outputs; source data/LUTs are never redistributed by default.

## Remaining low-bias audit (2026-10-26)

A deterministic sample of 200 bins, evenly indexed among 34,556 same-scene passing RFT+cloudbow-quality candidates, retained 200 bins/925 branch-1 main-bow observations (137–150°, model and observed −Q >0.005, at least three views/bin). Binwise median model/observed ratios have p10/median/p90 0.4790/0.5602/0.6504; 99% of retained bins have ratios below one. Pooled mean model-minus-observed is −0.0201954. This is a positive-main-bow sample, not a claim about all bins/angles. Diagnostic least-squares fits of observed to thick-model amplitude plus constant/cos² background gave amplitude p10/median/p90 1.0374/1.3608/1.5019. These regressions audit shape versus smooth background only; they are not dashboard refits or a proposed universal multiplier. Script/results remain ignored at outputs/audit_thick_bias.py and outputs/thick-bias-audit.json.

Saturation with optical depth does not establish that the absolute polarized signal equals first-order scattering. Forward-directed multiple scattering can preserve cloudbow structure while increasing amplitude; Alexandrov et al. (2012), section 8 explicitly demonstrates this [in the primary paper](https://ntrs.nasa.gov/api/citations/20150000170/downloads/20150000170.pdf). This is a leading physical explanation, not a scene-specific quantitative attribution established by this audit. Other differences include TOA molecular/background contributions and approximate RFT gamma-mode reconstruction. No missing universal pi/two multiplier has been established, and no empirical scale was applied.

The GPC `cloud_optical_thickness` field is available at the registered original bins, units 1, long_name "Cloud optical thickness obtained from AUX file." It is auxiliary input, not inferred here from RFT; its underlying retrieval provenance/quality needs checking before finite-thickness production use. At [363,311], tau=19.45853 and exact branch-1 beta=(1/mu0+1/mu) is 2.2158–2.3174, so exp(-beta*tau) is 2.6e-20–1.9e-19: the finite-thickness bracket is indistinguishable from one in float64. Of the 200 sampled bins, 195 have finite nonnegative auxiliary tau, with p10/median/p90 3.3224/8.9831/15.5746; five are missing. The finite bracket 1-exp(-beta*tau) only reduces pure single-scattering predictions, so it cannot repair the observed low bias. No finite-thickness control/model change was implemented by this audit.

## Fractional droplet-addition audit after Rayleigh (2026-10-26)

Read-only diagnostic script outputs/audit_rft_fractional_addition.py reused the deterministic 200-bin sample with the approved atmospheric cache. 198 bins/2,859 branch-1 observations (135–165°) were retained; two bins had incompatible cached cloud boundaries and were rejected explicitly. The positive main-bow subset contained 914 observations (137–150°, cloud and observed −Q >0.005, at least three samples/bin). The combined cloud+Rayleigh prediction remained low in 97.98% of retained bin median main-bow ratios; model/observed p10/median/p90 were 0.5389/0.6435/0.7558.

Diagnostic hypothesis: observed ≈ (1+epsilon)*D + R, with D the sum of weighted thick-cloud droplet contributions and R the fixed existing above-cloud Rayleigh path. Per-bin least-squares epsilon over 135–165° had p10/median/p90 0.3929/0.6017/0.8135. Main-bow-only epsilon was 0.3812/0.5806/0.8339. Median per-bin RMS decreased from 0.011641 to 0.005546; median removed squared residual energy was 73.26%. Those are in-sample per-bin diagnostic coefficients, not validated physical second-order probabilities.

A single epsilon=0.60107 estimated from alternating 99 training bins reduced pooled RMS on the other 99 bins from 0.012136 to 0.007980 (34.24%). This split is within the same scene and not independent-scene validation; spatial dependence can remain. If a constant/cos² background is also allowed diagnostically, droplet scale p10/median/p90 becomes 1.0445/1.3601/1.5021, and background at 145° is 0.00158/0.00639/0.01229. Median per-bin RMS then becomes 0.002963. Thus a common fractional addition explains a substantial cloudbow-shaped error, but it also absorbs smooth background when used alone. It is not a complete explanation or universal multiplier. Results are preserved under ignored outputs/rft-fractional-addition-audit.json. No fit/control/scale has been added to the dashboard, and original observations/weights/coefficients are unchanged.

The phase-preserving forward-scattering mechanism is consistent with Alexandrov et al. (2012), section 8, but data resemblance alone does not identify its magnitude or scattering order. A scalar repeated-phase term approximates narrowly forward-directed paths; general second-order vector scattering includes angular integration and reference-plane rotations. The extra fraction cannot be derived from P12 alone: forward P11 and transport/path information are needed for a physical estimate. Remaining omitted effects include smooth multiple-scattering background, cloud attenuation by the overlying molecular layer, cloud–molecular coupling, subpixel/3-D/vertical structure, and differences between operational RFT distributions and the two reconstructed gamma modes. Attenuation/finite-thickness terms generally lower the cloud-only prediction and should not be presented as solutions to the low bias.

## Cornet 3DMCPOL scattering-order figure (user-supplied paper, 2026-10-26)

Verified directly in the supplied Cornet, C.-Labonnote & Szczap (2010), DOI 10.1016/j.jqsrt.2009.06.013, HAL hal-01971907v1. Figure 9(c–d), PDF page 12 in the supplied HAL version, compares cumulative scattering-order contributions across X (km) for a step cloud. Setup: solar zenith 60°, view zenith 30°, relative view azimuth 180°; optical thickness 0.5/10 for the order comparison. Panel c (total) has not converged at roughly twenty orders; panel d (polarized magnitude) is essentially converged by four. The plotted curves are cumulative through the indicated order, not isolated individual-order contributions. Away from the step in the thick region, visually approximate panel-d reflectances are ~1.0% first order, ~1.5% through second, and ~1.9% final: second order adds a substantial part of the enhancement, with third/fourth still contributing. The paper's section 5.3 explicitly discusses this low-order convergence.

This strengthens the physical motivation for a low-order, approximately phase-preserving correction rather than treating the deficit as arbitrary high-order background. It does not directly calibrate the liquid-cloudbow enhancement: the example uses cirrus/IHM optical properties and polarized magnitude at one geometry. Figure 8 (PDF page 10) provides angular dependence (view azimuth for several view zeniths) of total/polarized reflectance, but does not decompose by scattering order. Figure 9 itself is spatial, not angular. Neither figure directly supplies Q_order(theta) for liquid droplets at 135–165°. No dashboard/model change was made from this reference check. Author's HAL version: https://hal.science/hal-01971907v1 ; user-supplied reference preserved unchanged.

### Fixed four-order trial check

Repeated the same deterministic 200-bin audit with the explicit fixed gain 1.61 and unchanged Rayleigh, no fitted parameters. The same 198 bins/2,859 branch-1 observations passed; two were rejected for incompatible cloud boundaries. Main-bow support remained 914 samples. Bin-median model/observed ratios (137–150°, positive support) changed from p10/median/p90 0.5389/0.6435/0.7558 to 0.8319/0.9837/1.1567. Pooled full-interval RMS (135–165°) fell from 0.0121876 to 0.00777467 (36.21%); mean model-minus-observed changed from -0.00746030 to -0.00254272. Per-bin RMS improved in 91.92% of pixels. 58.08% of bin main-bow median ratios remained below one, versus 97.98% before. Median per-bin RMS fell from 0.0116410 to 0.00610474. The previous alternating 99-pixel test subset had RMS 0.0121361 -> 0.00799028. These are same-scene comparisons after discussing the earlier sample, not independent validation or proof of the individual scattering-order weights. No per-pixel retuning was performed. Read-only audit: outputs/check_rft_four_orders.py; complete metrics: outputs/rft-four-orders-check.json.

Interactive scattering-angle plots (main polarization and residuals) start at 130–180°; no source data are filtered by that initial viewport. Zoom out/Autoscale can expose side-scattering, Reset axes restores the initial range, and toggling overlays preserves interactive zoom. Sector-angle plots still autorange. This browser-only viewport does not change Python scientific export limits.
