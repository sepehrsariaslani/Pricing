<template>
  <div class="p-4 lg:p-6 space-y-6">
    <!-- Header -->
    <div class="flex items-center gap-4">
      <button @click="$router.back()" class="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg">
        <ArrowRightIcon class="w-5 h-5 text-gray-600 dark:text-gray-400" />
      </button>
      <div>
        <h1 class="text-2xl font-bold text-gray-900 dark:text-white">بسته محصولات</h1>
        <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">{{ id }}</p>
      </div>
    </div>

    <!-- Fetch Button -->
    <div class="flex gap-3">
      <input
        type="text"
        v-model="bundleFilter"
        placeholder="فیلتر نام بسته..."
        class="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
      />
      <button
        @click="fetchBundles"
        :disabled="fetching"
        class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 transition-colors"
      >
        <span v-if="fetching">در حال دریافت...</span>
        <span v-else>دریافت بسته‌ها</span>
      </button>
    </div>

    <!-- Bundles -->
    <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
      <div class="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <h2 class="font-bold text-gray-900 dark:text-white">
          بسته‌های محصولات
          <span v-if="bundles.length > 0" class="text-sm font-normal text-gray-500 dark:text-gray-400">
            ({{ bundles.length }} بسته)
          </span>
        </h2>
      </div>
      
      <LoadingSpinner v-if="loading" />
      
      <EmptyState
        v-else-if="bundles.length === 0"
        title="بسته‌ای یافت نشد"
        description="بسته‌های محصولات را دریافت کنید"
        :icon="PackageIcon"
      />
      
      <div v-else class="divide-y divide-gray-100 dark:divide-gray-700">
        <div
          v-for="bundle in bundles"
          :key="bundle.bundle_item"
          class="p-4 hover:bg-gray-50 dark:hover:bg-gray-700"
        >
          <div class="flex items-center justify-between">
            <div>
              <div class="font-medium text-gray-900 dark:text-white">{{ bundle.bundle_name || bundle.bundle_item }}</div>
              <div class="text-sm text-gray-500 dark:text-gray-400">{{ bundle.bundle_item }}</div>
            </div>
            <div class="text-left">
              <div class="text-sm text-gray-500 dark:text-gray-400">هزینه: {{ formatPrice(bundle.total_cost) }}</div>
              <div class="font-bold text-blue-600 dark:text-blue-400 persian-nums">
                {{ formatPrice(bundle.selling_price) }} ریال
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Link to DocType -->
    <div class="bg-gray-50 dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6 text-center">
      <LayersIcon class="w-12 h-12 text-gray-400 mx-auto mb-3" />
      <h3 class="font-medium text-gray-900 dark:text-white mb-2">مدیریت پیشرفته بسته‌ها</h3>
      <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">
        برای اعمال قیمت بسته‌ها به داکتایپ اصلی مراجعه کنید
      </p>
      <a
        :href="`/app/auto-price-list/${id}#product_bundles_tab`"
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
import { getPriceListDetail, fetchProductBundles as apiFetchBundles } from '@/data/api'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import EmptyState from '@/components/EmptyState.vue'
import {
  ArrowRight as ArrowRightIcon,
  Package as PackageIcon,
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
const fetching = ref(false)
const bundles = ref([])
const bundleFilter = ref('')

function formatPrice(value) {
  if (!value && value !== 0) return '-'
  return new Intl.NumberFormat('fa-IR').format(Math.round(value))
}

async function loadData() {
  loading.value = true
  try {
    const data = await getPriceListDetail(props.id)
    bundles.value = data?.product_bundles || []
  } catch (error) {
    console.error('Error loading data:', error)
  } finally {
    loading.value = false
  }
}

async function fetchBundles() {
  fetching.value = true
  try {
    const result = await apiFetchBundles(props.id, bundleFilter.value)
    if (result?.bundles) {
      bundles.value = result.bundles
    }
  } catch (error) {
    console.error('Error fetching bundles:', error)
  } finally {
    fetching.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

