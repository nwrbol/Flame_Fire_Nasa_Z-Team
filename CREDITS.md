# Credits and sources

Everything the browser loads is in this repository; nothing is fetched from the network at run time.

## Libraries (vendored in `frontend/vendor/`)

| File | Source | Licence |
| --- | --- | --- |
| `three.module.js`, `OrbitControls.js` | three.js r160 (`three@0.160.1`, npm) | MIT — `THREE-LICENSE.txt` |
| `cannon-es.js` | cannon-es 0.20.0, npm registry tarball `cannon-es-0.20.0.tgz`, sha512 integrity verified at download (build time) | MIT — `CANNON-ES-LICENSE.txt` |

## 3D items in the cabin

No external 3D models are used. Every item is built in code in `frontend/js/cabin3d.js`
from primitives with details, at real size, by this project (no third-party licence):

| Item | Size | Mass | Collider | Construction |
| --- | --- | --- | --- | --- |
| Hardcover book | 240 × 40 × 170 mm | 1.47 kg | box | covers, spine, page block with page-line texture, title |
| Paperback | 210 × 25 × 150 mm | 0.71 kg | box | same |
| Thin manual | 280 × 12 × 210 mm | 0.64 kg | box | same |
| Drop-test book | 220 × 30 × 160 mm | 0.95 kg | box | same |
| Water bottle 0.5 L | Ø66 × 205 mm | 0.53 kg | 2 cylinders (body + neck) | lathe profile, water, cap, label |
| Mug | Ø84 × 95 mm | 0.32 kg | cylinder + handle box | hollow lathe profile, handle, coffee |
| Laptop | 320 × 220 mm, lid open 105° | 1.6 kg | 2 boxes (base + tilted lid) | keyboard texture, screen |
| Tablet | 245 × 170 × 7 mm | 0.47 kg | box | bezel, screen |
| Document box | 400 × 270 × 320 mm | 3 kg | box | lid, hand holes, label |
| Toolbox | 450 × 210 × 220 mm | 4.5 kg | box + handle box | lid seam, latches, handle |
| Cable coil | Ø180 mm | 0.25 kg | ring of 8 spheres | tube along a coil, plug |
| Office chair | seat height 0.47 m | 7 kg | seat, back, column, base | 5-star base with casters |
| First aid kit | 300 × 100 × 200 mm | 1.2 kg | box | ISO 7010 green with white cross, handle |
| Fire extinguisher, smoke detector | — | fixed | static | decor only, no safety hints |

Why not glTF models: compressing glTF with Draco or meshopt needs Node.js tools (gltf-transform /
gltfpack), which are not available on the build machine, and downloaded binaries were not run.
Uncompressed CC0 scans (e.g. Poly Haven) with textures would exceed the 10 MB budget.

## Porthole views and textures

All textures are procedural (drawn on a canvas in `cabin3d.js` with a fixed random seed):
cabin panels, fabric sample, book pages, keyboard, screens, labels, and the four window views
(Earth sky and horizon; Moon surface with craters, stars and a small Earth; Mars surface with
rocks, ochre sky and a small Sun; orbit with stars and Earth's limb). No photographs, no people,
no logos.

## Data and gravity

- Gravity values: NASA NSSDCA Planetary Fact Sheets (Earth, Moon, Mars), retrieved 2026-11-15 —
  see `backend/data/environments.json`.
- Test data and facts: FireGap dataset (NASA PSI) in `backend/data/firegap_dataset/`.
- Hero photo `frontend/assets/hero-flame.webp`: supplied by the project team (cropped and compressed);
  original source and licence to be confirmed by the team.
