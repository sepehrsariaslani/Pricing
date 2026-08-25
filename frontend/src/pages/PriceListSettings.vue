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
              <h1 class="text-xl font-bold text-gray-900 dark:text-white">تنظیمات لیست قیمت</h1>
              <p class="text-sm text-gray-500 dark:text-gray-400">{{ priceList?.price_list }}</p>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <span v-if="!isEditable" class="px-3 py-1 text-sm bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400 rounded-full">
              فقط خواندنی
            </span>
            <button
              v-if="isEditable && hasChanges"
              @click="saveAllSettings"
              :disabled="saving"
              class="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 flex items-center gap-2"
            >
              <SaveIcon class="w-4 h-4" />
              {{ saving ? 'در حال ذخیره...' : 'ذخیره تغییرات' }}
            </button>
          </div>
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
            ? 'border-primary-600 text-primary-600 dark:text-primary-400' 
            : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'"
        >
          {{ tab.label }}
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-20">
      <div class="w-8 h-8 border-4 border-primary-600 border-t-transparent rounded-full animate-spin"></div>
    </div>

    <!-- Content -->
    <div v-else class="p-4 max-w-4xl mx-auto space-y-6">
      <!-- Basic Settings -->
      <div v-show="activeTab === 'basic'" class="space-y-6">
        <div class="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
          <h2 class="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <SettingsIcon class="w-5 h-5" />
            تنظیمات پایه
          </h2>
          
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">تاریخ شروع</label>
              <input
                type="date"
                v-model="form.valid_from"
                :disabled="!isEditable"
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">تاریخ پایان</label>
              <input
                type="date"
                v-model="form.valid_until"
                :disabled="!isEditable"
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">درصد سود</label>
              <div class="relative">
                <input
                  type="number"
                  v-model.number="form.profit_margin"
                  :disabled="!isEditable"
                  step="0.1"
                  class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50"
                />
                <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">%</span>
              </div>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">درصد کمیسیون</label>
              <div class="relative">
                <input
                  type="number"
                  v-model.number="form.commission_percentage"
                  :disabled="!isEditable"
                  step="0.1"
                  class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50"
                />
                <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">%</span>
              </div>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">مبلغ رند کردن</label>
              <input
                type="number"
                v-model.number="form.price_rounding_amount"
                :disabled="!isEditable"
                step="1000"
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">درصد تخفیف هدف</label>
              <div class="relative">
                <input
                  type="number"
                  v-model.number="form.target_discount_percentage"
                  :disabled="!isEditable"
                  step="0.1"
                  class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50"
                />
                <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">%</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Display Settings -->
        <div class="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
          <h2 class="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <EyeIcon class="w-5 h-5" />
            تنظیمات نمایش
          </h2>
          
          <div class="grid grid-cols-2 md:grid-cols-3 gap-4">
            <label class="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" v-model="form.show_base_cost" :disabled="!isEditable" class="w-4 h-4 text-primary-600 rounded" />
              <span class="text-sm text-gray-700 dark:text-gray-300">نمایش هزینه پایه</span>
            </label>
            <label class="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" v-model="form.show_profit_amount" :disabled="!isEditable" class="w-4 h-4 text-primary-600 rounded" />
              <span class="text-sm text-gray-700 dark:text-gray-300">نمایش سود</span>
            </label>
            <label class="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" v-model="form.show_commission_amount" :disabled="!isEditable" class="w-4 h-4 text-primary-600 rounded" />
              <span class="text-sm text-gray-700 dark:text-gray-300">نمایش کمیسیون</span>
            </label>
            <label class="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" v-model="form.show_installment_details" :disabled="!isEditable" class="w-4 h-4 text-primary-600 rounded" />
              <span class="text-sm text-gray-700 dark:text-gray-300">نمایش جزئیات قسط</span>
            </label>
            <label class="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" v-model="form.show_discount_amount" :disabled="!isEditable" class="w-4 h-4 text-primary-600 rounded" />
              <span class="text-sm text-gray-700 dark:text-gray-300">نمایش تخفیف</span>
            </label>
          </div>
        </div>
      </div>

      <!-- Installment Settings -->
      <div v-show="activeTab === 'installment'" class="space-y-6">
        <div class="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
          <h2 class="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <CreditCardIcon class="w-5 h-5" />
            تنظیمات قسط
          </h2>
          
          <label class="flex items-center gap-2 cursor-pointer mb-4">
            <input type="checkbox" v-model="form.enable_installment" :disabled="!isEditable" class="w-4 h-4 text-primary-600 rounded" />
            <span class="text-sm font-medium text-gray-700 dark:text-gray-300">فعال‌سازی فروش اقساطی</span>
          </label>
          
          <div v-if="form.enable_installment" class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">درصد پیش‌پرداخت</label>
              <div class="relative">
                <input
                  type="number"
                  v-model.number="form.down_payment_percentage"
                  :disabled="!isEditable"
                  step="1"
                  class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50"
                />
                <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">%</span>
              </div>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">تعداد اقساط</label>
              <input
                type="number"
                v-model.number="form.number_of_months"
                :disabled="!isEditable"
                step="1"
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">نرخ بهره ماهانه</label>
              <div class="relative">
                <input
                  type="number"
                  v-model.number="form.monthly_interest_rate"
                  :disabled="!isEditable"
                  step="0.1"
                  class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50"
                />
                <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">%</span>
              </div>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">درصد کل بهره</label>
              <div class="px-3 py-2 bg-gray-100 dark:bg-gray-700 rounded-lg text-gray-900 dark:text-white">
                {{ formatNumber(form.installment_total_interest_percentage) }}%
              </div>
            </div>
          </div>
        </div>

        <!-- Deferred Payment -->
        <div class="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
          <h2 class="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <ClockIcon class="w-5 h-5" />
            پرداخت تأخیری
          </h2>
          
          <label class="flex items-center gap-2 cursor-pointer mb-4">
            <input type="checkbox" v-model="form.enable_deferred_payment" :disabled="!isEditable" class="w-4 h-4 text-primary-600 rounded" />
            <span class="text-sm font-medium text-gray-700 dark:text-gray-300">فعال‌سازی پرداخت تأخیری</span>
          </label>
          
          <div v-if="form.enable_deferred_payment" class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">تعداد ماه تأخیر</label>
              <input
                type="number"
                v-model.number="form.deferred_payment_months"
                :disabled="!isEditable"
                step="1"
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">نرخ بهره ماهانه</label>
              <div class="relative">
                <input
                  type="number"
                  v-model.number="form.deferred_payment_interest_rate"
                  :disabled="!isEditable"
                  step="0.1"
                  class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50"
                />
                <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">%</span>
              </div>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">درصد کل بهره تأخیری</label>
              <div class="px-3 py-2 bg-gray-100 dark:bg-gray-700 rounded-lg text-gray-900 dark:text-white">
                {{ formatNumber(form.deferred_payment_total_interest_percentage) }}%
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Pricing Steps -->
      <div v-show="activeTab === 'steps'" class="space-y-6">
        <div class="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-lg font-bold text-gray-900 dark:text-white flex items-center gap-2">
              <LayersIcon class="w-5 h-5" />
              مراحل قیمت‌گذاری
            </h2>
            <button
              v-if="isEditable"
              @click="addPricingStep"
              class="px-3 py-1.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 text-sm flex items-center gap-1"
            >
              <PlusIcon class="w-4 h-4" />
              افزودن مرحله
            </button>
          </div>
          
          <div v-if="form.pricing_steps?.length" class="space-y-3">
            <div
              v-for="(step, index) in form.pricing_steps"
              :key="index"
              class="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg"
            >
              <input
                type="checkbox"
                v-model="step.enabled"
                :disabled="!isEditable"
                class="w-4 h-4 text-primary-600 rounded"
              />
              <input
                type="text"
                v-model="step.step_name"
                :disabled="!isEditable"
                placeholder="نام مرحله"
                class="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50 text-sm"
              />
              <select
                v-model="step.step_type"
                :disabled="!isEditable"
                class="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50 text-sm"
              >
                <option value="percentage">درصد</option>
                <option value="fixed">مبلغ ثابت</option>
              </select>
              <input
                type="number"
                v-model.number="step.percentage"
                v-if="step.step_type === 'percentage'"
                :disabled="!isEditable"
                placeholder="درصد"
                step="0.1"
                class="w-24 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50 text-sm"
              />
              <input
                type="number"
                v-model.number="step.amount"
                v-else
                :disabled="!isEditable"
                placeholder="مبلغ"
                class="w-32 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50 text-sm"
              />
              <button
                v-if="isEditable"
                @click="removePricingStep(index)"
                class="p-2 text-red-600 hover:bg-red-100 dark:hover:bg-red-900/30 rounded-lg"
              >
                <TrashIcon class="w-4 h-4" />
              </button>
            </div>
          </div>
          <div v-else class="text-center py-8 text-gray-500 dark:text-gray-400">
            هیچ مرحله قیمت‌گذاری تعریف نشده است
          </div>
        </div>
      </div>

      <!-- Advanced Pricing -->
      <div v-show="activeTab === 'advanced'" class="space-y-6">
        <!-- Volume Pricing -->
        <div class="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
          <h2 class="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <PackageIcon class="w-5 h-5" />
            قیمت‌گذاری حجمی
          </h2>
          
          <label class="flex items-center gap-2 cursor-pointer mb-4">
            <input type="checkbox" v-model="form.enable_volume_pricing" :disabled="!isEditable" class="w-4 h-4 text-primary-600 rounded" />
            <span class="text-sm font-medium text-gray-700 dark:text-gray-300">فعال‌سازی قیمت‌گذاری حجمی</span>
          </label>
          
          <div v-if="form.enable_volume_pricing">
            <div class="flex items-center justify-between mb-3">
              <span class="text-sm text-gray-600 dark:text-gray-400">سطوح تخفیف بر اساس تعداد</span>
              <button
                v-if="isEditable"
                @click="addVolumeTier"
                class="px-3 py-1.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 text-sm flex items-center gap-1"
              >
                <PlusIcon class="w-4 h-4" />
                افزودن سطح
              </button>
            </div>
            
            <div v-if="form.volume_pricing_tiers?.length" class="space-y-2">
              <div
                v-for="(tier, index) in form.volume_pricing_tiers"
                :key="index"
                class="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg"
              >
                <span class="text-sm text-gray-600 dark:text-gray-400">از</span>
                <input
                  type="number"
                  v-model.number="tier.min_qty"
                  :disabled="!isEditable"
                  class="w-24 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50 text-sm"
                />
                <span class="text-sm text-gray-600 dark:text-gray-400">تا</span>
                <input
                  type="number"
                  v-model.number="tier.max_qty"
                  :disabled="!isEditable"
                  class="w-24 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50 text-sm"
                />
                <span class="text-sm text-gray-600 dark:text-gray-400">تخفیف:</span>
                <input
                  type="number"
                  v-model.number="tier.discount_percentage"
                  :disabled="!isEditable"
                  step="0.1"
                  class="w-20 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50 text-sm"
                />
                <span class="text-sm text-gray-500">%</span>
                <button
                  v-if="isEditable"
                  @click="removeVolumeTier(index)"
                  class="p-2 text-red-600 hover:bg-red-100 dark:hover:bg-red-900/30 rounded-lg"
                >
                  <TrashIcon class="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Seasonal Pricing -->
        <div class="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
          <h2 class="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <SunIcon class="w-5 h-5" />
            قیمت‌گذاری فصلی
          </h2>
          
          <label class="flex items-center gap-2 cursor-pointer mb-4">
            <input type="checkbox" v-model="form.enable_seasonal_pricing" :disabled="!isEditable" class="w-4 h-4 text-primary-600 rounded" />
            <span class="text-sm font-medium text-gray-700 dark:text-gray-300">فعال‌سازی قیمت‌گذاری فصلی</span>
          </label>
          
          <div v-if="form.enable_seasonal_pricing" class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">ضریب فصلی</label>
              <input
                type="number"
                v-model.number="form.seasonal_factor"
                :disabled="!isEditable"
                step="0.01"
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50"
              />
            </div>
          </div>
        </div>

        <!-- Customer Tier Pricing -->
        <div class="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
          <h2 class="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <UsersIcon class="w-5 h-5" />
            قیمت‌گذاری سطح مشتری
          </h2>
          
          <label class="flex items-center gap-2 cursor-pointer mb-4">
            <input type="checkbox" v-model="form.enable_customer_tier_pricing" :disabled="!isEditable" class="w-4 h-4 text-primary-600 rounded" />
            <span class="text-sm font-medium text-gray-700 dark:text-gray-300">فعال‌سازی قیمت‌گذاری سطح مشتری</span>
          </label>
          
          <div v-if="form.enable_customer_tier_pricing">
            <div class="flex items-center justify-between mb-3">
              <span class="text-sm text-gray-600 dark:text-gray-400">تخفیف بر اساس گروه مشتری</span>
              <button
                v-if="isEditable"
                @click="addCustomerTier"
                class="px-3 py-1.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 text-sm flex items-center gap-1"
              >
                <PlusIcon class="w-4 h-4" />
                افزودن گروه
              </button>
            </div>
            
            <div v-if="form.customer_tier_discounts?.length" class="space-y-2">
              <div
                v-for="(tier, index) in form.customer_tier_discounts"
                :key="index"
                class="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg"
              >
                <input
                  type="text"
                  v-model="tier.customer_group"
                  :disabled="!isEditable"
                  placeholder="نام گروه مشتری"
                  class="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50 text-sm"
                />
                <span class="text-sm text-gray-600 dark:text-gray-400">تخفیف:</span>
                <input
                  type="number"
                  v-model.number="tier.discount_percentage"
                  :disabled="!isEditable"
                  step="0.1"
                  class="w-20 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50 text-sm"
                />
                <span class="text-sm text-gray-500">%</span>
                <button
                  v-if="isEditable"
                  @click="removeCustomerTier(index)"
                  class="p-2 text-red-600 hover:bg-red-100 dark:hover:bg-red-900/30 rounded-lg"
                >
                  <TrashIcon class="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Financial Analysis -->
      <div v-show="activeTab === 'financial'" class="space-y-6">
        <div class="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
          <h2 class="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <TrendingUpIcon class="w-5 h-5" />
            تحلیل مالی
          </h2>
          
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">هزینه‌های ثابت ماهانه</label>
              <input
                type="number"
                v-model.number="form.monthly_fixed_costs"
                :disabled="!isEditable"
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">هدف درآمد ماهانه</label>
              <input
                type="number"
                v-model.number="form.target_monthly_revenue"
                :disabled="!isEditable"
                class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white disabled:opacity-50"
              />
            </div>
          </div>
          
          <!-- Read-only calculated fields -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6 pt-6 border-t border-gray-200 dark:border-gray-700">
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">نقطه سربه‌سر</label>
              <div class="px-3 py-2 bg-gray-100 dark:bg-gray-700 rounded-lg text-gray-900 dark:text-white">
                {{ formatCurrency(priceList?.break_even_point || 0) }}
              </div>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">سود بعد از نقطه سربه‌سر</label>
              <div class="px-3 py-2 bg-gray-100 dark:bg-gray-700 rounded-lg text-gray-900 dark:text-white">
                {{ formatCurrency(priceList?.profit_after_breakeven || 0) }}
              </div>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">سود خالص پس از کمیسیون</label>
              <div class="px-3 py-2 bg-gray-100 dark:bg-gray-700 rounded-lg text-gray-900 dark:text-white">
                {{ formatCurrency(priceList?.net_profit_after_commission || 0) }}
              </div>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">کل سود</label>
              <div class="px-3 py-2 bg-green-100 dark:bg-green-900/30 rounded-lg text-green-800 dark:text-green-400 font-bold">
                {{ formatCurrency(priceList?.total_profit || 0) }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  getPriceListFullDetail,
  updatePriceListSettings,
  updateInstallmentSettings,
  updateAdvancedPricing,
  updatePricingSteps
} from '@/data/api'
import {
  ArrowRight as ArrowRightIcon,
  Save as SaveIcon,
  Settings as SettingsIcon,
  Eye as EyeIcon,
  CreditCard as CreditCardIcon,
  Clock as ClockIcon,
  Layers as LayersIcon,
  Package as PackageIcon,
  Sun as SunIcon,
  Users as UsersIcon,
  TrendingUp as TrendingUpIcon,
  Plus as PlusIcon,
  Trash2 as TrashIcon
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const priceListId = computed(() => route.params.id)

const loading = ref(true)
const saving = ref(false)
const priceList = ref(null)
const activeTab = ref('basic')
const originalForm = ref(null)

const tabs = [
  { id: 'basic', label: 'تنظیمات پایه' },
  { id: 'installment', label: 'قسط و تأخیری' },
  { id: 'steps', label: 'مراحل قیمت‌گذاری' },
  { id: 'advanced', label: 'قیمت‌گذاری پیشرفته' },
  { id: 'financial', label: 'تحلیل مالی' },
]

const form = ref({
  valid_from: '',
  valid_until: '',
  profit_margin: 0,
  commission_percentage: 0,
  price_rounding_amount: 0,
  target_discount_percentage: 0,
  show_base_cost: false,
  show_profit_amount: false,
  show_commission_amount: false,
  show_installment_details: false,
  show_discount_amount: false,
  enable_installment: false,
  down_payment_percentage: 0,
  number_of_months: 0,
  monthly_interest_rate: 0,
  installment_total_interest_percentage: 0,
  enable_deferred_payment: false,
  deferred_payment_months: 0,
  deferred_payment_interest_rate: 0,
  deferred_payment_total_interest_percentage: 0,
  enable_volume_pricing: false,
  enable_seasonal_pricing: false,
  seasonal_factor: 1,
  enable_customer_tier_pricing: false,
  monthly_fixed_costs: 0,
  target_monthly_revenue: 0,
  pricing_steps: [],
  volume_pricing_tiers: [],
  customer_tier_discounts: [],
})

const isEditable = computed(() => priceList.value?.is_editable || false)

const hasChanges = computed(() => {
  if (!originalForm.value) return false
  return JSON.stringify(form.value) !== JSON.stringify(originalForm.value)
})

async function loadPriceList() {
  loading.value = true
  try {
    const data = await getPriceListFullDetail(priceListId.value)
    priceList.value = data
    
    // Populate form
    form.value = {
      valid_from: data.valid_from || '',
      valid_until: data.valid_until || '',
      profit_margin: data.profit_margin || 0,
      commission_percentage: data.commission_percentage || 0,
      price_rounding_amount: data.price_rounding_amount || 0,
      target_discount_percentage: data.target_discount_percentage || 0,
      show_base_cost: !!data.show_base_cost,
      show_profit_amount: !!data.show_profit_amount,
      show_commission_amount: !!data.show_commission_amount,
      show_installment_details: !!data.show_installment_details,
      show_discount_amount: !!data.show_discount_amount,
      enable_installment: !!data.enable_installment,
      down_payment_percentage: data.down_payment_percentage || 0,
      number_of_months: data.number_of_months || 0,
      monthly_interest_rate: data.monthly_interest_rate || 0,
      installment_total_interest_percentage: data.installment_total_interest_percentage || 0,
      enable_deferred_payment: !!data.enable_deferred_payment,
      deferred_payment_months: data.deferred_payment_months || 0,
      deferred_payment_interest_rate: data.deferred_payment_interest_rate || 0,
      deferred_payment_total_interest_percentage: data.deferred_payment_total_interest_percentage || 0,
      enable_volume_pricing: !!data.enable_volume_pricing,
      enable_seasonal_pricing: !!data.enable_seasonal_pricing,
      seasonal_factor: data.seasonal_factor || 1,
      enable_customer_tier_pricing: !!data.enable_customer_tier_pricing,
      monthly_fixed_costs: data.monthly_fixed_costs || 0,
      target_monthly_revenue: data.target_monthly_revenue || 0,
      pricing_steps: data.pricing_steps || [],
      volume_pricing_tiers: data.volume_pricing_tiers || [],
      customer_tier_discounts: data.customer_tier_discounts || [],
    }
    
    originalForm.value = JSON.parse(JSON.stringify(form.value))
  } catch (error) {
    console.error('Error loading price list:', error)
  } finally {
    loading.value = false
  }
}

async function saveAllSettings() {
  if (!isEditable.value) return
  
  saving.value = true
  try {
    // Save basic settings
    await updatePriceListSettings(priceListId.value, {
      profit_margin: form.value.profit_margin,
      valid_from: form.value.valid_from,
      valid_until: form.value.valid_until,
      commission_percentage: form.value.commission_percentage,
      target_discount_percentage: form.value.target_discount_percentage,
      price_rounding_amount: form.value.price_rounding_amount,
      show_base_cost: form.value.show_base_cost,
      show_profit_amount: form.value.show_profit_amount,
      show_commission_amount: form.value.show_commission_amount,
      show_installment_details: form.value.show_installment_details,
      show_discount_amount: form.value.show_discount_amount,
      monthly_fixed_costs: form.value.monthly_fixed_costs,
      target_monthly_revenue: form.value.target_monthly_revenue,
    })
    
    // Save installment settings
    await updateInstallmentSettings(priceListId.value, {
      enable_installment: form.value.enable_installment,
      down_payment_percentage: form.value.down_payment_percentage,
      number_of_months: form.value.number_of_months,
      monthly_interest_rate: form.value.monthly_interest_rate,
      enable_deferred_payment: form.value.enable_deferred_payment,
      deferred_payment_months: form.value.deferred_payment_months,
      deferred_payment_interest_rate: form.value.deferred_payment_interest_rate,
    })
    
    // Save advanced pricing
    await updateAdvancedPricing(priceListId.value, {
      enable_volume_pricing: form.value.enable_volume_pricing,
      enable_seasonal_pricing: form.value.enable_seasonal_pricing,
      seasonal_factor: form.value.seasonal_factor,
      enable_customer_tier_pricing: form.value.enable_customer_tier_pricing,
      volume_pricing_tiers: form.value.volume_pricing_tiers,
      customer_tier_discounts: form.value.customer_tier_discounts,
    })
    
    // Save pricing steps
    await updatePricingSteps(priceListId.value, form.value.pricing_steps)
    
    originalForm.value = JSON.parse(JSON.stringify(form.value))
    
    // Reload to get calculated fields
    await loadPriceList()
  } catch (error) {
    console.error('Error saving settings:', error)
    alert('خطا در ذخیره تنظیمات')
  } finally {
    saving.value = false
  }
}

// Pricing steps helpers
function addPricingStep() {
  form.value.pricing_steps.push({
    step_name: '',
    step_type: 'percentage',
    percentage: 0,
    amount: 0,
    enabled: true,
  })
}

function removePricingStep(index) {
  form.value.pricing_steps.splice(index, 1)
}

// Volume tier helpers
function addVolumeTier() {
  form.value.volume_pricing_tiers.push({
    min_qty: 0,
    max_qty: 0,
    discount_percentage: 0,
  })
}

function removeVolumeTier(index) {
  form.value.volume_pricing_tiers.splice(index, 1)
}

// Customer tier helpers
function addCustomerTier() {
  form.value.customer_tier_discounts.push({
    customer_group: '',
    discount_percentage: 0,
  })
}

function removeCustomerTier(index) {
  form.value.customer_tier_discounts.splice(index, 1)
}

// Formatters
function formatNumber(num) {
  return new Intl.NumberFormat('fa-IR', { maximumFractionDigits: 2 }).format(num || 0)
}

function formatCurrency(num) {
  return new Intl.NumberFormat('fa-IR').format(num || 0) + ' ریال'
}

onMounted(() => {
  loadPriceList()
})
</script>

