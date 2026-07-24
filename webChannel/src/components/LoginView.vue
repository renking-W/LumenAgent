<template>
  <main class="login-page">
    <header class="login-brand">
      <img src="/logo.svg" alt="" />
      <div>
        <strong>LumenAgent</strong>
        <span>AI Agent 管理控制台</span>
      </div>
    </header>

    <section class="login-workbench" aria-labelledby="login-title">
      <div class="status-rail" aria-hidden="true"></div>
      <div class="login-panel">
        <div class="login-heading">
          <span class="login-context">WORKSPACE ACCESS</span>
          <h1 id="login-title">进入控制台</h1>
          <p>使用管理员分配的账号继续。</p>
        </div>

        <div v-if="authState.initializationError.value" class="login-error" role="alert">
          <strong>认证服务不可用</strong>
          <span>{{ authState.initializationError.value }}</span>
          <button type="button" class="secondary-action" @click="retryInitialization">
            重新检查
          </button>
        </div>

        <form v-else class="login-form" @submit.prevent="submitLogin">
          <label for="login-username">用户名</label>
          <input
            id="login-username"
            ref="usernameInput"
            v-model="username"
            name="username"
            type="text"
            autocomplete="username"
            maxlength="64"
            :disabled="submitting"
            required
          />

          <label for="login-password">密码</label>
          <input
            id="login-password"
            v-model="password"
            name="password"
            type="password"
            autocomplete="current-password"
            maxlength="256"
            :disabled="submitting"
            required
          />

          <p v-if="errorMessage" class="form-error" role="alert">{{ errorMessage }}</p>

          <button class="login-action" type="submit" :disabled="submitting || !canSubmit">
            {{ submitting ? '正在登录' : '登录' }}
          </button>
        </form>
      </div>
    </section>

    <footer>LumenAgent v0.0.1</footer>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { authState, initializeAuth, login } from '../services/auth'

const username = ref('')
const password = ref('')
const submitting = ref(false)
const errorMessage = ref('')
const usernameInput = ref<HTMLInputElement | null>(null)

const canSubmit = computed(() => username.value.trim().length > 0 && password.value.length > 0)

const submitLogin = async () => {
  if (!canSubmit.value || submitting.value) return
  submitting.value = true
  errorMessage.value = ''
  try {
    await login(username.value, password.value)
    password.value = ''
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '登录失败'
  } finally {
    submitting.value = false
  }
}

const retryInitialization = async () => {
  await initializeAuth()
  await nextTick()
  usernameInput.value?.focus()
}

onMounted(() => usernameInput.value?.focus())
</script>

<style scoped>
.login-page {
  min-height: 100%;
  display: grid;
  grid-template-rows: auto 1fr auto;
  color: #1f3424;
  background: #f7faf5;
}

.login-brand {
  height: 72px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 clamp(20px, 5vw, 64px);
  border-bottom: 1px solid #d5e3cc;
  background: rgba(247, 250, 245, 0.94);
}

.login-brand img {
  width: 34px;
  height: 34px;
  padding: 7px;
  border-radius: 6px;
  background: #eab308;
}

.login-brand div {
  display: flex;
  flex-direction: column;
}

.login-brand strong {
  font-size: 1rem;
  font-weight: 700;
}

.login-brand span {
  margin-top: 2px;
  color: #6b7e69;
  font-size: 0.74rem;
}

.login-workbench {
  width: min(460px, calc(100% - 32px));
  align-self: center;
  justify-self: center;
  display: grid;
  grid-template-columns: 5px minmax(0, 1fr);
  border: 1px solid #cad9c4;
  border-radius: 8px;
  overflow: hidden;
  background: #ffffff;
  box-shadow: 0 20px 55px rgba(31, 52, 36, 0.12);
}

.status-rail {
  background: #eab308;
}

.login-panel {
  padding: clamp(28px, 5vw, 44px);
}

.login-heading {
  margin-bottom: 30px;
}

.login-context {
  display: block;
  margin-bottom: 10px;
  color: #8a6d00;
  font: 600 0.7rem/1.2 ui-monospace, SFMono-Regular, Consolas, monospace;
}

.login-heading h1 {
  margin: 0;
  color: #203d25;
  font-size: 2rem;
  font-weight: 700;
  letter-spacing: 0;
}

.login-heading p {
  margin: 9px 0 0;
  color: #6b7e69;
  font-size: 0.9rem;
}

.login-form {
  display: grid;
  gap: 9px;
}

.login-form label {
  color: #405542;
  font-size: 0.8rem;
  font-weight: 600;
}

.login-form input {
  width: 100%;
  height: 42px;
  box-sizing: border-box;
  margin-bottom: 8px;
  padding: 0 12px;
  border: 1px solid #c5d3c0;
  border-radius: 6px;
  outline: none;
  color: #1f3424;
  background: #fbfcfa;
  font: inherit;
  transition: border-color 160ms ease, box-shadow 160ms ease;
}

.login-form input:focus {
  border-color: #8aa45f;
  box-shadow: 0 0 0 3px rgba(138, 164, 95, 0.16);
}

.login-form input:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.login-action,
.secondary-action {
  min-height: 42px;
  border: 1px solid #284a2d;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 600;
}

.login-action {
  margin-top: 8px;
  color: #ffffff;
  background: #284a2d;
}

.login-action:hover:not(:disabled) {
  background: #1f3d24;
}

.login-action:focus-visible,
.secondary-action:focus-visible {
  outline: 3px solid rgba(234, 179, 8, 0.4);
  outline-offset: 2px;
}

.login-action:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.form-error,
.login-error {
  color: #a13c34;
  font-size: 0.82rem;
}

.form-error {
  margin: 0;
}

.login-error {
  display: grid;
  gap: 8px;
  padding: 14px;
  border: 1px solid #e6bbb5;
  border-radius: 6px;
  background: #fff7f5;
}

.login-error span {
  color: #75433f;
}

.secondary-action {
  margin-top: 6px;
  color: #284a2d;
  background: #ffffff;
}

.login-page footer {
  padding: 20px;
  text-align: center;
  color: #7c8c79;
  font-size: 0.72rem;
}

@media (max-width: 560px) {
  .login-brand { height: 64px; }
  .login-workbench { align-self: start; margin-top: 12vh; }
  .login-panel { padding: 28px 24px; }
}

@media (prefers-reduced-motion: reduce) {
  .login-form input { transition: none; }
}
</style>
  .login-heading h1 { font-size: 1.75rem; }
