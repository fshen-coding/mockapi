<script setup>
// 参考 React Bits 的 ClickSpark：点击处向外迸出短线火花，画在全屏固定的 canvas 上，不拦截指针事件。
import { onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({
  color: { type: String, default: '#1f6c9f' },
  size: { type: Number, default: 10 },
  radius: { type: Number, default: 18 },
  count: { type: Number, default: 8 },
  duration: { type: Number, default: 420 },
})

const canvasRef = ref(null)
let sparks = []
let frame = 0
let ctx = null
let motionQuery = null
let motionHandler = null

const easeOut = (t) => t * (2 - t)

function resize() {
  const canvas = canvasRef.value
  if (!canvas) return
  const dpr = window.devicePixelRatio || 1
  canvas.width = window.innerWidth * dpr
  canvas.height = window.innerHeight * dpr
  ctx = canvas.getContext('2d')
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
}

function draw(now) {
  if (!ctx) return
  ctx.clearRect(0, 0, window.innerWidth, window.innerHeight)
  sparks = sparks.filter((spark) => {
    const t = (now - spark.start) / props.duration
    if (t >= 1) return false
    const eased = easeOut(t)
    const distance = eased * props.radius
    const length = props.size * (1 - eased)
    const x1 = spark.x + distance * Math.cos(spark.angle)
    const y1 = spark.y + distance * Math.sin(spark.angle)
    const x2 = spark.x + (distance + length) * Math.cos(spark.angle)
    const y2 = spark.y + (distance + length) * Math.sin(spark.angle)
    ctx.strokeStyle = props.color
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.moveTo(x1, y1)
    ctx.lineTo(x2, y2)
    ctx.stroke()
    return true
  })
  frame = sparks.length ? requestAnimationFrame(draw) : 0
}

function onClick(event) {
  if (event.pointerType === 'touch' || motionQuery?.matches) return
  const now = performance.now()
  for (let i = 0; i < props.count; i += 1) {
    sparks.push({ x: event.clientX, y: event.clientY, angle: (2 * Math.PI * i) / props.count, start: now })
  }
  if (!frame) frame = requestAnimationFrame(draw)
}

onMounted(() => {
  motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
  motionHandler = () => {
    if (!motionQuery.matches) return
    sparks = []
    if (frame) cancelAnimationFrame(frame)
    frame = 0
  }
  motionQuery.addEventListener?.('change', motionHandler)
  resize()
  window.addEventListener('resize', resize)
  document.addEventListener('pointerdown', onClick, { passive: true })
})

onBeforeUnmount(() => {
  if (motionQuery && motionHandler) motionQuery.removeEventListener?.('change', motionHandler)
  window.removeEventListener('resize', resize)
  document.removeEventListener('pointerdown', onClick)
  if (frame) cancelAnimationFrame(frame)
})
</script>

<template>
  <canvas ref="canvasRef" class="click-spark-layer" aria-hidden="true" />
</template>

<style scoped>
.click-spark-layer {
  position: fixed;
  inset: 0;
  width: 100vw;
  height: 100vh;
  z-index: 9999;
  pointer-events: none;
}
</style>
