let csrfToken = ''

export function setCsrfToken(token) {
  csrfToken = token || ''
}

export function getCsrfToken() {
  return csrfToken
}

export async function api(url, options = {}) {
  const headers = { ...(options.headers || {}), 'Content-Type': 'application/json' }
  if (options.method && options.method !== 'GET') {
    headers['X-CSRF-Token'] = csrfToken
  }
  const response = await fetch(url, { ...options, headers })
  const data = await response.json().catch(() => ({ error: '请求失败' }))
  if (response.status === 401) {
    throw Object.assign(Error(data.error || '请先登录'), { data, status: 401, unauthorized: true })
  }
  if (!response.ok) {
    throw Object.assign(Error(data.error || '请求失败'), { data, status: response.status })
  }
  return data
}

export async function refreshSession() {
  const data = await api('/api/session')
  csrfToken = data.csrf_token || ''
  return data
}
