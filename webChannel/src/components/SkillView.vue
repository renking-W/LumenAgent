<template>
  <div class="catalog-pane">
    <div class="hero-card">
      <div>
        <div class="hero-kicker">Agent Skills</div>
        <h2>技能能力总览</h2>
      </div>
      <div class="hero-stats">
        <div class="stat-box">
          <span class="stat-label">技能数量</span>
          <span class="stat-value">{{ skills.length }}</span>
        </div>
        <div class="stat-box">
          <span class="stat-label">可用技能</span>
          <span class="stat-value">{{ availableSkillsCount }}</span>
        </div>
      </div>
    </div>

    <div class="grid-cards">
      <article v-for="skill in skills" :key="skill.path" class="card">
        <div class="card-top">
          <div>
            <h3>{{ skill.emoji || '•' }} {{ skill.name }}</h3>
            <p>{{ skill.description }}</p>
          </div>
          <div class="card-top-actions">
            <el-tag :type="skill.available ? 'success' : 'info'" effect="light">
              {{ skill.available ? '可用' : '缺失环境' }}
            </el-tag>
            <el-button size="small" type="primary" plain @click="showSkillDetail(skill)">
              查看详情
            </el-button>
          </div>
        </div>
        <div class="meta-row">
          <span class="meta-key">路径</span>
          <span class="meta-val">{{ skill.path }}</span>
        </div>
        <div class="meta-row">
          <span class="meta-key">主环境</span>
          <span class="meta-val">{{ skill.primary_env || '无' }}</span>
        </div>
        <div class="meta-row">
          <span class="meta-key">依赖环境</span>
          <span class="meta-val">{{ skill.requires_env?.length ? skill.requires_env.join(', ') : '无' }}</span>
        </div>
        <div v-if="skill.missing_envs?.length" class="missing-box">
          <div class="missing-title">缺失环境</div>
          <div class="missing-list">{{ skill.missing_envs.join(', ') }}</div>
        </div>
      </article>
    </div>

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

const availableSkillsCount = computed(() =>
  props.skills.filter((item) => item.available).length
)

const skillDialogVisible = ref(false)
const selectedSkill = ref<SkillInfo | null>(null)

const showSkillDetail = (skill: SkillInfo) => {
  selectedSkill.value = skill
  skillDialogVisible.value = true
}
</script>

<style scoped>
.catalog-pane {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 100%;
}
.hero-card {
  background: #ffffff; border: 1px solid #e5e7eb; border-radius: 24px;
  padding: 22px; display: flex; justify-content: space-between;
  gap: 16px; box-shadow: 0 12px 30px rgba(15, 23, 42, 0.05);
}
.hero-kicker {
  font-size: 0.8rem; letter-spacing: 0.12em; text-transform: uppercase;
  color: #2563eb; margin-bottom: 6px;
}
.hero-card h2 { margin: 0; color: #111827; }
.hero-card p { margin: 8px 0 0; color: #6b7280; }
.hero-stats {
  display: grid; grid-template-columns: repeat(2, minmax(120px, 1fr));
  gap: 12px; min-width: 260px;
}
.stat-box {
  border: 1px solid #e5e7eb; border-radius: 18px; padding: 14px;
  background: #f8fafc; display: flex; flex-direction: column; gap: 6px;
}
.stat-label { font-size: 0.8rem; color: #6b7280; }
.stat-value { font-size: 1.2rem; font-weight: 700; color: #111827; }
.grid-cards { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.card {
  background: #ffffff; border: 1px solid #e5e7eb; border-radius: 22px;
  padding: 18px; box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
  display: flex; flex-direction: column; gap: 14px;
  height: 320px; overflow: hidden;
}
.card-top {
  display: flex; justify-content: space-between; gap: 12px;
  align-items: start; flex-shrink: 0; overflow: hidden;
}
.card h3 { margin: 0; color: #111827; font-size: 1rem; }
.card p {
  margin: 8px 0 0; color: #6b7280; line-height: 1.6;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;
  overflow: hidden; line-clamp: 3;
}
.card-top > div { min-width: 0; overflow: hidden; }
.card-top-actions { display: flex; flex-direction: column; align-items: flex-end; gap: 8px; flex-shrink: 0; }
.meta-row { display: flex; flex-direction: column; gap: 4px; }
.meta-key { font-size: 0.8rem; color: #6b7280; }
.meta-val { color: #111827; word-break: break-all; line-height: 1.5; }
.missing-box {
  padding: 12px 14px; border-radius: 16px;
  background: #fff7ed; border: 1px solid #fed7aa;
}
.missing-title { font-size: 0.8rem; color: #c2410c; margin-bottom: 4px; font-weight: 600; }
.missing-list { color: #9a3412; line-height: 1.5; }
.dialog-section { margin-bottom: 20px; }
.dialog-label { font-size: 0.9rem; color: #111827; margin: 0 0 8px; font-weight: 600; }
.dialog-text { color: #6b7280; line-height: 1.7; white-space: pre-wrap; }
.dialog-info-grid { display: flex; flex-direction: column; gap: 12px; }
.dialog-info-item { display: flex; align-items: center; gap: 12px; }
.dialog-info-key { font-size: 0.85rem; color: #6b7280; min-width: 80px; flex-shrink: 0; }
.dialog-info-val { color: #111827; }
.missing-val { color: #c2410c; }
</style>
