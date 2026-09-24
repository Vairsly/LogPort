import { createRouter, createWebHistory } from 'vue-router'
import { api } from '../api/client'
import LoginView from '../views/LoginView.vue'
import DashboardView from '../views/DashboardView.vue'
import ExportPanel from '../components/ExportPanel.vue'
import TaskList from '../components/TaskList.vue'
import ServerList from '../components/ServerList.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView },
    {
      path: '/',
      component: DashboardView,
      meta: { requiresAuth: true },
      children: [
        { path: '', name: 'export', component: ExportPanel },
        { path: 'tasks', name: 'tasks', component: TaskList },
        { path: 'servers', name: 'servers', component: ServerList }
      ]
    }
  ]
})

router.beforeEach(async (to) => {
  if (to.name === 'login') return true
  if (!to.meta.requiresAuth) return true
  try {
    await api('/api/session')
    return true
  } catch {
    return { name: 'login' }
  }
})

export default router
