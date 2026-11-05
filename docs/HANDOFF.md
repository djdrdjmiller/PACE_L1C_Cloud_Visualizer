# Current implementation handoff — 5 November 2026

This is the current working contract for the implemented **PACE L1C · Quicklook Dashboard**. It replaces the original build-from-scratch prompt. [STATUS.md](STATUS.md) separates measured verification from gaps. [SCIENCE.md](SCIENCE.md), [RFT.md](RFT.md), and [ATMOSPHERE.md](ATMOSPHERE.md) describe actual algorithms. Original requirements and superseded decisions are preserved in [history](history/HANDOFF-2026-10-16.md); they do not authorize restoring removed features.

## What exists

A reusable Python package (`src/pace_l1c`), loopback FastAPI service, TypeScript/Vite/Plotly frontend, bounded Earthdata discovery/download/cache utility and Python PNG/PDF/JSON exporter. The service can launch scene setup without science inputs, discover/acquire a bounded user-selected OCI/HARP2 pair and optional GPC/cloud/MET inputs, or open existing/cached files. Registered GPC scalars now work without Mie. Optional local Mie/atmosphere files remain supported. The release wheel bundles the frontend. Remote Mie and user keys were deferred; web hosting remains separate.

Three linked maps show selectable OCI total/OCI phase/operational or calculated LI on the left, HARP2 total reflectance, and HARP2 polarized magnitude/DoLP/signed scattering-plane reflectance. Source measurements are original L1C, not the synthetic mockup. Default crop bounds valid default HARP2 RGB support. Plate Carrée, regional equal area and native source-swath displays share original-bin selection. Geographic preview cell IDs preserve selection without regridding science arrays.

Projection is first in the sidebar. OCI RGB targets are edited below its map; default library targets remain 645/555/443 nm, while a saved session may use another choice (including 450 nm blue). Imagery labels show measured wavelengths/nominal angles without dataset view indices; full indices remain in provenance/advanced controls. The correction note is concise and mode-specific. A discrete nominal-angle slider sits below both HARP2 maps; manual source dropdowns override/disable it and can be cleared. Scattering-angle contours belong only on the HARP2 maps; regular labels follow contours. Beauty is a fixed adjustable display recipe, not automatic physical correction.

The liquid-index workspace now sits beside the cloudbow/RFT workspace, with OCI spectra moved below both (2026-10-27). It shows observed red TOA reflectance, off-bow baseline windows, a 135° normalization reference, discrete or optional trapezoidal excess/cumulative LI, and comparison with reported GPC. Left-map choices include GPC LI plus calculated discrete/trapezoidal LI using the workspace quantity/branch. See [LIQUID_INDEX.md](LIQUID_INDEX.md) for estimator/support rules, first-calculation cost and unresolved operational parity. The aligned multiangular panel shows only the metadata-derived red hyperangular band, discrete observations and branch/quantity/axis menus. Cloudbow, RFT refl., RFT component and RFT P12 checkboxes occupy their own row below menus. Plot dimensions do not change when overlays toggle; a distinct palette, patterned outlined mode curves, boxed axes/ticks/light grids and separated legends aid comparison. The hover toolbars for spectrum, polarization and residuals sit inside their plotting axes; fixed-width Plotly buttons avoid inheriting the app’s full-width form-button style. Interactive scattering-angle plots initially span 130–180°; zoom out/Autoscale retains access to all source measurements, Reset axes restores the initial range, and overlay toggles preserve zoom. Nominal-sector axes remain automatic.

Cloudbow and RFT P12 use stored same-bin C/B/A. RFT refl. and RFT component use the user-authorized thick-cloud formula, omega=1 and actual geometry without A/B/C, now enhanced by fixed order weights [1,0.5,0.1,0.01] (gain 1.61) as an explicit phase-preserving trial; Rayleigh is added separately and not enhanced. Components use normalized number-fraction*Csca weights. With the boundary cache, RFT refl. also adds the existing above-cloud molecular −Q path once; droplet components plus a separate amber Rayleigh contribution sum to that total. Without a cache the curve is explicitly cloud-only; invalid supplied cloud boundaries disable the total. See RFT.md. Native LUT P21 declares sr^-1, but an independent Mie check supports dimensionless values for the supplied LUT hash; this audited override uses 1/[4*(mu0+mu)], with evidence in RFT.md/provenance. Full P11 integral remains unverified. See RFT.md for formula, limitations and recipe behavior changes. Named residuals compare cloudbow/thick-RFT minus observed on identical branch-1 TOA samples. Branch 2 is a sanity check, not a second retrieval.

## Correction status

On 2026-10-26 the user authorized wavelength-dependent molecular depolarization while leaving multiple scattering separate. Maps and the RFT above-cloud contribution share the versioned Bates/Bodhaine dry-air phase elements and consistent optical depth. Boundaries, land policy and frame/F0 conversions are unchanged. This replaces the ideal phase matrix/Hansen–Travis polynomial; old Rayleigh artifacts will not replay bit-identically with the current model. See ATMOSPHERE.md for constants, sources and unverified refractivity extrapolation above 1690 nm.

TOA is the code default. One **Atmospheric Correction** dropdown selects TOA or experimental Rayleigh for both total and polarized imagery together. The browser writes `correction=rayleigh` with `polar_rayleigh=true`, or TOA/false. Saved/imported older independent Rayleigh choices become the shared Rayleigh setting if available; legacy transmission-only choices become TOA. The Python/API still supports independent fields and legacy transmission for historical recipe reproduction, outside the dashboard. Rayleigh now applies to classified land and water in the live dashboard and exports; the user approved promoting the unchanged [land trial](LAND_RAYLEIGH_TRIAL.md). Unclassified bins remain TOA. Missing/unsupported classified corrections stay missing without TOA fallback. No new terrain model, pressure adjustment, gap fill or transmission is applied to land. Angular observations, spectra, fits and residuals always remain TOA. These are visualization experiments, not validated atmosphere-free reflectance products. Preserve the user-approved MERRA-2/OCI cloud boundaries; consult before introducing a new model or source.

The surface-transmission extension to 1050 hPa was retired on 19 October. UI state/imports force `extrapolate_surface=false`; default recipes are false and recipe validation rejects true. Old CLI/export recipes with true need an explicit edit and produce different transmission coverage; do not claim bit-identical replay. The analytical Rayleigh pressure limit is a separate unchanged bound. Internal legacy extension calculations/tests are retained as historical research code, unreachable through a validated enabled recipe.

Do not continue atmospheric-model research now. The hosted demonstration should use only TOA/experimental Rayleigh options, with the existing pressure fields and classified land+water correction; only unclassified areas bypass Rayleigh. Neither new delivery variant should require or distribute the transmission LUT. Rayleigh preparation/loading is independent: `atmosphere-prepare --mode rayleigh` uses OCI CLD and declared MET PS only; `atmosphere-extract-rayleigh` copies audited boundary/classification fields from a legacy cache. New versioned Rayleigh-only caches omit transmission/humidity arrays. Capability flags disable unavailable Rayleigh in the shared dropdown; API requests for unsupported transmission still reject. See ATMOSPHERE.md for commands and cache provenance/replay rules.

## Land policy, migration and provenance

`Recipe.rayleigh_land=true` is the new library default, included in `/api/scene` defaults and cache keys. The browser forces true on startup/import, and the single correction dropdown applies total/polar Rayleigh together. For Python/API/export compatibility, `Recipe.from_dict` treats old Rayleigh recipes lacking this field as false (water-only); explicitly include true for the new behavior. Old explicit false remains supported outside the UI. Raw API requests missing this field follow that compatibility rule.

PNG/PDF scope labels and `rayleigh_land_policy` provenance identify actual land total/polar behavior. Coverage records water/land corrected bins separately from land-TOA and unknown-TOA bins. Legacy transmission-only leaves land TOA; combined mode corrects land with Rayleigh only, never the transmission table. Sources/fits/residuals remain TOA in every mode. New cache metadata describes surface classification without hard-coding correction behavior; older cache `land_policy` strings are historical source metadata, not a current mask instruction. The current copied cache has the same scientific arrays and a new provenance hash; preserve original files for old replay.

## Launch, acquisition and export

See the root README for portable environment setup and [TOOLS.md](TOOLS.md) for the exact current command/API inventory. Existing local benchmark launch:

```bash
pace-l1c serve --manifest data/manifests/development.json --case science_scene \
  --mie data/reference/MiedBaseE4_Parm_HARP2_LR.nc \
  --atmosphere data/atmosphere/scene-rayleigh-land.nc
```

Omit optional Mie/atmosphere arguments for the L1C core. The complete matched GPC entry is selected from the manifest when `--mie` is supplied. No Earthdata login/network is needed to view already cached files. Do not include this machine's private paths/data in a distribution.

## Next delivery tracks

1. [Fixed-scene hosted demonstration](handoffs/FIXED_SCENE_WEB.md): the current 20251002T182635 scene, Rayleigh-only experimental correction, original sampling, linked diagnostics, optional private-service Mie access. Host deployment is not implemented or authorized by writing this brief.
2. [Shareable locally deployed GitHub tool](handoffs/SHAREABLE_LOCAL.md): implemented and published as v0.1.0 at `djdrdjmiller/PACE_L1C_Cloud_Visualizer`, with user-granule discovery/acquisition, wheel setup and no transmission-table dependency. Apache-2.0 was already chosen in the target repository; the user authorized source publication. Remote Mie/user keys are deferred; local authorized files remain optional.

Shared [remote Mie guidance](REMOTE_MIE.md) defines the proposed provider contract and Drive/server options. Keep shared science semantics common across tracks. Each future agent should work in its own branch/worktree and report changes to interfaces; neither should overwrite the other's work or change cloudbow/RFT physics as a deployment shortcut.

## Acceptance and remaining evidence

Run the pinned Python suite and frontend TypeScript/build checks. Retain meaningful synthetic tests for metadata permutations, radiometry/rotations, source selection, geometry, acquisitions/budgets, LUT interpolation/weights, residual support, and export pixels/page sizes/provenance. Real benchmark alignment, metadata sectors, native reconstruction and earlier click/export checks are recorded in STATUS. Recheck maps/selection/exports when those paths change.

Dateline/high-latitude real-pair verification remains deferred to the end. Operational cloudbow/LUT conventions remain unresolved and are not the immediate delivery priority. Do not relabel experimental reconstructions as operational or claim full release acceptance/hosted CI/clean-clone install based on local tests. Preserve raw/reference assets and hashes; never execute supplied notebooks/scripts. There is no authorization to delete data, upload LUTs or publish a remote in these handoffs.


LI branch clarification: all LI calculations/maps now use branch 1 only. The LI branch-2 option was removed; separate polarization-panel branch-2 observations remain available. Adaptive missing values can occur despite coverage of 135°: the boundary requires crossing the horizontal reflectance level L(135°), not merely observing that angle.

Adaptive LI bounds clarification: integration is restricted to 130–150°. Use a horizontal-reference crossing inside the window or cap at its edge; no endpoint extrapolation. This supersedes the initial unbounded-crossing experiment. Endpoint kind is explicit in plots/provenance.


## Separate granule-statistics project

The user requested a handoff for a separate dashboard showing full-granule cloudbow, RFT and LI distributions for 20251002T182635. See the separate statistics dashboard brief (retained only in the development checkout). It includes exact local input identities, metadata-derived fields/QA/glint flags, finite-count checks, branch-1-only LI semantics and acceptance criteria. This brief does not implement or launch the new project.

Statistics-handoff clarification: conditional distributions are core scope, including LI split by the GPC glint warning, arbitrary cloud-optical-thickness ranges and joint conditions. The brief distinguishes binary warning from a future verified continuous geometry metric, and specifies cohort denominators, missing conditions and avoidance of LI censoring by retrieval-success filters.


Render responsiveness update (2026-10-27): expensive native derived maps cooperatively cancel on a newer render generation from the same browser or client disconnect. Browser render requests carry optional client_id/generation; these are request-control metadata, not recipe/science/cache identity. Partial results are never cached. Keep HDF5/Matplotlib serialization. A pending left map shows the previous image dimmed with an updating note; only the latest response is applied. Regression tests are in tests/test_render_cancellation.py.


## Shareable-version cleanup — 2026-11-05

The current map selector targets the left panel (`left_mode`); HARP2 total remains middle and HARP2 polarimetry right with shared sectors. Wider/adaptive LI and baseline-angle controls/maps/calculation paths are retired from quicklook, with original narrow discrete/trapezoidal LI preserved. The left angular panel also offers observation-only DoLP; integration is disabled there and calculated LI maps retain their reflectance quantity. The statistics navigation link is removed; its independent project is unchanged. Legacy LI helper routines remain for statistics/history only. Recipe migration/export behavior is in LIQUID_INDEX.md. The updated SHAREABLE_LOCAL.md is the next-chat brief for GitHub staging, portable install, user granule-ID selection and bounded paired/ancillary acquisition; none of those future capabilities is claimed complete.

## Shareable implementation — 2026-11-05

The user approved the discovery prototype, requested the same design as the existing quicklook, and authorized code publication to the existing public Apache-2.0 repository. `serve` now launches setup without granules; `discovery.py`/`launcher.py` implement bounded producer-filename/CMR-ID and date/bbox searches, explicit candidate/revision review, Earthdata session/opt-in remembered login, streaming imports/downloads, cancellation, persistent failed-byte budgets, saved source hashes, and native-grid verification before opening. Existing atmosphere/cloud/MET routines provide optional Rayleigh preparation under a separate ceiling; unsupported optional data leave a saved TOA core with warnings. No new science model/source was introduced.

`RegisteredGPC` separates reported fields/LI from optional phase-library overlays. All three maps, retained LI definitions, TOA observations, source-hit identity and Rayleigh land policy remain unchanged. Setup and viewer share the original stylesheet and approved µCloud branding. The frontend is bundled into wheels; source builds use the pinned frontend lock. CI checks the package on fresh platform runners before releasing a new version. Refer to STATUS for actual execution evidence; configured CI is not evidence of a passing hosted run.

Earlier preparation sections saying arbitrary-granule setup is unimplemented or remote Mie is mandatory are superseded by this section and the user's deferral. Private libraries, reference snapshots, real products and the independent statistics project are excluded from publication.

## Authorized fixed-scene showcase implementation — 2026-11-05

The user requested a public fixed-original-scene demo and chose a static showcase with marked examples, then requested selectable markers on the maps. This supersedes the earlier hosting-not-authorized brief for this finite scope. `showcase.py`/`scripts/build_showcase.py` use the existing science/rendering code without a Mie library; the independent `showcase.html` frontend links twelve numbered original bins across all three maps and TOA diagnostics. Six pre-rendered presets preserve actual source sectors and existing land+water Rayleigh semantics. No arbitrary-bin Python backend, remote LUT or private phase outputs are provided. GitHub Pages deploys only the hash-declared derived-data release archive using the manually dispatched showcase workflow. See STATUS for actual deployment evidence and remaining limitations.

Beauty quicklook is the scene/browser startup display choice; Recipe replay and saved explicit selections remain compatible. Scene-setup warnings distinguish missing supported cloud inputs from an exceeded ancillary candidate ceiling; optional missing GPC is not a core-L1C failure.
