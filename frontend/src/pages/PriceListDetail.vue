<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900">
    <!-- Header -->
    <div class="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 sticky top-0 z-10">
      <div class="px-4 py-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <button @click="$router.push('/price-lists')" class="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg">
              <ArrowRightIcon class="w-5 h-5 text-gray-600 dark:text-gray-300" />
            </button>
            <div>
              <div class="flex items-center gap-2">
                <h1 class="text-xl font-bold text-gray-900 dark:text-white">{{ priceList.name }}</h1>
                <StatusBadge v-if="priceList.docstatus !== undefined" :status="priceList.docstatus" />
              </div>
              <p class="text-sm text-gray-500 dark:text-gray-400">{{ priceList.price_list }}</p>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <!-- Actions for Draft -->
            <template v-if="priceList.docstatus === 0">
              <button
                @click="submitPriceList"
                :disabled="submitting"
                class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 flex items-center gap-2"
              >
                <CheckIcon class="w-4 h-4" />
                {{ submitting ? 'در حال ارسال...' : 'تأیید' }}
              </button>
              <button
                @click="deletePriceListDoc"
                :disabled="deleting"
                class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 flex items-center gap-2"
              >
                <TrashIcon class="w-4 h-4" />
                حذف
              </button>
            </template>
            <!-- Actions for Submitted -->
            <template v-else-if="priceList.docstatus === 1">
              <button
                @click="cancelPriceListDoc"
                :disabled="canceling"
                class="px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50 flex items-center gap-2"
              >
                <XIcon class="w-4 h-4" />
                {{ canceling ? 'در حال لغو...' : 'لغو' }}
              </button>
            </template>
            <button
              @click="duplicatePriceListDoc"
              :disabled="duplicating"
              class="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center gap-2"
            >
              <CopyIcon class="w-4 h-4" />
              کپی
            </button>
            <a
              :href="`/app/auto-price-list/${id}`"
              target="_blank"
              class="p-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700"
            >
              <ExternalLinkIcon class="w-5 h-5" />
            </a>
          </div>
        </div>
      </div>
    </div>

    <LoadingSpinner v-if="loading" />
    
    <div v-else class="p-4 space-y-6">
      <!-- Info Cards -->
      <div class="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
          <div class="text-2xl font-bold text-blue-600 dark:text-blue-400">{{ priceList.profit_margin }}%</div>
          <p class="text-sm text-gray-500 dark:text-gray-400">حاشیه سود</p>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
          <div class="text-2xl font-bold text-gray-900 dark:text-white">{{ items.length }}</div>
          <p class="text-sm text-gray-500 dark:text-gray-400">تعداد کالا</p>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
          <div class="text-2xl font-bold text-green-600 dark:text-green-400">{{ formatPrice(priceList.total_profit) }}</div>
          <p class="text-sm text-gray-500 dark:text-gray-400">سود کل</p>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
          <div class="text-2xl font-bold text-purple-600 dark:text-purple-400">{{ priceList.commission_percentage || 0 }}%</div>
          <p class="text-sm text-gray-500 dark:text-gray-400">کمیسیون</p>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
          <div class="text-sm text-gray-900 dark:text-white">{{ formatDate(priceList.valid_from) }}</div>
          <div class="text-sm text-gray-900 dark:text-white">{{ formatDate(priceList.valid_until) }}</div>
          <p class="text-xs text-gray-500 dark:text-gray-400">بازه اعتبار</p>
        </div>
      </div>

      <!-- Quick Actions -->
      <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
        <h2 class="text-lg font-bold text-gray-900 dark:text-white mb-4">بخش‌ها</h2>
        <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3">
          <router-link
            :to="`/price-lists/${id}/settings`"
            class="flex flex-col items-center gap-2 p-4 rounded-xl bg-gray-50 dark:bg-gray-700/50 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          >
            <SettingsIcon class="w-6 h-6" />
            <span class="text-xs font-medium text-center">تنظیمات</span>
          </router-link>
          <router-link
            :to="`/price-lists/${id}/items`"
            class="flex flex-col items-center gap-2 p-4 rounded-xl bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/30 transition-colors"
          >
            <CalculatorIcon class="w-6 h-6" />
            <span class="text-xs font-medium text-center">قیمت‌گذاری</span>
          </router-link>
          <router-link
            :to="`/price-lists/${id}/prev-import`"
            class="flex flex-col items-center gap-2 p-4 rounded-xl bg-indigo-50 dark:bg-indigo-900/20 text-indigo-700 dark:text-indigo-400 hover:bg-indigo-100 dark:hover:bg-indigo-900/30 transition-colors"
          >
            <DownloadIcon class="w-6 h-6" />
            <span class="text-xs font-medium text-center">واردات قیمت</span>
          </router-link>
          <router-link
            :to="`/price-lists/${id}/bulk`"
            class="flex flex-col items-center gap-2 p-4 rounded-xl bg-cyan-50 dark:bg-cyan-900/20 text-cyan-700 dark:text-cyan-400 hover:bg-cyan-100 dark:hover:bg-cyan-900/30 transition-colors"
          >
            <LayersIcon class="w-6 h-6" />
            <span class="text-xs font-medium text-center">دستی</span>
          </router-link>
          <router-link
            :to="`/price-lists/${id}/materials`"
            class="flex flex-col items-center gap-2 p-4 rounded-xl bg-purple-50 dark:bg-purple-900/20 text-purple-700 dark:text-purple-400 hover:bg-purple-100 dark:hover:bg-purple-900/30 transition-colors"
          >
            <PackageIcon class="w-6 h-6" />
            <span class="text-xs font-medium text-center">مواد اولیه</span>
          </router-link>
          <router-link
            :to="`/price-lists/${id}/bundles`"
            class="flex flex-col items-center gap-2 p-4 rounded-xl bg-pink-50 dark:bg-pink-900/20 text-pink-700 dark:text-pink-400 hover:bg-pink-100 dark:hover:bg-pink-900/30 transition-colors"
          >
            <BoxesIcon class="w-6 h-6" />
            <span class="text-xs font-medium text-center">بسته‌ها</span>
          </router-link>
          <router-link
            :to="`/price-lists/${id}/compare`"
            class="flex flex-col items-center gap-2 p-4 rounded-xl bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 hover:bg-amber-100 dark:hover:bg-amber-900/30 transition-colors"
          >
            <GitCompareIcon class="w-6 h-6" />
            <span class="text-xs font-medium text-center">مقایسه</span>
          </router-link>
          <router-link
            :to="`/price-lists/${id}/analytics`"
            class="flex flex-col items-center gap-2 p-4 rounded-xl bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400 hover:bg-emerald-100 dark:hover:bg-emerald-900/30 transition-colors"
          >
            <BarChartIcon class="w-6 h-6" />
            <span class="text-xs font-medium text-center">تحلیل</span>
          </router-link>
        </div>
      </div>

      <!-- Installment Info (if enabled) -->
      <div v-if="priceList.enable_installment" class="bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 rounded-xl border border-green-200 dark:border-green-800 p-4">
        <h3 class="font-bold text-green-900 dark:text-green-300 mb-3 flex items-center gap-2">
          <CreditCardIcon class="w-5 h-5" />
          فروش اقساطی فعال
        </h3>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <div class="text-green-600 dark:text-green-400 font-bold">{{ priceList.down_payment_percentage }}%</div>
            <div class="text-green-700 dark:text-green-300">پیش‌پرداخت</div>
          </div>
          <div>
            <div class="text-green-600 dark:text-green-400 font-bold">{{ priceList.number_of_months }} ماه</div>
            <div class="text-green-700 dark:text-green-300">تعداد اقساط</div>
          </div>
          <div>
            <div class="text-green-600 dark:text-green-400 font-bold">{{ priceList.monthly_interest_rate }}%</div>
            <div class="text-green-700 dark:text-green-300">بهره ماهانه</div>
          </div>
          <div>
            <div class="text-green-600 dark:text-green-400 font-bold">{{ formatNumber(priceList.installment_total_interest_percentage) }}%</div>
            <div class="text-green-700 dark:text-green-300">بهره کل</div>
          </div>
        </div>
      </div>

      <!-- Items Preview -->
      <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div class="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <h2 class="font-bold text-gray-900 dark:text-white">کالاها ({{ items.length }})</h2>
          <router-link
            :to="`/price-lists/${id}/items`"
            class="text-sm text-blue-600 dark:text-blue-400 font-medium"
          >
            مشاهده همه ←
          </router-link>
        </div>
        
        <div v-if="items.length === 0" class="p-8 text-center text-gray-500 dark:text-gray-400">
          <PackageIcon class="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p>هنوز کالایی اضافه نشده است</p>
          <router-link
            :to="`/price-lists/${id}/items`"
            class="inline-block mt-3 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            افزودن کالا
          </router-link>
        </div>
        
        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="bg-gray-50 dark:bg-gray-700/50">
              <tr>
                <th class="px-4 py-3 text-right font-medium text-gray-600 dark:text-gray-300">کالا</th>
                <th class="px-4 py-3 text-right font-medium text-gray-600 dark:text-gray-300">هزینه کل</th>
                <th class="px-4 py-3 text-right font-medium text-gray-600 dark:text-gray-300">قیمت فروش</th>
                <th class="px-4 py-3 text-right font-medium text-gray-600 dark:text-gray-300">سود</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100 dark:divide-gray-700">
              <tr v-for="item in items.slice(0, 10)" :key="item.item_code" class="hover:bg-gray-50 dark:hover:bg-gray-700/30">
                <td class="px-4 py-3">
                  <div class="font-medium text-gray-900 dark:text-white">{{ item.item_name || item.item_code }}</div>
                  <div class="text-xs text-gray-500">{{ item.item_code }}</div>
                </td>
                <td class="px-4 py-3 text-gray-600 dark:text-gray-400">{{ formatPrice(item.total_cost) }}</td>
                <td class="px-4 py-3 font-medium text-blue-600 dark:text-blue-400">
                  {{ formatPrice(item.final_selected_price || item.selling_price) }}
                </td>
                <td class="px-4 py-3" :class="(item.profit_amount || 0) >= 0 ? 'text-green-600' : 'text-red-600'">
                  {{ formatPrice(item.profit_amount) }}
                </td>
              </tr>
            </tbody>
          </table>
          <div v-if="items.length > 10" class="px-4 py-3 text-center text-sm text-gray-500 dark:text-gray-400 border-t border-gray-200 dark:border-gray-700">
            و {{ items.length - 10 }} کالای دیگر...
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { 
  getPriceListFullDetail, 
  submitPriceList as apiSubmit, 
  cancelPriceList as apiCancel,
  deletePriceList as apiDelete,
  duplicatePriceList as apiDuplicate
} from '@/data/api'
import StatusBadge from '@/components/StatusBadge.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import {
  ArrowRight as ArrowRightIcon,
  ExternalLink as ExternalLinkIcon,
  Calculator as CalculatorIcon,
  Layers as LayersIcon,
  Package as PackageIcon,
  GitCompare as GitCompareIcon,
  Settings as SettingsIcon,
  Download as DownloadIcon,
  Boxes as BoxesIcon,
  BarChart3 as BarChartIcon,
  CreditCard as CreditCardIcon,
  Check as CheckIcon,
  X as XIcon,
  Trash2 as TrashIcon,
  Copy as CopyIcon,
} from 'lucide-vue-next'

const router = useRouter()

const props = defineProps({
  id: {
    type: String,
    required: true,
  },
})

const loading = ref(true)
const submitting = ref(false)
const canceling = ref(false)
const deleting = ref(false)
const duplicating = ref(false)
const priceList = ref({})
const items = ref([])

function formatPrice(value) {
  if (!value && value !== 0) return '-'
  return new Intl.NumberFormat('fa-IR').format(Math.round(value))
}

function formatNumber(value) {
  if (!value && value !== 0) return '0'
  return new Intl.NumberFormat('fa-IR', { maximumFractionDigits: 2 }).format(value)
}

function formatDate(dateStr) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString('fa-IR')
}

async function loadPriceList() {
  loading.value = true
  try {
    const data = await getPriceListFullDetail(props.id)
    priceList.value = data || {}
    items.value = data?.items || []
  } catch (error) {
    console.error('Error loading price list:', error)
  } finally {
    loading.value = false
  }
}

async function submitPriceList() {
  if (!confirm('آیا از تأیید این لیست قیمت مطمئن هستید؟')) return
  
  submitting.value = true
  try {
    await apiSubmit(props.id)
    await loadPriceList()
  } catch (error) {
    console.error('Error submitting:', error)
    alert('خطا در تأیید لیست قیمت')
  } finally {
    submitting.value = false
  }
}

async function cancelPriceListDoc() {
  if (!confirm('آیا از لغو این لیست قیمت مطمئن هستید؟')) return
  
  canceling.value = true
  try {
    await apiCancel(props.id)
    await loadPriceList()
  } catch (error) {
    console.error('Error canceling:', error)
    alert('خطا در لغو لیست قیمت')
  } finally {
    canceling.value = false
  }
}

async function deletePriceListDoc() {
  if (!confirm('آیا از حذف این لیست قیمت مطمئن هستید؟ این عمل غیرقابل بازگشت است.')) return
  
  deleting.value = true
  try {
    await apiDelete(props.id)
    router.push('/price-lists')
  } catch (error) {
    console.error('Error deleting:', error)
    alert('خطا در حذف لیست قیمت')
  } finally {
    deleting.value = false
  }
}

async function duplicatePriceListDoc() {
  duplicating.value = true
  try {
    const result = await apiDuplicate(props.id)
    if (result?.name) {
      router.push(`/price-lists/${result.name}`)
    }
  } catch (error) {
    console.error('Error duplicating:', error)
    alert('خطا در کپی لیست قیمت')
  } finally {
    duplicating.value = false
  }
}

onMounted(() => {
  loadPriceList()
})
</script>
