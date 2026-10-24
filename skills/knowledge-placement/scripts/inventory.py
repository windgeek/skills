#!/usr/bin/env python3
"""盘点：每个 Claude 记忆目录对应哪个项目、项目里有哪些说明文件、记忆有几条。
用法：python3 inventory.py [--all]   （默认跳过没有记忆条目的目录）"""
import glob, os, re, sys

HOME = os.path.expanduser('~')
BASE = os.path.join(HOME, '.claude/projects')
DOCS = ('AGENTS.md', 'CLAUDE.md', 'GEMINI.md', 'CLAUDE.local.md')


def decode(key):
    """把 -Users-x-a-b 还原成真实路径：'/'、'.'、'~'、空格都被编码成 '-'，逐段试探。"""
    parts = key.strip('-').split('-')
    path, i = '/', 0
    while i < len(parts):
        for j in range(len(parts), i, -1):
            seg = '-'.join(parts[i:j])
            for cand in {seg, seg.replace('-', '.'), seg.replace('-', ' '), seg.replace('-', '~')}:
                p = os.path.join(path, cand)
                if os.path.exists(p):
                    path, i = p, j
                    break
            else:
                continue
            break
        else:
            return None  # 目录已不存在
    return path


def describe(f):
    t = open(f, encoding='utf-8', errors='replace').read()
    m = re.search(r'^description:\s*(.*)$', t, re.M)
    ty = re.search(r'^\s*type:\s*(\S+)', t, re.M)
    return (ty.group(1) if ty else '?'), (m.group(1).strip('"') if m else '')[:90], len(t)


def main():
    show_all = '--all' in sys.argv
    for d in sorted(glob.glob(BASE + '/*/memory')):
        fs = [f for f in sorted(glob.glob(d + '/*.md')) if not f.endswith('MEMORY.md')]
        if not fs and not show_all:
            continue
        key = d.split('/')[-2]
        proj = decode(key)
        print(f'\n## {proj or "（目录已不存在） " + key}')
        if proj:
            docs = []
            for name in DOCS:
                p = os.path.join(proj, name)
                if os.path.lexists(p):
                    link = os.readlink(p) if os.path.islink(p) else ''
                    docs.append(f'{name}' + (f'→{link}' if link else f'({os.path.getsize(p)}B)'))
            print('   说明文件：' + (', '.join(docs) or '无'))
        for f in fs:
            ty, desc, n = describe(f)
            print(f'   {os.path.basename(f)[:-3]:40} {ty:9} {n:>6}B  {desc}')


if __name__ == '__main__':
    main()
