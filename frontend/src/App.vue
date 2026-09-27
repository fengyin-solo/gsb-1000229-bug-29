<template>
  <div class="app-shell">
    <aside class="app-side">
      <h1 class="app-title">光伏电站运维管理平台</h1>
      <nav class="nav-list">
        <RouterLink v-for="item in navItems" :key="item.path" :to="item.path" class="nav-item">
          {{ item.label }}
        </RouterLink>
      </nav>
    </aside>
    <main class="app-main">
      <header class="app-head">
        <span class="head-desc">面向集中式与分布式光伏电站的巡检计划、组件清洗、逆变器检修、发电监测、备品备件与故障处置的综合运维管理后台。</span>
        <span class="head-user">
          当前值班：{{ store.operator }} · {{ store.shiftLabel }}
          <label class="account-switch">
            切换账号
            <select :value="store.accountKey" @change="onAccountChange">
              <option v-for="option in accountOptions" :key="option.key" :value="option.key">
                {{ option.name }}
              </option>
            </select>
          </label>
        </span>
      </header>
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

import { setCurrentAccountKey } from '@/api/client'
import { ACCOUNT_OPTIONS, useSessionStore } from '@/stores/session'

const store = useSessionStore()
const router = useRouter()
const accountOptions = ACCOUNT_OPTIONS

onMounted(() => {
  // 启动时把本地保存的演示账号同步进 store，保证三个入口身份一致
  store.setAccount(localStorage.getItem('x-account') || 'admin')
})

function onAccountChange(event: Event) {
  const key = (event.target as HTMLSelectElement).value
  setCurrentAccountKey(key)
  store.setAccount(key)
  // 重新进入当前页，让列表/详情/看板按新账号的共享目录口径重新取数
  void router.replace({ path: router.currentRoute.value.path, query: { _t: Date.now().toString() } })
}

const navItems = [{ label: "运营概览", path: "/" }, { label: "电站档案", path: "/plant" }, { label: "巡检计划", path: "/inspection" }, { label: "组件清洗", path: "/panel_clean" }, { label: "逆变器管理", path: "/inverter" }, { label: "发电监测", path: "/power_data" }, { label: "故障处置", path: "/fault" }, { label: "备件管理", path: "/spare_part" }, { label: "箱变管理", path: "/transformer" }, { label: "开关站管理", path: "/switchgear" }, { label: "关口计量", path: "/meter" }, { label: "气象监测", path: "/weather" }, { label: "并网调度", path: "/grid_connect" }, { label: "电缆线路", path: "/cable" }, { label: "安防巡视", path: "/security" }, { label: "定期检修", path: "/maintenance" }, { label: "汇流箱管理", path: "/dc_box" }, { label: "能效分析", path: "/energy_saving" }, { label: "安全培训", path: "/training" }]
</script>
