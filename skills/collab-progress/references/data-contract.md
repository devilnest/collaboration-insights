# Review data contract

`prepare` produces a local packet with `context`, `existing_assessment`, and
`draft`. Save **only the completed `draft`** to the review JSON passed to `commit`.
The script never infers dispositions from keywords or generates model judgments.

## Session envelope

- `schema_version`: integer `1`.
- `rubric_version`: `mega-private-v1`.
- `session_id`: actual source thread ID from the packet.
- `source_revision`: exact source-prefix fingerprint from the packet.
- `base_review_revision`: exact prior-review fingerprint from the draft, or null
  for a new chat. This prevents a second stale reviewer from overwriting a newer
  review. Preserve it when preparing the commit; it is consumed by the helper.
- `reviewed_through_ordinal`: exact cursor from the packet, non-negative integer.
- `exclusion_reason`: `null`, or a generic reason for excluding the whole chat.
- `episodes`: the complete replacement list for this chat, including unchanged
  historical episodes. Empty only for an excluded/no-task chat.
- `observations`: derived observations; each has `trait_id`, `episode_id`,
  `statement` (40–280 characters), and `evidence_refs` pointing to recorded events.

## Episode

`id` is stable within the chat. Preserve the import's IDs; for new work use
`ep-START_ORDINAL`. `start_ordinal` and `end_ordinal` are inclusive, ordered event
bounds. Episodes cannot overlap. Keep follow-ups within the same objective.

- `closed`: true when the objective is resolved, abandoned, or replaced; false
  while work continues. Recent/previous windows use completed episodes only.
- `cohort`: `general`, `mega-dev`, `other-course`, or `unclassified`.
- `course_episode_ids`: observed codes, e.g. `S01E01`; empty when unknown.
- `work_class`: one of the nine classes in the frozen rubric's original record:
  `bug-fix`, `feature-build`, `refactor`, `investigation`, `release-operations`,
  `documentation`, `configuration-maintenance`, `research`, `other`.
- `summary`: 8–280 characters, original generic prose with no identifying details.
- `languages`: observed language tokens from actual tool/file/build evidence,
  not the assistant's prose or an offhand user mention; otherwise empty.
- `baseline`: false for new episodes. An imported episode keeps its original flag.
- `traits`: all T01–T24 keys. `indicators`: all 47 keys from `rubric.json`.
  Every key has a judgment object below.
- `start_at_ms` and `active_dates` are helper-maintained source metadata. Preserve
  existing values; the helper derives them for new/revised episodes.

## Judgment object

```json
{
  "state": "applied",
  "verified_outcome": false,
  "evidence_refs": ["U003"],
  "outcome_refs": [],
  "reason": "The user specified a concrete expected state before implementation."
}
```

State meanings:

- `ineligible`: there was no qualifying opportunity, with a specific reason.
- `unobserved`: the record cannot establish what was needed, with the visibility
  limitation stated. Never use an unresolved draft placeholder as a finished row.
- `applied`: the behaviour came from the user. Cite at least one non-maintenance
  user message. Merely accepting the assistant's work is insufficient.
- `declined`: the user deliberately skipped this behaviour, with user evidence.
- `missed`: a qualifying opportunity existed but the user behaviour did not appear;
  cite the message/event establishing the opportunity. This is not a failure grade.

Each reason is 1–500 characters. Eligible judgments need refs inside their episode.
Verified outcomes require `applied` plus independent user/tool `outcome_refs`.
Assistant assertions alone are insufficient. An eligible indicator requires an
observed eligible parent. Source prefix edits, invented refs, overlap, missing
keys, and unresolved review placeholders reject the write without advancing a cursor.

## Counts and interpretation

Each eligible episode contributes exactly one applied/declined/missed count.
`eligible = applied + declined + missed`; `verified_outcome <= applied`.
Ineligible and unobserved rows are not missed. Raw opportunities remain stored
below threshold, so the third opportunity can mature a previously unmeasured row.
The displayed rate is `applied / (eligible - declined)` when at least three
opportunities are observed. Declines never lower it. No composite score exists.

Baseline files are immutable snapshots; current totals can change if a task is
reopened and new evidence changes its assessment. A revision replaces that
session's prior contribution, including corrections. Snapshots and the audit table
retain when updates occurred. Identical payload replay does not create another
contribution or snapshot. Scan/prepare/coaching never mark a chat as processed.

The original external record constrained each indicator disposition count to its
parent's corresponding aggregate count. That constraint can conflict with genuine
episode evidence: an episode can apply the broad parent habit while missing one
narrow indicator. This private tracker retains the original baseline unchanged
but stores new parent/indicator dispositions independently. It enforces eligibility
containment, never changes evidence to manufacture export compatibility, and
produces no external submission payload.

Do not change the rubric definitions or reinterpret old rows opportunistically.
A deliberate rubric revision requires a new version and a documented migration.
