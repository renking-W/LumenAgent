import { marked } from 'marked'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'

// 自定义 marked renderer 实现代码高亮 & 链接新标签打开
const renderer: Partial<import('marked').MarkedExtension['renderer']> = {
  code({ text, lang }: { text: string; lang?: string; escaped?: boolean }) {
    const language = lang || ''
    let highlighted: string
    try {
      highlighted = language
        ? hljs.highlight(text, { language, ignoreIllegals: true }).value
        : hljs.highlightAuto(text).value
    } catch {
      highlighted = text
    }
    const langClass = language ? ` language-${language}` : ''
    return `<pre class="hljs-pre"><code class="hljs${langClass}">${highlighted}</code></pre>`
  },
  link({ href, title, text }: { href: string; title?: string; text: string }) {
    const titleAttr = title ? ` title="${title}"` : ''
    return `<a href="${href}" target="_blank" rel="noopener noreferrer"${titleAttr}>${text}</a>`
  },
}

marked.use({ renderer })

export function renderMarkdown(text: string): string {
  return marked.parse(text, { breaks: true, gfm: true }) as string
}
