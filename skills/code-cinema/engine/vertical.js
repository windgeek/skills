// 竖版包装：把横版片子的一段装进 1080×1920。
// 用法：在 vertical.html 里先加载横版的全部脚本，再设 window.VCFG，最后加载本文件。
// VCFG = {
//   from, to,                         // 横版里的时间段（秒）
//   hook: ['第一行', '第二行'],        // 顶部钩子标题（前 3 秒最重要）
//   tag: '歌手《歌名》',               // 钩子下面的小字
//   subs: [[a, b, '主字幕', '副字幕'?]], // 横版时间轴上的字幕（大字，放在画面下方）
//   end: { text: ['完整音源', '在某某平台搜索 你的账号名'], dur: 2.6 },
//   hideFilmText: false,              // true：不画横版自己的字层
//   font, subFont, color, accent,
// }
// 布局：顶部 150px 和底部 28% 留给平台界面；画面在中间，背景是同一帧放大模糊。
(() => {
const V = window.VCFG, OW = 1080, OH = 1920;
const src = document.getElementById('c');
const out = document.createElement('canvas'); out.width = OW; out.height = OH;
document.body.appendChild(out); src.style.display = 'none';
out.style.cssText = 'height:100vh;display:block;margin:auto';
const o = out.getContext('2d');
if (V.hideFilmText) FILM.drawText = () => true;
const PIC_Y = 600, PIC_H = Math.round(OW * 9 / 16);
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const sm = u => { u = clamp(u); return u * u * (3 - 2 * u); };
const seg = (t, a, b) => clamp((t - a) / (b - a));
const FONT = V.font || '"Songti SC", serif', SUB = V.subFont || FONT, COL = V.color || '#fff6e0', ACC = V.accent || '#ffd24a';

function text(s, x, y, size, col, font, a = 1, stroke = .16) {
  o.save(); o.globalAlpha = a; o.font = `${size}px ${font}`; o.textAlign = 'center'; o.textBaseline = 'middle';
  let sz = size; while (o.measureText(s).width > OW - 90 && sz > 20) { sz -= 2; o.font = `${sz}px ${font}`; }
  o.lineJoin = 'round'; o.lineWidth = sz * stroke; o.strokeStyle = 'rgba(0,0,0,0.85)'; o.strokeText(s, x, y);
  o.fillStyle = col; o.fillText(s, x, y); o.restore();
}

function compose(tl) {       // tl = 竖版里的时间
  const t = V.from + tl;
  window.render(t);
  o.save();
  o.filter = 'blur(28px) brightness(0.42) saturate(1.2)';
  const s = OH / src.height * 1.08; o.drawImage(src, OW / 2 - src.width * s / 2, OH / 2 - src.height * s / 2, src.width * s, src.height * s);
  o.restore(); o.filter = 'none';
  o.fillStyle = 'rgba(0,0,0,0.25)'; o.fillRect(0, 0, OW, OH);
  o.drawImage(src, 0, PIC_Y, OW, PIC_H);
  o.strokeStyle = 'rgba(255,255,255,0.12)'; o.lineWidth = 2; o.strokeRect(0, PIC_Y, OW, PIC_H);
  // 钩子标题：一开始弹一下
  const pop = 1 + .12 * Math.exp(-tl * 6);
  (V.hook || []).forEach((line, i) => { o.save(); o.translate(OW / 2, 300 + i * 118); o.scale(pop, pop); text(line, 0, 0, 96, i ? ACC : COL, FONT, 1, .14); o.restore(); });
  if (V.tag) text(V.tag, OW / 2, 300 + (V.hook || []).length * 118 + 10, 40, 'rgba(255,246,224,0.85)', SUB, 1, .12);
  // 字幕
  for (const [a, b, main, sub] of V.subs || []) {
    if (t < a - .05 || t > b + .35) continue;
    const al = sm(seg(t, a, a + .15)) * (1 - sm(seg(t, b + .05, b + .35)));
    if (sub) { text(sub, OW / 2, PIC_Y + PIC_H + 70, 40, 'rgba(255,246,224,0.8)', SUB, al, .12); text(main, OW / 2, PIC_Y + PIC_H + 150, 64, COL, FONT, al); }
    else text(main, OW / 2, PIC_Y + PIC_H + 110, 66, COL, FONT, al);
  }
  // 结尾引导
  if (V.end) { const d = V.to - V.from, a = sm(seg(tl, d - V.end.dur, d - V.end.dur + .4));
    if (a > 0) { o.fillStyle = `rgba(0,0,0,${.55 * a})`; o.fillRect(0, PIC_Y, OW, PIC_H); V.end.text.forEach((s, i) => text(s, OW / 2, PIC_Y + PIC_H / 2 - 40 + i * 90, i ? 60 : 44, i ? ACC : COL, i ? FONT : SUB, a)); } }
}
window.DUR = V.to - V.from;
window.OUT_SIZE = [OW, OH];
window.AUDIO_OFFSET = V.from;
window.renderFrame = t => { compose(t); return out.toDataURL('image/jpeg', .93); };
window.renderVertical = compose;
})();
