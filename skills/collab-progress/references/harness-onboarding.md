# Making the skill work in any harness

Follow this when `doctor` reports an unknown or partly supported environment, or
when the human uses a tool that has no `harness-<name>.md` yet. Every step says
who acts: **agent** (you), **human**, or both. Ask before installing anything,
writing code into the user's data folder, or reading a new transcript store.

## 0. Run the doctor

```bash
PY -X utf8 SKILL_DIR/scripts/progress.py doctor
```

It reports which harness it can detect from the environment, Python/Node, the
data folder, every transcript home and how many chats each holds, whether a
current-session ID is available, which skills folders contain the skill, and
`next_steps` (each tagged `agent`, `human` or `agent+human`). Work through those
steps; rerun `doctor` until it says everything is in place.

## 1. Which kind of harness is this?

| Kind | Examples | What reads the chats |
|---|---|---|
| **Agent** — runs the model loop, writes its own transcripts | Claude Code, Codex, pi, OpenCode, Gemini CLI, Cursor agent | an adapter for that agent |
| **Wrapper / multiplexer / GUI** — hosts other agents | herdr, T3 Code, IDE panels, tmux setups | the adapters of the agents it hosts |

If `doctor` cannot tell, **ask the human** which tool they use and, for a
wrapper, which agent runs in this pane/thread. Do not guess from the folder name.

## 2. Make the skill visible to the agent (human, once)

The installer puts the skill in `~/.agents/skills` (Codex, pi and other
Agent-Skills tools read it) and links it into `~/.claude/skills` (Claude Code).
If the agent loads skills from elsewhere — a custom `CLAUDE_CONFIG_DIR`,
`PI_CODING_AGENT_DIR`, a per-account directory configured in a wrapper — the
human links or copies `collab-progress` and `collab-coach` there too. `doctor`
lists which skills folders contain the skill.

## 3. Make the transcripts readable

- **Supported agent, default location:** nothing to do.
- **Supported agent, other location** (for example a T3 Code provider instance
  with its own `CODEX_HOME` / `CLAUDE_CONFIG_DIR`, or a second account): ask the
  human for the folder, then register it under a labelled key:

  ```bash
  PY -X utf8 SKILL_DIR/scripts/progress.py home --add codex:t3-work=~/.codex_work
  PY -X utf8 SKILL_DIR/scripts/progress.py home            # list
  PY -X utf8 SKILL_DIR/scripts/progress.py home --remove codex:t3-work
  ```

  Keys are `HARNESS` or `HARNESS:LABEL`; one harness may have several homes.
- **Agent without an adapter:** go to step 5.

## 4. Identify the current chat

Claude Code and Codex export the session ID (`CLAUDE_CODE_SESSION_ID`,
`CODEX_THREAD_ID`). pi, herdr panes and several wrappers do not. Then:
run `scan`, show the human the few pending chats for this project (time, first
words, harness), and use the ID they confirm with `--session ID`. Never pick the
newest chat by timestamp alone — a parallel pane may be newer.

## 5. Teach the skill a new agent (agent + human)

1. **Ask** the human where the agent keeps its history and whether it may be
   read. Check the agent's own docs for a "session format" page first.
2. **Probe** the folder. This prints structure only — record types, key names,
   roles, content-block types, SQLite tables and row counts — never message text:

   ```bash
   PY -X utf8 SKILL_DIR/scripts/progress.py probe ~/path/to/agent/sessions
   ```

3. **Write an adapter** at `DATA_DIR/adapters/<name>.py` (the user's private
   folder, so skill updates never overwrite it). Copy the closest built-in
   adapter (`scripts/adapters/pi.py` for append-only JSONL, `codex.py` for
   SQLite) and keep the contract:

   | Name | Meaning |
   |---|---|
   | `NAME` | short lowercase harness name, not a built-in one, no `:` |
   | `SESSION_ENV` | env vars holding the current session ID (may be empty) |
   | `default_home()` | the default transcript folder, honouring the agent's own env var |
   | `READER(home)` | class with `catalog()` and `raw(meta)` |
   | `catalog()` | list of `dict(id, rollout_path, source, created_at)`; `source` is `'human'`, or contains `subagent` for automated work |
   | `raw(meta)` | `(origin, [(ordinal, ms, turn_id, item), ...])` |

   `item` shapes: `userMessage{content:[{type:'text',text}]}` for what the person
   typed (question-dialog answers as `<send_user_message_question_reply>[{"answer":…}]`),
   `agentMessage{text}` for assistant prose, `mcpToolCall{tool, arguments, result}`
   for tool calls/results and harness notices, `contextCompaction{}`.
   **Ordinals must stay stable as the file grows** (line numbers of an
   append-only file, or a database row order) or every review goes stale.
   Drop injected system text; never turn harness notifications into user evidence;
   mark subagent transcripts so they are never scored.
4. **Test it** with a small synthetic fixture (see `test_harnesses.py`), then run
   `doctor` and `scan`. A broken custom adapter is reported, never fatal.
5. **Share it.** If it works, offer the human to send the adapter (code only, no
   transcripts) to the skill's maintainers so it can ship as a built-in.

## 6. What the human may need to do

- Install Python 3.11+ (and Node for the dashboard server) — the agent asks first.
- Choose the private data folder on first use.
- Link the skill into any extra skills folder their harness uses (step 2).
- Tell the agent about extra transcript folders (step 3) and confirm the current
  chat when no session variable exists (step 4).
- In wrappers that store their own logs or telemetry (for example T3 Code), nothing
  is needed for this skill: it reads only the hosted agents' native transcripts.
