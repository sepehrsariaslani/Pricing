<template>
  <div 
    class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 card-hover cursor-pointer"
    @click="$emit('click')"
  >
    <div class="flex items-start justify-between mb-3">
      <div class="flex-1 min-w-0">
        <h3 class="font-semibold text-gray-900 dark:text-white truncate">{{ item.item_name || item.item_code }}</h3>
        <p class="text-sm text-gray-500 dark:text-gray-400 truncate">{{ item.item_code }}</p>
      </div>
      <span v-if="item.item_group" class="text-xs bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 px-2 py-1 rounded-full mr-2">
        {{ item.item_group }}
      </span>
    </div>

    <div class="space-y-2">
      <!-- Cost breakdown -->
      <div class="flex justify-between text-sm">
        <span class="text-gray-500 dark:text-gray-400">هزینه کل:</span>
        <span class="font-medium text-gray-900 dark:text-white persian-nums price">
          {{ formatPrice(item.total_cost) }}
        </span>
      </div>

      <!-- Selling price -->
      <div class="flex justify-between text-sm">
        <span class="text-gray-500 dark:text-gray-400">قیمت فروش:</span>
        <span class="font-bold text-blue-600 dark:text-blue-400 persian-nums price">
          {{ formatPrice(item.final_selected_price || item.selling_price) }}
        </span>
      </div>

      <!-- Profit -->
      <div class="flex justify-between text-sm pt-2 border-t border-gray-100 dark:border-gray-700">
        <span class="text-gray-500 dark:text-gray-400">سود:</span>
        <span 
          class="font-medium persian-nums price"
          :class="item.profit_amount > 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'"
        >
          {{ formatPrice(item.profit_amount) }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  item: {
    type: Object,
    required: true,
  },
})

defineEmits(['click'])

function formatPrice(value) {
  if (!value && value !== 0) return '-'
  return new Intl.NumberFormat('fa-IR').format(Math.round(value)) + ' ریال'
}
</script>

