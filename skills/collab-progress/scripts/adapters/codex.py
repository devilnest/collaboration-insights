"""Codex transcript adapter (read-only).

Source: CODEX_HOME (default ~/.codex). Reads the newest numbered state_*.sqlite and
thread_history_*.sqlite (respecting CODEX_SQLITE_HOME or config.toml sqlite_home),
plus sessions/ and archived_sessions/ JSONL as a fallback. Behaviour is identical
to the original codex-progress reader so existing source revisions stay valid.
"""
from contextlib import closing as closing_connection
import datetime as dt
import json
import os
from pathlib import Path
import re
import sqlite3

NAME = 'codex'
SESSION_ENV = ('CODEX_THREAD_ID', 'CODEX_SESSION_ID')


def default_home():
    return Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex').resolve()


def readonly_db(path):
    db = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True, timeout=15)
    db.row_factory = sqlite3.Row
    return db


class CodexHistory:
    harness = NAME

    def __init__(self, home):
        self.home = Path(home).resolve()
        cfg = {}
        if (self.home / 'config.toml').exists():
            import tomllib
            cfg = tomllib.loads((self.home / 'config.toml').read_text(encoding='utf-8-sig'))
        sqlhome = Path(os.environ.get('CODEX_SQLITE_HOME') or cfg.get('sqlite_home') or self.home)
        self.state = self._latest(sqlhome, 'state_*.sqlite')
        self.history = self._latest(sqlhome, 'thread_history_*.sqlite')

    @staticmethod
    def _latest(root, pattern):
        files = list(Path(root).glob(pattern))
        return max(files, key=lambda p: int(re.search(r'_(\d+)\.sqlite$', p.name).group(1))) if files else None

    def catalog(self):
        rows = {}
        if self.state:
            with closing_connection(readonly_db(self.state)) as db:
                cols = {r['name'] for r in db.execute('pragma table_info(threads)')}
                needed = ['id', 'rollout_path', 'source', 'created_at', 'updated_at']
                if not set(needed) <= cols:
                    raise ValueError('Unsupported Codex session index schema; no cursor advanced')
                for row in db.execute('select ' + ','.join(needed) + ' from threads'):
                    rows[row['id']] = dict(row)
        for folder in ('sessions', 'archived_sessions'):
            for path in (self.home / folder).rglob('*.jsonl'):
                try:
                    with path.open(encoding='utf-8') as stream:
                        meta = json.loads(next(stream)).get('payload', {})
                    sid = meta.get('id')
                    if sid and sid not in rows:
                        rows[sid] = dict(id=sid, rollout_path=str(path), source=meta.get('source'), created_at=meta.get('timestamp'), updated_at=None)
                except (OSError, ValueError, StopIteration):
                    continue
        for row in rows.values():
            row['harness'] = NAME
        return sorted(rows.values(), key=lambda r: str(r['created_at']))

    def raw(self, meta):
        """Return (origin, [(ordinal, ms, turn_id, item), ...]) in the shared item shape."""
        sid = meta['id']
        raw = []
        origin = 'sqlite'
        if self.history:
            with closing_connection(readonly_db(self.history)) as db:
                for row in db.execute('select rollout_ordinal,created_at_ms,turn_id,item_json from thread_items where thread_id=? order by rollout_ordinal', (sid,)):
                    raw.append((row['rollout_ordinal'], row['created_at_ms'], row['turn_id'], json.loads(row['item_json'])))
        if not raw:
            origin = 'jsonl'
            path = Path(meta.get('rollout_path') or '')
            if not path.is_file():
                raise ValueError('Indexed history unavailable; no cursor advanced')
            turn = None
            with path.open(encoding='utf-8') as stream:
                for ordinal, line in enumerate(stream):
                    try:
                        event = json.loads(line)
                    except ValueError:
                        raise ValueError('Incomplete transcript; retry after the writer finishes')
                    payload = event.get('payload', {})
                    if event.get('type') == 'turn_context' or (event.get('type') == 'event_msg' and payload.get('type') == 'task_started'):
                        turn = payload.get('turn_id', turn)
                    if event.get('type') != 'response_item':
                        continue
                    kind = payload.get('type')
                    if kind == 'message' and payload.get('role') in ('user', 'assistant'):
                        role = payload['role']
                        content = payload.get('content', [])
                        text = '\n'.join(c.get('text', '') for c in content)
                        if role == 'user' and re.match(r'^\s*<(?:environment_context|external_codex_apps_open_page|skills_instructions)\b', text):
                            continue
                        item = dict(type='userMessage', content=content) if role == 'user' else dict(type='agentMessage', text=text, phase=payload.get('phase'))
                    elif kind in ('function_call', 'custom_tool_call'):
                        item = dict(type='mcpToolCall', tool=payload.get('name', kind), arguments=payload.get('arguments', payload.get('input', '')), result=None)
                    elif kind in ('function_call_output', 'custom_tool_call_output'):
                        item = dict(type='mcpToolCall', tool='recorded_tool_result', arguments={}, result=payload.get('output'))
                    else:
                        continue
                    stamp = event.get('timestamp')
                    ms = int(dt.datetime.fromisoformat(stamp.replace('Z', '+00:00')).timestamp()*1000) if stamp else 0
                    raw.append((ordinal, ms, turn, item))
        return origin, raw


READER = CodexHistory
