import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory('/pricing/'),
  routes: [
    {
      path: '/',
      name: 'Dashboard',
      component: () => import('@/pages/Dashboard.vue'),
      meta: { title: 'داشبورد' },
    },
    {
      path: '/price-lists',
      name: 'PriceLists',
      component: () => import('@/pages/PriceLists.vue'),
      meta: { title: 'لیست‌های قیمت' },
    },
    {
      path: '/price-lists/new',
      name: 'NewPriceList',
      component: () => import('@/pages/PriceListForm.vue'),
      meta: { title: 'ایجاد لیست قیمت جدید' },
    },
    {
      path: '/pricing-wizard',
      name: 'NewPricingWizard',
      component: () => import('@/pages/PricingWizard.vue'),
      meta: { title: 'فرآیند قیمت‌گذاری جدید' },
    },
    {
      path: '/pricing-wizard/:id',
      name: 'PricingWizard',
      component: () => import('@/pages/PricingWizard.vue'),
      props: true,
      meta: { title: 'فرآیند قیمت‌گذاری' },
    },
    {
      path: '/price-lists/:id',
      name: 'PriceListDetail',
      component: () => import('@/pages/PriceListDetail.vue'),
      props: true,
      meta: { title: 'جزئیات لیست قیمت' },
    },
    {
      path: '/price-lists/:id/settings',
      name: 'PriceListSettings',
      component: () => import('@/pages/PriceListSettings.vue'),
      props: true,
      meta: { title: 'تنظیمات لیست قیمت' },
    },
    {
      path: '/price-lists/:id/items',
      name: 'ItemsPricing',
      component: () => import('@/pages/ItemsPricing.vue'),
      props: true,
      meta: { title: 'قیمت‌گذاری کالاها' },
    },
    {
      path: '/price-lists/:id/bulk',
      name: 'BulkPricing',
      component: () => import('@/pages/BulkPricing.vue'),
      props: true,
      meta: { title: 'قیمت‌گذاری دستی' },
    },
    {
      path: '/price-lists/:id/materials',
      name: 'MaterialsManagement',
      component: () => import('@/pages/MaterialsManagement.vue'),
      props: true,
      meta: { title: 'مدیریت مواد اولیه' },
    },
    {
      path: '/price-lists/:id/bundles',
      name: 'ProductBundles',
      component: () => import('@/pages/ProductBundles.vue'),
      props: true,
      meta: { title: 'بسته محصولات' },
    },
    {
      path: '/price-lists/:id/compare',
      name: 'PriceComparison',
      component: () => import('@/pages/PriceComparison.vue'),
      props: true,
      meta: { title: 'مقایسه قیمت‌ها' },
    },
    {
      path: '/price-lists/:id/prev-import',
      name: 'PrevPriceListImport',
      component: () => import('@/pages/PrevPriceListImport.vue'),
      props: true,
      meta: { title: 'واردات از لیست قیمت قبلی' },
    },
    {
      path: '/price-lists/:id/analytics',
      name: 'PriceListAnalytics',
      component: () => import('@/pages/PriceListAnalytics.vue'),
      props: true,
      meta: { title: 'تحلیل لیست قیمت' },
    },
    {
      path: '/analytics',
      name: 'Analytics',
      component: () => import('@/pages/Analytics.vue'),
      meta: { title: 'تحلیل‌ها' },
    },
  ],
})

// Update page title
router.beforeEach((to, from, next) => {
  document.title = `${to.meta.title || 'قیمت‌گذاری'} | Pricing`
  next()
})

export default router

