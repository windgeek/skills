#!/usr/bin/env python3
"""公众号正文 HTML 校验：粘贴进公众号编辑器之前，查会被过滤或会走样的写法。

用法:
    check_html.py 正文-排版.html

ERROR：公众号会过滤掉或改写，粘贴后样式丢失，必须修。
WARNING：能粘贴但读起来会出问题（半角标点、文字没包 leaf、图片缺地址等），交付前修到 0。
退出码：有 ERROR 为 1，否则为 0。输出最后一行是 “ERROR × n · WARNING × m”。
"""

import re
import sys
from html.parser import HTMLParser

BANNED = [
    (r"<style[\s>]", "<style> 会被过滤，样式必须写在 style 属性里"),
    (r"<script[\s>]", "<script> 会被过滤"),
    (r"<link[\s>]", "<link> 外部样式表会被过滤"),
    (r"</?div[\s>]", "<div> 会被改写，用 <section>"),
    (r"</?(?:h[1-6])[\s>]", "h1–h6 会套上编辑器自带样式，用 <p> 加内联样式"),
    (r"</?(?:ul|ol|li)[\s>]", "ul/ol/li 在各端缩进不一致，用 <section> 自排列表"),
    (r"\sclass\s*=", "class 会被剥离"),
    (r"\sid\s*=", "id 会被剥离"),
    (r"position\s*:\s*(?:absolute|fixed|sticky)", "绝对/固定定位不被支持"),
    (r"float\s*:", "float 不被支持"),
    (r"display\s*:\s*grid", "grid 不被支持，用 flex"),
    (r"var\(\s*--", "CSS 变量不被支持，写死颜色"),
    (r"@(?:media|keyframes|import|font-face)", "@ 规则不被支持"),
    (r"<(?:iframe|video|audio|form|input|button)[\s>]", "交互元素会被过滤"),
]

CJK = r"㐀-鿿＀-￯　-〿"
HALF = re.compile(rf"[{CJK}][,;:!?]|[,;:!?](?=[{CJK}])")
STRAIGHT_QUOTE = re.compile(rf"[{CJK}][\"']|[\"'][{CJK}]")
MONO = re.compile(r"monospace|white-space\s*:\s*pre", re.I)


class Walker(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.leaf = 0
        self.mono = 0
        self.unwrapped, self.punct, self.imgs_bad = [], [], []
        self.leaf_total = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        is_leaf = tag == "span" and "leaf" in a
        is_mono = bool(MONO.search(a.get("style") or ""))
        if tag == "img":
            src = (a.get("src") or "").strip()
            if not src:
                self.imgs_bad.append("缺 src")
            if "width:100%" in (a.get("style") or "").replace(" ", "") and "max-width" not in (a.get("style") or ""):
                self.imgs_bad.append(f"{src[:40]} 强制铺满会把小图拉糊")
            return
        if tag in ("br", "hr"):
            return
        self.leaf += is_leaf
        self.leaf_total += is_leaf
        self.mono += is_mono
        self.stack.append((tag, is_leaf, is_mono))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                for _, l, m in self.stack[i:]:
                    self.leaf -= l
                    self.mono -= m
                del self.stack[i:]
                return

    def handle_data(self, data):
        t = data.strip()
        if not t:
            return
        snippet = t[:20] + ("…" if len(t) > 20 else "")
        if self.leaf == 0:
            self.unwrapped.append(snippet)
        if self.mono == 0 and (HALF.search(t) or STRAIGHT_QUOTE.search(t)):
            self.punct.append(snippet)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    src = open(path, encoding="utf-8").read()
    errors, warnings = [], []

    for rx, msg in BANNED:
        n = len(re.findall(rx, src, re.I))
        if n:
            errors.append(f"{msg}（{n} 处）")
    if not src.lstrip().startswith("<section"):
        errors.append("正文必须从一个 <section> 开始，不要带 <html>/<head>/<body>")

    w = Walker()
    w.feed(src)
    if w.leaf_total == 0:
        errors.append('没有任何 <span leaf="">，粘贴后样式会大面积丢失')
    if w.unwrapped:
        warnings.append(f"{len(w.unwrapped)} 处文字没包在 <span leaf> 里，例：" + "；".join(w.unwrapped[:4]))
    if w.punct:
        warnings.append(f"{len(w.punct)} 处中文旁边是半角标点或直引号（代码除外），应改全角，例："
                        + "；".join(w.punct[:4]) + "。改母稿再重排，不要改 HTML")
    for b in w.imgs_bad:
        warnings.append(f"图片：{b}")

    print(f"公众号正文校验：{path}")
    for e in errors:
        print(f"  ERROR    {e}")
    for x in warnings:
        print(f"  WARNING  {x}")
    print(f"ERROR × {len(errors)} · WARNING × {len(warnings)}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
