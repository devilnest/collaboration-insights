"""pi coding agent transcript adapter (read-only).

Source: PI_CODING_AGENT_DIR (default ~/.pi/agent), sessions at
sessions/--<cwd-slug>--/<timestamp>_<session-id>.jsonl, an append-only JSONL tree
(format version 3: header line `{"type":"session","id":...}` then entries with
id/parentId/timestamp). The event ordinal is the 1-based line number, which stays
stable because files are append-only. Abandoned branches stay in the file and are
read too: what the user typed on them is still their behaviour.

Verified against pi's docs/session-format.md; the assistant block shapes
(`toolCall` with `name`/`arguments`, `thinking`) and PI_CODING_AGENT_DIR follow pi's
public types and should be confirmed on a real install (`progress.py probe`).
pi exposes no current-session environment variable: pass `--session ID`.
"""
import datetime as dt
import json
import os
from pathlib import Path

NAME = 'pi'
SESSION_ENV = ()   # pi does not export its session id to tools


def default_home():
    return Path(os.environ.get('PI_CODING_AGENT_DIR') or Path.home() / '.pi' / 'agent').resolve()


def _iso_ms(value):
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(dt.datetime.fromisoformat(str(value).replace('Z', '+00:00')).timestamp() * 1000)
    except ValueError:
        return 0


def _records(path):
    lines = Path(path).read_text(encoding='utf-8').splitlines()
    for ordinal, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            yield ordinal, json.loads(line)
        except ValueError:
            if ordinal == len(lines):
                return  # unfinished last line from the live writer
            raise ValueError('Incomplete pi transcript; retry after the writer finishes')


def _text(content):
    if isinstance(content, str):
        return content
    return '\n'.join(b.get('text', '') for b in content or [] if isinstance(b, dict) and b.get('type') == 'text')


class PiHistory:
    harness = NAME

    def __init__(self, home):
        self.home = Path(home).resolve()
        self.sessions = self.home / 'sessions'

    def catalog(self):
        rows = {}
        files = sorted(self.sessions.glob('*/*.jsonl')) if self.sessions.is_dir() else []
        for path in files:
            try:
                header = next((r for _, r in _records(path)), None)
            except (OSError, ValueError):
                continue
            if not isinstance(header, dict) or header.get('type') != 'session' or not header.get('id'):
                continue
            sid = str(header['id'])
            rows[sid] = dict(id=sid, rollout_path=str(path), source='human', created_at=header.get('timestamp'),
                             updated_at=None, project=path.parent.name, parent_session=header.get('parentSession'), harness=NAME)
        return sorted(rows.values(), key=lambda r: str(r['created_at']))

    def raw(self, meta):
        path = Path(meta['rollout_path'])
        if not path.is_file():
            raise ValueError('Indexed history unavailable; no cursor advanced')
        raw = []; turn = None
        for ordinal, entry in _records(path):
            kind = entry.get('type'); ms = _iso_ms(entry.get('timestamp'))
            if kind == 'compaction':
                raw.append((ordinal, ms, turn, dict(type='contextCompaction', arguments={'note': 'context compacted'}, id=entry.get('id'))))
                continue
            if kind == 'branch_summary':
                raw.append((ordinal, ms, turn, dict(type='mcpToolCall', tool='pi:branch_summary', arguments={}, result=entry.get('summary', ''), id=entry.get('id'))))
                continue
            if kind != 'message':
                continue  # header, model/thinking changes, usage, labels, custom state
            message = entry.get('message') or {}
            role = message.get('role'); content = message.get('content')
            if role == 'user':
                text = _text(content).strip()
                if text:
                    turn = entry.get('id') or turn
                    raw.append((ordinal, ms, turn, dict(type='userMessage', content=[dict(type='text', text=text)], id=entry.get('id'))))
            elif role == 'assistant':
                for block in content if isinstance(content, list) else [dict(type='text', text=str(content or ''))]:
                    if not isinstance(block, dict):
                        continue
                    if block.get('type') == 'text' and block.get('text', '').strip():
                        raw.append((ordinal, ms, turn, dict(type='agentMessage', text=block['text'], id=entry.get('id'))))
                    elif block.get('type') == 'toolCall':
                        raw.append((ordinal, ms, turn, dict(type='mcpToolCall', tool=block.get('name'), arguments=block.get('arguments', {}), result=None, id=block.get('id'))))
            elif role == 'toolResult':
                raw.append((ordinal, ms, turn, dict(type='mcpToolCall', tool='recorded_tool_result:' + str(message.get('toolName') or 'unknown'),
                                                    arguments={}, result=_text(content), status='error' if message.get('isError') else 'ok', id=message.get('toolCallId'))))
            elif role in ('custom', 'system'):
                text = _text(content) if role == 'custom' else ''
                if text.strip():
                    raw.append((ordinal, ms, turn, dict(type='mcpToolCall', tool='harness-event:pi-' + role, arguments={}, result=text, id=entry.get('id'))))
        return 'pi-jsonl', raw


READER = PiHistory
