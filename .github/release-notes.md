Locally installed PACE OCI/HARP2 scene discovery and scientific visualizer.

Install the wheel with Python 3.14 and the attached requirements-lock.txt as pip constraints, then run `pace-l1c serve`. The built interface is included; Node/pnpm are unnecessary for release users. Search by producer filename/CMR ID or bounded dates/region, review transfer limits, authenticate with your own NASA Earthdata Login and save a verified native-bin pair. Existing files, saved scenes and a synthetic demonstration are also supported.

Operational GPC LI is independent of phase-library access. An authorized local Mie file remains optional; private remote-library service/user keys are deferred. No private tables or real science products are bundled.

Experimental Rayleigh/cloudbow/RFT science limitations and remaining real dateline/high-latitude acceptance gaps are documented in the repository. This release is a research visualization tool, not validated atmospheric-correction/retrieval software.

Version 0.1.1 adds clearer installation/Earthdata instructions, Beauty quicklook startup defaults, explicit optional-Rayleigh preparation warnings, and a separate fixed-scene static showcase with linked numbered selections. The showcase release archive contains only finite derived maps/public observation diagnostics, not raw granules or the private phase library.
