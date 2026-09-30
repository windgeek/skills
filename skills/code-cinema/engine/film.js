// 这支片子自己的内容：场景、镜头表、全局状态、歌词。引擎见 engine.js。
// 这是模板示例：一个着色器镜头 + 一个 Canvas 2D 镜头。开工时整份替换。
(() => {
const SCENE_FS = `#version 300 es
precision highp float;
uniform vec2 uRes; uniform float uT, uLT; uniform int uScene;
uniform vec4 uP0, uP1, uP2, uP3, uA;
out vec4 outColor;
void main(){
  vec2 p = (gl_FragCoord.xy - .5*uRes) / uRes.y;
  vec3 c = vec3(.02,.03,.05);
  if (uScene == 0) {           // 示例：随低频跳动的光环
    float r = length(p);
    c += vec3(1.,.6,.3) * exp(-abs(r - .25 - uA.y*.05) * 60.) * (1. + uA.x);
  }
  outColor = vec4(c, 1.);
}`;

window.FILM = {
  dur: 12,
  size: [1920, 1080],
  fps: 30,
  audio: 'audio.wav',
  post: { bloom: 1, halation: 1, ca: 1, vignette: .6, letterbox: 2.39, grain: 0, tonemap: 1 },
  sceneFS: SCENE_FS,
  globals: t => ({}),
  shots: [
    { t: 0, sc: 0, f: (lt, t, G) => ({ p0: [lt] }) },
    { t: 6, xf: 1, post: { tonemap: 0 }, draw: (c, lt, t, G) => {   // Canvas 2D 镜头
      const { W, H } = CINEMA;
      c.fillStyle = '#e9e1cf'; c.fillRect(0, 0, W, H);
      c.fillStyle = '#b3261e'; c.beginPath(); c.arc(W / 2, H / 2, 120 + 20 * Math.sin(lt * 3), 0, 7); c.fill();
    } },
  ],
  lyricStyle: { font: '"Songti SC", serif', size: 40, color: '240,233,218' },
  lyrics: [
    [0.5, 3, '第一句歌词', 'sub'],
    [3.2, 5.8, '竖排的，第二句', 'v-r'],
    [6.5, 10, '大字卡', 'big'],
  ],
};
})();
