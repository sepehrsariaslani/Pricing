<template>
  <div class="p-4 lg:p-6 space-y-6">
    <!-- Header -->
    <div class="flex items-center gap-4">
      <button @click="$router.back()" class="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg">
        <ArrowRightIcon class="w-5 h-5 text-gray-600 dark:text-gray-400" />
      </button>
      <div>
        <h1 class="text-2xl font-bold text-gray-900 dark:text-white">مقایسه قیمت‌ها</h1>
        <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">{{ id }}</p>
      </div>
    </div>

    <!-- Compare Selection -->
    <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
      <div class="flex gap-4 items-end">
        <div class="flex-1">
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">مقایسه با لیست قیمت</label>
          <select
            v-model="comparePriceList"
            class="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
          >
            <option value="">انتخاب کنید...</option>
            <option v-for="pl in availablePriceLists" :key="pl.name" :value="pl.name">{{ pl.name }}</option>
          </select>
        </div>
        <button
          @click="loadComparison"
          :disabled="!comparePriceList || loading"
          class="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 transition-colors"
        >
          مقایسه
        </button>
      </div>
    </div>

    <!-- Summary -->
    <div v-if="summary" class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
        <div class="text-2xl font-bold text-gray-900 dark:text-white persian-nums">{{ summary.total_items }}</div>
        <p class="text-sm text-gray-500 dark:text-gray-400">کل کالاها</p>
      </div>
      <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
        <div class="text-2xl font-bold text-green-600 dark:text-green-400 persian-nums">{{ summary.increased }}</div>
        <p class="text-sm text-gray-500 dark:text-gray-400">افزایش قیمت</p>
      </div>
      <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
        <div class="text-2xl font-bold text-red-600 dark:text-red-400 persian-nums">{{ summary.decreased }}</div>
        <p class="text-sm text-gray-500 dark:text-gray-400">کاهش قیمت</p>
      </div>
      <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
        <div class="text-2xl font-bold text-blue-600 dark:text-blue-400 persian-nums">{{ summary.avg_change_percent?.toFixed(1) }}%</div>
        <p class="text-sm text-gray-500 dark:text-gray-400">میانگین تغییر</p>
      </div>
    </div>

    <!-- Comparison Table -->
    <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
      <LoadingSpinner v-if="loading" />
      
      <EmptyState
        v-else-if="comparisons.length === 0"
        title="مقایسه‌ای یافت نشد"
        description="ابتدا لیست قیمت مقایسه را انتخاب کنید"
        :icon="GitCompareIcon"
      />
      
      <div v-else class="overflow-x-auto">
        <table class="w-full pricing-table">
          <thead>
            <tr>
              <th class="px-4 py-3 text-right">کالا</th>
              <th class="px-4 py-3 text-right">قیمت قبلی</th>
              <th class="px-4 py-3 text-right">قیمت جدید</th>
              <th class="px-4 py-3 text-right">تغییر</th>
              <th class="px-4 py-3 text-right">درصد</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100 dark:divide-gray-700">
            <tr v-for="item in comparisons" :key="item.item_code">
              <td class="px-4 py-3">
                <div class="font-medium">{{ item.item_name || item.item_code }}</div>
                <div class="text-xs text-gray-500">{{ item.item_code }}</div>
              </td>
              <td class="px-4 py-3 persian-nums price">{{ formatPrice(item.old_price) }}</td>
              <td class="px-4 py-3 font-medium text-blue-600 dark:text-blue-400 persian-nums price">
                {{ formatPrice(item.new_price) }}
              </td>
              <td class="px-4 py-3 persian-nums price" :class="item.change > 0 ? 'text-green-600' : item.change < 0 ? 'text-red-600' : ''">
                {{ item.change > 0 ? '+' : '' }}{{ formatPrice(item.change) }}
              </td>
              <td class="px-4 py-3 persian-nums" :class="item.change_percent > 0 ? 'text-green-600' : item.change_percent < 0 ? 'text-red-600' : ''">
                {{ item.change_percent > 0 ? '+' : '' }}{{ item.change_percent?.toFixed(1) }}%
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getAvailablePriceLists, getPriceComparison } from '@/data/api'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import EmptyState from '@/components/EmptyState.vue'
import {
  ArrowRight as ArrowRightIcon,
  GitCompare as GitCompareIcon,
} from 'lucide-vue-next'

const props = defineProps({
  id: {
    type: String,
    required: true,
  },
})

const loading = ref(false)
const comparePriceList = ref('')
const availablePriceLists = ref([])
const comparisons = ref([])
const summary = ref(null)

function formatPrice(value) {
  if (!value && value !== 0) return '-'
  return new Intl.NumberFormat('fa-IR').format(Math.round(value))
}

async function loadPriceLists() {
  try {
    availablePriceLists.value = await getAvailablePriceLists()
  } catch (error) {
    console.error('Error loading price lists:', error)
  }
}

async function loadComparison() {
  if (!comparePriceList.value) return
  
  loading.value = true
  try {
    const data = await getPriceComparison(props.id, comparePriceList.value)
    comparisons.value = data?.items || []
    summary.value = data?.summary || null
  } catch (error) {
    console.error('Error loading comparison:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadPriceLists()
})
</script>

