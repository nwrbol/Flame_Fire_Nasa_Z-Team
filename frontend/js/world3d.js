// MicroFlame world around the cabin — one real 3D environment seen both through the porthole
// and from outside. No flat backdrop, no reliance on the clear colour:
//  - sky: a full sphere CENTRED ON THE CAMERA every frame (so it can never be reached), drawn
//    first with depth test/write off; gradient, haze, clouds (Earth) and the Sun disc in a shader
//  - stars: Points on a camera-centred sphere (Moon, open space)
//  - ground (Earth, Moon, Mars): 6 km disc with planetary curvature, near/far texture detail and
//    a fade into the horizon colour, plus rocks (near + far LOD) and a ring of distant hills
//  - distant bodies (Earth seen from the Moon, Earth below in orbit): placed thousands of metres
//    away relative to the camera (no parallax) and sized for the right angular diameter
import * as THREE from 'three';

export const FAR = 25000;                 // camera far plane (m)
const SKY_R = 20000, STAR_R = 19000;      // camera-centred spheres, inside the far plane
const GROUND_R = 6000;                    // ground disc radius (m)
const GROUND_Y = -0.125;                  // just below the cabin's outer floor
const PLANET_R = { earth: 6.371e6, moon: 1.7374e6, mars: 3.3895e6 };

// Sun: shines from behind the back wall so its light falls through the porthole.
export const SUN_DIR = new THREE.Vector3(-.25, .42, -.87).normalize();

const ENV = {
  earth: { zenith: '#3f78c9', horizon: '#c9dcea', below: '#a9b6aa', sun: '#fff4dc', sunSize: .0047, glow: .45, clouds: 1, haze: 1, stars: 0,
           ground: '#6f8a52', far: '#a9b6aa', fadeStart: 900, fadeEnd: 5200, rock: '#7d7a72', hills: '#7f93a8', exposure: 1, planet: true },
  moon:  { zenith: '#000000', horizon: '#000000', below: '#3c3c3b', sun: '#ffffff', sunSize: .0047, glow: .06, clouds: 0, haze: 0, stars: 1,
           ground: '#8a8a87', far: '#3c3c3b', fadeStart: 2500, fadeEnd: 5800, rock: '#77766f', hills: '#6c6c69', exposure: 1, planet: true, earthInSky: true },
  mars:  { zenith: '#b7845e', horizon: '#e2bc97', below: '#a9744f', sun: '#fff4e6', sunSize: .0031, glow: .3, clouds: 0, haze: .8, stars: 0,
           ground: '#b4683a', far: '#a9744f', fadeStart: 1200, fadeEnd: 5400, rock: '#6e3a20', hills: '#b88a68', exposure: 1, planet: true },
  space: { zenith: '#000000', horizon: '#000000', below: '#000000', sun: '#ffffff', sunSize: .0047, glow: .05, clouds: 0, haze: 0, stars: 1,
           planet: false, earthBelow: true },
};

function rng(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const NOISE = `
  float hash(vec3 p){ p=fract(p*0.3183099+.1); p*=17.0; return fract(p.x*p.y*p.z*(p.x+p.y+p.z)); }
  float noise(vec3 x){ vec3 i=floor(x), f=fract(x); f=f*f*(3.0-2.0*f);
    return mix(mix(mix(hash(i),hash(i+vec3(1,0,0)),f.x),mix(hash(i+vec3(0,1,0)),hash(i+vec3(1,1,0)),f.x),f.y),
               mix(mix(hash(i+vec3(0,0,1)),hash(i+vec3(1,0,1)),f.x),mix(hash(i+vec3(0,1,1)),hash(i+vec3(1,1,1)),f.x),f.y),f.z); }
  float fbm(vec3 p){ float a=.5, s=0.; for(int i=0;i<5;i++){ s+=a*noise(p); p*=2.03; a*=.5; } return s; }`;

// ---------- sky dome ----------
function skyMaterial() {
  return new THREE.ShaderMaterial({
    side: THREE.BackSide, depthTest: false, depthWrite: false,
    uniforms: { uZenith: { value: new THREE.Color() }, uHorizon: { value: new THREE.Color() }, uBelow: { value: new THREE.Color() },
      uSun: { value: new THREE.Color() }, uSunDir: { value: SUN_DIR.clone() }, uSunSize: { value: .0047 }, uGlow: { value: .4 },
      uClouds: { value: 0 }, uHaze: { value: 0 }, uTime: { value: 0 } },
    vertexShader: `varying vec3 vDir; void main(){ vDir = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: NOISE + `
      uniform vec3 uZenith, uHorizon, uBelow, uSun, uSunDir; uniform float uSunSize, uGlow, uClouds, uHaze, uTime;
      varying vec3 vDir;
      void main(){
        vec3 d = normalize(vDir); float h = d.y;
        vec3 col = mix(uHorizon, uZenith, pow(clamp(h, 0.0, 1.0), 0.55));
        // below the horizon: the far-ground colour (same as the ground fade) -> no visible edge
        col = mix(col, uBelow, smoothstep(0.0, mix(0.0008, 0.02, uHaze), -h));
        // haze band hugging the horizon (none on the Moon / in orbit: sharp horizon)
        col = mix(col, uHorizon, uHaze * exp(-abs(h) * 28.0) * 0.6);
        // clouds (Earth): fbm on a flat cloud layer, fading towards the horizon
        if (uClouds > 0.0 && h > 0.0) {
          vec2 p = d.xz / (h + 0.12) * 2.2 + vec2(uTime * 0.004, 0.0);
          float c = smoothstep(0.52, 0.78, fbm(vec3(p, 1.7)));
          col = mix(col, vec3(1.0), c * 0.85 * uClouds * smoothstep(0.02, 0.18, h));
        }
        // the Sun: disc (angular radius uSunSize rad) plus glow
        float cs = dot(d, normalize(uSunDir)), ang = acos(clamp(cs, -1.0, 1.0));
        col += uSun * (smoothstep(uSunSize * 1.15, uSunSize * 0.85, ang) * 6.0 + uGlow * exp(-ang * 9.0) + uGlow * 0.35 * exp(-ang * 2.5));
        gl_FragColor = vec4(col, 1.0);
      }`,
  });
}

// ---------- distant spheres (Earth) ----------
function planetMaterial() {
  return new THREE.ShaderMaterial({
    uniforms: { uSunDir: { value: SUN_DIR.clone() }, uTime: { value: 0 } },   // uSunDir: set per body in update()
    vertexShader: `
      #include <common>
      #include <logdepthbuf_pars_vertex>
      varying vec3 vN; varying vec3 vP;
      void main(){ vN = normalize(mat3(modelMatrix) * normal); vP = normalize(position);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        #include <logdepthbuf_vertex>
      }`,
    fragmentShader: NOISE + `
      #include <logdepthbuf_pars_fragment>
      uniform vec3 uSunDir; uniform float uTime; varying vec3 vN; varying vec3 vP;
      void main(){
        #include <logdepthbuf_fragment>
        float land = smoothstep(0.5, 0.56, fbm(vP * 2.4 + 3.0));
        vec3 col = mix(vec3(0.05, 0.18, 0.45), mix(vec3(0.22, 0.36, 0.16), vec3(0.55, 0.48, 0.33), fbm(vP * 6.0)), land);
        float cl = smoothstep(0.5, 0.75, fbm(vP * 5.0 + vec3(uTime * 0.002, 0.0, 0.0)));
        col = mix(col, vec3(0.95), cl * 0.85);
        float light = clamp(dot(normalize(vN), normalize(uSunDir)) * 1.1 + 0.08, 0.0, 1.0);
        gl_FragColor = vec4(col * light, 1.0);
      }`,
  });
}
function atmosphereMaterial() {
  return new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.BackSide,
    uniforms: { uSunDir: { value: SUN_DIR.clone() } },
    vertexShader: `
      #include <common>
      #include <logdepthbuf_pars_vertex>
      varying vec3 vN; varying vec3 vV;
      void main(){ vec4 mv = modelViewMatrix * vec4(position, 1.0); vN = normalize(normalMatrix * normal); vV = normalize(-mv.xyz);
        gl_Position = projectionMatrix * mv;
        #include <logdepthbuf_vertex>
      }`,
    fragmentShader: `
      #include <logdepthbuf_pars_fragment>
      varying vec3 vN; varying vec3 vV;
      void main(){
        #include <logdepthbuf_fragment>
        float rim = pow(1.0 - abs(dot(vN, vV)), 3.0);
        gl_FragColor = vec4(vec3(0.35, 0.6, 1.0) * rim * 1.4, rim);
      }`,
  });
}

// ---------- ground ----------
function tileTexture(env, size = 512) {
  const r = rng({ earth: 1, moon: 2, mars: 3 }[env]);
  const c = document.createElement('canvas'); c.width = c.height = size; const g = c.getContext('2d');
  const base = { earth: [104, 132, 76], moon: [140, 140, 136], mars: [178, 104, 60] }[env];
  g.fillStyle = `rgb(${base})`; g.fillRect(0, 0, size, size);
  for (let i = 0; i < 9000; i++) { const k = (r() - .5) * 46; g.fillStyle = `rgba(${base.map(v => Math.max(0, Math.min(255, v + k)))},${.35 + r() * .4})`; const s = 1 + r() * 3; g.fillRect(r() * size, r() * size, s, s); }
  if (env === 'moon') for (let i = 0; i < 45; i++) { const x = r() * size, y = r() * size, rad = 4 + r() * 26;
    const gr = g.createRadialGradient(x - rad * .2, y - rad * .2, rad * .1, x, y, rad); gr.addColorStop(0, 'rgba(70,70,68,.55)'); gr.addColorStop(.85, 'rgba(110,110,106,.2)'); gr.addColorStop(1, 'rgba(0,0,0,0)');
    g.fillStyle = gr; g.beginPath(); g.arc(x, y, rad, 0, 7); g.fill(); g.strokeStyle = 'rgba(205,205,198,.35)'; g.lineWidth = 1.5; g.beginPath(); g.arc(x, y, rad, 3.6, 5.8); g.stroke(); }
  if (env === 'mars') for (let i = 0; i < 260; i++) { g.fillStyle = `rgba(70,35,18,${.4 + r() * .4})`; g.beginPath(); g.ellipse(r() * size, r() * size, 1 + r() * 4, 1 + r() * 3, r() * 3, 0, 7); g.fill(); }
  if (env === 'earth') for (let i = 0; i < 1400; i++) { g.strokeStyle = `rgba(${60 + r() * 50},${110 + r() * 50},${40 + r() * 30},.55)`; g.lineWidth = 1; const x = r() * size, y = r() * size; g.beginPath(); g.moveTo(x, y); g.lineTo(x + (r() - .5) * 3, y - 3 - r() * 5); g.stroke(); }
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; return t;
}
function macroTexture(env, size = 1024) {   // large-scale variation and big craters (Moon), shared repeat ~1.5 km
  const r = rng(10 + { earth: 1, moon: 2, mars: 3 }[env]);
  const c = document.createElement('canvas'); c.width = c.height = size; const g = c.getContext('2d');
  g.fillStyle = '#808080'; g.fillRect(0, 0, size, size);
  for (let i = 0; i < 140; i++) { const x = r() * size, y = r() * size, rad = 20 + r() * 160, v = 128 + (r() - .5) * 60;
    const gr = g.createRadialGradient(x, y, 0, x, y, rad); gr.addColorStop(0, `rgba(${v},${v},${v},.5)`); gr.addColorStop(1, 'rgba(128,128,128,0)'); g.fillStyle = gr; g.fillRect(x - rad, y - rad, rad * 2, rad * 2); }
  if (env === 'moon') for (let i = 0; i < 60; i++) { const x = r() * size, y = r() * size, rad = 6 + r() * 40;
    g.fillStyle = 'rgba(60,60,60,.45)'; g.beginPath(); g.arc(x, y, rad, 0, 7); g.fill(); g.strokeStyle = 'rgba(210,210,210,.5)'; g.lineWidth = 2; g.beginPath(); g.arc(x, y, rad, 3.5, 6); g.stroke(); }
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; return t;
}
// Polar grid with rings packed near the cabin (r ∝ i²): fine detail close by, coarse far away.
function groundGeometry() {
  const rings = 90, segs = 160, pos = [], uv = [], idx = [];
  pos.push(0, 0, 0); uv.push(0, 0);
  for (let i = 1; i <= rings; i++) { const r = GROUND_R * (i / rings) ** 2;
    for (let j = 0; j < segs; j++) { const a = j / segs * Math.PI * 2, x = Math.cos(a) * r, z = Math.sin(a) * r; pos.push(x, 0, z); uv.push(x, z); } }
  for (let j = 0; j < segs; j++) idx.push(0, 1 + (j + 1) % segs, 1 + j);
  for (let i = 1; i < rings; i++) for (let j = 0; j < segs; j++) {
    const a = 1 + (i - 1) * segs + j, b = 1 + (i - 1) * segs + (j + 1) % segs, c = 1 + i * segs + j, d = 1 + i * segs + (j + 1) % segs;
    idx.push(a, b, c, b, d, c); }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.setIndex(idx); g.computeVertexNormals(); return g;
}
// Standard (shadow-receiving) material + curvature, macro detail and fade into the horizon colour.
function groundMaterial(env) {
  const mat = new THREE.MeshStandardMaterial({ map: tileTexture(env), roughness: 1, metalness: 0 });
  mat.map.repeat.set(1 / 6, 1 / 6);                         // tile = 6 m
  const u = { uMacro: { value: macroTexture(env) }, uFar: { value: new THREE.Color(ENV[env].far) }, uFade: { value: new THREE.Vector2(ENV[env].fadeStart, ENV[env].fadeEnd) }, uPlanetR: { value: PLANET_R[env] } };
  mat.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, u);
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nuniform float uPlanetR; varying vec3 vWorldG;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\n vec2 wxz = (modelMatrix * vec4(transformed, 1.0)).xz; transformed.y -= dot(wxz, wxz) / (2.0 * uPlanetR);')
      .replace('#include <worldpos_vertex>', '#include <worldpos_vertex>\n vWorldG = (modelMatrix * vec4(transformed, 1.0)).xyz;');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nuniform sampler2D uMacro; uniform vec3 uFar; uniform vec2 uFade; varying vec3 vWorldG;')
      .replace('#include <map_fragment>', '#include <map_fragment>\n diffuseColor.rgb *= 0.55 + 0.9 * texture2D(uMacro, vWorldG.xz / 1500.0).r;')
      .replace('#include <dithering_fragment>', '#include <dithering_fragment>\n float dd = length(vWorldG.xz - cameraPosition.xz);\n gl_FragColor.rgb = mix(gl_FragColor.rgb, uFar, smoothstep(uFade.x, uFade.y, dd));');
  };
  return mat;
}
function hillsMesh(env) {   // ring of distant hills / mountains on the horizon (4.2–5.6 km)
  const r = rng(30 + { earth: 1, moon: 2, mars: 3 }[env]), segs = 360, pos = [], idx = [], col = [];
  const base = new THREE.Color(ENV[env].hills), far = new THREE.Color(ENV[env].far), c = new THREE.Color();
  const amp = { earth: 220, moon: 340, mars: 260 }[env];
  let phase = r() * 10;
  for (let j = 0; j <= segs; j++) {
    const a = j / segs * Math.PI * 2, R = 4600 + Math.sin(a * 3 + phase) * 300;
    const hgt = amp * (.35 + .65 * Math.abs(Math.sin(a * 5 + phase) * .6 + Math.sin(a * 13.7 + phase * 2) * .3 + Math.sin(a * 31 + phase) * .1));
    const drop = R * R / (2 * PLANET_R[env]);
    pos.push(Math.cos(a) * (R + 600), GROUND_Y - drop - 40, Math.sin(a) * (R + 600), Math.cos(a) * R, GROUND_Y - drop + hgt, Math.sin(a) * R);
    c.copy(far).lerp(base, .25); col.push(c.r, c.g, c.b); c.copy(base); col.push(c.r, c.g, c.b);
    if (j < segs) { const k = j * 2; idx.push(k, k + 1, k + 2, k + 1, k + 3, k + 2); }
  }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3)); g.setIndex(idx); g.computeVertexNormals();
  const m = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.DoubleSide, fog: false }));
  m.frustumCulled = false; return m;
}
function rocks(env, count, rMin, rMax, sMin, sMax, seed) {
  const r = rng(seed), geo = new THREE.IcosahedronGeometry(1, 1);
  const p = geo.attributes.position; for (let i = 0; i < p.count; i++) { const k = .75 + r() * .5; p.setXYZ(i, p.getX(i) * k, p.getY(i) * k * .7, p.getZ(i) * k); }
  geo.computeVertexNormals();
  const mesh = new THREE.InstancedMesh(geo, new THREE.MeshStandardMaterial({ color: ENV[env].rock, roughness: .95, flatShading: true }), count);
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(), v = new THREE.Vector3();
  for (let i = 0; i < count; i++) {
    let d, a; do { d = rMin + (rMax - rMin) * Math.sqrt(r()); a = r() * Math.PI * 2; } while (Math.abs(Math.cos(a) * d) < 3.2 && Math.abs(Math.sin(a) * d) < 2.8);  // keep the cabin footprint clear
    const sc = sMin + (sMax - sMin) * Math.pow(r(), 2.2), x = Math.cos(a) * d, z = Math.sin(a) * d;
    v.set(x, GROUND_Y - (x * x + z * z) / (2 * PLANET_R[env]) + sc * .15, z);
    q.setFromEuler(new THREE.Euler(r() * .5, r() * 6.3, r() * .5)); s.set(sc * (.7 + r() * .6), sc, sc * (.7 + r() * .6));
    mesh.setMatrixAt(i, m.compose(v, q, s));
  }
  mesh.castShadow = mesh.receiveShadow = true; mesh.frustumCulled = false; return mesh;
}

export function createWorld(scene, { small = false } = {}) {
  const world = new THREE.Group(); scene.add(world);
  // sky dome and stars follow the camera
  const skyMat = skyMaterial();
  const sky = new THREE.Mesh(new THREE.SphereGeometry(SKY_R, 64, 32), skyMat); sky.renderOrder = -10; sky.frustumCulled = false; scene.add(sky);
  const r = rng(99), N = small ? 1800 : 3600, sp = new Float32Array(N * 3), sc = new Float32Array(N * 3);
  for (let i = 0; i < N; i++) { const v = new THREE.Vector3().randomDirection().multiplyScalar(STAR_R); v.toArray(sp, i * 3); const k = .45 + r() * .55, warm = r(); sc.set([k, k * (.93 + warm * .07), k * (1 - warm * .15)], i * 3); }
  const sg = new THREE.BufferGeometry(); sg.setAttribute('position', new THREE.BufferAttribute(sp, 3)); sg.setAttribute('color', new THREE.BufferAttribute(sc, 3));
  const stars = new THREE.Points(sg, new THREE.PointsMaterial({ size: small ? 1.6 : 2, sizeAttenuation: false, vertexColors: true, depthTest: false, depthWrite: false, transparent: false, fog: false }));   // opaque list: drawn first, behind everything
  stars.renderOrder = -9; stars.frustumCulled = false; scene.add(stars);

  // distant Earth (from the Moon: ~1.9° across; from orbit: a huge ball below, ~60° across)
  const planetMat = planetMaterial();
  const earthBall = new THREE.Mesh(new THREE.SphereGeometry(1, 96, 48), planetMat); earthBall.frustumCulled = false; scene.add(earthBall);
  const atmo = new THREE.Mesh(new THREE.SphereGeometry(1.025, 96, 48), atmosphereMaterial()); atmo.frustumCulled = false; scene.add(atmo);
  // light: direction lighting the body's visible face (a waxing gibbous Earth seen from the cabin)
  const BODY = { moon: { dir: new THREE.Vector3(-.512, .058, -.857).normalize(), dist: 8000, angDiam: 1.9 * Math.PI / 180, light: new THREE.Vector3(.65, .35, .68).normalize() },
                 space: { dir: new THREE.Vector3(-.5, -.5, -.72).normalize(), dist: 9000, angDiam: 62 * Math.PI / 180, light: new THREE.Vector3(.2, .62, .76).normalize() } };

  // ground sets per planet surface, built lazily
  const grounds = {};
  function groundFor(env) {
    if (grounds[env]) return grounds[env];
    const g = new THREE.Group();
    const disc = new THREE.Mesh(groundGeometry(), groundMaterial(env)); disc.position.y = GROUND_Y; disc.receiveShadow = true; disc.frustumCulled = false; g.add(disc);
    g.add(rocks(env, small ? 140 : 280, 4, 70, .04, .45, 7));          // near: pebbles and stones
    g.add(rocks(env, small ? 60 : 120, 70, 1400, 1, 9, 8));             // far: boulders
    g.add(hillsMesh(env));
    world.add(g); grounds[env] = g; return g;
  }

  let env = null;
  const fogColor = new THREE.Color();
  function setEnv(id) {
    env = id; const e = ENV[id];
    const u = skyMat.uniforms;
    u.uZenith.value.set(e.zenith); u.uHorizon.value.set(e.horizon); u.uBelow.value.set(e.below || e.horizon); u.uSun.value.set(e.sun);
    u.uSunSize.value = e.sunSize; u.uGlow.value = e.glow; u.uClouds.value = e.clouds; u.uHaze.value = e.haze;
    stars.visible = !!e.stars;
    for (const [k, g] of Object.entries(grounds)) g.visible = false;
    if (e.planet) groundFor(id).visible = true;
    earthBall.visible = atmo.visible = !!(e.earthInSky || e.earthBelow);
    // renderer clear colour = sky colour at the horizon (never the only background)
    scene.background = new THREE.Color(e.horizon);
    scene.fog = e.haze ? new THREE.Fog(fogColor.set(e.far), e.fadeStart * .6, e.fadeEnd * 1.2) : null;
  }
  function update(camera, t) {
    sky.position.copy(camera.position); stars.position.copy(camera.position);
    skyMat.uniforms.uTime.value = t; planetMat.uniforms.uTime.value = t;
    const b = BODY[env];
    if (b && earthBall.visible) {   // fixed direction from the camera: zero parallax, right angular size
      const R = b.dist * Math.sin(b.angDiam / 2);
      earthBall.position.copy(camera.position).addScaledVector(b.dir, b.dist); earthBall.scale.setScalar(R);
      atmo.position.copy(earthBall.position); atmo.scale.setScalar(R); planetMat.uniforms.uSunDir.value.copy(b.light);
    }
  }
  return { setEnv, update, get env() { return env; }, sky, stars, earthBall };
}
