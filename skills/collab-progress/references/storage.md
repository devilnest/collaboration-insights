# Private progress storage

One tracker covers every harness. No path is built in: the user chooses the
folder on first use (`setup`, default `SKILL_DIR/data`) and it is recorded in
`SKILL_DIR/config.json` (relative when inside the skill folder). Resolution order:
`--data` for one command, then `COLLAB_PROGRESS_HOME`, then `config.json`; with
none of these every tracker command exits with code 2 and `needs_setup: true`.
`where` prints the current answer. No network service or API key is used.

**Time zone.** Active dates, weekly buckets and report labels use the system's
local time. To pin one IANA zone, set `COLLAB_PROGRESS_TZ` (for example
`America/New_York`) or add `"timezone": "America/New_York"` to `config.json`.
Named zones need Python's tz database; on Windows that is the `tzdata` package.
Without it, or for an unknown name, the skill falls back to local time and the
reports say `local time`. The dashboard shows times in the same zone, or in the
viewer's own zone when none is set.

**Baseline import** (`init --baseline DIR`) reads an assessment record and an
evidence ledger, such as the output of the MEGA.dev assessment. Each ledger
episode may carry an optional `cohort` (`general`, `mega-dev`, `other-course`)
and `course_episode_ids`. Episodes without a valid cohort are imported as
`unclassified`.

The folder is private by default: `.gitignore` of `*`, a `PRIVATE.txt` notice,
owner-only permissions on POSIX, and `data/` + `config.json` in the skill's own
`.gitignore`. On Windows, a folder under the user's profile is already readable
only by that user and administrators; elsewhere, tell the user if the chosen
folder looks shared (another drive root, a synced or network folder).

A tracker may carry history from earlier per-harness trackers (for example a
copy of a Codex tracker with its baseline, merged with Claude reviews); such
imports are recorded in `audit`, and their source folders are never modified.

## Layout

- `progress.sqlite`: per-chat latest reviews, per-episode judgments, source
  fingerprints/cursors, change audit, aggregate snapshots, and the
  `history_homes` setting (`{"codex": PATH, "claude": PATH}`).
- `baseline/`: exact copies of the original Codex assessment, evidence ledger,
  audit, metadata and report, with their hashes in the settings.
- `reports/latest.md` and `latest.json`: original baseline, cumulative counts,
  work since baseline, recent/previous 10 completed tasks, all indicators, and
  weekly volume. `course.md/json` is the combined course view. Other cohort
  reports are separate files.
- `coaching/`: Markdown reviews saved by `collab-coach`, one file per review.
- `inbox/`: temporary redacted review packets and completed review JSON. Delete
  only the files created by a completed update; they may contain source snippets.
- `reports/history/ID.md` and `ID.json`: immutable status for each skill invocation,
  including unchanged runs. IDs contain UTC generation time.
- `reports/history/index.json`: derived archive index.
- `reports/dashboard.html`, `dashboard.js`, `dashboard-data.js`: the offline trait deck
  and report viewer; only `dashboard-data.js` holds statistics. No network requests.

A tracker started with `setup` has a zero baseline; one copied from an older
tracker keeps that tracker's imported baseline under `baseline/`. Episodes are not
labelled by harness; trends compare collaboration habits, whichever agent was
used. Only explicitly known course work is labelled; uncertain course identity
is `unclassified`.

## Discovery and adapters

`scripts/progress_core.py` holds everything harness-neutral: event numbering
(`U###`, `A###`, `E<ordinal>`), administrative-turn detection, fingerprints,
packets, validation and storage. `History` combines one read-only adapter per
harness from `scripts/adapters/`:

| Adapter | Home | Details |
|---|---|---|
| `codex.py` | `CODEX_HOME` or `~/.codex` | [harness-codex.md](harness-codex.md) |
| `claude.py` | `CLAUDE_CONFIG_DIR` or `~/.claude` | [harness-claude.md](harness-claude.md) |
| `pi.py` | `PI_CODING_AGENT_DIR` or `~/.pi/agent` | [harness-pi.md](harness-pi.md) |

Homes come from the tracker's `history_homes`, then defaults for unlisted
harnesses, then `--history-home HARNESS=PATH`. A missing home is skipped; a
harness whose index cannot be read is reported in `scan.errors` without hiding
the other harnesses. A session ID found in two harnesses is an error.

Built-in adapters: `codex.py`, `claude.py`, `pi.py`. Homes are keyed `HARNESS`
or `HARNESS:LABEL`, so one harness may have several (`progress.py home --add`
stores them in the tracker's `history_homes`). **Adding a harness:** a module
with `NAME`, `SESSION_ENV`, `default_home()` and `READER` (a class with
`catalog()` and `raw(meta)`), placed in `DATA_DIR/adapters/` for a user-owned
adapter (loaded automatically, never overwritten by updates, cannot replace a
built-in, failures reported in `scan.errors`) or in `scripts/adapters/` plus
`adapters()` in `progress_core.py` to ship it. The full contract and the
`probe` workflow are in [harness-onboarding.md](harness-onboarding.md).
Ordinals must be stable as a transcript grows, or every review goes stale.

Each assessed thread has a reviewed source-prefix fingerprint and event ordinal.
Every scan compares all human threads, so an older chat receiving new work is
found even if it is older than a global timestamp cursor. Tool-result updates
at an existing ordinal also change the fingerprint. Automatic guardians,
subagents and explicitly excluded assessment threads do not become scored work.

`scan` reports candidates; only a successful reviewed commit advances a cursor.
Newly appended events beyond the committed prefix remain pending. Real source
edits inside that prefix invalidate a stale review. Pure farewell turns and pure
progress/coaching maintenance turns (`collab-*`, and the legacy `codex-*` /
`claude-*` names) are ignored in the fingerprint, while keeping stable refs.
A Codex skill pick arrives as a Markdown link (`[$collab-progress](…/SKILL.md)`);
it is reduced to the skill name before this check. When newly ignored turns sit
after the last scored event, the cursor may move back to that event, but only
when the fingerprint over the skipped range is unchanged; a retreat over scored
work is still rejected.
Mixed requests containing actual product work remain visible. Uncertain closing
wording is conservatively left for review. Baseline cursors come from reviewed
event boundaries, never from filesystem modification dates.

## Privacy and recovery

There is no networking, telemetry, external model process, upload command, API
key, or course connector in either skill's helper. Analysis takes place in the
current agent session, so this is not an offline-model guarantee. Never attach
the database or reports to an external service as part of these workflows.

Packets use best-effort secret/query/email redaction. Derived summaries must
still avoid identifiers and verbatim excerpts. The tracker stores references to
history rather than duplicating full transcripts. The original history and
projects are read-only; no repository mentioned in history is opened for scoring.

Back up the data folder to another private local directory if desired. Keep
the baseline files and SQLite database together. If commit succeeds but a report
write fails, the database remains authoritative; run `report` again. If source
history is unavailable, keep its prior counts and expose the gap. Do not drop the
session or advance its cursor. Never initialize over an existing database.

No lifecycle hooks or scheduler are installed in this skills-first version.
Goodbye triggers are model-driven while a response is active; the skill
description and the global Codex instruction point the agent to this skill at a genuine closure. App-close or
startup processing can later reuse the scan cursor through a reviewed hook/plugin.

## Presentation recovery

`snapshot` reads the tracker without changing judgments, counts or cursors. It
saves a dated report, refreshes legacy aliases and rebuilds the viewer. An
exclusive writer lock protects concurrent generation. Invalid history or a lock
is reported, never silently discarded. A missing Markdown companion can be
restored from its saved JSON after interrupted generation. `dashboard` only
rebuilds the derived viewer and index. Include report history in private backups.
