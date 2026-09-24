<template>
  <section class="panel">
    <h2>创建导出任务</h2>
    <form class="grid" @submit.prevent="onSubmit">
      <label>
        服务器
        <select v-model="serverId" required>
          <option v-if="!servers.length" value="">请先添加服务器</option>
          <option v-for="server in servers" :key="server.id" :value="String(server.id)">
            {{ server.name }}
          </option>
        </select>
      </label>
      <label>
        容器
        <select v-model="container" required>
          <option v-for="name in containers" :key="name" :value="name">{{ name }}</option>
        </select>
      </label>

      <div class="span-2 mode">
        <button type="button" :class="{ active: mode === 'recent' }" @click="mode = 'recent'">最近一段时间</button>
        <button type="button" :class="{ active: mode === 'range' }" @click="mode = 'range'">指定时间范围</button>
      </div>

      <div v-if="mode === 'recent'" class="span-2 inline">
        <label>
          导出当前时间之前
          <input v-model.number="recentValue" type="number" min="1" required />
        </label>
        <label>
          单位
          <select v-model="recentUnit">
            <option value="minutes">分钟</option>
            <option value="hours">小时</option>
          </select>
        </label>
      </div>

      <div v-else class="span-2 inline">
        <label>
          开始时间
          <input v-model="startTime" type="datetime-local" />
        </label>
        <label>
          结束时间
          <input v-model="endTime" type="datetime-local" />
        </label>
      </div>

      <div v-if="error" class="alert span-2">{{ error }}</div>
      <button class="primary span-2" type="submit" :disabled="submitting">
        {{ submitting ? '提交中…' : '导出并生成下载' }}
      </button>
    </form>
  </section>
</template>

<script setup>
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'

const router = useRouter()
const toast = inject('toast')

const servers = ref([])
const serverId = ref('')
const container = ref('')
const mode = ref('recent')
const recentValue = ref(30)
const recentUnit = ref('minutes')
const startTime = ref('')
const endTime = ref('')
const error = ref('')
const submitting = ref(false)

const selectedServer = computed(() => servers.value.find((item) => String(item.id) === serverId.value))
const containers = computed(() => selectedServer.value?.containers || [])

watch(serverId, () => {
  container.value = containers.value[0] || ''
})

watch(containers, (list) => {
  if (!list.includes(container.value)) {
    container.value = list[0] || ''
  }
})

async function loadServers() {
  servers.value = await api('/api/servers')
  if (!serverId.value && servers.value.length) {
    serverId.value = String(servers.value[0].id)
  }
  container.value = containers.value[0] || ''
}

function toIso(localValue) {
  return new Date(localValue).toISOString()
}

async function onSubmit() {
  error.value = ''
  submitting.value = true
  try {
    let start
    let end
    if (mode.value === 'recent') {
      end = new Date()
      const ms = recentUnit.value === 'hours' ? 3600000 : 60000
      start = new Date(end.getTime() - Number(recentValue.value) * ms)
    } else {
      if (!startTime.value || !endTime.value) {
        throw new Error('请填写开始和结束时间')
      }
      start = new Date(startTime.value)
      end = new Date(endTime.value)
    }

    await api('/api/export-tasks', {
      method: 'POST',
      body: JSON.stringify({
        server_id: Number(serverId.value),
        container: container.value,
        start: start.toISOString(),
        end: end.toISOString()
      })
    })
    toast('任务已创建')
    router.push({ name: 'tasks' })
  } catch (err) {
    error.value = err.message || '创建失败'
  } finally {
    submitting.value = false
  }
}

onMounted(loadServers)
</script>
