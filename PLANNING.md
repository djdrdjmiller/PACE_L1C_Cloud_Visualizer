# Current decisions and roadmap — 19 October 2026

The local PACE L1C dashboard is implemented. Use [docs/HANDOFF.md](docs/HANDOFF.md) for the current contract, [docs/STATUS.md](docs/STATUS.md) for evidence and gaps, and [docs/TOOLS.md](docs/TOOLS.md) for actual interfaces. The original discovery/scientific planning and detailed source links are preserved in [the historical decision record](docs/history/PLANNING-2026-10-16.md). Its unimplemented/future-tense and refitting/transmission instructions are historical, not current requirements.

## Settled current behavior

- Python science library/local service, three original-bin maps, synchronized TOA spectra/red hyperangular measurements, source-aware native/geographic display and reproducible PNG/PDF/JSON exports.
- Metadata-derived channels/sectors, shared HARP2 crop/slider/manual override, independent scientific and display transforms, OCI channel controls under its map, boxed fixed-size diagnostic axes and overlay controls below menus.
- Experimental stored cloudbow and RFT reflectance reconstruction, fixed reported modes, user-confirmed number fractions times bulk Csca normalized, original cloudbow C/B/A only. Full mode responses include common A/B/C. No coefficient refitting or phase-only plot feature. Branch-1 named model residuals; branch 2 observation sanity check.
- Authorized experimental analytical Rayleigh correction of total/polarimetric maps over classified land and water, based on approved unchanged OCI cloud/MERRA-2 boundaries; unclassified remains TOA and unsupported classified corrections remain missing. The successful offline land trial was explicitly promoted by the user to production. Source diagnostics/fits remain TOA. Further atmospheric-model development is parked.
- Surface transmission extrapolation to 1050 hPa is retired; default off, UI enforces false, enabled recipe requests reject. Rayleigh's separate pressure support is unchanged. Legacy transmission research remains local; no transmission tables in either new distribution.
- Preserve supplied snapshots/provenance without executing reference actions. No large data, private LUTs, credentials or generated outputs in Git. Public target: `djdrdjmiller/PACE_L1C_Cloud_Visualizer` (user-created; checked 2026-11-05). Resolve license/data rights and publication authorization before uploading.

## Delivery priorities

1. Documentation/tool/agent-instruction cleanup for the existing implementation, with measured tests and limits rather than an additive contradictory decision log.
2. [Fixed-scene web implementation](docs/handoffs/FIXED_SCENE_WEB.md): current benchmark scene, Rayleigh-only correction options, web-safe serving/assets and original sampling. Hosting/provider/audience/cost decisions precede any external deployment.
3. [Shareable local repository implementation](docs/handoffs/SHAREABLE_LOCAL.md): user granule-ID acquisition, portable install/launch/export, private remote Mie query access, no transmission-table requirement. Repository publication remains a separate owner-authorized step.
4. Real paired dateline/high-latitude acceptance, deferred by the user to the end. Synthetic checks do not close this gap. Operational cloudbow/LUT reconstruction verification remains documented and outside the immediate delivery focus.

Tracks 2 and 3 share science/provider/cache contracts but are distinct deliverables. Independent Rayleigh-only cache preparation/loading and extraction are implemented; both should reuse that path rather than introduce another cache/model. [Remote Mie design](docs/REMOTE_MIE.md) recommends a private query service, with Google Drive or server storage behind it; it is not implemented yet. Do not silently turn a full-file public download into a private-value service.

## Scientific references and unresolved conventions

Current conventions and original sources are described in [SCIENCE](docs/SCIENCE.md), [RFT](docs/RFT.md) and [ATMOSPHERE](docs/ATMOSPHERE.md). Detailed original references remain in the archived planning record, including PACE L1C normalization, NASA native grid implementation, supplied reference/LUT metadata and the HelpHub Rayleigh tutorial.

Keep experimental labels: current cloudbow/RFT LUT identity/spectral response/phase normalization, stored B/C background basis versus ATBD, and operational branch mapping are unresolved. Single-scattering Rayleigh includes authorized wavelength-dependent molecular depolarization with consistent Bates/Bodhaine optical depth; aerosols, multiple scattering, bandpass integration and cloud/surface coupling remain absent. See ATMOSPHERE.md for fixed dry-air constants and unverified SWIR extrapolation. Visual appeal and numerical unit tests do not establish quantitative atmospheric-correction accuracy. Discuss new models or source assumptions with the user before implementation.

Implemented 2026-10-27: the [liquid-index workspace](docs/LIQUID_INDEX.md), GPC left map and own discrete/trapezoidal left maps use original hyperangular TOA sampling. The user authorized trapezoidal integration as an explicit alternative to the ATBD-style discrete estimator. Baseline normalization follows the 135° reference illustrated in the original paper; operational equivalence remains unverified.

Current scope update (2026-11-05): the shareable quicklook cleanup retires wider/adaptive LI and baseline-angle features, keeps original narrow discrete/trapezoidal LI, and adds observation-only DoLP to the left angular inspector. Auxiliary maps replace the left OCI view; HARP2 total stays middle and shares sectors with right polarimetry. Statistics navigation/capabilities are deferred outside this version. Granule-ID selection/download, portable local setup and GitHub staging are the next-chat requirements in docs/handoffs/SHAREABLE_LOCAL.md, not implemented capabilities.

Preparation review, 2026-11-05: installation should require no granule; a proposed launcher opens a setup screen for granule acquisition/local files/cached scenes. Recommend a wheel with built frontend, then consider platform-specific bundles. Current serving still requires a loaded pair. Private authenticated Mie queries remain the recommended table-protection design; local decryption cannot guarantee secrecy from recipients. See the updated [local handoff](docs/handoffs/SHAREABLE_LOCAL.md) and [protection comparison](docs/REMOTE_MIE.md). These are recommendations, not implemented capabilities.

Implementation update, 2026-11-05: approved local discovery/setup is integrated with the current quicklook design. Remote phase-library service/user keys are deferred; local library remains optional. The user authorized audited code publication to the existing public Apache-2.0 repository. See README/STATUS for delivered commands, actual checks and remaining gaps.
