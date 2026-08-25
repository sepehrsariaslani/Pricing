<template>
  <div class="h-full bg-gray-50 dark:bg-gray-900">
    <!-- Mobile Layout -->
    <div class="flex flex-col h-full lg:hidden">
      <!-- Top Header -->
      <header class="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 safe-area-top">
        <div class="flex items-center justify-between px-4 h-14">
          <button @click="sidebarOpen = true" class="p-2 -mr-2 text-gray-600 dark:text-gray-300">
            <MenuIcon class="w-6 h-6" />
          </button>
          <h1 class="text-lg font-bold text-gray-900 dark:text-white">{{ currentPageTitle }}</h1>
          <router-link to="/" class="p-2 -ml-2">
            <HomeIcon class="w-6 h-6 text-gray-600 dark:text-gray-300" />
          </router-link>
        </div>
      </header>

      <!-- Main Content -->
      <main class="flex-1 overflow-auto">
        <router-view />
      </main>

      <!-- Bottom Navigation -->
      <nav class="bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 safe-area-bottom">
        <div class="flex justify-around items-center h-16">
          <router-link
            v-for="item in bottomNavItems"
            :key="item.to"
            :to="item.to"
            class="flex flex-col items-center justify-center w-full h-full text-xs"
            :class="[
              $route.path === item.to || $route.path.startsWith(item.to + '/')
                ? 'text-blue-600 dark:text-blue-400'
                : 'text-gray-500 dark:text-gray-400'
            ]"
          >
            <component :is="item.icon" class="w-6 h-6 mb-1" />
            <span>{{ item.label }}</span>
          </router-link>
        </div>
      </nav>
    </div>

    <!-- Desktop Layout -->
    <div class="hidden lg:flex h-full">
      <!-- Sidebar -->
      <aside class="w-64 bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 flex flex-col">
        <!-- Logo -->
        <div class="h-16 flex items-center px-6 border-b border-gray-200 dark:border-gray-700">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 bg-gradient-to-br from-blue-600 to-cyan-500 rounded-xl flex items-center justify-center">
              <TagIcon class="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 class="font-bold text-gray-900 dark:text-white">قیمت‌گذاری</h1>
              <p class="text-xs text-gray-500 dark:text-gray-400">مدیریت قیمت‌ها</p>
            </div>
          </div>
        </div>

        <!-- Navigation -->
        <nav class="flex-1 px-4 py-4 overflow-auto">
          <template v-for="(section, sectionIndex) in sidebarSections" :key="sectionIndex">
            <!-- Section Header -->
            <div v-if="section.title" class="px-3 py-2 mt-4 mb-1 first:mt-0">
              <span class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">{{ section.title }}</span>
            </div>
            
            <!-- Section Items -->
            <router-link
              v-for="item in section.items"
              :key="item.to"
              :to="item.to"
              class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors mb-0.5"
              :class="[
                $route.path === item.to || $route.path.startsWith(item.to + '/')
                  ? 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                  : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
              ]"
            >
              <component :is="item.icon" class="w-5 h-5" />
              <span>{{ item.label }}</span>
              <span
                v-if="item.badge"
                class="mr-auto bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-400 text-xs px-2 py-0.5 rounded-full"
              >
                {{ item.badge }}
              </span>
            </router-link>
          </template>
        </nav>

        <!-- Theme Toggle & User Info -->
        <div class="p-4 border-t border-gray-200 dark:border-gray-700">
          <!-- Theme Toggle -->
          <button
            @click="toggleTheme"
            class="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors mb-3"
            :class="[
              isDarkMode
                ? 'bg-gray-700 text-yellow-400 hover:bg-gray-600'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            ]"
          >
            <SunIcon v-if="isDarkMode" class="w-5 h-5" />
            <MoonIcon v-else class="w-5 h-5" />
            <span>{{ isDarkMode ? 'حالت روز' : 'حالت شب' }}</span>
          </button>
          
          <!-- User Info -->
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 bg-gray-200 dark:bg-gray-700 rounded-full flex items-center justify-center">
              <UserIcon class="w-5 h-5 text-gray-600 dark:text-gray-400" />
            </div>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-medium text-gray-900 dark:text-white truncate">{{ userName }}</p>
              <p class="text-xs text-gray-500 dark:text-gray-400 truncate">{{ userRole }}</p>
            </div>
          </div>
        </div>
      </aside>

      <!-- Main Content -->
      <main class="flex-1 overflow-auto">
        <router-view />
      </main>
    </div>

    <!-- Mobile Sidebar Overlay -->
    <Teleport to="body">
      <Transition name="fade">
        <div
          v-if="sidebarOpen"
          class="fixed inset-0 bg-black/50 z-40 lg:hidden"
          @click="sidebarOpen = false"
        />
      </Transition>
      <Transition name="slide-right">
        <aside
          v-if="sidebarOpen"
          class="fixed top-0 right-0 bottom-0 w-72 bg-white dark:bg-gray-800 z-50 lg:hidden safe-area-top flex flex-col"
        >
          <!-- Close Button -->
          <div class="flex items-center justify-between px-4 h-14 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
            <h2 class="font-bold text-gray-900 dark:text-white">منو</h2>
            <button @click="sidebarOpen = false" class="p-2 -ml-2 text-gray-600 dark:text-gray-300">
              <XIcon class="w-6 h-6" />
            </button>
          </div>

          <!-- Navigation - Scrollable -->
          <nav class="flex-1 overflow-y-auto px-4 py-4">
            <template v-for="(section, sectionIndex) in sidebarSections" :key="sectionIndex">
              <!-- Section Header -->
              <div v-if="section.title" class="px-3 py-2 mt-4 mb-1 first:mt-0 border-t border-gray-100 dark:border-gray-700 pt-4">
                <span class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">{{ section.title }}</span>
              </div>
              
              <!-- Section Items -->
              <router-link
                v-for="item in section.items"
                :key="item.to"
                :to="item.to"
                @click="sidebarOpen = false"
                class="flex items-center gap-3 px-3 py-3 rounded-lg text-sm font-medium transition-colors mb-0.5"
                :class="[
                  $route.path === item.to || $route.path.startsWith(item.to + '/')
                    ? 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                    : 'text-gray-700 dark:text-gray-300'
                ]"
              >
                <component :is="item.icon" class="w-5 h-5" />
                <span>{{ item.label }}</span>
                <span
                  v-if="item.badge"
                  class="mr-auto bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-400 text-xs px-2 py-0.5 rounded-full"
                >
                  {{ item.badge }}
                </span>
              </router-link>
            </template>
          </nav>

          <!-- Theme Toggle & User Info -->
          <div class="border-t border-gray-200 dark:border-gray-700 p-4 flex-shrink-0 safe-area-bottom">
            <!-- Theme Toggle -->
            <button
              @click="toggleTheme"
              class="w-full flex items-center gap-3 px-3 py-3 rounded-lg text-sm font-medium transition-colors mb-3"
              :class="[
                isDarkMode
                  ? 'bg-gray-700 text-yellow-400'
                  : 'bg-gray-100 text-gray-700'
              ]"
            >
              <SunIcon v-if="isDarkMode" class="w-5 h-5" />
              <MoonIcon v-else class="w-5 h-5" />
              <span>{{ isDarkMode ? 'حالت روز' : 'حالت شب' }}</span>
            </button>
            
            <!-- User Info -->
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 bg-gray-200 dark:bg-gray-700 rounded-full flex items-center justify-center">
                <UserIcon class="w-5 h-5 text-gray-600 dark:text-gray-400" />
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium text-gray-900 dark:text-white truncate">{{ userName }}</p>
                <p class="text-xs text-gray-500 dark:text-gray-400 truncate">{{ userRole }}</p>
              </div>
            </div>
          </div>
        </aside>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  Tag as TagIcon,
  Home as HomeIcon,
  Menu as MenuIcon,
  X as XIcon,
  User as UserIcon,
  LayoutGrid as LayoutGridIcon,
  List as ListIcon,
  Calculator as CalculatorIcon,
  BarChart3 as BarChartIcon,
  Settings as SettingsIcon,
  Package as PackageIcon,
  GitCompare as CompareIcon,
  Sun as SunIcon,
  Moon as MoonIcon,
  Layers as LayersIcon,
} from 'lucide-vue-next'

const route = useRoute()
const sidebarOpen = ref(false)

// Dark mode
const isDarkMode = ref(false)

// Initialize theme from localStorage or system preference
function initTheme() {
  const savedTheme = localStorage.getItem('pricing-theme')
  if (savedTheme) {
    isDarkMode.value = savedTheme === 'dark'
  } else {
    isDarkMode.value = window.matchMedia('(prefers-color-scheme: dark)').matches
  }
  applyTheme()
}

function applyTheme() {
  if (isDarkMode.value) {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
}

function toggleTheme() {
  isDarkMode.value = !isDarkMode.value
  localStorage.setItem('pricing-theme', isDarkMode.value ? 'dark' : 'light')
  applyTheme()
}

// Initialize on mount
initTheme()

// User info from window (set by backend)
const userName = computed(() => window.user_full_name || 'کاربر')
const userRole = computed(() => window.user_role || 'کاربر')

// Current page title
const currentPageTitle = computed(() => route.meta.title || 'قیمت‌گذاری')

// Sidebar navigation items - organized by sections
const sidebarSections = [
  {
    title: null, // Main section without title
    items: [
      { to: '/', label: 'داشبورد', icon: LayoutGridIcon },
      { to: '/price-lists', label: 'لیست‌های قیمت', icon: ListIcon, badge: window.active_price_lists },
    ]
  },
  {
    title: 'قیمت‌گذاری',
    items: [
      { to: '/price-lists/new', label: 'ایجاد لیست جدید', icon: TagIcon },
    ]
  },
  {
    title: 'تحلیل',
    items: [
      { to: '/analytics', label: 'تحلیل‌ها و نمودارها', icon: BarChartIcon },
    ]
  },
]

// Bottom navigation items (mobile)
const bottomNavItems = [
  { to: '/', label: 'داشبورد', icon: LayoutGridIcon },
  { to: '/price-lists', label: 'لیست‌ها', icon: ListIcon },
  { to: '/price-lists/new', label: 'جدید', icon: TagIcon },
  { to: '/analytics', label: 'تحلیل', icon: BarChartIcon },
]
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-right-enter-active,
.slide-right-leave-active {
  transition: transform 0.3s ease;
}

.slide-right-enter-from,
.slide-right-leave-to {
  transform: translateX(100%);
}
</style>

