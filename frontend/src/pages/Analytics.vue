<template>
  <div class="p-4 lg:p-6 space-y-6">
    <!-- Header -->
    <div>
      <h1 class="text-2xl font-bold text-gray-900 dark:text-white">تحلیل‌ها و نمودارها</h1>
      <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">تحلیل عملکرد قیمت‌گذاری</p>
    </div>

    <!-- Price List Selection -->
    <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
      <div class="flex gap-4 items-end">
        <div class="flex-1">
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">انتخاب لیست قیمت</label>
          <select
            v-model="selectedPriceList"
            @change="loadAnalytics"
            class="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
          >
            <option value="">انتخاب کنید...</option>
            <option v-for="pl in priceLists" :key="pl.name" :value="pl.name">{{ pl.name }}</option>
          </select>
        </div>
      </div>
    </div>

    <LoadingSpinner v-if="loading" text="در حال بارگذاری تحلیل‌ها..." />

    <template v-else-if="analytics">
      <!-- Summary Cards -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
          <div class="text-2xl font-bold text-gray-900 dark:text-white persian-nums">{{ analytics.summary?.total_items || 0 }}</div>
          <p class="text-sm text-gray-500 dark:text-gray-400">تعداد کالا</p>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
          <div class="text-2xl font-bold text-blue-600 dark:text-blue-400 persian-nums">{{ formatPrice(analytics.summary?.total_cost) }}</div>
          <p class="text-sm text-gray-500 dark:text-gray-400">هزینه کل</p>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
          <div class="text-2xl font-bold text-cyan-600 dark:text-cyan-400 persian-nums">{{ formatPrice(analytics.summary?.total_selling) }}</div>
          <p class="text-sm text-gray-500 dark:text-gray-400">فروش کل</p>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
          <div class="text-2xl font-bold text-green-600 dark:text-green-400 persian-nums">{{ formatPrice(analytics.summary?.total_profit) }}</div>
          <p class="text-sm text-gray-500 dark:text-gray-400">سود کل</p>
        </div>
      </div>

      <!-- Profit by Group -->
      <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div class="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
          <h2 class="font-bold text-gray-900 dark:text-white">سود به تفکیک گروه کالا</h2>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full pricing-table">
            <thead>
              <tr>
                <th class="px-4 py-3 text-right">گروه کالا</th>
                <th class="px-4 py-3 text-right">تعداد</th>
                <th class="px-4 py-3 text-right">هزینه کل</th>
                <th class="px-4 py-3 text-right">فروش کل</th>
                <th class="px-4 py-3 text-right">سود</th>
                <th class="px-4 py-3 text-right">حاشیه</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100 dark:divide-gray-700">
              <tr v-for="group in analytics.by_group" :key="group.group">
                <td class="px-4 py-3 font-medium">{{ group.group }}</td>
                <td class="px-4 py-3 persian-nums">{{ group.count }}</td>
                <td class="px-4 py-3 persian-nums price">{{ formatPrice(group.total_cost) }}</td>
                <td class="px-4 py-3 persian-nums price">{{ formatPrice(group.total_selling) }}</td>
                <td class="px-4 py-3 persian-nums price" :class="group.profit > 0 ? 'text-green-600' : 'text-red-600'">
                  {{ formatPrice(group.profit) }}
                </td>
                <td class="px-4 py-3 persian-nums" :class="group.margin > 0 ? 'text-green-600' : 'text-red-600'">
                  {{ group.margin?.toFixed(1) }}%
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Top Profitable Items -->
      <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div class="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
          <h2 class="font-bold text-gray-900 dark:text-white">۱۰ کالای پرسود</h2>
        </div>
        <div class="divide-y divide-gray-100 dark:divide-gray-700">
          <div
            v-for="(item, index) in analytics.top_profitable_items"
            :key="item.item_code"
            class="p-4 flex items-center gap-4"
          >
            <div class="w-8 h-8 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center text-blue-600 dark:text-blue-400 font-bold persian-nums">
              {{ index + 1 }}
            </div>
            <div class="flex-1">
              <div class="font-medium text-gray-900 dark:text-white">{{ item.item_name || item.item_code }}</div>
              <div class="text-sm text-gray-500 dark:text-gray-400">{{ item.item_code }}</div>
            </div>
            <div class="text-left">
              <div class="font-bold text-green-600 dark:text-green-400 persian-nums">{{ formatPrice(item.profit) }} ریال</div>
              <div class="text-sm text-gray-500 dark:text-gray-400 persian-nums">حاشیه: {{ item.margin?.toFixed(1) }}%</div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <EmptyState
      v-else-if="!selectedPriceList"
      title="لیست قیمت انتخاب نشده"
      description="ابتدا یک لیست قیمت انتخاب کنید"
      :icon="BarChartIcon"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getPriceLists, getAnalyticsData } from '@/data/api'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import EmptyState from '@/components/EmptyState.vue'
import { BarChart3 as BarChartIcon } from 'lucide-vue-next'

const loading = ref(false)
const priceLists = ref([])
const selectedPriceList = ref('')
const analytics = ref(null)

function formatPrice(value) {
  if (!value && value !== 0) return '-'
  return new Intl.NumberFormat('fa-IR').format(Math.round(value))
}

async function loadPriceLists() {
  try {
    priceLists.value = await getPriceLists()
  } catch (error) {
    console.error('Error loading price lists:', error)
  }
}

async function loadAnalytics() {
  if (!selectedPriceList.value) {
    analytics.value = null
    return
  }
  
  loading.value = true
  try {
    analytics.value = await getAnalyticsData(selectedPriceList.value)
  } catch (error) {
    console.error('Error loading analytics:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadPriceLists()
})
</script>

