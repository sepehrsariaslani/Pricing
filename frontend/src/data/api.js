import { frappeRequest } from 'frappe-ui'

// API base path
const API_BASE = '/api/method/pricing.pricing_api'

// Helper function to call API
async function callApi(method, params = {}) {
  try {
    const result = await frappeRequest({
      url: `${API_BASE}.${method}`,
      params,
    })
    return result.message || result
  } catch (error) {
    console.error(`API Error (${method}):`, error)
    throw error
  }
}

// Dashboard
export async function getDashboardStats() {
  return callApi('get_dashboard_stats')
}

// Price Lists
export async function getPriceLists(filters = {}) {
  return callApi('get_price_lists', { filters: JSON.stringify(filters) })
}

export async function getPriceListDetail(name) {
  return callApi('get_price_list_detail', { name })
}

export async function getPriceListFullDetail(name) {
  return callApi('get_price_list_full_detail', { name })
}

export async function createPriceList(data) {
  return callApi('create_price_list', { data: JSON.stringify(data) })
}

export async function submitPriceList(name) {
  return callApi('submit_price_list', { name })
}

export async function cancelPriceList(name) {
  return callApi('cancel_price_list', { name })
}

export async function deletePriceList(name) {
  return callApi('delete_price_list', { name })
}

export async function duplicatePriceList(name) {
  return callApi('duplicate_price_list', { name })
}

// Items
export async function fetchItemsForPriceList(name, filters = {}) {
  return callApi('fetch_items_for_price_list', { name, filters: JSON.stringify(filters) })
}

export async function calculatePrices(name) {
  return callApi('calculate_prices', { name })
}

export async function updatePricesToPriceList(name) {
  return callApi('update_prices_to_price_list', { name })
}

export async function removeItemsFromPriceList(name, filters = {}) {
  return callApi('remove_items_from_price_list', { name, filters: JSON.stringify(filters) })
}

// Analytics
export async function getAnalyticsData(name) {
  return callApi('get_analytics_data', { name })
}

// Price Comparison
export async function getPriceComparison(name, comparePriceList = null) {
  return callApi('get_price_comparison', { name, compare_price_list: comparePriceList })
}

// Product Bundles
export async function fetchProductBundles(name, bundleFilter = null) {
  return callApi('fetch_product_bundles', { name, bundle_filter: bundleFilter })
}

// Materials
export async function updateManualMaterialPrice(name, itemCode, price) {
  return callApi('update_manual_material_price', { name, item_code: itemCode, price })
}

export async function getMissingMaterials(name) {
  return callApi('get_missing_materials', { name })
}

export async function updateMaterialSubstitutions(name, substitutions) {
  return callApi('update_material_substitutions', { name, substitutions: JSON.stringify(substitutions) })
}

// Lookups
export async function getItemGroups() {
  return callApi('get_item_groups')
}

export async function getBrands() {
  return callApi('get_brands')
}

export async function getAvailablePriceLists() {
  return callApi('get_available_price_lists')
}

// ==================== Edit APIs ====================

// Settings
export async function updatePriceListSettings(name, data) {
  return callApi('update_price_list_settings', { name, data: JSON.stringify(data) })
}

export async function updateInstallmentSettings(name, data) {
  return callApi('update_installment_settings', { name, data: JSON.stringify(data) })
}

export async function updateAdvancedPricing(name, data) {
  return callApi('update_advanced_pricing', { name, data: JSON.stringify(data) })
}

export async function updatePricingSteps(name, steps) {
  return callApi('update_pricing_steps', { name, steps: JSON.stringify(steps) })
}

// Item Costs
export async function updateItemCosts(name, itemCode, costs) {
  return callApi('update_item_costs', { name, item_code: itemCode, costs: JSON.stringify(costs) })
}

export async function addManualItemPrice(name, data) {
  return callApi('add_manual_item_price', { name, data: JSON.stringify(data) })
}

// Previous Price List Import
export async function importFromPrevPriceList(name, prevPriceList, increasePercent = 0, roundingAmount = 0) {
  return callApi('import_from_prev_price_list', { 
    name, 
    prev_price_list: prevPriceList, 
    increase_percent: increasePercent,
    rounding_amount: roundingAmount 
  })
}

export async function updatePrevItem(name, itemCode, data) {
  return callApi('update_prev_item', { name, item_code: itemCode, data: JSON.stringify(data) })
}

export async function applyPrevPricesToPriceList(name) {
  return callApi('apply_prev_prices_to_price_list', { name })
}

// ==================== Reports & Analytics ====================

export async function getRawMaterialsReport(name) {
  return callApi('get_raw_materials_report', { name })
}

export async function getPurchaseAnalysis(name, itemCode) {
  return callApi('get_purchase_analysis', { name, item_code: itemCode })
}

export async function getCostAnalysis(name) {
  return callApi('get_cost_analysis', { name })
}

export async function getBreakEvenAnalysis(name) {
  return callApi('get_break_even_analysis', { name })
}

// ==================== Currency ====================

export async function getCurrencyRates() {
  return callApi('get_currency_rates')
}

export async function convertPrices(name, targetCurrency, exchangeRate = null) {
  return callApi('convert_prices', { name, target_currency: targetCurrency, exchange_rate: exchangeRate })
}

// ==================== Search (Autocomplete) ====================

export async function searchItems(query, limit = 20) {
  return callApi('search_items', { query, limit })
}

export async function searchItemGroups(query, limit = 20) {
  return callApi('search_item_groups', { query, limit })
}

export async function searchBrands(query, limit = 20) {
  return callApi('search_brands', { query, limit })
}

// ==================== Wizard Steps ====================

export async function wizard_step_1_save(name, data) {
  return callApi('wizard_step_1_save', { name, data: JSON.stringify(data) })
}

export async function wizard_step_2_fetch_items(name, filters = {}) {
  return callApi('wizard_step_2_fetch_items', { name, filters: JSON.stringify(filters) })
}

export async function wizard_step_3_calculate(name) {
  return callApi('wizard_step_3_calculate', { name })
}

export async function wizard_step_4_review(name) {
  return callApi('wizard_step_4_review', { name })
}

export async function wizard_apply_prices(name) {
  return callApi('wizard_apply_prices', { name })
}

