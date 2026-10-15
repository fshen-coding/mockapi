<script setup lang="ts">
import * as THREE from 'three'
import { onMounted, onUnmounted, ref } from 'vue'

interface Props {
  colorStops?: string[]
  amplitude?: number
  blend?: number
  speed?: number
}

const props = withDefaults(defineProps<Props>(), {
  colorStops: () => ['#1f6c9f', '#d6b278', '#3a3a38'],
  amplitude: 1,
  blend: 0.6,
  speed: 0.6,
})

const host = ref<HTMLDivElement | null>(null)

let renderer: THREE.WebGLRenderer | null = null
let geometry: THREE.PlaneGeometry | null = null
let surfaceMaterial: THREE.MeshStandardMaterial | null = null
let wireMaterial: THREE.MeshBasicMaterial | null = null
let resizeObserver: ResizeObserver | null = null
let intersectionObserver: IntersectionObserver | null = null
let resizeHandler: (() => void) | null = null
let visibilityHandler: (() => void) | null = null
let motionQuery: MediaQueryList | null = null
let motionHandler: (() => void) | null = null
let pointerMoveHandler: ((event: PointerEvent) => void) | null = null
let pointerLeaveHandler: (() => void) | null = null
let animationFrame = 0
let inView = true

onMounted(() => {
  const element = host.value
  if (!element) return

  motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
  const lowPower = motionQuery.matches || window.matchMedia('(pointer: coarse)').matches
  const scene = new THREE.Scene()
  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 90)
  const baseCameraPosition = new THREE.Vector3(0, 8, 16)
  const pointerTarget = new THREE.Vector2()
  const pointerPosition = new THREE.Vector2()
  camera.position.copy(baseCameraPosition)
  camera.lookAt(0, -1, 0)

  try {
    renderer = new THREE.WebGLRenderer({
      alpha: true,
      antialias: !lowPower,
      powerPreference: 'low-power',
    })
  } catch {
    element.dataset.sceneFallback = 'true'
    return
  }

  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, lowPower ? 1 : 1.5))
  renderer.setClearColor(0x000000, 0)
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.domElement.setAttribute('aria-hidden', 'true')
  element.appendChild(renderer.domElement)

  const colors = props.colorStops.map((value) => new THREE.Color(value))
  geometry = new THREE.PlaneGeometry(25, 18, 56, 34)
  surfaceMaterial = new THREE.MeshStandardMaterial({
    color: colors[0],
    emissive: colors[0],
    emissiveIntensity: 0.12,
    metalness: 0.08,
    roughness: 0.78,
    side: THREE.DoubleSide,
    transparent: true,
    opacity: 0.12 + props.blend * 0.08,
  })
  wireMaterial = new THREE.MeshBasicMaterial({
    color: colors[1] || colors[0],
    side: THREE.DoubleSide,
    transparent: true,
    opacity: 0.1 + props.blend * 0.08,
    wireframe: true,
  })

  const terrain = new THREE.Mesh(geometry, surfaceMaterial)
  const contours = new THREE.Mesh(geometry, wireMaterial)
  terrain.rotation.x = -Math.PI / 2
  contours.rotation.x = -Math.PI / 2
  terrain.position.y = -1.2
  contours.position.y = -1.18
  scene.add(terrain, contours)
  scene.add(new THREE.HemisphereLight(0xc5e2f4, 0x132333, 1.25))

  const keyLight = new THREE.DirectionalLight(colors[1] || 0xd6b278, 1.6)
  keyLight.position.set(-4, 8, 4)
  scene.add(keyLight)

  const positions = geometry.attributes.position.array as Float32Array
  const basePositions = positions.slice()
  let waveInitialized = false
  const renderFrame = (timestamp: number) => {
    animationFrame = 0
    if (!renderer || document.hidden || !inView) return

    const time = lowPower ? 0.75 : timestamp * props.speed * 0.00022
    if (!motionQuery?.matches && (!lowPower || !waveInitialized)) {
      for (let i = 0; i < positions.length; i += 3) {
        const x = basePositions[i]
        const z = basePositions[i + 1]
        positions[i + 2] = (
          Math.sin(x * 0.34 + time) * 0.22
          + Math.cos(z * 0.42 - time * 0.72) * 0.19
          + Math.sin((x + z) * 0.22 + time * 0.5) * 0.1
        ) * props.amplitude
      }
      geometry.attributes.position.needsUpdate = true
      geometry.computeVertexNormals()
      waveInitialized = true
    }
    if (!lowPower && !motionQuery?.matches) {
      pointerPosition.lerp(pointerTarget, 0.035)
      camera.position.x = baseCameraPosition.x + pointerPosition.x * 0.5
      camera.position.y = baseCameraPosition.y - pointerPosition.y * 0.25
      camera.lookAt(0, -1, 0)
    }

    renderer.render(scene, camera)
    if (!lowPower && !motionQuery?.matches) {
      animationFrame = requestAnimationFrame(renderFrame)
    }
  }

  const requestRender = () => {
    if (!animationFrame && !document.hidden && inView) {
      animationFrame = requestAnimationFrame(renderFrame)
    }
  }
  const renderStaticFrame = () => {
    if (!renderer || document.hidden || !inView) return
    if (!waveInitialized) {
      for (let i = 0; i < positions.length; i += 3) {
        const x = basePositions[i]
        const z = basePositions[i + 1]
        positions[i + 2] = (
          Math.sin(x * 0.34 + 0.75)
          + Math.cos(z * 0.42 - 0.54) * 0.86
          + Math.sin((x + z) * 0.22 + 0.375) * 0.45
        ) * 0.22 * props.amplitude
      }
      geometry.attributes.position.needsUpdate = true
      geometry.computeVertexNormals()
      waveInitialized = true
    }
    renderer.render(scene, camera)
  }

  resizeHandler = () => {
    if (!renderer) return
    const width = Math.max(element.clientWidth, 1)
    const height = Math.max(element.clientHeight, 1)
    renderer.setSize(width, height, false)
    camera.aspect = width / height
    camera.updateProjectionMatrix()
    requestRender()
  }

  if (typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(resizeHandler)
    resizeObserver.observe(element)
  } else {
    window.addEventListener('resize', resizeHandler)
  }

  pointerMoveHandler = (event) => {
    if (lowPower || event.pointerType === 'touch') return
    const bounds = element.getBoundingClientRect()
    const isInside = event.clientX >= bounds.left && event.clientX <= bounds.right
      && event.clientY >= bounds.top && event.clientY <= bounds.bottom
    pointerTarget.set(isInside ? (event.clientX / window.innerWidth - 0.5) * 2 : 0,
      isInside ? (event.clientY / window.innerHeight - 0.5) * 2 : 0)
  }
  pointerLeaveHandler = () => pointerTarget.set(0, 0)
  window.addEventListener('pointermove', pointerMoveHandler, { passive: true })

  visibilityHandler = () => {
    if (document.hidden) {
      cancelAnimationFrame(animationFrame)
      animationFrame = 0
    } else {
      requestRender()
    }
  }
  motionHandler = () => {
    if (motionQuery?.matches) {
      cancelAnimationFrame(animationFrame)
      animationFrame = 0
      renderStaticFrame()
      return
    }
    requestRender()
  }
  document.addEventListener('visibilitychange', visibilityHandler)
  motionQuery.addEventListener?.('change', motionHandler)
  if (typeof IntersectionObserver !== 'undefined') {
    intersectionObserver = new IntersectionObserver(([entry]) => {
      inView = Boolean(entry?.isIntersecting)
      if (inView) requestRender()
      else {
        cancelAnimationFrame(animationFrame)
        animationFrame = 0
      }
    })
    intersectionObserver.observe(element)
  }
  if (lowPower || motionQuery.matches) renderStaticFrame()
  resizeHandler()
})

onUnmounted(() => {
  cancelAnimationFrame(animationFrame)
  if (resizeHandler) window.removeEventListener('resize', resizeHandler)
  resizeObserver?.disconnect()
  intersectionObserver?.disconnect()
  if (visibilityHandler) document.removeEventListener('visibilitychange', visibilityHandler)
  if (motionQuery && motionHandler) motionQuery.removeEventListener?.('change', motionHandler)
  if (pointerMoveHandler) window.removeEventListener('pointermove', pointerMoveHandler)
  geometry?.dispose()
  surfaceMaterial?.dispose()
  wireMaterial?.dispose()
  renderer?.dispose()
  renderer?.forceContextLoss()
  renderer?.domElement.remove()
})
</script>

<template>
  <div ref="host" class="workflow-scene" />
</template>

<style scoped>
.workflow-scene {
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.workflow-scene :deep(canvas) {
  display: block;
  width: 100%;
  height: 100%;
}
</style>
