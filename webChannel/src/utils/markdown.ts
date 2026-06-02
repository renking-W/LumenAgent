import { marked } from 'marked'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'

// 自定义 marked renderer 实现代码高亮
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
}

marked.use({ renderer })

export function renderMarkdown(text: string): string {
  return marked.parse(text, { breaks: true, gfm: true }) as string
}
