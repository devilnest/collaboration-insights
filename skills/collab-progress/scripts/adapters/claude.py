"""Claude Code transcript adapter (read-only).

Source: CLAUDE_CONFIG_DIR (default ~/.claude), sessions at
projects/<project>/<session-id>.jsonl. The event ordinal is the 1-based line number.
Subagent transcripts (projects/<project>/<session>/subagents/*.jsonl) are not
globbed; a transcript with isSidechain records is treated as automated work.
"""
import datetime as dt
import json
import os
from pathlib import Path
import re

NAME = 'claude'
SESSION_ENV = ('CLAUDE_CODE_SESSION_ID',)
SYSTEM_BLOCK = re.compile(r'<(system-reminder|local-command-stdout|local-command-stderr|local-command-caveat)>.*?</\1>', re.S)


def default_home():
    return Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude').resolve()


def human_text(content):
    """Visible text a person typed, without harness-injected reminders."""
    if isinstance(content, str):
        parts = [content]
    else:
        parts = [c.get('text', '') for c in content or [] if isinstance(c, dict) and c.get('type') == 'text']
    text = SYSTEM_BLOCK.sub('', '\n'.join(parts))
    command = re.search(r'<command-name>(.*?)</command-name>', text, re.S)
    if command:
        args = re.search(r'<command-args>(.*?)</command-args>', text, re.S)
        text = (command.group(1).strip() + ' ' + (args.group(1).strip() if args else '')).strip()
    text = re.sub(r'</?(?:command-message|pasted_content)[^>]*>', '', text)
    return text.strip()


def stamp_ms(record):
    stamp = record.get('timestamp')
    try:
        return int(dt.datetime.fromisoformat(stamp.replace('Z', '+00:00')).timestamp() * 1000) if stamp else 0
    except ValueError:
        return 0


def records(path):
    lines = Path(path).read_text(encoding='utf-8').splitlines()
    for ordinal, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            yield ordinal, json.loads(line)
        except ValueError:
            if ordinal == len(lines):
                return  # the live writer has not finished the last line
            raise ValueError('Incomplete transcript; retry after the writer finishes')


class ClaudeHistory:
    harness = NAME

    def __init__(self, home):
        self.home = Path(home).resolve()
        self.projects = self.home / 'projects'

    def catalog(self):
        rows = {}
        files = [p for p in self.projects.glob('*/*.jsonl') if p.is_file()] if self.projects.is_dir() else []
        for path in files:
            created = None; sidechain = False; human = False
            try:
                for _, record in records(path):
                    if record.get('type') not in ('user', 'assistant'):
                        continue
                    created = created or record.get('timestamp')
                    sidechain = sidechain or bool(record.get('isSidechain'))
                    if (record.get('type') == 'user' and not record.get('isMeta')
                            and record.get('turnOrigin', 'human') == 'human'
                            and human_text((record.get('message') or {}).get('content'))):
                        human = True
            except (OSError, ValueError):
                continue
            source = 'subagent' if sidechain else ('human' if human else 'automated')
            rows[path.stem] = dict(id=path.stem, rollout_path=str(path), source=source, created_at=created, updated_at=None, project=path.parent.name, harness=NAME)
        return sorted(rows.values(), key=lambda r: str(r['created_at']))

    def raw(self, meta):
        if meta['source'] == 'subagent':
            raise ValueError('Automated/subagent histories cannot be reviewed')
        path = Path(meta['rollout_path'])
        if not path.is_file():
            raise ValueError('Indexed history unavailable; no cursor advanced')
        raw = []; turn = None; tools = {}
        for ordinal, record in records(path):
            kind = record.get('type'); ms = stamp_ms(record)
            if kind == 'system' and record.get('subtype') == 'compact_boundary':
                raw.append((ordinal, ms, turn, dict(type='contextCompaction', arguments={'note': 'context compacted'})))
                continue
            if kind not in ('user', 'assistant') or record.get('isMeta') or record.get('isCompactSummary'):
                continue
            content = (record.get('message') or {}).get('content')
            if kind == 'assistant':
                blocks = content if isinstance(content, list) else [dict(type='text', text=str(content or ''))]
                for block in blocks:
                    if block.get('type') == 'text' and block.get('text', '').strip():
                        raw.append((ordinal, ms, turn, dict(type='agentMessage', text=block['text'], id=record.get('uuid'))))
                    elif block.get('type') == 'tool_use':
                        tools[block.get('id')] = block.get('name')
                        raw.append((ordinal, ms, turn, dict(type='mcpToolCall', tool=block.get('name'), arguments=block.get('input', {}), result=None, id=block.get('id'))))
                continue
            results = [b for b in content if isinstance(b, dict) and b.get('type') == 'tool_result'] if isinstance(content, list) else []
            if results:
                answer = record.get('toolUseResult')
                for block in results:
                    name = tools.get(block.get('tool_use_id'))
                    if name == 'AskUserQuestion' and isinstance(answer, dict) and isinstance(answer.get('answers'), dict):
                        reply = [dict(answer=v) for v in answer['answers'].values()]
                        item = dict(type='userMessage', id=block.get('tool_use_id'), content=[dict(type='text', text='<send_user_message_question_reply>' + json.dumps(reply, ensure_ascii=False) + '</send_user_message_question_reply>')])
                    else:
                        out = block.get('content')
                        if isinstance(out, list):
                            out = '\n'.join(c.get('text', '') for c in out if isinstance(c, dict) and c.get('type') == 'text')
                        item = dict(type='mcpToolCall', tool='recorded_tool_result:' + str(name or 'unknown'), arguments={}, result=out, status='error' if block.get('is_error') else 'ok', id=block.get('tool_use_id'))
                    raw.append((ordinal, ms, turn, item))
                continue
            text = human_text(content)
            if not text:
                continue
            if record.get('turnOrigin', 'human') != 'human':
                raw.append((ordinal, ms, turn, dict(type='mcpToolCall', tool='harness-event:' + str(record.get('turnOrigin')), arguments={}, result=text, id=record.get('uuid'))))
                continue
            turn = record.get('promptId') or record.get('uuid') or turn
            raw.append((ordinal, ms, turn, dict(type='userMessage', content=[dict(type='text', text=text)], id=record.get('uuid'))))
        return 'claude-jsonl', raw


READER = ClaudeHistory
