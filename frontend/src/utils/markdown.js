import { Marked } from 'marked'

const SAFE_URL = /^(https?:|mailto:|#|\/)/i

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function safeUrl(href) {
  const value = String(href ?? '').trim()
  return SAFE_URL.test(value) ? value : ''
}

const COPY_ICON = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>'

// AI 回复不可信：原始 HTML 一律转义，链接和图片只放行 http(s)/mailto/站内地址。
const markdown = new Marked({ breaks: true, gfm: true })
markdown.use({
  renderer: {
    html({ text }) {
      return escapeHtml(text)
    },
    link({ href, title, tokens }) {
      const text = this.parser.parseInline(tokens)
      const url = safeUrl(href)
      if (!url) return text
      const titleAttr = title ? ` title="${escapeHtml(title)}"` : ''
      return `<a href="${escapeHtml(url)}"${titleAttr} target="_blank" rel="noopener noreferrer">${text}</a>`
    },
    image({ href, title, text }) {
      const url = safeUrl(href)
      if (!url) return escapeHtml(text)
      const titleAttr = title ? ` title="${escapeHtml(title)}"` : ''
      return `<img src="${escapeHtml(url)}" alt="${escapeHtml(text)}"${titleAttr}>`
    },
    code({ text, lang }) {
      const label = escapeHtml((lang || 'plaintext').split(/\s+/)[0])
      return `<div class="chat-code-block"><div class="chat-code-header"><span class="chat-code-lang">${label}</span><button type="button" class="chat-code-copy" data-code="${encodeURIComponent(text)}">${COPY_ICON} 复制</button></div><pre class="chat-code-pre"><code>${escapeHtml(text)}</code></pre></div>`
    },
  },
})

export function renderMarkdown(text) {
  if (!text) return ''
  // 解码 JSON unicode 转义序列（如 \u003d → =）和字面 \n，让粘贴的 JSON 字符串可读
  const decoded = text
    .replace(/\\u([0-9a-fA-F]{4})/g, (_, h) => String.fromCharCode(parseInt(h, 16)))
    .replace(/\\n/g, '\n')
    .replace(/\\t/g, '\t')
  return markdown.parse(decoded)
}
