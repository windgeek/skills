#!/usr/bin/env python3
"""Claude Code PostToolUse 钩子：文件写进某个 skill 目录后，提醒 agent 做一遍精炼。
同一会话里，每个 skill 只提醒一次。读 stdin 的 JSON，不改任何文件（只在临时目录记一个“已提醒”标记）。
"""
import json, os, sys, tempfile, hashlib
from pathlib import Path


def skill_root(path: Path):
    """向上找含 SKILL.md 的目录（最多 4 层）。"""
    for p in [path] + list(path.parents)[:4]:
        if (p / 'SKILL.md').exists():
            return p
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    fp = (data.get('tool_input') or {}).get('file_path') or ''
    if not fp or not fp.endswith(('.md', '.py', '.js', '.mjs', '.sh', '.json')):
        return
    root = skill_root(Path(fp).expanduser().resolve().parent)
    if not root:
        return
    sid = data.get('session_id', 'nosession')
    mark = Path(tempfile.gettempdir()) / f'skill-refine-{hashlib.md5((sid + str(root)).encode()).hexdigest()[:12]}'
    if mark.exists():
        return
    mark.touch()
    lint = Path(__file__).resolve().parent / 'lint_skill.py'
    msg = (f'你刚改了 skill「{root.name}」。改完这一轮后，按 skill-refine 做一遍精炼：通读全部内容、'
           f'把新规则归到对的主题下、合并重复、消除冲突，然后跑 `python3 {lint} {root}`（有相关 skill 用 --related 带上），'
           f'最后向用户报告合并了什么、统一了什么。')
    print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PostToolUse', 'additionalContext': msg}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
