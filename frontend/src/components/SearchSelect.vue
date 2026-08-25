<template>
  <div class="relative" ref="containerRef">
    <div
      @click="openDropdown"
      class="w-full px-4 py-3 border rounded-xl bg-white dark:bg-gray-700 cursor-pointer flex items-center justify-between"
      :class="[
        isOpen ? 'border-primary-500 ring-2 ring-primary-500/20' : 'border-gray-300 dark:border-gray-600',
        disabled ? 'opacity-50 cursor-not-allowed' : ''
      ]"
    >
      <span v-if="displayValue" class="text-gray-900 dark:text-white">{{ displayValue }}</span>
      <span v-else class="text-gray-400">{{ placeholder }}</span>
      <ChevronDownIcon class="w-5 h-5 text-gray-400 transition-transform" :class="{ 'rotate-180': isOpen }" />
    </div>
    
    <!-- Dropdown -->
    <Transition
      enter-active-class="transition ease-out duration-100"
      enter-from-class="transform opacity-0 scale-95"
      enter-to-class="transform opacity-100 scale-100"
      leave-active-class="transition ease-in duration-75"
      leave-from-class="transform opacity-100 scale-100"
      leave-to-class="transform opacity-0 scale-95"
    >
      <div
        v-if="isOpen"
        class="absolute z-50 w-full mt-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-lg overflow-hidden"
      >
        <!-- Search Input -->
        <div class="p-2 border-b border-gray-200 dark:border-gray-700">
          <div class="relative">
            <SearchIcon class="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              ref="searchInputRef"
              type="text"
              v-model="searchQuery"
              :placeholder="searchPlaceholder"
              class="w-full pl-3 pr-10 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
              @input="onSearch"
            />
            <button
              v-if="searchQuery"
              @click.stop="clearSearch"
              class="absolute left-3 top-1/2 -translate-y-1/2 p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
            >
              <XIcon class="w-3 h-3 text-gray-400" />
            </button>
          </div>
        </div>
        
        <!-- Loading -->
        <div v-if="searching" class="p-4 text-center">
          <div class="w-5 h-5 border-2 border-primary-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
        </div>
        
        <!-- Options List -->
        <div v-else class="max-h-60 overflow-y-auto">
          <div v-if="filteredOptions.length === 0" class="p-4 text-center text-gray-500 dark:text-gray-400">
            {{ noResultsText }}
          </div>
          <button
            v-for="option in filteredOptions"
            :key="getOptionValue(option)"
            @click="selectOption(option)"
            class="w-full px-4 py-3 text-right hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center justify-between transition-colors"
            :class="{ 'bg-primary-50 dark:bg-primary-900/20': isSelected(option) }"
          >
            <span class="text-gray-900 dark:text-white">{{ getOptionLabel(option) }}</span>
            <CheckIcon v-if="isSelected(option)" class="w-4 h-4 text-primary-600" />
          </button>
        </div>
        
        <!-- Clear Selection -->
        <div v-if="modelValue && clearable" class="p-2 border-t border-gray-200 dark:border-gray-700">
          <button
            @click="clearSelection"
            class="w-full py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg"
          >
            پاک کردن انتخاب
          </button>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import {
  ChevronDown as ChevronDownIcon,
  Search as SearchIcon,
  X as XIcon,
  Check as CheckIcon,
} from 'lucide-vue-next'

const props = defineProps({
  modelValue: {
    type: [String, Number, Object],
    default: null
  },
  options: {
    type: Array,
    default: () => []
  },
  searchFn: {
    type: Function,
    default: null
  },
  labelKey: {
    type: String,
    default: 'label'
  },
  valueKey: {
    type: String,
    default: 'value'
  },
  placeholder: {
    type: String,
    default: 'انتخاب کنید...'
  },
  searchPlaceholder: {
    type: String,
    default: 'جستجو...'
  },
  noResultsText: {
    type: String,
    default: 'نتیجه‌ای یافت نشد'
  },
  disabled: {
    type: Boolean,
    default: false
  },
  clearable: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['update:modelValue'])

const containerRef = ref(null)
const searchInputRef = ref(null)
const isOpen = ref(false)
const searchQuery = ref('')
const searching = ref(false)
const searchResults = ref([])
const debounceTimer = ref(null)

const filteredOptions = computed(() => {
  // If using search function, return search results
  if (props.searchFn) {
    return searchResults.value
  }
  
  // Otherwise filter local options
  if (!searchQuery.value) return props.options
  
  const q = searchQuery.value.toLowerCase()
  return props.options.filter(opt => {
    const label = getOptionLabel(opt).toLowerCase()
    const value = String(getOptionValue(opt)).toLowerCase()
    return label.includes(q) || value.includes(q)
  })
})

const displayValue = computed(() => {
  if (!props.modelValue) return ''
  
  // If modelValue is an object
  if (typeof props.modelValue === 'object') {
    return props.modelValue[props.labelKey]
  }
  
  // Find in options
  const found = props.options.find(opt => getOptionValue(opt) === props.modelValue)
  if (found) return getOptionLabel(found)
  
  // Return as is
  return props.modelValue
})

function getOptionLabel(option) {
  if (typeof option === 'string') return option
  return option[props.labelKey] || option.name || option.label || ''
}

function getOptionValue(option) {
  if (typeof option === 'string') return option
  return option[props.valueKey] || option.name || option.value || ''
}

function isSelected(option) {
  return getOptionValue(option) === props.modelValue
}

function openDropdown() {
  if (props.disabled) return
  isOpen.value = true
  nextTick(() => {
    searchInputRef.value?.focus()
    if (props.searchFn && searchQuery.value === '') {
      // Initial search
      performSearch('')
    }
  })
}

function closeDropdown() {
  isOpen.value = false
  searchQuery.value = ''
}

function selectOption(option) {
  emit('update:modelValue', getOptionValue(option))
  closeDropdown()
}

function clearSelection() {
  emit('update:modelValue', null)
  closeDropdown()
}

function clearSearch() {
  searchQuery.value = ''
  if (props.searchFn) {
    performSearch('')
  }
}

function onSearch() {
  if (!props.searchFn) return
  
  // Debounce
  if (debounceTimer.value) {
    clearTimeout(debounceTimer.value)
  }
  
  debounceTimer.value = setTimeout(() => {
    performSearch(searchQuery.value)
  }, 300)
}

async function performSearch(query) {
  if (!props.searchFn) return
  
  searching.value = true
  try {
    const results = await props.searchFn(query)
    searchResults.value = results || []
  } catch (error) {
    console.error('Search error:', error)
    searchResults.value = []
  } finally {
    searching.value = false
  }
}

// Click outside handler
function handleClickOutside(event) {
  if (containerRef.value && !containerRef.value.contains(event.target)) {
    closeDropdown()
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  if (debounceTimer.value) {
    clearTimeout(debounceTimer.value)
  }
})
</script>

