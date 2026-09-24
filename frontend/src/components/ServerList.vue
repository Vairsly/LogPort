<template>
  <section class="panel">
    <div class="section-head">
      <h2>服务器管理</h2>
      <button class="primary" type="button" @click="openCreate">添加服务器</button>
    </div>

    <div class="cards">
      <article v-for="server in servers" :key="server.id" class="card">
        <h3>{{ server.name }}</h3>
        <div class="meta">
          {{ server.username }}@{{ server.host }}:{{ server.port }}<br />
          {{ server.containers.length }} 个容器 ·
          {{ server.host_fingerprint ? '已验证' : '待验证' }}
        </div>
        <div class="card-actions">
          <button type="button" @click="openEdit(server)">编辑</button>
          <button type="button" :disabled="testingId === server.id" @click="testConnection(server)">
            {{ testingId === server.id ? '测试中…' : '测试连接' }}
          </button>
          <button type="button" @click="removeServer(server)">删除</button>
        </div>
      </article>
      <p v-if="!servers.length">暂无服务器，点击右上角添加。</p>
    </div>

    <dialog ref="dialog">
      <form class="grid" @submit.prevent="onSubmit">
        <div class="span-2 section-head">
          <h2>服务器配置</h2>
          <button type="button" @click="closeDialog">×</button>
        </div>

        <label>
          显示名称
          <input v-model="form.name" required />
        </label>
        <label>
          主机地址
          <input v-model="form.host" required />
        </label>
        <label>
          SSH 端口
          <input v-model.number="form.port" type="number" min="1" max="65535" required />
        </label>
        <label>
          用户名
          <input v-model="form.username" required />
        </label>
        <label>
          认证方式
          <select v-model="form.auth_type">
            <option value="private_key">SSH 私钥</option>
            <option value="password">密码</option>
          </select>
        </label>
        <label>
          凭据（编辑时留空不修改）
          <textarea v-model="form.secret" rows="4"></textarea>
        </label>
        <label class="span-2">
          私钥口令（可选）
          <input v-model="form.key_passphrase" type="password" />
        </label>
        <label class="span-2">
          容器白名单（每行一个）
          <textarea v-model="form.containersText" rows="4" required></textarea>
        </label>
        <div v-if="formError" class="alert span-2">{{ formError }}</div>
        <button class="primary span-2" type="submit" :disabled="saving">
          {{ saving ? '保存中…' : '保存服务器' }}
        </button>
      </form>
    </dialog>

    <dialog ref="fingerprintDialog">
      <div class="section-head">
        <h2>确认主机指纹</h2>
        <button type="button" @click="closeFingerprint">×</button>
      </div>
      <p>首次连接指纹：</p>
      <code class="fingerprint">{{ pendingFingerprint }}</code>
      <p>请与服务器管理员核对。确认信任该指纹吗？</p>
      <div class="card-actions" style="margin-top: 16px">
        <button type="button" class="primary" @click="confirmFingerprint">确认信任</button>
        <button type="button" @click="closeFingerprint">取消</button>
      </div>
    </dialog>
  </section>
</template>

<script setup>
import { inject, onMounted, reactive, ref } from 'vue'
import { api } from '../api/client'

const toast = inject('toast')
const servers = ref([])
const dialog = ref(null)
const fingerprintDialog = ref(null)
const formError = ref('')
const saving = ref(false)
const testingId = ref(0)
const editingId = ref(0)
const pendingServerId = ref(0)
const pendingFingerprint = ref('')

const emptyForm = () => ({
  name: '',
  host: '',
  port: 22,
  username: '',
  auth_type: 'private_key',
  secret: '',
  key_passphrase: '',
  containersText: ''
})

const form = reactive(emptyForm())

async function loadServers() {
  servers.value = await api('/api/servers')
}

function openCreate() {
  editingId.value = 0
  Object.assign(form, emptyForm())
  formError.value = ''
  dialog.value.showModal()
}

function openEdit(server) {
  editingId.value = server.id
  Object.assign(form, {
    name: server.name,
    host: server.host,
    port: server.port,
    username: server.username,
    auth_type: server.auth_type,
    secret: '',
    key_passphrase: '',
    containersText: server.containers.join('\n')
  })
  formError.value = ''
  dialog.value.showModal()
}

function closeDialog() {
  dialog.value.close()
}

async function onSubmit() {
  formError.value = ''
  saving.value = true
  try {
    const payload = {
      name: form.name,
      host: form.host,
      port: Number(form.port),
      username: form.username,
      auth_type: form.auth_type,
      secret: form.secret,
      key_passphrase: form.key_passphrase,
      containers: form.containersText.split('\n')
    }
    if (editingId.value) {
      await api(`/api/servers/${editingId.value}`, { method: 'PUT', body: JSON.stringify(payload) })
    } else {
      await api('/api/servers', { method: 'POST', body: JSON.stringify(payload) })
    }
    closeDialog()
    await loadServers()
    toast('服务器已保存')
  } catch (err) {
    formError.value = err.message || '保存失败'
  } finally {
    saving.value = false
  }
}

async function testConnection(server) {
  testingId.value = server.id
  try {
    await api(`/api/servers/${server.id}/test`, { method: 'POST', body: '{}' })
    toast('连接和 Docker 权限正常')
    await loadServers()
  } catch (err) {
    if (err.data?.confirmation_required) {
      pendingServerId.value = server.id
      pendingFingerprint.value = err.data.fingerprint || ''
      fingerprintDialog.value.showModal()
    } else {
      toast(err.message || '测试失败')
    }
  } finally {
    testingId.value = 0
  }
}

function closeFingerprint() {
  fingerprintDialog.value.close()
}

async function confirmFingerprint() {
  try {
    await api(`/api/servers/${pendingServerId.value}/test`, {
      method: 'POST',
      body: JSON.stringify({ confirm_fingerprint: true })
    })
    toast('指纹已确认')
    await loadServers()
    closeFingerprint()
  } catch (err) {
    toast(err.message || '指纹确认失败')
  }
}

async function removeServer(server) {
  if (!window.confirm('确定删除这台服务器？')) return
  try {
    await api(`/api/servers/${server.id}`, { method: 'DELETE' })
    await loadServers()
    toast('服务器已删除')
  } catch (err) {
    toast(err.message || '删除失败')
  }
}

onMounted(loadServers)
</script>

<style scoped>
.fingerprint {
  display: block;
  margin: 12px 0;
  padding: 12px;
  border-radius: 8px;
  background: #f4f7fb;
  color: var(--ink);
  overflow-wrap: anywhere;
}
</style>
