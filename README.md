# PACE L1C Cloud Visualizer

A locally installed µCloud dashboard for NASA PACE OCI and HARP2 observations. Search for a scene, download a verified OCI/HARP2 L1C pair, then explore linked maps, spectra, polarimetry and liquid-index diagnostics from original source bins. Export reproducible PNG/PDF figures and JSON recipes.

The code is hosted on GitHub; the Python service and science data run on your own computer. No private phase-function library, transmission table, NASA products or credentials are distributed.

## Installation and getting started

No GitHub account, repository clone, Node installation or initial granule is needed. Use **Python 3.14**; the release includes the complete browser interface.

1. **Install [Python 3.14.x](https://www.python.org/downloads/)**, then open a terminal in a folder you want to use for the visualizer.
2. **Create and activate an environment.**

   macOS / Linux:

   ```bash
   python3.14 -m venv .venv
   source .venv/bin/activate
   ```

   Windows PowerShell:

   ```powershell
   py -3.14 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. **Install the release and launch.** Run these commands in the activated environment:

   ```bash
   python -m pip install -c https://raw.githubusercontent.com/djdrdjmiller/PACE_L1C_Cloud_Visualizer/v0.1.1/requirements-lock.txt https://github.com/djdrdjmiller/PACE_L1C_Cloud_Visualizer/releases/download/v0.1.1/pace_l1c_vis-0.1.1-py3-none-any.whl
   pace-l1c serve
   ```

   The dashboard opens at [localhost:8000](http://127.0.0.1:8000/). Keep the terminal open; Control-C stops the server. If the port is occupied, use `pace-l1c serve --port 8001`.

4. **Connect Earthdata to download NASA files.** Create a free [NASA Earthdata Login](https://urs.earthdata.nasa.gov/users/new) if you do not already have one. In the dashboard, choose **Earthdata sign-in** and enter those credentials, or choose **Use existing local Earthdata setup**. There is no separate earthaccess account. **Remember on this computer** is optional and saves credentials in an unencrypted local netrc file. Searching, the synthetic demo and already downloaded scenes need no login.
5. **Choose a scene.** Select **Find a scene**, enter a complete OCI/HARP2 filename or search by UTC date and region, then review the candidate and transfer ceiling. For a first example, use `PACE_OCI.20251002T182635.L1C.V3.5km.nc`. GPC adds reported LI/cloud properties; **Prepare experimental Rayleigh / OCI phase** additionally acquires separate OCI cloud and MERRA-2 pressure inputs. Missing optional products do not prevent opening a verified OCI/HARP2 core. Download, wait for validation, then select **Open dashboard**. New scenes start with **Beauty · quicklook** display enhancement; observations remain TOA unless a supported map correction is selected.
6. **Return later.** Activate the same environment, run `pace-l1c serve`, and choose **Saved scenes**. No reinstallation or repeat download is needed. **Choose scene** returns from the viewer to setup; incomplete acquisitions have revalidate/retry controls.

The per-user data cache is separate from the installation folder. Set `PACE_L1C_CACHE` or use `serve --cache-dir PATH` to choose its location. See [Releases](https://github.com/djdrdjmiller/PACE_L1C_Cloud_Visualizer/releases) and [verification status](docs/STATUS.md) for tested versions. Choose **Try a synthetic demo** to explore before signing in or downloading real data.

## Scene discovery and Earthdata

Search with a complete producer filename (for example `PACE_OCI.20251002T182635.L1C.V3.5km.nc`), a CMR granule concept ID, or a date range of at most seven days plus geographic bounds. The supported collections are OCI L1C V3, HARP2 L1C V4 and HARP2 GPC V4.0. Filenames/CMR IDs identify requested versions; no bare-timestamp, arbitrary URL or wildcard input is accepted. Catalog timestamps only identify candidate companions. Metadata and full geolocation must establish native-bin correspondence after download; incompatible pairs are rejected without resampling science arrays.

Review candidate revisions, optional GPC and catalog sizes before downloading. Transfers have a user-selected ceiling, retain completed files and count failed attempts against the saved budget. Cancellation is cooperative at transfer/preparation checkpoints; retry uses verified completed files. It does not promise byte-range resume of a partial file. Saved scenes also lists incomplete acquisitions with file status, budget usage and revalidate/retry controls. Complete staged files that previously failed a reader can be checked again without a new download; only verified pairs enter the ready-scene list.

Searching is public. Downloading new NASA products requires a free [NASA Earthdata Login](https://urs.earthdata.nasa.gov/users/new), not a separate earthaccess account. The setup screen can reuse environment/netrc credentials or authenticate locally for the current server session. Remembering credentials is optional and uses earthaccess's **unencrypted local netrc file**. Credentials are never placed in scene manifests, recipes or this repository. NASA may require authorizing the data-provider application in your Earthdata account. [Authentication details](https://earthaccess.readthedocs.io/en/stable/user/explanation/authenticate/)

Optional GPC enables reported LI/cloud properties without any Mie library. Optional experimental Rayleigh/OCI-phase preparation uses the established overlapping OCI L2 cloud and declared MERRA-2 MET pressure inputs, under a separately displayed transfer ceiling. Exact ancillary requirements are resolved after the L1C pair is available. Missing products or unsupported boundaries leave the core TOA scene available and report a warning; they never invent pressure or fill corrections with TOA at unsupported classified bins.

The current release supports one active scene per local server. **Choose scene** returns to setup. Switching scenes clears old render/hit caches. Local file pickers copy files into the local cache; explicit paths avoid a duplicate copy. [Commands and API](docs/TOOLS.md)

## Optional local phase library

Private remote-library access is deferred. You may load your own authorized local GPC/Mie files from setup or the CLI. No service account, phase-library user key or table download is required for the core dashboard. Cloudbow/RFT overlays stay disabled without the matching local inputs. The library is excluded from the source, wheel, release and CI fixtures.

```bash
pace-l1c serve --oci OCI.nc --harp2 HARP2.nc --gpc GPC.nc --mie LOCAL_LIBRARY.nc
```

Existing manifests and offline explicit-file workflows remain supported:

```bash
pace-l1c serve --oci OCI.nc --harp2 HARP2.nc
pace-l1c serve --manifest LOCAL_MANIFEST.json --case selected_scene
```

The equivalent bounded CLI acquisition workflow is:

```bash
pace-l1c search-scenes --identifier PACE_OCI.20251002T182635.L1C.V3.5km.nc --output search.local.json
pace-l1c login --remember
pace-l1c acquire-scene --search search.local.json --candidate CANDIDATE_ID --budget-gib 4
```

Choose the candidate ID from the search output. `--gpc-id` selects an optional companion explicitly. The acquisition command prints the portable-local manifest path and exact launch command. Browser setup additionally supports optional cloud/MET acquisition and Rayleigh preparation; the existing atmospheric CLI commands remain available. Search/scene manifests contain local paths and are user-local files, not distributable data bundles.

## Science and figure exports

Maps preserve source-bin selection, missing-data masks and metadata-derived wavelength/view identity. Auxiliary maps occupy the left panel; HARP2 total and polarimetry retain shared sectors. Calculated LI retains the narrow discrete/trapezoidal definitions; DoLP inspection is observation-only. Spectra, angular observations and fitting diagnostics remain TOA. [Science conventions](docs/SCIENCE.md), [liquid index](docs/LIQUID_INDEX.md)

Rayleigh is experimental molecular single scattering over classified land and water, not validated full atmospheric correction. Unclassified bins stay TOA; unsupported classified corrections stay missing. No transmission table or surface-pressure extrapolation is required. Local cloudbow/RFT reconstructions retain documented heuristic/normalization limitations. [Atmosphere](docs/ATMOSPHERE.md), [RFT](docs/RFT.md)

Use the dashboard export controls, or replay an exported JSON recipe:

```bash
pace-l1c export --oci OCI.nc --harp2 HARP2.nc --recipe figure.json --output outputs/replayed
```

Supply the same optional `--gpc`, `--mie` and `--atmosphere` inputs when relevant. Replay verifies L1C hashes and supplied optional provenance. Old enabled surface-transmission-extension recipes fail explicitly. Older Rayleigh recipes without `rayleigh_land` preserve the legacy water-only Python/API policy; new/browser recipes enable land. See the scientific docs for compatibility details.

## Development

The supported pinned environment is Python 3.14, Node 22.12+ and pnpm 11.25.0. Source builds need Node/pnpm; release wheel users do not.

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
cd frontend
pnpm install --frozen-lockfile
pnpm run build
cd ..
python -m pip install --no-deps -e .
python -m pytest -q
python -m pip wheel --no-deps . --wheel-dir dist
```

CI uses independent synthetic science/catalog/transfer fixtures without real NASA credentials or private data, builds the frontend and wheel, and smoke-tests installation outside the checkout. Passing CI creates the first GitHub release for a new package version; existing version assets are never overwritten. See [CONTRIBUTING](CONTRIBUTING.md), [AGENTS](AGENTS.md) and [current evidence and gaps](docs/STATUS.md). Real dateline/high-latitude acceptance remains deferred; catalog discovery is not real-scene validation.

Apache 2.0 applies to this project's code. NASA products, private libraries and dependencies retain their own terms. See [LICENSE](LICENSE), [NOTICE](NOTICE), [third-party notices](THIRD_PARTY.md) and [citation metadata](CITATION.cff).

## Try the fixed-scene web demo

[Open the original-scene showcase](https://djdrdjmiller.github.io/PACE_L1C_Cloud_Visualizer/) in your browser; no installation or Earthdata login is required. It uses the 2 October 2025 scene, twelve numbered original bins selectable on all three linked maps, three HARP2 sector presets, and TOA/experimental Rayleigh map choices. Selecting a marker updates its OCI spectrum, discrete hyperangular observations and narrow liquid-index diagnostics. Map corrections do not alter those TOA observations.

The demo is a finite set of precomputed maps and selected-bin observations. Use the installed dashboard for new scenes, arbitrary-bin inspection, unrestricted rendering and exports. The private phase library and its cloudbow/RFT model curves are excluded. Source identities, map recipes, missing support and asset hashes accompany the demo. Rebuilding requires locally authorized original products; `scripts/build_showcase.py` exports only bounded derived assets. The manually dispatched Pages workflow verifies the declared release archive before deployment.
