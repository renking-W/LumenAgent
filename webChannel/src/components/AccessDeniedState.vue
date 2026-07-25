<template>
  <section class="access-denied" :class="{ 'access-denied--compact': compact }" role="alert">
    <div class="access-denied__code" aria-hidden="true">403</div>
    <div class="access-denied__brand">
      <span class="access-denied__brand-mark" aria-hidden="true">
        <img src="/logo.svg" alt="" />
      </span>
      <span>LumenAgent</span>
    </div>
    <div class="access-denied__rule" aria-hidden="true"></div>
    <p class="access-denied__eyebrow">Restricted area</p>
    <h2>{{ title }}</h2>
    <p class="access-denied__message">{{ message }}</p>
    <div class="access-denied__identity">
      <span>当前身份</span>
      <strong>{{ username || '普通用户' }}</strong>
      <span class="access-denied__role">{{ roleLabel }}</span>
    </div>
    <el-button v-if="showBack" type="primary" plain @click="$emit('back')">
      返回对话
    </el-button>
  </section>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  title?: string
  message?: string
  username?: string
  roleLabel?: string
  compact?: boolean
  showBack?: boolean
}>(), {
  title: '当前账号无权访问',
  message: '该区域仅向管理员开放。如需使用，请切换管理员账号。',
  username: '',
  roleLabel: '普通用户',
  compact: false,
  showBack: true,
})

defineEmits<{ back: [] }>()
</script>

<style scoped>
.access-denied {
  width: min(620px, calc(100% - 32px));
  min-height: 360px;
  margin: 42px auto;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  position: relative;
  overflow: hidden;
  color: var(--color-navy-900, #17352f);
}

.access-denied--compact {
  width: 100%;
  min-height: 280px;
  margin: 0;
  padding: 12px 8px;
}

.access-denied__code {
  position: absolute;
  right: 0;
  top: 16px;
  color: rgba(23, 53, 47, 0.055);
  font-family: var(--font-mono, monospace);
  font-size: clamp(6rem, 20vw, 11rem);
  font-weight: 800;
  line-height: 0.8;
  pointer-events: none;
}

.access-denied__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 18px;
  color: var(--color-navy-800, #244a42);
  font-size: 0.78rem;
  font-weight: 700;
}

.access-denied__brand-mark {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  border-radius: 6px;
  background: #eab308;
}

.access-denied__brand-mark img {
  width: 27px;
  height: 27px;
}

.access-denied__rule {
  width: 42px;
  height: 3px;
  margin-bottom: 18px;
  background: var(--color-gold-600, #b68a3a);
}

.access-denied__eyebrow {
  margin: 0 0 6px;
  color: var(--color-gold-600, #9a722d);
  font-family: var(--font-mono, monospace);
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
}

.access-denied h2 {
  margin: 0;
  font-size: 1.45rem;
  font-weight: 700;
}

.access-denied__message {
  max-width: 430px;
  margin: 10px 0 22px;
  color: var(--color-slate-500, #64736c);
  font-size: 0.9rem;
  line-height: 1.7;
}

.access-denied__identity {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 24px;
  color: var(--color-slate-400, #7a8982);
  font-size: 0.78rem;
}

.access-denied__identity strong {
  color: var(--color-navy-800, #244a42);
  font-family: var(--font-mono, monospace);
}

.access-denied__role {
  padding-left: 9px;
  border-left: 1px solid var(--color-slate-200, #dce4df);
}

.access-denied--compact .access-denied__brand {
  margin-bottom: 14px;
}

.access-denied--compact .access-denied__brand-mark {
  width: 36px;
  height: 36px;
}

.access-denied--compact .access-denied__brand-mark img {
  width: 23px;
  height: 23px;
}

@media (max-width: 640px) {
  .access-denied { min-height: 300px; margin-top: 18px; }
  .access-denied__code { top: 32px; }
}
</style>
