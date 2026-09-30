// node render.mjs                         → build/<name>.mp4（发布版）+ build/master.mp4（母版）
// node render.mjs --stills 5,42,110       → build/still_*.jpg
// node render.mjs --from 40 --to 60       → build/preview.mp4
// node render.mjs --page vertical.html --name 片名_竖版   → 竖版切片（见 vertical.js）
// 可选：--workers 8  --grain 3（ffmpeg 颗粒强度，0 关闭）  --name 片名  --crf 22
import puppeteer from 'puppeteer-core';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

const dir = path.dirname(new URL(import.meta.url).pathname);
const build = path.join(dir, 'build');
const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf('--' + k); return i >= 0 ? args[i + 1] : d; };
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

async function openPage() {
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: true,
    args: ['--allow-file-access-from-files', '--force-device-scale-factor=1', '--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage();
  page.on('console', m => m.type() === 'error' && console.error('console:', m.text()));
  page.on('pageerror', e => { console.error('PAGE ERROR', e.message); process.exit(1); });
  await page.goto('file://' + path.join(dir, opt('page', 'index.html')) + '?render', { waitUntil: 'load' });
  const [w, h] = await page.evaluate(() => window.OUT_SIZE || FILM.size || [1920, 1080]);
  await page.setViewport({ width: w, height: h });
  await page.evaluate(() => window.READY);
  const info = await page.evaluate(() => ({ dur: DUR, fps: FILM.fps || 30, audio: FILM.audio, offset: window.AUDIO_OFFSET || 0 }));
  const grab = t => page.evaluate(t => window.renderFrame(t), t).then(d => Buffer.from(d.split(',')[1], 'base64'));
  return { browser, grab, ...info };
}
const run = (cmd, a) => new Promise((res, rej) => spawn(cmd, a, { stdio: 'inherit' }).on('close', c => c ? rej(new Error(cmd + ' failed')) : res()));

async function renderRange(f0, f1, fps, out, label) {
  const { browser, grab } = await openPage();
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-nostdin', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-preset', 'fast', '-crf', '14', '-pix_fmt', 'yuv420p', out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const t0 = Date.now();
  for (let f = f0; f < f1; f++) {
    const buf = await grab(f / fps);
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if ((f - f0) % 300 === 0) console.log(`[${label}] ${f - f0}/${f1 - f0}  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on('close', r));
  await browser.close();
}

fs.mkdirSync(build, { recursive: true });
if (opt('stills')) {
  const { browser, grab } = await openPage();
  for (const t of opt('stills').split(',').map(Number)) {
    const f = path.join(build, `still_${String(t).replace('.', '_')}.jpg`);
    fs.writeFileSync(f, await grab(t)); console.log(f);
  }
  await browser.close();
} else {
  const { browser, dur, fps, audio, offset } = await openPage(); await browser.close();
  const from = Number(opt('from', 0)), to = Math.min(Number(opt('to', dur)), dur);
  const F0 = Math.round(from * fps), F1 = Math.round(to * fps);
  const N = Number(opt('workers', Math.max(2, Math.min(8, os.cpus().length - 2))));
  const parts = [];
  for (let i = 0; i < N; i++) parts.push({ a: F0 + Math.round((F1 - F0) * i / N), b: F0 + Math.round((F1 - F0) * (i + 1) / N), out: path.join(build, `part${i}.mp4`) });
  const t0 = Date.now();
  await Promise.all(parts.map((p, i) => renderRange(p.a, p.b, fps, p.out, 'w' + i)));
  fs.writeFileSync(path.join(build, 'parts.txt'), parts.map(p => `file '${p.out}'`).join('\n'));
  const full = !args.includes('--from') && !args.includes('--to');
  const name = opt('name', path.basename(dir));
  const master = path.join(build, full ? `${name}_master.mp4` : 'preview_master.mp4');
  const audioPath = path.resolve(dir, audio);
  const hasAudio = audio && fs.existsSync(audioPath);
  await run('ffmpeg', ['-y', '-loglevel', 'error', '-nostdin', '-f', 'concat', '-safe', '0', '-i', path.join(build, 'parts.txt'),
    ...(hasAudio ? ['-ss', String(from + offset), '-t', String(to - from), '-i', audioPath] : []),
    '-c:v', 'copy', ...(hasAudio ? ['-c:a', 'aac', '-b:a', '256k', '-shortest'] : []),
    ...(hasAudio && offset ? ['-af', `afade=t=in:d=0.4,afade=t=out:st=${Math.max(0, to - from - 1.6)}:d=1.6`] : []), master]);
  for (const p of parts) fs.unlinkSync(p.out);
  fs.unlinkSync(path.join(build, 'parts.txt'));
  // 发布版：颗粒在这里加（不要画在页面里），再压缩
  const grain = Number(opt('grain', 3));
  const out = path.join(build, full ? `${name}.mp4` : 'preview.mp4');
  await run('ffmpeg', ['-y', '-loglevel', 'error', '-nostdin', '-i', master,
    ...(grain > 0 ? ['-vf', `noise=c0s=${grain}:allf=t`] : []),
    '-c:v', 'libx264', '-preset', 'slow', '-crf', opt('crf', '22'), '-pix_fmt', 'yuv420p',
    '-c:a', 'copy', '-movflags', '+faststart', out]);
  const mb = (fs.statSync(out).size / 1e6).toFixed(0);
  console.log(`done → ${out}  (${mb} MB, ${((Date.now() - t0) / 1000).toFixed(0)}s)`);
}
