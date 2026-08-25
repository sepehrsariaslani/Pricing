<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900">
    <!-- Header -->
    <div class="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 sticky top-0 z-10">
      <div class="px-4 py-4">
        <div class="flex items-center gap-3">
          <button @click="$router.back()" class="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg">
            <ArrowRightIcon class="w-5 h-5 text-gray-600 dark:text-gray-300" />
          </button>
          <div>
            <h1 class="text-xl font-bold text-gray-900 dark:text-white">تحلیل لیست قیمت</h1>
            <p class="text-sm text-gray-500 dark:text-gray-400">{{ priceList?.price_list }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-20">
      <div class="w-8 h-8 border-4 border-primary-600 border-t-transparent rounded-full animate-spin"></div>
    </div>

    <!-- Content -->
    <div v-else class="p-4 space-y-6">
      <!-- Summary Cards -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div class="text-3xl font-bold text-gray-900 dark:text-white">{{ formatNumber(analytics?.summary?.total_items || 0) }}</div>
          <div class="text-sm text-gray-500 dark:text-gray-400 mt-1">تعداد کالا</div>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div class="text-3xl font-bold text-gray-900 dark:text-white">{{ formatCurrency(analytics?.summary?.total_cost || 0) }}</div>
          <div class="text-sm text-gray-500 dark:text-gray-400 mt-1">مجموع هزینه</div>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div class="text-3xl font-bold text-primary-600 dark:text-primary-400">{{ formatCurrency(analytics?.summary?.total_selling || 0) }}</div>
          <div class="text-sm text-gray-500 dark:text-gray-400 mt-1">مجموع فروش</div>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div class="text-3xl font-bold text-green-600 dark:text-green-400">{{ formatCurrency(analytics?.summary?.total_profit || 0) }}</div>
          <div class="text-sm text-gray-500 dark:text-gray-400 mt-1">مجموع سود</div>
        </div>
      </div>

      <!-- Profit by Group -->
      <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
        <div class="p-4 border-b border-gray-200 dark:border-gray-700">
          <h2 class="font-bold text-gray-900 dark:text-white">سود به تفکیک گروه کالا</h2>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="bg-gray-50 dark:bg-gray-700/50">
              <tr>
                <th class="px-4 py-3 text-right font-medium text-gray-600 dark:text-gray-300">گروه</th>
                <th class="px-4 py-3 text-right font-medium text-gray-600 dark:text-gray-300">تعداد</th>
                <th class="px-4 py-3 text-right font-medium text-gray-600 dark:text-gray-300">هزینه کل</th>
                <th class="px-4 py-3 text-right font-medium text-gray-600 dark:text-gray-300">فروش کل</th>
                <th class="px-4 py-3 text-right font-medium text-gray-600 dark:text-gray-300">سود</th>
                <th class="px-4 py-3 text-right font-medium text-gray-600 dark:text-gray-300">حاشیه</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100 dark:divide-gray-700">
              <tr v-for="group in analytics?.by_group || []" :key="group.group" class="hover:bg-gray-50 dark:hover:bg-gray-700/30">
                <td class="px-4 py-3 font-medium text-gray-900 dark:text-white">{{ group.group }}</td>
                <td class="px-4 py-3 text-gray-600 dark:text-gray-400">{{ formatNumber(group.count) }}</td>
                <td class="px-4 py-3 text-gray-600 dark:text-gray-400">{{ formatCurrency(group.total_cost) }}</td>
                <td class="px-4 py-3 text-gray-600 dark:text-gray-400">{{ formatCurrency(group.total_selling) }}</td>
                <td class="px-4 py-3 font-medium" :class="group.profit >= 0 ? 'text-green-600' : 'text-red-600'">
                  {{ formatCurrency(group.profit) }}
                </td>
                <td class="px-4 py-3">
                  <div class="flex items-center gap-2">
                    <div class="w-16 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                      <div
                        class="h-full rounded-full"
                        :class="group.margin >= 0 ? 'bg-green-500' : 'bg-red-500'"
                        :style="{ width: Math.min(Math.abs(group.margin), 100) + '%' }"
                      ></div>
                    </div>
                    <span class="text-sm" :class="group.margin >= 0 ? 'text-green-600' : 'text-red-600'">
                      {{ group.margin.toFixed(1) }}%
                    </span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Top Profitable Items -->
      <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
        <div class="p-4 border-b border-gray-200 dark:border-gray-700">
          <h2 class="font-bold text-gray-900 dark:text-white">پرسودترین کالاها</h2>
        </div>
        <div class="divide-y divide-gray-100 dark:divide-gray-700">
          <div
            v-for="(item, index) in analytics?.top_profitable_items || []"
            :key="item.item_code"
            class="flex items-center gap-4 p-4 hover:bg-gray-50 dark:hover:bg-gray-700/30"
          >
            <div class="w-8 h-8 bg-gradient-to-br from-green-500 to-emerald-600 rounded-lg flex items-center justify-center text-white font-bold text-sm">
              {{ index + 1 }}
            </div>
            <div class="flex-1 min-w-0">
              <div class="font-medium text-gray-900 dark:text-white truncate">{{ item.item_name }}</div>
              <div class="text-sm text-gray-500 dark:text-gray-400">{{ item.item_code }}</div>
            </div>
            <div class="text-left">
              <div class="font-bold text-green-600 dark:text-green-400">{{ formatCurrency(item.profit) }}</div>
              <div class="text-sm text-gray-500 dark:text-gray-400">{{ item.margin.toFixed(1) }}% حاشیه</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getPriceListFullDetail, getAnalyticsData } from '@/data/api'
import { ArrowRight as ArrowRightIcon } from 'lucide-vue-next'

const route = useRoute()
const priceListId = computed(() => route.params.id)

const loading = ref(true)
const priceList = ref(null)
const analytics = ref(null)

async function loadData() {
  loading.value = true
  try {
    const [plData, analyticsData] = await Promise.all([
      getPriceListFullDetail(priceListId.value),
      getAnalyticsData(priceListId.value)
    ])
    priceList.value = plData
    analytics.value = analyticsData
  } catch (error) {
    console.error('Error loading data:', error)
  } finally {
    loading.value = false
  }
}

function formatNumber(num) {
  return new Intl.NumberFormat('fa-IR').format(num || 0)
}

function formatCurrency(num) {
  if (!num && num !== 0) return '-'
  return new Intl.NumberFormat('fa-IR').format(Math.round(num))
}

onMounted(() => {
  loadData()
})
</script>

