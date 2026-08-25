<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900">
    <!-- Header with Steps -->
    <div class="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 sticky top-0 z-20">
      <div class="px-4 py-3">
        <div class="flex items-center justify-between mb-4">
          <div class="flex items-center gap-3">
            <button @click="$router.push('/price-lists')" class="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg">
              <XIcon class="w-5 h-5 text-gray-600 dark:text-gray-300" />
            </button>
            <div>
              <h1 class="text-lg font-bold text-gray-900 dark:text-white">فرآیند قیمت‌گذاری</h1>
              <p class="text-sm text-gray-500 dark:text-gray-400">{{ priceListName || 'لیست جدید' }}</p>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-sm text-gray-500">مرحله {{ currentStep }} از {{ totalSteps }}</span>
          </div>
        </div>
        
        <!-- Steps Indicator -->
        <div class="flex items-center gap-2 overflow-x-auto pb-2">
          <button
            v-for="(step, index) in steps"
            :key="index"
            @click="goToStep(index + 1)"
            :disabled="!canGoToStep(index + 1)"
            class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm whitespace-nowrap transition-all"
            :class="getStepClass(index + 1)"
          >
            <span class="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold"
                  :class="getStepNumberClass(index + 1)">
              <CheckIcon v-if="index + 1 < currentStep" class="w-4 h-4" />
              <span v-else>{{ index + 1 }}</span>
            </span>
            <span class="hidden sm:inline">{{ step.title }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-20">
      <div class="w-8 h-8 border-4 border-primary-600 border-t-transparent rounded-full animate-spin"></div>
    </div>

    <!-- Step Content -->
    <div v-else class="p-4 max-w-4xl mx-auto">
      <!-- Step 1: Basic Settings -->
      <div v-show="currentStep === 1" class="space-y-6">
        <div class="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
          <h2 class="text-xl font-bold text-gray-900 dark:text-white mb-6 flex items-center gap-2">
            <SettingsIcon class="w-6 h-6 text-primary-500" />
            تنظیمات پایه
          </h2>
          
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">لیست قیمت</label>
              <SearchSelect
                v-model="formData.price_list"
                :options="availablePriceLists"
                placeholder="جستجو و انتخاب لیست قیمت..."
                label-key="name"
                value-key="name"
              />
            </div>
            
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">تاریخ شروع</label>
                <input
                  type="date"
                  v-model="formData.valid_from"
                  class="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">تاریخ پایان</label>
                <input
                  type="date"
                  v-model="formData.valid_until"
                  class="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                />
              </div>
            </div>
            
            <div class="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">درصد سود</label>
                <div class="relative">
                  <input
                    type="number"
                    v-model.number="formData.profit_margin"
                    step="0.1"
                    class="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  />
                  <span class="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500">%</span>
                </div>
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">درصد کمیسیون</label>
                <div class="relative">
                  <input
                    type="number"
                    v-model.number="formData.commission_percentage"
                    step="0.1"
                    class="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  />
                  <span class="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500">%</span>
                </div>
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">مبلغ رند کردن</label>
                <input
                  type="number"
                  v-model.number="formData.price_rounding_amount"
                  step="1000"
                  class="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 2: Select Products -->
      <div v-show="currentStep === 2" class="space-y-6">
        <div class="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
          <h2 class="text-xl font-bold text-gray-900 dark:text-white mb-6 flex items-center gap-2">
            <PackageIcon class="w-6 h-6 text-cyan-500" />
            انتخاب کالاها
          </h2>
          
          <div class="space-y-4">
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">گروه کالا</label>
                <SearchSelect
                  v-model="filters.item_group"
                  :search-fn="searchItemGroups"
                  placeholder="جستجوی گروه کالا..."
                  label-key="name"
                  value-key="name"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">برند</label>
                <SearchSelect
                  v-model="filters.brand"
                  :search-fn="searchBrands"
                  placeholder="جستجوی برند..."
                  label-key="name"
                  value-key="name"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">فیلتر نام</label>
                <input
                  type="text"
                  v-model="filters.item_name_filter"
                  placeholder="جستجو در نام کالا..."
                  class="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                />
              </div>
            </div>
            
            <button
              @click="fetchItems"
              :disabled="fetchingItems"
              class="w-full py-3 bg-cyan-600 text-white rounded-xl hover:bg-cyan-700 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              <RefreshCwIcon class="w-5 h-5" :class="{ 'animate-spin': fetchingItems }" />
              {{ fetchingItems ? 'در حال دریافت...' : 'دریافت کالاها' }}
            </button>
          </div>
        </div>
        
        <!-- Items List -->
        <div v-if="items.length > 0" class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
          <div class="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
            <h3 class="font-bold text-gray-900 dark:text-white">کالاهای انتخاب شده ({{ items.length }})</h3>
            <input
              type="text"
              v-model="itemSearchQuery"
              placeholder="جستجو..."
              class="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm w-40"
            />
          </div>
          <div class="max-h-64 overflow-y-auto divide-y divide-gray-100 dark:divide-gray-700">
            <div
              v-for="item in filteredItems"
              :key="item.item_code"
              class="px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-700/30 flex items-center justify-between"
            >
              <div>
                <div class="font-medium text-gray-900 dark:text-white">{{ item.item_name }}</div>
                <div class="text-sm text-gray-500">{{ item.item_code }} • {{ item.item_group }}</div>
              </div>
              <span class="text-sm text-gray-500">{{ item.brand }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 3: Calculate Prices -->
      <div v-show="currentStep === 3" class="space-y-6">
        <div class="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
          <h2 class="text-xl font-bold text-gray-900 dark:text-white mb-6 flex items-center gap-2">
            <CalculatorIcon class="w-6 h-6 text-purple-500" />
            محاسبه قیمت‌ها
          </h2>
          
          <button
            @click="calculatePrices"
            :disabled="calculating"
            class="w-full py-4 bg-purple-600 text-white rounded-xl hover:bg-purple-700 disabled:opacity-50 flex items-center justify-center gap-2 text-lg"
          >
            <CalculatorIcon class="w-6 h-6" :class="{ 'animate-pulse': calculating }" />
            {{ calculating ? 'در حال محاسبه...' : 'محاسبه قیمت‌ها' }}
          </button>
        </div>
        
        <!-- Calculated Items -->
        <div v-if="calculatedItems.length > 0" class="space-y-4">
          <!-- Summary -->
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
              <div class="text-2xl font-bold text-gray-900 dark:text-white">{{ formatNumber(calculatedItems.length) }}</div>
              <div class="text-sm text-gray-500">تعداد</div>
            </div>
            <div class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
              <div class="text-2xl font-bold text-gray-900 dark:text-white">{{ formatCurrency(totalCost) }}</div>
              <div class="text-sm text-gray-500">هزینه کل</div>
            </div>
            <div class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
              <div class="text-2xl font-bold text-primary-600">{{ formatCurrency(totalSelling) }}</div>
              <div class="text-sm text-gray-500">فروش کل</div>
            </div>
            <div class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
              <div class="text-2xl font-bold text-green-600">{{ formatCurrency(totalProfit) }}</div>
              <div class="text-sm text-gray-500">سود کل</div>
            </div>
          </div>
          
          <!-- Currency Converter -->
          <div class="bg-gradient-to-r from-indigo-50 to-purple-50 dark:from-indigo-900/20 dark:to-purple-900/20 rounded-xl p-4 border border-indigo-200 dark:border-indigo-800">
            <div class="flex items-center gap-4 flex-wrap">
              <span class="text-sm font-medium text-indigo-700 dark:text-indigo-300">نمایش به ارز:</span>
              <div class="flex gap-2">
                <button
                  v-for="curr in currencies"
                  :key="curr.name"
                  @click="convertCurrency(curr.name)"
                  class="px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
                  :class="selectedCurrency === curr.name 
                    ? 'bg-indigo-600 text-white' 
                    : 'bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600'"
                >
                  {{ curr.symbol || curr.name }}
                </button>
              </div>
              <div v-if="selectedCurrency !== 'IRR'" class="text-sm text-indigo-600 dark:text-indigo-400">
                نرخ: {{ formatNumber(exchangeRate) }} ریال
              </div>
            </div>
          </div>
          
          <!-- Items Table -->
          <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
            <div class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead class="bg-gray-50 dark:bg-gray-700/50">
                  <tr>
                    <th class="px-4 py-3 text-right">کالا</th>
                    <th class="px-4 py-3 text-right">هزینه کل</th>
                    <th class="px-4 py-3 text-right">قیمت فروش</th>
                    <th class="px-4 py-3 text-right">سود</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-100 dark:divide-gray-700">
                  <tr v-for="item in displayItems" :key="item.item_code" class="hover:bg-gray-50 dark:hover:bg-gray-700/30">
                    <td class="px-4 py-3">
                      <div class="font-medium text-gray-900 dark:text-white">{{ item.item_name }}</div>
                      <div class="text-xs text-gray-500">{{ item.item_code }}</div>
                    </td>
                    <td class="px-4 py-3 text-gray-600 dark:text-gray-400">{{ formatDisplayPrice(item.total_cost) }}</td>
                    <td class="px-4 py-3 font-medium text-primary-600">{{ formatDisplayPrice(item.final_selected_price || item.selling_price) }}</td>
                    <td class="px-4 py-3" :class="item.profit_amount >= 0 ? 'text-green-600' : 'text-red-600'">
                      {{ formatDisplayPrice(item.profit_amount) }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 4: Review & Apply -->
      <div v-show="currentStep === 4" class="space-y-6">
        <div class="bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 rounded-xl p-6 border border-green-200 dark:border-green-800">
          <h2 class="text-xl font-bold text-green-800 dark:text-green-300 mb-4 flex items-center gap-2">
            <CheckCircleIcon class="w-6 h-6" />
            بررسی نهایی و اعمال
          </h2>
          
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div class="bg-white dark:bg-gray-800 rounded-lg p-4 text-center">
              <div class="text-3xl font-bold text-gray-900 dark:text-white">{{ summary.items_count }}</div>
              <div class="text-sm text-gray-500">کالا</div>
            </div>
            <div class="bg-white dark:bg-gray-800 rounded-lg p-4 text-center">
              <div class="text-3xl font-bold text-gray-900 dark:text-white">{{ formatCurrency(summary.total_cost) }}</div>
              <div class="text-sm text-gray-500">هزینه</div>
            </div>
            <div class="bg-white dark:bg-gray-800 rounded-lg p-4 text-center">
              <div class="text-3xl font-bold text-primary-600">{{ formatCurrency(summary.total_selling) }}</div>
              <div class="text-sm text-gray-500">فروش</div>
            </div>
            <div class="bg-white dark:bg-gray-800 rounded-lg p-4 text-center">
              <div class="text-3xl font-bold text-green-600">{{ summary.avg_profit_margin?.toFixed(1) }}%</div>
              <div class="text-sm text-gray-500">حاشیه سود</div>
            </div>
          </div>
          
          <div class="flex gap-4">
            <button
              @click="applyPrices"
              :disabled="applying"
              class="flex-1 py-4 bg-green-600 text-white rounded-xl hover:bg-green-700 disabled:opacity-50 flex items-center justify-center gap-2 text-lg font-medium"
            >
              <CheckIcon class="w-6 h-6" />
              {{ applying ? 'در حال اعمال...' : 'اعمال قیمت‌ها به لیست قیمت' }}
            </button>
            <button
              @click="submitPriceList"
              :disabled="submitting"
              class="px-6 py-4 bg-primary-600 text-white rounded-xl hover:bg-primary-700 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              <SendIcon class="w-5 h-5" />
              {{ submitting ? 'در حال تأیید...' : 'تأیید نهایی' }}
            </button>
          </div>
        </div>
        
        <!-- Reports Section -->
        <div class="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
          <h3 class="font-bold text-gray-900 dark:text-white mb-4">گزارش‌ها و تحلیل‌ها</h3>
          <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <button @click="showCostAnalysis" class="p-4 rounded-xl border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/30 text-center">
              <PieChartIcon class="w-8 h-8 mx-auto mb-2 text-blue-500" />
              <span class="text-sm">تحلیل هزینه</span>
            </button>
            <button @click="showBreakEven" class="p-4 rounded-xl border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/30 text-center">
              <TrendingUpIcon class="w-8 h-8 mx-auto mb-2 text-green-500" />
              <span class="text-sm">نقطه سربه‌سر</span>
            </button>
            <button @click="showRawMaterials" class="p-4 rounded-xl border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/30 text-center">
              <BoxesIcon class="w-8 h-8 mx-auto mb-2 text-purple-500" />
              <span class="text-sm">مواد اولیه</span>
            </button>
            <button @click="exportExcel" class="p-4 rounded-xl border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/30 text-center">
              <DownloadIcon class="w-8 h-8 mx-auto mb-2 text-emerald-500" />
              <span class="text-sm">خروجی Excel</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Navigation Buttons -->
      <div class="flex items-center justify-between mt-8 pt-4 border-t border-gray-200 dark:border-gray-700">
        <button
          v-if="currentStep > 1"
          @click="prevStep"
          class="px-6 py-3 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center gap-2"
        >
          <ChevronRightIcon class="w-5 h-5" />
          مرحله قبل
        </button>
        <div v-else></div>
        
        <button
          v-if="currentStep < totalSteps"
          @click="nextStep"
          :disabled="!canProceed"
          class="px-6 py-3 bg-primary-600 text-white rounded-xl hover:bg-primary-700 disabled:opacity-50 flex items-center gap-2"
        >
          مرحله بعد
          <ChevronLeftIcon class="w-5 h-5" />
        </button>
      </div>
    </div>

    <!-- Modals -->
    <ReportModal
      v-if="activeModal"
      :title="modalTitle"
      :data="modalData"
      :type="modalType"
      @close="activeModal = false"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  getPriceListFullDetail,
  getAvailablePriceLists,
  wizard_step_1_save,
  wizard_step_2_fetch_items,
  wizard_step_3_calculate,
  wizard_step_4_review,
  wizard_apply_prices,
  submitPriceList as apiSubmit,
  getCurrencyRates,
  convertPrices,
  getCostAnalysis,
  getBreakEvenAnalysis,
  getRawMaterialsReport,
  searchItemGroups as apiSearchItemGroups,
  searchBrands as apiSearchBrands,
  createPriceList
} from '@/data/api'
import SearchSelect from '@/components/SearchSelect.vue'
import ReportModal from '@/components/ReportModal.vue'
import {
  X as XIcon,
  Check as CheckIcon,
  CheckCircle as CheckCircleIcon,
  Settings as SettingsIcon,
  Package as PackageIcon,
  Calculator as CalculatorIcon,
  RefreshCw as RefreshCwIcon,
  ChevronLeft as ChevronLeftIcon,
  ChevronRight as ChevronRightIcon,
  Send as SendIcon,
  PieChart as PieChartIcon,
  TrendingUp as TrendingUpIcon,
  Boxes as BoxesIcon,
  Download as DownloadIcon,
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const currentStep = ref(1)
const totalSteps = 4
const priceListId = ref(route.params.id || null)
const priceListName = ref('')

const steps = [
  { title: 'تنظیمات پایه', icon: SettingsIcon },
  { title: 'انتخاب کالاها', icon: PackageIcon },
  { title: 'محاسبه قیمت‌ها', icon: CalculatorIcon },
  { title: 'بررسی و اعمال', icon: CheckCircleIcon },
]

// Form data
const formData = ref({
  price_list: '',
  valid_from: '',
  valid_until: '',
  profit_margin: 20,
  commission_percentage: 0,
  price_rounding_amount: 10000,
})

const filters = ref({
  item_group: '',
  brand: '',
  item_name_filter: '',
})

// Lists
const availablePriceLists = ref([])
const items = ref([])
const calculatedItems = ref([])
const itemSearchQuery = ref('')

// Currency
const currencies = ref([{ name: 'IRR', symbol: 'ریال' }])
const selectedCurrency = ref('IRR')
const exchangeRate = ref(1)
const convertedItems = ref([])

// Summary
const summary = ref({})

// Loading states
const fetchingItems = ref(false)
const calculating = ref(false)
const applying = ref(false)
const submitting = ref(false)

// Modals
const activeModal = ref(false)
const modalTitle = ref('')
const modalData = ref(null)
const modalType = ref('')

const filteredItems = computed(() => {
  if (!itemSearchQuery.value) return items.value
  const q = itemSearchQuery.value.toLowerCase()
  return items.value.filter(i => 
    i.item_code?.toLowerCase().includes(q) ||
    i.item_name?.toLowerCase().includes(q)
  )
})

const displayItems = computed(() => {
  if (selectedCurrency.value !== 'IRR' && convertedItems.value.length) {
    return convertedItems.value
  }
  return calculatedItems.value
})

const totalCost = computed(() => calculatedItems.value.reduce((s, i) => s + (i.total_cost || 0), 0))
const totalSelling = computed(() => calculatedItems.value.reduce((s, i) => s + (i.final_selected_price || i.selling_price || 0), 0))
const totalProfit = computed(() => calculatedItems.value.reduce((s, i) => s + (i.profit_amount || 0), 0))

const canProceed = computed(() => {
  switch (currentStep.value) {
    case 1: return formData.value.price_list && formData.value.profit_margin > 0
    case 2: return items.value.length > 0
    case 3: return calculatedItems.value.length > 0
    default: return true
  }
})

function getStepClass(step) {
  if (step === currentStep.value) return 'bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-400'
  if (step < currentStep.value) return 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
  return 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400'
}

function getStepNumberClass(step) {
  if (step === currentStep.value) return 'bg-primary-600 text-white'
  if (step < currentStep.value) return 'bg-green-600 text-white'
  return 'bg-gray-300 dark:bg-gray-600 text-gray-600 dark:text-gray-300'
}

function canGoToStep(step) {
  return step <= currentStep.value
}

function goToStep(step) {
  if (canGoToStep(step)) {
    currentStep.value = step
  }
}

async function nextStep() {
  if (!canProceed.value) return
  
  // Save current step
  if (currentStep.value === 1) {
    await saveStep1()
  }
  
  if (currentStep.value < totalSteps) {
    currentStep.value++
    
    // Auto actions for each step
    if (currentStep.value === 4) {
      await loadReview()
    }
  }
}

function prevStep() {
  if (currentStep.value > 1) {
    currentStep.value--
  }
}

async function loadData() {
  loading.value = true
  try {
    // Get available price lists
    availablePriceLists.value = await getAvailablePriceLists()
    
    // Get currencies
    try {
      const currData = await getCurrencyRates()
      currencies.value = [{ name: 'IRR', symbol: 'ریال' }, ...currData.currencies]
    } catch (e) {
      console.log('Currency rates not available')
    }
    
    // If editing existing
    if (priceListId.value) {
      const data = await getPriceListFullDetail(priceListId.value)
      priceListName.value = data.name
      
      formData.value = {
        price_list: data.price_list,
        valid_from: data.valid_from,
        valid_until: data.valid_until,
        profit_margin: data.profit_margin || 20,
        commission_percentage: data.commission_percentage || 0,
        price_rounding_amount: data.price_rounding_amount || 10000,
      }
      
      items.value = data.items || []
      if (items.value.length > 0 && items.value[0].total_cost) {
        calculatedItems.value = items.value
      }
    }
  } catch (error) {
    console.error('Error loading data:', error)
  } finally {
    loading.value = false
  }
}

async function saveStep1() {
  if (!priceListId.value) {
    // Create new price list
    const result = await createPriceList(formData.value)
    priceListId.value = result.name
    priceListName.value = result.name
    router.replace(`/pricing-wizard/${result.name}`)
  } else {
    await wizard_step_1_save(priceListId.value, formData.value)
  }
}

async function fetchItems() {
  fetchingItems.value = true
  try {
    const result = await wizard_step_2_fetch_items(priceListId.value, filters.value)
    items.value = result.items || []
  } catch (error) {
    console.error('Error fetching items:', error)
    alert('خطا در دریافت کالاها')
  } finally {
    fetchingItems.value = false
  }
}

async function calculatePrices() {
  calculating.value = true
  try {
    const result = await wizard_step_3_calculate(priceListId.value)
    calculatedItems.value = result.items || []
  } catch (error) {
    console.error('Error calculating:', error)
    alert('خطا در محاسبه قیمت‌ها')
  } finally {
    calculating.value = false
  }
}

async function loadReview() {
  try {
    const result = await wizard_step_4_review(priceListId.value)
    summary.value = result.summary || {}
  } catch (error) {
    console.error('Error loading review:', error)
  }
}

async function convertCurrency(currency) {
  selectedCurrency.value = currency
  
  if (currency === 'IRR') {
    convertedItems.value = []
    exchangeRate.value = 1
    return
  }
  
  try {
    const result = await convertPrices(priceListId.value, currency)
    convertedItems.value = result.items || []
    exchangeRate.value = result.exchange_rate || 1
  } catch (error) {
    console.error('Error converting:', error)
  }
}

async function applyPrices() {
  if (!confirm('آیا از اعمال قیمت‌ها به لیست قیمت مطمئن هستید؟')) return
  
  applying.value = true
  try {
    const result = await wizard_apply_prices(priceListId.value)
    alert(result.message || 'قیمت‌ها با موفقیت اعمال شدند')
  } catch (error) {
    console.error('Error applying:', error)
    alert('خطا در اعمال قیمت‌ها')
  } finally {
    applying.value = false
  }
}

async function submitPriceList() {
  if (!confirm('آیا از تأیید نهایی لیست قیمت مطمئن هستید؟')) return
  
  submitting.value = true
  try {
    await apiSubmit(priceListId.value)
    router.push(`/price-lists/${priceListId.value}`)
  } catch (error) {
    console.error('Error submitting:', error)
    alert('خطا در تأیید لیست قیمت')
  } finally {
    submitting.value = false
  }
}

// Search functions for autocomplete
async function searchItemGroups(query) {
  return apiSearchItemGroups(query)
}

async function searchBrands(query) {
  return apiSearchBrands(query)
}

// Reports
async function showCostAnalysis() {
  try {
    const data = await getCostAnalysis(priceListId.value)
    modalTitle.value = 'تحلیل هزینه'
    modalData.value = data
    modalType.value = 'cost'
    activeModal.value = true
  } catch (error) {
    alert('خطا در دریافت گزارش')
  }
}

async function showBreakEven() {
  try {
    const data = await getBreakEvenAnalysis(priceListId.value)
    modalTitle.value = 'تحلیل نقطه سربه‌سر'
    modalData.value = data
    modalType.value = 'breakeven'
    activeModal.value = true
  } catch (error) {
    alert('خطا در دریافت گزارش')
  }
}

async function showRawMaterials() {
  try {
    const data = await getRawMaterialsReport(priceListId.value)
    modalTitle.value = 'گزارش مواد اولیه'
    modalData.value = data
    modalType.value = 'materials'
    activeModal.value = true
  } catch (error) {
    alert('خطا در دریافت گزارش')
  }
}

function exportExcel() {
  // Generate CSV
  let csv = 'کد کالا,نام کالا,هزینه کل,قیمت فروش,سود\n'
  calculatedItems.value.forEach(item => {
    csv += `"${item.item_code}","${item.item_name}",${item.total_cost},${item.final_selected_price || item.selling_price},${item.profit_amount}\n`
  })
  
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `pricing_${priceListId.value}_${new Date().toISOString().slice(0,10)}.csv`
  link.click()
}

function formatNumber(num) {
  return new Intl.NumberFormat('fa-IR').format(num || 0)
}

function formatCurrency(num) {
  if (!num && num !== 0) return '-'
  return new Intl.NumberFormat('fa-IR').format(Math.round(num))
}

function formatDisplayPrice(num) {
  if (!num && num !== 0) return '-'
  if (selectedCurrency.value !== 'IRR') {
    return new Intl.NumberFormat('en-US', { 
      style: 'currency', 
      currency: selectedCurrency.value,
      minimumFractionDigits: 2 
    }).format(num)
  }
  return formatCurrency(num)
}

onMounted(() => {
  loadData()
})
</script>

