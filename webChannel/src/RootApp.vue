<template>
  <div v-if="!authState.ready.value" class="auth-boot" aria-live="polite">
    <img src="/logo.svg" alt="LumenAgent" />
    <span>正在检查访问状态</span>
  </div>
  <LoginView
    v-else-if="authState.initializationError.value || !authState.authenticated.value"
  />
  <App v-else />
</template>

<script setup lang="ts">
import App from './App.vue'
import LoginView from './components/LoginView.vue'
import { authState } from './services/auth'
</script>

<style scoped>
.auth-boot {
  min-height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #496143;
  background: #f7faf5;
  font-size: 0.9rem;
}

.auth-boot img {
  width: 28px;
  height: 28px;
  animation: auth-pulse 1.2s ease-in-out infinite;
}

@keyframes auth-pulse {
  50% { opacity: 0.45; }
}

@media (prefers-reduced-motion: reduce) {
  .auth-boot img { animation: none; }
}
</style>
