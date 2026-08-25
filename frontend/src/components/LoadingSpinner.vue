<template>
  <div class="flex flex-col items-center justify-center" :class="containerClass">
    <div 
      class="border-4 border-blue-100 dark:border-blue-900 border-t-blue-600 dark:border-t-blue-400 rounded-full animate-spin"
      :class="sizeClass"
    ></div>
    <p v-if="text" class="mt-3 text-sm text-gray-500 dark:text-gray-400">{{ text }}</p>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  size: {
    type: String,
    default: 'md',
    validator: (value) => ['sm', 'md', 'lg'].includes(value),
  },
  text: {
    type: String,
    default: '',
  },
  fullPage: {
    type: Boolean,
    default: false,
  },
})

const sizeClass = computed(() => {
  const sizes = {
    sm: 'w-6 h-6',
    md: 'w-10 h-10',
    lg: 'w-16 h-16',
  }
  return sizes[props.size]
})

const containerClass = computed(() => {
  return props.fullPage ? 'py-20' : 'py-8'
})
</script>

