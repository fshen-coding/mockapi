import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

gsap.registerPlugin(ScrollTrigger)

const VIEW_ROOTS = '.tool-page-view, .workspace-grid, .interface-test-view, .ai-page-view'
const REVEAL_TARGETS = '.surface-card, .prompt-template-card, .environment-card, .usage-log-stat'

export const prefersReducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

let motionContext = null
let revealTriggers = []
let revealTargets = []
let refreshFrame = 0
let layoutObserver = null

function scheduleRefresh() {
  if (refreshFrame) return
  refreshFrame = requestAnimationFrame(() => {
    refreshFrame = 0
    ScrollTrigger.refresh()
  })
}

function killReveals() {
  revealTriggers.forEach((trigger) => trigger.kill())
  revealTriggers = []
  if (revealTargets.length) gsap.killTweensOf(revealTargets)
  revealTargets = []
  motionContext?.revert()
  motionContext = null
  layoutObserver?.disconnect()
  layoutObserver = null
  if (refreshFrame) cancelAnimationFrame(refreshFrame)
  refreshFrame = 0
}

// 视图切换完成后，为当前内容中的主要区域安装一次性滚动揭示。
export function playViewEnter(scope) {
  killReveals()
  if (prefersReducedMotion()) return
  const root = scope?.querySelector ? scope : document.querySelector(VIEW_ROOTS)
  if (!root) return

  const view = root.matches?.(VIEW_ROOTS) ? root : root.querySelector(VIEW_ROOTS) || root
  motionContext = gsap.context(() => {
    revealTargets = Array.from(view.querySelectorAll(REVEAL_TARGETS))
    if (!revealTargets.length) return

    gsap.set(revealTargets, { autoAlpha: 0, y: 10 })
    revealTriggers = ScrollTrigger.batch(revealTargets, {
      start: 'top 90%',
      once: true,
      interval: 0.08,
      batchMax: 4,
      onEnter: (batch) => gsap.to(batch, {
        autoAlpha: 1,
        y: 0,
        duration: 0.48,
        ease: 'power3.out',
        stagger: 0.06,
        clearProps: 'opacity,visibility,transform',
        overwrite: 'auto',
      }),
    })
  }, view)

  // 面板展开/收起会改变页面高度，触发位置必须随之重算，否则移回视口的元素会一直保持隐藏。
  if (revealTriggers.length && typeof ResizeObserver !== 'undefined') {
    layoutObserver = new ResizeObserver(scheduleRefresh)
    layoutObserver.observe(view)
  }
  scheduleRefresh()
}

// 卡片聚光：把指针位置写进 CSS 变量，由 style.css 里的 ::before 渲染光斑。
export function installSpotlight() {
  if (prefersReducedMotion()) return () => {}
  let frame = 0
  let latestEvent = null
  const onMove = (event) => {
    if (event.pointerType === 'touch') return
    latestEvent = event
    if (frame) return
    frame = requestAnimationFrame(() => {
      frame = 0
      const pointerEvent = latestEvent
      latestEvent = null
      const card = pointerEvent?.target?.closest?.('.surface-card, .prompt-template-card, .environment-card')
      if (!card) return
      const rect = card.getBoundingClientRect()
      card.style.setProperty('--spot-x', `${pointerEvent.clientX - rect.left}px`)
      card.style.setProperty('--spot-y', `${pointerEvent.clientY - rect.top}px`)
    })
  }
  document.addEventListener('pointermove', onMove, { passive: true })
  return () => {
    document.removeEventListener('pointermove', onMove)
    if (frame) cancelAnimationFrame(frame)
  }
}

export function disposeMotion() {
  killReveals()
}
