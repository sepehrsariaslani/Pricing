<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900">
    <!-- Header -->
    <div class="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 sticky top-0 z-10">
      <div class="px-4 py-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <button @click="$router.back()" class="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg">
              <ArrowRightIcon class="w-5 h-5 text-gray-600 dark:text-gray-300" />
            </button>
            <div>
              <h1 class="text-xl font-bold text-gray-900 dark:text-white">واردات از لیست قیمت قبلی</h1>
              <p class="text-sm text-gray-500 dark:text-gray-400">{{ priceList?.price_list }}</p>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <span v-if="!isEditable" class="px-3 py-1 text-sm bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400 rounded-full">
              فقط خواندنی
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-20">
      <div class="w-8 h-8 border-4 border-primary-600 border-t-transparent rounded-full animate-spin"></div>
    </div>

    <!-- Content -->
    <div v-else class="p-4 max-w-6xl mx-auto space-y-6">
      <!-- Import Settings -->
      <div class="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
        <h2 class="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <DownloadIcon class="w-5 h-5" />
          تنظیمات واردات
        </h2>
        
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">لیست قیمت مرجع</label>
            <select
              v-model="importSettings.prevPriceList"
              :disabled="!isEditable"
              class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50"
            >
              <option value="">انتخاب کنید</option>
              <option v-for="pl in availablePriceLists" :key="pl.name" :value="pl.name">
                {{ pl.name }}
              </option>
            </select>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">درصد افزایش قیمت</label>
            <div class="relative">
              <input
                type="number"
                v-model.number="importSettings.increasePercent"
                :disabled="!isEditable"
                step="0.1"
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50"
              />
              <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">%</span>
            </div>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">مبلغ رند کردن</label>
            <input
              type="number"
              v-model.number="importSettings.roundingAmount"
              :disabled="!isEditable"
              step="1000"
              class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50"
            />
          </div>
          <div class="flex items-end">
            <button
              v-if="isEditable"
              @click="importFromPrevList"
              :disabled="importing || !importSettings.prevPriceList"
              class="w-full px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              <DownloadIcon class="w-4 h-4" />
              {{ importing ? 'در حال واردات...' : 'واردات قیمت‌ها' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Stats -->
      <div v-if="prevItems.length" class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div class="text-2xl font-bold text-gray-900 dark:text-white">{{ formatNumber(prevItems.length) }}</div>
          <div class="text-sm text-gray-500 dark:text-gray-400">تعداد کالا</div>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div class="text-2xl font-bold text-gray-900 dark:text-white">{{ formatNumber(includedCount) }}</div>
          <div class="text-sm text-gray-500 dark:text-gray-400">انتخاب شده</div>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div class="text-2xl font-bold text-green-600 dark:text-green-400">{{ formatNumber(avgIncrease) }}%</div>
          <div class="text-sm text-gray-500 dark:text-gray-400">میانگین افزایش</div>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div class="text-2xl font-bold text-primary-600 dark:text-primary-400">{{ formatCurrency(totalNewPrice) }}</div>
          <div class="text-sm text-gray-500 dark:text-gray-400">مجموع قیمت جدید</div>
        </div>
      </div>

      <!-- Items Table -->
      <div v-if="prevItems.length" class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div class="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <h2 class="text-lg font-bold text-gray-900 dark:text-white">کالاهای وارد شده</h2>
          <div class="flex items-center gap-2">
            <button
              @click="selectAll"
              class="px-3 py-1.5 text-sm bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600"
            >
              انتخاب همه
            </button>
            <button
              @click="deselectAll"
              class="px-3 py-1.5 text-sm bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600"
            >
              لغو انتخاب
            </button>
          </div>
        </div>
        
        <!-- Search -->
        <div class="p-4 border-b border-gray-200 dark:border-gray-700">
          <input
            type="text"
            v-model="searchQuery"
            placeholder="جستجو در کالاها..."
            class="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
          />
        </div>
        
        <div class="overflow-x-auto">
          <table class="w-full">
            <thead class="bg-gray-50 dark:bg-gray-700/50">
              <tr>
                <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">انتخاب</th>
                <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">کد کالا</th>
                <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">قیمت قبلی</th>
                <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">افزایش %</th>
                <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">رند</th>
                <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">قیمت جدید</th>
                <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">تفاوت</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-200 dark:divide-gray-700">
              <tr
                v-for="item in filteredItems"
                :key="item.item_code"
                class="hover:bg-gray-50 dark:hover:bg-gray-700/50"
                :class="{ 'opacity-50': !item.include }"
              >
                <td class="px-4 py-3">
                  <input
                    type="checkbox"
                    v-model="item.include"
                    :disabled="!isEditable"
                    @change="updateItem(item)"
                    class="w-4 h-4 text-primary-600 rounded"
                  />
                </td>
                <td class="px-4 py-3 text-sm text-gray-900 dark:text-white font-medium">
                  {{ item.item_code }}
                </td>
                <td class="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">
                  {{ formatCurrency(item.prev_price) }}
                </td>
                <td class="px-4 py-3">
                  <input
                    type="number"
                    v-model.number="item.increase_percent"
                    :disabled="!isEditable"
                    @change="recalculateItemPrice(item)"
                    step="0.1"
                    class="w-20 px-2 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm disabled:opacity-50"
                  />
                </td>
                <td class="px-4 py-3">
                  <input
                    type="number"
                    v-model.number="item.rounding_amount"
                    :disabled="!isEditable"
                    @change="recalculateItemPrice(item)"
                    step="1000"
                    class="w-24 px-2 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm disabled:opacity-50"
                  />
                </td>
                <td class="px-4 py-3">
                  <input
                    type="number"
                    v-model.number="item.new_price"
                    :disabled="!isEditable"
                    @change="updateItem(item)"
                    class="w-32 px-2 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm disabled:opacity-50"
                  />
                </td>
                <td class="px-4 py-3 text-sm">
                  <span :class="item.new_price > item.prev_price ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'">
                    {{ item.new_price > item.prev_price ? '+' : '' }}{{ formatCurrency(item.new_price - item.prev_price) }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        
        <!-- Apply Button -->
        <div v-if="isEditable" class="p-4 border-t border-gray-200 dark:border-gray-700 flex justify-end">
          <button
            @click="applyPrices"
            :disabled="applying || includedCount === 0"
            class="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 flex items-center gap-2 font-medium"
          >
            <CheckIcon class="w-5 h-5" />
            {{ applying ? 'در حال اعمال...' : `اعمال ${includedCount} قیمت به لیست قیمت` }}
          </button>
        </div>
      </div>

      <!-- Empty State -->
      <div v-else class="bg-white dark:bg-gray-800 rounded-xl p-12 border border-gray-200 dark:border-gray-700 text-center">
        <DownloadIcon class="w-12 h-12 mx-auto text-gray-400 mb-4" />
        <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-2">هیچ قیمتی وارد نشده</h3>
        <p class="text-gray-500 dark:text-gray-400">
          یک لیست قیمت مرجع انتخاب کرده و دکمه واردات را بزنید
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import {
  getPriceListFullDetail,
  getAvailablePriceLists,
  importFromPrevPriceList,
  updatePrevItem,
  applyPrevPricesToPriceList
} from '@/data/api'
import {
  ArrowRight as ArrowRightIcon,
  Download as DownloadIcon,
  Check as CheckIcon
} from 'lucide-vue-next'

const route = useRoute()
const priceListId = computed(() => route.params.id)

const loading = ref(true)
const importing = ref(false)
const applying = ref(false)
const priceList = ref(null)
const availablePriceLists = ref([])
const prevItems = ref([])
const searchQuery = ref('')

const importSettings = ref({
  prevPriceList: '',
  increasePercent: 0,
  roundingAmount: 10000,
})

const isEditable = computed(() => priceList.value?.is_editable || false)

const filteredItems = computed(() => {
  if (!searchQuery.value) return prevItems.value
  const q = searchQuery.value.toLowerCase()
  return prevItems.value.filter(item => 
    item.item_code.toLowerCase().includes(q)
  )
})

const includedCount = computed(() => prevItems.value.filter(i => i.include).length)

const avgIncrease = computed(() => {
  const included = prevItems.value.filter(i => i.include)
  if (!included.length) return 0
  const sum = included.reduce((acc, i) => acc + (i.increase_percent || 0), 0)
  return (sum / included.length).toFixed(1)
})

const totalNewPrice = computed(() => {
  return prevItems.value
    .filter(i => i.include)
    .reduce((acc, i) => acc + (i.new_price || 0), 0)
})

async function loadData() {
  loading.value = true
  try {
    const [plData, priceLists] = await Promise.all([
      getPriceListFullDetail(priceListId.value),
      getAvailablePriceLists()
    ])
    
    priceList.value = plData
    availablePriceLists.value = priceLists
    
    // Load existing prev_items if any
    if (plData.prev_items?.length) {
      prevItems.value = plData.prev_items.map(item => ({
        ...item,
        include: item.include !== 0
      }))
    }
    
    // Set import settings from existing data
    if (plData.compare_previous_price_list) {
      importSettings.value.prevPriceList = plData.compare_previous_price_list
    }
    if (plData.prev_price_increase_percent) {
      importSettings.value.increasePercent = plData.prev_price_increase_percent
    }
    if (plData.prev_price_rounding_amount) {
      importSettings.value.roundingAmount = plData.prev_price_rounding_amount
    }
  } catch (error) {
    console.error('Error loading data:', error)
  } finally {
    loading.value = false
  }
}

async function importFromPrevList() {
  if (!importSettings.value.prevPriceList) return
  
  importing.value = true
  try {
    const result = await importFromPrevPriceList(
      priceListId.value,
      importSettings.value.prevPriceList,
      importSettings.value.increasePercent,
      importSettings.value.roundingAmount
    )
    
    // Reload to get the imported items
    await loadData()
  } catch (error) {
    console.error('Error importing:', error)
    alert('خطا در واردات قیمت‌ها')
  } finally {
    importing.value = false
  }
}

function recalculateItemPrice(item) {
  let newPrice = item.prev_price * (1 + item.increase_percent / 100)
  if (item.rounding_amount > 0) {
    newPrice = Math.ceil(newPrice / item.rounding_amount) * item.rounding_amount
  }
  item.new_price = newPrice
  updateItem(item)
}

async function updateItem(item) {
  if (!isEditable.value) return
  
  try {
    await updatePrevItem(priceListId.value, item.item_code, {
      increase_percent: item.increase_percent,
      rounding_amount: item.rounding_amount,
      new_price: item.new_price,
      include: item.include ? 1 : 0,
    })
  } catch (error) {
    console.error('Error updating item:', error)
  }
}

function selectAll() {
  prevItems.value.forEach(item => {
    item.include = true
  })
}

function deselectAll() {
  prevItems.value.forEach(item => {
    item.include = false
  })
}

async function applyPrices() {
  if (!isEditable.value || includedCount.value === 0) return
  
  if (!confirm(`آیا از اعمال ${includedCount.value} قیمت به لیست قیمت مطمئن هستید؟`)) return
  
  applying.value = true
  try {
    const result = await applyPrevPricesToPriceList(priceListId.value)
    alert(result.message || 'قیمت‌ها با موفقیت اعمال شدند')
  } catch (error) {
    console.error('Error applying prices:', error)
    alert('خطا در اعمال قیمت‌ها')
  } finally {
    applying.value = false
  }
}

function formatNumber(num) {
  return new Intl.NumberFormat('fa-IR').format(num || 0)
}

function formatCurrency(num) {
  return new Intl.NumberFormat('fa-IR').format(num || 0) + ' ریال'
}

onMounted(() => {
  loadData()
})
</script>

