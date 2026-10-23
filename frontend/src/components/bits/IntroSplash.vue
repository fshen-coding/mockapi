<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({
  storageKey: { type: String, default: 'mockapi-intro-seen-v5' },
  maxDuration: { type: Number, default: 4200 },
})

const visible = ref(false)
const leaving = ref(false)
const progress = ref(0)

let fallbackTimer = 0
let leaveTimer = 0
let progressFrame = 0
let progressStartedAt = 0

// WebGL state
let gl = null
let canvas = null
let program = null
let rafId = 0
let startTime = 0
let uniforms = {}
let textTexture = null
let textCanvas = null
let textCtx = null

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
  window.cancelAnimationFrame(progressFrame)
  leaving.value = true
  leaveTimer = window.setTimeout(() => {
    visible.value = false
    cleanupWebGL()
  }, 700)
}

function updateProgress(now) {
  if (!visible.value || leaving.value) return
  progress.value = Math.min(1, Math.max(0, (now - progressStartedAt) / Math.max(1, props.maxDuration)))
  if (progress.value >= 1) {
    finish()
    return
  }
  progressFrame = window.requestAnimationFrame(updateProgress)
}

function onKeydown(event) {
  if (event.key === 'Escape' || event.key === 'Enter' || event.key === ' ') finish()
}

// --- Draw "Mockapi" text into offscreen canvas → WebGL texture ---
function drawTextTexture(width, height) {
  if (!textCanvas) {
    textCanvas = document.createElement('canvas')
    textCtx = textCanvas.getContext('2d')
  }
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  textCanvas.width = width * dpr
  textCanvas.height = height * dpr
  textCtx.scale(dpr, dpr)

  const W = width
  const H = height
  const isMobile = W < 768 || W / H < 1

  // Background: light blue-white gradient
  const bgGrad = textCtx.createLinearGradient(0, 0, 0, H)
  bgGrad.addColorStop(0, '#f5f7fd')
  bgGrad.addColorStop(1, '#e8eef9')
  textCtx.fillStyle = bgGrad
  textCtx.fillRect(0, 0, W, H)

  // Subtle grid
  textCtx.strokeStyle = 'rgba(100,140,220,0.07)'
  textCtx.lineWidth = 0.5
  const gridSize = 40
  for (let x = 0; x <= W; x += gridSize) {
    textCtx.beginPath()
    textCtx.moveTo(x, 0)
    textCtx.lineTo(x, H)
    textCtx.stroke()
  }
  for (let y = 0; y <= H; y += gridSize) {
    textCtx.beginPath()
    textCtx.moveTo(0, y)
    textCtx.lineTo(W, y)
    textCtx.stroke()
  }

  // Big text "Mockapi" — split into two lines like reference "Explore/New/Ideas"
  const lines = isMobile ? ['Mock', 'api'] : ['Mock', 'api']
  let fs = Math.min(H * (isMobile ? 0.32 : 0.28), W * (isMobile ? 0.28 : 0.22))
  textCtx.font = `800 ${fs}px 'Geist Variable', 'Inter', system-ui, sans-serif`

  // Measure widest line
  let maxW = 0
  for (const line of lines) {
    const m = textCtx.measureText(line)
    if (m.width > maxW) maxW = m.width
  }
  const maxAllowed = W * (isMobile ? 0.85 : 0.55)
  if (maxW > maxAllowed) {
    fs *= maxAllowed / maxW
    textCtx.font = `800 ${fs}px 'Geist Variable', 'Inter', system-ui, sans-serif`
  }

  const cx = W * (isMobile ? 0.5 : 0.48)
  const cy = H * (isMobile ? 0.42 : 0.44)
  const lineGap = fs * 1.02
  const capH = fs * 0.7

  textCtx.textAlign = 'center'
  textCtx.textBaseline = 'alphabetic'

  lines.forEach((line, i) => {
    const baselineY = cy + capH / 2 + (i - (lines.length - 1) / 2) * lineGap

    // Stroke outline
    textCtx.strokeStyle = 'rgba(30,80,180,0.18)'
    textCtx.lineWidth = 1.5
    textCtx.strokeText(line, cx, baselineY)

    // Fill gradient
    const grad = textCtx.createLinearGradient(cx - fs, baselineY - capH, cx + fs, baselineY)
    grad.addColorStop(0, '#1a56c4')
    grad.addColorStop(0.5, '#2874e8')
    grad.addColorStop(1, '#5b8df0')
    textCtx.fillStyle = grad
    textCtx.fillText(line, cx, baselineY)
  })

  return textCanvas
}

function updateTextTexture() {
  if (!gl) return
  const src = drawTextTexture(window.innerWidth, window.innerHeight)
  if (textTexture) {
    gl.bindTexture(gl.TEXTURE_2D, textTexture)
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, src)
  }
}

// --- Shaders ---
const VERT_SRC = `
attribute vec3 aPos;
attribute vec3 aNormal;
uniform mat4 uModel;
uniform mat4 uView;
uniform mat4 uProj;
varying vec3 vNormal;
varying vec3 vWorldPos;
void main() {
  vec4 worldPos = uModel * vec4(aPos, 1.0);
  vWorldPos = worldPos.xyz;
  vNormal = normalize(mat3(uModel) * aNormal);
  gl_Position = uProj * uView * worldPos;
}
`

const FRAG_SRC = `
precision highp float;
uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uTime;
uniform vec3 uCamera;
varying vec3 vNormal;
varying vec3 vWorldPos;

void main() {
  vec2 uv = gl_FragCoord.xy / uResolution;
  vec3 n = normalize(vNormal);
  vec3 viewDir = normalize(uCamera - vWorldPos);

  // Chromatic dispersion — 6-band IOR
  float iorR = 1.15, iorY = 1.16, iorG = 1.18, iorC = 1.22, iorB = 1.22, iorP = 1.22;
  float refractPower = 0.35;
  float chromatic = 0.6;

  vec3 refrR = refract(-viewDir, n, 1.0 / iorR);
  vec3 refrY = refract(-viewDir, n, 1.0 / iorY);
  vec3 refrG = refract(-viewDir, n, 1.0 / iorG);
  vec3 refrC = refract(-viewDir, n, 1.0 / iorC);
  vec3 refrB = refract(-viewDir, n, 1.0 / iorB);
  vec3 refrP = refract(-viewDir, n, 1.0 / iorP);

  vec2 uvR = uv + refrR.xy * refractPower * chromatic;
  vec2 uvY = uv + refrY.xy * refractPower * chromatic;
  vec2 uvG = uv + refrG.xy * refractPower * chromatic;
  vec2 uvC = uv + refrC.xy * refractPower * chromatic * 1.2;
  vec2 uvB = uv + refrB.xy * refractPower * chromatic * 1.4;
  vec2 uvP = uv + refrP.xy * refractPower * chromatic;

  float r = texture2D(uTexture, uvR).r * 0.5;
  float y = (texture2D(uTexture, uvY).r * 2.0 + texture2D(uTexture, uvY).g * 2.0 - texture2D(uTexture, uvY).b) / 6.0;
  float g = texture2D(uTexture, uvG).g * 0.5;
  float c = (texture2D(uTexture, uvC).g * 2.0 + texture2D(uTexture, uvC).b * 2.0 - texture2D(uTexture, uvC).r) / 6.0;
  float b = texture2D(uTexture, uvB).b * 0.5;
  float p = (texture2D(uTexture, uvP).b * 2.0 + texture2D(uTexture, uvP).r * 2.0 - texture2D(uTexture, uvP).g) / 6.0;

  float R = r + (2.0 * p + 2.0 * y - c) / 3.0;
  float G = g + (2.0 * y + 2.0 * c - p) / 3.0;
  float B = b + (2.0 * c + 2.0 * p - y) / 3.0;

  vec3 color = vec3(R, G, B);

  // Saturation boost
  float luma = dot(color, vec3(0.2125, 0.7154, 0.0721));
  color = mix(vec3(luma), color, 1.1);

  // Specular — Blinn-Phong
  vec3 light1 = normalize(vec3(-0.6, 0.8, 0.5));
  vec3 h1 = normalize(light1 + viewDir);
  float spec1 = pow(max(dot(n, h1), 0.0), 80.0);
  spec1 += max(0.0, dot(n, light1)) * 0.02;

  vec3 light2 = normalize(vec3(0.7, -0.3, 0.6));
  vec3 h2 = normalize(light2 + viewDir);
  float spec2 = pow(max(dot(n, h2), 0.0), 50.0) * 0.5;
  spec2 += max(0.0, dot(n, light2)) * 0.01 * 0.5;

  color += (spec1 + spec2) * vec3(1.0);

  // Fresnel rim
  float fres = pow(1.0 - abs(dot(viewDir, n)), 5.0);
  color = mix(color, vec3(1.0), fres * 0.6);

  // Slight blue edge tint
  color += vec3(0.1, 0.18, 0.4) * fres * 0.15;

  gl_FragColor = vec4(color, 1.0);
}
`

// Background quad shader (fullscreen, draws the text texture)
const BG_VERT_SRC = `
attribute vec2 aPos;
varying vec2 vUv;
void main() {
  vUv = aPos * 0.5 + 0.5;
  gl_Position = vec4(aPos, 0.0, 1.0);
}
`

const BG_FRAG_SRC = `
precision highp float;
uniform sampler2D uTexture;
varying vec2 vUv;
void main() {
  vec3 color = texture2D(uTexture, vUv).rgb;
  gl_FragColor = vec4(color, 1.0);
}
`

function createShader(gl, type, src) {
  const s = gl.createShader(type)
  gl.shaderSource(s, src)
  gl.compileShader(s)
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
    console.error('Shader error:', gl.getShaderInfoLog(s))
    return null
  }
  return s
}

function createProgram(gl, vsSrc, fsSrc) {
  const vs = createShader(gl, gl.VERTEX_SHADER, vsSrc)
  const fs = createShader(gl, gl.FRAGMENT_SHADER, fsSrc)
  if (!vs || !fs) return null
  const p = gl.createProgram()
  gl.attachShader(p, vs)
  gl.attachShader(p, fs)
  gl.linkProgram(p)
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) {
    console.error('Link error:', gl.getProgramInfoLog(p))
    return null
  }
  return p
}

// Matrix helpers
function mat4Perspective(fov, aspect, near, far) {
  const f = 1 / Math.tan(fov / 2)
  const nf = 1 / (near - far)
  return new Float32Array([
    f / aspect, 0, 0, 0,
    0, f, 0, 0,
    0, 0, (far + near) * nf, -1,
    0, 0, 2 * far * near * nf, 0,
  ])
}

function mat4LookAt(eye, center, up) {
  const [ex, ey, ez] = eye
  const [cx, cy, cz] = center
  const [ux, uy, uz] = up
  let fx = cx - ex, fy = cy - ey, fz = cz - ez
  const fl = Math.sqrt(fx * fx + fy * fy + fz * fz)
  fx /= fl; fy /= fl; fz /= fl
  let rx = fy * uz - fz * uy, ry = fz * ux - fx * uz, rz = fx * uy - fy * ux
  const rl = Math.sqrt(rx * rx + ry * ry + rz * rz)
  rx /= rl; ry /= rl; rz /= rl
  const ux2 = fy * rz - fz * ry, uy2 = fz * rx - fx * rz, uz2 = fx * ry - fy * rx
  return new Float32Array([
    rx, ux2, -fx, 0,
    ry, uy2, -fy, 0,
    rz, uz2, -fz, 0,
    -(rx * ex + ry * ey + rz * ez),
    -(ux2 * ex + uy2 * ey + uz2 * ez),
    (fx * ex + fy * ey + fz * ez), 1,
  ])
}

function mat4RotateY(angle) {
  const c = Math.cos(angle), s = Math.sin(angle)
  return new Float32Array([c, 0, -s, 0, 0, 1, 0, 0, s, 0, c, 0, 0, 0, 0, 1])
}

function mat4RotateX(angle) {
  const c = Math.cos(angle), s = Math.sin(angle)
  return new Float32Array([1, 0, 0, 0, 0, c, s, 0, 0, -s, c, 0, 0, 0, 0, 1])
}

function mat4Multiply(a, b) {
  const r = new Float32Array(16)
  for (let i = 0; i < 4; i++) {
    for (let j = 0; j < 4; j++) {
      r[j * 4 + i] = a[i] * b[j * 4] + a[4 + i] * b[j * 4 + 1] + a[8 + i] * b[j * 4 + 2] + a[12 + i] * b[j * 4 + 3]
    }
  }
  return r
}

// Build rounded box geometry
function buildRoundedCube(size, segments, radius) {
  const positions = []
  const normals = []
  const indices = []
  const half = size / 2
  const inner = half - radius

  const faces = [
    { n: [0, 0, 1], u: [1, 0, 0], v: [0, 1, 0] },
    { n: [0, 0, -1], u: [-1, 0, 0], v: [0, 1, 0] },
    { n: [1, 0, 0], u: [0, 0, -1], v: [0, 1, 0] },
    { n: [-1, 0, 0], u: [0, 0, 1], v: [0, 1, 0] },
    { n: [0, 1, 0], u: [1, 0, 0], v: [0, 0, -1] },
    { n: [0, -1, 0], u: [1, 0, 0], v: [0, 0, 1] },
  ]

  for (const face of faces) {
    const base = positions.length / 3
    const [nx, ny, nz] = face.n
    const [ux, uy, uz] = face.u
    const [vx, vy, vz] = face.v

    for (let j = 0; j <= segments; j++) {
      for (let i = 0; i <= segments; i++) {
        const fu = (i / segments) * 2 - 1
        const fv = (j / segments) * 2 - 1
        const cu = Math.max(-1, Math.min(1, fu))
        const cv = Math.max(-1, Math.min(1, fv))
        const du = fu - cu
        const dv = fv - cv
        const dist = Math.sqrt(du * du + dv * dv)
        const clampedDist = Math.min(dist, 1) * radius

        let px = nx * inner + ux * cu * inner + vx * cv * inner
        let py = ny * inner + uy * cu * inner + vy * cv * inner
        let pz = nz * inner + uz * cu * inner + vz * cv * inner

        if (dist > 0.001) {
          const offset = clampedDist / dist
          px += (ux * du + vx * dv) * offset
          py += (uy * du + vy * dv) * offset
          pz += (uz * du + vz * dv) * offset
        }

        positions.push(px, py, pz)

        let nx2 = nx, ny2 = ny, nz2 = nz
        if (dist > 0.001) {
          const nd = Math.sqrt(nx2 * nx2 + ny2 * ny2 + nz2 * nz2)
          nx2 /= nd; ny2 /= nd; nz2 /= nd
        }
        normals.push(nx2, ny2, nz2)
      }
    }

    for (let j = 0; j < segments; j++) {
      for (let i = 0; i < segments; i++) {
        const a = base + j * (segments + 1) + i
        const b = a + 1
        const c = a + segments + 1
        const d = c + 1
        indices.push(a, b, c, b, d, c)
      }
    }
  }

  return { positions, normals, indices }
}

// Cube buffers
let cubePosBuf, cubeNormBuf, cubeIdxBuf, cubeIndexCount
// BG quad buffers
let bgPosBuf

function initWebGL() {
  canvas = document.getElementById('intro-canvas')
  if (!canvas) return

  gl = canvas.getContext('webgl', { antialias: true, alpha: false })
  if (!gl) {
    console.warn('WebGL not supported')
    return
  }

  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  canvas.width = window.innerWidth * dpr
  canvas.height = window.innerHeight * dpr
  gl.viewport(0, 0, canvas.width, canvas.height)

  // --- Create text texture ---
  textTexture = gl.createTexture()
  gl.bindTexture(gl.TEXTURE_2D, textTexture)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR)

  const src = drawTextTexture(window.innerWidth, window.innerHeight)
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, src)

  // --- Cube program ---
  program = createProgram(gl, VERT_SRC, FRAG_SRC)
  if (!program) return

  // Build cube
  const { positions, normals, indices } = buildRoundedCube(2.4, 10, 0.18)
  cubeIndexCount = indices.length

  cubePosBuf = gl.createBuffer()
  gl.bindBuffer(gl.ARRAY_BUFFER, cubePosBuf)
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(positions), gl.STATIC_DRAW)

  cubeNormBuf = gl.createBuffer()
  gl.bindBuffer(gl.ARRAY_BUFFER, cubeNormBuf)
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(normals), gl.STATIC_DRAW)

  cubeIdxBuf = gl.createBuffer()
  gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, cubeIdxBuf)
  gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array(indices), gl.STATIC_DRAW)

  // --- Background program ---
  const bgProgram = createProgram(gl, BG_VERT_SRC, BG_FRAG_SRC)
  if (!bgProgram) return

  bgPosBuf = gl.createBuffer()
  gl.bindBuffer(gl.ARRAY_BUFFER, bgPosBuf)
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW)

  // Store both programs
  gl._cubeProgram = program
  gl._bgProgram = bgProgram

  // Get uniform locations for cube
  uniforms = {
    uModel: gl.getUniformLocation(program, 'uModel'),
    uView: gl.getUniformLocation(program, 'uView'),
    uProj: gl.getUniformLocation(program, 'uProj'),
    uTexture: gl.getUniformLocation(program, 'uTexture'),
    uResolution: gl.getUniformLocation(program, 'uResolution'),
    uTime: gl.getUniformLocation(program, 'uTime'),
    uCamera: gl.getUniformLocation(program, 'uCamera'),
  }

  gl._bgUniforms = {
    uTexture: gl.getUniformLocation(bgProgram, 'uTexture'),
  }

  startTime = performance.now()
  render()
}

function render() {
  if (!gl || !program) return
  rafId = requestAnimationFrame(render)

  const elapsed = (performance.now() - startTime) / 1000
  const W = canvas.width
  const H = canvas.height

  gl.viewport(0, 0, W, H)
  gl.clearColor(0.94, 0.96, 1.0, 1.0)
  gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT)

  // --- Draw background (text texture) ---
  const bgProgram = gl._bgProgram
  gl.useProgram(bgProgram)
  gl.disable(gl.DEPTH_TEST)

  gl.bindBuffer(gl.ARRAY_BUFFER, bgPosBuf)
  const bgAPos = gl.getAttribLocation(bgProgram, 'aPos')
  gl.enableVertexAttribArray(bgAPos)
  gl.vertexAttribPointer(bgAPos, 2, gl.FLOAT, false, 0, 0)

  gl.activeTexture(gl.TEXTURE0)
  gl.bindTexture(gl.TEXTURE_2D, textTexture)
  gl.uniform1i(gl._bgUniforms.uTexture, 0)

  gl.drawArrays(gl.TRIANGLES, 0, 3)

  // --- Draw cube with refraction ---
  gl.useProgram(program)
  gl.enable(gl.DEPTH_TEST)

  const aspect = W / H
  const proj = mat4Perspective(Math.PI / 6, aspect, 0.1, 100)
  const view = mat4LookAt([0, 0, 8], [0, 0, 0], [0, 1, 0])

  const rotY = elapsed * 0.3 + 0.6
  const rotX = Math.sin(elapsed * 0.2) * 0.12 + 0.2

  let model = mat4Multiply(mat4RotateY(rotY), mat4RotateX(rotX))
  const breathe = 1 + Math.sin(elapsed * 0.6) * 0.012
  const scaleM = new Float32Array([breathe, 0, 0, 0, 0, breathe, 0, 0, 0, 0, breathe, 0, 0, 0, 0, 1])
  model = mat4Multiply(model, scaleM)

  const aPos = gl.getAttribLocation(program, 'aPos')
  const aNormal = gl.getAttribLocation(program, 'aNormal')

  gl.bindBuffer(gl.ARRAY_BUFFER, cubePosBuf)
  gl.enableVertexAttribArray(aPos)
  gl.vertexAttribPointer(aPos, 3, gl.FLOAT, false, 0, 0)

  gl.bindBuffer(gl.ARRAY_BUFFER, cubeNormBuf)
  gl.enableVertexAttribArray(aNormal)
  gl.vertexAttribPointer(aNormal, 3, gl.FLOAT, false, 0, 0)

  gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, cubeIdxBuf)

  gl.uniformMatrix4fv(uniforms.uModel, false, model)
  gl.uniformMatrix4fv(uniforms.uView, false, view)
  gl.uniformMatrix4fv(uniforms.uProj, false, proj)
  gl.uniform2f(uniforms.uResolution, W, H)
  gl.uniform1f(uniforms.uTime, elapsed)
  gl.uniform3f(uniforms.uCamera, 0, 0, 8)

  gl.activeTexture(gl.TEXTURE0)
  gl.bindTexture(gl.TEXTURE_2D, textTexture)
  gl.uniform1i(uniforms.uTexture, 0)

  gl.drawElements(gl.TRIANGLES, cubeIndexCount, gl.UNSIGNED_SHORT, 0)
}

function cleanupWebGL() {
  if (rafId) cancelAnimationFrame(rafId)
  rafId = 0
  if (gl) {
    if (textTexture) gl.deleteTexture(textTexture)
    if (cubePosBuf) gl.deleteBuffer(cubePosBuf)
    if (cubeNormBuf) gl.deleteBuffer(cubeNormBuf)
    if (cubeIdxBuf) gl.deleteBuffer(cubeIdxBuf)
    if (bgPosBuf) gl.deleteBuffer(bgPosBuf)
    if (program) gl.deleteProgram(program)
    if (gl._bgProgram) gl.deleteProgram(gl._bgProgram)
  }
  gl = null
  program = null
  canvas = null
  textTexture = null
  textCanvas = null
  textCtx = null
}

function onResize() {
  if (!gl || !canvas) return
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  canvas.width = window.innerWidth * dpr
  canvas.height = window.innerHeight * dpr
  gl.viewport(0, 0, canvas.width, canvas.height)
  updateTextTexture()
}

onMounted(() => {
  if (!shouldPlay()) return
  visible.value = true
  fallbackTimer = window.setTimeout(finish, props.maxDuration + 900)
  window.addEventListener('keydown', onKeydown)
  window.addEventListener('resize', onResize)
  progressStartedAt = window.performance.now()
  progressFrame = window.requestAnimationFrame(updateProgress)

  // Wait for fonts then init WebGL
  if (document.fonts?.ready) {
    document.fonts.ready.then(() => {
      setTimeout(() => initWebGL(), 30)
    })
  } else {
    setTimeout(() => initWebGL(), 300)
  }
})

onBeforeUnmount(() => {
  window.clearTimeout(fallbackTimer)
  window.clearTimeout(leaveTimer)
  window.cancelAnimationFrame(progressFrame)
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('resize', onResize)
  cleanupWebGL()
})
</script>

<template>
  <div
    v-if="visible"
    class="intro-splash"
    :class="{ 'is-leaving': leaving }"
    :style="{ '--intro-duration': `${maxDuration}ms` }"
  >
    <!-- WebGL Canvas: draws text texture + refracting glass cube -->
    <canvas id="intro-canvas" class="intro-splash__canvas" aria-hidden="true"></canvas>

    <!-- UI Overlay -->
    <div class="intro-splash__ui">
      <header class="intro-splash__header">
      </header>

      <div class="intro-splash__tagline">
        <p class="intro-splash__tagline-main">测试 · 追踪 · 验证</p>
        <p class="intro-splash__tagline-sub">企业级 Mock 平台</p>
      </div>

      <div class="intro-splash__loader">
        <div class="intro-splash__loader-bar">
          <div class="intro-splash__loader-fill" :style="{ transform: `scaleX(${progress})` }"></div>
        </div>
        <span class="intro-splash__loader-text">INITIALIZING {{ Math.round(progress * 100) }}%</span>
      </div>

      <button type="button" class="intro-splash__skip" @click="finish">
        跳过 <span>→</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.intro-splash {
  --bg-primary: #f0f4fc;
  --ink-primary: #0f1f3d;
  --ink-secondary: #51617c;
  --accent-blue: #2874e8;
  --accent-violet: #7c68f0;

  position: fixed;
  inset: 0;
  z-index: 10000;
  overflow: hidden;
  isolation: isolate;
  color: var(--ink-primary);
  background: var(--bg-primary);
  opacity: 1;
  transition: opacity 700ms cubic-bezier(0.76, 0, 0.24, 1), filter 700ms cubic-bezier(0.76, 0, 0.24, 1);
}

.intro-splash.is-leaving {
  opacity: 0;
  filter: blur(12px);
  pointer-events: none;
}

.intro-splash__canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: block;
}

.intro-splash__ui {
  position: absolute;
  inset: 0;
  z-index: 4;
  pointer-events: none;
}

.intro-splash__ui > * {
  pointer-events: auto;
}

.intro-splash__header {
  position: absolute;
  top: clamp(20px, 4vh, 48px);
  left: clamp(20px, 4vw, 64px);
  right: clamp(20px, 4vw, 64px);
  display: flex;
  align-items: center;
  justify-content: space-between;
  animation: fade-in-down 0.8s 0.2s cubic-bezier(0.16, 1, 0.3, 1) both;
}

.intro-splash__logo {
  display: flex;
  align-items: center;
  gap: 10px;
}

.intro-splash__logo-mark {
  width: 32px;
  height: 32px;
  display: block;
}

.intro-splash__logo-mark svg {
  width: 100%;
  height: 100%;
}

.intro-splash__logo-text {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: -0.03em;
  color: var(--ink-primary);
}

.intro-splash__badge {
  font-family: 'Geist Mono', 'Cascadia Code', Consolas, monospace;
  font-size: 9px;
  font-weight: 650;
  letter-spacing: 0.14em;
  color: var(--ink-secondary);
  padding: 6px 12px;
  border: 1px solid rgba(100, 140, 220, 0.22);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.5);
  backdrop-filter: blur(8px);
}

.intro-splash__tagline {
  position: absolute;
  bottom: clamp(80px, 12vh, 140px);
  left: clamp(20px, 4vw, 64px);
  animation: fade-in-up 0.8s 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
}

.intro-splash__tagline-main {
  font-size: clamp(18px, 2vw, 26px);
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--ink-primary);
  margin: 0 0 6px 0;
}

.intro-splash__tagline-sub {
  font-size: clamp(13px, 1.2vw, 15px);
  font-weight: 450;
  color: var(--ink-secondary);
  margin: 0;
}

.intro-splash__loader {
  position: absolute;
  bottom: clamp(24px, 4vh, 48px);
  left: clamp(20px, 4vw, 64px);
  width: min(280px, 40vw);
  animation: fade-in-up 0.8s 0.7s cubic-bezier(0.16, 1, 0.3, 1) both;
}

.intro-splash__loader-bar {
  height: 3px;
  border-radius: 99px;
  background: rgba(100, 140, 220, 0.15);
  overflow: hidden;
  margin-bottom: 8px;
}

.intro-splash__loader-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--accent-blue), var(--accent-violet));
  transform-origin: left;
  transform: scaleX(0);
  transition: transform 100ms linear;
  box-shadow: 0 0 12px rgba(74, 142, 240, 0.4);
}

.intro-splash__loader-text {
  font-family: 'Geist Mono', 'Cascadia Code', Consolas, monospace;
  font-size: 9px;
  font-weight: 650;
  letter-spacing: 0.12em;
  color: var(--ink-secondary);
}

.intro-splash__skip {
  position: absolute;
  bottom: clamp(24px, 4vh, 48px);
  right: clamp(20px, 4vw, 64px);
  padding: 10px 20px;
  border: 1px solid rgba(100, 140, 220, 0.25);
  border-radius: 99px;
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(12px);
  color: var(--ink-primary);
  font-size: 12px;
  font-weight: 550;
  cursor: pointer;
  transition: all 0.2s ease;
  animation: fade-in-up 0.8s 0.4s cubic-bezier(0.16, 1, 0.3, 1) both;
}

.intro-splash__skip:hover {
  background: var(--accent-blue);
  color: white;
  border-color: var(--accent-blue);
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(40, 116, 232, 0.3);
}

.intro-splash__skip span {
  margin-left: 6px;
  transition: transform 0.2s ease;
}

.intro-splash__skip:hover span {
  transform: translateX(3px);
}

@keyframes fade-in-down {
  from { opacity: 0; transform: translateY(-16px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes fade-in-up {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 768px) {
  .intro-splash__badge {
    display: none;
  }
  .intro-splash__tagline {
    bottom: clamp(100px, 16vh, 160px);
    left: 50%;
    transform: translateX(-50%);
    text-align: center;
  }
  .intro-splash__loader {
    left: 50%;
    transform: translateX(-50%);
    text-align: center;
  }
}

@media (prefers-reduced-motion: reduce) {
  .intro-splash,
  .intro-splash *,
  .intro-splash *::before,
  .intro-splash *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
</style>
