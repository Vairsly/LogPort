<template>
  <div class="login-body">
    <main class="login-card">
      <div class="brand-mark">L</div>
      <h1>LogPort</h1>
      <p>安全、快速地导出服务器日志</p>
      <form @submit.prevent="onSubmit">
        <label>
          用户名
          <input v-model="username" name="username" autocomplete="username" required />
        </label>
        <label>
          密码
          <input v-model="password" name="password" type="password" autocomplete="current-password" required />
        </label>
        <div v-if="error" class="alert">{{ error }}</div>
        <button class="primary full" type="submit" :disabled="loading">
          {{ loading ? '登录中…' : '进入控制台' }}
        </button>
      </form>
    </main>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, setCsrfToken } from '../api/client'

const router = useRouter()
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function onSubmit() {
  error.value = ''
  loading.value = true
  try {
    const data = await api('/api/login', {
      method: 'POST',
      body: JSON.stringify({ username: username.value, password: password.value })
    })
    setCsrfToken(data.csrf_token)
    await router.replace('/')
  } catch (err) {
    error.value = err.message || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>
