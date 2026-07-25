<template>
  <div class="admin-app">
    <aside class="admin-rail">
      <a class="admin-brand" href="/admin" aria-label="LumenAgent 管理后台">
        <span class="admin-brand__mark"><img src="/logo.svg" alt="" /></span>
        <span class="admin-brand__text">
          <strong>LumenAgent</strong>
          <small>ADMIN</small>
        </span>
      </a>

      <nav class="admin-nav" aria-label="管理员导航">
        <button class="admin-nav__item admin-nav__item--active" type="button">
          <span class="admin-nav__indicator" aria-hidden="true"></span>
          用户管理
        </button>
      </nav>

      <div class="admin-rail__footer">
        <span class="admin-status"><i aria-hidden="true"></i>管理权限有效</span>
        <strong>{{ authState.user.value?.username || '本地管理员' }}</strong>
        <span>{{ authState.user.value?.role === 'admin' ? '管理员' : '本地模式' }}</span>
      </div>
    </aside>

    <section class="admin-workspace">
      <header class="admin-header">
        <div>
          <span class="admin-header__context">CONTROL / USERS</span>
          <h1>账号与额度</h1>
        </div>
        <div class="admin-header__actions">
          <button type="button" class="admin-action admin-action--quiet" @click="goToWorkspace">
            返回工作台
          </button>
          <button type="button" class="admin-action" @click="handleLogout">
            退出登录
          </button>
        </div>
      </header>

      <main class="admin-content">
        <AdminUsersView />
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import AdminUsersView from './AdminUsersView.vue'
import { authState, logout } from '../services/auth'

// 管理后台使用独立页面，跨应用切换时直接更新浏览器路径。
const goToWorkspace = () => {
  window.location.assign('/')
}

const handleLogout = () => {
  logout()
}
</script>

<style scoped>
.admin-app {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 224px minmax(0, 1fr);
  color: #18221b;
  background: #f4f7f3;
  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
}

.admin-rail {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  padding: 24px 16px 18px;
  border-right: 1px solid #d7dfd8;
  background: #18221b;
  color: #f7faf7;
}

.admin-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  color: inherit;
  text-decoration: none;
}

.admin-brand__mark {
  width: 38px;
  height: 38px;
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 6px;
  background: #eab308;
}

.admin-brand__mark img {
  width: 25px;
  height: 25px;
}

.admin-brand__text {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.admin-brand__text strong {
  font-size: 0.96rem;
  line-height: 1.2;
}

.admin-brand__text small {
  margin-top: 3px;
  color: #a9b7ad;
  font-family: Bahnschrift, Consolas, monospace;
  font-size: 0.64rem;
  letter-spacing: 0;
}

.admin-nav {
  margin-top: 42px;
}

.admin-nav__item {
  width: 100%;
  height: 42px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 12px;
  border: 0;
  border-radius: 5px;
  color: #cad5cd;
  background: transparent;
  font: inherit;
  font-size: 0.84rem;
  text-align: left;
  cursor: pointer;
}

.admin-nav__item--active {
  color: #ffffff;
  background: #2b392f;
}

.admin-nav__indicator {
  width: 3px;
  height: 18px;
  border-radius: 2px;
  background: #eab308;
}

.admin-rail__footer {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: auto;
  padding: 16px 10px 4px;
  border-top: 1px solid #354239;
  font-size: 0.74rem;
}

.admin-rail__footer strong {
  overflow: hidden;
  margin-top: 5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.admin-rail__footer > span:last-child {
  color: #95a49a;
}

.admin-status {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #b8c7bd;
}

.admin-status i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #67b77d;
  box-shadow: 0 0 0 3px rgba(103, 183, 125, 0.14);
}

.admin-workspace {
  min-width: 0;
}

.admin-header {
  min-height: 88px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 18px clamp(22px, 4vw, 52px);
  border-bottom: 1px solid #d7dfd8;
  background: rgba(255, 255, 255, 0.86);
}

.admin-header__context {
  color: #647168;
  font-family: Bahnschrift, Consolas, monospace;
  font-size: 0.68rem;
}

.admin-header h1 {
  margin: 5px 0 0;
  font-size: 1.42rem;
  font-weight: 700;
  letter-spacing: 0;
}

.admin-header__actions {
  display: flex;
  gap: 8px;
}

.admin-action {
  min-height: 36px;
  padding: 0 14px;
  border: 1px solid #c9d2cb;
  border-radius: 5px;
  color: #26342a;
  background: #ffffff;
  font: inherit;
  font-size: 0.78rem;
  cursor: pointer;
}

.admin-action:hover {
  border-color: #8f9e93;
  background: #f7f9f7;
}

.admin-action--quiet {
  border-color: transparent;
  background: transparent;
}

.admin-action:focus-visible,
.admin-nav__item:focus-visible {
  outline: 2px solid #eab308;
  outline-offset: 2px;
}

.admin-content {
  width: min(1420px, 100%);
  margin: 0 auto;
  padding: 30px clamp(22px, 4vw, 52px) 52px;
}

@media (max-width: 760px) {
  .admin-app {
    grid-template-columns: 1fr;
  }

  .admin-rail {
    min-height: auto;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    padding: 12px 16px;
    border-right: 0;
  }

  .admin-brand__text small,
  .admin-rail__footer,
  .admin-nav__indicator {
    display: none;
  }

  .admin-nav {
    margin: 0;
  }

  .admin-nav__item {
    width: auto;
    padding: 0 10px;
  }

  .admin-header {
    min-height: 78px;
    align-items: flex-end;
    padding: 14px 16px;
  }

  .admin-header__context {
    display: none;
  }

  .admin-header h1 {
    font-size: 1.2rem;
  }

  .admin-action {
    padding: 0 10px;
  }

  .admin-content {
    padding: 22px 16px 36px;
  }
}
</style>