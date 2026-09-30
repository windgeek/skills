# 技术管线

全部用代码生成：画面是网页里的 `render(t)`，headless Chrome 逐帧截图，ffmpeg 合成。不用视频生成，不用素材库画面。模板在 `engine/`。

```
歌 (wav)
 ├─► 分析：librosa → audio.js（拍点、能量、低频、高频、onset，30 fps）
 ├─► 歌词：原稿 + whisper 逐字时间戳 → 歌词时间表
 └─► 剪辑表（shots）+ 歌词表 ──► index.html 里的 render(t) ──► 并行渲染 ──► ffmpeg（颗粒、编码、混入原曲）
```

## 1. 画面是时间的纯函数

```js
window.DUR = 179.6;
window.render = t => { ... };            // 同一个 t 永远画出同一帧
window.renderFrame = t => dataURL;       // 渲染器调用
```

- 不用 `Math.random()`、不用 `Date.now()`、不保留上一帧的状态。任何一帧都能被任意 worker 单独渲染。
- 2D 风格用 Canvas 2D；需要光、折射、辉光的用 WebGL2 着色器；3D 用 three.js。
- 按两拍/三拍“一拍一画”（12 fps 或 8 fps 步进）是动画味的来源，但**镜头和光保持每帧平滑**。

## 2. 一张剪辑表管全片

```js
{ t: 41.3, sc: SEA, flash: 1, xf: 0, f: (localT, t, G) => ({ p0: [...], p1: [...] }) }
```

- `t` 自动吸附到最近的拍点。`xf` 为叠化时长。`f` 返回这个镜头此刻的参数。
- 全局状态（光源、水位、色温等）写成时间的函数，所有镜头共用，保证跨镜头连续。
- 歌词表：`[开始, 结束, 文本, 版式]`，版式由 STYLE.md 规定。

## 3. 渲染

- `node render.mjs --stills 3,42,110`：抽帧检查。`sheet.sh` 拼成总览图。
- `node render.mjs`：按 CPU 核数分段并行，每段一个浏览器，最后 concat 并混入原曲。
- WebGL 需要 GPU：Chrome 参数 `--use-angle=metal --enable-gpu --ignore-gpu-blocklist`。
- 场景渲染到 RGBA16F 帧缓冲（HDR），后期 pass 做辉光、色差、调色、暗角、黑边、歌词合成。
- 辉光：对帧缓冲 `generateMipmap`，从 mip 2–7 取样叠加。不要用 24 个离散采样点（细亮线会出条纹）。

## 4. 颗粒与编码

- **颗粒不要画在页面里**，否则每帧都不可压缩（可能膨胀到 1 GB 以上）。`render.mjs` 默认在 ffmpeg 里加 `noise=c0s=3:allf=t`（`--grain 0` 关闭；像素、矢量、平面纸艺风格建议 0–2）。
- 母版 `build/master.mp4`（crf 14，无颗粒）；发布版 `build/<名字>.mp4`（颗粒 + `-preset slow -crf 22`）。不要用 `-tune grain`，文件会大十几倍。

## 5. 检查

1. 总览：每 6 秒一帧拼 5×6，看全片节奏和色彩弧线。
2. 抽帧：每段 2–3 帧放大看；叠化中间帧必须看（容易出现双重曝光的脏画面）。
3. 字：亮背景上的字加阴影；大字卡不遮主体。
4. 成片：`ffprobe` 查时长，`blackdetect` 查黑帧。

## 6. 字体

- 只用 OFL 字体，下载到项目 `fonts/`，用 `@font-face` 加载；渲染前 `document.fonts.load` 每个字重。
- 中文衬线：Noto Serif SC / Shippori Mincho / Zen Old Mincho（OFL）。
- 字体本身就是风格的一部分，由 STYLE.md 指定。
