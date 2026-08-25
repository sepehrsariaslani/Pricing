<template>
  <div class="p-4 lg:p-6 space-y-6">
    <!-- Header -->
    <div class="flex items-center gap-4">
      <button @click="$router.back()" class="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg">
        <ArrowRightIcon class="w-5 h-5 text-gray-600 dark:text-gray-400" />
      </button>
      <div>
        <h1 class="text-2xl font-bold text-gray-900 dark:text-white">ایجاد لیست قیمت جدید</h1>
        <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">تنظیمات اولیه Auto Price List</p>
      </div>
    </div>

    <!-- Form -->
    <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6">
      <form @submit.prevent="createPriceList" class="space-y-6">
        <!-- Price List Selection -->
        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            لیست قیمت <span class="text-red-500">*</span>
          </label>
          <select
            v-model="form.price_list"
            required
            class="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="">انتخاب کنید...</option>
            <option v-for="pl in availablePriceLists" :key="pl.name" :value="pl.name">
              {{ pl.name }} ({{ pl.currency }})
            </option>
          </select>
        </div>

        <!-- Date Range -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              معتبر از تاریخ <span class="text-red-500">*</span>
            </label>
            <input
              type="date"
              v-model="form.valid_from"
              required
              class="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              معتبر تا تاریخ <span class="text-red-500">*</span>
            </label>
            <input
              type="date"
              v-model="form.valid_until"
              required
              class="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
        </div>

        <!-- Profit Margin -->
        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            حاشیه سود (درصد) <span class="text-red-500">*</span>
          </label>
          <input
            type="number"
            v-model="form.profit_margin"
            required
            min="0"
            max="100"
            step="0.1"
            class="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <!-- Commission -->
        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            درصد کمیسیون
          </label>
          <input
            type="number"
            v-model="form.commission_percentage"
            min="0"
            max="100"
            step="0.1"
            class="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <!-- Rounding -->
        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            مبلغ رند کردن قیمت
          </label>
          <input
            type="number"
            v-model="form.price_rounding_amount"
            min="0"
            step="1000"
            placeholder="مثال: 10000"
            class="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">قیمت‌ها به سمت بالا به این مبلغ رند می‌شوند</p>
        </div>

        <!-- Submit -->
        <div class="flex gap-3 pt-4">
          <button
            type="submit"
            :disabled="submitting"
            class="flex-1 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors font-medium"
          >
            <span v-if="submitting">در حال ایجاد...</span>
            <span v-else>ایجاد لیست قیمت</span>
          </button>
          <button
            type="button"
            @click="$router.back()"
            class="px-6 py-3 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          >
            انصراف
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getAvailablePriceLists, createPriceList as apiCreatePriceList } from '@/data/api'
import { ArrowRight as ArrowRightIcon } from 'lucide-vue-next'

const router = useRouter()

const availablePriceLists = ref([])
const submitting = ref(false)

const form = reactive({
  price_list: '',
  valid_from: new Date().toISOString().split('T')[0],
  valid_until: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
  profit_margin: 20,
  commission_percentage: 0,
  price_rounding_amount: 0,
})

async function loadPriceLists() {
  try {
    availablePriceLists.value = await getAvailablePriceLists()
  } catch (error) {
    console.error('Error loading price lists:', error)
  }
}

async function createPriceList() {
  submitting.value = true
  try {
    const result = await apiCreatePriceList(form)
    if (result?.success && result?.name) {
      router.push(`/price-lists/${result.name}`)
    }
  } catch (error) {
    console.error('Error creating price list:', error)
    alert('خطا در ایجاد لیست قیمت: ' + (error.message || 'خطای ناشناخته'))
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  loadPriceLists()
})
</script>

