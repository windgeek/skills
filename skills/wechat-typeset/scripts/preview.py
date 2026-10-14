#!/usr/bin/env python3
"""把排好的正文 HTML 包成预览页：手机宽度、可切换深色模式（模拟微信的自动反色），
右上角“复制”按钮把正文以富文本放进剪贴板，到公众号编辑器里直接粘贴。

按钮和脚本只在预览外壳里，复制出去的只有正文 <section>。

用法:
    preview.py 正文-排版.html [输出.html]
默认输出：正文同目录 <正文名去掉“-排版”>-预览.html
"""

import html
import sys
from pathlib import Path

SHELL = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
  :root { color-scheme: light; }
  body { margin:0; background:#ecebe7; font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif; }
  .bar { position:sticky; top:0; z-index:2; display:flex; gap:8px; justify-content:flex-end; align-items:center;
         padding:10px 16px; background:rgba(236,235,231,.92); backdrop-filter:blur(8px); }
  .bar span { margin-right:auto; font-size:12px; color:#8c8c8c; letter-spacing:.1em; }
  button { font:inherit; font-size:13px; padding:6px 14px; border-radius:999px; border:1px solid #cfcac0;
           background:#fff; color:#2b2b2b; cursor:pointer; }
  button.primary { background:#2b2b2b; color:#fff; border-color:#2b2b2b; }
  .phone { box-sizing:border-box; width:min(414px, 100% - 32px); margin:12px auto 64px; background:#fff;
           padding:28px 16px 40px; border-radius:6px; box-shadow:0 1px 3px rgba(0,0,0,.06); }
  .dark .phone { filter:invert(.92) hue-rotate(180deg); }
  .dark .phone img { filter:invert(1) hue-rotate(180deg); }
  .toast { position:fixed; left:50%; bottom:28px; transform:translateX(-50%); padding:8px 16px; border-radius:999px;
           background:#2b2b2b; color:#fff; font-size:13px; opacity:0; transition:opacity .2s; pointer-events:none; }
  .toast.on { opacity:1; }
</style></head>
<body>
<div class="bar"><span>预览 · 宽 414</span>
  <button id="mode">深色</button>
  <button id="copy" class="primary">复制正文</button></div>
<div class="phone"><div id="article">__BODY__</div></div>
<div class="toast" id="toast"></div>
<script>
const art = document.getElementById('article');
const toast = msg => { const t = document.getElementById('toast'); t.textContent = msg; t.classList.add('on');
  setTimeout(() => t.classList.remove('on'), 1800); };
document.getElementById('mode').onclick = e => {
  document.body.classList.toggle('dark');
  e.target.textContent = document.body.classList.contains('dark') ? '浅色' : '深色'; };
document.getElementById('copy').onclick = async () => {
  const htmlText = art.innerHTML, plain = art.innerText;
  try {
    await navigator.clipboard.write([new ClipboardItem({
      'text/html': new Blob([htmlText], {type: 'text/html'}),
      'text/plain': new Blob([plain], {type: 'text/plain'}) })]);
    toast('已复制，去公众号编辑器粘贴');
  } catch (err) {
    const r = document.createRange(); r.selectNodeContents(art);
    const s = getSelection(); s.removeAllRanges(); s.addRange(r);
    const ok = document.execCommand('copy'); s.removeAllRanges();
    toast(ok ? '已复制，去公众号编辑器粘贴' : '复制失败：请手动全选正文复制');
  }
};
</script>
</body></html>
"""


def main():
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    src = Path(sys.argv[1])
    body = src.read_text(encoding="utf-8").strip()
    stem = src.stem[:-3] if src.stem.endswith("-排版") else src.stem
    out = Path(sys.argv[2]) if len(sys.argv) == 3 else src.with_name(f"{stem}-预览.html")
    page = SHELL.replace("__TITLE__", html.escape(stem)).replace("__BODY__", body)
    out.write_text(page, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
