# Handoff — consistent µCloud PACE dashboard headers and navigation

**2026-11-05 update:** the user removed quicklook’s Granule statistics link for the forthcoming shareable version. Header branding/spacing guidance remains relevant; reciprocal navigation requirements below are historical and must not be restored.

Prepared 2026-10-27 for the agent maintaining the **L1C visualizer**. This is a narrow frontend alignment task. The granule-statistics agent has implemented the statistics-side changes described below. Do not restart product/science discovery, alter scientific calculations, or merge the two applications.

## Read first and scope

Follow root AGENTS.md and the existing quicklook development instructions. For this task, inspect the current header in `frontend/src/main.ts`, its styles in `frontend/src/style.css`, and `frontend/public/branding/`. The corresponding statistics files are `granule-statistics/frontend/src/main.ts`, `granule-statistics/frontend/src/style.css` and `granule-statistics/frontend/src/assets/brand/`.

The user requested more consistent dashboard headers and a handoff to enable links between the dashboards. Preserve the working visualizer controls, loading/status/error messages, scene identity, correction badge and scientific behavior. Do not modify the statistics application or restart its service as part of this task.

## Running applications — distinct ports

| Application | Local URL | Source |
| --- | --- | --- |
| PACE L1C · Quicklook Dashboard | http://127.0.0.1:8000/ | `frontend/`, `src/pace_l1c/` |
| PACE L1C · Granule Statistics | http://127.0.0.1:8010/ | `granule-statistics/` |

Both URLs returned their intended application during the 2026-10-27 check. Port 8010 belongs to the statistics application. Never stop, replace or bind over the other application's port. Check actual listener identity before service operations; sandboxed loopback failures previously produced a misleading shutdown diagnosis. Statistics implementation/evidence is in `granule-statistics/docs/STATUS.md`.

## Shared header contract

Use the visualizer's existing light header as the common pattern. The statistics app has been changed to match it; the earlier dark PACE strip and large title with the logo on the right have been removed.

- Header surface: `#faf9f5`; text `#253632`; one-pixel bottom border `#bdc8bf`.
- Desktop padding: **22px 28px**. Allow normal height from content, with roughly 88px minimum in statistics; no rigid height that clips status or badges.
- Left identity group: µCloud wordmark **first**, then a title/subtitle block, with **20px gap** and centered vertical alignment.
- Approved light-surface wordmark: **150 × 36 CSS px**, preserving 300:72 proportions; `alt="µCloud"`. Use U+00B5, capital C. Do not redraw or recolor its lettering/cloud/rays.
- Desktop title: **23px**, weight **550**, system UI sans serif, normal letter spacing, no margin. Exact application names distinguish their roles: `PACE L1C · Quicklook Dashboard` and `PACE L1C · Granule Statistics`.
- Subtitle: **12px**, muted `#60776c`. Visualizer keeps `OCI + HARP2 · Original L1C bins`; statistics uses `HARP2 · Full granule · Original L1C bins`.
- Right group: compact status/meaningful badge plus sibling-dashboard navigation. Badge background `#e7eee8`, muted text, restrained radius. Keep the visualizer's correction badge truthful; the statistics `Local research workspace` badge is not a correction state.
- Header links: **12px**, `#356b61`, subtle underline/bottom border `#bdc8bf`, stronger accent on hover. Keep visible keyboard focus.
- At **800px and below**, stack logo above title with **8px gap**; logo becomes **142px wide**, height auto. Header padding **14px**. Title can reduce to **20px**. Let navigation/status wrap below without overlap or horizontal overflow.
- All metadata/status must remain readable at 390px. A long filename belongs in the scene strip below the header, not in the title row.

The statistics header uses classes `.dashboard-header`, `.dashboard-brand`, `.dashboard-title`, `.header-links`, `.dashboard-link`, with the local logo class `.mucloud-logo`. The visualizer already uses `.dashboard-brand`, `.dashboard-title` and `.mucloud-wordmark`; retain its class names if that avoids churn. The shared contract is visual/semantic, not a requirement to rename unrelated selectors.

## Reciprocal links — small, independent change

Already implemented in statistics: a visible **L1C visualizer ↗** header link to `http://127.0.0.1:8000/`, `target="_blank"`, `rel="noopener"`.

Add to the visualizer's right header group:

```html
<a class="dashboard-link"
   href="http://127.0.0.1:8010/"
   target="_blank" rel="noopener">Granule statistics ↗</a>
```

Opening a sibling app must preserve the current map selection, correction settings, cohorts and plot zoom in the originating tab. This first link does **not** transfer scene IDs, bins, crop bounds or filter recipes. The currently prepared applications use the same full scene, but that is not a universal correspondence guarantee. Do not add pixel/filter synchronization or infer correspondence from timestamps alone.

These addresses are explicit local-development destinations, not published URLs. If either app later becomes portable/hosted, expose its sibling URL through deployment configuration and hide/disable the link when unavailable. Never silently link a remote user back to their own localhost. Link-only cross-port navigation needs no CORS change, API bridge, data copy, new server, upload or hosting resource.

## Asset source and icons

Both use the approved October 19, 2026 µCloud brand kit. Visualizer assets already live under `frontend/public/branding/`; statistics owns unmodified local copies under `granule-statistics/frontend/src/assets/brand/`, with hashes in SOURCE.json. Read the mucloud-brand skill if replacing any asset. Keep the same approved web icon/favicons. Do not reference the user's skill-installation path from browser HTML.

## Content layout intentionally differs

The visualizer's maps/angular inspectors and the statistics app's distributions/cohorts serve different purposes. Keep those content structures distinct while sharing the header and navigation hierarchy. Do not recreate three maps in statistics or replace the visualizer's science controls with cohort controls.

Statistics now shows response controls beside a figure stack: distributions first, paired density second, conditions below both. The summary table is collapsed by default. Display defaults use declared data-based ranges/bins, report omitted tails and expose full-range/manual options. These are statistics display policies, not shared map limits or new retrieval thresholds.

## Verification and acceptance for the receiving agent

1. Run the committed frontend TypeScript check and Vite production build using the existing lock/environment. No Python science changes are needed for header/navigation edits.
2. Inspect the **actual browser** at desktop and **390px** widths: wordmark on the left/above the title, proper 150:36 proportions, title/subtitle hierarchy, badge/status legible, links visible, no clipped text or page overflow after chart resize settles. Reset temporary viewport overrides.
3. Follow each sibling link and verify its title/port. Original tab state must remain intact. Keep status/error reporting and keyboard focus behavior intact.
4. Use the statistics header as the current implemented reference; do not restore its superseded logo-right/dark-strip layout.
5. Record actual evidence in STATUS. Local browser/build checks do not establish hosted availability or clean-clone deployment. Do not change scientific policies, sources, raw/cache files, publication/sharing, or the other application's service.

## Useful task prompt

“Read docs/handoffs/DASHBOARD_VISUAL_ALIGNMENT.md. Align the visualizer header with the documented µCloud contract and add the reciprocal Granule statistics link to localhost:8010. Preserve its scientific behavior and working port 8000; do not edit or restart the statistics application. Verify the frontend build, desktop/mobile header layout and cross-dashboard navigation, and record actual results.”

Statistics joint histograms now use a square **inner plotting area**, with independent physical-axis ranges and explicit auto/manual range policies. This is a statistical-chart layout policy; it does not impose equal numerical units on unlike quantities or change the visualizer's scientific plotting conventions.
