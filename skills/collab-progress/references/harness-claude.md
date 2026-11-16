# Running in Claude Code

## Install and invoke

- Skill folder: `~/.agents/skills/collab-progress`, linked (Windows junction /
  symlink) as `~/.claude/skills/collab-progress` so every project sees it. A
  project can instead link it under `<project>/.claude/skills/`.
- Invoke with `/collab-progress`, or implicitly from the description.
- Run commands with the Bash tool (Git Bash on Windows) or PowerShell:

```bash
export PYTHONDONTWRITEBYTECODE=1
S="$SKILL_DIR/scripts/progress.py"   # SKILL_DIR: folder of the loaded SKILL.md
python -X utf8 "$S" where            # first run: see SKILL.md "First use"
DATA_DIR=$(python -X utf8 "$S" where | python -X utf8 -c "import json,sys;print(json.load(sys.stdin)['data_dir'])")
python -X utf8 "$S" scan
python -X utf8 "$S" prepare --session current --output "$DATA_DIR/inbox/current.packet.json"
```

Do not pass `-I` to Python here: isolated mode ignores `PYTHONDONTWRITEBYTECODE`
and drops the script folder from the import path that `adapters/` needs.

## Session identity

`--session current` reads `CLAUDE_CODE_SESSION_ID`, set by Claude Code for the
running session. The transcript is `~/.claude/projects/<project-slug>/<id>.jsonl`
(`CLAUDE_CONFIG_DIR` overrides `~/.claude`). It is written live: the newest turn
may be missing or its last line unfinished; the adapter ignores an unfinished
last line. If the session variable is absent, use an ID from `scan`.

## How Claude records map to evidence (`scripts/adapters/claude.py`)

| Transcript record | Evidence |
|---|---|
| `user` with typed text (`turnOrigin` human) | `U###`; `promptId` = turn |
| `<system-reminder>`, local-command output, `isMeta`, compact summaries | dropped |
| slash command (`<command-name>`) | `U###` text `/name args` |
| `AskUserQuestion` tool result | `U###` `User answer: …` |
| `user` with non-human `turnOrigin` (task/hook notifications) | tool event, never user evidence |
| assistant `text` block | `A###` |
| assistant `tool_use` / user `tool_result` | `E<line>` tool events |
| `system` `compact_boundary` | `contextCompaction` tool event |
| transcript with `isSidechain`, or files under `<id>/subagents/` | automated, never scored |

Ordinals are 1-based line numbers, so refs stay stable as the file grows.

## Evidence notes specific to Claude Code

- Plan-mode approvals, permission prompts the user accepted, and answers in
  question dialogs are user decisions; the wording of the options is not.
- Task-list (`update_plan`/`TodoWrite`) and wrap-up tool calls are assistant
  bookkeeping, not user decomposition or acceptance.
- Project `CLAUDE.md`/`AGENTS.md` and memory files are standing user
  instructions in scope (rule 6), but only where they were actually loaded.
- The desktop app's browser pane shows `file://` pages as static, script-free
  copies, so the dashboard looks empty there. Serve it instead:
  - add a launch entry to the project's `.claude/launch.json` and open it with the
    browser pane's `preview_start` by name:

    ```json
    { "name": "collab-progress-dashboard", "runtimeExecutable": "node",
      "runtimeArgs": ["SKILL_DIR/scripts/serve.mjs", "--port", "4785"], "port": 4785 }
    ```

    (replace `SKILL_DIR` with the real absolute path; the pane manages and stops
    the process), or
  - run `node SKILL_DIR/scripts/serve.mjs` in the background and open the printed
    URL; stop the background task when the user is done.
