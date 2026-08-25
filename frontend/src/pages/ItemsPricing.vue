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
              <h1 class="text-xl font-bold text-gray-900 dark:text-white">قیمت‌گذاری کالاها</h1>
              <p class="text-sm text-gray-500 dark:text-gray-400">{{ priceList?.price_list }} • {{ items.length }} کالا</p>
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

    <div v-else class="p-4 space-y-4">
      <!-- Filters & Actions -->
      <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
        <div class="grid grid-cols-1 md:grid-cols-5 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">گروه کالا</label>
            <select
              v-model="filters.item_group"
              class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
            >
              <option value="">همه</option>
              <option v-for="g in itemGroups" :key="g.name" :value="g.name">{{ g.name }}</option>
            </select>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">برند</label>
            <select
              v-model="filters.brand"
              class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
            >
              <option value="">همه</option>
              <option v-for="b in brands" :key="b.name" :value="b.name">{{ b.name }}</option>
            </select>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">فیلتر نام</label>
            <input
              type="text"
              v-model="filters.item_name_filter"
              placeholder="جستجو..."
              class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
            />
          </div>
          <div class="flex items-end">
            <button
              @click="fetchItems"
              :disabled="fetching"
              class="w-full px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              <RefreshCwIcon class="w-4 h-4" :class="{ 'animate-spin': fetching }" />
              {{ fetching ? 'در حال دریافت...' : 'دریافت کالاها' }}
            </button>
          </div>
          <div class="flex items-end">
            <button
              v-if="isEditable"
              @click="removeItems"
              :disabled="removing"
              class="w-full px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              <TrashIcon class="w-4 h-4" />
              حذف با فیلتر
            </button>
          </div>
        </div>
      </div>

      <!-- Action Buttons -->
      <div class="flex flex-wrap gap-3">
        <button
          @click="calculatePrices"
          :disabled="calculating || items.length === 0"
          class="px-5 py-2.5 bg-cyan-600 text-white rounded-lg hover:bg-cyan-700 disabled:opacity-50 flex items-center gap-2"
        >
          <CalculatorIcon class="w-5 h-5" />
          {{ calculating ? 'در حال محاسبه...' : 'محاسبه قیمت‌ها' }}
        </button>
        <button
          @click="updatePrices"
          :disabled="updating || items.length === 0"
          class="px-5 py-2.5 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 flex items-center gap-2"
        >
          <CheckCircleIcon class="w-5 h-5" />
          {{ updating ? 'در حال اعمال...' : 'اعمال قیمت‌ها' }}
        </button>
      </div>

      <!-- Summary Stats -->
      <div v-if="items.length" class="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div class="text-2xl font-bold text-gray-900 dark:text-white">{{ formatNumber(items.length) }}</div>
          <div class="text-sm text-gray-500 dark:text-gray-400">تعداد کالا</div>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div class="text-2xl font-bold text-gray-900 dark:text-white">{{ formatCurrency(totalCost) }}</div>
          <div class="text-sm text-gray-500 dark:text-gray-400">مجموع هزینه</div>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div class="text-2xl font-bold text-primary-600 dark:text-primary-400">{{ formatCurrency(totalSelling) }}</div>
          <div class="text-sm text-gray-500 dark:text-gray-400">مجموع فروش</div>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div class="text-2xl font-bold text-green-600 dark:text-green-400">{{ formatCurrency(totalProfit) }}</div>
          <div class="text-sm text-gray-500 dark:text-gray-400">مجموع سود</div>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div class="text-2xl font-bold text-purple-600 dark:text-purple-400">{{ avgProfitMargin.toFixed(1) }}%</div>
          <div class="text-sm text-gray-500 dark:text-gray-400">میانگین سود</div>
        </div>
      </div>

      <!-- Items Table -->
      <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div class="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <h2 class="font-bold text-gray-900 dark:text-white">لیست کالاها</h2>
          <input
            type="text"
            v-model="searchQuery"
            placeholder="جستجو در جدول..."
            class="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm w-48"
          />
        </div>
        
        <div v-if="items.length === 0" class="p-12 text-center text-gray-500 dark:text-gray-400">
          <PackageIcon class="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>کالایی یافت نشد. ابتدا با فیلترها کالاها را دریافت کنید.</p>
        </div>
        
        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="bg-gray-50 dark:bg-gray-700/50">
              <tr>
                <th class="px-3 py-3 text-right font-medium text-gray-600 dark:text-gray-300 sticky right-0 bg-gray-50 dark:bg-gray-700/50">کالا</th>
                <th class="px-3 py-3 text-right font-medium text-gray-600 dark:text-gray-300">مواد اولیه</th>
                <th class="px-3 py-3 text-right font-medium text-gray-600 dark:text-gray-300">برق</th>
                <th class="px-3 py-3 text-right font-medium text-gray-600 dark:text-gray-300">مصرفی</th>
                <th class="px-3 py-3 text-right font-medium text-gray-600 dark:text-gray-300">اجاره</th>
                <th class="px-3 py-3 text-right font-medium text-gray-600 dark:text-gray-300">نیروی کار</th>
                <th class="px-3 py-3 text-right font-medium text-gray-600 dark:text-gray-300">پیمانکاری</th>
                <th class="px-3 py-3 text-right font-medium text-gray-600 dark:text-gray-300">سربار</th>
                <th class="px-3 py-3 text-right font-medium text-gray-600 dark:text-gray-300 bg-gray-100 dark:bg-gray-600">هزینه کل</th>
                <th class="px-3 py-3 text-right font-medium text-gray-600 dark:text-gray-300 bg-blue-50 dark:bg-blue-900/30">قیمت فروش</th>
                <th class="px-3 py-3 text-right font-medium text-gray-600 dark:text-gray-300 bg-green-50 dark:bg-green-900/30">سود</th>
                <th v-if="isEditable" class="px-3 py-3 text-center font-medium text-gray-600 dark:text-gray-300">عملیات</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100 dark:divide-gray-700">
              <tr 
                v-for="item in filteredItems" 
                :key="item.item_code"
                class="hover:bg-gray-50 dark:hover:bg-gray-700/30"
                :class="{ 'bg-amber-50 dark:bg-amber-900/10': editingItem === item.item_code }"
              >
                <td class="px-3 py-2 sticky right-0 bg-white dark:bg-gray-800">
                  <div class="font-medium text-gray-900 dark:text-white">{{ item.item_name || item.item_code }}</div>
                  <div class="text-xs text-gray-500">{{ item.item_code }}</div>
                </td>
                <td class="px-3 py-2">
                  <EditableCell
                    :value="item.raw_material_cost"
                    :editable="isEditable && editingItem === item.item_code"
                    @update="val => updateItemField(item, 'raw_material_cost', val)"
                  />
                </td>
                <td class="px-3 py-2">
                  <EditableCell
                    :value="item.electricity_cost"
                    :editable="isEditable && editingItem === item.item_code"
                    @update="val => updateItemField(item, 'electricity_cost', val)"
                  />
                </td>
                <td class="px-3 py-2">
                  <EditableCell
                    :value="item.consumable_cost"
                    :editable="isEditable && editingItem === item.item_code"
                    @update="val => updateItemField(item, 'consumable_cost', val)"
                  />
                </td>
                <td class="px-3 py-2">
                  <EditableCell
                    :value="item.rent_cost"
                    :editable="isEditable && editingItem === item.item_code"
                    @update="val => updateItemField(item, 'rent_cost', val)"
                  />
                </td>
                <td class="px-3 py-2">
                  <EditableCell
                    :value="item.labor_cost"
                    :editable="isEditable && editingItem === item.item_code"
                    @update="val => updateItemField(item, 'labor_cost', val)"
                  />
                </td>
                <td class="px-3 py-2">
                  <EditableCell
                    :value="item.subcontracting_cost"
                    :editable="isEditable && editingItem === item.item_code"
                    @update="val => updateItemField(item, 'subcontracting_cost', val)"
                  />
                </td>
                <td class="px-3 py-2">
                  <EditableCell
                    :value="item.overhead_cost"
                    :editable="isEditable && editingItem === item.item_code"
                    @update="val => updateItemField(item, 'overhead_cost', val)"
                  />
                </td>
                <td class="px-3 py-2 bg-gray-50 dark:bg-gray-700/30 font-medium">
                  {{ formatCurrency(item.total_cost) }}
                </td>
                <td class="px-3 py-2 bg-blue-50 dark:bg-blue-900/20 font-bold text-primary-600 dark:text-primary-400">
                  {{ formatCurrency(item.final_selected_price || item.selling_price) }}
                </td>
                <td class="px-3 py-2 bg-green-50 dark:bg-green-900/20" :class="(item.profit_amount || 0) >= 0 ? 'text-green-600' : 'text-red-600'">
                  {{ formatCurrency(item.profit_amount) }}
                </td>
                <td v-if="isEditable" class="px-3 py-2 text-center">
                  <button
                    v-if="editingItem !== item.item_code"
                    @click="startEditing(item)"
                    class="p-1.5 text-gray-500 hover:text-primary-600 hover:bg-primary-50 dark:hover:bg-primary-900/30 rounded"
                    title="ویرایش"
                  >
                    <EditIcon class="w-4 h-4" />
                  </button>
                  <div v-else class="flex items-center justify-center gap-1">
                    <button
                      @click="saveItemCosts(item)"
                      :disabled="savingItem"
                      class="p-1.5 text-green-600 hover:bg-green-50 dark:hover:bg-green-900/30 rounded"
                      title="ذخیره"
                    >
                      <CheckIcon class="w-4 h-4" />
                    </button>
                    <button
                      @click="cancelEditing"
                      class="p-1.5 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                      title="انصراف"
                    >
                      <XIcon class="w-4 h-4" />
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { 
  getPriceListFullDetail,
  fetchItemsForPriceList, 
  calculatePrices as apiCalculatePrices,
  updatePricesToPriceList,
  removeItemsFromPriceList,
  updateItemCosts,
  getItemGroups,
  getBrands,
} from '@/data/api'
import {
  ArrowRight as ArrowRightIcon,
  Calculator as CalculatorIcon,
  CheckCircle as CheckCircleIcon,
  Package as PackageIcon,
  RefreshCw as RefreshCwIcon,
  Trash2 as TrashIcon,
  Edit as EditIcon,
  Check as CheckIcon,
  X as XIcon,
} from 'lucide-vue-next'

// Editable Cell Component
const EditableCell = {
  props: ['value', 'editable'],
  emits: ['update'],
  template: `
    <div>
      <input
        v-if="editable"
        type="number"
        :value="value || 0"
        @input="$emit('update', parseFloat($event.target.value) || 0)"
        class="w-20 px-2 py-1 border border-primary-300 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
      />
      <span v-else class="text-gray-600 dark:text-gray-400">{{ formatVal(value) }}</span>
    </div>
  `,
  methods: {
    formatVal(v) {
      if (!v && v !== 0) return '-'
      return new Intl.NumberFormat('fa-IR').format(Math.round(v))
    }
  }
}

const route = useRoute()
const priceListId = computed(() => route.params.id)

const loading = ref(true)
const fetching = ref(false)
const calculating = ref(false)
const updating = ref(false)
const removing = ref(false)
const savingItem = ref(false)

const priceList = ref(null)
const items = ref([])
const itemGroups = ref([])
const brands = ref([])
const searchQuery = ref('')
const editingItem = ref(null)
const editingItemBackup = ref(null)

const filters = reactive({
  item_group: '',
  brand: '',
  item_name_filter: '',
})

const isEditable = computed(() => priceList.value?.is_editable || false)

const filteredItems = computed(() => {
  if (!searchQuery.value) return items.value
  const q = searchQuery.value.toLowerCase()
  return items.value.filter(item => 
    (item.item_code?.toLowerCase().includes(q)) ||
    (item.item_name?.toLowerCase().includes(q))
  )
})

const totalCost = computed(() => items.value.reduce((sum, i) => sum + (i.total_cost || 0), 0))
const totalSelling = computed(() => items.value.reduce((sum, i) => sum + (i.final_selected_price || i.selling_price || 0), 0))
const totalProfit = computed(() => items.value.reduce((sum, i) => sum + (i.profit_amount || 0), 0))
const avgProfitMargin = computed(() => {
  if (totalCost.value === 0) return 0
  return (totalProfit.value / totalCost.value) * 100
})

function formatNumber(num) {
  return new Intl.NumberFormat('fa-IR').format(num || 0)
}

function formatCurrency(num) {
  if (!num && num !== 0) return '-'
  return new Intl.NumberFormat('fa-IR').format(Math.round(num))
}

async function loadData() {
  loading.value = true
  try {
    const [plData, groupsData, brandsData] = await Promise.all([
      getPriceListFullDetail(priceListId.value),
      getItemGroups(),
      getBrands(),
    ])
    priceList.value = plData
    items.value = plData?.items || []
    itemGroups.value = groupsData || []
    brands.value = brandsData || []
  } catch (error) {
    console.error('Error loading data:', error)
  } finally {
    loading.value = false
  }
}

async function fetchItems() {
  fetching.value = true
  try {
    const result = await fetchItemsForPriceList(priceListId.value, filters)
    if (result?.items) {
      // Reload full data to get updated items
      await loadData()
    }
  } catch (error) {
    console.error('Error fetching items:', error)
    alert('خطا در دریافت کالاها')
  } finally {
    fetching.value = false
  }
}

async function removeItems() {
  if (!confirm('آیا از حذف کالاها با این فیلترها مطمئن هستید؟')) return
  
  removing.value = true
  try {
    await removeItemsFromPriceList(priceListId.value, filters)
    await loadData()
  } catch (error) {
    console.error('Error removing items:', error)
    alert('خطا در حذف کالاها')
  } finally {
    removing.value = false
  }
}

async function calculatePrices() {
  calculating.value = true
  try {
    const result = await apiCalculatePrices(priceListId.value)
    if (result?.items) {
      items.value = result.items
    }
    alert('محاسبه قیمت‌ها با موفقیت انجام شد')
  } catch (error) {
    console.error('Error calculating prices:', error)
    alert('خطا در محاسبه قیمت‌ها')
  } finally {
    calculating.value = false
  }
}

async function updatePrices() {
  if (!confirm('آیا از اعمال قیمت‌ها به لیست قیمت مطمئن هستید؟')) return
  
  updating.value = true
  try {
    const result = await updatePricesToPriceList(priceListId.value)
    alert(result?.message || 'قیمت‌ها با موفقیت اعمال شدند')
  } catch (error) {
    console.error('Error updating prices:', error)
    alert('خطا در اعمال قیمت‌ها')
  } finally {
    updating.value = false
  }
}

function startEditing(item) {
  editingItem.value = item.item_code
  editingItemBackup.value = { ...item }
}

function cancelEditing() {
  // Restore backup
  if (editingItemBackup.value) {
    const idx = items.value.findIndex(i => i.item_code === editingItem.value)
    if (idx !== -1) {
      items.value[idx] = { ...editingItemBackup.value }
    }
  }
  editingItem.value = null
  editingItemBackup.value = null
}

function updateItemField(item, field, value) {
  item[field] = value
  // Recalculate operation_cost and total_cost locally
  item.operation_cost = (item.electricity_cost || 0) + (item.consumable_cost || 0) + 
                        (item.rent_cost || 0) + (item.labor_cost || 0) + (item.subcontracting_cost || 0)
  item.total_cost = (item.raw_material_cost || 0) + item.operation_cost + (item.overhead_cost || 0)
}

async function saveItemCosts(item) {
  savingItem.value = true
  try {
    await updateItemCosts(priceListId.value, item.item_code, {
      raw_material_cost: item.raw_material_cost,
      electricity_cost: item.electricity_cost,
      consumable_cost: item.consumable_cost,
      rent_cost: item.rent_cost,
      labor_cost: item.labor_cost,
      subcontracting_cost: item.subcontracting_cost,
      overhead_cost: item.overhead_cost,
    })
    editingItem.value = null
    editingItemBackup.value = null
  } catch (error) {
    console.error('Error saving item costs:', error)
    alert('خطا در ذخیره هزینه‌ها')
  } finally {
    savingItem.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>
