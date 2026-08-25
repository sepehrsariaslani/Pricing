<template>
  <div class="flex flex-col items-center justify-center py-12 px-4 text-center">
    <div class="w-16 h-16 bg-gray-100 dark:bg-gray-800 rounded-full flex items-center justify-center mb-4">
      <component :is="icon" class="w-8 h-8 text-gray-400 dark:text-gray-500" />
    </div>
    <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-1">{{ title }}</h3>
    <p class="text-sm text-gray-500 dark:text-gray-400 max-w-sm">{{ description }}</p>
    <slot name="action" />
  </div>
</template>

<script setup>
import { Inbox as InboxIcon } from 'lucide-vue-next'

defineProps({
  title: {
    type: String,
    default: 'داده‌ای یافت نشد',
  },
  description: {
    type: String,
    default: '',
  },
  icon: {
    type: Object,
    default: () => InboxIcon,
  },
})
</script>

