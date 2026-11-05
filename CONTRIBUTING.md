Use Python 3.14 and the committed dependency lock for the validated environment. Build the frontend with the committed pnpm lock. Run `python -m pytest -q` and `pnpm --dir frontend run build` before proposing changes.

Keep scientific computations separate from display enhancement. Preserve original bin/view identity, full wavelength metadata and missing values. New reader or geometry behavior needs an independently calculated fixture and real-product evidence. Do not clip scientific values, silently repair geometry or substitute observations at missing bins.

Keep raw products, LUTs, reference assets, credentials, account details and generated results out of Git. Synthetic fixtures are generated from independent code in the package. Describe scientific limitations with evidence, distinguish experimental curves from operational reconstruction, and update `docs/STATUS.md` when validation changes.

Project code uses Apache-2.0 in the public PACE_L1C_Cloud_Visualizer repository. Private reference/library assets are not covered by that grant and must not be redistributed. Build wheels only after the pinned frontend build; audit artifacts with `python scripts/check_wheel.py dist --smoke`. Remote phase-library infrastructure remains deferred.
