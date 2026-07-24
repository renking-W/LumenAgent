<template>
  <div
    class="loading-state"
    :class="`loading-state--${size}`"
    role="status"
    aria-live="polite"
  >
    <div class="loading-state__mark" aria-hidden="true">
      <span class="loading-state__ring"></span>
      <img src="/logo.svg" alt="" />
    </div>
    <div class="loading-state__copy">
      <span class="loading-state__label">{{ label }}</span>
      <span v-if="detail" class="loading-state__detail">{{ detail }}</span>
    </div>
    <span class="loading-state__track" aria-hidden="true">
      <span></span>
    </span>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  label?: string
  detail?: string
  size?: 'screen' | 'page' | 'section' | 'compact'
}>(), {
  label: '正在加载',
  detail: '',
  size: 'section',
})
</script>

<style scoped>
.loading-state {
  width: 100%;
  min-height: 180px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--color-navy-900, #17352f);
}

.loading-state--screen { min-height: 100vh; }
.loading-state--page { min-height: 320px; }
.loading-state--compact { min-height: 112px; gap: 9px; }

.loading-state__mark {
  position: relative;
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
}

.loading-state__mark img {
  position: relative;
  width: 30px;
  height: 30px;
  z-index: 1;
  animation: loading-breathe 1.5s ease-in-out infinite;
}

.loading-state__ring {
  position: absolute;
  inset: 0;
  border: 1px solid rgba(82, 121, 91, 0.25);
  border-radius: 50%;
  animation: loading-ring 1.5s ease-out infinite;
}

.loading-state__copy {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  text-align: center;
}

.loading-state__label {
  font-size: 0.88rem;
  font-weight: 600;
}

.loading-state__detail {
  color: var(--color-slate-400, #718079);
  font-size: 0.76rem;
}

.loading-state__track {
  width: 72px;
  height: 2px;
  overflow: hidden;
  background: rgba(82, 121, 91, 0.14);
}

.loading-state__track span {
  display: block;
  width: 28px;
  height: 100%;
  background: var(--color-gold-600, #b68a3a);
  animation: loading-track 1.25s ease-in-out infinite;
}

@keyframes loading-breathe {
  50% { opacity: 0.48; transform: scale(0.94); }
}

@keyframes loading-ring {
  from { opacity: 0.7; transform: scale(0.72); }
  to { opacity: 0; transform: scale(1.18); }
}

@keyframes loading-track {
  from { transform: translateX(-30px); }
  to { transform: translateX(76px); }
}

@media (prefers-reduced-motion: reduce) {
  .loading-state__mark img,
  .loading-state__ring,
  .loading-state__track span { animation: none; }
}
</style>
