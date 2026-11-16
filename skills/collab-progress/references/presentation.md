# Invocation reports and progress deck

Run `scripts/progress.py snapshot` once after the review phase of every skill
invocation, even with no new work. A catch-up with several commits still produces
one invocation snapshot. `report` renders a legacy alias; `scan`, `prepare`,
`context`, and `read-event` do not append reports.

## Comparison contract

- Compare each cohort with the most recent earlier saved report whose counts for
  that cohort differ (`comparison_base` in `progress_present.py`). Runs that change
  no counts (maintenance, re-confirmations, moving the data folder) carry the last
  real change forward instead of resetting every arrow to →. With no differing
  report, the immediately preceding one is used. Each snapshot records the report
  it compared against in `compared_with` (per cohort) next to `previous_id`.
- Rate is `applied / (eligible - declined)` after at least three eligible
  opportunities. A zero non-declined denominator has no usable rate.
- ↑ and ↓ indicate rate increases/decreases; → indicates equal rate, including
  changed counts with an equal rate. Show counts, declined, verified and unknown.
- Numeric differences are percentage points, not relative percentages.
- First, newly measured and newly unmeasured values get neutral labels. Unknown
  evidence is not missed. A changed sample does not prove personal improvement.
- Trait and indicator comparisons are independent; do not force their counts to
  match. There is no overall score.

Markdown contains all traits, indicators and recent/previous completed-task windows
for every cohort. JSON retains numeric aggregates and comparison metadata, not
transcript text, raw evidence packets or source cursors. Migration retains the
actual previous report as an import, never fabricated historical invocation files.

## Local page

The viewer is three offline files in `reports/`, with no statistics in the page:

| File | Source | Changes when |
|---|---|---|
| `dashboard.html` | copied from `assets/dashboard.html` | the template changes |
| `dashboard.js` | copied from `assets/dashboard.js` (application) | the template changes |
| `dashboard-data.js` | generated: `window.PROGRESS_DATA = {...}` | every `snapshot` / `dashboard` |

The data file is a classic script, not JSON fetched at runtime and not an ES
module: browsers refuse both for pages opened from `file://`, and the page must
open straight from disk. `progress_present.load_dashboard_data()` parses it back.
Its JSON escapes `<`, `>` and `&`. The CSP allows only same-folder scripts
(`script-src 'self' file:`) and blocks all network access. If the data file is
missing the page says so instead of showing an empty deck. Open it in a regular
browser, or through `scripts/serve.mjs`: a read-only loopback server for viewers
that do not run scripts on `file://` pages, such as built-in app browsers.

The summary bar fades in with a short stagger, its numbers count up to their
value (and pulse when a value changes, e.g. on a cohort switch), and on hover a
number lifts and turns red while a red rule draws under it.

Trait cards lift and tilt toward the pointer (`--rx`/`--ry` set by
`dashboard.js`), with a pointer-following glow, a turning emblem and red title
and score rule; keyboard focus gets the same lift. With
`prefers-reduced-motion: reduce` all of it is off, and touch input never tilts. The archive has an
in-page reader and Markdown downloads. Accessible trait dialogs show definitions,
indicators, counts and comparisons. Cohort filters keep course and general work
separate. Gaps in weekly evidence remain unmeasured.

Use the inspected MEGA.dev deck's white canvas, warm card stock, red/black accents,
framed cards, serif titles and monospaced labels. Artwork is original inline SVG.
Do not copy its logo, private account details, card art or fonts, or fetch remote
assets when the dashboard opens. No hosting, uploads, telemetry or background
server is part of this skill.

The footer has an accessible Auto / Light / Dark radio group. Auto follows the
operating system, including changes while open. Explicit choices override the
system and persist in browser-local storage when available. Storage failure
keeps the switch usable for the current page. Apply the chosen palette before
first paint and use it in cards, charts, controls, dialogs and report readers.
Rebuild with `dashboard` for appearance changes; do not append a statistics
snapshot or alter scoring data for a template update.

## Icon families

The inline template uses an explicit `TRAIT_ART` entry for every rubric trait;
never cycle or hash a short set of symbols. Each center silhouette is unique and
expresses that trait's meaning. `CATEGORY_ART` supplies a shared family frame and
a matching category-filter emblem. Card and detail views use the same artwork.
Keep every symbol legible in both themes and when unmeasured.

| Category | Shared frame | Trait symbols |
|---|---|---|
| Direction | Navigation medallion with cardinal points | T01 north-star compass; T02 watchtower; T05 chained portcullis; T06 pierced target |
| Context | Engraved bookplate | T04 anchored map; T09 evidence lens; T10 unfolding folio; T11 folio press; T12 memory grimoire |
| Ground | Circuit hexagon | T03 state terminal; T07 diagnostic oscilloscope; T13 inspection eye; T14 keyed capability port |
| Orchestration | Connected nodes | T15 dispatch raven; T16 branched blocks; T17 sealed mission scroll; T19 isolated parallel lanes; T20 convergence forge |
| Proof | Pointed shield | T08 root circuit; T18 decision scales; T21 annotated quill; T22 calibrated helm; T23 independent verification seal; T24 phoenix return |

These are original SVG line drawings with no external dependencies. Update the
explicit registry when rubric traits change; a missing entry must be visible as
an error rather than silently reusing another trait's icon.
