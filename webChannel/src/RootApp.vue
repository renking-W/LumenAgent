<template>
  <LoadingState
    v-if="!authState.ready.value"
    label="正在检查访问状态"
    detail="正在确认账号与本地会话"
    size="screen"
  />
  <LoginView
    v-else-if="authState.initializationError.value || !authState.authenticated.value"
  />
  <App v-else />
</template>

<script setup lang="ts">
import App from './App.vue'
import LoginView from './components/LoginView.vue'
import LoadingState from './components/LoadingState.vue'
import { authState } from './services/auth'
</script>
