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
  <AdminApp
    v-else-if="isAdminPath && canAccessAdmin"
    :key="'admin:' + authenticatedUserKey"
  />
  <main v-else-if="isAdminPath" class="admin-access-denied">
    <AccessDeniedState
      title="管理员后台仅限管理员"
      message="当前账号没有管理用户和额度的权限。"
      :username="authState.user.value?.username"
      @back="goToWorkspace"
    />
  </main>
  <App v-else :key="'workspace:' + authenticatedUserKey" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AdminApp from './admin/AdminApp.vue'
import App from './App.vue'
import AccessDeniedState from './components/AccessDeniedState.vue'
import LoginView from './components/LoginView.vue'
import LoadingState from './components/LoadingState.vue'
import { authState } from './services/auth'

// 根入口只负责在聊天应用与独立管理员应用之间分发。
const isAdminPath = window.location.pathname === '/admin'
  || window.location.pathname.startsWith('/admin/')
const canAccessAdmin = computed(
  () => !authState.enabled.value || authState.user.value?.role === 'admin',
)
// 用户身份变化时重建应用实例，清除上一位用户残留的内存会话与界面状态。
const authenticatedUserKey = computed(
  () => authState.user.value?.id || 'local',
)

const goToWorkspace = () => {
  window.location.assign('/')
}
</script>

<style scoped>
.admin-access-denied {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  background: #f4f7f3;
}
</style>