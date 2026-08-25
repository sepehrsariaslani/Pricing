<template>
  <div class="p-4 lg:p-6 space-y-6">
    <!-- Welcome Header -->
    <div class="bg-gradient-to-l from-blue-600 to-cyan-500 rounded-2xl p-6 text-white">
      <div class="flex items-center justify-between">
        <div>
          <p class="text-blue-100 text-sm">سلام 👋</p>
          <h1 class="text-2xl font-bold mt-1">{{ userName }}</h1>
          <p class="text-blue-100 mt-2 text-sm">{{ todayDate }}</p>
        </div>
        <div class="text-left">
          <div class="text-4xl font-bold persian-nums">{{ stats.total_price_lists || 0 }}</div>
          <p class="text-blue-100 text-sm">لیست قیمت</p>
        </div>
      </div>
    </div>

    <!-- Quick Stats -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div
        v-for="stat in quickStats"
        :key="stat.label"
        class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700"
      >
        <div class="flex items-center justify-between">
          <component :is="stat.icon" class="w-8 h-8" :class="stat.iconClass" />
          <span class="text-2xl font-bold text-gray-900 dark:text-white persian-nums">
            {{ stat.value }}
          </span>
        </div>
        <p class="text-sm text-gray-600 dark:text-gray-400 mt-2">{{ stat.label }}</p>
      </div>
    </div>

    <!-- Start Wizard CTA -->
    <router-link
      to="/pricing-wizard"
      class="block bg-gradient-to-r from-emerald-500 via-green-500 to-teal-500 rounded-2xl p-6 text-white hover:shadow-lg transition-shadow"
    >
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-xl font-bold mb-2">🚀 شروع فرآیند قیمت‌گذاری</h2>
          <p class="text-green-100">قیمت‌گذاری قدم به قدم با راهنمای هوشمند</p>
        </div>
        <div class="bg-white/20 rounded-full p-4">
          <PlayCircleIcon class="w-10 h-10" />
        </div>
      </div>
    </router-link>

    <!-- Quick Actions -->
    <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
      <h2 class="text-lg font-bold text-gray-900 dark:text-white mb-4">دسترسی سریع</h2>
      <div class="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <router-link
          to="/pricing-wizard"
          class="flex flex-col items-center gap-2 p-4 rounded-xl bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 text-green-700 dark:text-green-400 hover:from-green-100 hover:to-emerald-100 dark:hover:from-green-900/30 dark:hover:to-emerald-900/30 transition-colors border border-green-200 dark:border-green-800"
        >
          <PlayCircleIcon class="w-8 h-8" />
          <span class="text-sm font-medium">فرآیند قیمت‌گذاری</span>
        </router-link>
        <router-link
          to="/price-lists/new"
          class="flex flex-col items-center gap-2 p-4 rounded-xl bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/30 transition-colors"
        >
          <PlusCircleIcon class="w-8 h-8" />
          <span class="text-sm font-medium">لیست جدید</span>
        </router-link>
        <router-link
          to="/price-lists"
          class="flex flex-col items-center gap-2 p-4 rounded-xl bg-cyan-50 dark:bg-cyan-900/20 text-cyan-700 dark:text-cyan-400 hover:bg-cyan-100 dark:hover:bg-cyan-900/30 transition-colors"
        >
          <ListIcon class="w-8 h-8" />
          <span class="text-sm font-medium">لیست‌های قیمت</span>
        </router-link>
        <router-link
          to="/analytics"
          class="flex flex-col items-center gap-2 p-4 rounded-xl bg-purple-50 dark:bg-purple-900/20 text-purple-700 dark:text-purple-400 hover:bg-purple-100 dark:hover:bg-purple-900/30 transition-colors"
        >
          <BarChartIcon class="w-8 h-8" />
          <span class="text-sm font-medium">تحلیل‌ها</span>
        </router-link>
        <a
          href="/app/auto-price-list"
          class="flex flex-col items-center gap-2 p-4 rounded-xl bg-gray-50 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors"
        >
          <ExternalLinkIcon class="w-8 h-8" />
          <span class="text-sm font-medium">داکتایپ</span>
        </a>
      </div>
    </div>

    <!-- Recent Price Lists -->
    <div class="space-y-3">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-bold text-gray-900 dark:text-white">لیست‌های قیمت اخیر</h2>
        <router-link to="/price-lists" class="text-sm text-blue-600 dark:text-blue-400 font-medium">
          مشاهده همه ←
        </router-link>
      </div>
      
      <LoadingSpinner v-if="loading" text="در حال بارگذاری..." />
      
      <EmptyState
        v-else-if="recentPriceLists.length === 0"
        title="لیست قیمتی یافت نشد"
        description="هنوز هیچ لیست قیمتی ایجاد نشده است"
        :icon="TagOffIcon"
      >
        <template #action>
          <router-link
            to="/price-lists/new"
            class="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <PlusIcon class="w-4 h-4" />
            ایجاد لیست جدید
          </router-link>
        </template>
      </EmptyState>
      
      <div v-else class="space-y-2">
        <router-link
          v-for="pl in recentPriceLists"
          :key="pl.name"
          :to="`/price-lists/${pl.name}`"
          class="block bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700 hover:shadow-md transition-shadow"
        >
          <div class="flex items-center justify-between">
            <div class="flex-1 min-w-0">
              <h3 class="font-medium text-gray-900 dark:text-white truncate">{{ pl.name }}</h3>
              <p class="text-sm text-gray-500 dark:text-gray-400">{{ pl.price_list }}</p>
            </div>
            <div class="text-left mr-4">
              <StatusBadge :status="pl.docstatus" :show-dot="false" />
              <p class="text-xs text-gray-500 dark:text-gray-400 mt-1 persian-nums">
                سود: {{ pl.profit_margin }}%
              </p>
            </div>
          </div>
        </router-link>
      </div>
    </div>

    <!-- Available Price Lists -->
    <div v-if="priceLists.length > 0" class="space-y-3">
      <h2 class="text-lg font-bold text-gray-900 dark:text-white">لیست‌های قیمت فروش</h2>
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div
          v-for="pl in priceLists"
          :key="pl.name"
          class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700"
        >
          <div class="font-medium text-gray-900 dark:text-white truncate">{{ pl.name }}</div>
          <div class="text-xs text-gray-500 dark:text-gray-400 mt-1">{{ pl.currency }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getDashboardStats } from '@/data/api'
import StatusBadge from '@/components/StatusBadge.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import EmptyState from '@/components/EmptyState.vue'
import {
  PlusCircle as PlusCircleIcon,
  Plus as PlusIcon,
  List as ListIcon,
  BarChart3 as BarChartIcon,
  ExternalLink as ExternalLinkIcon,
  Tag as TagOffIcon,
  FileText as FileTextIcon,
  Package as PackageIcon,
  Layers as LayersIcon,
  Calculator as CalculatorIcon,
  PlayCircle as PlayCircleIcon,
} from 'lucide-vue-next'

const loading = ref(true)
const stats = ref({})
const recentPriceLists = ref([])
const priceLists = ref([])

const userName = computed(() => window.user_full_name || 'کاربر')

const todayDate = computed(() => {
  const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }
  return new Date().toLocaleDateString('fa-IR', options)
})

const quickStats = computed(() => [
  {
    label: 'پیش‌نویس',
    value: stats.value.draft_price_lists || 0,
    icon: FileTextIcon,
    iconClass: 'text-amber-500',
  },
  {
    label: 'تأیید شده',
    value: stats.value.submitted_price_lists || 0,
    icon: LayersIcon,
    iconClass: 'text-green-500',
  },
  {
    label: 'گروه کالا',
    value: stats.value.item_groups || 0,
    icon: PackageIcon,
    iconClass: 'text-purple-500',
  },
  {
    label: 'کالا با BOM',
    value: stats.value.items_with_bom || 0,
    icon: CalculatorIcon,
    iconClass: 'text-blue-500',
  },
])

async function loadDashboard() {
  loading.value = true
  try {
    const data = await getDashboardStats()
    stats.value = data?.stats || {}
    recentPriceLists.value = data?.recent_price_lists || []
    priceLists.value = data?.price_lists || []
  } catch (error) {
    console.error('Error loading dashboard:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadDashboard()
})
</script>

