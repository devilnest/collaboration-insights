"""Append-only report snapshots and an offline viewer. No network or scoring writes."""
from contextlib import contextmanager
import datetime as dt
import json
import os
from pathlib import Path
import re
import time

from progress_core import atomic_json, atomic_text, read_json, rubric, timezone_label, timezone_name

SCOPES = ('all', 'course', 'mega-dev', 'general', 'other-course', 'unclassified')
SCOPE_NAMES = {'all': 'All work', 'course': 'All courses', 'mega-dev': 'MEGA.dev',
               'general': 'General work', 'other-course': 'Other courses', 'unclassified': 'Unclassified history'}
GROUPS = {'Direction': ['T01', 'T02', 'T05', 'T06'],
          'Context': ['T04', 'T09', 'T10', 'T11', 'T12'],
          'Ground': ['T03', 'T07', 'T13', 'T14'],
          'Orchestration': ['T15', 'T16', 'T17', 'T19', 'T20'],
          'Proof': ['T08', 'T18', 'T21', 'T22', 'T23', 'T24']}
COUNT_KEYS = ('eligible', 'applied', 'declined', 'missed', 'verified_outcome', 'unobserved')
ID = re.compile(r'^[A-Za-z0-9_-]+$')


def usable_rate(counts):
    if not counts or counts.get('eligible', 0) < 3:
        return None
    denominator = counts['eligible'] - counts.get('declined', 0)
    return counts.get('applied', 0) / denominator if denominator > 0 else None


def movement(current, previous):
    """Rates compare the same cohort; counts never masquerade as rate gains."""
    value, old = usable_rate(current), usable_rate(previous)
    changed = previous is not None and any(current.get(k, 0) != previous.get(k, 0) for k in COUNT_KEYS)
    if previous is None:
        return dict(direction='initial', arrow='—', delta_pp=None, label='First saved comparison', counts_changed=False)
    if value is None or old is None:
        direction = 'newly-measured' if value is not None else 'below-threshold' if old is not None else 'unmeasured'
        label = {'newly-measured': 'Newly measured', 'below-threshold': 'Below measurement threshold',
                 'unmeasured': 'Not enough comparable evidence'}[direction]
        return dict(direction=direction, arrow='—', delta_pp=None, label=label, counts_changed=changed)
    delta = (value - old) * 100
    direction = 'up' if delta > 1e-10 else 'down' if delta < -1e-10 else 'flat'
    delta = round(delta, 6) if direction != 'flat' else 0.0
    arrow = {'up': '↑', 'down': '↓', 'flat': '→'}[direction]
    label = '→ 0.00 pp' if not delta else f'{arrow} <0.01 pp' if abs(delta) < 0.005 else f'{arrow} {delta:+.2f} pp'
    return dict(direction=direction, arrow=arrow, delta_pp=delta, label=label, counts_changed=changed)


def compare_scope(current, previous):
    result = {}
    for kind in ('traits', 'indicators'):
        result[kind] = {key: movement(value, (previous or {}).get('cumulative', {}).get(kind, {}).get(key))
                        for key, value in current['cumulative'][kind].items()}
    return result


def counts_key(view):
    """Fingerprint of the counts a comparison looks at (cumulative traits and indicators)."""
    cumulative = (view or {}).get('cumulative', {})
    return json.dumps({kind: cumulative.get(kind, {}) for kind in ('traits', 'indicators')}, sort_keys=True)


def comparison_base(scope, view, history):
    """Most recent earlier snapshot whose counts for this cohort differ from `view`.

    Runs that change nothing (maintenance, re-confirmations, moving the data folder)
    must not reset every arrow to "unchanged"; they carry the last real change forward.
    With no differing snapshot the immediately preceding one is used (all flat).
    """
    key = counts_key(view); fallback = None
    for snap in reversed(history or []):
        other = snap.get('scopes', {}).get(scope)
        if other is None:
            continue
        fallback = fallback or snap
        if counts_key(other) != key:
            return snap
    return fallback


def snapshot_payload(views, generated_at, snapshot_id, previous=None, origin='skill-run', history=None):
    # Only numeric aggregates enter the viewer; transcript cursors and descriptive baseline prose stay in the tracker.
    clean = {scope: {key: view[key] for key in ('cohort', 'cumulative', 'since_baseline', 'recent_10', 'previous_10')}
             for scope, view in views.items()}
    baseline = {row['trait_id']: row['counts'] for row in views.get('all', {}).get('baseline', {}).get('traits', [])}
    history = history if history is not None else ([previous] if previous else [])
    bases = {scope: comparison_base(scope, view, history) for scope, view in clean.items()}
    return dict(schema_version=1, id=snapshot_id, generated_at=generated_at, origin=origin,
                sequence=previous.get('sequence', 0) + 1 if previous else 0,
                previous_id=previous['id'] if previous else None, scopes=clean, baseline=baseline,
                compared_with={scope: dict(id=base['id'], generated_at=base['generated_at']) if base else None
                               for scope, base in bases.items()},
                comparison={scope: compare_scope(view, (bases[scope] or {}).get('scopes', {}).get(scope))
                            for scope, view in clean.items()})


def rate_cell(counts):
    rate = usable_rate(counts)
    if rate is None:
        return f"unmeasured ({counts.get('eligible', 0)} eligible; {counts.get('declined', 0)} declined)"
    denominator = counts['eligible'] - counts.get('declined', 0)
    return f"{100 * rate:.2f}% ({counts['applied']}/{denominator}; {counts.get('declined', 0)} declined)"


def markdown_report(snapshot):
    rules = rubric()['traits']
    lines = ['# Private collaboration progress snapshot', '',
             f"Saved: {snapshot['generated_at']} · Snapshot: {snapshot['id']}", '',
             'One saved invocation, including runs with no new work. Historical snapshots are never overwritten.', '',
             '↑ and ↓ compare applied rates with the last earlier saved report whose counts differ, in the same cohort; → means unchanged.',
             'Runs that changed no counts carry the previous change forward instead of resetting it.',
             'Differences are percentage points (pp). Newly measured or unmeasured values have no directional arrow.',
             'Rate = applied / (eligible − declined), after at least three eligible opportunities. Declines do not lower the rate.',
             'Rates describe reviewed evidence, not proof of personal improvement. Unknown evidence is not a missed opportunity.', '',
             f"Previous snapshot: {snapshot['previous_id'] or 'none'}",
             f"Compared with: {((snapshot.get('compared_with') or {}).get('all') or {}).get('id') or snapshot['previous_id'] or 'none'} (all work)", '',
             'Private local files only. No uploads, external scoring, or overall score.', '']
    for scope in SCOPES:
        if scope not in snapshot['scopes']:
            continue
        view = snapshot['scopes'][scope]
        totals, change = view['cumulative'], snapshot['comparison'][scope]
        lines += [f'## {SCOPE_NAMES[scope]}', '',
                  f"**{totals['episodes']} task episodes in {totals['sessions']} chats.** "
                  f"{view['since_baseline']['episodes']} episodes since the imported baseline.", '',
                  '| Trait | Current applied rate | Change | Verified | Unknown |',
                  '|---|---|---|---:|---:|']
        for trait in rules:
            key = trait['id']; c = totals['traits'][key]; m = change['traits'][key]
            lines.append(f"| {key} {trait['name']} | {rate_cell(c)} | {m['label']} | {c['verified_outcome']} | {c['unobserved']} |")
        lines += ['', '### Indicators', '',
                  '| Indicator | Current applied rate | Change | Verified | Unknown |', '|---|---|---|---:|---:|']
        for key, c in totals['indicators'].items():
            lines.append(f"| {key} | {rate_cell(c)} | {change['indicators'][key]['label']} | {c['verified_outcome']} | {c['unobserved']} |")
        lines += ['', '### Recent and previous completed work', '',
                  f"Recent window: {view['recent_10']['episodes']} completed tasks. Previous window: {view['previous_10']['episodes']} completed tasks.", '',
                  '| Trait | Recent window | Previous window |', '|---|---|---|']
        for trait in rules:
            key = trait['id']
            lines.append(f"| {key} {trait['name']} | {rate_cell(view['recent_10']['traits'][key])} | {rate_cell(view['previous_10']['traits'][key])} |")
        lines += ['', '### Weekly task volume', '', f'| Week beginning ({timezone_label()}) | Episodes |', '|---|---:|']
        lines += [f'| {week} | {n} |' for week, n in sorted(totals['weekly'].items())]
        lines += ['']
    lines += ['The original baseline and audited review history remain unchanged. Snapshots do not review pending chats automatically.', '']
    return '\n'.join(lines)


@contextmanager
def snapshot_lock(reports):
    path = reports / '.snapshot.lock'
    deadline = time.monotonic() + 10
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(fd, str(os.getpid()).encode('ascii')); os.close(fd)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise ValueError('Another snapshot writer is active, or a stale snapshot lock needs review; no report overwritten')
            time.sleep(0.05)
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


def load_snapshots(history):
    result = []
    if history.exists():
        for path in history.glob('*.json'):
            if path.name == 'index.json':
                continue
            value = read_json(path)
            if value.get('schema_version') != 1 or not ID.fullmatch(value.get('id', '')) or path.stem != value['id']:
                raise ValueError('Invalid snapshot history entry; previous reports were retained')
            if not (history / (value['id'] + '.md')).exists():
                # Recover a missing derived companion after a partial filesystem write.
                atomic_text(history / (value['id'] + '.md'), markdown_report(value))
            result.append(value)
    return sorted(result, key=lambda x: (x.get('sequence', 0), x['generated_at'], x['id']))


def write_new_snapshot(history, snapshot, markdown=None):
    # The writer lock serializes selection; exclusive creation prevents replacement even on timestamp collisions.
    for extension, content in (('.json', json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n'),
                               ('.md', markdown if markdown is not None else markdown_report(snapshot))):
        with (history / (snapshot['id'] + extension)).open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(content); stream.flush(); os.fsync(stream.fileno())


def preserve_previous_report(root, locked=False):
    """Capture aliases before the documented commit/report phase can replace them."""
    reports = Path(root) / 'reports'; history = reports / 'history'
    pending = reports / '.previous-status.json'
    if not (reports / 'latest.json').exists() or pending.exists():
        return
    if history.exists() and any(p.name != 'index.json' for p in history.glob('*.json')):
        return
    if not locked:
        with snapshot_lock(reports):
            return preserve_previous_report(root, locked=True)
    prior = {}
    for scope in SCOPES:
        path = reports / (('latest' if scope == 'all' else scope) + '.json')
        if path.exists():
            prior[scope] = read_json(path)
    markdown = (reports / 'latest.md').read_text(encoding='utf-8') if (reports / 'latest.md').exists() else None
    atomic_json(pending, dict(views=prior, markdown=markdown))


def _id_for(generated_at, origin='run'):
    stamp = dt.datetime.fromisoformat(generated_at.replace('Z', '+00:00')).astimezone(dt.timezone.utc)
    return stamp.strftime('%Y-%m-%d_%H%M%S%fZ') + '_' + origin


DATA_FILE = 'dashboard-data.js'
DATA_PREFIX = ('// Generated by collab-progress. Private statistics: do not commit or share.\n'
               '// Loaded by dashboard.html as a classic script, so the page also works from file://.\n'
               'window.PROGRESS_DATA = ')


def load_dashboard_data(path):
    """Parse a generated dashboard-data.js back into the payload (used by tests and tools)."""
    text = Path(path).read_text(encoding='utf-8')
    if not text.startswith(DATA_PREFIX) or not text.rstrip().endswith(';'):
        raise ValueError('Not a collab-progress dashboard data file: ' + str(path))
    return json.loads(text[len(DATA_PREFIX):].rstrip().rstrip(';'))


def refresh_viewer(root, snapshots=None):
    reports = Path(root) / 'reports'; history = reports / 'history'
    snapshots = snapshots if snapshots is not None else load_snapshots(history)
    if not snapshots:
        raise ValueError('No saved snapshots; run snapshot first')
    current = snapshots[-1]
    entries = []
    for snap in reversed(snapshots):
        counts = snap['scopes'].get('all', next(iter(snap['scopes'].values())))['cumulative']
        changes = snap['comparison'].get('all', {}).get('traits', {})
        entries.append(dict(id=snap['id'], generated_at=snap['generated_at'], origin=snap['origin'],
                            episodes=counts['episodes'], sessions=counts['sessions'],
                            up=sum(m['direction'] == 'up' for m in changes.values()),
                            down=sum(m['direction'] == 'down' for m in changes.values()),
                            markdown=(history / (snap['id'] + '.md')).read_text(encoding='utf-8')))
    payload = dict(current=current, reports=entries, groups=GROUPS, rubric=rubric()['traits'], scope_names=SCOPE_NAMES, timezone=timezone_name())
    safe_json = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    # The page and its application script are static assets copied unchanged; only the data file is generated.
    assets = Path(__file__).resolve().parents[1] / 'assets'
    for name in ('dashboard.html', 'dashboard.js'):
        atomic_text(reports / name, (assets / name).read_text(encoding='utf-8'))
    atomic_text(reports / DATA_FILE, DATA_PREFIX + safe_json + ';\n')
    manifest = {key: value for key, value in payload.items() if key not in ('current', 'reports', 'rubric', 'groups')}
    manifest.update(schema_version=1, current_id=current['id'], reports=[{k: v for k, v in e.items() if k != 'markdown'} for e in entries])
    atomic_json(history / 'index.json', manifest)
    return str(reports / 'dashboard.html')


def create_snapshot(root, views):
    root = Path(root); reports = root / 'reports'; history = reports / 'history'
    history.mkdir(parents=True, exist_ok=True)
    with snapshot_lock(reports):
        snapshots = load_snapshots(history)
        preserve_previous_report(root, locked=True)
        if not snapshots and (reports / 'latest.json').exists():
            # Keep the actual prior saved report, explicitly labelled as an import, not a fabricated past invocation.
            preserved = read_json(reports / '.previous-status.json')
            prior = preserved['views']
            saved_at = prior['all']['generated_at']
            seed = snapshot_payload(prior, saved_at, _id_for(saved_at, 'imported'), origin='previous-saved-report')
            write_new_snapshot(history, seed, preserved['markdown']); snapshots.append(seed)
        generated_at = dt.datetime.now(dt.timezone.utc).isoformat()
        snapshot_id = _id_for(generated_at)
        suffix = 2
        while (history / (snapshot_id + '.json')).exists():
            snapshot_id = _id_for(generated_at) + '_' + str(suffix); suffix += 1
        snap = snapshot_payload(views, generated_at, snapshot_id, snapshots[-1] if snapshots else None, history=snapshots)
        write_new_snapshot(history, snap); snapshots.append(snap)
        # Existing aliases remain available. One new immutable report represents the complete invocation.
        for scope, view in views.items():
            alias = 'latest' if scope == 'all' else scope
            atomic_json(reports / (alias + '.json'), view)
            scoped = {**snap, 'scopes': {scope: snap['scopes'][scope]}, 'comparison': {scope: snap['comparison'][scope]}}
            atomic_text(reports / (alias + '.md'), markdown_report(scoped))
        page = refresh_viewer(root, snapshots)
        (reports / '.previous-status.json').unlink(missing_ok=True)
    return dict(snapshot=str(history / (snapshot_id + '.md')), snapshot_data=str(history / (snapshot_id + '.json')),
                dashboard=page, snapshot_id=snapshot_id, reports=len(snapshots),
                task_episodes=views['all']['cumulative']['episodes'], scoring_unchanged=True)
