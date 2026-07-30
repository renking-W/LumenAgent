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
    // 语言名称同时用于高亮类名和代码块顶部标签，仅保留安全字符。
    const safeLanguage = language.replace(/[^a-zA-Z0-9_+-]/g, '')
    const langClass = safeLanguage ? ` language-${safeLanguage}` : ''
    const languageLabel = safeLanguage || 'code'
    return `<pre class="hljs-pre" data-language="${languageLabel}"><code class="hljs${langClass}">${highlighted}</code></pre>`
  },
  link({ href, title, text }: import('marked').Tokens.Link) {
    const titleAttr = title ? ` title="${title}"` : ''
    return `<a href="${href}" target="_blank" rel="noopener noreferrer"${titleAttr}>${text}</a>`
  },
}

marked.use({ renderer })

export function renderMarkdown(text: string): string {
  return marked.parse(text, { breaks: true, gfm: true }) as string
}
