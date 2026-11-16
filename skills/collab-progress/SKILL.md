---
name: collab-progress
description: Update private collaboration statistics across every coding-agent harness on this machine (Codex, Claude Code and pi chats, also when run inside T3 Code or herdr; other agents via a guided adapter), save a dated report with changes from the previous run, and refresh the local trait-card dashboard. Use at a genuine end-of-chat message or when asked to refresh statistics, show progress, or catch up on chats. Measures how the user collaborates with agents, not product telemetry. A simple thanks during ongoing work is not a closing trigger.
---

# Private collaboration progress

Maintain the user's private 24-trait, 47-indicator collaboration assessment over
all harnesses in one tracker. The user authorized local updates at chat closure
and on request. Never upload, call a course service, install a scheduled job, or
start another model process. Supersedes `codex-progress` and `claude-progress`.

Use this skill before your final farewell when the user clearly ends the work.
Finish remaining authorized work first. “Goodbye” inside quoted material, or with
work still requested, is not a trigger. Missed closures are found by a catch-up.

## Which harness am I in?

Run `PY -X utf8 SKILL_DIR/scripts/progress.py doctor` first in a new
environment (after the prerequisite check below). It detects the harness from
its environment, lists transcript homes, adapters and skills folders, says
whether the current chat can be identified, and returns `next_steps` tagged
`agent`, `human` or `agent+human`. Work through them, then read the reference
for the harness you are in:

| Harness | Kind | Reference |
|---|---|---|
| Claude Code | agent | [references/harness-claude.md](references/harness-claude.md) |
| Codex | agent | [references/harness-codex.md](references/harness-codex.md) |
| pi | agent | [references/harness-pi.md](references/harness-pi.md) |
| T3 Code | GUI hosting other agents | [references/harness-t3code.md](references/harness-t3code.md) |
| herdr | multiplexer hosting other agents | [references/harness-herdr.md](references/harness-herdr.md) |
| anything else | — | [references/harness-onboarding.md](references/harness-onboarding.md) |

A wrapper (T3 Code, herdr, an IDE panel) needs no adapter: the agent it hosts
writes its own transcripts, so also follow that agent's reference. For an agent
without an adapter, the onboarding guide shows how to `probe` its history
(structure only, no message text) and write a user-owned adapter in
`DATA_DIR/adapters/`. Extra transcript folders (second accounts, a provider's
custom `CODEX_HOME`/`CLAUDE_CONFIG_DIR`) are added with
`progress.py home --add HARNESS:LABEL=PATH`. The scoring workflow below is the
same everywhere; one `scan` covers every home and harness.

## First use: prerequisites and data location

`SKILL_DIR` is the folder holding this file; the CLI is
`SKILL_DIR/scripts/progress.py` (Python standard library only). Set
`PYTHONDONTWRITEBYTECODE=1` so no bytecode lands in the skill folder. No path is
hardcoded: everything below is discovered or chosen by the user.

**1. Check the tools, and ask before installing anything.**

| Tool | Needed for | Check |
|---|---|---|
| Python ≥ 3.11 | every command | `python --version`, then `python3 --version`, then (Windows) `py -3 --version` |
| Node.js ≥ 18 | the dashboard server `serve.mjs` and the `.mjs` tests; scoring never needs it | `node --version` |

Use whichever Python command works as `PY` below. If Python is missing or older
than 3.11, stop and tell the user what is missing, then ask for permission to
install it, naming the exact command for their OS, for example
`winget install Python.Python.3.12` (Windows), `brew install python` (macOS) or
`sudo apt install python3` (Debian/Ubuntu). Install only after a clear yes, and
re-check the version afterwards. If they decline, explain that the skill cannot
run and stop. Without Node the statistics still work and the dashboard still
opens from disk in a regular browser; only the server and its tests are
unavailable. Ask before installing Node too (`winget install OpenJS.NodeJS.LTS`,
`brew install node`, `sudo apt install nodejs`). Never install packages: none
are needed, for Python or Node.

**2. Find the data location.** Run `PY -X utf8 SKILL_DIR/scripts/progress.py where`.
It reports `configured`, `data_dir`, `default_data_dir` (= `SKILL_DIR/data`),
the Python in use and which harness transcript folders were found. Any other
command exits with code 2 and `needs_setup: true` while nothing is configured.

**3. If `configured` is false, ask the user where to keep the private data**
before doing anything else. Offer `SKILL_DIR/data` as the default, explain that
it holds private statistics, review packets and coaching notes, and ask whether
they already have a tracker folder to bring along. Then run exactly one of:

```bash
PY -X utf8 SKILL_DIR/scripts/progress.py setup --default
PY -X utf8 SKILL_DIR/scripts/progress.py setup --data "CHOSEN/PATH"
PY -X utf8 SKILL_DIR/scripts/progress.py setup --data "CHOSEN/PATH" --copy-from "EXISTING/TRACKER"
```

`setup` writes `SKILL_DIR/config.json` (a relative path when inside the skill
folder, so the skill stays movable), creates the folder privately, and starts an
empty tracker, reuses an existing one, or copies one (the source is only read).
It refuses to overwrite a tracker or take over a non-empty unrelated folder.
Dates and weekly buckets use the system's local time unless `COLLAB_PROGRESS_TZ`
or a `"timezone"` key in `config.json` names an IANA zone (see storage.md).
`COLLAB_PROGRESS_HOME` overrides the config for one environment; `--data` for
one command. Ask again only if the user wants to move the data.

**Privacy by default.** The data folder gets a `.gitignore` of `*`, a
`PRIVATE.txt` notice and, on POSIX, owner-only permissions; `SKILL_DIR/.gitignore`
lists `data/` and `config.json`. Treat everything there as private: never commit,
upload, attach, paste in full or share it, and never put it in a project folder
unless the user chose that location.

## Runtime

`DATA_DIR` below means the `data_dir` reported by `where`.

- Transcripts (read-only): one adapter per harness in `scripts/adapters/`
  (`codex.py`, `claude.py`). Homes default to `CODEX_HOME`/`~/.codex` and
  `CLAUDE_CONFIG_DIR`/`~/.claude`, are stored in the tracker, and can be
  overridden with `--history-home codex=PATH` / `--history-home claude=PATH`.
- A missing home is skipped; an unreadable one is reported under `errors`.
- Read [references/storage.md](references/storage.md) for layout, cursors and how
  to add another harness. Never put private data in a project or edit transcripts.

```bash
PY -X utf8 SKILL_DIR/scripts/progress.py scan
PY -X utf8 SKILL_DIR/scripts/progress.py prepare --session current --output DATA_DIR/inbox/current.packet.json
```

`scan` reports `by_harness` counts. `--session current` reads the running
harness's session variable (see its reference); otherwise pass a real ID from
`scan`. Never infer an ID from cwd, recency or a pasted transcript. If the data
directory is inaccessible, report the path and leave cursors unchanged.
`setup` creates the tracker; never re-initialize an existing one.

## Review and update

1. Run `scan`. At a farewell, update the current chat if eligible. On an explicit
   refresh/catch-up, review every pending human chat from every harness, in
   batches; report the remaining queue accurately. Never claim a complete refresh
   with pending chats, unreadable sources or harness errors.
2. Run `prepare` for a pending session and read its packet and existing review.
   The `draft` is a skeleton. Read [references/data-contract.md](references/data-contract.md)
   before editing it and [references/rubric.md](references/rubric.md) before scoring.
   Full events: `read-event --session ID --ref U003`. Inspect truncated evidence.
3. Exclude chats about this assessment, tracker development/migration, score
   manipulation and subagent/guardian work. An excluded chat is committed with
   `episodes: []` and a generic `exclusion_reason`. In ordinary work containing a
   coaching/progress turn, exclude only that maintenance portion.
4. Split contiguous objectives into episodes; keep follow-ups and repairs
   together. Preserve episode IDs and unchanged rows; extend the last episode if
   work continues, append one for a new objective. Never split a task for a rate.
5. Review all 24 traits and 47 indicators for every new or revised episode.
   Counts are **user-originated**: assistant suggestions, tests and docs alone do
   not show the user's behaviour; acting on advice may count, accepting work does
   not. Question-dialog answers appear as `User answer: …` user events — the
   choice is the user's, the option wording is the assistant's.
6. Distinguish `ineligible`, `unobserved`, `applied`, `declined`, `missed`. A miss
   needs evidence the task offered the opportunity. Do not penalize letting the
   agent do routine work. Standing instructions (AGENTS.md, CLAUDE.md, memory)
   apply in scope; the user need not repeat them.
7. Cite real `U###`, `A###`, `E<ordinal>` refs. `applied`/`declined` need a user
   ref. `verified_outcome: true` needs inspected user/tool outcome evidence, not an
   assistant success claim; an exit code contradicted by output is insufficient.
8. Cohort: `mega-dev` only for explicitly identified course work, `other-course`,
   `general`, or `unclassified`. Course codes must be observed. Summaries stay
   generic: no secrets, quotes, names, private URLs or paths.
9. Save the completed draft as `DATA_DIR/inbox/ID.review.json` and run:

   ```bash
   PY -X utf8 SKILL_DIR/scripts/progress.py commit --file DATA_DIR/inbox/ID.review.json
   PY -X utf8 SKILL_DIR/scripts/progress.py report --cohort course
   PY -X utf8 SKILL_DIR/scripts/progress.py scan
   ```

   Commit is transactional; an edited source prefix needs a new `prepare`;
   identical replays are no-ops. Never edit the database to pass validation.
10. End every invocation with exactly one `snapshot`, even with no changes:
    `PY -X utf8 SKILL_DIR/scripts/progress.py snapshot`. It writes an immutable
    report in `DATA_DIR/reports/history/` and refreshes the dashboard (`DATA_DIR/reports/dashboard.html` + its generated `dashboard-data.js`).
11. Delete only this run's packet/review files after a successful commit. At
    closure give one sentence: task count, snapshot link, dashboard link. Do not
    force a coaching debrief into every farewell.

## Read progress and dashboard

`report` writes `reports/latest.md|json`; `--cohort course|mega-dev|general|…`
writes cohort reports. Fewer than three eligible episodes stays unmeasured;
declines never lower a rate; there is no overall score or claim of improvement.
See [references/presentation.md](references/presentation.md). `dashboard` rebuilds
the offline viewer without adding a report.

**Showing the dashboard.** The page runs JavaScript, so a static file preview
(such as an app's built-in browser showing a `file://` page) looks empty. Either
open `DATA_DIR/reports/dashboard.html` in a regular browser, or start the
built-in server and open its URL in any browser, built-in ones included:

```bash
node SKILL_DIR/scripts/serve.mjs            # prints {"url": "http://127.0.0.1:4785/", ...}
node SKILL_DIR/scripts/serve.mjs --port 0   # any free port; --open also launches the default browser
```

`serve.mjs` is Node standard library only. It finds the data folder like
`progress.py` (`--data`, `COLLAB_PROGRESS_HOME`, `config.json`; exit code 2 when
unconfigured), listens on 127.0.0.1 only, accepts only `GET`/`HEAD` with a
loopback `Host`, and serves exactly `dashboard.html`, `dashboard.js` and
`dashboard-data.js` — never the database, inbox, coaching notes or config. Files
are read on each request, so after a new `snapshot` a reload is enough. Run it
in the background and stop it when the user is done (Ctrl+C or stop the task).

## Tests

```bash
cd SKILL_DIR/scripts && PY -X utf8 -m unittest test_harnesses test_setup test_admin test_multi test_progress_claude test_progress_codex test_presentation && node test_dashboard.mjs && node test_serve.mjs
```
