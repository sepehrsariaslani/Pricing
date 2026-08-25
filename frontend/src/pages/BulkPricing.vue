<template>
  <div class="p-4 lg:p-6 space-y-6">
    <!-- Header -->
    <div class="flex items-center gap-4">
      <button @click="$router.back()" class="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg">
        <ArrowRightIcon class="w-5 h-5 text-gray-600 dark:text-gray-400" />
      </button>
      <div>
        <h1 class="text-2xl font-bold text-gray-900 dark:text-white">قیمت‌گذاری دستی</h1>
        <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">{{ id }}</p>
      </div>
    </div>

    <!-- Info -->
    <div class="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl p-4">
      <div class="flex gap-3">
        <InfoIcon class="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
        <div>
          <h3 class="font-medium text-blue-900 dark:text-blue-300">قیمت‌گذاری دستی</h3>
          <p class="text-sm text-blue-700 dark:text-blue-400 mt-1">
            در این بخش می‌توانید قیمت‌های دستی برای کالاها تعریف کنید. این قیمت‌ها بر محاسبات خودکار BOM اولویت دارند.
          </p>
        </div>
      </div>
    </div>

    <!-- Manual Item Prices -->
    <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
      <h2 class="font-bold text-gray-900 dark:text-white mb-4">قیمت‌های دستی ذخیره شده</h2>
      
      <LoadingSpinner v-if="loading" />
      
      <EmptyState
        v-else-if="manualPrices.length === 0"
        title="قیمت دستی یافت نشد"
        description="هنوز قیمت دستی‌ای تعریف نشده است"
        :icon="TagIcon"
      />
      
      <div v-else class="space-y-3">
        <div
          v-for="price in manualPrices"
          :key="price.item_code"
          class="flex items-center gap-4 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg"
        >
          <div class="flex-1">
            <div class="font-medium text-gray-900 dark:text-white">{{ price.item_name || price.item_code }}</div>
            <div class="text-sm text-gray-500 dark:text-gray-400">{{ price.item_code }}</div>
          </div>
          <div class="text-left">
            <div class="font-bold text-blue-600 dark:text-blue-400 persian-nums">
              {{ formatPrice(price.manual_price) }} ریال
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Link to DocType -->
    <div class="bg-gray-50 dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6 text-center">
      <LayersIcon class="w-12 h-12 text-gray-400 mx-auto mb-3" />
      <h3 class="font-medium text-gray-900 dark:text-white mb-2">قیمت‌گذاری پیشرفته</h3>
      <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">
        برای قیمت‌گذاری گروهی و تنظیمات پیشرفته به داکتایپ اصلی مراجعه کنید
      </p>
      <a
        :href="`/app/auto-price-list/${id}#bulk_pricing_tab`"
        target="_blank"
        class="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
      >
        <ExternalLinkIcon class="w-4 h-4" />
        رفتن به داکتایپ
      </a>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getPriceListDetail } from '@/data/api'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import EmptyState from '@/components/EmptyState.vue'
import {
  ArrowRight as ArrowRightIcon,
  Info as InfoIcon,
  Tag as TagIcon,
  Layers as LayersIcon,
  ExternalLink as ExternalLinkIcon,
} from 'lucide-vue-next'

const props = defineProps({
  id: {
    type: String,
    required: true,
  },
})

const loading = ref(true)
const manualPrices = ref([])

function formatPrice(value) {
  if (!value && value !== 0) return '-'
  return new Intl.NumberFormat('fa-IR').format(Math.round(value))
}

async function loadData() {
  loading.value = true
  try {
    const data = await getPriceListDetail(props.id)
    manualPrices.value = data?.manual_material_prices || []
  } catch (error) {
    console.error('Error loading data:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

