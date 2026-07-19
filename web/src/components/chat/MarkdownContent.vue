<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import hljs from 'highlight.js/lib/core'
import javascript from 'highlight.js/lib/languages/javascript'
import typescript from 'highlight.js/lib/languages/typescript'
import python from 'highlight.js/lib/languages/python'
import java from 'highlight.js/lib/languages/java'
import go from 'highlight.js/lib/languages/go'
import sql from 'highlight.js/lib/languages/sql'
import bash from 'highlight.js/lib/languages/bash'
import json from 'highlight.js/lib/languages/json'
import yaml from 'highlight.js/lib/languages/yaml'
import xml from 'highlight.js/lib/languages/xml'
import css from 'highlight.js/lib/languages/css'

// 只注册常见语言,控制包体积;xml 同时覆盖 html
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('js', javascript)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('ts', typescript)
hljs.registerLanguage('python', python)
hljs.registerLanguage('py', python)
hljs.registerLanguage('java', java)
hljs.registerLanguage('go', go)
hljs.registerLanguage('sql', sql)
hljs.registerLanguage('bash', bash)
hljs.registerLanguage('sh', bash)
hljs.registerLanguage('shell', bash)
hljs.registerLanguage('json', json)
hljs.registerLanguage('yaml', yaml)
hljs.registerLanguage('yml', yaml)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('html', xml)
hljs.registerLanguage('css', css)

const props = withDefaults(
  defineProps<{
    content: string
    streaming?: boolean
  }>(),
  { streaming: false },
)

const md: MarkdownIt = new MarkdownIt({
  // 禁原生 HTML,配合 DOMPurify 双保险防 XSS
  html: false,
  linkify: true,
  breaks: true,
  highlight(str: string, lang: string): string {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return (
          '<pre class="hljs"><code>' +
          hljs.highlight(str, { language: lang, ignoreIllegals: true }).value +
          '</code></pre>'
        )
      } catch {
        // fall through to escaped output
      }
    }
    return '<pre class="hljs"><code>' + md.utils.escapeHtml(str) + '</code></pre>'
  },
})

// 链接统一新窗口打开并防 reverse tabnabbing
const defaultLinkOpen =
  md.renderer.rules.link_open ??
  ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options))
md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  tokens[idx].attrSet('target', '_blank')
  tokens[idx].attrSet('rel', 'noopener noreferrer')
  return defaultLinkOpen(tokens, idx, options, env, self)
}

// 表格外包一层容器,用于横向滚动
md.renderer.rules.table_open = () => '<div class="md-table-wrap"><table>'
md.renderer.rules.table_close = () => '</table></div>'

/**
 * 流式输出可能截断在代码围栏中间,
 * 临时补一个闭合围栏,避免整段内容在渲染时抖动成代码块。
 */
function normalizeStreaming(src: string): string {
  const fences = src.match(/```/g)
  if (fences && fences.length % 2 === 1) return src + '\n```'
  return src
}

function render(src: string): string {
  const input = props.streaming ? normalizeStreaming(src) : src
  const raw = md.render(input)
  return DOMPurify.sanitize(raw, { ADD_ATTR: ['target', 'rel'] })
}

const html = ref('')
let timer: ReturnType<typeof setTimeout> | undefined

// 流式中做 120ms 防抖降级,避免每个 token 都全量重解析造成抖动;非流式立即渲染
watch(
  () => [props.content, props.streaming] as const,
  () => {
    if (props.streaming) {
      clearTimeout(timer)
      timer = setTimeout(() => {
        html.value = render(props.content)
      }, 120)
    } else {
      clearTimeout(timer)
      html.value = render(props.content)
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => clearTimeout(timer))
</script>

<template>
  <!-- eslint-disable-next-line vue/no-v-html : 内容已经过 DOMPurify 净化 -->
  <div class="markdown-body" v-html="html" />
</template>

<style scoped>
.markdown-body {
  font-size: inherit;
  line-height: inherit;
  word-break: break-word;
}
.markdown-body > :deep(*:first-child) {
  margin-top: 0;
}
.markdown-body > :deep(*:last-child) {
  margin-bottom: 0;
}

/* ===== 标题 ===== */
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4) {
  margin: var(--space-4) 0 var(--space-2);
  color: var(--text-primary);
  font-weight: 700;
  line-height: 1.4;
}
.markdown-body :deep(h1) {
  font-size: var(--font-size-lg);
  padding-bottom: var(--space-1);
  border-bottom: 1px solid var(--border-subtle);
}
.markdown-body :deep(h2) {
  font-size: var(--font-size-md);
}
.markdown-body :deep(h3) {
  font-size: var(--font-size-base);
}
.markdown-body :deep(h4) {
  font-size: var(--font-size-sm);
}

/* ===== 段落与列表 ===== */
.markdown-body :deep(p) {
  margin: 0 0 var(--space-3);
}
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 0 0 var(--space-3);
  padding-left: var(--space-5);
}
.markdown-body :deep(li) {
  margin-bottom: var(--space-1);
}
.markdown-body :deep(li > ul),
.markdown-body :deep(li > ol) {
  margin: var(--space-1) 0 0;
}

/* ===== 表格 ===== */
.markdown-body :deep(.md-table-wrap) {
  margin: 0 0 var(--space-3);
  overflow-x: auto;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
}
.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);
}
.markdown-body :deep(th),
.markdown-body :deep(td) {
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-subtle);
  text-align: left;
  white-space: nowrap;
}
.markdown-body :deep(th) {
  background: var(--bg-3);
  color: var(--text-primary);
  font-weight: 600;
}
.markdown-body :deep(tbody tr:nth-child(even)) {
  background: var(--bg-1);
}
.markdown-body :deep(tbody tr:last-child td) {
  border-bottom: none;
}

/* ===== 代码块与行内代码 ===== */
.markdown-body :deep(pre) {
  margin: 0 0 var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--bg-0);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  overflow-x: auto;
}
.markdown-body :deep(pre code) {
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  line-height: 1.6;
  color: var(--text-secondary);
  background: transparent;
  padding: 0;
}
.markdown-body :deep(code) {
  font-family: var(--font-mono);
  font-size: 0.9em;
  background: var(--bg-3);
  border-radius: var(--radius-sm);
  padding: 2px 5px;
}

/* ===== 引用块 ===== */
.markdown-body :deep(blockquote) {
  margin: 0 0 var(--space-3);
  padding: 2px 0 2px var(--space-3);
  border-left: 3px solid var(--accent);
  color: var(--text-secondary);
}
.markdown-body :deep(blockquote p:last-child) {
  margin-bottom: 0;
}

/* ===== 链接 / 分隔线 / 强调 ===== */
.markdown-body :deep(a) {
  color: var(--accent-hover);
  text-decoration: none;
}
.markdown-body :deep(a:hover) {
  text-decoration: underline;
}
.markdown-body :deep(hr) {
  margin: var(--space-4) 0;
  border: none;
  border-top: 1px solid var(--border-default);
}
.markdown-body :deep(strong) {
  color: var(--text-primary);
  font-weight: 700;
}
.markdown-body :deep(img) {
  max-width: 100%;
}

/* ===== highlight.js 语法着色(全部映射到设计 token) ===== */
.markdown-body :deep(.hljs-keyword),
.markdown-body :deep(.hljs-selector-tag),
.markdown-body :deep(.hljs-built_in) {
  color: var(--accent-hover);
}
.markdown-body :deep(.hljs-string),
.markdown-body :deep(.hljs-regexp) {
  color: var(--success);
}
.markdown-body :deep(.hljs-number),
.markdown-body :deep(.hljs-literal) {
  color: var(--warning);
}
.markdown-body :deep(.hljs-comment),
.markdown-body :deep(.hljs-quote) {
  color: var(--text-tertiary);
  font-style: italic;
}
.markdown-body :deep(.hljs-title),
.markdown-body :deep(.hljs-name),
.markdown-body :deep(.hljs-section) {
  color: var(--text-primary);
}
.markdown-body :deep(.hljs-attr),
.markdown-body :deep(.hljs-attribute),
.markdown-body :deep(.hljs-variable),
.markdown-body :deep(.hljs-type) {
  color: var(--notice);
}
</style>
