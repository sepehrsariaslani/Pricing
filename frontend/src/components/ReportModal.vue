<template>
  <Teleport to="body">
    <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" @click.self="$emit('close')">
      <div class="bg-white dark:bg-gray-800 rounded-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        <!-- Header -->
        <div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <h2 class="text-xl font-bold text-gray-900 dark:text-white">{{ title }}</h2>
          <button @click="$emit('close')" class="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg">
            <XIcon class="w-5 h-5 text-gray-500" />
          </button>
        </div>
        
        <!-- Content -->
        <div class="flex-1 overflow-y-auto p-6">
          <!-- Cost Analysis -->
          <template v-if="type === 'cost'">
            <div class="space-y-6">
              <!-- Summary Cards -->
              <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div class="bg-gray-50 dark:bg-gray-700/50 rounded-xl p-4 text-center">
                  <div class="text-2xl font-bold text-gray-900 dark:text-white">{{ data.items_count }}</div>
                  <div class="text-sm text-gray-500">تعداد کالا</div>
                </div>
                <div class="bg-blue-50 dark:bg-blue-900/20 rounded-xl p-4 text-center">
                  <div class="text-2xl font-bold text-blue-600">{{ formatCurrency(data.total_cost) }}</div>
                  <div class="text-sm text-gray-500">هزینه کل</div>
                </div>
              </div>
              
              <!-- Breakdown Chart -->
              <div class="bg-gray-50 dark:bg-gray-700/30 rounded-xl p-4">
                <h3 class="font-bold text-gray-900 dark:text-white mb-4">تفکیک هزینه‌ها</h3>
                <div class="space-y-3">
                  <div v-for="(value, key) in data.breakdown" :key="key" class="flex items-center gap-4">
                    <span class="w-24 text-sm text-gray-600 dark:text-gray-400">{{ getCostLabel(key) }}</span>
                    <div class="flex-1 h-6 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                      <div
                        class="h-full rounded-full transition-all"
                        :class="getCostColor(key)"
                        :style="{ width: (data.percentages?.[key] || 0) + '%' }"
                      ></div>
                    </div>
                    <span class="w-20 text-sm text-gray-900 dark:text-white text-left">
                      {{ (data.percentages?.[key] || 0).toFixed(1) }}%
                    </span>
                    <span class="w-28 text-sm text-gray-600 dark:text-gray-400 text-left">
                      {{ formatCurrency(value) }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </template>
          
          <!-- Break-even Analysis -->
          <template v-else-if="type === 'breakeven'">
            <div class="space-y-6">
              <div class="grid grid-cols-2 gap-4">
                <div class="bg-red-50 dark:bg-red-900/20 rounded-xl p-4">
                  <div class="text-sm text-gray-600 dark:text-gray-400 mb-1">هزینه‌های ثابت</div>
                  <div class="text-2xl font-bold text-red-600">{{ formatCurrency(data.fixed_costs) }}</div>
                </div>
                <div class="bg-amber-50 dark:bg-amber-900/20 rounded-xl p-4">
                  <div class="text-sm text-gray-600 dark:text-gray-400 mb-1">هزینه‌های متغیر</div>
                  <div class="text-2xl font-bold text-amber-600">{{ formatCurrency(data.variable_costs) }}</div>
                </div>
                <div class="bg-blue-50 dark:bg-blue-900/20 rounded-xl p-4">
                  <div class="text-sm text-gray-600 dark:text-gray-400 mb-1">فروش کل</div>
                  <div class="text-2xl font-bold text-blue-600">{{ formatCurrency(data.total_selling) }}</div>
                </div>
                <div class="bg-purple-50 dark:bg-purple-900/20 rounded-xl p-4">
                  <div class="text-sm text-gray-600 dark:text-gray-400 mb-1">حاشیه مشارکت</div>
                  <div class="text-2xl font-bold text-purple-600">{{ (data.contribution_margin_ratio || 0).toFixed(1) }}%</div>
                </div>
              </div>
              
              <div class="bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 rounded-xl p-6">
                <h3 class="font-bold text-green-800 dark:text-green-300 mb-4">نقطه سربه‌سر</h3>
                <div class="grid grid-cols-2 gap-6">
                  <div>
                    <div class="text-sm text-green-700 dark:text-green-400 mb-1">درآمد نقطه سربه‌سر</div>
                    <div class="text-3xl font-bold text-green-600">{{ formatCurrency(data.break_even_revenue) }}</div>
                  </div>
                  <div>
                    <div class="text-sm text-green-700 dark:text-green-400 mb-1">تعداد واحد نقطه سربه‌سر</div>
                    <div class="text-3xl font-bold text-green-600">{{ formatNumber(data.break_even_units) }}</div>
                  </div>
                </div>
              </div>
              
              <div class="bg-emerald-50 dark:bg-emerald-900/20 rounded-xl p-4">
                <div class="text-sm text-gray-600 dark:text-gray-400 mb-1">سود در هدف فروش</div>
                <div class="text-3xl font-bold" :class="data.profit_at_target >= 0 ? 'text-emerald-600' : 'text-red-600'">
                  {{ formatCurrency(data.profit_at_target) }}
                </div>
              </div>
            </div>
          </template>
          
          <!-- Raw Materials Report -->
          <template v-else-if="type === 'materials'">
            <div class="space-y-6">
              <!-- Summary -->
              <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div class="bg-blue-50 dark:bg-blue-900/20 rounded-xl p-4 text-center">
                  <div class="text-2xl font-bold text-blue-600">{{ data.summary?.total_items_analyzed }}</div>
                  <div class="text-sm text-gray-500">محصولات</div>
                </div>
                <div class="bg-purple-50 dark:bg-purple-900/20 rounded-xl p-4 text-center">
                  <div class="text-2xl font-bold text-purple-600">{{ data.summary?.total_raw_materials }}</div>
                  <div class="text-sm text-gray-500">مواد اولیه</div>
                </div>
                <div class="bg-green-50 dark:bg-green-900/20 rounded-xl p-4 text-center">
                  <div class="text-2xl font-bold text-green-600">{{ data.summary?.materials_with_manual_prices }}</div>
                  <div class="text-sm text-gray-500">قیمت دستی</div>
                </div>
                <div class="bg-amber-50 dark:bg-amber-900/20 rounded-xl p-4 text-center">
                  <div class="text-2xl font-bold text-amber-600">{{ formatCurrency(data.summary?.total_raw_materials_cost) }}</div>
                  <div class="text-sm text-gray-500">هزینه کل</div>
                </div>
              </div>
              
              <!-- Materials Table -->
              <div class="overflow-x-auto">
                <table class="w-full text-sm">
                  <thead class="bg-gray-50 dark:bg-gray-700/50">
                    <tr>
                      <th class="px-4 py-3 text-right">کد ماده</th>
                      <th class="px-4 py-3 text-right">نام ماده</th>
                      <th class="px-4 py-3 text-right">مقدار کل</th>
                      <th class="px-4 py-3 text-right">قیمت واحد</th>
                      <th class="px-4 py-3 text-right">هزینه کل</th>
                      <th class="px-4 py-3 text-center">منبع</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-gray-100 dark:divide-gray-700">
                    <tr
                      v-for="(mat, code) in data.raw_materials_summary"
                      :key="code"
                      class="hover:bg-gray-50 dark:hover:bg-gray-700/30"
                    >
                      <td class="px-4 py-3 font-medium text-gray-900 dark:text-white">{{ code }}</td>
                      <td class="px-4 py-3 text-gray-600 dark:text-gray-400">{{ mat.item_name }}</td>
                      <td class="px-4 py-3 text-gray-600 dark:text-gray-400">
                        {{ formatNumber(mat.total_required_qty) }} {{ mat.uom }}
                      </td>
                      <td class="px-4 py-3 text-gray-600 dark:text-gray-400">{{ formatCurrency(mat.unit_cost) }}</td>
                      <td class="px-4 py-3 font-medium text-gray-900 dark:text-white">
                        {{ formatCurrency(mat.total_required_qty * mat.unit_cost) }}
                      </td>
                      <td class="px-4 py-3 text-center">
                        <span
                          class="px-2 py-1 text-xs rounded-full"
                          :class="mat.manual_price_available 
                            ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' 
                            : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'"
                        >
                          {{ mat.manual_price_available ? 'دستی' : 'سیستم' }}
                        </span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </template>
        </div>
        
        <!-- Footer -->
        <div class="px-6 py-4 border-t border-gray-200 dark:border-gray-700 flex justify-end gap-3">
          <button
            @click="exportReport"
            class="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 flex items-center gap-2"
          >
            <DownloadIcon class="w-4 h-4" />
            خروجی Excel
          </button>
          <button
            @click="$emit('close')"
            class="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700"
          >
            بستن
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import {
  X as XIcon,
  Download as DownloadIcon,
} from 'lucide-vue-next'

const props = defineProps({
  title: String,
  data: Object,
  type: String, // 'cost', 'breakeven', 'materials'
})

const emit = defineEmits(['close'])

const costLabels = {
  raw_material: 'مواد اولیه',
  operation: 'عملیات',
  overhead: 'سربار',
  labor: 'نیروی کار',
  subcontracting: 'پیمانکاری',
  electricity: 'برق',
  rent: 'اجاره',
  consumable: 'مصرفی',
}

const costColors = {
  raw_material: 'bg-blue-500',
  operation: 'bg-purple-500',
  overhead: 'bg-amber-500',
  labor: 'bg-green-500',
  subcontracting: 'bg-red-500',
  electricity: 'bg-yellow-500',
  rent: 'bg-pink-500',
  consumable: 'bg-cyan-500',
}

function getCostLabel(key) {
  return costLabels[key] || key
}

function getCostColor(key) {
  return costColors[key] || 'bg-gray-500'
}

function formatNumber(num) {
  return new Intl.NumberFormat('fa-IR').format(num || 0)
}

function formatCurrency(num) {
  if (!num && num !== 0) return '-'
  return new Intl.NumberFormat('fa-IR').format(Math.round(num))
}

function exportReport() {
  let csv = ''
  
  if (props.type === 'cost') {
    csv = 'نوع هزینه,مبلغ,درصد\n'
    for (const [key, value] of Object.entries(props.data.breakdown || {})) {
      csv += `"${getCostLabel(key)}",${value},${props.data.percentages?.[key] || 0}\n`
    }
  } else if (props.type === 'materials') {
    csv = 'کد ماده,نام ماده,مقدار کل,واحد,قیمت واحد,هزینه کل,منبع\n'
    for (const [code, mat] of Object.entries(props.data.raw_materials_summary || {})) {
      csv += `"${code}","${mat.item_name}",${mat.total_required_qty},"${mat.uom}",${mat.unit_cost},${mat.total_required_qty * mat.unit_cost},"${mat.manual_price_available ? 'دستی' : 'سیستم'}"\n`
    }
  }
  
  if (csv) {
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `report_${props.type}_${new Date().toISOString().slice(0,10)}.csv`
    link.click()
  }
}
</script>

