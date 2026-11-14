import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

const COLORS = { low: 0x5ab0ff, medium: 0xffb347, high: 0xff5d4a }

// Сферическое пламя: в невесомости нет конвекции, поэтому огонь круглый.
export default function Flame({ rate, risk }) {
  const el = useRef()
  const live = useRef({ rate, risk })
  live.current = { rate, risk }

  useEffect(() => {
    const box = el.current
    const scene = new THREE.Scene()
    const cam = new THREE.PerspectiveCamera(45, 1, 0.1, 200)
    cam.position.set(0, 0.5, 9)
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    box.appendChild(renderer.domElement)

    const controls = new OrbitControls(cam, renderer.domElement)
    controls.enableDamping = true
    controls.enablePan = false
    controls.minDistance = 5
    controls.maxDistance = 16
    controls.autoRotate = !window.matchMedia('(prefers-reduced-motion: reduce)').matches
    controls.autoRotateSpeed = 0.5

    const core = new THREE.Mesh(
      new THREE.SphereGeometry(1, 64, 64),
      new THREE.MeshBasicMaterial({ color: COLORS.low, transparent: true, opacity: 0.9 })
    )
    const halo = new THREE.Mesh(
      new THREE.SphereGeometry(1, 32, 32),
      new THREE.MeshBasicMaterial({ color: COLORS.low, transparent: true, opacity: 0.18,
        blending: THREE.AdditiveBlending, depthWrite: false })
    )
    scene.add(core, halo)

    const starPos = new Float32Array(900)
    for (let i = 0; i < 300; i++) {
      const v = new THREE.Vector3().randomDirection().multiplyScalar(40 + Math.random() * 30)
      starPos.set([v.x, v.y, v.z], i * 3)
    }
    const starGeo = new THREE.BufferGeometry()
    starGeo.setAttribute('position', new THREE.BufferAttribute(starPos, 3))
    scene.add(new THREE.Points(starGeo, new THREE.PointsMaterial({ color: 0xcfd6ff, size: 0.12, sizeAttenuation: true })))

    const N = 700
    const dirs = Array.from({ length: N }, () => new THREE.Vector3().randomDirection())
    const smokeGeo = new THREE.BufferGeometry()
    smokeGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(N * 3), 3))
    scene.add(new THREE.Points(smokeGeo, new THREE.PointsMaterial({ color: 0xaab4e8, size: 0.06, transparent: true, opacity: 0.55 })))

    const resize = () => {
      const w = box.clientWidth, h = box.clientHeight
      renderer.setSize(w, h)
      cam.aspect = w / h
      cam.updateProjectionMatrix()
    }
    const ro = new ResizeObserver(resize)
    ro.observe(box)
    resize()

    const target = new THREE.Color(COLORS.low)
    let id, t = 0
    const loop = () => {
      id = requestAnimationFrame(loop)
      t += 0.016
      const s = live.current
      const R = 0.6 + Math.min(s.rate, 10) * 0.15
      target.set(COLORS[s.risk] ?? COLORS.low)
      core.material.color.lerp(target, 0.08)
      halo.material.color.lerp(target, 0.08)
      core.scale.setScalar(R * (1 + 0.025 * Math.sin(t * 6)))
      halo.scale.setScalar(R * 1.9)
      const a = smokeGeo.attributes.position
      for (let i = 0; i < N; i++) {
        const k = R + (((t * 0.08 * (1 + s.rate * 0.4)) + i / N) % 1) * 3.5
        a.setXYZ(i, dirs[i].x * k, dirs[i].y * k, dirs[i].z * k)
      }
      a.needsUpdate = true
      controls.update()
      renderer.render(scene, cam)
    }
    loop()

    return () => {
      cancelAnimationFrame(id)
      ro.disconnect()
      controls.dispose()
      renderer.dispose()
      renderer.domElement.remove()
    }
  }, [])

  return <div ref={el} className="flame" />
}
