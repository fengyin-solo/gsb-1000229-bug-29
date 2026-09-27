import { defineStore } from 'pinia'

/**
 * 演示账号：key 与后端 app/sharing.py 的 ACCOUNTS 一一对应，
 * 通过 X-Account 请求头透传给后端，可见范围一律以后端共享目录为准。
 * 前端只负责切换身份与按钮显隐，绝不自己另写一套过滤口径。
 */
export type AccountKind = 'admin' | 'station' | 'vendor'

export interface AccountOption {
  key: string
  name: string
  kind: AccountKind
  station?: string
}

export const ACCOUNT_OPTIONS: AccountOption[] = [
  { key: 'admin', name: '值班管理员', kind: 'admin' },
  { key: 'station-1', name: 'WEAT-0001 站点账号', kind: 'station', station: 'WEAT-0001' },
  { key: 'station-2', name: 'WEAT-0002 站点账号', kind: 'station', station: 'WEAT-0002' },
  { key: 'vendor', name: '外协账号（只读共享）', kind: 'vendor' },
]

interface SessionState {
  operator: string
  shiftLabel: string
  scope: string
  accountKey: string
}

export const useSessionStore = defineStore('session', {
  state: (): SessionState => ({
    operator: '值班管理员',
    shiftLabel: '白班 08:00-20:00',
    scope: '光伏电站运维管理平台',
    accountKey: 'admin',
  }),
  getters: {
    canOperate: (state) => state.operator.length > 0,
    account(state): AccountOption {
      return ACCOUNT_OPTIONS.find((item) => item.key === state.accountKey) ?? ACCOUNT_OPTIONS[0]
    },
    isVendor(): boolean {
      return this.account.kind === 'vendor'
    },
  },
  actions: {
    setShift(label: string) {
      this.shiftLabel = label
    },
    setAccount(key: string) {
      const option = ACCOUNT_OPTIONS.find((item) => item.key === key)
      if (!option) {
        return
      }
      this.accountKey = option.key
      this.operator = option.name
    },
  },
})
