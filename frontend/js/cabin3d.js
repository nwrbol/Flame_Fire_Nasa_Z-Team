// MicroFlame 3D cabin — an ILLUSTRATION. 1 scene unit = 1 metre; time in seconds.
//
// Physics (cannon-es): gravity is the vector (0, -g, 0) with g = g_ms2 from environments.json,
// stepped at a fixed 1/120 s. No animation curves, no 9.8 constant, no fall multipliers.
// Changing the environment re-applies g, wakes every body and re-places the items so they
// fall (or float off) again. Open space: g = 0, every item floats and drifts.
//
// Smoke, dust and the flame shape use the same g: hot smoke buoyancy a = g·(T/Ta − 1),
// grains fall with g, the flame's vertical stretch follows g/g_Earth. The scene computes
// no spread rate, burn time or risk. Items are decor: they do not burn and do not affect data.
import * as THREE from 'three';
import * as CANNON from '/vendor/cannon-es.js';
import { OrbitControls } from '/vendor/OrbitControls.js';
import { createPerf } from '/js/perf.js';

export const STEP = 1 / 120;
// Sunlight comes in through the porthole (from behind the back wall).
const SUN_DIR = new THREE.Vector3(-.25, .42, -.87).normalize();
const W = 4.2, H = 2.4, D = 3.2;                 // cabin (m), closed on all sides; the camera stays inside
const TOP = 0.93;                                // workbench surface height (m)
const SAMPLE = new THREE.Vector3(0, TOP + 0.001, 0.1);
const WIN = { x: -0.95, y: 1.5, r: 0.32, z: -D / 2 };   // porthole in the back wall
const SHELF_Y = [0.8, 1.3, 1.8], SHELF_X = 1.1, SHELF_Z = -D / 2 + 0.2;
const DROP = { x: 1.15, z: 1.05, h: 1.0 };       // drop test: book released with its bottom 1.00 m above the floor
// Camera limits (m, rad, deg): the camera never leaves the room.
const LIMITS = { wallMargin: .3, objectMargin: .15, minDistance: .4, maxDistance: 2.3, minPolar: Math.PI * .28, maxPolar: Math.PI * .7, fov: 60 };
const ROOM = { min: new THREE.Vector3(-W / 2 + LIMITS.wallMargin, LIMITS.wallMargin, -D / 2 + LIMITS.wallMargin),
               max: new THREE.Vector3(W / 2 - LIMITS.wallMargin, H - LIMITS.wallMargin, D / 2 - LIMITS.wallMargin) };
const CENTER = new THREE.Vector3(0, 1.2, 0);
// Smoke parcel thermodynamics (documented physical parameters, identical in every environment)
const T_AIR = 293, T_SMOKE0 = 400, TAU_COOL = 1.5, TAU_DRAG = 0.15, D_TURB = 1e-3;

// ---------- small utilities ----------
function rng(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function canvasTex(w, h, draw, srgb = true) {
  const c = document.createElement('canvas'); c.width = w; c.height = h; draw(c.getContext('2d'), w, h);
  const t = new THREE.CanvasTexture(c); if (srgb) t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; return t;
}
const MATS = new Map();
function std(color, o = {}) {
  const key = color + JSON.stringify(o);
  if (!MATS.has(key)) MATS.set(key, new THREE.MeshStandardMaterial({ color, roughness: o.r ?? .7, metalness: o.m ?? 0, ...(o.extra || {}) }));
  return MATS.get(key);
}
function part(group, geo, material, x = 0, y = 0, z = 0, rx = 0, ry = 0, rz = 0) {
  const m = new THREE.Mesh(geo, material); m.position.set(x, y, z); m.rotation.set(rx, ry, rz);
  m.castShadow = m.receiveShadow = true; group.add(m); return m;
}

// ---------- procedural textures ----------
function panelTexture(base, line) {
  return canvasTex(256, 256, (g) => {
    g.fillStyle = base; g.fillRect(0, 0, 256, 256); g.strokeStyle = line; g.lineWidth = 3; g.strokeRect(6, 6, 244, 244);
    g.fillStyle = line; [[24, 24], [232, 24], [24, 232], [232, 232]].forEach(([x, y]) => { g.beginPath(); g.arc(x, y, 5, 0, 7); g.fill(); });
  });
}
const fabricTex = () => canvasTex(256, 160, (g) => {
  g.fillStyle = '#d9cdb2'; g.fillRect(0, 0, 256, 160); g.strokeStyle = 'rgba(120,100,70,.25)';
  for (let i = 0; i < 256; i += 4) { g.beginPath(); g.moveTo(i, 0); g.lineTo(i, 160); g.stroke(); }
  for (let j = 0; j < 160; j += 4) { g.beginPath(); g.moveTo(0, j); g.lineTo(256, j); g.stroke(); }
  const r = g.createRadialGradient(128, 80, 4, 128, 80, 90); r.addColorStop(0, 'rgba(20,14,10,.95)'); r.addColorStop(.45, 'rgba(60,35,20,.7)'); r.addColorStop(1, 'rgba(60,35,20,0)');
  g.fillStyle = r; g.fillRect(0, 0, 256, 160);
});
const pagesTex = () => canvasTex(128, 64, (g) => { g.fillStyle = '#f2ede1'; g.fillRect(0, 0, 128, 64); g.strokeStyle = 'rgba(150,140,120,.45)'; for (let y = 1; y < 64; y += 3) { g.beginPath(); g.moveTo(0, y); g.lineTo(128, y); g.stroke(); } });
const discTex = () => canvasTex(64, 64, (g) => { const r = g.createRadialGradient(32, 32, 0, 32, 32, 32); r.addColorStop(0, 'rgba(255,255,255,1)'); r.addColorStop(1, 'rgba(255,255,255,0)'); g.fillStyle = r; g.fillRect(0, 0, 64, 64); }, false);
const textTex = (lines, bg, fg, w = 256, h = 128, font = 'bold 38px system-ui') => canvasTex(w, h, (g) => {
  g.fillStyle = bg; g.fillRect(0, 0, w, h); g.fillStyle = fg; g.font = font; g.textAlign = 'center'; g.textBaseline = 'middle';
  lines.forEach((l, i) => g.fillText(l, w / 2, h * (i + 1) / (lines.length + 1)));
});
const keyboardTex = () => canvasTex(256, 160, (g) => {
  g.fillStyle = '#2b2e33'; g.fillRect(0, 0, 256, 160); g.fillStyle = '#3e434b';
  for (let r = 0; r < 5; r++) for (let c = 0; c < 14; c++) g.fillRect(8 + c * 17.4, 8 + r * 17, 14.5, 14);
  g.fillRect(60, 95, 136, 14); g.fillStyle = '#353a41'; g.fillRect(88, 116, 80, 38);
});
const screenTex = (tint) => canvasTex(256, 160, (g) => {
  const gr = g.createLinearGradient(0, 0, 256, 160); gr.addColorStop(0, tint); gr.addColorStop(1, '#0b0f18');
  g.fillStyle = gr; g.fillRect(0, 0, 256, 160); g.fillStyle = 'rgba(255,255,255,.18)';
  for (let i = 0; i < 6; i++) g.fillRect(18, 20 + i * 20, 120 + (i % 3) * 30, 6);
});

const VIEWS = { earth: ['View: Earth'], moon: ['View: Moon'], mars: ['View: Mars'], space: ['View: orbit'] };
const VIEW_ID = { earth: 0, moon: 1, mars: 2, space: 3 };
// Sunlight through the porthole: hard shadows on the Moon and in orbit (no atmosphere), soft on Earth.
const LIGHT = {
  earth: { sun: '#fff3df', sunI: 2.4, radius: 7, hemiSky: '#a9c6f2', hemiGround: '#6b5d4b', hemiI: 1.15 },
  moon: { sun: '#ffffff', sunI: 3.4, radius: 1, hemiSky: '#20232a', hemiGround: '#2b2b2b', hemiI: .2 },
  mars: { sun: '#ffe0c0', sunI: 1.8, radius: 3, hemiSky: '#d39a74', hemiGround: '#5a3a2a', hemiI: .8 },
  space: { sun: '#ffffff', sunI: 3.6, radius: 1, hemiSky: '#20232a', hemiGround: '#28466e', hemiI: .22 },
};

// ---------- shaders: flame and particles ----------
const NOISE = `float hash(vec3 p){ p=fract(p*0.3183099+.1); p*=17.0; return fract(p.x*p.y*p.z*(p.x+p.y+p.z)); }
  float noise(vec3 x){ vec3 i=floor(x), f=fract(x); f=f*f*(3.0-2.0*f);
    return mix(mix(mix(hash(i),hash(i+vec3(1,0,0)),f.x),mix(hash(i+vec3(0,1,0)),hash(i+vec3(1,1,0)),f.x),f.y),
               mix(mix(hash(i+vec3(0,0,1)),hash(i+vec3(1,0,1)),f.x),mix(hash(i+vec3(0,1,1)),hash(i+vec3(1,1,1)),f.x),f.y),f.z); }`;
// uG = g / g_Earth (0 in orbit, 0.165 Moon, 0.38 Mars, 1 Earth): dome at 0 g, tall flickering flame at 1 g.
function flameMaterial() {
  return new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    uniforms: { uTime: { value: 0 }, uG: { value: 0 }, uFlow: { value: 0 }, uAlive: { value: 1 }, uSoot: { value: .5 }, uHeat: { value: .3 } },
    vertexShader: NOISE + `
      #include <common>
      #include <logdepthbuf_pars_vertex>
      uniform float uTime, uG, uFlow; varying float vH; varying vec3 vN; varying vec3 vV;
      void main(){
        vec3 p = position; float h = clamp(p.y, 0.0, 1.0); vec3 q = p;
        q.y = p.y < 0.0 ? p.y * 0.12 : p.y * (0.85 + 2.8 * uG);
        q.xz *= p.y < 0.0 ? 1.0 : mix(1.0, mix(0.9, 0.12, uG), pow(h, 1.4));
        float fl = (noise(vec3(p.xz * 1.6, uTime * 6.0)) - 0.5) * uG;
        q.xz += vec2(fl, noise(vec3(p.zx * 1.7, uTime * 5.0 + 7.0)) - 0.5) * 0.4 * h * h * uG;
        q.y *= 1.0 + (noise(vec3(0.0, uTime * 8.0, 3.0)) - 0.5) * 0.16 * uG;
        float lean = uFlow * (1.0 - 0.6 * uG);
        q.x = q.x * (1.0 + 0.8 * lean) + lean * (0.35 + 0.9 * h * h);
        vH = h; vec4 mv = modelViewMatrix * vec4(q, 1.0);
        vN = normalize(normalMatrix * normal); vV = normalize(-mv.xyz); gl_Position = projectionMatrix * mv;
        #include <logdepthbuf_vertex>
      }`,
    fragmentShader: `
      #include <logdepthbuf_pars_fragment>
      uniform float uG, uAlive, uSoot, uHeat; varying float vH; varying vec3 vN; varying vec3 vV;
      void main(){
        #include <logdepthbuf_fragment>
        float facing = clamp(abs(dot(vN, vV)), 0.0, 1.0), rim = pow(1.0 - facing, 1.7);
        // uSoot (material): methanol = clean blue dome, wax/heptane/ethylene = orange sooty core
        vec3 dome = vec3(0.32, 0.42, 1.7) * (0.25 + 1.7 * rim) * (1.0 - 0.45 * uSoot)
                  + vec3(2.3, 1.0, 0.32) * uSoot * pow(facing, 1.4) * 1.5;
        float aDome = 0.16 + 0.6 * rim + 0.45 * uSoot * facing;
        vec3 tall = mix(vec3(0.3, 0.5, 1.8), mix(vec3(2.6, 1.9, 0.9), vec3(1.9, 0.7, 0.18), smoothstep(0.55, 0.95, vH)), smoothstep(0.03, 0.25, vH));
        tall = mix(vec3(0.35, 0.5, 1.6), tall, clamp(0.25 + uSoot, 0.0, 1.0));
        float aTall = pow(facing, 1.2) * (1.0 - smoothstep(0.8, 1.0, vH)) * (0.55 + 0.45 * smoothstep(0.0, 0.2, vH));
        float k = smoothstep(0.0, 0.85, uG); vec3 col = mix(dome, tall, k); float a = mix(aDome, aTall, k) * uAlive;
        // uHeat (oxygen): lean air = dim flame, O2-rich air = bright, whiter flame
        // (kept moderate: additive blending saturates to white and would hide the material colour)
        col = mix(col, vec3(dot(col, vec3(0.33))) * vec3(1.1, 1.0, 0.9), 0.15 * uHeat) * (0.55 + 0.6 * uHeat);
        a = min(1.0, a * (0.75 + 0.35 * uHeat));
        gl_FragColor = vec4(col * a, a);
      }`,
  });
}
// Picture behind the porthole, by direction from the dome centre (cheap: no textures, no fBm).
// uView: 0 Earth (sky, clouds, horizon), 1 Moon (grey ground, black sky, stars, small Earth),
// 2 Mars (ochre ground, butterscotch sky, small Sun), 3 orbit (stars and the limb of the Earth).
function viewMaterial() {
  return new THREE.ShaderMaterial({
    side: THREE.BackSide,
    uniforms: { uView: { value: 0 }, uFade: { value: 1 }, uSun: { value: SUN_DIR.clone() }, uTime: { value: 0 } },
    vertexShader: `varying vec3 vDir; void main(){ vDir = mat3(modelMatrix) * position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: `
      uniform int uView; uniform float uFade, uTime; uniform vec3 uSun; varying vec3 vDir;
      float h2(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
      float n2(vec2 p){ vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
        return mix(mix(h2(i), h2(i + vec2(1, 0)), f.x), mix(h2(i + vec2(0, 1)), h2(i + vec2(1, 1)), f.x), f.y); }
      float f3(vec2 p){ return .55 * n2(p) + .3 * n2(p * 2.1) + .15 * n2(p * 4.3); }
      float stars(vec3 d){ vec3 q = floor(d * 260.0); float s = fract(sin(dot(q, vec3(12.9898, 78.233, 37.719))) * 43758.5453); return step(.996, s) * (.5 + .5 * fract(s * 91.0)); }
      void main(){
        vec3 d = normalize(vDir); float h = d.y, sa = acos(clamp(dot(d, normalize(uSun)), -1.0, 1.0));
        vec2 gp = d.xz / max(.02, -h);                       // ground-plane coordinates (perspective)
        vec3 c;
        if (uView == 0) {          // Earth: blue sky, clouds, hazy horizon, green fields
          c = mix(vec3(.80, .87, .93), vec3(.25, .47, .79), pow(clamp(h, 0.0, 1.0), .55));
          c = mix(c, vec3(1.0), smoothstep(.55, .8, f3(d.xz / (h + .15) * 2.0 + vec2(uTime * .01, 0.0))) * .8 * smoothstep(.02, .15, h));
          c += vec3(1.0, .95, .85) * (exp(-sa * 9.0) * .45 + smoothstep(.006, .004, sa) * 3.0);
          vec3 g = mix(vec3(.30, .42, .22), vec3(.42, .52, .30), f3(gp * 1.5));
          if (h < 0.0) c = mix(g, vec3(.66, .71, .66), exp(h * 14.0));
        } else if (uView == 1) {   // Moon: sharp horizon, black sky, stars, the Earth small in the sky
          c = vec3(stars(d));
          vec3 e = normalize(vec3(-.47, .10, -.875)); float ea = acos(clamp(dot(d, e), -1.0, 1.0));
          if (ea < .05) { vec3 n = normalize(d - e * .9); float lit = clamp(.35 + dot(n, normalize(vec3(.7, .3, .6))) * .9, 0.0, 1.0);
            c = mix(vec3(.12, .3, .65), vec3(.9), smoothstep(.55, .7, n2(d.xy * 90.0))) * lit; }
          c += vec3(1.0) * smoothstep(.006, .004, sa) * 3.0;
          float cr = f3(gp * 2.2); vec3 g = vec3(.52, .52, .50) * (.75 + .5 * cr) - vec3(.12) * smoothstep(.62, .7, n2(gp * 5.0));
          if (h < 0.0) c = mix(g, vec3(.30), exp(h * 30.0) * .6);
        } else if (uView == 2) {   // Mars: dusty butterscotch sky, small pale Sun, ochre ground with stones
          c = mix(vec3(.89, .74, .59), vec3(.72, .52, .37), pow(clamp(h, 0.0, 1.0), .6));
          c += vec3(1.0, .95, .9) * (exp(-sa * 14.0) * .3 + smoothstep(.004, .0028, sa) * 2.5);
          vec3 g = mix(vec3(.62, .34, .18), vec3(.75, .45, .26), f3(gp * 1.8)) - vec3(.2, .12, .07) * smoothstep(.7, .78, n2(gp * 7.0));
          if (h < 0.0) c = mix(g, vec3(.80, .58, .42), exp(h * 18.0));
        } else {                   // orbit: stars, the curved limb of the Earth with its blue atmosphere
          c = vec3(stars(d));
          vec3 e = normalize(vec3(-.5, -.5, -.72)); float ea = acos(clamp(dot(d, e), -1.0, 1.0)), R = .54;
          if (ea < R) { vec2 q = vec2(atan(d.x, d.z), d.y) * 6.0;
            vec3 g = mix(vec3(.04, .16, .42), vec3(.24, .34, .18), smoothstep(.55, .62, f3(q)));
            g = mix(g, vec3(.95), smoothstep(.55, .75, f3(q * 1.7 + 3.0)) * .8);
            c = g * (.35 + .65 * smoothstep(R, R * .55, ea)); }
          c += vec3(.35, .6, 1.0) * exp(-abs(ea - R) * 60.0) * .9;
          c += vec3(1.0) * smoothstep(.006, .004, sa) * 3.0;
        }
        gl_FragColor = vec4(c * uFade, 1.0);
      }`,
  });
}
function particleMaterial(tex) {
  return new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, uniforms: { uScale: { value: 400 }, uTex: { value: tex } },
    vertexShader: `
      #include <common>
      #include <logdepthbuf_pars_vertex>
      attribute float aSize; attribute float aAlpha; attribute vec3 aColor; uniform float uScale; varying float vA; varying vec3 vC;
      void main(){ vA = aAlpha; vC = aColor; vec4 mv = modelViewMatrix * vec4(position, 1.0);
        gl_PointSize = aSize * uScale / max(0.05, -mv.z); gl_Position = projectionMatrix * mv;
        #include <logdepthbuf_vertex>
      }`,
    fragmentShader: `
      #include <logdepthbuf_pars_fragment>
      uniform sampler2D uTex; varying float vA; varying vec3 vC;
      void main(){
        #include <logdepthbuf_fragment>
        float a = vA * texture2D(uTex, gl_PointCoord).a; if (a < 0.004) discard; gl_FragColor = vec4(vC, a); }`,
  });
}
class ParticlePool {
  constructor(scene, n, material) {
    this.n = n; this.list = []; const geo = new THREE.BufferGeometry();
    this.pos = new Float32Array(n * 3); this.size = new Float32Array(n); this.alpha = new Float32Array(n); this.col = new Float32Array(n * 3);
    geo.setAttribute('position', new THREE.BufferAttribute(this.pos, 3)); geo.setAttribute('aSize', new THREE.BufferAttribute(this.size, 1));
    geo.setAttribute('aAlpha', new THREE.BufferAttribute(this.alpha, 1)); geo.setAttribute('aColor', new THREE.BufferAttribute(this.col, 3));
    this.geo = geo; this.points = new THREE.Points(geo, material); this.points.frustumCulled = false; scene.add(this.points);
  }
  add(p) { if (this.list.length < this.n) this.list.push(p); }
  flush(alphaOf) {
    for (let i = 0; i < this.n; i++) { const p = this.list[i]; if (!p) { this.alpha[i] = 0; continue; }
      p.p.toArray(this.pos, i * 3); this.size[i] = p.size; this.alpha[i] = alphaOf(p); p.c.toArray(this.col, i * 3); }
    for (const k of ['position', 'aSize', 'aAlpha', 'aColor']) this.geo.attributes[k].needsUpdate = true;
  }
}

// ---------- items: real sizes (m) and masses (kg); colliders follow the shape ----------
// Each builder returns { group, shapes: [[CANNON.Shape, offset Vec3, quat?]], mass, friction, restitution, bottom }
// where `bottom` is the distance from the body origin down to the resting contact.
const V = (x, y, z) => new CANNON.Vec3(x, y, z);
const Q = (rx, ry, rz) => { const q = new CANNON.Quaternion(); q.setFromEuler(rx, ry, rz); return q; };
function book(w, t, d, color, title) {
  const g = new THREE.Group(), cover = std(color, { r: .55 }), pages = new THREE.MeshStandardMaterial({ map: pagesTex(), roughness: .9 });
  part(g, new THREE.BoxGeometry(w, .0025, d), cover, 0, t / 2 - .00125, 0);                 // front cover
  part(g, new THREE.BoxGeometry(w, .0025, d), cover, 0, -t / 2 + .00125, 0);                // back cover
  part(g, new THREE.BoxGeometry(.004, t, d), cover, -w / 2 + .002, 0, 0);                   // spine
  part(g, new THREE.BoxGeometry(w - .008, t - .005, d - .006), pages, .002, 0, 0);          // page block
  const label = new THREE.Mesh(new THREE.PlaneGeometry(w * .55, d * .25), new THREE.MeshStandardMaterial({ map: textTex([title], '#00000000', 'rgba(255,255,255,.85)', 256, 96, 'bold 40px system-ui'), transparent: true }));
  label.rotation.x = -Math.PI / 2; label.position.set(.01, t / 2 + .0002, -d * .18); g.add(label);
  return { group: g, shapes: [[new CANNON.Box(V(w / 2, t / 2, d / 2)), V(0, 0, 0)]], mass: 900 * w * t * d, friction: .5, restitution: .1, bottom: t / 2 };
}
function bottle() {
  const g = new THREE.Group(), y0 = -.1025;                                                // 0.5 L PET bottle, 205 mm
  const prof = [[0, 0], [.028, 0], [.033, .006], [.033, .13], [.031, .148], [.019, .172], [.0155, .182], [.0155, .19], [0, .19]].map(([x, y]) => new THREE.Vector2(x, y));
  part(g, new THREE.LatheGeometry(prof, 36), new THREE.MeshStandardMaterial({ color: '#cfe6f7', transparent: true, opacity: .42, roughness: .08 }), 0, y0, 0);
  const water = [[0, .003], [.031, .003], [.031, .14], [0, .14]].map(([x, y]) => new THREE.Vector2(x, y));
  part(g, new THREE.LatheGeometry(water, 30), new THREE.MeshStandardMaterial({ color: '#7fb5e0', transparent: true, opacity: .35, roughness: .1 }), 0, y0, 0);
  part(g, new THREE.CylinderGeometry(.0165, .0165, .016, 24), std('#2f68d8', { r: .4 }), 0, y0 + .198, 0);           // cap
  const lab = new THREE.Mesh(new THREE.CylinderGeometry(.0336, .0336, .065, 36, 1, true), new THREE.MeshStandardMaterial({ map: textTex(['WATER · 0.5 L'], '#e9f3ff', '#2f68d8', 512, 96, 'bold 44px system-ui'), roughness: .6 }));
  lab.position.set(0, y0 + .075, 0); g.add(lab);
  return { group: g, shapes: [[new CANNON.Cylinder(.033, .033, .148, 16), V(0, y0 + .074, 0)], [new CANNON.Cylinder(.0165, .0165, .058, 12), V(0, y0 + .177, 0)]], mass: .53, friction: .45, restitution: .2, bottom: -y0 };
}
function mug() {
  const g = new THREE.Group(), y0 = -.0475;                                                 // 95 mm ceramic mug
  const prof = [[0, 0], [.039, 0], [.042, .004], [.042, .095], [.038, .095], [.0375, .008], [0, .008]].map(([x, y]) => new THREE.Vector2(x, y));
  part(g, new THREE.LatheGeometry(prof, 36), std('#e7e3da', { r: .35 }), 0, y0, 0);
  part(g, new THREE.TorusGeometry(.025, .0065, 10, 20, Math.PI), std('#e7e3da', { r: .35 }), .042, y0 + .05, 0, 0, 0, -Math.PI / 2);
  part(g, new THREE.CircleGeometry(.0375, 24), std('#3b2416', { r: .2 }), 0, y0 + .07, 0, -Math.PI / 2);           // coffee
  return { group: g, shapes: [[new CANNON.Cylinder(.042, .042, .095, 16), V(0, 0, 0)], [new CANNON.Box(V(.012, .025, .006)), V(.062, .0025, 0)]], mass: .32, friction: .55, restitution: .15, bottom: .0475 };
}
function laptop() {
  const g = new THREE.Group(), alu = std('#a7acb4', { r: .35, m: .6 });                   // 13" laptop, open 105°
  part(g, new THREE.BoxGeometry(.32, .016, .22), alu, 0, 0, 0);
  const kb = new THREE.Mesh(new THREE.PlaneGeometry(.29, .19), new THREE.MeshStandardMaterial({ map: keyboardTex(), roughness: .8 }));
  kb.rotation.x = -Math.PI / 2; kb.position.set(0, .0082, .005); g.add(kb);
  const lid = new THREE.Group(); lid.position.set(0, .008, -.11); lid.rotation.x = -Math.PI * 105 / 180; g.add(lid);
  part(lid, new THREE.BoxGeometry(.32, .007, .21), alu, 0, .0035, .105);
  const scr = new THREE.Mesh(new THREE.PlaneGeometry(.29, .18), new THREE.MeshStandardMaterial({ map: screenTex('#26406e'), emissive: '#1b2b4a', emissiveIntensity: .6, roughness: .3 }));
  scr.rotation.set(Math.PI / 2, 0, 0); scr.position.set(0, -.0002, .105); lid.add(scr);   // inner face of the lid
  const a = -Math.PI * 105 / 180, dir = V(0, -Math.sin(a), Math.cos(a));
  return { group: g, shapes: [[new CANNON.Box(V(.16, .008, .11)), V(0, 0, 0)], [new CANNON.Box(V(.16, .0035, .105)), V(0, .008 + dir.y * .105, -.11 + dir.z * .105), Q(a, 0, 0)]], mass: 1.6, friction: .5, restitution: .1, bottom: .008 };
}
function tablet() {
  const g = new THREE.Group();
  part(g, new THREE.BoxGeometry(.245, .007, .17), std('#1e2126', { r: .3, m: .3 }), 0, 0, 0);
  const s = new THREE.Mesh(new THREE.PlaneGeometry(.225, .15), new THREE.MeshStandardMaterial({ map: screenTex('#2d5a4c'), emissive: '#16302a', emissiveIntensity: .5, roughness: .2 }));
  s.rotation.x = -Math.PI / 2; s.position.y = .0036; g.add(s);
  return { group: g, shapes: [[new CANNON.Box(V(.1225, .0035, .085)), V(0, 0, 0)]], mass: .47, friction: .4, restitution: .15, bottom: .0035 };
}
function docBox() {
  const g = new THREE.Group(), card = std('#b98f5a', { r: .9 });                          // archive box 400×270×320 mm
  part(g, new THREE.BoxGeometry(.4, .24, .32), card, 0, -.015, 0);
  part(g, new THREE.BoxGeometry(.41, .045, .33), std('#a97f4c', { r: .9 }), 0, .1125, 0);   // lid
  [-1, 1].forEach(s => part(g, new THREE.PlaneGeometry(.08, .025), std('#2a1d10'), s * .2005, .02, 0, 0, s * Math.PI / 2));   // hand holes
  const l = new THREE.Mesh(new THREE.PlaneGeometry(.16, .07), new THREE.MeshStandardMaterial({ map: textTex(['DOCUMENTS', 'Mission files'], '#f4f1e8', '#333', 256, 112, 'bold 30px system-ui') }));
  l.position.set(0, 0, .1605); g.add(l);
  return { group: g, shapes: [[new CANNON.Box(V(.205, .135, .165)), V(0, 0, 0)]], mass: 3, friction: .6, restitution: .05, bottom: .135 };
}
function toolbox() {
  const g = new THREE.Group(), red = std('#b3261e', { r: .45, m: .5 });                   // steel toolbox 450×210×220 mm
  part(g, new THREE.BoxGeometry(.45, .15, .22), red, 0, -.03, 0);
  part(g, new THREE.BoxGeometry(.455, .05, .225), std('#c83a2f', { r: .45, m: .5 }), 0, .072, 0);
  part(g, new THREE.BoxGeometry(.456, .006, .226), std('#2a2a2a'), 0, .046, 0);            // lid seam
  [-1, 1].forEach(s => part(g, new THREE.BoxGeometry(.03, .04, .012), std('#9aa0a8', { m: .8, r: .3 }), s * .15, .04, .115));   // latches
  const handle = new THREE.Mesh(new THREE.TorusGeometry(.09, .008, 10, 24, Math.PI), std('#222', { r: .5 }));
  handle.position.set(0, .097, 0); handle.castShadow = true; g.add(handle);
  return { group: g, shapes: [[new CANNON.Box(V(.228, .1, .113)), V(0, -.005, 0)], [new CANNON.Box(V(.09, .045, .01)), V(0, .14, 0)]], mass: 4.5, friction: .55, restitution: .05, bottom: .105 };
}
function cable() {
  const g = new THREE.Group(), pts = [];                                                   // coiled power cable
  for (let i = 0; i <= 160; i++) { const a = i / 160 * Math.PI * 6.2, r = .07 + .012 * Math.sin(i * .21); pts.push(new THREE.Vector3(Math.cos(a) * r, .006 * Math.sin(a * .5) + (i / 160) * .012, Math.sin(a) * r)); }
  pts.push(new THREE.Vector3(.12, .01, .03), new THREE.Vector3(.16, .01, .05));
  part(g, new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 260, .005, 8), std('#16181b', { r: .6 }), 0, -.006, 0);
  part(g, new THREE.BoxGeometry(.035, .02, .028), std('#202226', { r: .5 }), .175, .004, .057, 0, -.4, 0);   // plug
  const shapes = []; for (let i = 0; i < 8; i++) { const a = i / 8 * Math.PI * 2; shapes.push([new CANNON.Sphere(.014), V(Math.cos(a) * .078, 0, Math.sin(a) * .078)]); }
  return { group: g, shapes, mass: .25, friction: .8, restitution: .05, bottom: .014 };
}
function chair() {
  const g = new THREE.Group(), fab = std('#2c3442', { r: .95 }), metal = std('#8b9098', { m: .7, r: .35 });   // office chair, seat 0.47 m
  part(g, new THREE.BoxGeometry(.46, .07, .45), fab, 0, .47, 0);
  part(g, new THREE.BoxGeometry(.44, .42, .06), fab, 0, .77, -.21, -.12, 0, 0);
  part(g, new THREE.CylinderGeometry(.025, .025, .34, 16), metal, 0, .27, 0);
  for (let i = 0; i < 5; i++) { const a = i / 5 * Math.PI * 2;
    part(g, new THREE.BoxGeometry(.3, .03, .04), metal, Math.cos(a) * .15, .07, Math.sin(a) * .15, 0, -a, 0);
    part(g, new THREE.SphereGeometry(.025, 12, 8), std('#111'), Math.cos(a) * .29, .025, Math.sin(a) * .29); }
  return { group: g, shapes: [[new CANNON.Box(V(.23, .035, .225)), V(0, .47, 0)], [new CANNON.Box(V(.22, .21, .03)), V(0, .77, -.21), Q(-.12, 0, 0)],
    [new CANNON.Cylinder(.025, .025, .34, 10), V(0, .27, 0)], [new CANNON.Cylinder(.3, .3, .05, 12), V(0, .025, 0)]], mass: 7, friction: .6, restitution: .05, bottom: 0 };
}
function firstAid() {
  const g = new THREE.Group(), green = std('#1f8a4c', { r: .5 });                         // ISO 7010 first-aid colours, no emblem text
  part(g, new THREE.BoxGeometry(.3, .1, .2), green, 0, 0, 0);
  part(g, new THREE.BoxGeometry(.06, .002, .018), std('#ffffff', { r: .4 }), 0, .051, 0);
  part(g, new THREE.BoxGeometry(.018, .002, .06), std('#ffffff', { r: .4 }), 0, .051, 0);
  part(g, new THREE.BoxGeometry(.1, .012, .02), std('#155d34'), 0, .0, .105);              // handle
  return { group: g, shapes: [[new CANNON.Box(V(.15, .05, .1)), V(0, 0, 0)]], mass: 1.2, friction: .5, restitution: .1, bottom: .05 };
}

export async function initCabin(host, getState) {
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const small = innerWidth < 760 || (navigator.hardwareConcurrency || 8) <= 4 || (navigator.deviceMemory || 8) <= 4;
  const MAX_SMOKE = reduce ? 0 : small ? 220 : 650, MAX_DUST = reduce ? 0 : small ? 80 : 220, VIEW_W = small ? 768 : 1280;

  const renderer = new THREE.WebGLRenderer({ antialias: !small, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, small ? 1.5 : 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.0;
  renderer.shadowMap.enabled = !small; renderer.shadowMap.type = THREE.PCFShadowMap;      // PCF: shadow.radius controls softness
  renderer.domElement.setAttribute('role', 'img');
  renderer.domElement.setAttribute('aria-label', 'Illustration: a cabin with a porthole and a burning fabric sample; drag to orbit, scroll to zoom');
  host.append(renderer.domElement);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(LIMITS.fov, 1, 0.05, 20);   // the whole scene is the room + the window view
  // test mode (?testbg): magenta clear colour, so any pixel outside the room / window view shows up
  const TEST_BG = new URLSearchParams(location.search).has('testbg');

  // ---------- physics world ----------
  const world = new CANNON.World({ gravity: V(0, 0, 0) });
  world.broadphase = new CANNON.SAPBroadphase(world);
  world.solver.iterations = 14;
  world.defaultContactMaterial.friction = .4; world.defaultContactMaterial.restitution = .1;
  const staticMat = new CANNON.Material({ friction: .7, restitution: .5 });
  const addStatic = (shape, pos, quat) => { const b = new CANNON.Body({ mass: 0, material: staticMat }); b.addShape(shape); b.position.copy(pos); if (quat) b.quaternion.copy(quat); world.addBody(b); return b; };

  // ---------- cabin shell with a porthole ----------
  const wallTex = panelTexture('#c9ccd2', '#9ea3ad'); wallTex.wrapS = wallTex.wrapT = THREE.RepeatWrapping; wallTex.repeat.set(5, 3);
  const floorTex = panelTexture('#7d838d', '#5f646c'); floorTex.wrapS = floorTex.wrapT = THREE.RepeatWrapping; floorTex.repeat.set(5, 4);
  const wallMat = new THREE.MeshStandardMaterial({ map: wallTex, roughness: .85, side: THREE.DoubleSide });
  const plane = (w, h, m, x, y, z, rx, ry) => { const p = new THREE.Mesh(new THREE.PlaneGeometry(w, h), m); p.position.set(x, y, z); p.rotation.set(rx, ry, 0); p.receiveShadow = true; p.castShadow = true; scene.add(p); return p; };
  plane(W, D, new THREE.MeshStandardMaterial({ map: floorTex, roughness: .9, side: THREE.DoubleSide }), 0, 0, 0, -Math.PI / 2, 0);
  plane(W, D, wallMat, 0, H, 0, Math.PI / 2, 0);
  plane(D, H, wallMat, -W / 2, H / 2, 0, 0, Math.PI / 2);
  plane(D, H, wallMat, W / 2, H / 2, 0, 0, -Math.PI / 2);
  plane(W, H, wallMat, 0, H / 2, D / 2, 0, Math.PI);                          // front wall: the room is closed on all sides
  // back wall: a shape with a round hole for the porthole (UVs in metres → one panel per 0.84 × 0.8 m)
  const wallShape = new THREE.Shape(); wallShape.moveTo(-W / 2, 0); wallShape.lineTo(W / 2, 0); wallShape.lineTo(W / 2, H); wallShape.lineTo(-W / 2, H); wallShape.lineTo(-W / 2, 0);
  const hole = new THREE.Path(); hole.absarc(WIN.x, WIN.y, WIN.r, 0, Math.PI * 2, true); wallShape.holes.push(hole);
  const backTex = wallTex.clone(); backTex.repeat.set(1 / .84, 1 / .8); backTex.needsUpdate = true;
  const back = new THREE.Mesh(new THREE.ShapeGeometry(wallShape, 48), new THREE.MeshStandardMaterial({ map: backTex, roughness: .85, side: THREE.DoubleSide }));
  back.position.z = -D / 2; back.receiveShadow = back.castShadow = true; scene.add(back);
  // porthole: wall tunnel, frame ring with bolts, glass with a soft highlight
  const frameMat = std('#5b616b', { m: .7, r: .35 });
  const tunnel = new THREE.Mesh(new THREE.CylinderGeometry(WIN.r, WIN.r, .14, 48, 1, true), new THREE.MeshStandardMaterial({ color: '#6c727c', metalness: .5, roughness: .5, side: THREE.BackSide }));
  tunnel.rotation.x = Math.PI / 2; tunnel.position.set(WIN.x, WIN.y, -D / 2 - .065); tunnel.castShadow = true; scene.add(tunnel);
  const ring = new THREE.Mesh(new THREE.TorusGeometry(WIN.r + .03, .035, 16, 64), frameMat); ring.position.set(WIN.x, WIN.y, -D / 2 + .012); ring.castShadow = true; scene.add(ring);
  for (let i = 0; i < 16; i++) { const a = i / 16 * Math.PI * 2, b = new THREE.Mesh(new THREE.CylinderGeometry(.009, .009, .014, 10), std('#c7ccd3', { m: .9, r: .25 }));
    b.rotation.x = Math.PI / 2; b.position.set(WIN.x + Math.cos(a) * (WIN.r + .03), WIN.y + Math.sin(a) * (WIN.r + .03), -D / 2 + .05); scene.add(b); }
  const glass = new THREE.Mesh(new THREE.CircleGeometry(WIN.r, 48), new THREE.MeshPhysicalMaterial({ color: '#cfe3ff', transparent: true, opacity: .1, roughness: .05, metalness: 0, clearcoat: 1, depthWrite: false }));
  glass.position.set(WIN.x, WIN.y, -D / 2 - .03); scene.add(glass);
  const glint = new THREE.Mesh(new THREE.CircleGeometry(WIN.r, 48), new THREE.MeshBasicMaterial({ map: canvasTex(256, 256, (g) => { const gr = g.createLinearGradient(40, 0, 220, 256); gr.addColorStop(0, 'rgba(255,255,255,0)'); gr.addColorStop(.42, 'rgba(255,255,255,.0)'); gr.addColorStop(.5, 'rgba(255,255,255,.22)'); gr.addColorStop(.56, 'rgba(255,255,255,0)'); g.fillStyle = gr; g.fillRect(0, 0, 256, 256); }), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
  glint.position.set(WIN.x, WIN.y, -D / 2 - .028); scene.add(glint);
  // the view through the porthole: a dome (half sphere, r = 2.5 m) whose rim sits on the outer end
  // of the wall tunnel. Every ray that passes the porthole hits its inner side, so from any camera
  // position inside the room only the picture is visible, never its edge or empty space.
  const stubMat = viewMaterial();
  const stub = new THREE.Mesh(new THREE.SphereGeometry(2.5, 48, 24, 0, Math.PI * 2, 0, Math.PI / 2), stubMat);
  stub.name = 'windowView'; stub.rotation.x = -Math.PI / 2; stub.position.set(WIN.x, WIN.y, -D / 2 - .135); scene.add(stub);
  // caption under the porthole
  const capTex = {}; for (const [k, [label]] of Object.entries(VIEWS)) capTex[k] = textTex([label], 'rgba(10,12,16,.82)', '#e9edf5', 512, 72, '600 30px system-ui');
  const caption = new THREE.Mesh(new THREE.PlaneGeometry(.62, .087), new THREE.MeshBasicMaterial({ transparent: true, toneMapped: false }));
  caption.position.set(WIN.x, WIN.y - WIN.r - .11, -D / 2 + .006); scene.add(caption);

  // invisible colliders for the shell (six planes: floating items stay inside)
  addStatic(new CANNON.Plane(), V(0, 0, 0), Q(-Math.PI / 2, 0, 0));
  addStatic(new CANNON.Plane(), V(0, H, 0), Q(Math.PI / 2, 0, 0));
  addStatic(new CANNON.Plane(), V(-W / 2, 0, 0), Q(0, Math.PI / 2, 0));
  addStatic(new CANNON.Plane(), V(W / 2, 0, 0), Q(0, -Math.PI / 2, 0));
  addStatic(new CANNON.Plane(), V(0, 0, -D / 2), Q(0, 0, 0));
  addStatic(new CANNON.Plane(), V(0, 0, D / 2), Q(0, Math.PI, 0));

  const box = (w, h, d, material, x, y, z, collide = true) => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), material); m.position.set(x, y, z); m.castShadow = m.receiveShadow = true; scene.add(m);
    if (collide) addStatic(new CANNON.Box(V(w / 2, h / 2, d / 2)), V(x, y, z)); return m;
  };
  // handrails (ISS style), vent grille, shelves with brackets and a front lip, workbench
  const railMat = std('#e0b43a', { r: .5 });
  [[-.3, .55, -D / 2 + .07, 0], [-1.6, 1.1, 0, 1], [1.6, .6, 0, 1]].forEach(([x, y, z, side]) => {
    const r = new THREE.Mesh(new THREE.CylinderGeometry(.018, .018, .7, 10), railMat); r.castShadow = true;
    if (side) { r.rotation.x = Math.PI / 2; r.position.set(Math.sign(x) * (W / 2 - .07), y, z); } else { r.rotation.z = Math.PI / 2; r.position.set(x, y, z); }
    scene.add(r); });
  box(.04, .5, .8, std('#2b3038'), -W / 2 + .03, 1.25, .1, false);
  for (let i = 0; i < 6; i++) box(.05, .02, .74, std('#59606b'), -W / 2 + .06, 1.05 + i * .08, .1, false);
  const shelfMat = std('#8e949e', { m: .3, r: .5 });
  SHELF_Y.forEach(y => { box(1.6, .03, .38, shelfMat, SHELF_X, y, SHELF_Z); box(1.6, .03, .012, shelfMat, SHELF_X, y + .03, SHELF_Z + .184);
    [-.7, .7].forEach(dx => box(.02, .12, .3, std('#6a7079', { m: .5 }), SHELF_X + dx, y - .07, SHELF_Z - .02, false)); });
  box(1.4, .06, .8, std('#6d737d', { m: .3 }), 0, TOP - .03, .1);
  [[-.62, -.25], [.62, -.25], [-.62, .45], [.62, .45]].forEach(([x, z]) => box(.05, TOP - .06, .05, std('#4a4f58'), x, (TOP - .06) / 2, z));
  // decor only (fixed, no hints): fire extinguisher on a wall bracket, smoke detector on the ceiling
  const ext = new THREE.Group(); ext.position.set(-W / 2 + .1, .62, -.95); scene.add(ext);
  part(ext, new THREE.CylinderGeometry(.075, .075, .42, 24), std('#c0261c', { r: .4, m: .2 }), 0, 0, 0);
  part(ext, new THREE.SphereGeometry(.075, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2), std('#c0261c', { r: .4, m: .2 }), 0, .21, 0);
  part(ext, new THREE.CylinderGeometry(.02, .025, .05, 12), std('#2b2b2b'), 0, .3, 0);
  part(ext, new THREE.BoxGeometry(.11, .015, .03), std('#2b2b2b'), .03, .335, 0);
  part(ext, new THREE.TorusGeometry(.06, .007, 8, 20, Math.PI * 1.2), std('#1a1a1a'), .07, .2, 0, 0, Math.PI / 2, 0);
  part(ext, new THREE.BoxGeometry(.03, .08, .16), std('#5b616b', { m: .6 }), -.08, .05, 0);
  addStatic(new CANNON.Cylinder(.075, .075, .5, 12), V(-W / 2 + .1, .66, -.95));
  const det = new THREE.Group(); det.position.set(-.2, H - .015, -.5); scene.add(det);
  part(det, new THREE.CylinderGeometry(.065, .07, .03, 32), std('#f2f2ee', { r: .6 }), 0, 0, 0);
  part(det, new THREE.SphereGeometry(.004, 8, 6), new THREE.MeshStandardMaterial({ color: '#22ff66', emissive: '#22ff66', emissiveIntensity: 2 }), .04, -.016, 0);

  // burning sample: fabric sheet lying on the bench (the only thing that burns)
  const sample = new THREE.Mesh(new THREE.PlaneGeometry(.34, .21), new THREE.MeshStandardMaterial({ map: fabricTex(), roughness: 1 }));
  sample.rotation.x = -Math.PI / 2; sample.position.copy(SAMPLE); sample.receiveShadow = true; scene.add(sample);

  // ---------- items ----------
  const items = [];
  const add = (name, built, home, ry = 0) => {
    const body = new CANNON.Body({ mass: built.mass, material: new CANNON.Material({ friction: built.friction, restitution: built.restitution }),
      linearDamping: .01, angularDamping: .05, sleepSpeedLimit: .04, sleepTimeLimit: .6 });
    for (const [shape, off, q] of built.shapes) body.addShape(shape, off, q);
    world.addBody(body); scene.add(built.group);
    const it = { name, group: built.group, body, mass: built.mass, bottom: built.bottom, home: new THREE.Vector3(home[0], home[1] + built.bottom, home[2]), ry };
    items.push(it); return it;
  };
  add('book (hardcover)', book(.24, .04, .17, '#7a2e2e', 'FLAMMABILITY'), [SHELF_X - .45, SHELF_Y[0] + .015, SHELF_Z]);
  add('book (paperback)', book(.21, .025, .15, '#2e4d7a', 'FIELD NOTES'), [SHELF_X - .43, SHELF_Y[0] + .055, SHELF_Z + .01], .2);
  add('book (thin manual)', book(.28, .012, .21, '#3f6b47', 'CHECKLIST'), [SHELF_X + .2, SHELF_Y[2] + .015, SHELF_Z]);
  add('water bottle', bottle(), [SHELF_X, SHELF_Y[0] + .015, SHELF_Z]);
  add('first aid kit', firstAid(), [SHELF_X - .3, SHELF_Y[1] + .015, SHELF_Z]);
  add('cable', cable(), [SHELF_X + .4, SHELF_Y[1] + .015, SHELF_Z]);
  add('laptop', laptop(), [-.38, TOP, .2], .1);
  add('tablet', tablet(), [.42, TOP, .4], -.3);
  add('mug', mug(), [.5, TOP, -.12]);
  add('document box', docBox(), [SHELF_X + .45, 0, SHELF_Z + .02]);
  add('toolbox', toolbox(), [1.55, 0, .55], -.4);
  add('chair', chair(), [-1.1, 0, .2], -Math.PI / 2);
  const dropBook = add('drop-test book', book(.22, .03, .16, '#e2672a', 'DROP TEST'), [DROP.x, -10, DROP.z]);
  const bigItems = items.filter(it => ['chair', 'document box', 'toolbox'].includes(it.name));
  dropBook.excluded = true; dropBook.group.visible = false; world.removeBody(dropBook.body);

  // ---------- flame, lights, arrows, particles ----------
  const flameMat = flameMaterial();
  const flame = new THREE.Mesh(new THREE.SphereGeometry(1, 48, 32), flameMat); flame.position.copy(SAMPLE); flame.renderOrder = 3; scene.add(flame);
  const fireLight = new THREE.PointLight('#ffb070', 1, 0, 2); fireLight.castShadow = !small; fireLight.shadow.mapSize.set(512, 512); fireLight.shadow.bias = -.002; scene.add(fireLight);
  const hemi = new THREE.HemisphereLight('#cfd6e4', '#2b2622', .5); scene.add(hemi);
  // cabin lighting panels (same in every environment) so the interior stays readable
  const cabinLight = new THREE.PointLight('#e8eef8', 2.4, 0, 2); cabinLight.position.set(.3, H - .15, .2); scene.add(cabinLight);
  const cabinLight2 = new THREE.PointLight('#e8eef8', 1.4, 0, 2); cabinLight2.position.set(1.3, H - .15, .9); scene.add(cabinLight2);
  const sun = new THREE.DirectionalLight('#ffffff', 3); sun.castShadow = !small;
  sun.target.position.set(0, 1.1, 0); sun.position.copy(sun.target.position).addScaledVector(SUN_DIR, 30); scene.add(sun, sun.target);
  Object.assign(sun.shadow.camera, { left: -6, right: 6, top: 6, bottom: -6, near: 1, far: 70 }); sun.shadow.mapSize.set(2048, 2048); sun.shadow.bias = -.0006; sun.shadow.normalBias = .02;
  const lightNow = { ...LIGHT.space }, sunC = new THREE.Color(), hs = new THREE.Color(), hg = new THREE.Color();

  const arrows = [];
  for (let i = 0; i < 6; i++) { const a = new THREE.ArrowHelper(new THREE.Vector3(1, 0, 0), new THREE.Vector3(), .3, 0x5fd0ff, .07, .045);
    a.userData = { y: TOP + .06 + (i % 3) * .1, z: -.08 + Math.floor(i / 3) * .36, phase: i / 6 }; scene.add(a); arrows.push(a); }
  const disc = discTex();
  const smoke = new ParticlePool(scene, Math.max(1, MAX_SMOKE), particleMaterial(disc));
  const dust = new ParticlePool(scene, Math.max(1, MAX_DUST), particleMaterial(disc));
  const sootC = new THREE.Color(.42, .42, .45), vapC = new THREE.Color(.9, .92, .95), dustC = new THREE.Color(.78, .74, .66);

  // ---------- camera ----------
  const controls = new OrbitControls(camera, renderer.domElement);
  // Camera only inside the room: orbit around the room centre with OrbitControls limits, plus a
  // per-frame clamp: inside the room box shrunk by 0.3 m and out of large objects.
  controls.target.copy(CENTER);
  const VIEWPOINTS = {
    overview: { pos: [1.3, 1.65, 1.25], target: [0, 1.2, 0] },
    window: { pos: [.55, 1.45, .85], target: [WIN.x, WIN.y, WIN.z] },
    drop: { pos: [-.4, .75, 1.25], target: [DROP.x, .52, DROP.z] },
  };
  const setView = (k) => { const v = VIEWPOINTS[k] || VIEWPOINTS.overview; camera.position.set(...v.pos); controls.target.set(...v.target); controls.update(); constrain(); dirty = true; };
  controls.enableDamping = true; controls.dampingFactor = .08; controls.enablePan = false; controls.zoomSpeed = .7;
  controls.minDistance = LIMITS.minDistance; controls.maxDistance = LIMITS.maxDistance;
  controls.minPolarAngle = LIMITS.minPolar; controls.maxPolarAngle = LIMITS.maxPolar;
  // static obstacles (workbench with legs, shelves); large movable items are checked every frame
  const OBSTACLES = [new THREE.Box3(new THREE.Vector3(-.72, 0, -.32), new THREE.Vector3(.72, TOP, .52)),
    new THREE.Box3(new THREE.Vector3(SHELF_X - .82, SHELF_Y[0] - .14, SHELF_Z - .2), new THREE.Vector3(SHELF_X + .82, SHELF_Y[2] + .06, SHELF_Z + .2))];
  const _box = new THREE.Box3(), _room = new THREE.Box3(ROOM.min, ROOM.max);
  function pushOut(b) {   // move the camera out of box b (+ margin) through the nearest face
    _box.copy(b).expandByScalar(LIMITS.objectMargin); const p = camera.position;
    if (!_box.containsPoint(p)) return;
    const pen = [p.x - _box.min.x, _box.max.x - p.x, p.y - _box.min.y, _box.max.y - p.y, p.z - _box.min.z, _box.max.z - p.z];
    let k = 0; for (let i = 1; i < 6; i++) if (pen[i] < pen[k]) k = i;
    if (k === 0) p.x = _box.min.x; else if (k === 1) p.x = _box.max.x; else if (k === 2) p.y = _box.min.y;
    else if (k === 3) p.y = _box.max.y; else if (k === 4) p.z = _box.min.z; else p.z = _box.max.z;
  }
  const _ib = new THREE.Box3();
  function constrain() {
    for (const o of OBSTACLES) pushOut(o);
    for (const it of bigItems) if (it.group.visible) pushOut(_ib.setFromObject(it.group));
    _room.clampPoint(camera.position, camera.position);         // last: never closer than 0.3 m to a wall, floor or ceiling
    controls.target.clamp(ROOM.min, ROOM.max);
  }
  // Test helper: rays from the camera through points spread over the porthole. Each ray that gets
  // past the wall must end on the window view (never in empty space). ok: no such ray escapes and
  // at least one ray sees the view.
  const _rc = new THREE.Raycaster(), _pt = new THREE.Vector3(), _dir = new THREE.Vector3();
  function windowCheck() {
    scene.updateMatrixWorld(true);
    const solid = []; scene.traverse(o => { if (o.isMesh && o.visible && !(o.material.transparent)) solid.push(o); });
    let rays = 0, view = 0, escaped = 0;
    for (let k = 0; k < 25; k++) {
      const a = k * 2.399963, rr = WIN.r * .95 * Math.sqrt((k + .5) / 25);       // sunflower spread over the glass
      _pt.set(WIN.x + Math.cos(a) * rr, WIN.y + Math.sin(a) * rr, -D / 2 - .03);
      _rc.set(camera.position, _dir.copy(_pt).sub(camera.position).normalize()); _rc.near = 0; _rc.far = 100;
      const hit = _rc.intersectObjects(solid, false)[0]; rays++;
      if (!hit) { escaped++; continue; }
      if (hit.object === stub) view++;
    }
    return { ok: escaped === 0 && view > 0, rays, view, escaped };
  }
  // raw placement for tests: the limits apply on the next frame, exactly as for user input
  function setCamera(pos, target) { camera.position.set(...pos); if (target) controls.target.set(...target); dirty = true; }
  function resize() { const w = host.clientWidth, h = host.clientHeight; if (!w || !h) return; renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
    smoke.points.material.uniforms.uScale.value = dust.points.material.uniforms.uScale.value = h * .9; dirty = true; }
  let dirty = true; setView('overview');
  new ResizeObserver(resize).observe(host); resize();
  let visible = true; new IntersectionObserver(([e]) => { visible = e.isIntersecting; }).observe(host);
  controls.addEventListener('change', () => { dirty = true; });

  // ---------- environment changes: re-apply g, wake every body, re-place items ----------
  let g = 0, gEarth = 9.80665, env = null, drop = null, envFade = null, pendingEnv = null;
  let viewEnv = null;
  function applyWorld(id) {
    viewEnv = id; stubMat.uniforms.uView.value = VIEW_ID[id] ?? 0;
    if (TEST_BG) { scene.background = null; renderer.setClearColor(0xff00ff, 1); } else scene.background = new THREE.Color('#0b0d12');
  }
  const rand = rng(42);
  function placeItems(zeroG) {
    world.allowSleep = !zeroG;
    for (const it of items) {
      if (it.excluded) continue;
      const b = it.body;
      b.type = CANNON.Body.DYNAMIC; b.mass = it.mass; b.updateMassProperties();
      const lift = zeroG ? .06 + rand() * .2 : .05 + rand() * .2;   // released a little above the surface
      b.position.set(it.home.x, it.home.y + lift, it.home.z);
      b.quaternion.setFromEuler((rand() - .5) * .25, it.ry, (rand() - .5) * .25);
      b.velocity.set(0, 0, 0); b.angularVelocity.set(0, 0, 0);
      if (zeroG) {   // every item floats: very small random drift and spin; soft bounces off the walls
        const d = new THREE.Vector3().randomDirection().multiplyScalar(.006 + rand() * .014);
        b.velocity.set(d.x, d.y, d.z); b.angularVelocity.set((rand() - .5) * .2, (rand() - .5) * .2, (rand() - .5) * .2);
      }
      b.previousPosition.copy(b.position); b.interpolatedPosition.copy(b.position);
      b.wakeUp();
    }
  }
  function setEnvironment(s) {
    env = s.env; g = Math.max(0, s.g); gEarth = s.gEarth;
    world.gravity.set(0, -g, 0);
    placeItems(g === 0);
    cancelDrop();
    smoke.list.length = 0; dust.list.length = 0;
    const L = LIGHT[env] || LIGHT.earth; Object.assign(lightNow, { target: L });
    // the view through the porthole: fade the exposure down, swap, fade back up
    envFade = envFade === null ? 1 : 0; pendingEnv = env;
    if (envFade === 1) applyWorld(env);
    caption.material.map = capTex[env]; caption.material.needsUpdate = true;
    if (reduce) settle(4);
    dirty = true;
  }
  function settle(seconds) { for (let i = 0; i < seconds / STEP; i++) world.step(STEP); syncMeshes(); }
  // Simulation clock = number of fixed steps × STEP. (cannon-es world.time follows wall-clock frame
  // time in its accumulator mode and silently drops steps under load, so it is not used for timing.)
  let simTime = 0;
  world.addEventListener('postStep', () => { simTime += STEP; });

  // ---------- drop test: a book released with its bottom 1.00 m above the floor ----------
  function cancelDrop() { if (drop) { world.removeBody(dropBook.body); dropBook.group.visible = false; drop = null; } }
  function dropTest(onTick) {
    cancelDrop();
    const b = dropBook.body, half = .015;
    b.type = CANNON.Body.DYNAMIC; b.mass = dropBook.mass; b.updateMassProperties();
    b.position.set(DROP.x, DROP.h + half, DROP.z); b.quaternion.set(0, 0, 0, 1);
    b.velocity.set(0, 0, 0); b.angularVelocity.set(0, 0, 0); b.previousPosition.copy(b.position); b.interpolatedPosition.copy(b.position);
    world.addBody(b); b.wakeUp(); dropBook.group.visible = true;
    drop = { t0: simTime, prevY: DROP.h, prevT: simTime, landed: null, onTick, half, expected: g > 0 ? Math.sqrt(2 * DROP.h / g) : Infinity, h: DROP.h, g, env };
    if (reduce) { for (let i = 0; i < 6 / STEP && !drop.landed; i++) { world.step(STEP); } syncMeshes(); reportDrop(true); }
    return drop;
  }
  world.addEventListener('postStep', () => {   // registered after the clock listener, so simTime is already advanced
    if (!drop || drop.landed != null) return;
    const y = dropBook.body.position.y - drop.half, t = simTime;
    if (y <= 0.0005) {   // interpolate the crossing of the floor between the last two fixed steps
      const f = drop.prevY > 0 ? drop.prevY / (drop.prevY - y) : 0;
      drop.landed = (drop.prevT + f * (t - drop.prevT)) - drop.t0;
    }
    drop.prevY = y; drop.prevT = t;
  });
  function reportDrop(final) {
    if (!drop || !drop.onTick) return;
    const elapsed = drop.landed ?? (simTime - drop.t0);
    drop.onTick({ env: drop.env, g: drop.g, h: drop.h, elapsed, expected: drop.expected, landed: drop.landed != null, done: final || drop.landed != null || (drop.g === 0 && elapsed > 3) });
  }

  function syncMeshes() {
    for (const it of items) { if (it.excluded && !it.group.visible) continue; it.group.position.copy(it.body.position); it.group.quaternion.copy(it.body.quaternion); }
  }

  // ---------- render loop ----------
  const clock = new THREE.Clock(); let acc = 0, t = 0, alive = 1, wasOut = false, vapor = 0, dropper = 0, fpsFrames = 0, fpsT0 = performance.now(), fps = 0;
  function frame() {
    requestAnimationFrame(frame);
    const dtReal = Math.min(.25, clock.getDelta());
    const s = getState ? getState() : { env: 'space', g: 0, gEarth: 9.80665, flow: 10, soot: .5, out: false };
    if (s.env !== env || s.g !== g) setEnvironment(s);
    const key = `${s.flow}|${s.soot}|${s.out}|${s.o2}|${s.kpa}|${s.thick}`; if (key !== frame.key) { frame.key = key; dirty = true; }
    if (!visible || (reduce && !dirty)) return;
    perf.begin();
    fpsFrames++; const now = performance.now(); if (now - fpsT0 > 1000) { fps = fpsFrames * 1000 / (now - fpsT0); fpsFrames = 0; fpsT0 = now; }
    // fixed 1/120 s steps covering the real elapsed time; if a frame is very late the backlog
    // is dropped (the scene runs in slow motion) — the physics and the sim clock stay exact
    if (!reduce) {
      acc += dtReal; let n = 0;
      while (acc >= STEP && n < 30) { world.step(STEP); acc -= STEP; n++; }
      if (n === 30) acc = 0;
    }
    syncMeshes();
    if (drop && !drop.reported) { reportDrop(false); if (drop.landed != null || (drop.g === 0 && simTime - drop.t0 > 3)) drop.reported = true; }
    const dt = reduce ? 0 : dtReal; t += dt;
    const gr = g / gEarth;                                   // 0 orbit · 0.165 Moon · 0.38 Mars · 1 Earth
    const flowMS = s.flow / 100;                             // slider cm/s -> m/s (real speed)

    // light fades towards the environment's sunlight through the porthole
    const L = lightNow.target || LIGHT.space, k = reduce ? 1 : Math.min(1, dtReal * 2);
    lightNow.sunI += (L.sunI - lightNow.sunI) * k; lightNow.hemiI += (L.hemiI - lightNow.hemiI) * k;
    sun.color.lerp(sunC.set(L.sun), k); sun.intensity = lightNow.sunI; sun.shadow.radius = L.radius;
    hemi.color.lerp(hs.set(L.hemiSky), k); hemi.groundColor.lerp(hg.set(L.hemiGround), k); hemi.intensity = lightNow.hemiI;
    if (envFade < 1) {   // 0 -> 0.5: dim, swap the world, 0.5 -> 1: brighten
      const before = envFade; envFade = Math.min(1, envFade + (reduce ? 1 : dtReal / 1.0));
      if (before < .5 && envFade >= .5) applyWorld(pendingEnv);
      renderer.toneMappingExposure = .2 + .8 * Math.abs(envFade - .5) * 2;
    } else renderer.toneMappingExposure = 1;
    stubMat.uniforms.uFade.value = renderer.toneMappingExposure; stubMat.uniforms.uTime.value = t;

    // flame (decor items never burn). Qualitative illustration, not a model:
    // shape from g/g_Earth and airflow; size and brightness grow with O2; lower pressure gives a
    // larger, dimmer flame and higher pressure a sootier one; colour from the material's soot level.
    alive += ((s.out ? 0 : 1) - alive) * (reduce ? 1 : Math.min(1, dtReal * 2.5));
    if (s.out && !wasOut) vapor = 2.5; wasOut = s.out;
    const o2 = s.o2 ?? 21, kpa = Math.max(20, s.kpa ?? 101);
    const heat = Math.min(1, Math.max(0, (o2 - 12) / 28));                       // 12 % dim … 40 % hot
    const oxy = Math.min(1.7, Math.max(.55, Math.pow(o2 / 21, 1.1)));           // size factor from O2
    const pres = Math.min(1.5, Math.max(.75, Math.pow(101 / kpa, .25)));        // low pressure: bigger
    const sootE = Math.min(1, (s.soot ?? .45) * (.6 + .4 * Math.min(2, kpa / 101)) * (.75 + .5 * heat));
    // solid samples only: a thin sheet burns more vigorously than a thick slab (0.05 mm … 20 mm)
    const thin = s.solid && s.thick > 0 ? Math.min(1.35, Math.max(.7, Math.pow(.5 / s.thick, .12))) : 1;
    const R = (.045 + .03 * gr) * oxy * pres * thin; flame.scale.set(R, R, R * .8);
    const u = flameMat.uniforms; u.uTime.value = t; u.uG.value = gr; u.uFlow.value = Math.min(1, s.flow / 30); u.uAlive.value = alive;
    u.uSoot.value = sootE; u.uHeat.value = heat;
    flame.visible = alive > .01;
    fireLight.color.set('#7f9dff').lerp(new THREE.Color('#ffb46a'), Math.min(1, gr * 1.3 + sootE * .8));
    fireLight.intensity = alive * (.35 + .9 * gr) * (.55 + .8 * heat) * thin;
    fireLight.position.copy(SAMPLE).add(new THREE.Vector3(Math.min(1, s.flow / 30) * R * .8, R * (.6 + 1.6 * gr), 0));
    arrows.forEach(a => { a.visible = s.flow > 0; const span = 1.1; a.position.set(-.95 + ((a.userData.phase * span + t * flowMS * 2) % span), a.userData.y, a.userData.z); a.setLength(.08 + .5 * Math.min(1, s.flow / 30), .06, .04); });

    if (!reduce) {
      // grains slip off the top shelf now and then and fall with g (0.5 mm grains: air drag neglected over < 2 m)
      dropper += dt;
      if (g > 0 && dropper > 4) { dropper = 0; for (let n = 0; n < 14; n++) dust.add({ p: new THREE.Vector3(SHELF_X - .6 + rand() * 1.2, SHELF_Y[2] + .05, SHELF_Z + .19), v: new THREE.Vector3((rand() - .5) * .03, 0, .03 + rand() * .04), life: 0, max: 6, size: .012, c: dustC }); }
      if (rand() < dt * 3) dust.add({ p: new THREE.Vector3((rand() - .5) * (W - .4), .4 + rand() * (H - .7), (rand() - .5) * (D - .4)), v: new THREE.Vector3((rand() - .5) * .01, 0, (rand() - .5) * .01), life: 0, max: 8, size: .008, c: dustC });
      const tip = SAMPLE.clone().add(new THREE.Vector3(Math.min(1, s.flow / 30) * R, R * (.7 + 2.6 * gr), 0));
      if (alive > .3 && rand() < dt * (8 + 30 * sootE) * oxy) {
        const dir = new THREE.Vector3().randomDirection(); if (g > 0) dir.y = Math.abs(dir.y);
        smoke.add({ p: tip.clone().addScaledVector(dir, R * .6), v: dir.multiplyScalar(.05), life: 0, max: g > 0 ? 6 : 8, size: .02, c: sootC, kind: 'soot' });
      }
      if (vapor > 0) { vapor -= dt; if (rand() < dt * 30) smoke.add({ p: SAMPLE.clone(), v: new THREE.Vector3((rand() - .5) * .02, 0, (rand() - .5) * .02), life: 0, max: 6, size: .018, c: vapC, kind: 'vapor' }); }
    }
    for (let i = dust.list.length - 1; i >= 0; i--) { const p = dust.list[i]; p.life += dt;
      if (p.life > p.max) { dust.list.splice(i, 1); continue; }
      p.v.y -= g * dt; p.v.x += (flowMS * .5 - p.v.x) * dt * .3; p.p.addScaledVector(p.v, dt);
      if (p.p.y < .004) { p.p.y = .004; p.v.set(0, 0, 0); } }
    for (let i = smoke.list.length - 1; i >= 0; i--) { const p = smoke.list[i]; p.life += dt;
      if (p.life > p.max) { smoke.list.splice(i, 1); continue; }
      // hot-gas buoyancy a = g·(T/Ta − 1), T cooling towards Ta; drag relaxes the parcel to the airflow
      const T = T_AIR + (T_SMOKE0 - T_AIR) * Math.exp(-p.life / TAU_COOL), aUp = g * (T / T_AIR - 1);
      p.v.y += (aUp - p.v.y / TAU_DRAG) * dt; p.v.x += ((flowMS - p.v.x) / TAU_DRAG) * dt; p.v.z += (-p.v.z / TAU_DRAG) * dt;
      p.p.addScaledVector(p.v, dt);
      // turbulent mixing (random walk, D_TURB m²/s): the only spreading left when there is no buoyancy
      p.p.addScaledVector(new THREE.Vector3().randomDirection(), Math.sqrt(2 * D_TURB * dt)); p.p.y = Math.min(H - .05, Math.max(.02, p.p.y)); p.size += dt * .04; }
    smoke.flush(p => { const q = p.life / p.max; return (p.kind === 'vapor' ? .3 : .2) * Math.sin(Math.PI * Math.min(1, q * 1.5)) * (1 - q); });
    dust.flush(p => .6 * (1 - p.life / p.max));

    controls.update(); constrain(); renderer.render(scene, camera); dirty = false;
    perf.end();
    if (!frame.first) { frame.first = true; performance.mark('mf-3d-first-frame'); }
  }
  const perf = createPerf(renderer, () => ({ particles: smoke.list.length + dust.list.length, bodies: world.bodies.length,
    bodiesAwake: world.bodies.filter(b => b.mass > 0 && b.sleepState !== CANNON.Body.SLEEPING).length, quality: 'n/a', scale: 1, dpr: renderer.getPixelRatio() }));
  frame();
  return {
    scene, camera, controls, renderer, world, items, setView, STEP, setCamera, ROOM, LIMITS, CENTER,
    get viewEnv() { return viewEnv; }, windowCheck,
    dropTest: (onTick) => dropTest(onTick),   // no UI: used by the automated gravity test
    get g() { return g; }, get fps() { return fps; }, get simTime() { return simTime; }, perf: () => perf.snapshot(),
  };
}
