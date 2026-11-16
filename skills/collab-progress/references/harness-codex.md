# Running in Codex

## Install and invoke

- Skill folder: `~/.agents/skills/collab-progress` (Codex loads skills from
  `~/.agents/skills`). Invoke with `$collab-progress` or implicitly from the
  description. `agents/openai.yaml` supplies the Codex display name and prompt.
- Run commands in PowerShell (Windows) or a POSIX shell:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$S = Join-Path $SKILL_DIR "scripts\progress.py"   # SKILL_DIR: folder of the loaded SKILL.md
python -X utf8 $S where              # first run: see SKILL.md "First use"
$DATA_DIR = (python -X utf8 $S where | ConvertFrom-Json).data_dir
python -X utf8 $S scan
python -X utf8 $S prepare --session current --output (Join-Path $DATA_DIR "inbox\current.packet.json")
```

## Session identity

`--session current` reads `CODEX_THREAD_ID`, then `CODEX_SESSION_ID`. If neither
exists, find the real thread ID through the host's thread tools or `scan`; never
pick the newest thread by timestamp.

## Where Codex history comes from (`scripts/adapters/codex.py`)

- Home: `CODEX_HOME`, otherwise `~/.codex`.
- Index: newest numbered `state_*.sqlite` (`threads` table) and items from the
  newest `thread_history_*.sqlite` (`thread_items`), opened read-only. Their folder
  is `CODEX_SQLITE_HOME`, else `sqlite_home` in `config.toml`, else the home.
- Fallback: `sessions/` and `archived_sessions/` JSONL rollouts for threads absent
  from the history store; `<environment_context>`, `<skills_instructions>` and
  apps-page injections are dropped.
- Threads whose `source` is a dict or names a subagent (guardians, reviewers) are
  automated and never scored.
- Question replies (`<send_user_message_question_reply>`) become `User answer: …`.

This adapter is byte-for-byte the original `codex-progress` reader, so source
revisions and cursors from the Codex tracker remain valid after the merge.

## Evidence notes specific to Codex

- `$codex-progress`, `$codex-coach`, `$collab-progress` and `$collab-coach` turns
  are maintenance; pure maintenance turns are ignored in the fingerprint.
- Approval prompts the user answered are user decisions; Codex's own plan updates
  are assistant bookkeeping.
- The global Codex instruction (`~/.codex/AGENTS.md`) may point here at closure;
  update it to name `collab-progress` instead of `codex-progress`.
- To view the dashboard in an embedded browser that will not run scripts on
  `file://` pages, run `node $SKILL_DIR\scripts\serve.mjs` in the background and
  open the printed `http://127.0.0.1:4785/`; stop it when the user is done.
