<template>
  <div class="knowledge-page">
    <!-- ======== 紧凑顶栏 ======== -->
    <div class="knowledge-header">
      <div class="knowledge-header-left">
        <div class="knowledge-kicker">Knowledge Base</div>
        <h2>知识库管理</h2>
      </div>
      <div class="knowledge-header-stats">
        <div class="knowledge-stat">
          <span class="knowledge-stat-value">{{ documents.length }}</span>
          <span class="knowledge-stat-label">文档数</span>
        </div>
        <span class="knowledge-stat-div"></span>
        <div class="knowledge-stat">
          <span class="knowledge-stat-value">{{ totalChunks }}</span>
          <span class="knowledge-stat-label">Chunks</span>
        </div>
        <span class="knowledge-stat-div"></span>
        <div class="knowledge-stat">
          <span class="knowledge-stat-value">{{ collections.length }}</span>
          <span class="knowledge-stat-label">集合</span>
        </div>
      </div>
      <div class="knowledge-header-actions">
        <el-button size="small" type="primary" @click="openIngestDialog">＋ 入库</el-button>
        <el-button size="small" plain @click="openSearchDialog">🔍 检索</el-button>
        <el-popconfirm
          title="确定重建索引？"
          confirm-button-text="确定"
          cancel-button-text="取消"
          @confirm="handleRebuild"
        >
          <template #reference>
            <el-button size="small" plain :loading="rebuilding" :disabled="rebuilding">⟳ 重建</el-button>
          </template>
        </el-popconfirm>
        <el-button size="small" plain @click="fetchData" :loading="loading">⟳</el-button>
      </div>
    </div>

    <!-- 操作结果提示 -->
    <div v-if="actionResult" class="knowledge-result" :class="actionResult.type">
      {{ actionResult.message }}
    </div>

    <!-- ======== 加载 / 空状态 ======== -->
    <div v-if="loading && !documents.length" class="empty-state">
      <p>加载中...</p>
    </div>
    <div v-else-if="!documents.length" class="empty-state">
      <div class="empty-icon">📚</div>
      <h3>暂无知识文档</h3>
      <p>点击「＋ 知识入库」添加你的第一个知识文档</p>
    </div>

    <!-- ======== 文档表格 ======== -->
    <div v-else class="knowledge-table-wrap">
      <table class="knowledge-table">
        <thead>
          <tr>
            <th class="col-name">文件名</th>
            <th class="col-source">来源</th>
            <th class="col-status">状态</th>
            <th class="col-chunks">切片</th>
            <th class="col-time">创建时间</th>
            <th class="col-actions">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="doc in documents" :key="doc.knowledge_id + '-' + doc.file_name" class="knowledge-row">
            <td class="col-name">
              <span class="knowledge-row-name">{{ doc.file_name }}</span>
              <span class="knowledge-row-id">{{ doc.knowledge_id }}</span>
            </td>
            <td class="col-source">{{ doc.source_name || '-' }}</td>
            <td class="col-status">
              <el-tag :type="doc.status === 'indexed' ? 'success' : 'info'" effect="light" size="small">
                {{ doc.status }}
              </el-tag>
            </td>
            <td class="col-chunks">{{ doc.chunk_count }}</td>
            <td class="col-time">{{ formatTime(doc.created_at) }}</td>
            <td class="col-actions">
              <el-button size="small" type="primary" plain @click="showDocumentDetail(doc)">详情</el-button>
              <el-popconfirm
                title="确定删除此文档？"
                confirm-button-text="删除"
                cancel-button-text="取消"
                @confirm="handleDeleteDocument(doc)"
              >
                <template #reference>
                  <el-button size="small" type="danger" plain @click.stop>删除</el-button>
                </template>
              </el-popconfirm>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ======== 文档详情弹窗 ======== -->
    <el-dialog
      v-model="detailDialogVisible"
      :title="'📄 ' + (selectedDoc?.file_name || '文档详情')"
      width="760px"
      destroy-on-close
      class="doc-dialog"
    >
      <template v-if="selectedDocDetail">
        <div class="dialog-section">
          <h4 class="dialog-label">基本信息</h4>
          <div class="dialog-info-grid">
            <div class="dialog-info-item">
              <span class="dialog-info-key">文件名</span>
              <span class="dialog-info-val">{{ selectedDocDetail.file_name }}</span>
            </div>
            <div class="dialog-info-item">
              <span class="dialog-info-key">来源</span>
              <span class="dialog-info-val">{{ selectedDocDetail.source_name || '-' }}</span>
            </div>
            <div class="dialog-info-item">
              <span class="dialog-info-key">状态</span>
              <el-tag :type="selectedDocDetail.status === 'indexed' ? 'success' : 'info'" effect="light" size="small">
                {{ selectedDocDetail.status }}
              </el-tag>
            </div>
            <div class="dialog-info-item">
              <span class="dialog-info-key">切片数</span>
              <span class="dialog-info-val">{{ selectedDocDetail.chunk_count }}</span>
            </div>
          </div>
        </div>

        <div class="dialog-section">
          <h4 class="dialog-label">
            切片详情
            <span class="chunk-count-badge">{{ selectedDocDetail.chunks.length }} 个切片</span>
          </h4>
          <div v-if="selectedDocDetail.chunks.length === 0" class="no-chunks">
            暂无切片数据
          </div>
          <div v-else class="chunks-list">
            <div
              v-for="chunk in selectedDocDetail.chunks"
              :key="chunk.chunk_index"
              class="chunk-item"
            >
              <div class="chunk-header">
                <span class="chunk-index">#{{ chunk.chunk_index + 1 }}</span>
                <span class="chunk-pos">字符 {{ chunk.start_char }} - {{ chunk.end_char }}</span>
              </div>
              <div class="chunk-content">{{ chunk.content_preview || chunk.content }}</div>
              <div class="chunk-footer">
                <span class="chunk-meta">{{ chunk.file_name }} · {{ formatTime(chunk.created_at) }}</span>
                <el-button size="small" text type="primary" @click="expandChunk(chunk)">查看完整内容</el-button>
              </div>
            </div>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- ======== Chunk 完整内容弹窗 ======== -->
    <el-dialog v-model="chunkDialogVisible" title="切片完整内容" width="640px" destroy-on-close>
      <pre class="chunk-full-content">{{ expandedChunkContent }}</pre>
    </el-dialog>

    <!-- ======== 知识入库弹窗 ======== -->
    <el-dialog
      v-model="ingestDialogVisible"
      title="知识入库"
      width="560px"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <el-form ref="ingestFormRef" :model="ingestForm" :rules="ingestFormRules" label-position="top" class="knowledge-form">
        <el-form-item label="文本内容" prop="text">
          <div class="ingest-textarea-wrapper">
            <el-input v-model="ingestForm.text" type="textarea" :autosize="{ minRows: 6, maxRows: 16 }" placeholder="输入要入库的知识文本内容，或点击下方按钮选择文件…" />
            <div class="ingest-file-actions">
              <input ref="fileInputRef" type="file" style="display: none" @change="onFileSelected" />
              <el-button type="default" @click="triggerFileSelect"><span class="btn-icon">📎</span> 选择文件</el-button>
              <span v-if="selectedFileName" class="ingest-file-name">已选择：{{ selectedFileName }}<el-button size="small" text type="info" @click="clearSelectedFile">清除</el-button></span>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="来源名称（可选）" prop="source_name">
          <el-input v-model="ingestForm.source_name" placeholder="例如：技术文档、项目说明" />
        </el-form-item>
        <el-form-item label="知识编号（可选）" prop="knowledge_id">
          <el-input v-model="ingestForm.knowledge_id" placeholder="留空自动生成" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ingestDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="ingesting" @click="submitIngest">提交入库</el-button>
      </template>
    </el-dialog>

    <!-- ======== 检索弹窗 ======== -->
    <el-dialog v-model="searchDialogVisible" title="检索知识库" width="680px" destroy-on-close>
      <el-form :model="searchForm" label-position="top" class="knowledge-form" @keydown.enter.prevent="submitSearch">
        <el-form-item label="查询内容" prop="query">
          <el-input v-model="searchForm.query" placeholder="输入检索关键词..." autofocus />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="返回条数">
              <el-input-number v-model="searchForm.top_k" :min="1" :max="50" :step="5" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="相似度阈值">
              <el-input-number v-model="searchForm.similarity_threshold" :min="0.0" :max="1.0" :step="0.05" :precision="2" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <div v-if="searchResults" class="search-results">
        <div class="search-results-header">共命中 {{ searchResults.chunks.length }} 条结果</div>
        <div v-for="(chunk, idx) in searchResults.chunks" :key="idx" class="search-chunk">
          <div class="search-chunk-header">
            <span class="search-chunk-score">相似度: {{ (chunk.score * 100).toFixed(1) }}%</span>
            <span class="search-chunk-meta">{{ chunk.metadata?.source_name || chunk.metadata?.file_name || '-' }}</span>
          </div>
          <div class="search-chunk-text">{{ chunk.text }}</div>
        </div>
      </div>

      <template #footer>
        <el-button @click="searchDialogVisible = false">关闭</el-button>
        <el-button type="primary" :loading="searching" @click="submitSearch">检索</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import type {
  KnowledgeDocumentSummary,
  KnowledgeDocumentDetail,
  KnowledgeChunkDetail,
  KnowledgeSearchResponse,
  KnowledgeIngestResponse,
} from '../types'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

const loading = ref(false)
const documents = ref<KnowledgeDocumentSummary[]>([])
const collections = ref<string[]>([])
const rebuilding = ref(false)
const actionResult = ref<{ type: string; message: string } | null>(null)

const totalChunks = computed(() =>
  documents.value.reduce((sum, d) => sum + d.chunk_count, 0)
)

const detailDialogVisible = ref(false)
const selectedDocDetail = ref<KnowledgeDocumentDetail | null>(null)
const selectedDoc = ref<KnowledgeDocumentSummary | null>(null)

const chunkDialogVisible = ref(false)
const expandedChunkContent = ref('')

const ingestDialogVisible = ref(false)
const ingesting = ref(false)
const ingestFormRef = ref<FormInstance | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const selectedFileName = ref('')
const selectedFile = ref<File | null>(null)

const ingestForm = reactive({
  text: '',
  source_name: '',
  knowledge_id: '',
})
const ingestFormRules: FormRules = {}

const resetIngestForm = () => {
  ingestForm.text = ''
  ingestForm.source_name = ''
  ingestForm.knowledge_id = ''
  selectedFileName.value = ''
  selectedFile.value = null
}

const triggerFileSelect = () => {
  fileInputRef.value?.click()
}

const onFileSelected = (e: Event) => {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  selectedFileName.value = file.name
  selectedFile.value = file
  if (!ingestForm.source_name) ingestForm.source_name = file.name
  input.value = ''
}

const clearSelectedFile = () => {
  selectedFileName.value = ''
  selectedFile.value = null
}

const searchDialogVisible = ref(false)
const searching = ref(false)
const searchResults = ref<KnowledgeSearchResponse | null>(null)
const searchForm = reactive({ query: '', top_k: 10, similarity_threshold: 0.0 })

const fetchCollections = async () => {
  try {
    const res = await fetch('/v1/knowledge/collections')
    if (res.ok) {
      const data = await res.json()
      collections.value = data.collections || []
    }
  } catch { /* 静默 */ }
}

const fetchDocuments = async () => {
  try {
    const res = await fetch('/v1/knowledge/documents')
    if (res.ok) documents.value = await res.json()
  } catch { ElMessage.error('获取文档列表失败') }
}

const fetchData = async () => {
  loading.value = true
  actionResult.value = null
  await Promise.all([fetchDocuments(), fetchCollections()])
  loading.value = false
}

const showDocumentDetail = async (doc: KnowledgeDocumentSummary) => {
  selectedDoc.value = doc
  selectedDocDetail.value = null
  detailDialogVisible.value = true
  try {
    const res = await fetch(`/v1/knowledge/documents/${doc.knowledge_id}/${doc.file_name}`)
    if (res.ok) selectedDocDetail.value = await res.json()
    else ElMessage.error('获取文档详情失败')
  } catch { ElMessage.error('网络错误') }
}

const expandChunk = (chunk: KnowledgeChunkDetail) => {
  expandedChunkContent.value = chunk.content
  chunkDialogVisible.value = true
}

const handleDeleteDocument = async (doc: KnowledgeDocumentSummary) => {
  try {
    const res = await fetch(`/v1/knowledge/${doc.knowledge_id}/${doc.file_name}`, { method: 'DELETE' })
    if (res.ok) {
      documents.value = documents.value.filter((d) => d.knowledge_id !== doc.knowledge_id || d.file_name !== doc.file_name)
      ElMessage.success('文档已删除')
    } else ElMessage.error('删除失败')
  } catch { ElMessage.error('网络错误') }
}

const openIngestDialog = () => { resetIngestForm(); ingestDialogVisible.value = true }

const submitIngest = async () => {
  const valid = await ingestFormRef.value?.validate().catch(() => false)
  if (!valid) return
  if (!ingestForm.text.trim() && !selectedFile.value) { ElMessage.warning('请输入文本内容或选择文件'); return }
  ingesting.value = true
  actionResult.value = null
  try {
    const payload: Record<string, unknown> = {}
    if (selectedFile.value) {
      const formData = new FormData()
      formData.append('file', selectedFile.value)
      const uploadRes = await fetch('/v1/upload', { method: 'POST', body: formData })
      if (!uploadRes.ok) throw new Error(await uploadRes.text())
      const uploaded: { path: string } = await uploadRes.json()
      payload.file_path = uploaded.path
    } else {
      payload.text = ingestForm.text
    }
    if (ingestForm.source_name.trim()) payload.source_name = ingestForm.source_name
    if (ingestForm.knowledge_id.trim()) payload.knowledge_id = ingestForm.knowledge_id
    const res = await fetch('/v1/knowledge/ingest', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
    if (res.ok) {
      const data: KnowledgeIngestResponse = await res.json()
      actionResult.value = { type: 'success', message: `入库成功：${data.source_name}，新增 ${data.chunks_added} 个切片，集合: ${data.collection_name}` }
      ingestDialogVisible.value = false
      await fetchData()
    } else {
      const err = await res.text()
      actionResult.value = { type: 'error', message: `入库失败: ${err}` }
    }
  } catch (error) {
    const detail = error instanceof Error ? error.message : '网络错误'
    actionResult.value = { type: 'error', message: `入库失败：${detail}` }
  }
  finally { ingesting.value = false }
}

const openSearchDialog = () => {
  searchForm.query = ''; searchForm.top_k = 10; searchForm.similarity_threshold = 0.0
  searchResults.value = null; searchDialogVisible.value = true
}

const submitSearch = async () => {
  if (!searchForm.query.trim()) { ElMessage.warning('请输入查询内容'); return }
  searching.value = true; searchResults.value = null
  try {
    const res = await fetch('/v1/knowledge/search', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query: searchForm.query, top_k: searchForm.top_k, similarity_threshold: searchForm.similarity_threshold || undefined }) })
    if (res.ok) searchResults.value = await res.json()
    else ElMessage.error('检索失败')
  } catch { ElMessage.error('网络错误') }
  finally { searching.value = false }
}

const handleRebuild = async () => {
  rebuilding.value = true; actionResult.value = null
  try {
    const res = await fetch('/v1/knowledge/rebuild', { method: 'DELETE' })
    if (res.ok) { const data = await res.json(); actionResult.value = { type: 'success', message: `索引重建完成：${data.detail}` }; await fetchData() }
    else actionResult.value = { type: 'error', message: '重建索引失败' }
  } catch { actionResult.value = { type: 'error', message: '网络错误' } }
  finally { rebuilding.value = false }
}

const formatTime = (iso: string) => {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

defineExpose({ fetchData })
onMounted(fetchData)
</script>

<style scoped>
.knowledge-page {
  padding: var(--space-5) var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-height: 100%;
}

/* ── 紧凑顶栏 ── */
.knowledge-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5);
  background: var(--color-white);
  border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-2xl);
  box-shadow: var(--shadow-sm);
}
.knowledge-header-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.knowledge-kicker {
  font-size: 0.7rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-gold-600);
  font-weight: 600;
}
.knowledge-header-left h2 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--color-navy-900);
}
.knowledge-header-stats {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.knowledge-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
}
.knowledge-stat-value {
  font-size: 1rem;
  font-weight: 700;
  color: var(--color-navy-800);
}
.knowledge-stat-label {
  font-size: 0.68rem;
  color: var(--color-slate-400);
}
.knowledge-stat-div {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: var(--color-slate-300);
}
.knowledge-header-actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}

/* ── 操作结果 ── */
.knowledge-result {
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-lg);
  font-size: 0.9rem;
  line-height: 1.5;
}
.knowledge-result.success {
  background: var(--color-success-bg);
  border: 1px solid #A7F3D0;
  color: #065F46;
}
.knowledge-result.error {
  background: var(--color-error-bg);
  border: 1px solid #FECACA;
  color: #991B1B;
}

/* ── 表格 ── */
.knowledge-table-wrap {
  flex: 1;
  overflow-y: auto;
  background: var(--color-white);
  border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-sm);
}
.knowledge-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}
.knowledge-table th {
  text-align: left;
  padding: var(--space-3) var(--space-4);
  font-weight: 600;
  color: var(--color-slate-500);
  background: var(--color-slate-50);
  border-bottom: 1px solid var(--color-slate-200);
  white-space: nowrap;
  position: sticky;
  top: 0;
  z-index: 1;
}
.knowledge-table td {
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-slate-100);
  color: var(--color-navy-700);
}
.knowledge-table tbody tr:hover {
  background: var(--color-slate-50);
}
.knowledge-table tbody tr:last-child td {
  border-bottom: none;
}

.col-name { min-width: 200px; }
.col-source { min-width: 120px; }
.col-status { width: 80px; }
.col-chunks { width: 60px; text-align: center; }
.col-time { width: 140px; }
.col-actions { width: 150px; }

.knowledge-row-name {
  display: block;
  font-weight: 600;
  color: var(--color-navy-900);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.knowledge-row-id {
  font-size: 0.75rem;
  color: var(--color-slate-400);
  font-family: var(--font-mono);
}
.col-source { color: var(--color-slate-500); }
.col-chunks { text-align: center; font-weight: 600; color: var(--color-navy-800); }
.col-time { color: var(--color-slate-400); font-size: 0.82rem; white-space: nowrap; }
.col-actions { white-space: nowrap; }
.col-actions .el-button + .el-button { margin-left: 6px; }

/* ── 空状态 ── */
.empty-state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 48px; color: var(--color-slate-400); gap: var(--space-2);
  border: 2px dashed var(--color-slate-200); border-radius: var(--radius-2xl); background: var(--color-white);
}
.empty-icon { font-size: 2.5rem; }
.empty-state h3 { margin: 0; color: var(--color-slate-500); font-weight: 600; }
.empty-state p { margin: 0; font-size: 0.9rem; color: var(--color-slate-400); }

/* ── 表单 ── */
.knowledge-form { margin-top: var(--space-2); }

.ingest-textarea-wrapper { width: 100%; }
.ingest-file-actions { display: flex; align-items: center; gap: var(--space-3); margin-top: var(--space-3); }
.ingest-file-name { font-size: 0.85rem; color: var(--color-slate-500); display: flex; align-items: center; gap: 6px; }
.btn-icon { font-style: normal; }

/* ── 检索结果 ── */
.search-results { margin-top: var(--space-4); border-top: 1px solid var(--color-slate-200); padding-top: var(--space-4); }
.search-results-header { font-size: 0.85rem; font-weight: 600; color: var(--color-slate-500); margin-bottom: var(--space-3); }
.search-chunk { padding: var(--space-3) var(--space-4); border: 1px solid var(--color-slate-200); border-radius: var(--radius-lg); margin-bottom: var(--space-3); background: var(--color-slate-50); }
.search-chunk-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; font-size: 0.82rem; }
.search-chunk-score { color: var(--color-success); font-weight: 600; }
.search-chunk-meta { color: var(--color-slate-400); }
.search-chunk-text { font-size: 0.85rem; color: var(--color-navy-700); line-height: 1.6; display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; line-clamp: 4; }

/* ── 弹窗 ── */
.dialog-section { margin-bottom: var(--space-5); }
.dialog-label { font-size: 0.9rem; color: var(--color-navy-900); margin: 0 0 var(--space-2); font-weight: 600; display: flex; align-items: center; gap: var(--space-2); }
.chunk-count-badge { font-size: 0.75rem; font-weight: 400; color: var(--color-slate-400); background: var(--color-slate-100); padding: 2px 8px; border-radius: var(--radius-full); }
.dialog-info-grid { display: flex; flex-direction: column; gap: var(--space-3); }
.dialog-info-item { display: flex; align-items: center; gap: var(--space-3); }
.dialog-info-key { font-size: 0.85rem; color: var(--color-slate-400); min-width: 80px; flex-shrink: 0; }
.dialog-info-val { color: var(--color-navy-800); }
.no-chunks { padding: var(--space-6); text-align: center; color: var(--color-slate-400); border: 1px dashed var(--color-slate-200); border-radius: var(--radius-lg); }
.chunks-list { max-height: 480px; overflow-y: auto; }
.chunk-item { border: 1px solid var(--color-slate-200); border-radius: var(--radius-lg); background: var(--color-white); }
.chunk-item + .chunk-item { margin-top: var(--space-3); }
.chunk-header { display: flex; justify-content: space-between; align-items: center; padding: var(--space-2) var(--space-3); background: var(--color-slate-50); border-bottom: 1px solid var(--color-slate-200); font-size: 0.82rem; }
.chunk-index { font-weight: 700; color: var(--color-gold-600); }
.chunk-pos { color: var(--color-slate-400); font-size: 0.78rem; }
.chunk-content { padding: var(--space-3); font-size: 0.85rem; line-height: 1.6; color: var(--color-navy-700); max-height: 200px; overflow-y: auto; }
.chunk-footer { display: flex; justify-content: space-between; align-items: center; padding: 6px 12px; border-top: 1px solid var(--color-slate-100); background: #FAFAFA; }
.chunk-meta { font-size: 0.75rem; color: var(--color-slate-400); }
.chunk-full-content { margin: 0; padding: var(--space-4); background: var(--color-slate-50); border: 1px solid var(--color-slate-200); border-radius: var(--radius-lg); max-height: 480px; overflow: auto; white-space: pre-wrap; word-break: break-word; font-size: 0.85rem; line-height: 1.7; color: var(--color-navy-800); }

@media (max-width: 768px) {
  .knowledge-table-wrap { overflow-x: auto; }
  .knowledge-header { flex-direction: column; align-items: stretch; }
  .knowledge-header-stats { justify-content: center; }
  .knowledge-header-actions { justify-content: center; }
}
</style>
