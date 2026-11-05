> Historical record, archived 2026-10-19. This file includes superseded instructions and measurements. Use docs/HANDOFF.md, docs/STATUS.md, and the current scientific documents for current behavior. Relative paths below refer to their original document location.

# Developer starting prompt

Implement release 1 of the PACE L1C visualization project in this repository. Begin with AGENTS.md, docs/HANDOFF.md, and skills/pace-l1c-development/SKILL.md; consult PLANNING.md for detailed scientific conventions and sources. Do not restart product discovery or ask the user to repeat decisions already documented.

Build a reusable Python science library and local service, a browser dashboard with OCI total-reflectance imagery, HARP2 total-reflectance imagery, and a third HARP2 polarized-reflectance/DoLP map, plus synchronized selected-bin spectra/polarimetry. All imagery uses original L1C sampling. Deliver reproducible PNG/PDF figure exports and a separate bounded Earthdata acquisition/cache utility for the five development cases.

Use the Analysis desk mockup as the default layout guide, with responsive stacking; retain Figure studio as a reference for figure composition, not a requirement to build two separate applications. The mockup's source is docs/mockups/dashboard-sketch.html. It contains synthetic data and simulated interactions only.

Start with the documented defaults and inspect real NetCDF metadata. Preserve the supplied reference snapshots and their provenance; do not execute their notebook actions. Implement meaningful synthetic tests, then verify real paired-granule alignment, metadata-derived sectors, native/geographic display, linked selection from all three maps, and export consistency. Authenticate acquisition using the user's existing Earthdata setup where available; stop for user login only if actually needed. Record failed searches or missing cases without claiming success.

Complete release 1 before implementing stored GPC overlays, RFT fitting, or atmospheric correction. The approved later features remain in the roadmap. Keep HARP2 polarized quantities uncorrected. Report substantive unresolved scientific verification with its evidence rather than making silent assumptions.

Prepare the code as a shareable GitHub repository with reproducible setup, CI, examples, data exclusions, and citation metadata. Ask for owner/name, visibility, and license when local publication-ready code exists; this prompt does not authorize creating or publishing a remote. Finish with implemented behavior, test results, measured limitations, and launch/acquisition/export commands.
