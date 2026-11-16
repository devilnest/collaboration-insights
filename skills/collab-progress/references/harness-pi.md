# Running in pi (pi coding agent)

## Install and invoke

- pi loads Agent Skills from `~/.pi/agent/skills/`, `~/.agents/skills/`,
  `.pi/skills/` and `.agents/skills/`. The installer's `~/.agents/skills` copy is
  therefore found without extra steps; `/reload` picks it up in a running session.
- Ask pi to use `collab-progress` (or `collab-coach`) by name.
- Run commands with pi's bash tool: `PY -X utf8 SKILL_DIR/scripts/progress.py …`.

## Session identity

pi does not export its session ID to tools, so `--session current` fails here.
Run `scan`, show the human the pending `pi` chats for this project, and pass the
confirmed ID with `--session ID`. The ID is the `id` in the session file's header
(also the UUID at the end of the file name). Never pick by recency alone.

## Where pi history comes from (`scripts/adapters/pi.py`)

- Home: `PI_CODING_AGENT_DIR`, else `~/.pi/agent`; sessions in
  `sessions/--<cwd-slug>--/<timestamp>_<session-id>.jsonl`. Another folder:
  `progress.py home --add pi:LABEL=PATH`.
- Format v3: header `{"type":"session","id",…}`, then entries with
  `id`/`parentId`/`timestamp`. Ordinals are line numbers (append-only files).
- `message` entries: `user` → `U###`; assistant `text` blocks → `A###`;
  `toolCall` blocks and `toolResult` messages → tool events; `thinking` ignored;
  `custom` messages → harness events, never user evidence.
- `compaction` → compaction event; `branch_summary` → tool event. Model, usage,
  label and extension-state entries are skipped.
- Branches: pi keeps abandoned branches in the same file. All of them are read;
  what the user typed on an abandoned branch is still their behaviour, but judge
  outcomes on the branch they continued.
- Forked sessions (`parentSession` in the header) are separate chats.

The block shapes for tool calls/thinking and `PI_CODING_AGENT_DIR` follow pi's
public types; if `doctor` or `scan` reports a pi read error, run
`progress.py probe ~/.pi/agent/sessions` and compare with the adapter.

## Evidence notes specific to pi

- `/tree` navigation and `/fork` are user steering decisions; the agent's own
  compaction is not.
- Extension (`custom`) messages are tool output, not the user's words.
