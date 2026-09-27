/** 统一请求封装：拼后端地址、带上当前账号、抛网络错误、给页脚留一句可读的说明。 */
const API_BASE = import.meta.env.VITE_API_BASE ?? ''

/**
 * 当前账号 key：列表 / 详情 / 值班看板共用，避免各入口各取一份身份。
 * 登录态接入前用 localStorage 持久化演示账号切换。
 */
export function currentAccountKey(): string {
  return localStorage.getItem('x-account') || 'admin'
}

export function setCurrentAccountKey(key: string): void {
  localStorage.setItem('x-account', key)
}

function buildHeaders(init?: RequestInit): Headers {
  const headers = new Headers(init?.headers)
  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  headers.set('X-Account', currentAccountKey())
  return headers
}

export function request(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  return fetch(url, {
    ...init,
    headers: buildHeaders(init),
  }).catch((error: unknown) => {
    const detail = error instanceof Error ? error.message : '请求未送达'
    throw new Error(`接口请求失败：${detail}`)
  })
}

export async function fetchJson<T>(path: string): Promise<T> {
  const response = await request(path)
  if (!response.ok) {
    throw new Error(`接口返回 ${response.status}，数据未更新`)
  }
  return (await response.json()) as T
}
