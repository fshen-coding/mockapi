<script setup>
// 登录页 3D 背景：节点网络（plexus）+ 流动的光线。
// 鼠标：镜头视差、靠近指针的节点被吸引并与指针连线。
import { onBeforeUnmount, onMounted, ref } from 'vue'
import * as THREE from 'three'

const props = defineProps({
  dark: { type: Boolean, default: false },
})

const host = ref(null)
let cleanup = () => {}

const palettes = {
  light: {
    bg: new THREE.Color(0xeef2fb),
    line: new THREE.Color(0x6f8fd6),
    nodes: [0x2f6bea, 0x5b8def, 0x38bdf8, 0x34d399, 0xa78bfa],
    flow: [0x8aa8f0, 0xb4a6f5, 0x7cc4f5],
    nodeOpacity: 0.85,
  },
  dark: {
    bg: new THREE.Color(0x0b1424),
    line: new THREE.Color(0x5b8def),
    nodes: [0x60a5fa, 0x93c5fd, 0x38bdf8, 0x34d399, 0xc4b5fd],
    flow: [0x3b6fd8, 0x7c6cf0, 0x2fa8e0],
    nodeOpacity: 1,
  },
}

const nodeVertex = /* glsl */ `
  attribute float aSize;
  attribute vec3 aColor;
  uniform float uPixelRatio;
  varying vec3 vColor;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vColor = aColor;
    gl_PointSize = aSize * uPixelRatio * (34.0 / -mv.z);
    gl_Position = projectionMatrix * mv;
  }
`
const nodeFragment = /* glsl */ `
  uniform float uOpacity;
  varying vec3 vColor;
  void main() {
    float d = length(gl_PointCoord - 0.5);
    if (d > 0.5) discard;
    float core = smoothstep(0.22, 0.0, d);
    float halo = smoothstep(0.5, 0.0, d) * 0.45;
    gl_FragColor = vec4(vColor, (core + halo) * uOpacity);
  }
`

onMounted(() => {
  const el = host.value
  if (!el) return
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const palette = props.dark ? palettes.dark : palettes.light

  let renderer
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  } catch {
    return
  }
  const pixelRatio = Math.min(window.devicePixelRatio, 2)
  renderer.setPixelRatio(pixelRatio)
  el.appendChild(renderer.domElement)

  const scene = new THREE.Scene()
  const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 200)
  camera.position.set(0, 0, 30)

  // ---- 节点网络：主要铺在画面中下部，像图里那条横贯的网络带 ----
  const NODE_COUNT = 150
  const base = new Float32Array(NODE_COUNT * 3)
  const pos = new Float32Array(NODE_COUNT * 3)
  const sizes = new Float32Array(NODE_COUNT)
  const colors = new Float32Array(NODE_COUNT * 3)
  const seeds = new Float32Array(NODE_COUNT)
  const tmpColor = new THREE.Color()
  for (let i = 0; i < NODE_COUNT; i++) {
    const x = (Math.random() - 0.5) * 70
    const y = -6 + Math.sin(x * 0.12) * 3 + (Math.random() - 0.5) * 9
    const z = (Math.random() - 0.5) * 22 - 4
    base.set([x, y, z], i * 3)
    pos.set([x, y, z], i * 3)
    sizes[i] = Math.random() < 0.12 ? 9 + Math.random() * 6 : 3 + Math.random() * 4
    tmpColor.set(palette.nodes[Math.floor(Math.random() * palette.nodes.length)])
    colors.set([tmpColor.r, tmpColor.g, tmpColor.b], i * 3)
    seeds[i] = Math.random() * Math.PI * 2
  }
  const nodeGeo = new THREE.BufferGeometry()
  nodeGeo.setAttribute('position', new THREE.BufferAttribute(pos, 3))
  nodeGeo.setAttribute('aSize', new THREE.BufferAttribute(sizes, 1))
  nodeGeo.setAttribute('aColor', new THREE.BufferAttribute(colors, 3))
  const nodeMat = new THREE.ShaderMaterial({
    vertexShader: nodeVertex,
    fragmentShader: nodeFragment,
    uniforms: { uPixelRatio: { value: pixelRatio }, uOpacity: { value: palette.nodeOpacity } },
    transparent: true,
    depthWrite: false,
  })
  scene.add(new THREE.Points(nodeGeo, nodeMat))

  // 连线：按距离动态生成，距离越远颜色越接近背景色，相当于淡出
  const MAX_SEGMENTS = 2600
  const linePos = new Float32Array(MAX_SEGMENTS * 6)
  const lineCol = new Float32Array(MAX_SEGMENTS * 6)
  const lineGeo = new THREE.BufferGeometry()
  lineGeo.setAttribute('position', new THREE.BufferAttribute(linePos, 3).setUsage(THREE.DynamicDrawUsage))
  lineGeo.setAttribute('color', new THREE.BufferAttribute(lineCol, 3).setUsage(THREE.DynamicDrawUsage))
  const lineMat = new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.75, depthWrite: false })
  scene.add(new THREE.LineSegments(lineGeo, lineMat))

  // ---- 流动光线：几条交织的长曲线，从左下穿到右侧 ----
  const FLOW_POINTS = 220
  const flows = palette.flow.flatMap((c, k) => [0, 1].map((n) => ({ color: c, k: k * 2 + n })))
  const flowLines = flows.map(({ color, k }) => {
    const arr = new Float32Array(FLOW_POINTS * 3)
    const geo = new THREE.BufferGeometry()
    geo.setAttribute('position', new THREE.BufferAttribute(arr, 3).setUsage(THREE.DynamicDrawUsage))
    const mat = new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.38 + (k % 3) * 0.08, depthWrite: false })
    const line = new THREE.Line(geo, mat)
    line.userData = { k, arr }
    scene.add(line)
    return line
  })

  // ---- 鼠标：屏幕坐标映射到 z=0 平面 ----
  const pointer = { x: 0, y: 0, tx: 0, ty: 0, active: 0, tActive: 0 }
  const mouseWorld = new THREE.Vector3(999, 999, 0)
  const raycaster = new THREE.Raycaster()
  const plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0)
  const ndc = new THREE.Vector2()
  const onMove = (e) => {
    const rect = el.getBoundingClientRect()
    pointer.tx = ((e.clientX - rect.left) / rect.width) * 2 - 1
    pointer.ty = -(((e.clientY - rect.top) / rect.height) * 2 - 1)
    pointer.tActive = 1
  }
  const onLeave = () => { pointer.tActive = 0 }
  window.addEventListener('pointermove', onMove, { passive: true })
  document.addEventListener('pointerleave', onLeave)

  const resize = () => {
    const w = el.clientWidth || window.innerWidth
    const h = el.clientHeight || window.innerHeight
    renderer.setSize(w, h, false)
    camera.aspect = w / h
    camera.updateProjectionMatrix()
  }
  resize()
  const ro = new ResizeObserver(resize)
  ro.observe(el)

  const LINK_DIST = 7.2
  const MOUSE_DIST = 9
  const bg = palette.bg
  const lc = palette.line
  const writeSegment = (idx, ax, ay, az, bx, by, bz, strength) => {
    const o = idx * 6
    linePos[o] = ax; linePos[o + 1] = ay; linePos[o + 2] = az
    linePos[o + 3] = bx; linePos[o + 4] = by; linePos[o + 5] = bz
    const r = bg.r + (lc.r - bg.r) * strength
    const g = bg.g + (lc.g - bg.g) * strength
    const b = bg.b + (lc.b - bg.b) * strength
    lineCol[o] = lineCol[o + 3] = r
    lineCol[o + 1] = lineCol[o + 4] = g
    lineCol[o + 2] = lineCol[o + 5] = b
  }

  const clock = new THREE.Clock()
  let frame = 0
  const render = () => {
    const t = clock.getElapsedTime()
    pointer.x += (pointer.tx - pointer.x) * 0.06
    pointer.y += (pointer.ty - pointer.y) * 0.06
    pointer.active += (pointer.tActive - pointer.active) * 0.05

    camera.position.x = pointer.x * 2.4
    camera.position.y = pointer.y * 1.4
    camera.lookAt(0, -1, 0)

    ndc.set(pointer.x, pointer.y)
    raycaster.setFromCamera(ndc, camera)
    raycaster.ray.intersectPlane(plane, mouseWorld)

    // 节点漂移 + 被指针吸引
    for (let i = 0; i < NODE_COUNT; i++) {
      const o = i * 3
      const s = seeds[i]
      let x = base[o] + Math.sin(t * 0.3 + s) * 0.8
      let y = base[o + 1] + Math.cos(t * 0.25 + s * 1.3) * 0.6
      const z = base[o + 2]
      const dx = mouseWorld.x - x
      const dy = mouseWorld.y - y
      const d = Math.hypot(dx, dy)
      if (d < MOUSE_DIST && pointer.active > 0.01) {
        const pull = (1 - d / MOUSE_DIST) * 0.28 * pointer.active
        x += dx * pull
        y += dy * pull
      }
      pos[o] = x; pos[o + 1] = y; pos[o + 2] = z
    }
    nodeGeo.attributes.position.needsUpdate = true

    let seg = 0
    for (let i = 0; i < NODE_COUNT && seg < MAX_SEGMENTS; i++) {
      const ax = pos[i * 3], ay = pos[i * 3 + 1], az = pos[i * 3 + 2]
      for (let j = i + 1; j < NODE_COUNT && seg < MAX_SEGMENTS; j++) {
        const bx = pos[j * 3], by = pos[j * 3 + 1], bz = pos[j * 3 + 2]
        const d = Math.hypot(ax - bx, ay - by, az - bz)
        if (d < LINK_DIST) writeSegment(seg++, ax, ay, az, bx, by, bz, (1 - d / LINK_DIST) * 0.9)
      }
      // 指针附近的节点直接与指针连线
      if (pointer.active > 0.05) {
        const d = Math.hypot(ax - mouseWorld.x, ay - mouseWorld.y, az)
        if (d < MOUSE_DIST && seg < MAX_SEGMENTS) {
          writeSegment(seg++, ax, ay, az, mouseWorld.x, mouseWorld.y, 0, (1 - d / MOUSE_DIST) * pointer.active)
        }
      }
    }
    lineGeo.setDrawRange(0, seg * 2)
    lineGeo.attributes.position.needsUpdate = true
    lineGeo.attributes.color.needsUpdate = true

    // 流动光线：右侧抬升的 S 形曲线，靠近指针时向上鼓起
    flowLines.forEach((line) => {
      const { k, arr } = line.userData
      for (let p = 0; p < FLOW_POINTS; p++) {
        const u = p / (FLOW_POINTS - 1)
        const x = -40 + u * 80
        const rise = 1 / (1 + Math.exp(-(x - 6) * 0.22)) * 9
        let y = -9 + rise + Math.sin(x * 0.16 + t * 0.6 + k * 0.7) * (1.2 + k * 0.25) + k * 0.35
        const z = -3 + Math.cos(x * 0.1 + k) * 3
        const dm = Math.abs(x - mouseWorld.x)
        y += Math.exp(-dm * dm / 30) * 1.6 * pointer.active
        arr[p * 3] = x; arr[p * 3 + 1] = y; arr[p * 3 + 2] = z
      }
      line.geometry.attributes.position.needsUpdate = true
    })

    renderer.render(scene, camera)
    if (!reduced) frame = requestAnimationFrame(render)
  }
  render()

  const onVisibility = () => {
    cancelAnimationFrame(frame)
    if (!document.hidden && !reduced) frame = requestAnimationFrame(render)
  }
  document.addEventListener('visibilitychange', onVisibility)

  cleanup = () => {
    cancelAnimationFrame(frame)
    window.removeEventListener('pointermove', onMove)
    document.removeEventListener('pointerleave', onLeave)
    document.removeEventListener('visibilitychange', onVisibility)
    ro.disconnect()
    nodeGeo.dispose(); nodeMat.dispose()
    lineGeo.dispose(); lineMat.dispose()
    flowLines.forEach((l) => { l.geometry.dispose(); l.material.dispose() })
    renderer.dispose()
    renderer.domElement.remove()
  }
})

onBeforeUnmount(() => cleanup())
</script>

<template>
  <div ref="host" class="login-scene-3d" aria-hidden="true"></div>
</template>

<style scoped>
.login-scene-3d {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
}
.login-scene-3d :deep(canvas) {
  display: block;
  width: 100%;
  height: 100%;
}
</style>
