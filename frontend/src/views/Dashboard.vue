<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>运营概览 · 值班看板</h2>
        <p class="page-desc">汇总各业务模块的关键指标，气象监测可见范围与列表、详情共用同一共享目录。</p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn ghost" to="/weather">进入气象监测</RouterLink>
      </div>
    </header>
    <div class="stat-row">
      <article v-for="card in cards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
      </article>
    </div>
    <table class="data-table">
      <thead>
        <tr><th>业务模块</th><th>今日新增</th><th>待处理</th><th>异常量</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in moduleRows" :key="row.name">
          <td>{{ row.name }}</td>
          <td>{{ row.created }}</td>
          <td>{{ row.pending }}</td>
          <td>{{ row.abnormal }}</td>
        </tr>
      </tbody>
    </table>

    <!-- 值班看板·气象监测：取数口径与列表/详情一致，来自 /api/weather/board -->
    <header class="page-head" style="margin-top: 24px;">
      <div>
        <h3>值班看板 · 气象监测（{{ store.account.name }}）</h3>
        <p class="page-desc">跨站共享记录的风速等敏感字段按共享目录脱敏，外协只读记录同样在此呈现。</p>
      </div>
    </header>
    <table class="data-table">
      <thead>
        <tr>
          <th>站点编号</th>
          <th v-for="field in weatherFields" :key="field">{{ field }}</th>
          <th>状态</th>
          <th>来源</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in weatherRows" :key="String(row.id)">
          <td>{{ row['站点编号'] ?? '—' }}</td>
          <td v-for="field in weatherFields" :key="field">{{ row[field] ?? '—' }}</td>
          <td>{{ row.status ?? '—' }}</td>
          <td>{{ row['共享来源'] ? `共享自 ${row['共享来源']}` : '本站点' }}</td>
        </tr>
        <tr v-if="!weatherRows.length">
          <td :colspan="weatherFields.length + 3" class="empty-state">当前账号值班范围内暂无共享气象数据</td>
        </tr>
      </tbody>
    </table>
    <footer class="page-foot">
      <span v-if="weatherError" class="error-text">{{ weatherError }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { fetchJson } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type Overview = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
}

type WeatherRow = Record<string, string | number | null>

const store = useSessionStore()
const route = useRoute()
const weatherFields = ["辐照度", "风速", "气温"]

const cards = ref<Overview['cards']>([])
const moduleRows = ref<Overview['modules']>([])
const weatherRows = ref<WeatherRow[]>([])
const weatherError = ref('')

async function loadWeatherBoard() {
  weatherError.value = ''
  try {
    const payload = await fetchJson<{ items: WeatherRow[] }>('/api/weather/board')
    weatherRows.value = payload.items ?? []
  } catch (error) {
    weatherRows.value = []
    weatherError.value = error instanceof Error ? error.message : '值班看板气象数据读取失败'
  }
}

async function loadOverview() {
  try {
    const payload = await fetchJson<Overview>('/api/overview')
    cards.value = payload.cards
    moduleRows.value = payload.modules
  } catch {
    cards.value = [{"label": "业务模块", "value": 0}, {"label": "今日新增", "value": 0}]
    moduleRows.value = []
  }
}

onMounted(async () => {
  await loadOverview()
  // 看板气象区与列表/详情共用同一个共享目录入口
  await loadWeatherBoard()
})

// 切换账号时 App.vue 用 query 时间戳触发当前页重取，保证看板口径同步刷新
watch(
  () => route.query._t,
  () => {
    void loadWeatherBoard()
  },
)
</script>
