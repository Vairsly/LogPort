<template>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand"><span>L</span> LogPort</div>
      <nav>
        <button class="ghost" :class="{ active: route.name === 'export' }" @click="go('export')">日志导出</button>
        <button class="ghost" :class="{ active: route.name === 'tasks' }" @click="go('tasks')">任务记录</button>
        <button class="ghost" :class="{ active: route.name === 'servers' }" @click="go('servers')">服务器管理</button>
      </nav>
      <button class="ghost logout" @click="logout">退出登录</button>
    </aside>

    <main class="content">
      <header>
        <div>
          <h1>{{ pageTitle }}</h1>
          <p>{{ pageDesc }}</p>
        </div>
        <div class="status-dot">服务运行中</div>
      </header>
      <router-view />
    </main>

    <ToastHost :message="toastMessage" />
  </div>
</template>

<script setup>
import { computed, onMounted, provide, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, refreshSession } from '../api/client'
import ToastHost from '../components/ToastHost.vue'

const route = useRoute()
const router = useRouter()
const toastMessage = ref('')

const titles = {
  export: '日志导出',
  tasks: '任务记录',
  servers: '服务器管理'
}

const descs = {
  export: '选择目标与时间范围，后台安全生成日志文件',
  tasks: '查看导出进度、错误摘要与下载入口',
  servers: '维护 SSH 目标、凭据与容器白名单'
}

const pageTitle = computed(() => titles[route.name] || 'LogPort')
const pageDesc = computed(() => descs[route.name] || '')

function go(name) {
  router.push({ name })
}

function toast(message) {
  toastMessage.value = message
  window.setTimeout(() => {
    if (toastMessage.value === message) toastMessage.value = ''
  }, 2400)
}

provide('toast', toast)

async function logout() {
  try {
    await api('/api/logout', { method: 'POST', body: '{}' })
  } catch {
    // ignore
  }
  router.replace('/login')
}

onMounted(async () => {
  try {
    await refreshSession()
  } catch {
    router.replace('/login')
  }
})
</script>
