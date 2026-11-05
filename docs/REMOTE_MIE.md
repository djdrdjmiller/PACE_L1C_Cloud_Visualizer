# Remote private Mie values — proposed design and setup guidance

Current decision, 2026-11-05: the user deferred remote phase-library access and user keys. The shareable version supports optional authorized local files; this document is retained as future design guidance, not an implementation requirement.

Prepared 2026-10-19. This is a design for the two delivery tracks, not an implemented endpoint. The current `Cloudbow` class opens a local NetCDF, loads a selected wavelength's P21 grid and bulk optics, and RFT reuses those arrays. Neither a remote database nor a Drive/server connection is configured.

## Recommended architecture

Keep the original Mie NetCDF on a protected server and place a small authenticated scientific query API in front of it. A conventional database is unnecessary for this table; the file plus an indexed/cached query service is sufficient. Both the hosted demonstration and locally deployed dashboards can use the same provider contract. The repository contains client/server code and synthetic fixtures, not the private table, access tokens or private location.

The API returns only requested wavelength/microphysics phase curves and bulk optics, with provenance. Cloudbow/RFT model evaluation remains in the shared Python library so deployment does not change fitting/sign conventions. If exposing phase curves themselves is too permissive, a later server-side full-model evaluation endpoint can return curves for requested retrieval parameters instead; explicitly version that contract and test parity.

Keeping a file out of Git is different from keeping it inaccessible to users. A full-file download endpoint, even authenticated, gives permitted users a copy. A query API limits direct file access but users can retain returned values; unrestricted repeated queries could reconstruct much of a grid. Select the allowed audience, query domain, quotas and data-use policy accordingly. Do not promise mathematical prevention of copying values that a client can see.

## Protection choices reviewed — 2026-11-05

The public code repository and the private table are separate distributions. These options concern access control; none grants permission to use or redistribute a third party's data. Confirm whether remote computation, returned phase curves/bulk optics, cached results and exported derived plots are permitted before enabling access for other users.

| Option | What an installed user receives | Suitability for the requested protection |
|---|---|---|
| Encrypted table with local decryption | Ciphertext plus access to a decryptor/key or decrypted process memory | Protects storage/transport in some settings, but cannot keep the usable table secret from a determined recipient controlling the machine. Embedding or remotely delivering the key does not remove this limitation. |
| Private repository, authenticated download or signed file link | A complete table copy once authorized | Suitable only if sharing copies with approved users is acceptable. Revoking access cannot recall downloaded copies. |
| Authenticated phase/bulk-optics query service | Requested P21 curves and cross sections, never a full-file endpoint | Recommended initial design, matching the existing provider proposal. Per-user credentials, bounded queries, quotas and versioning constrain access; accumulated outputs may still reveal substantial table content. |
| Remote model-evaluation service | Requested cloudbow/RFT curves or rendered results | Exposes less direct table information, with more server logic and parity testing. A later alternative if phase-curve access is too permissive; output capture and repeated-query inference remain possible. |
| Full local table with provider permission | The original table | Simplest offline option if the developer permits it; keep optional and separately licensed rather than assume permission. |

Encryption at rest and HTTPS remain useful for the private backend. A shared secret embedded in public client code is not per-user authentication. Keep backend storage credentials on the backend and give each approved client revocable access separately. Minimize logs to metadata needed for operations; do not send Earthdata credentials or raw granules to the Mie service. Define result-cache retention/revocation limitations explicitly: local returned values can be copied even when the service account is later disabled.

Drive can be an optional private backend origin, but its [binary download API](https://developers.google.com/workspace/drive/api/guides/manage-downloads) supplies files, not this scientific query contract. Direct Drive-to-client download therefore does not achieve query-only access. No new plugin is needed for the present preparation: the connected GitHub tools and local tooling are sufficient. Runtime users will not need a ChatGPT plugin; they need the installed client and, for optional model overlays, service access. Hosting-provider tooling can be evaluated once an operator/account and budget are chosen.

## Proposed provider operations (to implement)

| Operation | Required behavior |
|---|---|
| Metadata | Immutable table ID/version/hash, phase element and sign/normalization convention, wavelength units/centers, native angle coordinates, supported re/ve bounds, cross-section/efficiency units, interpolation version and limitations. No filesystem paths or secrets. |
| Query/batch | Requested wavelength center and finite positive re/ve; bounded batch size. Return selected measured LUT center, native-angle P21, Csca and available Cext/Qsca/Qext, units, status and immutable provenance. Fixed-model clients must request all active modes from the same table/version. |
| Failure | Explicit unsupported domain/wavelength, missing corners, authorization, timeout, quota or version mismatch. No extrapolation, silent nearest-microphysics substitution or alternate table. |
| Client cache | Bounded, private cache keyed by table hash/version, interpolation version and exact query/selected wavelength; store only returned values outside Git. Protect authenticated/audience-specific data and never key cache by endpoint name alone. |

Preserve float64 log-radius/log-variance bilinear interpolation, native angular sampling, nearest supported spectral selection with reported mismatch, and current strict bounds. P21 is the table element actually supplied; do not rename it P12 without a validated convention. Csca is a bulk cross section in µm², whereas Qsca/Qext are dimensionless despite the supplied table's misleading efficiency-unit attributes. Never independently normalize P21 peaks/integrals. RFT uses alpha_i=f_i*Csca_i/sum(f_j*Csca_j), with user-confirmed number fractions and original same-bin C/B/A. Provider changes must not alter those semantics.

Pin the table hash/interpolation contract in saved/exported recipes. Explicitly map the existing local SHA-256 provenance to the remote provider's immutable identity and reject changed tables on replay. Missing provider access should leave L1C maps/TOA diagnostics usable and disable optional model overlays with a reason. Do not silently reuse stale curves from another bin. Local/server adapters need equivalence tests on interior, exact-edge, single-mode, two-mode and invalid-domain queries, plus residual/model/export parity.

## Option A — Google Drive as private origin storage

1. Use a dedicated restricted Drive folder/account; upload the table only after choosing access rights and obtaining redistribution/use permission. Record its content hash/version outside public configuration.
2. Share read access only with the backend's intended identity or operator. Use a supported OAuth/service identity arrangement appropriate to that Drive account; do not assume a service account automatically has access to a user's files. No public “anyone with link” setting is required.
3. At backend provisioning/startup, use the official Drive API to retrieve the binary file and verify its pinned hash before loading. The backend may cache the complete file privately; browser/local clients only see the query API.
4. Store backend credentials in its secret store, never in the repository, frontend, examples, URLs or export JSON. Configure frontend/local-client API authentication separately; a local client must not receive the backend Drive credential.
5. Document token renewal, table updates, health/error behavior and private-cache retention. Drive-origin availability/quota/auth failures must not silently switch LUTs.

Drive's official API downloads binary files using `files.get` with `alt=media`, and permissions can grant reader access to specific users/groups. This provides storage/access control, not a scientific subset-query interface; the query backend is still needed. See [Drive binary downloads](https://developers.google.com/workspace/drive/api/guides/manage-downloads) and [Drive sharing permissions](https://developers.google.com/workspace/drive/api/guides/manage-sharing).

A simpler Drive-to-local full-file download could serve trusted users willing to receive the LUT, but it does not meet the requested query-only/private-table architecture. Treat it as a separate explicit policy choice, not the default implementation.

## Option B — a web server or private object store

1. Put the NetCDF outside the public document root, readable only by the query-service account. Use HTTPS for the query API and authenticated access appropriate to the users.
2. Run the small query service with a read-only LUT mount, pinned hash, bounded request arrays/batches and cache. No route should return the entire table or accept an arbitrary server path/URL. Do not expose raw storage credentials.
3. Configure rate limits, monitoring, timeouts, worker/memory bounds, versioned updates and a backup. Keep an old immutable version available for reproducible exports or reject unavailable historical versions explicitly.
4. Give local users an API endpoint and their own revocable access credentials through a separate channel. Document configuration via a user-local file/environment; `.env.example` contains names/placeholders only.

A private object store can replace the server's disk or Drive origin. Signed download URLs still grant object access to whoever holds them; they are bearer tokens, not a substitute for a value-query API ([AWS presigned URL documentation](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html)). Avoid embedding them in recipes/logs. Direct remote HDF5/S3 reading also adds runtime/build constraints; standard PyPI h5py builds do not include the ros3 driver ([h5py file drivers](https://docs.h5py.org/en/stable/high/file.html)). A server-local verified copy avoids making every dashboard installation solve that problem.

## Decisions and suggested next step

Recommended starting point: one small HTTPS Python query service with a private local file, optionally provisioned from restricted Google Drive. Reuse current interpolation with independent synthetic fixtures and a pinned local-reference parity check. No general SQL database or public LUT link is required.

Before infrastructure provisioning, choose hosting account/server, intended users, authentication, permitted query volume/derived-data sharing, update/version policy and budget. Those are not prerequisites for preparing provider code and local synthetic tests. No uploads, sharing changes, server creation, DNS, billing or production deployment are authorized by this document. Transmission tables are outside the requested new distribution and are not part of this remote service.
