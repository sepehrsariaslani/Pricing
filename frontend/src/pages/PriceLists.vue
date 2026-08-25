<template>
  <div class="p-4 lg:p-6 space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900 dark:text-white">لیست‌های قیمت</h1>
        <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">مدیریت Auto Price List ها</p>
      </div>
      <router-link
        to="/price-lists/new"
        class="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
      >
        <PlusIcon class="w-4 h-4" />
        جدید
      </router-link>
    </div>

    <!-- Filters -->
    <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
      <div class="flex flex-wrap gap-4">
        <div class="flex-1 min-w-48">
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">وضعیت</label>
          <select
            v-model="filters.docstatus"
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option :value="null">همه</option>
            <option :value="0">پیش‌نویس</option>
            <option :value="1">تأیید شده</option>
          </select>
        </div>
        <div class="flex items-end">
          <button
            @click="loadPriceLists"
            class="px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
          >
            <RefreshCwIcon class="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>

    <!-- Price Lists -->
    <LoadingSpinner v-if="loading" text="در حال بارگذاری..." />
    
    <EmptyState
      v-else-if="priceLists.length === 0"
      title="لیست قیمتی یافت نشد"
      description="با فیلترهای فعلی هیچ لیست قیمتی پیدا نشد"
      :icon="InboxIcon"
    />
    
    <div v-else class="space-y-3">
      <router-link
        v-for="pl in priceLists"
        :key="pl.name"
        :to="`/price-lists/${pl.name}`"
        class="block bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 hover:shadow-lg transition-all card-hover"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <h3 class="font-semibold text-gray-900 dark:text-white">{{ pl.name }}</h3>
              <StatusBadge :status="pl.docstatus" />
            </div>
            <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
              لیست قیمت: {{ pl.price_list }}
            </p>
            <div class="flex flex-wrap gap-4 mt-3 text-sm text-gray-500 dark:text-gray-400">
              <span class="flex items-center gap-1">
                <CalendarIcon class="w-4 h-4" />
                {{ formatDate(pl.valid_from) }} - {{ formatDate(pl.valid_until) }}
              </span>
              <span class="flex items-center gap-1">
                <PackageIcon class="w-4 h-4" />
                {{ pl.items_count || 0 }} کالا
              </span>
            </div>
          </div>
          <div class="text-left">
            <div class="text-2xl font-bold text-blue-600 dark:text-blue-400 persian-nums">
              {{ pl.profit_margin }}%
            </div>
            <p class="text-xs text-gray-500 dark:text-gray-400">حاشیه سود</p>
          </div>
        </div>
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getPriceLists } from '@/data/api'
import StatusBadge from '@/components/StatusBadge.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import EmptyState from '@/components/EmptyState.vue'
import {
  Plus as PlusIcon,
  RefreshCw as RefreshCwIcon,
  Inbox as InboxIcon,
  Calendar as CalendarIcon,
  Package as PackageIcon,
} from 'lucide-vue-next'

const loading = ref(true)
const priceLists = ref([])
const filters = reactive({
  docstatus: null,
  price_list: null,
})

function formatDate(date) {
  if (!date) return '-'
  return new Date(date).toLocaleDateString('fa-IR')
}

async function loadPriceLists() {
  loading.value = true
  try {
    const data = await getPriceLists(filters)
    priceLists.value = data || []
  } catch (error) {
    console.error('Error loading price lists:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadPriceLists()
})
</script>

