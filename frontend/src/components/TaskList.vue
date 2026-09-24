<template>
  <section class="panel">
    <div class="section-head">
      <h2>任务记录</h2>
      <button type="button" @click="loadTasks">刷新</button>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>任务</th>
            <th>服务器 / 容器</th>
            <th>时间范围</th>
            <th>状态</th>
            <th>命令</th>
            <th>执行时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!tasks.length">
            <td colspan="7">暂无任务</td>
          </tr>
          <tr v-for="task in tasks" :key="task.id">
            <td>
              #{{ task.id }}<br />
              <small>{{ formatTime(task.created_at) }}</small>
            </td>
            <td>
              {{ task.server_name }}<br />
              <small>{{ task.container }}</small>
            </td>
            <td>
              {{ formatTime(task.start_time) }}<br />
              {{ formatTime(task.end_time) }}
            </td>
            <td>
              <span class="badge" :class="task.status">{{ labels[task.status] || task.status }}</span>
              <br v-if="task.error" />
              <small v-if="task.error" :title="task.error">{{ task.error.slice(0, 40) }}</small>
            </td>
            <td>
              <div v-if="task.export_command" class="command">
                <code :title="task.export_command">{{ task.export_command }}</code>
                <button type="button" @click="copyCommand(task.export_command, $event)">复制</button>
              </div>
              <span v-else>—</span>
            </td>
            <td>{{ duration(task) }}</td>
            <td>
              <a v-if="task.status === 'succeeded'" :href="`/api/export-tasks/${task.id}/download`">
                <button type="button">下载</button>
              </a>
              <span v-else>—</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { inject, onMounted, onUnmounted, ref } from 'vue'
import { api } from '../api/client'

const toast = inject('toast')
const tasks = ref([])
let timer = 0

const labels = {
  queued: '等待中',
  running: '执行中',
  succeeded: '已完成',
  failed: '失败',
  expired: '已过期',
  cancelled: '已取消'
}

function formatTime(value) {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}

function duration(task) {
  if (task.status !== 'succeeded' || !task.finished_at) return '—'
  const seconds = Math.max(0, Math.floor((new Date(task.finished_at) - new Date(task.created_at)) / 1000))
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const rest = seconds % 60
  if (hours) return `${hours}时 ${minutes}分 ${rest}秒`
  if (minutes) return `${minutes}分 ${rest}秒`
  return `${rest}秒`
}

async function loadTasks() {
  tasks.value = await api('/api/export-tasks')
}

async function copyCommand(command, event) {
  try {
    await navigator.clipboard.writeText(command)
    const button = event.currentTarget
    button.textContent = '已复制'
    window.setTimeout(() => {
      button.textContent = '复制'
    }, 1500)
  } catch {
    toast('复制失败，请手动选择命令')
  }
}

onMounted(async () => {
  try {
    await loadTasks()
  } catch {
    // router guard handles auth
  }
  timer = window.setInterval(loadTasks, 5000)
})

onUnmounted(() => {
  window.clearInterval(timer)
})
</script>
