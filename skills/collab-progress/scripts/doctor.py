"""Environment diagnosis for any harness: what works, what is missing, and who must act.

`doctor` tells the running agent (and its human) what this machine needs so the skill
works in their harness. `probe` describes the *structure* of an unknown transcript
store (file kinds, JSON keys, record types, SQLite tables) without printing any message
text, so an agent can write an adapter for a new harness. Read-only; no network.
"""
import collections
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess

from progress_core import (CONFIG_PATH, DEFAULT_DATA, SKILL_DIR, ADAPTER_LOAD_ERRORS, adapters, custom_adapter_dir,
                           harness_of, locate_data)

SKILL_NAMES = ('collab-progress', 'collab-coach')

# What each environment looks like from inside. `wrapper` harnesses run other agents,
# whose own adapters read the transcripts; `agent` harnesses need an adapter of their own.
KNOWN_HARNESSES = {
    'claude': dict(kind='agent', env=('CLAUDECODE', 'CLAUDE_CODE_SESSION_ID'), reference='harness-claude.md'),
    'codex': dict(kind='agent', env=('CODEX_THREAD_ID', 'CODEX_SESSION_ID'), reference='harness-codex.md'),
    'pi': dict(kind='agent', env=(), reference='harness-pi.md'),
    'herdr': dict(kind='wrapper', env=('HERDR_ENV',), reference='harness-herdr.md'),
    't3code': dict(kind='wrapper', env_prefix='T3CODE_', reference='harness-t3code.md'),
}
# Transcript stores of agents without a built-in adapter: their presence suggests onboarding.
UNSUPPORTED_STORES = {
    'opencode': ['~/.local/share/opencode'],
    'cursor-agent': ['~/.cursor'],
    'gemini-cli': ['~/.gemini'],
}


def _skill_dirs(cwd):
    home = Path.home(); dirs = [home / '.agents' / 'skills', home / '.claude' / 'skills', home / '.codex' / 'skills',
                                home / '.pi' / 'agent' / 'skills', cwd / '.agents' / 'skills', cwd / '.claude' / 'skills', cwd / '.pi' / 'skills']
    if os.environ.get('CLAUDE_CONFIG_DIR'):
        dirs.append(Path(os.environ['CLAUDE_CONFIG_DIR']) / 'skills')
    if os.environ.get('PI_CODING_AGENT_DIR'):
        dirs.append(Path(os.environ['PI_CODING_AGENT_DIR']) / 'skills')
    seen = []; [seen.append(d) for d in dirs if d not in seen]
    return seen


def _node():
    exe = shutil.which('node')
    if not exe:
        return dict(found=False)
    try:
        version = subprocess.run([exe, '--version'], capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        version = ''
    return dict(found=bool(version), version=version)


def detect_environment(env=None):
    env = os.environ if env is None else env
    found = []
    for name, info in KNOWN_HARNESSES.items():
        hits = [k for k in info.get('env', ()) if env.get(k)]
        if info.get('env_prefix'):
            hits += [k for k in env if k.startswith(info['env_prefix'])]
        if hits:
            found.append(dict(harness=name, kind=info['kind'], evidence=sorted(set(hits)), reference=info['reference']))
    return found


def doctor(history, python, resolve_session, cwd=None):
    cwd = Path(cwd or os.getcwd())
    registry = adapters(); steps = []
    data, chosen_by = locate_data()
    running = detect_environment()
    if not running:
        steps.append(dict(who='agent', what='Could not tell which harness this is from the environment. Ask the human which tool '
                          'they are using, then read references/harness-<name>.md, or references/harness-onboarding.md if none exists.'))
    for item in running:
        if item['kind'] == 'wrapper':
            steps.append(dict(who='agent', what=f"Running inside {item['harness']}, which hosts other agents. Identify the agent in this "
                              f"pane/thread (Claude Code, Codex, pi, ...) and follow references/{item['reference']}."))
    if not python['ok']:
        steps.append(dict(who='human', what='Install Python 3.11+ (the agent proposes the command and waits for a yes).'))
    node = _node()
    if not data:
        steps.append(dict(who='agent+human', what=f'Ask where to keep private data (default {DEFAULT_DATA}), then run setup.'))

    homes = []
    for key, path in history.homes.items():
        reader = history.readers.get(key); count = None; error = None
        if reader:
            try:
                count = len(reader.catalog())
            except (ValueError, OSError, sqlite3.Error) as exc:
                error = str(exc)
        homes.append(dict(home=key, harness=harness_of(key), path=str(path), found=path.is_dir(), chats=count, error=error))
        if error:
            steps.append(dict(who='agent', what=f'Home {key} could not be read ({error}); run `probe {path}` and check the adapter.'))
    for name in history.unknown_homes:
        steps.append(dict(who='agent', what=f'Home {name} has no adapter; follow references/harness-onboarding.md.'))
    for item in ADAPTER_LOAD_ERRORS:
        steps.append(dict(who='agent', what=f"Custom adapter failed to load: {item['adapter']}: {item['error']}"))

    try:
        current = dict(id=resolve_session('current'), ok=True)
    except ValueError:
        current = dict(id=None, ok=False)
        steps.append(dict(who='agent', what='No current-session variable here (normal for pi, herdr panes and some wrappers). '
                          'Use `scan`, show the human the candidate chats for this project, and pass --session ID they confirm. '
                          'Never pick the newest chat by time alone.'))

    unsupported = []
    for name, paths in UNSUPPORTED_STORES.items():
        if name in registry:
            continue
        for raw in paths:
            path = Path(raw).expanduser()
            if path.exists():
                unsupported.append(dict(harness=name, path=str(path)))
                steps.append(dict(who='agent+human', what=f'{name} history found at {path} but no adapter is installed. Ask the human '
                                  'whether to include it; if yes, follow references/harness-onboarding.md.'))

    skill_dirs = []
    for folder in _skill_dirs(cwd):
        present = {n: (folder / n / 'SKILL.md').is_file() for n in SKILL_NAMES}
        if folder.exists() or any(present.values()):
            skill_dirs.append(dict(path=str(folder), **present))
    if not any(d['collab-progress'] for d in skill_dirs):
        steps.append(dict(who='human', what='collab-progress is not in any known skills folder; rerun the installer or copy it.'))

    return dict(running_in=running, python=python, node=node,
                data=dict(configured=data is not None, data_dir=str(data) if data else None, chosen_by=chosen_by, config=str(CONFIG_PATH)),
                adapters=[dict(harness=k, custom=getattr(m, 'CUSTOM_PATH', None), session_env=list(m.SESSION_ENV)) for k, m in registry.items()],
                custom_adapter_dir=str(custom_adapter_dir()) if custom_adapter_dir() else None,
                homes=homes, current_session=current, unsupported_history=unsupported, skill_dirs=skill_dirs,
                next_steps=steps or [dict(who='nobody', what='Everything needed is in place.')])


def _shape(value, depth=0):
    """Type skeleton of a JSON value: keys and types, never string contents."""
    if isinstance(value, dict):
        if depth > 3:
            return 'object'
        return {k: _shape(v, depth + 1) for k, v in sorted(value.items())[:40]}
    if isinstance(value, list):
        kinds = sorted({json.dumps(_shape(v, depth + 1), sort_keys=True) for v in value[:20]})
        return [json.loads(k) for k in kinds[:5]]
    return type(value).__name__


def probe(target, max_files=20, max_lines=4000):
    """Structural description of a transcript store. Prints no message text."""
    target = Path(target).expanduser()
    if not target.exists():
        raise ValueError('Not found: ' + str(target))
    files = [target] if target.is_file() else [p for p in target.rglob('*') if p.is_file()]
    by_ext = collections.Counter(p.suffix.lower() or '(none)' for p in files)
    result = dict(path=str(target.resolve()), files=len(files), by_extension=dict(by_ext.most_common(15)), jsonl=[], json=[], sqlite=[])
    newest = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
    for path in [p for p in newest if p.suffix.lower() == '.jsonl'][:max_files]:
        types = collections.Counter(); keysets = {}; roles = collections.Counter(); blocks = collections.Counter(); lines = 0; bad = 0
        with path.open(encoding='utf-8', errors='replace') as stream:
            for line in stream:
                lines += 1
                if lines > max_lines:
                    break
                try:
                    row = json.loads(line)
                except ValueError:
                    bad += 1; continue
                if not isinstance(row, dict):
                    continue
                kind = str(row.get('type', row.get('kind', '(no type)')))
                types[kind] += 1
                keysets.setdefault(kind, _shape(row))
                message = row.get('message') if isinstance(row.get('message'), dict) else row.get('payload') if isinstance(row.get('payload'), dict) else row
                if isinstance(message, dict):
                    if 'role' in message:
                        roles[str(message['role'])] += 1
                    content = message.get('content')
                    if isinstance(content, list):
                        blocks.update(str(b.get('type')) for b in content if isinstance(b, dict))
        result['jsonl'].append(dict(file=str(path.relative_to(target)) if target.is_dir() else path.name, lines=lines,
                                    unparsed=bad, record_types=dict(types.most_common()), roles=dict(roles), content_blocks=dict(blocks),
                                    shapes=keysets))
        if len(result['jsonl']) >= 3:
            break  # three newest transcripts are enough to see the format
    for path in [p for p in newest if p.suffix.lower() == '.json'][:3]:
        try:
            result['json'].append(dict(file=path.name, shape=_shape(json.loads(path.read_text(encoding='utf-8', errors='replace')))))
        except ValueError:
            result['json'].append(dict(file=path.name, shape='unparsed'))
    for path in [p for p in files if p.suffix.lower() in ('.sqlite', '.db', '.sqlite3')][:5]:
        try:
            db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)
            tables = {t: [c[1] for c in db.execute(f'pragma table_info("{t}")')]
                      for (t,) in db.execute("select name from sqlite_master where type='table'")}
            counts = {t: db.execute(f'select count(*) from "{t}"').fetchone()[0] for t in list(tables)[:30]}
            db.close()
            result['sqlite'].append(dict(file=path.name, tables={t: dict(columns=c, rows=counts.get(t)) for t, c in tables.items()}))
        except sqlite3.Error as error:
            result['sqlite'].append(dict(file=path.name, error=str(error)))
    result['note'] = 'Structure only: keys, types, counts. No message text was read into this output.'
    return result
