<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({
  src: { type: String, default: '/intro.mp4' },
  storageKey: { type: String, default: 'mockapi-intro-seen' },
  maxDuration: { type: Number, default: 7000 },
})

const visible = ref(false)
const leaving = ref(false)
const videoRef = ref(null)
let fallbackTimer = 0
let leaveTimer = 0

function shouldPlay() {
  try {
    if (window.localStorage.getItem(props.storageKey)) return false
  } catch {
    return false
  }
  return !(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false)
}

function finish() {
  if (!visible.value || leaving.value) return
  try {
    window.localStorage.setItem(props.storageKey, '1')
  } catch {}
  window.clearTimeout(fallbackTimer)
  leaving.value = true
  leaveTimer = window.setTimeout(() => {
    visible.value = false
  }, 500)
}

function onKeydown(event) {
  if (event.key === 'Escape' || event.key === 'Enter' || event.key === ' ') finish()
}

onMounted(() => {
  if (!shouldPlay()) return
  visible.value = true
  fallbackTimer = window.setTimeout(finish, props.maxDuration)
  window.addEventListener('keydown', onKeydown)
  requestAnimationFrame(() => {
    const video = videoRef.value
    if (!video) return
    video.muted = true
    video.play()?.catch(finish)
  })
})

onBeforeUnmount(() => {
  window.clearTimeout(fallbackTimer)
  window.clearTimeout(leaveTimer)
  window.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div v-if="visible" class="intro-splash" :class="{ 'is-leaving': leaving }" role="presentation">
    <video
      ref="videoRef"
      class="intro-splash__video"
      :src="src"
      muted
      playsinline
      autoplay
      preload="auto"
      aria-hidden="true"
      @ended="finish"
      @error="finish"
    />
    <button type="button" class="intro-splash__skip" @click="finish">跳过</button>
  </div>
</template>

<style scoped>
.intro-splash {
  position: fixed;
  inset: 0;
  z-index: 10000;
  background: #eef2fb;
  opacity: 1;
  transition: opacity 0.5s ease;
}

.intro-splash.is-leaving {
  opacity: 0;
  pointer-events: none;
}

.intro-splash__video {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center;
  display: block;
}

.intro-splash__skip {
  position: absolute;
  right: 24px;
  bottom: 24px;
  padding: 6px 16px;
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: 999px;
  background: rgba(15, 30, 55, 0.35);
  color: #fff;
  font-size: 13px;
  letter-spacing: 0.08em;
  cursor: pointer;
  backdrop-filter: blur(6px);
  transition: background 0.2s ease;
}

.intro-splash__skip:hover,
.intro-splash__skip:focus-visible {
  background: rgba(15, 30, 55, 0.6);
  outline: none;
}
</style>
