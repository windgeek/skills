#!/usr/bin/env python3
"""把一个 SVG 渲染成一组透明 PNG，每张对应一个交互状态。

SVG 里需要变色的部件用 id="<prefix>1" … id="<prefix>N" 标好，初始填 --from-color。
第 k 张图（k = 0..N）把前 k 个部件改成 --to-color。

用法：
  python3 render_states.py ship.svg --prefix plank- --count 10 \
      --from-color '#6b5a45' --to-color '#e8c27a' --out ship_png --name ship --scale 3
输出 ship_00.png … ship_10.png。依赖 Google Chrome（headless）；不在默认位置时用环境变量 CHROME 指定可执行文件。
"""
import argparse, os, re, subprocess, tempfile

CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

ap = argparse.ArgumentParser()
ap.add_argument("svg")
ap.add_argument("--prefix", required=True)
ap.add_argument("--count", type=int, required=True)
ap.add_argument("--from-color", required=True)
ap.add_argument("--to-color", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--name", default="state")
ap.add_argument("--scale", type=float, default=3)
a = ap.parse_args()

src = open(a.svg, encoding="utf-8").read()
m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', src)
if not m:
    raise SystemExit("SVG 需要 viewBox=\"0 0 W H\"")
w, h = round(float(m[1]) * a.scale), round(float(m[2]) * a.scale)
src = re.sub(r'<svg([^>]*?)\swidth="[^"]*"\s+height="[^"]*"', r'<svg\1', src, count=1)
src = src.replace("<svg", f'<svg width="{w}" height="{h}"', 1)
os.makedirs(a.out, exist_ok=True)
digits = len(str(a.count))
tmp = tempfile.mkdtemp()

for k in range(a.count + 1):
    s = src
    for i in range(1, k + 1):
        s = re.sub(rf'(<[^>]*id="{re.escape(a.prefix)}{i}"[^>]*?)fill="{re.escape(a.from_color)}"',
                   rf'\1fill="{a.to_color}"', s, count=1)
    html = os.path.join(tmp, f"{k}.html")
    open(html, "w", encoding="utf-8").write(
        f'<html><body style="margin:0;background:transparent">{s}</body></html>')
    png = os.path.join(a.out, f"{a.name}_{k:0{max(2, digits)}d}.png")
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--default-background-color=00000000", f"--screenshot={png}",
                    f"--window-size={w},{h}", f"file://{html}"],
                   check=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    print(png)
