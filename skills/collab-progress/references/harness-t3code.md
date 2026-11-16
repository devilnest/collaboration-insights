# Running inside T3 Code

T3 Code is a GUI that drives other agents (Codex through its app-server, Claude
Code through the Agent SDK, and optionally Cursor, OpenCode, pi and others). It
does not need an adapter of its own: the hosted agent writes its normal native
history, and this skill reads that.

## Checklist

1. **Which provider runs this thread?** Ask the human if unsure, then also follow
   that agent's reference (`harness-codex.md`, `harness-claude.md`, `harness-pi.md`).
2. **Custom provider homes** (human): T3 Code lets each provider instance use its
   own `CODEX_HOME` or `CLAUDE_CONFIG_DIR` (Settings → Providers). If one is set,
   register it so its chats are scanned:
   `progress.py home --add codex:t3=PATH` or `home --add claude:t3=PATH`.
   An empty setting means the provider's normal default, already covered.
3. **Skill visibility** (human): with a custom `CLAUDE_CONFIG_DIR`, Claude loads
   skills from that directory's `skills/` folder (and the project's
   `.claude/skills`), so link `collab-progress` and `collab-coach` there. For Codex
   and pi, `~/.agents/skills` from the installer applies.
4. **Current chat:** if the provider exports its session variable, `--session
   current` works; otherwise use the `scan` + confirm flow from
   `harness-onboarding.md` step 4.
5. **Dashboard:** open `DATA_DIR/reports/dashboard.html` in a browser, or run
   `node SKILL_DIR/scripts/serve.mjs` and open the printed URL.

## Notes

- T3 Code's own data (thread events, settings, a SQLite store under its base
  directory) is not read by this skill and is not needed.
- `T3CODE_TELEMETRY_ENABLED=false` controls T3 Code's product telemetry; it has
  no effect on this skill, which never uses the network.
- Messages composed in T3 Code reach the provider as ordinary user turns, so
  evidence rules are those of the hosted agent.
