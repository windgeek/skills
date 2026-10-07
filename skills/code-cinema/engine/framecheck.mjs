// 框景检查：连续取帧，自动找“逐帧看才发现”的问题，出清单和标了红框的截图。交付前必跑。
// node framecheck.mjs [项目目录]               （默认是本文件所在目录；老项目可以直接用 skill 里的这份：node <skill>/engine/framecheck.mjs <项目>）
// 可选：--page vertical.html  --step 2（每几帧取一帧，默认 2）  --static 4（静止多少秒提示）
//
// 查这些（借鉴 huashu-art-motion 的 qa.py，按本引擎改写）：
//   1. 卡点：每个硬切镜头，切点前后 ±0.3 秒逐帧量画面变化，最大变化应落在切点那一帧。
//      晚了（新镜头先黑一下、淡入太慢）观众会觉得拖拍；切了但画面几乎没变，等于没切。你听不到声音，这一项是替耳朵看的。
//   2. 闪烁 / 跳变：不在切点上、却比前后帧变化大很多的孤立一帧（整屏重洗随机数、某一帧穿帮、叠化里新旧两层没对齐）。
//      有意的拍点闪白也会被报出来，看过就放。
//   3. 叠字：两串不同的字互相压住，包括歌词压在画面里的字上、叠化时新旧两个镜头的字半透明叠在一起。
//   4. 出画：字被画面边缘切掉一部分（含 letterbox 黑边）。
//   5. 静止：画面连续 N 秒几乎不动。安静段落可能是有意的，副歌里出现就要看。
//   6. 场景报错；同一时刻先后画两次不一样（并行渲染时，各段接缝处会跳）。
// 持续 ≥0.3 秒的文字问题才报。结果是“去看这一帧”的线索，报出来的都看截图确认。
// 盲区：着色器里画的字、画进离屏画布再贴上来的字量不到；字压在图形上（压脸、压主体）查不到，仍要看帧。
// 产物：build/qa/framecheck.md、build/qa/framecheck.jpg（问题帧拼图，#编号对应清单）
import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf('--' + k); return i >= 0 ? args[i + 1] : d; };
const dir = path.resolve(args[0] && !args[0].startsWith('--') ? args[0] : path.dirname(new URL(import.meta.url).pathname));
const STEP = Number(opt('step', 2)), STATIC_S = Number(opt('static', 4)), MIN_S = 0.3;
const qa = path.join(dir, 'build', 'qa'); fs.mkdirSync(qa, { recursive: true });
const require = createRequire(path.join(dir, 'package.json'));
const puppeteer = (await import(require.resolve('puppeteer-core'))).default;

const browser = await puppeteer.launch({ executablePath: process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true,
  args: ['--allow-file-access-from-files', '--force-device-scale-factor=1', '--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'] });
const page = await browser.newPage();
const errors = [];
page.on('pageerror', e => errors.push(e.message));
page.on('console', m => m.type() === 'error' && errors.push(m.text()));

// 页面脚本之前包一层 fillText / strokeText：记下画在整屏大小画布上的每串字的屏幕外框、透明度、属于哪个镜头
await page.evaluateOnNewDocument(() => {
  const FC = window.__fc = { on: false, layer: 'lyrics', rec: [], W: 0, H: 0 };
  const P = CanvasRenderingContext2D.prototype;
  for (const name of ['fillText', 'strokeText']) {
    const orig = P[name];
    P[name] = function (str, x, y, ...rest) {
      if (FC.on && this.filter === 'none' && this.canvas.width === FC.W && this.canvas.height === FC.H && String(str).trim()) {
        const m = this.measureText(str), T = this.getTransform();
        const pts = [[x - m.actualBoundingBoxLeft, y - m.actualBoundingBoxAscent], [x + m.actualBoundingBoxRight, y - m.actualBoundingBoxAscent],
          [x - m.actualBoundingBoxLeft, y + m.actualBoundingBoxDescent], [x + m.actualBoundingBoxRight, y + m.actualBoundingBoxDescent]]
          .map(([u, v]) => [T.a * u + T.c * v + T.e, T.b * u + T.d * v + T.f]);
        const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
        FC.rec.push({ s: String(str), x0: Math.min(...xs), x1: Math.max(...xs), y0: Math.min(...ys), y1: Math.max(...ys), a: this.globalAlpha, layer: FC.layer,
          fx: Math.round(T.e + T.a * x), fy: Math.round(T.f + T.d * y) });
      }
      return orig.call(this, str, x, y, ...rest);
    };
  }
});

await page.goto('file://' + path.join(dir, opt('page', 'index.html')) + '?render', { waitUntil: 'load' });
const [W, H] = await page.evaluate(() => window.OUT_SIZE || FILM.size || [1920, 1080]);
await page.setViewport({ width: W, height: H });
await page.evaluate(() => window.READY);
const info = await page.evaluate(([W, H]) => {
  const FC = window.__fc; FC.W = W; FC.H = H;
  const shots = (window.FILM && FILM.shots) || [];
  // 给每个 Canvas 2D 镜头包一层：画的时候记下“这是第几个镜头”，画完回到歌词层
  shots.forEach((s, k) => { if (s.draw && !s.__fc) { const d = s.draw; s.draw = (...a) => { FC.layer = k; try { return d(...a); } finally { FC.layer = 'lyrics'; } }; s.__fc = 1; } });
  const sm = u => { u = Math.min(1, Math.max(0, u)); return u * u * (3 - 2 * u); };
  // 叠化时每个镜头在成片里的权重（和 engine.js 的 render 同一算法）
  window.__fcMix = t => {
    let i = 0; while (i < shots.length - 1 && t >= shots[i + 1].t) i++;
    const sh = shots[i], w = { [i]: 1 };
    if (sh && sh.xf && i > 0 && t < sh.t + sh.xf) { const m = 1 - sm((t - sh.t) / sh.xf); w[i] = 1 - m; w[i - 1] = m; }
    return w;
  };
  const sw = 160, sh = Math.round(160 * H / W);
  const small = document.createElement('canvas'); small.width = sw; small.height = sh;
  const sx = small.getContext('2d', { willReadFrequently: true });
  const src = document.querySelector('canvas');
  let prev = null; const keep = new Map();
  window.__fcSample = (t, track = true) => {
    FC.rec = []; FC.on = true; let err = null;
    try { window.render(t); } catch (e) { err = e.message; } FC.on = false;
    sx.drawImage(src, 0, 0, sw, sh);
    const d = sx.getImageData(0, 0, sw, sh).data;
    let moved = 0, sum = 0;
    if (prev) for (let i = 0; i < d.length; i += 4) {
      const v = Math.max(Math.abs(d[i] - prev[i]), Math.abs(d[i + 1] - prev[i + 1]), Math.abs(d[i + 2] - prev[i + 2]));
      if (v > 12) moved++; sum += v;
    }
    const out = { rec: FC.rec, mix: window.__fcMix(t), motion: prev ? moved / (sw * sh) : 0, diff: prev ? sum / (sw * sh) : 0, err };
    prev = d.slice(); return out;
  };
  window.__fcKeep = t => keep.set(t, prev.slice());
  window.__fcSame = t => { const a = keep.get(t), b = prev; let n = 0;
    for (let i = 0; i < a.length; i += 4) if (Math.max(Math.abs(a[i] - b[i]), Math.abs(a[i + 1] - b[i + 1]), Math.abs(a[i + 2] - b[i + 2])) > 24) n++;
    return n / (a.length / 4) < 0.003; };
  window.__fcReset = () => { prev = null; };
  return { dur: window.DUR, fps: FILM.fps || 30, bar: (window.CINEMA && CINEMA.BAR) || 0,
    shots: shots.map((s, k) => ({ k, t: s.t, xf: s.xf || 0, burn: s.xfType === 'burn', flash: s.flash || 0, nosnap: !!s.nosnap })) };
}, [W, H]);
const { dur, fps, bar } = info;
const fmt = t => `${Math.floor(t / 60)}:${(t % 60).toFixed(2).padStart(5, '0')}`;
const sample = t => page.evaluate(t => { const r = window.__fcSample(t); return r; }, t);

// ── 文字判定 ──
const inter = (p, q) => Math.max(0, Math.min(p.x1, q.x1) - Math.max(p.x0, q.x0)) * Math.max(0, Math.min(p.y1, q.y1) - Math.max(p.y0, q.y0));
const area = p => (p.x1 - p.x0) * (p.y1 - p.y0);
const clip = s => s.length > 14 ? s.slice(0, 14) + '…' : s;
const burnAt = t => { const sh = info.shots; let i = 0; while (i < sh.length - 1 && t >= sh[i + 1].t) i++; return sh[i].burn && t < sh[i].t + sh[i].xf; };
function textIssues(rec, mix, t) {
  const burn = burnAt(t);
  const vis = rec.map(r => ({ ...r, ea: r.a * (r.layer === 'lyrics' ? 1 : (mix[r.layer] || 0)) }))
    .filter(r => r.ea >= 0.12 && r.x1 > 0 && r.x0 < W && r.y1 > bar && r.y0 < H - bar && area(r) > 40);
  const uniq = [];
  for (const r of vis) if (!uniq.some(u => u.s === r.s && Math.abs(u.x0 - r.x0) < 4 && Math.abs(u.y0 - r.y0) < 4)) uniq.push(r);
  const out = [];
  for (const r of uniq) if (r.x0 < -2 || r.x1 > W + 2 || r.y0 < bar - 2 || r.y1 > H - bar + 2)
    out.push({ type: '出画', key: '出画|' + r.s, boxes: [r], what: `「${clip(r.s)}」` });
  for (let i = 0; i < uniq.length; i++) for (let j = i + 1; j < uniq.length; j++) {
    const p = uniq[i], q = uniq[j];
    const single = [...p.s].length === 1 && [...q.s].length === 1;
    if (single && (Math.abs(p.fy - q.fy) < 3 || Math.abs(p.fx - q.fx) < 3)) continue;   // 逐字排的同一行 / 同一竖列
    if (p.s.includes(q.s) || q.s.includes(p.s)) continue;                               // 同一句话的投影层、描边层
    if (burn && p.layer !== q.layer && p.layer !== 'lyrics' && q.layer !== 'lyrics') continue;   // 烧纸转场按区域替换，新旧两层不会同时出现在同一处
    if (inter(p, q) / Math.min(area(p), area(q)) > 0.2) {
      const [a, b] = [p.s, q.s].sort();
      const why = p.layer !== q.layer ? (p.layer === 'lyrics' || q.layer === 'lyrics' ? '（歌词压在画面里的字上）' : '（叠化，新旧两个镜头）') : '';
      out.push({ type: '叠字', key: `叠|${a}|${b}`, boxes: [p, q], what: `「${clip(a)}」×「${clip(b)}」${why}` });
    }
  }
  return out;
}

// ── 第一遍：按 --step 帧连续取帧 ──
const N = Math.floor(dur * fps / STEP);
const runs = new Map(), done = [], keepT = [], statics = [], series = [];
let still = null; const t0 = Date.now();
for (let i = 0; i <= N; i++) {
  const t = +(i * STEP / fps).toFixed(4);
  const r = await page.evaluate(t => { const r = window.__fcSample(t); return r; }, t);
  if (r.err) errors.push(`${t.toFixed(2)}s：${r.err}`);
  series.push({ t, diff: r.diff, motion: r.motion });
  if (i % 60 === 0) { keepT.push(t); await page.evaluate(t => window.__fcKeep(t), t); }
  const seen = new Set();
  for (const is of textIssues(r.rec, r.mix, t)) {
    if (seen.has(is.key)) continue; seen.add(is.key);
    const g = runs.get(is.key); if (g) { g.t1 = t; g.last = is.boxes[0]; } else runs.set(is.key, { ...is, t0: t, t1: t, first: is.boxes[0], last: is.boxes[0] });
  }
  for (const [k, g] of runs) if (!seen.has(k)) { runs.delete(k); done.push(g); }
  if (r.motion < 0.002) { still = still || { t0: t }; still.t1 = t; } else { if (still && still.t1 - still.t0 >= STATIC_S) statics.push(still); still = null; }
  if (i % 300 === 0) process.stdout.write(`\r取帧 ${i}/${N}  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
}
done.push(...runs.values()); if (still && still.t1 - still.t0 >= STATIC_S) statics.push(still);
console.log(`\r取帧 ${N + 1} 帧（每 ${STEP} 帧一取），${((Date.now() - t0) / 1000).toFixed(0)}s`);

// ── 卡点：硬切镜头前后 ±0.3s 逐帧 ──
const cuts = [];
for (const s of info.shots) {
  if (s.k === 0 || s.xf > 0.2) continue;                     // 叠化镜头没有“那一帧”
  const fc = Math.ceil(s.t * fps - 1e-6), R = Math.round(0.3 * fps);
  await page.evaluate(() => window.__fcReset());
  const d = [];
  for (let f = fc - R - 1; f <= fc + R; f++) { const r = await sample(Math.max(0, f / fps)); if (f >= fc - R) d.push({ f, diff: r.diff }); }
  const best = d.reduce((a, b) => b.diff > a.diff ? b : a), atCut = d.find(x => x.f === fc);
  const others = d.filter(x => Math.abs(x.f - fc) > 2).map(x => x.diff).sort((a, b) => a - b);
  const base = others[Math.floor(others.length / 2)] || 0;
  cuts.push({ k: s.k, t: s.t, lag: best.f - fc, atCut: atCut.diff, best: best.diff, base });
}
const late = cuts.filter(c => c.lag >= 2 && c.best > 1.5 * c.atCut);
const early = cuts.filter(c => c.lag <= -2 && c.best > 1.5 * c.atCut);
const weak = cuts.filter(c => c.atCut < 4 && c.best < 4);       // 平均每像素变化 <4（0–255）：切了几乎看不出

// ── 闪烁 / 跳变：不在切点附近的孤立大变化 ──
const cutT = info.shots.map(s => s.t);
const jumps = [];
for (let i = 3; i < series.length - 3; i++) {
  const s = series[i]; const nb = [...series.slice(i - 3, i), ...series.slice(i + 1, i + 4)].map(x => x.diff).sort((a, b) => a - b);
  const med = nb[3];
  if (s.diff > 8 && s.diff > 6 * Math.max(med, 0.5) && s.motion > 0.03 && !cutT.some(c => Math.abs(c - s.t) < (STEP + 2) / fps)) jumps.push(s);
}

// ── 确定性：倒序重画抽样时刻 ──
// 成串出现的跳变（间隔 <1.2s）合成一组：多半是按拍的闪白 / 换色，有意的
const jumpRuns = [];
for (const j of jumps) { const r = jumpRuns.at(-1); if (r && j.t - r.t1 < 1.2) { r.t1 = j.t; r.n++; } else jumpRuns.push({ t0: j.t, t1: j.t, n: 1, diff: j.diff, motion: j.motion }); }

const nondet = [];
for (const t of [...keepT].reverse()) if (!await page.evaluate(t => { window.__fcSample(t); return window.__fcSame(t); }, t)) nondet.push(t);

// ── 截图 ──
const groups = new Map();
// 出画只报位置基本不动的字：随镜头、随场景移进移出画面的招牌是正常的
const moved = r => Math.hypot(r.first.x0 - r.last.x0, r.first.y0 - r.last.y0) > 30;
for (const r of done.filter(r => r.t1 - r.t0 >= MIN_S - 1e-6 && !(r.type === '出画' && moved(r))).sort((a, b) => a.t0 - b.t0)) {
  const g = groups.get(r.key); if (g) g.spans.push([r.t0, r.t1]); else groups.set(r.key, { ...r, spans: [[r.t0, r.t1]] });
}
// 同一时刻成批出现的叠字（一整页字在过渡里叠在一起）合成一条
const issues = [];
for (const g of groups.values()) {
  const b = issues.find(x => x.type === g.type && x.batch !== undefined && Math.abs(x.t0 - g.t0) < 0.1 && g.spans.length === 1);
  if (b) { b.batch++; continue; }
  const peers = [...groups.values()].filter(x => x.type === g.type && x.spans.length === 1 && Math.abs(x.t0 - g.t0) < 0.1).length;
  issues.push(peers > 3 && g.spans.length === 1 ? { ...g, batch: 1, what: g.what + ` 等，同一时刻共 ${peers} 对（一整组字在过渡里叠在一起）` } : g);
}
const shotList = [
  ...issues.map(is => ({ t: (is.t0 + is.t1) / 2, boxes: is.boxes, label: `${is.type}` })),
  ...late.map(c => ({ t: c.t + c.lag / fps, boxes: [], label: `拖拍 ${c.lag} 帧` })),
  ...jumpRuns.slice(0, 8).map(j => ({ t: j.t0, boxes: [], label: j.n > 1 ? `连续跳变 ×${j.n}` : '跳变' })),
].slice(0, 24);
const shots = [];
for (const [k, s] of shotList.entries()) {
  const url = await page.evaluate(({ t, boxes, label }) => {
    window.render(t);
    const c = document.createElement('canvas'); const src = document.querySelector('canvas');
    c.width = src.width; c.height = src.height; const x = c.getContext('2d'); x.drawImage(src, 0, 0);
    x.lineWidth = 5; x.strokeStyle = '#ff2020';
    for (const b of boxes) x.strokeRect(b.x0 - 6, b.y0 - 6, b.x1 - b.x0 + 12, b.y1 - b.y0 + 12);
    x.font = '600 40px "PingFang SC"'; x.fillStyle = 'rgba(0,0,0,.7)'; x.fillRect(0, 0, x.measureText(label).width + 30, 60);
    x.fillStyle = '#ff5050'; x.textBaseline = 'middle'; x.fillText(label, 15, 30);
    return c.toDataURL('image/jpeg', 0.85);
  }, { t: s.t, boxes: s.boxes.map(({ x0, y0, x1, y1 }) => ({ x0, y0, x1, y1 })), label: `#${k + 1} ${s.label} ${fmt(s.t)}` });
  const f = path.join(qa, `fc_${String(k + 1).padStart(2, '0')}.jpg`);
  fs.writeFileSync(f, Buffer.from(url.split(',')[1], 'base64')); shots.push(f);
}
await browser.close();
for (const f of fs.readdirSync(qa)) if (/^fc_\d+\.jpg$/.test(f) && !shots.includes(path.join(qa, f))) fs.rmSync(path.join(qa, f));
const sheet = path.join(qa, 'framecheck.jpg');
if (shots.length) {
  const cols = Math.min(3, shots.length), rows = Math.ceil(shots.length / cols), w = W > H ? 640 : 360, n = cols * rows;
  const inputs = shots.flatMap(f => ['-i', f]);
  const pad = Array.from({ length: n - shots.length }, () => ['-f', 'lavfi', '-i', `color=black:s=${W}x${H}`]).flat();
  const filter = Array.from({ length: n }, (_, i) => `[${i}:v]scale=${w}:-2[v${i}];`).join('') + Array.from({ length: n }, (_, i) => `[v${i}]`).join('') +
    `xstack=inputs=${n}:layout=` + Array.from({ length: n }, (_, i) => `${i % cols ? Array(i % cols).fill('w0').join('+') : 0}_${Math.floor(i / cols) ? Array(Math.floor(i / cols)).fill('h0').join('+') : 0}`).join('|');
  await new Promise(r => spawn('ffmpeg', ['-y', '-loglevel', 'error', '-nostdin', ...inputs, ...pad, '-filter_complex', filter + '[o]', '-map', '[o]', '-frames:v', '1', sheet]).on('close', r));
} else if (fs.existsSync(sheet)) fs.rmSync(sheet);

// ── 报告（编号和截图拼图一致）──
let no = 0; const num = () => (++no <= shotList.length ? `#${no} ` : '');
const L = [`# 框景检查 ${path.basename(dir)}`, '', `${fmt(dur)}，每 ${STEP} 帧取一帧；硬切镜头 ${cuts.length} 个逐帧量卡点。截图：build/qa/framecheck.jpg（#编号对应）。`, ''];
if (errors.length) L.push('## ❌ 页面报错', ...[...new Set(errors)].slice(0, 10).map(e => '- ' + e), ...(errors.length > 10 ? [`- …共 ${errors.length} 条`] : []), '');
if (nondet.length) L.push('## ❌ 同一时刻两次画得不一样', `抽查 ${keepT.length} 个时刻，${nondet.length} 个不一致：${nondet.map(fmt).join('、')}。查 Math.random、Date.now、保留上一帧状态的代码；并行渲染时接缝会跳。`, '');
L.push(`## ⚠️ 文字 ${issues.length} 处`);
issues.forEach(r => L.push(`- ${num()}${r.spans.slice(0, 4).map(([a, b]) => `${fmt(a)}–${fmt(b)}`).join('、')}${r.spans.length > 4 ? ` 等 ${r.spans.length} 处` : ''} ${r.type}：${r.what}`));
L.push('', `## ⚠️ 卡点：拖拍 ${late.length}、抢拍 ${early.length}、切了看不出 ${weak.length}`);
late.forEach(c => L.push(`- ${num()}镜头 ${c.k}（${fmt(c.t)}）画面最大变化晚了 ${c.lag} 帧（${(c.lag / fps * 1000).toFixed(0)}ms）：新镜头开头是不是先黑、先淡入？揭开的那一帧要落在拍点上`));
early.forEach(c => L.push(`- 镜头 ${c.k}（${fmt(c.t)}）最大变化早了 ${-c.lag} 帧：上一个镜头末尾就开始大变`));
weak.forEach(c => L.push(`- 镜头 ${c.k}（${fmt(c.t)}）切点前后画面几乎一样（平均变化 ${c.atCut.toFixed(1)}）：是故意的匹配剪辑就放过`));
L.push('', `## 提示：不在切点上的跳变 ${jumpRuns.length} 组`);
jumpRuns.slice(0, 12).forEach(j => L.push(`- ${num()}${j.n > 1 ? `${fmt(j.t0)}–${fmt(j.t1)} 连续 ${j.n} 个（成串出现，多半是按拍的闪白、换色）` : `${fmt(j.t0)}（覆盖 ${(j.motion * 100).toFixed(0)}% 画面）`}`));
L.push('', `## 提示：画面静止 ≥${STATIC_S}s ${statics.length} 处`);
statics.forEach(s => L.push(`- ${fmt(s.t0)}–${fmt(s.t1)}（${(s.t1 - s.t0).toFixed(1)}s）`));
L.push('', '判读：都看截图确认。叠字、出画、拖拍多数要改；有意的拍点闪白、匹配剪辑、安静段落的长镜头看过就放。卡点只说明画面变化落在哪一帧，镜头本身是否切在对的拍上，仍要用户听。');
fs.writeFileSync(path.join(qa, 'framecheck.md'), L.join('\n') + '\n');
console.log(L.slice(4).join('\n'));
console.log('\n' + path.join(qa, 'framecheck.md') + (shots.length ? '\n' + sheet : ''));
process.exitCode = errors.length || nondet.length ? 1 : 0;
