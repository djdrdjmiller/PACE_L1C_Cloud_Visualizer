# Current tools and interfaces

Inventory audited 2026-10-19 against `src/pace_l1c/cli.py` and `service.py`. All commands below exist; run `pace-l1c COMMAND --help` for flags. Granule-ID acquisition and the setup launcher are implemented; remote Mie access is deferred. Runtime files are outside Git.

## CLI

| Command | Current role |
|---|---|
| `demo` | Generate explicitly synthetic OCI/HARP2 fixtures. |
| `inspect FILE` | Print grouped product metadata/channel inventory. |
| `discover --config ... --manifest ...` | Search configured development cases and record catalog candidates/sizes. |
| `cache --manifest ...` | Report local manifest statuses; not a general filesystem cache cleaner. |
| `download --manifest ...` | Bounded authenticated staged acquisition; reuse verified files, preserve failed-budget accounting. |
| `qualify --manifest ...` | Verify acquired correspondence and development-case evidence. |
| `coastlines` | Explicitly acquire the public-domain Natural Earth annotation cache. |
| `validate` | Validate explicit OCI/HARP2 or a selected manifest pair. |
| `serve` | Launch scene setup without inputs, or open an explicit pair; loopback port 8000 by default. `--cache-dir`, `--no-browser`, `--port` configure local serving. |
| `login [--remember]` | Local interactive Earthdata sign-in; remembering is opt-in unencrypted netrc storage. |
| `search-scenes --identifier ... --output ...` | Search supported producer filename/CMR granule ID, or `--start/--end/--bbox`, without login. |
| `acquire-scene --search ... --candidate ...` | Acquire the explicit candidate under `--budget-gib`, optional `--gpc-id`; verify and save a scene/manifest. |
| `export` | Produce PNG/PDF/JSON from a recipe, layout, dimensions and DPI. |
| `atmosphere-clouds` | Bounded OCI CLD discovery/acquisition across actual OCI observation times. |
| `atmosphere-acquire` | Acquire exact cloud-product ancillary filenames under its own budget; `--kind met` selects only MET for Rayleigh. |
| `atmosphere-prepare` | `--mode rayleigh` builds pressure/land/phase/state cache from CLD/MET PS only. Legacy transmission mode additionally requires local HDF4 LUT/pyhdf and humidity inputs. |
| `atmosphere-extract-rayleigh` | Copy audited boundary/classification fields from an existing cache to a new Rayleigh-only file, without recalculation, table arrays or downloads. |
| `atmosphere-landmask` | Enrich an existing cache using audited OCI LAND/phase fields. |

`serve`, `validate`, `export`, `atmosphere-clouds` and `atmosphere-prepare` accept explicit `--oci`/`--harp2` or `--manifest`, `--case`, `--pair-index`. `--gpc`, `--mie` and `--atmosphere` add optional local data. A complete GPC entry from a manifest is selected independently of `--mie`. `search-scenes` and `acquire-scene` support producer filenames/CMR IDs and explicit bounded pairing.

Legacy atmospheric preparation commands remain for this local research checkout. Neither delivery handoff should require transmission data. Independent Rayleigh-only preparation/loading and extraction are implemented. Omit --lut for Rayleigh preparation (or select --mode rayleigh explicitly); --lut alone preserves legacy transmission preparation. Capability flags hide/reject transmission on boundary-only caches.

## Library boundaries

- `reader`, `science`: metadata-aware products and original TOA radiometry/Stokes.
- `scene`, `geometry`, `native`: correspondence, recipes, source selection, projected/native cells.
- `render`, `coastline`: preview cell IDs, annotations, reproducible figures.
- `cloudbow`, `rft`, `residuals`: registered stored coefficients, local LUT interpolation, fixed-mode comparison and branch-1 residuals.
- `acquisition`, `ancillary`, `discovery`, `launcher`: bounded acquisition/manifests, scene catalog and local setup jobs.
- `gpc`: independent registered scalar/QA reading without phase-function access.
- `atmosphere`, `rayleigh`: local column/cache handling, legacy transmission and experimental analytical molecular map removal. `land_trial` and `examples/land_rayleigh_trial.py` reproduce the historical water-only reference versus the now-production land-enabled calculation without changing caches or dashboard state.
- `service`, `cli`: HTTP/command orchestration. Reference notebooks/scripts are never invoked.

There is no remote Mie provider yet. `Cloudbow` currently opens the local LUT; `Atmosphere` now loads boundary-only caches without humidity/transmission; legacy combined caches load their optional table and advertise transmission support. The Mie provider seam remains for the repository-delivery agent.

## Local HTTP contract

| Endpoint | Current behavior |
|---|---|
| `GET /api/scene` | Inventories, alignment, anchors, optional atmosphere/phase capabilities correction capability flags and default recipe. |
| `GET /api/scenes` | The single already loaded scene, not a remote catalog. |
| `POST /api/render` | Recipe/preview size to map layers and expiring render ID/source-hit array. |
| `POST /api/hit` | Render ID plus screen pixel to original row/column; gaps reject. |
| `GET /api/bin/{row}/{col}?rft=true` | TOA spectrum/angular samples, GPC, cloudbow and optional RFT/residuals. |
| `POST /api/export` | Shared recipe plus physical layout/size/DPI to artifact URLs. |
| `GET /api/artifact/{name}` | Locally generated figure/recipe file. |

Host/origin are restricted to local same-origin requests. HDF5/Matplotlib work is locked; preview results retain up to eight render IDs. This is not a production multi-user authorization/resource-isolation scheme. The hosted track must bound requests, secure deployment and isolate artifacts before exposure.

## Verification commands

From an activated pinned environment:

```bash
python -m pytest -q
pnpm --dir frontend run build
pace-l1c validate --manifest data/manifests/development.json --case science_scene
```

On the current developer checkout, Python tests use `.venv-clean/bin/pytest` and Matplotlib cache `MPLCONFIGDIR=cache/matplotlib`. `frontend/package.json` build runs `tsc --noEmit` before Vite. See STATUS for actual last results and science gaps. Synthetic tests require no private data or credentials. Do not delete caches/raw data as a tooling cleanup step without a specific request.

Selected-bin API responses now include `liquid_index` evidence for both reflectance quantities, branch 1 and both narrow estimators. Left-map recipe values (`left_mode`) `liquid_index` (GPC), `liquid_index_discrete` and `liquid_index_trapezoidal` are implemented. New `liquid_index_quantity`, `liquid_index_branch`, and `liquid_index_trapezoidal` fields are documented in [LIQUID_INDEX.md](LIQUID_INDEX.md). Computed LI maps require only the L1C core; operational GPC scalar reading/registration now uses the independent `RegisteredGPC` adapter without a Mie requirement.

Render request control: `/api/render` accepts optional `client_id` (up to 100 characters) and nonnegative `generation`, used by the browser to cancel superseded derived-map calculations. Requests without them remain supported. Obsolete/disconnected renders can return 499; the browser treats this as cancellation. These fields do not affect science recipe hashes/render cache identity. Cancellation checkpoints discard incomplete derived fields and preserve HDF5/Matplotlib locking.

## Scene-setup endpoints

`GET /api/setup` reports scene-loaded/account/cache state. `POST /api/setup/search` starts a bounded catalog job; `GET /api/setup/job` polls progress and `POST /api/setup/cancel` cooperatively cancels it. `POST /api/setup/acquire` requires a returned search ID, candidate ID and explicit budgets. These catalog records are candidates, not verified alignment.

`GET /api/setup/saved`, `POST /api/setup/local`, `POST /api/setup/demo` and `POST /api/setup/open` manage user-local verified scenes. Opening rehashes all inputs and recreates the validated Scene, clears render/hit caches and closes the prior scene. `POST /api/setup/import?name=FILE.nc` streams a local browser-selected copy (3 GiB per file); explicit paths avoid duplication. Imports never go to an external service.

`POST /api/setup/login` supports existing environment/netrc credentials or session-only username/password with optional remember. Passwords are not included in jobs, manifests or validation responses. All mutating setup endpoints require same-origin JSON except the bounded binary import. This is a loopback tool; do not expose it as an authenticated multi-user service. Scene APIs return 409 until a scene is opened.

Incomplete acquisitions persist separately from verified scenes: `GET /api/setup/acquisitions` lists per-file failure stages/reasons and accumulated budget. `POST /api/setup/retry` takes an acquisition ID and an explicit total transfer ceiling. A complete staged file with exact catalog byte count is revalidated against current readers, identity and supplied catalog checksum before promotion, without new network/authentication or another byte reservation. Invalid/incomplete bodies remain unverified. The launcher shows these under **Saved scenes → Incomplete downloads**. Cancellation and failure never label an unverified pair ready.
