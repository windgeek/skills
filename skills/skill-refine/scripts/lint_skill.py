#!/usr/bin/env python3
"""Skill 体检：改完一个 skill 后跑一遍，列出需要人（或 agent）判断的地方。
只读，不改任何文件。

用法:
  python3 lint_skill.py <skill目录> [--related <另一个skill目录> ...] [--max-lines 500]

检查:
  1. 结构：frontmatter（name / description）、SKILL.md 篇幅、断链、没被引用的 references 文件
  2. 重复：不同位置几乎一样的句子或条目（跨文件、跨相关 skill）
  3. 冲突线索：同一个话题出现了不同的数字（如“10–20 段”和“20–40 段”），“必须 / 不要”说法相反的条目
  4. 堆积：一个列表平铺太多条、日期 / 期号戳太密（说明是按时间追加，没按主题归类）
"""
import argparse, re, sys
from pathlib import Path
from itertools import combinations

TEXT_EXT = {'.md', '.txt'}
STOP = set('的了是在和与及或也就都而要把被让给对从到这那一个一些我们你他她它'
           'the a an of to and or in on for is are be with as by it this that'.split())


def read_md(root: Path):
    files = {}
    for p in sorted(root.rglob('*')):
        if p.is_file() and p.suffix in TEXT_EXT and '.git' not in p.parts:
            files[p] = p.read_text(encoding='utf-8', errors='ignore')
    return files


def units(text):
    """把文档切成“条目”：列表项、表格行、段落。返回 (行号, 文本)。"""
    out, buf, start = [], [], 0
    in_code = False
    lines = text.split('\n')
    skip = 0
    if lines and lines[0].strip() == '---':   # frontmatter 不算正文
        for j in range(1, len(lines)):
            if lines[j].strip() == '---':
                skip = j + 1
                break
    for i, line in enumerate(lines, 1):
        if i <= skip:
            continue
        s = line.strip()
        if s.startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        is_item = bool(re.match(r'^([-*+]|\d+[.)、]|\|)', s))
        if not s or is_item or s.startswith('#'):
            if buf:
                out.append((start, ' '.join(buf)))
                buf = []
            if is_item:
                out.append((i, s))
            continue
        if not buf:
            start = i
        buf.append(s)
    if buf:
        out.append((start, ' '.join(buf)))
    return [(n, t) for n, t in out if len(re.sub(r'\W', '', t)) >= 18]


def grams(t, n=4):
    t = re.sub(r'`[^`]*`', '', t)   # 命令、路径不算内容
    t = re.sub(r'\[([^\]]*)\]\([^)]*\)', '', t)   # 链接（文字和目标）不算内容
    t = re.sub(r'[`*_>|#\-\s，。、；：“”‘’（）()\[\]!?！？.,;:"\']', '', t.lower())
    return {t[i:i + n] for i in range(len(t) - n + 1)}


def jacc(a, b):
    return len(a & b) / max(1, min(len(a), len(b)))


def rel(p, roots):
    for r in roots:
        try:
            return f'{r.name}/{p.relative_to(r)}'
        except ValueError:
            pass
    return str(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('skill')
    ap.add_argument('--related', nargs='*', default=[])
    ap.add_argument('--max-lines', type=int, default=500)
    ap.add_argument('--dup', type=float, default=0.6, help='重复判定阈值（0–1，越低报得越多）')
    a = ap.parse_args()

    root = Path(a.skill).expanduser().resolve()
    roots = [root] + [Path(r).expanduser().resolve() for r in a.related]
    skill_md = root / 'SKILL.md'
    if not skill_md.exists():
        sys.exit(f'找不到 {skill_md}')
    report = []
    say = lambda kind, msg: report.append((kind, msg))

    # ---------- 1. 结构 ----------
    md = skill_md.read_text(encoding='utf-8')
    fm = re.match(r'^---\n(.*?)\n---\n', md, re.S)
    if not fm:
        say('结构', 'SKILL.md 缺少 frontmatter（--- name / description ---）')
    else:
        head = fm.group(1)
        if not re.search(r'^name:\s*\S', head, re.M):
            say('结构', 'frontmatter 缺 name')
        d = re.search(r'^description:\s*(.+)$', head, re.M)
        if not d:
            say('结构', 'frontmatter 缺 description')
        elif len(d.group(1)) > 1024:
            say('结构', f'description {len(d.group(1))} 字符，偏长（多数平台上限 1024）')
    n_lines = md.count('\n') + 1
    if n_lines > a.max_lines:
        say('结构', f'SKILL.md {n_lines} 行，超过 {a.max_lines}：把案例和细则挪进 references/，SKILL.md 只留流程、硬规则和指针')
    kb = len(md.encode()) / 1024
    if kb > 20:
        say('结构', f'SKILL.md {kb:.0f} KB，每次触发都会整份读进上下文，考虑分层')

    files = read_md(root)
    linked = set()
    for p, t in files.items():
        for m in re.finditer(r'\]\(([^)#\s]+)(?:#[^)]*)?\)', t):
            tgt = m.group(1)
            if re.match(r'^[a-z]+://', tgt):
                continue
            q = (p.parent / tgt).resolve()
            linked.add(q)
            if not q.exists():
                say('结构', f'{rel(p, roots)} 链接到不存在的 {tgt}')
        for m in re.finditer(r'`((?:references|scripts|assets)/[^`\s]+)`', t):
            linked.add((root / m.group(1)).resolve())
    for p in sorted((root / 'references').rglob('*')) if (root / 'references').exists() else []:
        if p.is_file() and p.resolve() not in linked and p.name not in md:
            say('结构', f'{rel(p, roots)} 没有被任何文件提到，agent 不会去读它')

    # ---------- 2. 重复 ----------
    allu = []
    for r in roots:
        for p, t in read_md(r).items():
            for n, u in units(t):
                allu.append((p, n, u, grams(u)))
    seen = set()
    for (p1, n1, u1, g1), (p2, n2, u2, g2) in combinations(allu, 2):
        if p1 == p2 and abs(n1 - n2) < 2:
            continue
        if min(len(g1), len(g2)) < 16:
            continue
        s = jacc(g1, g2)
        if s >= a.dup:
            key = (p1, n1, p2, n2)
            if key in seen:
                continue
            seen.add(key)
            say('重复', f'{s:.0%}  {rel(p1, roots)}:{n1}  ⇄  {rel(p2, roots)}:{n2}\n'
                       f'        「{u1[:60]}」\n        「{u2[:60]}」')

    # ---------- 3. 冲突线索 ----------
    num = re.compile(r'(\d+(?:\.\d+)?(?:\s*[–\-~～到至]\s*\d+(?:\.\d+)?)?)\s*'
                     r'(段|分钟|秒|字|处|个|条|行|次|期|KB|MB|words?|lines?|seconds?|minutes?)')
    nums = []
    for p, n, u, _ in allu:
        for m in num.finditer(u):
            ctx = u[max(0, m.start() - 16):m.start()] + u[m.end():m.end() + 10]
            nums.append((m.group(1).replace(' ', ''), m.group(2), grams(ctx, 2), f'{rel(p, roots)}:{n}', ctx.strip()))
    reported = set()
    for (v1, u1_, c1, w1, t1), (v2, u2_, c2, w2, t2) in combinations(nums, 2):
        if u1_ != u2_ or v1 == v2 or w1 == w2 or min(len(c1), len(c2)) < 4:
            continue
        if jacc(c1, c2) >= 0.4 and (w1, w2) not in reported:
            reported.add((w1, w2))
            say('冲突?', f'同一话题、不同数值：{v1}{u1_}（{w1}「{t1[:24]}」） ⇄ {v2}{u2_}（{w2}「{t2[:24]}」）')

    pos = re.compile(r'必须|一定要|务必|always|must\b')
    neg = re.compile(r'不要|禁止|不能|别|一律不|never|must not|don\'t')
    rules = [(p, n, u, g) for p, n, u, g in allu if pos.search(u) or neg.search(u)]
    for (p1, n1, u1, g1), (p2, n2, u2, g2) in combinations(rules, 2):
        if (p1, n1) == (p2, n2):
            continue
        opp = (pos.search(u1) and neg.search(u2) and not neg.search(u1)) or \
              (neg.search(u1) and pos.search(u2) and not neg.search(u2))
        if opp and 0.35 <= jacc(g1, g2) < a.dup:
            say('冲突?', f'说法相反、话题相近：{rel(p1, roots)}:{n1}  ⇄  {rel(p2, roots)}:{n2}\n'
                        f'        「{u1[:60]}」\n        「{u2[:60]}」')

    # ---------- 4. 堆积 ----------
    for p, t in files.items():
        lines = t.split('\n')
        run, run_start = 0, 0
        for i, line in enumerate(lines + [''], 1):
            if re.match(r'^([-*+]|\d+[.)])\s', line):
                if run == 0:
                    run_start = i
                run += 1
            elif run and (line.strip() == '' or line.startswith((' ', '\t'))):
                continue   # 空行、子项、续行不打断列表
            else:
                if run > 12:
                    say('堆积', f'{rel(p, roots)}:{run_start} 一个列表平铺了 {run} 条：按主题分组，合并说同一件事的条目')
                run = 0
        stamps = re.findall(r'(?:20\d\d[-/.]\d{1,2}[-/.]\d{1,2}|\b\d{1,2}-\d{2}\b|EP\d+|v\d+\.\d+)', t)
        words = len(re.findall(r'[一-鿿]|\w+', t))
        heads = len(re.findall(r'^#{1,4} ', t, re.M))
        if words > 800 and len(stamps) / words * 1000 > 6 and heads / words * 1000 < 1.5:
            say('堆积', f'{rel(p, roots)} 日期 / 版本戳 {len(stamps)} 处：规则可能是按时间往后追加的，检查是否该按主题重排（戳可以留作出处）')

    # ---------- 输出 ----------
    if not report:
        print(f'✅ {root.name}：没有发现结构、重复、冲突或堆积问题。')
        return
    order = ['结构', '冲突?', '重复', '堆积']
    print(f'# {root.name} 体检：{len(report)} 条\n')
    for k in order:
        items = [m for kind, m in report if kind == k]
        if items:
            print(f'## {k}（{len(items)}）')
            for m in items:
                print(f'- {m}')
            print()
    print('这些只是线索，需要通读上下文再判断：重复的合并到一处，冲突的按用户最新的意思统一，堆积的按主题重排。')


if __name__ == '__main__':
    main()
