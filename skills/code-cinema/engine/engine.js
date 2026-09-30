// Code Cinema 引擎：时间轴、拍点、音频特征、镜头表、歌词层、WebGL 后期。
// 片子自己的内容写在 film.js 里（window.FILM），本文件不需要改。
//
// FILM = {
//   dur, size: [1920,1080], fps: 30, audio: 'audio.wav',
//   post: { bloom, threshold, halation, ca, vignette, letterbox (0 或 2.39 这样的画幅比), grain (页面内颗粒，建议 0), tonemap (1/0), exposure },
//   （镜头可用 shot.post 覆盖；Canvas 2D 镜头默认辉光阈值 .82，着色器镜头 .35）
//   sceneFS: '...'                       // 可选：WebGL 片元着色器，镜头用 sc 选场景
//   shots: [{ t, sc, f(lt,t,G) => ({p0,p1,p2,p3}), draw(ctx,lt,t,G), xf, xfType: 'fade'|'burn', xfOrigin: [u,v], flash, post }],
//   globals(t) => G,                     // 全局状态：G.post 可以按时间覆盖后期参数
//   lyrics: [[start, end, text, mode]],  // mode: sub | v-r | v-l | big | bigTop | card | none
//   lyricStyle: { font, weight, size, color, shadow },
//   drawText(tx, t, G, api) => bool,     // 可选：自定义字层；返回 true 则跳过默认歌词
// }
(() => {
const F = window.FILM;
const [W, H] = F.size || [1920, 1080];
const FPS = F.fps || 30;
const DUR = F.dur;
const A = window.AUDIO || { beats: [] };

// ───────── 工具 ─────────
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, u) => a + (b - a) * u;
const seg = (t, a, b) => clamp((t - a) / (b - a));
const sm = u => { u = clamp(u); return u * u * (3 - 2 * u); };
const ss = (t, a, b) => sm(seg(t, a, b));
const ease = u => { u = clamp(u); return u < .5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2; };
const easeOut = u => 1 - Math.pow(1 - clamp(u), 3);
const hash = n => { n = Math.sin(n * 127.1 + 311.7) * 43758.5453; return n - Math.floor(n); };
const rng = seed => () => { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; };
const snap = t => { let best = t, bd = 1e9; for (const b of A.beats) { const d = Math.abs(b - t); if (d < bd) { bd = d; best = b; } } return best; };
const beatsIn = (a, b) => A.beats.filter(x => x >= a && x < b);
const beatPhase = t => { let prev = -1e9, next = 1e9; for (const b of A.beats) { if (b <= t) prev = b; else { next = b; break; } } return next < 1e9 && prev > -1e9 ? (t - prev) / (next - prev) : 0; };
const lastBeat = t => { let p = -1e9; for (const b of A.beats) { if (b <= t) p = b; else break; } return p; };
const au = (k, t) => A[k] ? A[k][clamp(Math.floor(t * FPS), 0, A[k].length - 1)] : 0;
const api = { W, H, FPS, DUR, clamp, lerp, seg, sm, ss, ease, easeOut, hash, rng, snap, beatsIn, beatPhase, lastBeat, au };
window.CINEMA = api;

// 镜头的起点吸附到拍点（shot.nosnap 可关闭）
F.shots.forEach(s => { if (s.t > 0 && !s.nosnap && A.beats.length) s.t = snap(s.t); });
const post0 = Object.assign({ bloom: 1, halation: 1, ca: 1, vignette: .6, letterbox: 0, grain: 0, tonemap: 1, exposure: 1 }, F.post || {});
const LB = post0.letterbox ? Math.round((H - W / post0.letterbox) / 2) : 0;
api.BAR = LB;

// ───────── 字层 ─────────
const tc = document.createElement('canvas'); tc.width = W; tc.height = H;
const tx = tc.getContext('2d');
const LS = Object.assign({ font: '"Songti SC", "STSong", serif', weight: 300, size: 40, color: '240,233,218', shadow: 'rgba(0,0,0,0.55)' }, F.lyricStyle || {});

function drawLyrics(t) {
  const L = F.lyrics || [];
  for (let i = 0; i < L.length; i++) {
    const [a, b, s, mode = 'sub'] = L[i];
    if (mode === 'none') continue;
    const next = L[i + 1] ? L[i + 1][0] : 1e9;
    const big = mode.startsWith('big') || mode === 'card';
    const outEnd = Math.min(b + (big ? .9 : .7), next - .05), outStart = outEnd - .45;
    if (t < a - .05 || t > outEnd) continue;
    const fade = 1 - sm(seg(t, outStart, outEnd));
    const chars = [...s];
    const n = Math.max(1, chars.filter(c => !'，, '.includes(c)).length);
    const step = Math.min(.16, (b - a) * .6 / n);
    let k = 0;
    const alphaOf = () => { const v = sm(seg(t, a + k * step, a + k * step + .45)) * fade; k++; return v; };
    tx.textAlign = 'center'; tx.textBaseline = 'middle';
    tx.shadowColor = LS.shadow; tx.shadowBlur = big ? 28 : 12;
    if (mode === 'card') { tx.shadowBlur = 0; tx.fillStyle = `rgba(0,0,0,${fade})`; tx.fillRect(0, 0, W, H); }
    if (big) {
      const size = mode === 'card' ? LS.size * 2.6 : LS.size * 2.1;
      tx.font = `${LS.weight} ${size}px ${LS.font}`;
      const sp = size * .3, ws = chars.map(c => tx.measureText(c).width + sp);
      const yy = mode === 'bigTop' ? LB + 110 : H / 2;
      let x = W / 2 - ws.reduce((p, q) => p + q, 0) / 2;
      for (let j = 0; j < chars.length; j++) {
        if (!'，,'.includes(chars[j])) { const al = alphaOf(); tx.fillStyle = `rgba(${LS.color},${al})`; tx.fillText(chars[j], x + ws[j] / 2, yy + (1 - al) * 6); }
        x += ws[j];
      }
    } else if (mode === 'v-r' || mode === 'v-l') {
      const cols = s.split(/[，,]/);
      const pitch = LS.size * 1.4, colGap = LS.size * 1.6;
      const x0 = mode === 'v-r' ? W - 250 : 250 + (cols.length - 1) * colGap;
      tx.font = `${LS.weight} ${LS.size}px ${LS.font}`;
      cols.forEach((col, ci) => {
        const x = x0 - ci * colGap, y0 = LB + 110 + ci * pitch * 1.5;
        [...col].forEach((c, j) => { const al = alphaOf(); tx.fillStyle = `rgba(${LS.color},${al * .95})`; tx.fillText(c, x, y0 + j * pitch + (1 - al) * 5); });
      });
    } else {
      tx.font = `${LS.weight} ${LS.size}px ${LS.font}`;
      const ws = chars.map(c => tx.measureText(c).width + 4);
      let x = W / 2 - ws.reduce((p, q) => p + q, 0) / 2;
      const yy = LB ? H - LB / 2 : H - 90;
      for (let j = 0; j < chars.length; j++) { const al = alphaOf(); tx.fillStyle = `rgba(${LS.color},${al})`; tx.fillText(chars[j], x + ws[j] / 2, yy + (1 - al) * 4); x += ws[j]; }
    }
    tx.shadowBlur = 0;
  }
}

// ───────── WebGL ─────────
const canvas = document.getElementById('c');
canvas.width = W; canvas.height = H;
const gl = canvas.getContext('webgl2', { preserveDrawingBuffer: true, antialias: false });
gl.getExtension('EXT_color_buffer_float');
const VS = `#version 300 es
in vec2 aP; void main(){ gl_Position = vec4(aP, 0., 1.); }`;
function prog(fs) {
  const mk = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s)); return s; };
  const p = gl.createProgram(); gl.attachShader(p, mk(gl.VERTEX_SHADER, VS)); gl.attachShader(p, mk(gl.FRAGMENT_SHADER, fs));
  gl.bindAttribLocation(p, 0, 'aP'); gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
  const u = {}; const n = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS);
  for (let i = 0; i < n; i++) { const name = gl.getActiveUniform(p, i).name.replace('[0]', ''); u[name] = gl.getUniformLocation(p, name); }
  return { p, u };
}
const POST_FS = `#version 300 es
precision highp float;
uniform vec2 uRes;
uniform sampler2D uA, uB, uText;
uniform float uMix, uT, uSeed, uFade, uFlash, uTextWob, uExposure, uBloom, uHal, uCA, uVig, uBar, uGrain, uTonemap, uThr;
uniform vec3 uTint, uFlashCol;
uniform float uXf; uniform vec2 uXfO;
out vec4 outColor;
float h11(float p){ p=fract(p*.1031); p*=p+33.33; p*=p+p; return fract(p); }
float h21(vec2 p){ vec3 p3=fract(vec3(p.xyx)*.1031); p3+=dot(p3,p3.yzx+33.33); return fract((p3.x+p3.y)*p3.z); }
float vn2(vec2 p){ vec2 i=floor(p), f=fract(p); vec2 u=f*f*(3.-2.*f);
  return mix(mix(h21(i),h21(i+vec2(1,0)),u.x), mix(h21(i+vec2(0,1)),h21(i+vec2(1,1)),u.x), u.y); }
float fbm2(vec2 p){ float s=0., a=.5; for(int i=0;i<5;i++){ s+=a*vn2(p); p=p*2.03+vec2(1.7,9.2); a*=.5; } return s; }
vec3 tapA(vec2 uv){ vec2 c=uv-.5; float ca=.0022*uCA; return vec3(texture(uA,uv-c*ca).r, texture(uA,uv).g, texture(uA,uv+c*ca).b); }
vec3 tapB(vec2 uv){ vec2 c=uv-.5; float ca=.0022*uCA; return vec3(texture(uB,uv-c*ca).r, texture(uB,uv).g, texture(uB,uv+c*ca).b); }
void main(){
  vec2 uv = gl_FragCoord.xy / uRes;
  float asp = uRes.x / uRes.y;
  vec3 col = tapA(uv);
  vec3 fire = vec3(0);
  if (uMix > 0.) {
    if (uXf < .5) col = mix(col, tapB(uv), uMix);
    else {   // 烧纸：上一个镜头是正在烧掉的纸，火线从 uXfO 向外推进
      vec2 q = (uv - uXfO) * vec2(asp, 1.);
      float n = length(q) * .75 + (fbm2(uv * vec2(asp, 1.) * 4.) - .5) * .45 + (fbm2(uv * vec2(asp, 1.) * 18.) - .5) * .08;
      float prog = (1. - uMix) * 1.55 - .1;
      float e = n - prog, w = .035;
      vec3 b = tapB(uv);
      b *= mix(vec3(.45,.3,.2), vec3(1.), smoothstep(w, w*4., e));          // 火线前方的焦黄
      vec3 edge = mix(vec3(4.,1.6,.35), vec3(.02,.015,.01), smoothstep(0., w, e)); // 火边 → 炭黑
      col = e < 0. ? col : (e < w ? edge : b);
      fire = vec3(1.,.45,.12) * exp(-abs(e) * 45.) * .9;
    }
  }
  vec3 glow = vec3(0);
  for (int i=2;i<8;i++){
    float lod = float(i);
    vec3 g = textureLod(uA, uv, lod).rgb;
    if (uMix > 0.) g = mix(g, textureLod(uB, uv, lod).rgb, uMix);
    glow += max(g - uThr, 0.) / (1. + lod*.35);
  }
  glow /= 4.;
  col += glow * (vec3(1., .55, .36) * 1.1 * uHal + .35) * uBloom;
  col += fire;
  col *= uExposure * uTint;
  if (uTonemap > .5) col = (col*(2.51*col + .03)) / (col*(2.43*col + .59) + .14);
  float l = dot(col, vec3(.299, .587, .114));
  vec2 vc = uv - .5; vc.x *= asp;
  col *= 1. - smoothstep(.45, 1.15, length(vc)) * uVig;
  if (uGrain > 0.) { vec2 gc = floor(gl_FragCoord.xy / 1.5); col += (h21(gc + uSeed*113.) + h21(gc*1.7 - uSeed*71.) - 1.) * uGrain * (1. - l*.6); }
  col = mix(col, uFlashCol, uFlash);
  if (uv.y < uBar || uv.y > 1. - uBar) col = vec3(0);
  vec2 tuv = uv + uTextWob * vec2(sin(uv.y*38. + uT*2.), cos(uv.x*26. + uT*1.6)) * .0018;
  tuv.y = 1. - tuv.y;
  vec4 tx = texture(uText, tuv);
  col = col*(1. - tx.a) + tx.rgb;
  col *= uFade;
  outColor = vec4(col, 1.);
}`;
const PP = prog(POST_FS);
const SP = F.sceneFS ? prog(F.sceneFS) : null;
const vb = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, vb);
gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
const LEVELS = Math.floor(Math.log2(Math.max(W, H))) + 1;
function texParams() {
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
}
function target() {
  const tex = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, tex); gl.texStorage2D(gl.TEXTURE_2D, LEVELS, gl.RGBA16F, W, H); texParams();
  const fb = gl.createFramebuffer(); gl.bindFramebuffer(gl.FRAMEBUFFER, fb);
  gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);
  const tex2 = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, tex2); texParams();
  const cv = document.createElement('canvas'); cv.width = W; cv.height = H;
  return { tex, fb, tex2, cv, ctx: cv.getContext('2d') };
}
const TA = target(), TB = target();
const textTex = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, textTex); texParams();
gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);   // 字层没有 mipmap

function drawShot(sh, t, T, G) {
  const lt = t - sh.t;
  if (sh.draw) {                       // Canvas 2D 镜头
    const c = T.ctx;
    c.setTransform(1, 0, 0, 1, 0, 0); c.globalAlpha = 1; c.globalCompositeOperation = 'source-over'; c.filter = 'none';
    c.clearRect(0, 0, W, H);
    sh.draw(c, lt, t, G);
    gl.bindTexture(gl.TEXTURE_2D, T.tex2);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, T.cv);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
    gl.generateMipmap(gl.TEXTURE_2D);
    return T.tex2;
  }
  const P = sh.f ? sh.f(lt, t, G) : {};
  gl.bindFramebuffer(gl.FRAMEBUFFER, T.fb); gl.viewport(0, 0, W, H);
  gl.useProgram(SP.p);
  const u = SP.u, v4 = a => { a = a || []; return [a[0] || 0, a[1] || 0, a[2] || 0, a[3] || 0]; };
  const set = (n, fn, ...v) => { if (u[n] !== undefined && u[n] !== null) gl[fn](u[n], ...v); };
  set('uRes', 'uniform2f', W, H); set('uT', 'uniform1f', t); set('uLT', 'uniform1f', lt); set('uScene', 'uniform1i', sh.sc || 0);
  for (const k of ['p0', 'p1', 'p2', 'p3']) set('uP' + k[1], 'uniform4fv', v4(P[k]));
  set('uA', 'uniform4f', au('rms', t), au('low', t), au('high', t), au('onset', t));
  if (G.uniforms) for (const [n, v] of Object.entries(G.uniforms)) {
    if (typeof v === 'number') set(n, 'uniform1f', v); else set(n, 'uniform' + v.length + 'fv', v);
  }
  gl.drawArrays(gl.TRIANGLES, 0, 3);
  gl.bindTexture(gl.TEXTURE_2D, T.tex); gl.generateMipmap(gl.TEXTURE_2D);
  return T.tex;
}

function render(t) {
  t = clamp(t, 0, DUR);
  const G = F.globals ? F.globals(t) : {};
  const shots = F.shots;
  let i = 0; while (i < shots.length - 1 && t >= shots[i + 1].t) i++;
  const sh = shots[i];
  const texA = drawShot(sh, t, TA, G);
  let mix = 0, texB = texA;
  if (sh.xf && i > 0 && t < sh.t + sh.xf) { texB = drawShot(shots[i - 1], t, TB, G); mix = 1 - sm((t - sh.t) / sh.xf); }
  tx.clearRect(0, 0, W, H);
  if (!(F.drawText && F.drawText(tx, t, G, api))) drawLyrics(t);
  gl.bindTexture(gl.TEXTURE_2D, textTex);
  gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, tc);
  gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
  gl.bindFramebuffer(gl.FRAMEBUFFER, null); gl.viewport(0, 0, W, H);
  gl.useProgram(PP.p);
  const u = PP.u, P = Object.assign({}, post0, sh.post || {}, G.post || {});
  gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, texA); gl.uniform1i(u.uA, 0);
  gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, texB); gl.uniform1i(u.uB, 1);
  gl.activeTexture(gl.TEXTURE2); gl.bindTexture(gl.TEXTURE_2D, textTex); gl.uniform1i(u.uText, 2);
  gl.activeTexture(gl.TEXTURE0);
  const flash = sh.flash ? Math.exp(-(t - sh.t) * 9) * .55 * sh.flash : 0;
  const f1 = (n, v) => u[n] && gl.uniform1f(u[n], v);
  gl.uniform2f(u.uRes, W, H);
  f1('uMix', mix); f1('uT', t); f1('uSeed', Math.round(t * FPS) % 997);
  f1('uFade', (G.fade ?? 1) * seg(t, 0, .25) * (1 - seg(t, DUR - 2, DUR)));
  f1('uFlash', Math.max(flash, G.flash || 0)); f1('uTextWob', G.textWob || 0);
  f1('uExposure', P.exposure); f1('uBloom', P.bloom); f1('uHal', P.halation); f1('uCA', P.ca); f1('uVig', P.vignette);
  f1('uThr', P.threshold ?? (sh.draw ? .82 : .35)); f1('uBar', LB / H); f1('uGrain', P.grain); f1('uTonemap', P.tonemap);
  gl.uniform3fv(u.uTint, G.tint || [1, 1, 1]);
  f1('uXf', sh.xfType === 'burn' ? 1 : 0); gl.uniform2fv(u.uXfO, sh.xfOrigin || [.5, .5]); gl.uniform3fv(u.uFlashCol, G.flashCol || [1, .97, .92]);
  gl.drawArrays(gl.TRIANGLES, 0, 3);
}

window.DUR = DUR;
window.render = render;
window.renderFrame = t => { render(t); return canvas.toDataURL('image/jpeg', .93); };
window.READY = Promise.all((F.fonts || []).map(f => document.fonts.load(f))).then(() => document.fonts.ready).then(() => true);  // FILM.fonts: ['40px "MyFont"']
})();
