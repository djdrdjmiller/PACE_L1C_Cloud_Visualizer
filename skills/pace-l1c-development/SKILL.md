---
name: pace-l1c-development
description: "Develop or review PACE OCI/HARP2 L1C readers, linked imagery, polarimetry, acquisition and reproducible exports while preserving source sampling and scientific provenance."
---

# PACE L1C development

Use this repository skill for scientific readers, scene acquisition, map rendering, selected-bin diagnostics and exports. Read [the current handoff](../../docs/HANDOFF.md), [science conventions](../../docs/SCIENCE.md) and the relevant [RFT](../../docs/RFT.md) or [atmospheric](../../docs/ATMOSPHERE.md) document. [PLANNING.md](../../PLANNING.md) links historical source/convention detail; historical instructions do not override current policy. No global skill installation is needed.

## Readers and radiometry

Inspect NetCDF groups, dimensions, units, fill/scale metadata, source grid/time and processing version. Preserve view identity and singleton spatial axes; slice bands before materializing cubes. OCI selects one valid observed slot, never averages empty/ambiguous slots. Do not invent irradiance or Earth–Sun distance defaults.

Reflectance is pi*r²*X/(F0*cos(solar zenith)), with actual geometry and separate intensity/polarization irradiances. Keep canonical Stokes, scattering-plane rotation, magnitude, DoLP and negative signed display transforms distinct. Validate independently calculated normalization/rotation examples. Do not clip scientific arrays to image limits.

## Registration and display

Verify paired metadata and full geolocation. Projected source-cell hit IDs preserve original bin selection under crop, preview size and missing data. HARP2 maps share source sectors but have quantity-specific stretches. Use sparse-band anchors and metadata-derived matching channels; report actual angles and mismatch. Diagnostics plot only the metadata-derived red hyperangular band as points; all samples remain available in the API.

## Implemented research extensions

Stored cloudbow/RFT are authorized experimental reconstructions. Follow RFT.md: fixed reported microphysics and number fractions; normalized fraction*Csca weights; original same-bin C/B/A for cloudbow and RFT P12. User-authorized RFT refl./component use optically thick single scattering, omega=1 and actual geometry with declared phase-unit normalization, without A/B/C; the subsequent user-prescribed order weights [1,.5,.1,.01] give fixed droplet gain 1.61, with separate Rayleigh unscaled. This is a phase-preserving proxy, not resolved vector RT (see RFT.md). RFT component displays weighted thick-cloud contributions plus a separate above-cloud Rayleigh path (when the existing cache supports it), summing to RFT refl.; RFT P12 displays separate unweighted full A/B/C-transformed responses, not raw phase-only curves. Do not mix those two prediction types; exact source geometry drives thick-model residuals. No new fitting, peak normalization or phase-only plot controls. Compare named cloudbow/RFT residuals on the same branch-1 TOA samples only. Report unresolved operational LUT, background basis, normalization and branch identity.

Analytical total/polarimetric Rayleigh map correction is authorized and implemented, over classified land and water with TOA diagnostics and unclassified-only TOA bypass. Unsupported classified corrections remain missing; do not silently use TOA. Land uses unchanged cloud-top/MERRA-2 surface boundaries and Rayleigh equations from the approved trial. `rayleigh_land=true` is the new/browser default; preserve explicit legacy `false` when replaying older Python/API recipes, but do not restore a water-only dashboard control. Legacy transmission remains water-only even in combined mode (land gets Rayleigh only). Follow ATMOSPHERE.md and rayleigh.py for actual plane/irradiance conventions. Do not apply transmission LUTs to Q/U. Further atmospheric models/data assumptions require discussion with the user. The 1050 hPa surface transmission extension is retired; do not restore it. Rayleigh-only preparation/loading/extraction is independent of transmission/humidity; preserve capability flags and source/parent hashes when reusing it. Legacy transmission code/reference assets remain locally for provenance; new distributed variants must not require the transmission tables.

## Liquid-index diagnostics

Follow [LIQUID_INDEX.md](../../docs/LIQUID_INDEX.md) for the user-authorized TOA hyperangular-only LI workspace and native-bin maps. Use 120–130/150–160° baseline windows, 135–145° peak, a 135° fitted-baseline reference following original-paper Figure 4, default equal-view discrete mean and explicitly alternative trapezoidal angular mean. Preserve quantity/branch support, source-view IDs and missing reasons; do not tune to reported GPC. Operational parity is not verified. Calculated maps use the same scalar function in bounded row batches and remain independent of map anchor/atmospheric correction.

## Handoff and evidence

The approved 2026-10-26 molecular refinement uses wavelength-dependent Bates/Bodhaine dry-air depolarization in both Rayleigh phase elements and cross section/optical depth, shared by maps and RFT above-cloud addition. Keep existing pressure fields and rotations; molecular anisotropy is not multiple scattering. Preserve versioned constants/source provenance and explicit unverified SWIR refractivity extrapolation above 1690 nm. Do not restore the older ideal phase matrix or multiply the old optical-depth polynomial by an extra King factor. See ATMOSPHERE.md; old Rayleigh figures are not bit-identical under the new model.

Use the two briefs in docs/handoffs for future web/local delivery work; remote Mie querying is deferred; granule-ID acquisition and local scene setup are implemented with bounded catalog/transfer jobs. Preserve supplied snapshots without executing their notebook/script actions. Use synthetic tests plus recorded real granule checks, report measured performance honestly, and update STATUS when validation changes. Do not publish/upload or change data sharing from an implementation brief alone.

Current quicklook cleanup (2026-11-05): `left_mode` selects OCI total/phase/GPC LI/calculated narrow discrete or trapezoidal LI; HARP2 total stays middle and HARP2 polarimetry right, sharing sectors. Legacy `middle_mode` recipes migrate on import; retired extended/baseline modes reset to OCI total. Wider/adaptive LI and baseline-angle calculations are absent from quicklook (`extended=False`), but preserve independent legacy helpers used by statistics/history. Left DoLP is observation-only with disabled LI integration; never calculate LI from DoLP or change the retained reflectance LI-map quantity. Preserve export parity and original-bin hit identity. The statistics app/link is outside the current distributable scope. Follow docs/handoffs/SHAREABLE_LOCAL.md for the next implementation chat; granule-ID acquisition/UI is implemented; private remote Mie and user keys are explicitly deferred. Publication of audited code to the existing Apache-2.0 GitHub target was authorized on 2026-11-05.
