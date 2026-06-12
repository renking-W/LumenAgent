<template>
  <div class="skill-page">
    <!-- ======== 紧凑顶栏 ======== -->
    <div class="skill-header">
      <div class="skill-header-left">
        <div class="skill-kicker">Agent Skills</div>
        <h2>技能能力总览</h2>
      </div>
      <div class="skill-header-stats">
        <div class="skill-stat">
          <span class="skill-stat-value">{{ skills.length }}</span>
          <span class="skill-stat-label">技能总数</span>
        </div>
        <div class="skill-stat-divider"></div>
        <div class="skill-stat">
          <span class="skill-stat-value ok">{{ availableSkillsCount }}</span>
          <span class="skill-stat-label">可用</span>
        </div>
        <div class="skill-stat-divider"></div>
        <div class="skill-stat">
          <span class="skill-stat-value warn">{{ skills.length - availableSkillsCount }}</span>
          <span class="skill-stat-label">缺失环境</span>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="skills.length === 0" class="empty-state">
      <div class="empty-icon">🎯</div>
      <h3>暂无可用技能</h3>
      <p>当前没有注册的 Skill，去添加 SKILL 配置吧~</p>
    </div>

    <template v-else>
      <!-- 可用技能 -->
      <section v-if="availableSkills.length > 0" class="skill-section">
        <div class="skill-section-header">
          <span class="skill-section-dot dot-available"></span>
          <span class="skill-section-title">可用技能</span>
          <span class="skill-section-count">{{ availableSkills.length }}</span>
        </div>
        <div class="skill-grid-cols-3">
          <article v-for="skill in availableSkills" :key="skill.path" class="skill-card">
            <div class="skill-card-top">
              <h3 class="skill-card-name">{{ skill.emoji || '•' }} {{ skill.name }}</h3>
              <el-tag size="small" type="success" effect="light">可用</el-tag>
            </div>
            <p class="skill-card-desc">{{ skill.description }}</p>
            <div class="skill-card-meta">
              <span class="skill-meta-key">路径</span>
              <span class="skill-meta-val">{{ skill.path }}</span>
            </div>
            <div class="skill-card-actions">
              <el-button size="small" type="primary" plain @click="showSkillDetail(skill)">
                查看详情
              </el-button>
            </div>
          </article>
        </div>
      </section>

      <!-- 缺失环境的技能 -->
      <section v-if="missingSkills.length > 0" class="skill-section">
        <div class="skill-section-header">
          <span class="skill-section-dot dot-missing"></span>
          <span class="skill-section-title">缺失环境</span>
          <span class="skill-section-count">{{ missingSkills.length }}</span>
        </div>
        <div class="skill-grid-cols-2">
          <article v-for="skill in missingSkills" :key="skill.path" class="skill-card skill-card--missing">
            <div class="skill-card-top">
              <h3 class="skill-card-name">{{ skill.emoji || '•' }} {{ skill.name }}</h3>
              <el-tag size="small" type="info" effect="light">缺失环境</el-tag>
            </div>
            <p class="skill-card-desc">{{ skill.description }}</p>
            <div class="skill-card-meta">
              <span class="skill-meta-key">缺失环境</span>
              <span class="skill-meta-val skill-missing-val">{{ skill.missing_envs?.join(', ') }}</span>
            </div>
            <div v-if="skill.primary_env" class="skill-card-meta">
              <span class="skill-meta-key">主环境</span>
              <span class="skill-meta-val">{{ skill.primary_env }}</span>
            </div>
            <div class="skill-card-actions">
              <el-button size="small" type="primary" plain @click="showSkillDetail(skill)">
                查看详情
              </el-button>
            </div>
          </article>
        </div>
      </section>
    </template>

    <el-dialog
      v-model="skillDialogVisible"
      :title="selectedSkill?.emoji ? selectedSkill.emoji + ' ' : '' + (selectedSkill?.name || '技能详情')"
      width="640px"
      destroy-on-close
    >
      <template v-if="selectedSkill">
        <div class="dialog-section">
          <h4 class="dialog-label">完整描述</h4>
          <p class="dialog-text">{{ selectedSkill.description }}</p>
        </div>
        <div class="dialog-section">
          <h4 class="dialog-label">基本信息</h4>
          <div class="dialog-info-grid">
            <div class="dialog-info-item">
              <span class="dialog-info-key">路径</span>
              <span class="dialog-info-val">{{ selectedSkill.path }}</span>
            </div>
            <div class="dialog-info-item">
              <span class="dialog-info-key">可用状态</span>
              <el-tag :type="selectedSkill.available ? 'success' : 'info'" effect="light" size="small">
                {{ selectedSkill.available ? '可用' : '缺失环境' }}
              </el-tag>
            </div>
            <div class="dialog-info-item">
              <span class="dialog-info-key">主环境</span>
              <span class="dialog-info-val">{{ selectedSkill.primary_env || '无' }}</span>
            </div>
            <div class="dialog-info-item">
              <span class="dialog-info-key">依赖环境</span>
              <span class="dialog-info-val">{{ selectedSkill.requires_env?.length ? selectedSkill.requires_env.join(', ') : '无' }}</span>
            </div>
            <div v-if="selectedSkill.missing_envs?.length" class="dialog-info-item">
              <span class="dialog-info-key">缺失环境</span>
              <span class="dialog-info-val missing-val">{{ selectedSkill.missing_envs.join(', ') }}</span>
            </div>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { SkillInfo } from '../types'

const props = defineProps<{
  skills: SkillInfo[]
}>()

const availableSkills = computed(() => props.skills.filter((item) => item.available))
const missingSkills = computed(() => props.skills.filter((item) => !item.available))
const availableSkillsCount = computed(() => availableSkills.value.length)

const skillDialogVisible = ref(false)
const selectedSkill = ref<SkillInfo | null>(null)

const showSkillDetail = (skill: SkillInfo) => {
  selectedSkill.value = skill
  skillDialogVisible.value = true
}
</script>

<style scoped>
.skill-page {
  padding: var(--space-5) var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  min-height: 100%;
}

/* ── 紧凑顶栏 ── */
.skill-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-4) var(--space-5);
  background: var(--color-white);
  border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-2xl);
  box-shadow: var(--shadow-sm);
}
.skill-header-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.skill-kicker {
  font-size: 0.7rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-gold-600);
  font-weight: 600;
}
.skill-header-left h2 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--color-navy-900);
}
.skill-header-stats {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}
.skill-stat {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}
.skill-stat-value {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--color-navy-800);
}
.skill-stat-value.ok { color: var(--color-success); }
.skill-stat-value.warn { color: var(--color-warning); }
.skill-stat-label {
  font-size: 0.72rem;
  color: var(--color-slate-400);
}
.skill-stat-divider {
  width: 1px;
  height: 32px;
  background: var(--color-slate-200);
}

/* ── 分组 ── */
.skill-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.skill-section-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) 0;
}
.skill-section-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
.dot-available { background: var(--color-success); }
.dot-missing { background: var(--color-warning); }
.skill-section-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--color-navy-800);
}
.skill-section-count {
  font-size: 0.78rem;
  color: var(--color-slate-400);
  background: var(--color-slate-100);
  padding: 1px 8px;
  border-radius: var(--radius-full);
}

/* ── 网格 ── */
.skill-grid-cols-3 {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-3);
}
.skill-grid-cols-2 {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-3);
}
.skill-card {
  background: var(--color-white);
  border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-xl);
  padding: var(--space-4);
  box-shadow: var(--shadow-xs);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  transition: all var(--transition-normal);
}
.skill-card:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--color-gold-200);
  transform: translateY(-1px);
}
.skill-card--missing {
  border-color: var(--color-slate-100);
  background: var(--color-slate-50);
  opacity: 0.85;
}
.skill-card--missing:hover {
  opacity: 1;
}
.skill-card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-2);
}
.skill-card-name {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--color-navy-900);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.skill-card-desc {
  margin: 0;
  font-size: 0.82rem;
  color: var(--color-slate-500);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-clamp: 2;
}
.skill-card-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.skill-meta-key {
  font-size: 0.72rem;
  color: var(--color-slate-400);
}
.skill-meta-val {
  font-size: 0.82rem;
  color: var(--color-navy-700);
  word-break: break-all;
}
.skill-missing-val {
  color: #C2410C;
  font-weight: 500;
}
.skill-card-actions {
  display: flex;
  gap: var(--space-2);
  padding-top: var(--space-1);
  border-top: 1px solid var(--color-slate-100);
}

/* ── 弹窗 ── */
.dialog-section { margin-bottom: var(--space-5); }
.dialog-label { font-size: 0.9rem; color: var(--color-navy-900); margin: 0 0 var(--space-2); font-weight: 600; }
.dialog-text { color: var(--color-slate-500); line-height: 1.7; white-space: pre-wrap; }
.dialog-info-grid { display: flex; flex-direction: column; gap: var(--space-3); }
.dialog-info-item { display: flex; align-items: center; gap: var(--space-3); }
.dialog-info-key { font-size: 0.85rem; color: var(--color-slate-400); min-width: 80px; flex-shrink: 0; }
.dialog-info-val { color: var(--color-navy-800); }
.missing-val { color: #C2410C; }

/* ── 空状态 ── */
.empty-state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 64px 24px; color: var(--color-slate-400); gap: var(--space-2);
  border: 2px dashed var(--color-slate-200); border-radius: var(--radius-2xl); background: var(--color-white);
}
.empty-icon { font-size: 3rem; }
.empty-state h3 { margin: 0; color: var(--color-slate-500); font-weight: 600; font-size: 1.1rem; }
.empty-state p { margin: 0; font-size: 0.9rem; color: var(--color-slate-400); }
</style>
