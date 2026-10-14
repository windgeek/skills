#!/usr/bin/env python3
"""把公众号 Markdown 母稿排成可直接粘贴进公众号编辑器的正文 HTML（“书页”样式）。

确定性渲染：同一份 Markdown 永远得到同一份 HTML，不改写、不增删原文的字。
只用公众号保留的写法：<section>/<p>/<span>/<strong>/<img>/<table>，样式全部内联，
每个文字节点包在 <span leaf=""> 里。

用法:
    typeset.py 文章-gzh.md [-o 输出.html] [--numbers] [--accent '#9a3b26']
              [--keep-title] [--no-endmark]

默认输出与母稿同目录：<母稿名>-排版.html。运行结束会在 stderr 打印排版报告
（强调密度、图片、链接注释等），有 WARNING 时退出码为 0，但需要逐条处理。
"""

import argparse
import html
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------- 样式常量
INK = "#2b2b2b"          # 正文墨色：不用纯黑，长读不刺眼
INK_STRONG = "#111111"   # 加粗
SOFT = "#5c5c5c"         # 引用
GREY = "#8c8c8c"         # 图注、小字
FAINT = "#b9b4aa"        # 分隔符号
RULE = "#e7e3db"         # 细线
PAPER = "#f6f4ef"        # 代码、表头的纸色
DEFAULT_ACCENT = "#9a3b26"  # 朱砂：全篇唯一的颜色
MONO = "Menlo,Consolas,'SF Mono',monospace"

FINE_PRINT_HEADINGS = re.compile(
    r"^(信息来源|参考资料|参考文献|资料来源|来源|注释|延伸阅读|免责声明|说明)$")


def esc(s):
    return html.escape(s, quote=False)


def leaf(text):
    return f'<span leaf="">{esc(text)}</span>' if text else ""


def hex_rgba(hex_color, alpha):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


class Report:
    def __init__(self):
        self.warnings, self.notes = [], []

    def warn(self, msg):
        self.warnings.append(msg)

    def note(self, msg):
        self.notes.append(msg)


# ---------------------------------------------------------------- 行内
INLINE = re.compile(
    r"(?P<code>`[^`]+`)"
    r"|(?P<img>!\[[^\]]*\]\([^)]+\))"
    r"|(?P<link>\[[^\]]+\]\([^)\s]+(?:\s+\"[^\"]*\")?\))"
    r"|(?P<strong>\*\*[^*]+?\*\*|__[^_]+?__)"
    r"|(?P<mark>==[^=]+?==)"
    r"|(?P<u><u>.+?</u>|\+\+[^+]+?\+\+)"
    r"|(?P<em>(?<![*\w])\*[^*\s][^*]*?\*(?!\*))"
    r"|(?P<br><br\s*/?>)"
)


class Inline:
    def __init__(self, ctx):
        self.ctx = ctx

    def render(self, text, base_style=""):
        out, pos = [], 0
        for m in INLINE.finditer(text):
            out.append(leaf(text[pos:m.start()]))
            out.append(self.token(m))
            pos = m.end()
        out.append(leaf(text[pos:]))
        return "".join(out)

    def token(self, m):
        kind, raw = m.lastgroup, m.group(0)
        c = self.ctx
        if kind == "code":
            return (f'<span style="font-family:{MONO};font-size:0.86em;background:{PAPER};'
                    f'color:#4a4a4a;padding:0.1em 0.35em;border-radius:3px;">'
                    f'{leaf(raw[1:-1])}</span>')
        if kind == "strong":
            c.strong_in_block += 1
            return (f'<strong style="font-weight:600;color:{INK_STRONG};">'
                    f'{self.render(raw[2:-2])}</strong>')
        if kind == "mark":
            c.marks += 1
            tint = hex_rgba(c.accent, 0.16)
            return (f'<span style="background:linear-gradient(transparent 60%,{tint} 60%);'
                    f'padding:0 1px;">{self.render(raw[2:-2])}</span>')
        if kind == "u":
            inner = raw[3:-4] if raw.startswith("<u>") else raw[2:-2]
            return (f'<span style="border-bottom:1px solid {c.accent};padding-bottom:1px;">'
                    f'{self.render(inner)}</span>')
        if kind == "em":
            return f'<span style="color:{c.accent};">{self.render(raw[1:-1])}</span>'
        if kind == "br":
            return "<br>"
        if kind == "img":
            c.report.warn(f"行内图片未单独成段，已按文字处理：{raw[:40]}")
            return leaf(raw)
        if kind == "link":
            lm = re.match(r"\[([^\]]+)\]\(([^)\s]+)", raw)
            label, url = lm.group(1), lm.group(2)
            if c.fine_print:
                # 来源区：链接文字后直接给出网址，读者可以长按复制
                return (self.render(label)
                        + f'<span style="color:#a5a097;word-break:break-all;">'
                        + leaf(f" {url}") + "</span>")
            c.links.append((label, url))
            n = len(c.links)
            return (self.render(label)
                    + f'<span style="color:{c.accent};font-size:0.7em;vertical-align:super;'
                    f'line-height:0;margin-left:1px;">{leaf(f"[{n}]")}</span>')
        return leaf(raw)


# ---------------------------------------------------------------- 块级
class Ctx:
    def __init__(self, accent, numbers, report):
        self.accent, self.numbers, self.report = accent, numbers, report
        self.links, self.marks, self.strong_in_block = [], 0, 0
        self.fine_print = False
        self.h2_count = 0
        self.last_body = None   # (out 下标, 块类型)：正文最后一块，用来放文末记号
        self.fine_start = None  # 第一个来源/注释小字区在 out 里的下标


def align_for(text):
    """纯中文两端对齐；夹杂较多英文时两端对齐会把单词间距拉开，改左对齐。"""
    latin = len(re.findall(r"[A-Za-z]", text))
    return "left" if latin > 0.08 * max(len(text), 1) else "justify"


def p_style(ctx, text="", size=16, color=INK):
    if ctx.fine_print:
        size, color = 13, GREY
    lh = "1.8" if size <= 14 else "1.9"
    return (f"margin:0 0 1.35em;font-size:{size}px;line-height:{lh};color:{color};"
            f"letter-spacing:0.04em;text-align:{align_for(text)};")


def split_blocks(md):
    """切成块：(类型, 内容)。"""
    lines = md.replace("\r\n", "\n").split("\n")
    blocks, i = [], 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s:
            i += 1
            continue
        if s.startswith("<!--"):
            while i < len(lines) and "-->" not in lines[i]:
                i += 1
            i += 1
            continue
        fence = re.match(r"^(```+|~~~+)\s*([\w+-]*)", s)
        if fence:
            mark, lang, body = fence.group(1), fence.group(2), []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(mark):
                body.append(lines[i])
                i += 1
            blocks.append(("code", (lang, body)))
            i += 1
            continue
        h = re.match(r"^(#{1,6})\s+(.*?)\s*#*$", s)
        if h:
            blocks.append((f"h{len(h.group(1))}", h.group(2)))
            i += 1
            continue
        if re.match(r"^(\*\s*){3,}$|^(-\s*){3,}$|^(_\s*){3,}$", s):
            blocks.append(("hr", None))
            i += 1
            continue
        if s.startswith(">"):
            body = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                body.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            blocks.append(("quote", body))
            continue
        if s.startswith("|") and i + 1 < len(lines) and re.match(
                r"^\s*\|?\s*:?-{2,}", lines[i + 1]):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            blocks.append(("table", rows))
            continue
        if re.match(r"^([-*+]|\d+[.)])\s+", s):
            items = []
            while i < len(lines) and lines[i].strip():
                ln = lines[i]
                m = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", ln)
                if m:
                    items.append([len(m.group(1).expandtabs(4)), m.group(2), m.group(3)])
                elif items:
                    items[-1][2] += ln.strip()
                i += 1
            blocks.append(("list", items))
            continue
        img = re.match(r"^!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"([^\"]*)\")?\)$", s)
        if img:
            blocks.append(("img", (img.group(1), img.group(2))))
            i += 1
            continue
        para = []
        while i < len(lines) and lines[i].strip() and not re.match(
                r"^(#{1,6}\s|>|```|~~~|\|)", lines[i].strip()) and not re.match(
                r"^([-*+]|\d+[.)])\s+", lines[i].strip()):
            para.append(lines[i].strip())
            i += 1
        blocks.append(("p", para))
    return blocks


def render(md, accent=DEFAULT_ACCENT, numbers=False, keep_title=False, endmark=True):
    report = Report()
    ctx = Ctx(accent, numbers, report)
    inl = Inline(ctx)
    blocks = split_blocks(md)
    out = []
    first_content = True

    # 去掉紧挨在 ## 前面的 ---：章节标题自带留白，再加分隔符就重复了
    cleaned = []
    for k, (t, v) in enumerate(blocks):
        nxt = blocks[k + 1][0] if k + 1 < len(blocks) else None
        if t == "hr" and (nxt == "h2" or not cleaned or nxt is None):
            continue
        cleaned.append((t, v))
    blocks = cleaned

    title = None
    for t, v in blocks:
        if t == "h1":
            if title is None:
                title = v
                if keep_title:
                    out.append(
                        f'<p style="margin:0 0 1.6em;font-size:22px;line-height:1.5;font-weight:600;'
                        f'color:{INK_STRONG};letter-spacing:0.06em;">{inl.render(v)}</p>')
            else:
                report.warn(f"出现第二个 # 标题，已按 ## 处理：{v[:30]}")
                t = "h2"
            if t == "h1":
                continue

        ctx.strong_in_block = 0

        if t == "h2":
            ctx.h2_count += 1
            ctx.fine_print = bool(FINE_PRINT_HEADINGS.match(re.sub(r"[*：:]", "", v).strip()))
            if ctx.fine_print:
                if ctx.fine_start is None:
                    ctx.fine_start = len(out)
                out.append(
                    f'<section style="margin:3em 0 1em;padding-top:1.2em;border-top:1px solid {RULE};">'
                    f'<p style="margin:0;font-size:13px;font-weight:600;color:{GREY};letter-spacing:0.2em;">'
                    f'{inl.render(v)}</p></section>')
            else:
                num = ""
                if numbers and not re.match(r"^([一二三四五六七八九十]+、|\d+[.、])", v):
                    num = (f'<p style="margin:0 0 0.5em;font-size:13px;line-height:1;color:{accent};'
                           f'letter-spacing:0.18em;font-family:{MONO};">'
                           f'{leaf(f"{ctx.h2_count:02d}")}</p>')
                bar = ("" if num else
                       f'<section style="width:20px;height:2px;background:{accent};margin:0 0 0.9em;'
                       f'font-size:0;line-height:0;overflow:hidden;"><span leaf="">.</span></section>')
                out.append(
                    f'<section style="margin:2.8em 0 1.3em;">{num}{bar}'
                    f'<p style="margin:0;font-size:19px;line-height:1.55;font-weight:600;color:{INK_STRONG};'
                    f'letter-spacing:0.05em;">{inl.render(v)}</p></section>')
            first_content = False
            continue

        if t in ("h3", "h4", "h5", "h6"):
            size = 16 if not ctx.fine_print else 13
            out.append(
                f'<p style="margin:2em 0 0.8em;font-size:{size}px;line-height:1.6;font-weight:600;'
                f'color:{INK_STRONG};letter-spacing:0.04em;">{inl.render(v)}</p>')
            first_content = False
            continue

        if t == "hr":
            out.append(
                f'<p style="margin:2.4em 0;text-align:center;font-size:14px;line-height:1;color:#a8a39a;'
                f'letter-spacing:0.8em;">{leaf("· · ·")}</p>')
            continue

        if t == "quote":
            text_lines = [l for l in v]
            paras, buf = [], []
            for l in text_lines:
                if l.strip():
                    buf.append(l.strip())
                elif buf:
                    paras.append(buf)
                    buf = []
            if buf:
                paras.append(buf)
            if first_content:
                # 题记：文章开头的引言，居中、小一号、灰，下面一道短线
                body = "".join(
                    f'<p style="margin:0 0 0.6em;font-size:15px;line-height:1.95;color:{SOFT};'
                    f'letter-spacing:0.06em;text-align:center;">'
                    f'{"<br>".join(inl.render(x) for x in pa)}</p>' for pa in paras)
                out.append(
                    f'<section style="margin:0.5em 0 2.4em;padding:0 1em;">{body}'
                    f'<section style="width:28px;height:1px;background:{FAINT};margin:1.4em auto 0;'
                    f'font-size:0;line-height:0;overflow:hidden;"><span leaf="">.</span></section></section>')
            else:
                body = "".join(
                    f'<p style="margin:0 0 0.5em;font-size:15px;line-height:1.9;color:{SOFT};'
                    f'letter-spacing:0.04em;text-align:justify;">'
                    f'{"<br>".join(inl.render(x) for x in pa)}</p>' for pa in paras)
                out.append(
                    f'<section style="margin:1.8em 0;padding:0.1em 0 0.1em 1.1em;'
                    f'border-left:2px solid {RULE};">{body}</section>')
            if not ctx.fine_print:
                ctx.last_body = (len(out) - 1, "block")
            first_content = False
            continue

        if t == "code":
            lang, lines = v
            while lines and not lines[-1].strip():
                lines.pop()
            rows = "".join(
                f'<p style="margin:0;font-family:{MONO};font-size:12.5px;line-height:1.75;color:#3a3a3a;'
                f'white-space:pre;letter-spacing:0;">'
                f'{leaf(l.expandtabs(4).replace(" ", chr(0xa0))) if l.strip() else "<br>"}</p>'
                for l in lines)
            out.append(
                f'<section style="margin:1.6em 0;padding:14px 16px;background:{PAPER};border-radius:4px;'
                f'overflow-x:auto;">{rows}</section>')
            if not ctx.fine_print:
                ctx.last_body = (len(out) - 1, "block")
            first_content = False
            continue

        if t == "img":
            alt, src = v
            cap = ""
            if alt.strip() and not re.match(r"^(image|img|图片|图|cover|封面)\d*$", alt.strip(), re.I):
                cap = (f'<p style="margin:0.8em 0 0;font-size:13px;line-height:1.7;color:{GREY};'
                       f'text-align:center;letter-spacing:0.04em;">{leaf(alt.strip())}</p>')
            out.append(
                f'<section style="margin:1.9em 0;text-align:center;">'
                f'<img src="{html.escape(src)}" alt="{html.escape(alt)}" '
                f'style="max-width:100%;height:auto;display:block;margin:0 auto;border-radius:2px;">'
                f'{cap}</section>')
            if not ctx.fine_print:
                ctx.last_body = (len(out) - 1, "block")
            first_content = False
            continue

        if t == "table":
            rows = [r.strip().strip("|").split("|") for r in v]
            align_row = rows[1]
            aligns = []
            for a in align_row:
                a = a.strip()
                aligns.append("right" if a.endswith(":") and not a.startswith(":")
                              else "center" if a.startswith(":") and a.endswith(":") else "left")
            head, body_rows = rows[0], rows[2:]
            def cell(txt, j, th):
                al = aligns[j] if j < len(aligns) else "left"
                style = (f"padding:8px 10px;border-bottom:1px solid {RULE};text-align:{al};"
                         f"font-size:14px;line-height:1.6;color:{INK};")
                if th:
                    style += f"background:{PAPER};font-weight:600;color:{INK_STRONG};"
                tag = "th" if th else "td"
                return f'<{tag} style="{style}">{inl.render(txt.strip())}</{tag}>'
            thead = "<tr>" + "".join(cell(c, j, True) for j, c in enumerate(head)) + "</tr>"
            tbody = "".join("<tr>" + "".join(cell(c, j, False) for j, c in enumerate(r)) + "</tr>"
                            for r in body_rows)
            out.append(
                f'<section style="margin:1.8em 0;overflow-x:auto;">'
                f'<table style="width:100%;border-collapse:collapse;border-top:1px solid {RULE};">'
                f'{thead}{tbody}</table></section>')
            if not ctx.fine_print:
                ctx.last_body = (len(out) - 1, "block")
            first_content = False
            continue

        if t == "list":
            base = min(x[0] for x in v)
            counters = {}
            items_html = []
            for indent, marker, text in v:
                level = 0 if indent <= base else 1
                ctx.strong_in_block = 0
                size, color = (13, GREY) if ctx.fine_print else (16, INK)
                lh = "1.8" if ctx.fine_print else "1.9"
                mk_color = GREY if ctx.fine_print else ctx.accent
                if re.match(r"\d", marker):
                    counters[level] = counters.get(level, 0) + 1
                    mk = f"{counters[level]}."
                    mk_style = f"color:{mk_color};font-size:{size - 1}px;"
                else:
                    mk = "·" if level == 0 else "–"
                    mk_style = f"color:{mk_color};font-size:{size}px;font-weight:600;"
                items_html.append(
                    f'<section style="display:flex;margin:0 0 0.65em {1.4 * level}em;">'
                    f'<span style="flex-shrink:0;width:1.6em;{mk_style}line-height:{lh};">{leaf(mk)}</span>'
                    f'<span style="flex:1;font-size:{size}px;line-height:{lh};color:{color};'
                    f'letter-spacing:0.04em;text-align:{align_for(text)};">{inl.render(text)}</span></section>')
            out.append(f'<section style="margin:0 0 1.35em;">{"".join(items_html)}</section>')
            if not ctx.fine_print:
                ctx.last_body = (len(out) - 1, "block")
            first_content = False
            continue

        if t == "p":
            text = " ".join(v)
            # 中文行与行之间不该有空格
            text = re.sub(r"(?<=[　-鿿＀-￯]) (?=[　-鿿＀-￯])", "", text)
            rendered = inl.render(text)
            if ctx.strong_in_block > 2:
                report.warn(f"一段里加粗 {ctx.strong_in_block} 处，强调太密：{text[:24]}…")
            out.append(f'<p style="{p_style(ctx, text)}">{rendered}</p>')
            if not ctx.fine_print:
                ctx.last_body = (len(out) - 1, "p")
            first_content = False
            continue

    # 文末记号：朱砂小方块，跟在正文最后一段后面；正文最后一块不是段落时单独成行
    if endmark and ctx.last_body:
        mark = (f'<span style="display:inline-block;width:6px;height:6px;background:{accent};'
                f'margin-left:0.5em;vertical-align:middle;font-size:0;line-height:0;overflow:hidden;">'
                f'<span leaf="">.</span></span>')
        k, kind = ctx.last_body
        if kind == "p":
            out[k] = out[k][:-4] + mark + "</p>"
        else:
            out.insert(k + 1, f'<p style="margin:0 0 1.35em;line-height:1;">{mark}</p>')
            if ctx.fine_start is not None and ctx.fine_start >= k + 1:
                ctx.fine_start += 1

    if ctx.links:
        notes = "".join(
            f'<p style="margin:0 0 0.4em;font-size:12px;line-height:1.7;color:{GREY};word-break:break-all;">'
            f'{leaf(f"[{n}] {label}：{url}")}</p>'
            for n, (label, url) in enumerate(ctx.links, 1))
        block = (f'<section style="margin:2.6em 0 0;padding-top:1em;border-top:1px solid {RULE};">'
                 f'{notes}</section>')
        # 注释紧跟正文，排在“信息来源”等小字区之前
        if ctx.fine_start is not None:
            out.insert(ctx.fine_start, block)
        else:
            out.append(block)
        report.note(f"正文里 {len(ctx.links)} 个链接改为角标注释，网址列在文末（公众号正文外链不可点）")

    if ctx.marks > 3:
        report.warn(f"==高亮== 用了 {ctx.marks} 处，全篇最多 3 处")

    body = "".join(out)
    root = (f'<section style="margin:0 auto;padding:0;font-size:16px;line-height:1.9;color:{INK};'
            f'letter-spacing:0.04em;word-break:break-word;">{body}</section>')
    if title is None:
        report.warn("母稿没有 # 标题；公众号标题需要在发布时单独填写")
    return root, title, report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("md")
    ap.add_argument("-o", "--out")
    ap.add_argument("--numbers", action="store_true", help="章节标题上方加 01、02（教程、清单、步骤型文章用）")
    ap.add_argument("--accent", default=DEFAULT_ACCENT, help="唯一的强调色，默认朱砂 #9a3b26")
    ap.add_argument("--keep-title", action="store_true", help="正文里也排出 # 标题（默认不排：公众号自带标题）")
    ap.add_argument("--no-endmark", action="store_true", help="不加文末小方块")
    a = ap.parse_args()

    src = Path(a.md)
    md = src.read_text(encoding="utf-8")
    md = re.sub(r"^---\n.*?\n---\n", "", md, count=1, flags=re.S) if md.startswith("---\n") else md
    if not re.match(r"^#[0-9a-fA-F]{6}$", a.accent):
        sys.exit("--accent 需要 #RRGGBB 形式")
    root, title, rep = render(md, a.accent, a.numbers, a.keep_title, not a.no_endmark)
    out = Path(a.out) if a.out else src.with_name(f"{src.stem}-排版.html")
    out.write_text(root + "\n", encoding="utf-8")

    print(f"✓ 正文 HTML：{out}", file=sys.stderr)
    if title:
        print(f"  标题（发布时填在公众号标题栏）：{title}", file=sys.stderr)
    for n in rep.notes:
        print(f"  · {n}", file=sys.stderr)
    for w in rep.warnings:
        print(f"  WARNING {w}", file=sys.stderr)
    print(out)


if __name__ == "__main__":
    main()
