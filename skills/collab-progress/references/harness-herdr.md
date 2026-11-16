# Running inside herdr

herdr is a terminal multiplexer for coding agents: it hosts agent CLIs (Claude
Code, Codex, pi, OpenCode, …) in panes and never calls a model itself. Panes
have `HERDR_ENV=1`. This skill reads the hosted agents' native transcripts, so
herdr needs no adapter.

## Checklist

1. **Which agent runs in this pane?** Follow that agent's reference
   (`harness-claude.md`, `harness-codex.md`, `harness-pi.md`). The skill must be
   visible to that agent (the installer covers `~/.agents/skills` and
   `~/.claude/skills`).
2. **Current chat:** several panes can work in the same project at once, so the
   newest transcript is often *not* this pane's. Use the agent's session variable
   when it exists; otherwise show the human the candidates from `scan` and use
   the one they confirm (`harness-onboarding.md` step 4).
3. **Multi-agent work:** chats driven by another agent through herdr's CLI or
   socket API (prompts sent pane-to-pane) are orchestrated work. Score the human's
   messages; prompts one agent sent to another are agent briefs (T17), not the
   user's own words, unless the human wrote or edited them.
4. **Dashboard:** run `node SKILL_DIR/scripts/serve.mjs` in a spare pane and open
   the printed URL, or open `DATA_DIR/reports/dashboard.html` in a browser.

## Notes

- herdr's optional pane-history log is off by default and is not read by this
  skill; transcripts come from the agents themselves.
- Stop the dashboard server pane when finished.
