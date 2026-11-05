# Shareable GitHub/local dashboard

**Current update, 2026-11-05:** the user approved development and publication to the existing public Apache-2.0 repository. Bounded discovery/setup, wheel packaging and Mie-independent GPC reading are implemented; see README and STATUS for current commands/evidence. Remote Mie/user keys are deferred, with an optional local library only. The preparation brief below is preserved as design history; its future-tense/publication restrictions do not override the user’s later authorization.

Science update, 2026-10-26: reuse the current versioned Bates/Bodhaine wavelength-dependent molecular depolarization consistently in Rayleigh optical depth and phase elements, for both map removal and RFT above-cloud addition. Existing cloud/surface pressure, land policy and Stokes/F0 conversions remain. Do not restore the ideal phase matrix or add Rayleigh multiple scattering. Preserve model/constants provenance and unverified SWIR extrapolation above 1690 nm; see ../ATMOSPHERE.md.

Status: preparation brief updated 2026-11-05. The user has created [djdrdjmiller/PACE_L1C_Cloud_Visualizer](https://github.com/djdrdjmiller/PACE_L1C_Cloud_Visualizer); the GitHub connector reports public visibility, default branch `main` and repository size 0. This checkout has no configured remote or initial commit. Granule-ID acquisition/setup UI and a remote Mie service remain unimplemented. Read AGENTS.md, ../HANDOFF.md, ../TOOLS.md, ../SCIENCE.md, ../RFT.md and ../REMOTE_MIE.md first. Paths below are repository-relative unless stated otherwise.

## Installation and launch contract — preparation, 2026-11-05

Installation must not require a granule. Recommended first deliverable: a Python wheel containing the built frontend, with one launcher opening a loopback browser setup screen. Users should not need Node/pnpm to install a released build; those remain developer/build dependencies. This is a packaging recommendation, not a working wheel/launcher claim. Validate an isolated wheel install outside the source directory before documenting its install command. Keep source-checkout setup available for contributors.

The proposed user sequence is:

1. Install once, without science data, Earthdata credentials or private Mie access.
2. Launch to a setup screen without a preselected scene. Offer a granule producer filename/supported CMR ID, an existing local OCI/HARP2 pair, a saved cached scene, and a clearly synthetic demonstration.
3. For a new real scene, resolve/preview candidates and bytes, obtain Earthdata authentication only when required, then download on explicit action within budgets. Verify the pair before opening the existing dashboard. Optional-product failures must identify the affected capability.
4. Reopen a verified cached scene without reinstallation or Earthdata network access. New uncached Mie queries still require its separate service connection; unavailable model overlays must not prevent cached core observations/maps.

Current `serve` cannot launch empty: it requires explicit `--oci`/`--harp2` or a complete manifest pair before creating the app. Installation itself needs no scene today; the existing synthetic example can be used without NASA data. Implement the empty setup state separately from `Scene`, retaining explicit offline launch. Keep setup/progress outside scientific controls. Do not advertise a proposed command as implemented.

Current code gaps verified by inspection: `service.py` locates frontend assets relative to the source tree; `pyproject.toml` does not package them. `Scene` requires both GPC and a local Mie LUT when either is supplied, and the manifest CLI auto-selects GPC only with `--mie`. Separate registered scalar GPC support before promising Mie-independent operational LI. Granule-ID resolution, optional ancillary acquisition and remote-provider parity are separate implementation stages.

A later self-contained desktop bundle could remove the Python prerequisite, but requires OS-specific build/test work. [PyInstaller's documentation](https://pyinstaller.org/en/stable/operating-mode.html) describes bundling the interpreter and the platform-specific outputs. Choose supported platforms before committing to that release format. Start with the portable wheel path and measure clean-install behavior; no container runtime is required by this recommendation.

## Repository preparation boundary — 2026-11-05

Owner/name and current visibility are now known; do not ask for them again unless the user changes the target. Code license, citation authorship, third-party asset terms, permitted remote-query/derived-result use and actual push authorization remain unresolved. The user's present request authorizes local preparation and exploration, not uploading private data or provisioning hosting. GitHub stores the distributable source/releases; the dashboard executes locally. GitHub Pages cannot run this Python backend ([GitHub documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site)).

The index contains older staged additions, many current scientific files remain untracked, and HEAD is unborn. Do not publish the index as-is or use blanket staging. Audit current source plus build inputs and explicitly assemble the intended file set; exclude the independent statistics project, local launch assumptions, data/references/caches/outputs and private material from every release format. No complete secret/license/artifact audit has yet been performed. No remote was configured and no files were uploaded during this preparation review.

## Objective

Prepare the current dashboard/library as a reproducibly installed local tool that other users can clone, obtain their own chosen granules, launch locally and export figures. Keep scientific/display behavior intact. Large products, transmission tables, the private Mie LUT, credentials and machine-specific manifests must not enter Git, release assets, container images, source archives or CI artifacts.

The local app/library and bounded development-case acquisition already exist. Granule-ID-oriented acquisition, remotely queried Mie values and clean-clone packaging remain to complete. Independent Rayleigh preparation/cache loading is implemented; reuse it. Do not claim the existing five-case utility already provides the new granule-ID workflow.

## User-selected granule workflow

Implement an explicit CLI workflow accepting a NASA product/granule filename or supported CMR granule concept ID. Specify which forms are supported and reject ambiguous identifiers; do not interpret arbitrary input as a filesystem path, URL or shell expression. Distinguish L1C source from L2 GPC, product revisions, collections and grid sources.

1. Resolve the requested product through CMR/Earthdata metadata, preserving original producer ID, collection version, time range, links, catalog sizes and product identity.
2. Search candidate corresponding OCI/HARP2 L1C and optional GPC products with bounded time/region/version criteria. A matching timestamp is candidate evidence only. GPC may be optional/missing and must not block the L1C core.
3. Present selected candidates and expected bytes, allow explicit resolution of ambiguous revisions/pairs, and obey configurable candidate and cumulative transfer budgets. Reuse current acquisition/cache integrity and failed-byte accounting rather than inventing a second downloader.
4. Authenticate using the user's existing Earthdata setup. Offer an interactive login instruction only when actually necessary; never commit credentials or pass them to a remote Mie service. No service should need another user's Earthdata secret.
5. Stage complete downloads, validate NetCDF and hashes, then verify grid/time/nadir/full geolocation. Reject incompatible pairs with an actionable explanation, never silently resample. Record failed/missing/ambiguous outcomes honestly.
6. Write a portable local scene manifest and provide the exact launch command. Keep offline explicit `--oci`/`--harp2` and existing manifest workflows supported. Choose a user cache location/config independent of clone directory; do not commit runtime paths.

Suggested UX is an `acquire-scene` style command followed by `serve --manifest ...`, but the name/flags are not implemented yet. Document implemented commands only after delivering them. Avoid a broad multi-scene UI redesign unless necessary for this workflow.

## Mie and correction dependencies

Introduce a provider abstraction used by both cloudbow and RFT for phase functions and bulk cross sections, retaining a local adapter for reference/validation and a remote authenticated adapter for distribution. Follow REMOTE_MIE.md, especially immutable table identity/checksum, wavelength selection, native angle grids, log-re/log-ve interpolation, Csca weighting, strict bounds, failure behavior and pinned provenance. No silent fallback table or new fits. Remote unavailability should disable model overlays with a useful reason while preserving L1C maps/observations.

The user's aim is query access to values while the full table remains private. A public Drive link/download-to-client option does not satisfy that. Implement client endpoint/auth configuration without credentials in examples; the actual user's Drive/server infrastructure remains their provisioning choice. Provide step-by-step server setup options and an independently synthetic server fixture. A local CLI may cache bounded query results outside Git; authenticate and partition caches appropriately. Full-table access by authorized operators remains a separate access policy.

Transmission tables are excluded from the new distributable tool, not remotely relocated. Rayleigh-only setup/cache/serving is already independent of them: reuse `atmosphere-prepare --mode rayleigh` and the versioned `rayleigh_boundary` cache, with capability-aware UI/API rejection of transmission modes. `atmosphere-extract-rayleigh` preserves audited boundaries from old caches without copying table/humidity arrays. Reuse the existing analytical molecular correction and approved cloud/MERRA-2 boundary sources, keeping source diagnostics TOA and classified land+water correction with unclassified-only TOA bypass and explicit missing unsupported corrections. No new atmospheric science, scalar-Q/U correction or surface extension. Legacy transmission research code may remain isolated in the current development checkout; distribution must clearly omit/disable transmission controls and require no private table. Coordinate any additional cache/provider interface changes with agent 1; do not repeat the already implemented Rayleigh separation.

## Approved land Rayleigh behavior

The land trial is now integrated into production; do not defer it or reintroduce the former land bypass. The current shared dropdown applies unchanged Rayleigh to classified land and water, sets `rayleigh_land=true`, and leaves diagnostics/fits at TOA. Unsupported classified corrections stay missing without TOA fallback. Coarse MERRA-2/OCI boundaries and scientific limitations are unchanged. No transmission factor is applied to land, including legacy combined mode.

Preserve recipe compatibility: new `Recipe` defaults and browser imports use true, while `Recipe.from_dict` maps old Rayleigh recipes lacking the field to false for old Python/API/export replay. New raw API requests should include true explicitly to request the current policy. Export labels, `rayleigh_land_policy` and separate land/water corrected counts must agree. Cache content/filename cannot silently set the application domain. Preserve trial/production equivalence tests and do not mistake archived cache land-policy text for a current masking requirement.

## Packaging and repository preparation

Audit the Git index/history as well as ignore rules; `.gitignore` alone does not untrack old files. Never delete the user's data to make a repository appear clean. Verify no large binaries, private paths, reference notebook outputs, secrets or full private LUT-derived grids enter the deliverable. Preserve local reference snapshots and hashes. Any history rewrite or public redistribution needs explicit authorization.

Resolve Python/frontend compatibility and install assets. Source checkout serving currently finds `frontend/dist` relative to source; a wheel must explicitly package assets or clearly support source installs only. Build instructions use committed Python/pnpm locks; CI currently specifies Python 3.14, Node 22 and pnpm 11.25.0. `requires-python>=3.11` is a declaration, not proof of that whole support range: test or narrow it. Verify dependencies on a clean environment; don't infer portability from the developer's cached runtime. Assess optional HDF4/pyhdf removal for the no-transmission distribution.

Deliver concise README/quickstart, granule acquisition and offline launch examples, export/replay guide, science caveats, troubleshooting for credentials/missing products/remote LUT access, contribution guidance, CI, citation metadata and dependency/data attributions. Include independent synthetic demonstration/tests so CI needs no real credentials/data/private LUT or remote network. Avoid absolute author-machine paths in tracked examples/configuration.

Use the existing public repository identified above. Before publication, resolve the code license and any unresolved authorship/data permissions, then obtain authorization for the reviewed upload. Do not create another repository, push, upload LUTs or change Drive sharing from this brief alone. Keep the local service loopback/same-origin by default.

## Verification and completion report

- Portable synthetic install/build/test and one real explicit user-granule end-to-end acquisition/validation/launch/export when credentials/data are available; log bounded failures rather than claiming success.
- Missing/ambiguous/revised/incompatible products, optional GPC, failed/resumed transfer accounting, verified-cache reuse and no-login offline use.
- Provider equivalence with local reference for single/two-mode and coordinate-boundary cases; no new coefficients or altered number fractions. Assert single-mode identity and mixture/background invariants, exact shared residual support, missing-provider graceful behavior and hash/version mismatch rejection.
- Original-bin clicks from all maps, native/geographic display, saved recipes and PNG/PDF dimensions/provenance, corrected-map versus TOA-diagnostic labels. Document old enabled surface-extension recipes now failing and legacy fraction policies explicitly rather than silently replaying differently.
- Repository/wheel/image/CI output scan for data/secrets; hosted CI is only verified after actually running. Report commands, supported versions and measured limitations. Real dateline/high-latitude validation is deferred last; keep that gap explicit rather than blocking all preparatory work.

Deliver code and docs ready for user review plus a publication checklist limited to real unresolved choices. Do not expand scope into a new RFT retrieval, atmospheric model or public cloud deployment.

Current RFT display update (2026-10-26): RFT refl. and RFT component use the authorized optically thick single-scattering model without A/B/C, actual source geometry and omega=1; RFT P12/cloudbow retain stored A/B/C. Residuals are model minus observed in displayed −Q. Preserve explicit LUT phase-unit normalization and its unresolved P11-integral verification; see [RFT.md](../RFT.md). This supersedes earlier all-RFT-A/B/C wording.

The subsequently authorized RFT forward-model update adds above-cloud Rayleigh from the existing boundary cache. Droplet components plus a separate molecular contribution sum to RFT refl.; observations stay TOA. Preserve explicit cloud-only/no-cache labeling and unsupported cloud-boundary failures. See RFT.md for current details and STATUS.md for real verification.

Latest user-authorized RFT trial uses fixed proxy scattering-order weights [1,.5,.1,.01], multiplying droplet responses by 1.61 while keeping Rayleigh separate and unscaled. Preserve first-order/proxy-order provenance and experimental labels; these coefficients are not a Cornet-derived calibration. RFT P12/cloudbow A/B/C are unchanged. Current real-sample checks are in RFT.md/STATUS.md.


## Current quicklook product contract — 2026-11-05

Preserve the cleaned dashboard, not the historical research controls: left map selects OCI total / OCI phase / operational GPC LI / calculated narrow discrete or trapezoidal LI; middle is always HARP2 total; right is HARP2 polarimetry. Both HARP2 maps retain shared source sectors and actual-geometry contours. Left auxiliary fields preserve native-bin identity. The left angular inspector offers −Q, polarized magnitude and observation-only DoLP; DoLP disables LI integration and has no LI baseline/model. Original 135–145° LI, 135° reference and TOA diagnostics remain unchanged. Wider/adaptive LI and baseline-angle options were retired; do not restore them. Legacy routines remain for the independent statistics project, which is outside this delivery. The statistics header link has been removed. See ../LIQUID_INDEX.md for new `left_mode` recipe/migration and DoLP export behavior.


## Next chat: delivery sequence and granule selection

The user will start a new chat in this same project to implement this brief. Continue from the current local code; do not create a new application from the mockup, include `granule-statistics/` in the distributable package, or restore removed controls. This handoff updates requirements only: the arbitrary-granule workflow is still unimplemented.

1. Audit package/frontend dependencies and data exclusions, then verify a clean install in an isolated environment without the author's data paths. Keep the reusable one-scene launcher as a local convenience only; replace its `.venv-clean`/private manifest assumptions in the portable workflow. Installation/build happen once, serving starts again after reboot without reinstallation.
2. Implement the bounded granule-ID resolver/downloader described above, reusing `src/pace_l1c/acquisition.py`. Include a simple dashboard setup view accepting a producer granule filename or supported CMR concept ID, candidate/byte preview and explicit download action; retain an equivalent CLI and offline local-file selection. Keep acquisition/setup out of the scientific controls once a scene is open. Download into each user's cache, show progress/cancel/retry/missing products, and save a reusable local scene manifest. A bare timestamp may identify multiple products and must not silently choose a revision.
3. OCI+HARP2 L1C are the paired core. Acquire matching GPC when available for operational LI/cloudbow/RFT fields; absence must leave the core usable. Rayleigh/OCI-phase capability additionally needs the established OCI L2 cloud products (including adjacent source coverage when required) and MERRA-2 MET PS inputs used by existing boundary preparation. Resolve those dependencies explicitly and retain source identities, overlap coverage and unsupported-bin masks. No invented pressure or new ancillary model, no transmission LUT download. Optional capabilities stay disabled with a reason until their verified inputs are available.
4. Separate GPC scalar reading/registration from the current Mie-dependent cloudbow wrapper: operational LI and reported properties do not scientifically require a Mie table. Model overlays require a configured Mie provider; missing/private access must not prevent scene launch. Follow REMOTE_MIE.md for the future private provider. Infrastructure and access provisioning remain unresolved, not assumed available.
5. Test resolver ambiguity, unavailable companions, expired/missing authentication, budget limits, interrupted transfer, hash validation, cached offline relaunch and incompatible geolocation. Use synthetic fixtures for CI and an explicitly recorded real chosen granule for end-to-end acquisition/launch/export evidence; catalog discovery alone is not verification. Preserve same-bin selection across all three map types, sector changes and PNG/PDF exports.
6. Prepare GitHub staging (source, pinned setup, CI, examples, citation and exclusion audit). Owner/name and current public visibility are known; resolve license/authorship/data permissions and push authorization when the local result is publication-ready. Do not create a remote, publish or upload data from this brief. GitHub hosts code; this Python service runs locally. GitHub Pages hosting is a separate static-scene project with different constraints.

Start prompt for the new chat:

> Read AGENTS.md, docs/HANDOFF.md, skills/pace-l1c-development/SKILL.md and docs/handoffs/SHAREABLE_LOCAL.md. Implement the shareable locally installed GitHub version from the cleaned 2026-11-05 quicklook. Prioritize reproducible installation and a bounded granule-ID selection/discovery/download/cache workflow with verified OCI/HARP2 alignment, optional GPC and existing ancillary preparation. Preserve current map order, narrow LI and observation-only DoLP; keep statistics, retired LI experiments and transmission tables out of scope. Prepare locally for review; do not publish a remote or upload data without authorization.
