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
              <h1 class="text-xl font-bold text-gray-900 dark:text-white">مدیریت مواد اولیه</h1>
              <p class="text-sm text-gray-500 dark:text-gray-400">{{ priceList?.price_list }}</p>
            </div>
          </div>
          <span v-if="!isEditable" class="px-3 py-1 text-sm bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400 rounded-full">
            فقط خواندنی
          </span>
        </div>
      </div>
      
      <!-- Tabs -->
      <div class="px-4 flex gap-1 overflow-x-auto">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          @click="activeTab = tab.id"
          class="px-4 py-3 text-sm font-medium whitespace-nowrap border-b-2 transition-colors"
          :class="activeTab === tab.id 
            ? 'border-purple-600 text-purple-600 dark:text-purple-400' 
            : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'"
        >
          {{ tab.label }}
          <span v-if="tab.count" class="ml-1 px-1.5 py-0.5 text-xs bg-gray-200 dark:bg-gray-700 rounded-full">{{ tab.count }}</span>
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-20">
      <div class="w-8 h-8 border-4 border-purple-600 border-t-transparent rounded-full animate-spin"></div>
    </div>

    <!-- Content -->
    <div v-else class="p-4 max-w-5xl mx-auto space-y-6">
      
      <!-- Manual Material Prices Tab -->
      <div v-show="activeTab === 'manual'" class="space-y-4">
        <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
          <div class="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
            <h2 class="font-bold text-gray-900 dark:text-white">قیمت‌های دستی مواد اولیه</h2>
            <button
              v-if="isEditable"
              @click="showAddMaterialModal = true"
              class="px-3 py-1.5 bg-purple-600 text-white rounded-lg hover:bg-purple-700 text-sm flex items-center gap-1"
            >
              <PlusIcon class="w-4 h-4" />
              افزودن
            </button>
          </div>
          
          <div v-if="manualMaterialPrices.length === 0" class="p-12 text-center text-gray-500 dark:text-gray-400">
            <PackageIcon class="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>قیمت دستی مواد اولیه‌ای تعریف نشده است</p>
          </div>
          
          <div v-else class="divide-y divide-gray-200 dark:divide-gray-700">
            <div
              v-for="price in manualMaterialPrices"
              :key="price.item_code"
              class="flex items-center gap-4 p-4 hover:bg-gray-50 dark:hover:bg-gray-700/30"
            >
              <div class="flex-1 min-w-0">
                <div class="font-medium text-gray-900 dark:text-white truncate">{{ price.item_name || price.item_code }}</div>
                <div class="text-sm text-gray-500 dark:text-gray-400">{{ price.item_code }}</div>
              </div>
              <div v-if="editingMaterial === price.item_code" class="flex items-center gap-2">
                <input
                  type="number"
                  v-model.number="editingMaterialPrice"
                  class="w-32 px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                />
                <button @click="saveMaterialPrice(price)" class="p-1.5 text-green-600 hover:bg-green-50 rounded">
                  <CheckIcon class="w-4 h-4" />
                </button>
                <button @click="cancelEditMaterial" class="p-1.5 text-gray-500 hover:bg-gray-100 rounded">
                  <XIcon class="w-4 h-4" />
                </button>
              </div>
              <div v-else class="flex items-center gap-3">
                <div class="font-bold text-purple-600 dark:text-purple-400">
                  {{ formatCurrency(price.manual_price) }}
                </div>
                <button
                  v-if="isEditable"
                  @click="startEditMaterial(price)"
                  class="p-1.5 text-gray-500 hover:text-purple-600 hover:bg-purple-50 dark:hover:bg-purple-900/30 rounded"
                >
                  <EditIcon class="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Missing Materials Tab -->
      <div v-show="activeTab === 'missing'" class="space-y-4">
        <div class="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-4">
          <div class="flex gap-3">
            <AlertTriangleIcon class="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
            <div>
              <h3 class="font-medium text-amber-900 dark:text-amber-300">مواد اولیه بدون قیمت</h3>
              <p class="text-sm text-amber-700 dark:text-amber-400 mt-1">
                این مواد در BOM کالاها استفاده شده‌اند اما قیمت ندارند. برای محاسبه صحیح هزینه، قیمت آن‌ها را تعریف کنید.
              </p>
            </div>
          </div>
        </div>
        
        <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
          <div v-if="missingMaterials.length === 0" class="p-12 text-center text-gray-500 dark:text-gray-400">
            <CheckCircleIcon class="w-12 h-12 mx-auto mb-4 text-green-500 opacity-50" />
            <p>همه مواد اولیه قیمت دارند!</p>
          </div>
          
          <div v-else class="divide-y divide-gray-200 dark:divide-gray-700">
            <div
              v-for="material in missingMaterials"
              :key="material.item_code"
              class="flex items-center gap-4 p-4 hover:bg-gray-50 dark:hover:bg-gray-700/30"
            >
              <AlertTriangleIcon class="w-5 h-5 text-amber-500 flex-shrink-0" />
              <div class="flex-1 min-w-0">
                <div class="font-medium text-gray-900 dark:text-white truncate">{{ material.item_name || material.item_code }}</div>
                <div class="text-sm text-gray-500 dark:text-gray-400">{{ material.item_code }}</div>
              </div>
              <button
                v-if="isEditable"
                @click="addPriceForMissing(material)"
                class="px-3 py-1.5 bg-purple-600 text-white rounded-lg hover:bg-purple-700 text-sm"
              >
                تعریف قیمت
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Material Substitutions Tab -->
      <div v-show="activeTab === 'substitutions'" class="space-y-4">
        <div class="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl p-4">
          <div class="flex gap-3">
            <RefreshCwIcon class="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
            <div>
              <h3 class="font-medium text-blue-900 dark:text-blue-300">جایگزینی مواد</h3>
              <p class="text-sm text-blue-700 dark:text-blue-400 mt-1">
                می‌توانید برای محاسبه هزینه، یک ماده اولیه را با ماده دیگری جایگزین کنید.
              </p>
            </div>
          </div>
        </div>
        
        <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
          <div class="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
            <h2 class="font-bold text-gray-900 dark:text-white">جایگزینی‌های تعریف شده</h2>
            <button
              v-if="isEditable"
              @click="addSubstitution"
              class="px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm flex items-center gap-1"
            >
              <PlusIcon class="w-4 h-4" />
              افزودن جایگزین
            </button>
          </div>
          
          <div v-if="materialSubstitutions.length === 0" class="p-12 text-center text-gray-500 dark:text-gray-400">
            <RefreshCwIcon class="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>جایگزینی تعریف نشده است</p>
          </div>
          
          <div v-else class="divide-y divide-gray-200 dark:divide-gray-700">
            <div
              v-for="(sub, index) in materialSubstitutions"
              :key="index"
              class="flex items-center gap-4 p-4"
            >
              <div class="flex-1">
                <input
                  v-if="isEditable"
                  type="text"
                  v-model="sub.original_item"
                  placeholder="کد ماده اصلی"
                  class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
                />
                <span v-else class="text-gray-900 dark:text-white">{{ sub.original_item }}</span>
              </div>
              <ArrowLeftIcon class="w-5 h-5 text-gray-400" />
              <div class="flex-1">
                <input
                  v-if="isEditable"
                  type="text"
                  v-model="sub.substitute_item"
                  placeholder="کد ماده جایگزین"
                  class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
                />
                <span v-else class="text-gray-900 dark:text-white">{{ sub.substitute_item }}</span>
              </div>
              <button
                v-if="isEditable"
                @click="removeSubstitution(index)"
                class="p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 rounded"
              >
                <TrashIcon class="w-4 h-4" />
              </button>
            </div>
          </div>
          
          <div v-if="isEditable && materialSubstitutions.length > 0" class="p-4 border-t border-gray-200 dark:border-gray-700">
            <button
              @click="saveSubstitutions"
              :disabled="savingSubstitutions"
              class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {{ savingSubstitutions ? 'در حال ذخیره...' : 'ذخیره تغییرات' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Add Material Price Modal -->
    <Teleport to="body">
      <div v-if="showAddMaterialModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
        <div class="bg-white dark:bg-gray-800 rounded-xl max-w-md w-full p-6">
          <h3 class="text-lg font-bold text-gray-900 dark:text-white mb-4">افزودن قیمت دستی ماده</h3>
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">کد کالا</label>
              <input
                type="text"
                v-model="newMaterialPrice.item_code"
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">قیمت (ریال)</label>
              <input
                type="number"
                v-model.number="newMaterialPrice.manual_price"
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
            </div>
          </div>
          <div class="flex justify-end gap-3 mt-6">
            <button
              @click="showAddMaterialModal = false"
              class="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
            >
              انصراف
            </button>
            <button
              @click="addNewMaterialPrice"
              :disabled="!newMaterialPrice.item_code || !newMaterialPrice.manual_price"
              class="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
            >
              افزودن
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import {
  getPriceListFullDetail,
  updateManualMaterialPrice,
  getMissingMaterials,
  updateMaterialSubstitutions
} from '@/data/api'
import {
  ArrowRight as ArrowRightIcon,
  ArrowLeft as ArrowLeftIcon,
  Package as PackageIcon,
  Plus as PlusIcon,
  Edit as EditIcon,
  Check as CheckIcon,
  X as XIcon,
  Trash2 as TrashIcon,
  AlertTriangle as AlertTriangleIcon,
  CheckCircle as CheckCircleIcon,
  RefreshCw as RefreshCwIcon,
} from 'lucide-vue-next'

const route = useRoute()
const priceListId = computed(() => route.params.id)

const loading = ref(true)
const priceList = ref(null)
const manualMaterialPrices = ref([])
const missingMaterials = ref([])
const materialSubstitutions = ref([])
const activeTab = ref('manual')
const savingSubstitutions = ref(false)

const editingMaterial = ref(null)
const editingMaterialPrice = ref(0)
const showAddMaterialModal = ref(false)
const newMaterialPrice = ref({ item_code: '', manual_price: 0 })

const isEditable = computed(() => priceList.value?.is_editable || false)

const tabs = computed(() => [
  { id: 'manual', label: 'قیمت‌های دستی', count: manualMaterialPrices.value.length },
  { id: 'missing', label: 'بدون قیمت', count: missingMaterials.value.length },
  { id: 'substitutions', label: 'جایگزینی', count: materialSubstitutions.value.length },
])

async function loadData() {
  loading.value = true
  try {
    const [plData, missingData] = await Promise.all([
      getPriceListFullDetail(priceListId.value),
      getMissingMaterials(priceListId.value)
    ])
    
    priceList.value = plData
    manualMaterialPrices.value = plData?.manual_material_prices || []
    materialSubstitutions.value = plData?.material_substitutions || []
    missingMaterials.value = missingData?.missing_materials || []
  } catch (error) {
    console.error('Error loading data:', error)
  } finally {
    loading.value = false
  }
}

function formatCurrency(num) {
  if (!num && num !== 0) return '-'
  return new Intl.NumberFormat('fa-IR').format(Math.round(num)) + ' ریال'
}

function startEditMaterial(price) {
  editingMaterial.value = price.item_code
  editingMaterialPrice.value = price.manual_price || 0
}

function cancelEditMaterial() {
  editingMaterial.value = null
  editingMaterialPrice.value = 0
}

async function saveMaterialPrice(price) {
  try {
    await updateManualMaterialPrice(priceListId.value, price.item_code, editingMaterialPrice.value)
    price.manual_price = editingMaterialPrice.value
    editingMaterial.value = null
  } catch (error) {
    console.error('Error saving material price:', error)
    alert('خطا در ذخیره قیمت')
  }
}

async function addNewMaterialPrice() {
  try {
    await updateManualMaterialPrice(priceListId.value, newMaterialPrice.value.item_code, newMaterialPrice.value.manual_price)
    manualMaterialPrices.value.push({
      item_code: newMaterialPrice.value.item_code,
      manual_price: newMaterialPrice.value.manual_price
    })
    showAddMaterialModal.value = false
    newMaterialPrice.value = { item_code: '', manual_price: 0 }
  } catch (error) {
    console.error('Error adding material price:', error)
    alert('خطا در افزودن قیمت')
  }
}

function addPriceForMissing(material) {
  newMaterialPrice.value = { item_code: material.item_code, manual_price: 0 }
  showAddMaterialModal.value = true
}

function addSubstitution() {
  materialSubstitutions.value.push({ original_item: '', substitute_item: '' })
}

function removeSubstitution(index) {
  materialSubstitutions.value.splice(index, 1)
}

async function saveSubstitutions() {
  savingSubstitutions.value = true
  try {
    await updateMaterialSubstitutions(priceListId.value, materialSubstitutions.value)
    alert('جایگزینی‌ها ذخیره شد')
  } catch (error) {
    console.error('Error saving substitutions:', error)
    alert('خطا در ذخیره جایگزینی‌ها')
  } finally {
    savingSubstitutions.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>
