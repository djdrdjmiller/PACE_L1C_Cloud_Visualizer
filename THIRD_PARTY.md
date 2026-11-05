# Data, dependencies and attribution

Project code is distributed under Apache-2.0. This does not grant rights to private phase-function/transmission libraries or NASA source products. No supplied reference notebook, private table, table-derived grid or real product is bundled. Users obtain their own NASA files and any separately authorized local phase library.

The browser bundle contains Plotly.js (MIT); its license is included at `licenses/plotly-LICENSE.txt`. Frontend build tooling includes Vite (MIT) and TypeScript (Apache-2.0). Python dependencies are declared in pyproject.toml and pinned in requirements-lock.txt; each retains its own license and notices. Their packages are installed from their distributions rather than copied into this project's wheel.

Optional Natural Earth coastline downloads are public domain and retain source URL/hash/scale/license metadata. The application does not silently fetch coastlines. `pace-l1c coastlines --output PATH` explicitly acquires that cache. No Natural Earth file is included here.

The µCloud wordmark and icons are owner-supplied project branding. Do not imply endorsement by NASA or any data provider. Font outlines are included in the supplied logo artwork; no commercial font files are distributed.

Cite the original NASA products/processing versions alongside software, input hashes and experimental-model provenance. Scientific references and limitations are in docs/SCIENCE.md, docs/LIQUID_INDEX.md, docs/ATMOSPHERE.md and docs/RFT.md.
