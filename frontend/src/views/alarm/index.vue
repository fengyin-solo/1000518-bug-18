<template>
  <section class="page" data-module="alarm">
    <header class="page-head">
      <div>
        <h2>监测报警管理</h2>
        <p class="page-desc">维护报警事件，围绕报警编号、报警类型、报警等级、触发设备做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记报警事件</button>
        <button class="btn" type="button" @click="exportRows">导出监测报警清单</button>
      </div>
    </header>

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
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">
            <span v-if="column === '确认人员' && !hasConfirmer(row)" class="tag-warn">未指派</span>
            <template v-else>{{ row[column] ?? '—' }}</template>
          </td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无监测报警数据，可先登记报警事件</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条监测报警记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type Summary = {
  today?: number
  pending_confirm?: number
  missing_confirmer?: number
  high_level?: number
}

const ENDPOINT = '/api/alarm'
const columns = ["报警编号", "报警类型", "报警等级", "触发设备", "触发时间", "确认人员", "处置说明", "报警状态"]
const actions = ["确认报警", "处置报警", "忽略报警"]
const statuses = ["待确认", "已确认", "已处置", "已忽略"]

const stats = ref([
  { label: '今日报警', value: 0 },
  { label: '待确认报警', value: 0 },
  { label: '高等级报警', value: 0 },
  { label: '确认人缺失', value: 0 },
])

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '报警事件登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('监测报警动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '监测报警操作失败'
  }
}

function hasConfirmer(row: Row) {
  return String(row['确认人员'] ?? '').trim().length > 0
}

function applySummary(summary: Summary | undefined) {
  // 卡片口径以后端 summary 为准：它和列表、详情用的是同一份过滤结果，
  // 确认、处置、忽略之后随 reload 一起刷新，数字不会来回跳。
  const source: Summary = summary ?? {
    pending_confirm: rows.value.filter((row) => row['报警状态'] === '待确认' && hasConfirmer(row)).length,
    missing_confirmer: rows.value.filter((row) => row['报警状态'] === '待确认' && !hasConfirmer(row)).length,
    high_level: rows.value.filter((row) => ['高', '一级', '1级', 'I级', 'Ⅰ级', '紧急'].includes(String(row['报警等级'] ?? '').trim())).length,
  }
  stats.value = [
    { label: '今日报警', value: source.today ?? 0 },
    { label: '待确认报警', value: source.pending_confirm ?? 0 },
    { label: '高等级报警', value: source.high_level ?? 0 },
    { label: '确认人缺失', value: source.missing_confirmer ?? 0 },
  ]
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('报警事件列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    applySummary(payload.summary)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '监测报警列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.tag-warn {
  color: #b42318;
  background: #fef3f2;
  border: 1px solid #fecdca;
  border-radius: 4px;
  padding: 1px 6px;
  font-size: 12px;
}
</style>
