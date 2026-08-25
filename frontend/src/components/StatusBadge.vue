<template>
  <span
    class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
    :class="statusClasses"
  >
    <span v-if="showDot" class="w-1.5 h-1.5 rounded-full" :class="dotClass"></span>
    {{ label }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: {
    type: [Number, String],
    required: true,
  },
  showDot: {
    type: Boolean,
    default: true,
  },
})

const statusConfig = {
  0: { label: 'پیش‌نویس', bg: 'bg-gray-100 dark:bg-gray-700', text: 'text-gray-700 dark:text-gray-300', dot: 'bg-gray-500' },
  1: { label: 'تأیید شده', bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-700 dark:text-green-400', dot: 'bg-green-500' },
  2: { label: 'لغو شده', bg: 'bg-red-100 dark:bg-red-900/30', text: 'text-red-700 dark:text-red-400', dot: 'bg-red-500' },
  draft: { label: 'پیش‌نویس', bg: 'bg-gray-100 dark:bg-gray-700', text: 'text-gray-700 dark:text-gray-300', dot: 'bg-gray-500' },
  submitted: { label: 'تأیید شده', bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-700 dark:text-green-400', dot: 'bg-green-500' },
  cancelled: { label: 'لغو شده', bg: 'bg-red-100 dark:bg-red-900/30', text: 'text-red-700 dark:text-red-400', dot: 'bg-red-500' },
}

const config = computed(() => statusConfig[props.status] || statusConfig[0])
const label = computed(() => config.value.label)
const statusClasses = computed(() => `${config.value.bg} ${config.value.text}`)
const dotClass = computed(() => config.value.dot)
</script>

