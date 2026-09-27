<template>
  <section class="page" data-module="weather">
    <header class="page-head">
      <div>
        <h2>气象监测管理</h2>
        <p class="page-desc">维护气象数据，围绕站点编号、辐照度、风速、风向做登记、筛选与状态流转。可见范围以共享目录为准。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" :disabled="store.isVendor" @click="openCreate">登记气象数据</button>
        <button class="btn" type="button" @click="exportRows">导出气象监测清单</button>
        <button class="btn ghost" type="button" @click="toggleBoard">
          {{ showBoard ? '返回列表' : '值班看板' }}
        </button>
      </div>
    </header>

    <!-- 值班看板入口：取数同样走后端共享目录 /api/weather/board -->
    <div v-if="showBoard" class="stat-row">
      <article v-for="item in boardStats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <template v-if="!showBoard">
      <div class="stat-row">
        <article v-for="item in stats" :key="item.label" class="stat-card">
          <span class="stat-label">{{ item.label }}</span>
          <strong class="stat-value">{{ item.value }}</strong>
        </article>
      </div>

      <form class="filter-bar" @submit.prevent="reload">
        <label v-for="field in filterFields" :key="field" class="filter-item">
          <span>{{ field }}</span>
          <input v-model="filters[field]" :placeholder="`按${field}检索`" />
        </label>
        <button class="btn" type="submit">查询</button>
        <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
      </form>

      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in columns" :key="column">{{ column }}</th>
            <th>来源</th>
            <th>可执行动作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="String(row.id)">
            <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
            <td>{{ sourceLabel(row) }}</td>
            <td class="row-actions">
              <button
                class="link"
                type="button"
                @click="openDetail(row)"
              >
                详情
              </button>
              <template v-if="canWrite(row)">
                <button
                  v-for="action in actions"
                  :key="action"
                  class="link"
                  type="button"
                  :disabled="pendingId === row.id"
                  @click="runAction(action, row)"
                >
                  {{ action }}
                </button>
              </template>
              <span v-else class="readonly-hint">只读共享</span>
            </td>
          </tr>
          <tr v-if="!rows.length">
            <td :colspan="columns.length + 2" class="empty-state">当前账号可见范围内暂无气象监测数据</td>
          </tr>
        </tbody>
      </table>

      <footer class="page-foot">
        <span>共 {{ total }} 条气象监测记录（{{ store.account.name }}）</span>
        <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      </footer>
    </template>

    <!-- 值班看板：与列表、详情同一共享目录，敏感字段由后端统一脱敏 -->
    <template v-else>
      <table class="data-table">
        <thead>
          <tr>
            <th>站点编号</th>
            <th v-for="field in boardFields" :key="field">{{ field }}</th>
            <th>状态</th>
            <th>来源</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in boardRows" :key="String(row.id)">
            <td>{{ row['站点编号'] ?? '—' }}</td>
            <td v-for="field in boardFields" :key="field">{{ row[field] ?? '—' }}</td>
            <td>{{ row.status ?? '—' }}</td>
            <td>{{ sourceLabel(row) }}</td>
            <td class="row-actions">
              <button class="link" type="button" @click="openDetail(row)">详情</button>
            </td>
          </tr>
          <tr v-if="!boardRows.length">
            <td :colspan="boardFields.length + 4" class="empty-state">当前账号值班范围内暂无共享气象数据</td>
          </tr>
        </tbody>
      </table>
    </template>

    <!-- 详情弹层：详情入口，字段投影与列表/看板一致 -->
    <div v-if="detail" class="detail-mask" @click.self="closeDetail">
      <div class="detail-dialog" role="dialog" aria-modal="true">
        <header class="detail-head">
          <h3>气象数据详情 · {{ detail['站点编号'] }}</h3>
          <button class="link" type="button" @click="closeDetail">关闭</button>
        </header>
        <dl class="detail-grid">
          <template v-for="column in columns" :key="column">
            <dt>{{ column }}</dt>
            <dd>{{ detail[column] ?? '—' }}</dd>
          </template>
          <dt>状态</dt>
          <dd>{{ detail.status ?? '—' }}</dd>
          <dt>共享来源</dt>
          <dd>{{ detail['共享来源'] || '本站点' }}</dd>
        </dl>
        <div v-if="errorMessage" class="error-text">{{ errorMessage }}</div>
        <footer v-if="canWrite(detail)" class="detail-foot">
          <button
            v-for="action in actions"
            :key="action"
            class="btn"
            type="button"
            :disabled="pendingId === detail.id"
            @click="runAction(action, detail)"
          >
            {{ action }}
          </button>
        </footer>
        <p v-else class="readonly-hint">当前账号对该记录为只读共享，不能执行状态动作。</p>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type Row = Record<string, string | number | string[] | null>

const ENDPOINT = '/api/weather'
const columns = ["站点编号", "辐照度", "风速", "风向", "气温", "湿度", "降雨量", "记录时间"]
const boardFields = ["辐照度", "风速", "气温"]
const actions = ["发布预警", "升级预警", "解除预警"]
const stats = [{"label": "当前辐照", "value": 0}, {"label": "今日峰值", "value": 0}, {"label": "预警次数", "value": 0}]

const store = useSessionStore()

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

// 值班看板与详情
const showBoard = ref(false)
const boardRows = ref<Row[]>([])
const detail = ref<Row | null>(null)
// 正在提交动作的记录 id：提交期间禁用按钮，防止重复越权点击
const pendingId = ref<number | null>(null)

const boardStats = computed(() => [
  { label: "可见气象点", value: boardRows.value.length },
  { label: "预警中", value: boardRows.value.filter((row) => row.status !== '正常').length },
  { label: "当前账号", value: store.account.name },
])

/** 是否可写：以后端 owner 投影为准；外协/跨站只读，按钮不渲染或禁用。 */
function canWrite(row: Row): boolean {
  if (store.account.kind === 'admin') {
    return true
  }
  // 站点账号：归属本站点才可写；共享来的记录 owner 是他站，只读
  return typeof row.owner === 'string' && row.owner === store.account.station
}

function sourceLabel(row: Row): string {
  const source = row['共享来源']
  return typeof source === 'string' && source ? `共享自 ${source}` : '本站点'
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  // window.open 无法带 X-Account 请求头，用查询参数传递账号，导出仍走共享目录口径
  const query = new URLSearchParams({ account: store.accountKey }).toString()
  window.open(`${ENDPOINT}/export?${query}`, '_blank')
}

function toggleBoard() {
  showBoard.value = !showBoard.value
  errorMessage.value = ''
  if (showBoard.value) {
    void loadBoard()
  } else {
    void reload()
  }
}

function openCreate() {
  errorMessage.value = '气象数据登记入口尚未接入审批流'
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (response.status === 404) {
      throw new Error('该气象数据不存在或当前账号无权查看')
    }
    if (!response.ok) {
      throw new Error('气象数据详情读取失败')
    }
    detail.value = await response.json()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '气象数据详情读取失败'
  }
}

function closeDetail() {
  detail.value = null
  errorMessage.value = ''
  // 关闭详情后以服务端数据为准刷新列表/看板，避免本地残留旧按钮状态
  void (showBoard.value ? loadBoard() : reload())
}

async function runAction(action: string, row: Row) {
  // 前端再拦一次：外协与跨站只读，越权提交不发出
  if (!canWrite(row)) {
    errorMessage.value = '当前账号为只读共享，无权执行该操作'
    return
  }
  errorMessage.value = ''
  pendingId.value = Number(row.id)
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload?.ok) {
      // 关键：失败时不用本地值改按钮，直接保留服务端旧状态，
      // 这样“越权提交不生效、返回后按钮恢复旧值”表现为状态从未被改动
      throw new Error(payload?.message || '气象监测动作未生效，请稍后重试')
    }
    // 只有服务端确认 ok，才用返回的最新记录覆盖本地，杜绝前后端状态错位
    mergeEntry(payload.entry)
    if (detail.value && Number(detail.value.id) === Number(row.id)) {
      detail.value = payload.entry
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '气象监测操作失败'
  } finally {
    pendingId.value = null
  }
}

function mergeEntry(entry: Row) {
  const index = rows.value.findIndex((item) => Number(item.id) === Number(entry.id))
  if (index >= 0) {
    rows.value[index] = entry
  }
  const boardIndex = boardRows.value.findIndex((item) => Number(item.id) === Number(entry.id))
  if (boardIndex >= 0) {
    boardRows.value[boardIndex] = entry
  }
}

async function loadBoard() {
  try {
    const response = await request(`${ENDPOINT}/board`)
    if (!response.ok) {
      throw new Error('值班看板读取失败')
    }
    const payload = await response.json()
    boardRows.value = payload.items ?? []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '值班看板读取失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('气象数据列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '气象监测列表读取失败'
  }
}

onMounted(reload)

// 切换账号后按新共享目录口径重取；看板模式刷新看板，列表模式刷新列表
const route = useRoute()
watch(
  () => route.query._t,
  () => {
    detail.value = null
    void (showBoard.value ? loadBoard() : reload())
  },
)
</script>

<style scoped>
.readonly-hint {
  color: #9a6a00;
  font-size: 12px;
}
.account-switch {
  margin-left: 12px;
}
.detail-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}
.detail-dialog {
  background: #fff;
  border-radius: 10px;
  padding: 20px 24px;
  width: min(560px, 92vw);
  box-shadow: 0 18px 48px rgba(15, 23, 42, 0.25);
}
.detail-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.detail-grid {
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: 6px 12px;
  margin: 0;
}
.detail-grid dt {
  color: #64748b;
}
.detail-foot {
  margin-top: 16px;
  display: flex;
  gap: 8px;
}
</style>
