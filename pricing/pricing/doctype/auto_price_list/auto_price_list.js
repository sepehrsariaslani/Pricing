frappe.ui.form.on('Auto Price List', {
    refresh: function (frm) {
        console.log("Auto Price List refresh triggered", frm.doc.name);

        // بارگذاری Chart.js اگر لود نشده باشد
        if (typeof Chart === "undefined") {
            console.log("Loading Chart.js...");
            const script = document.createElement("script");
            script.src = "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js";
            script.onload = function () { console.log("Chart.js loaded successfully"); };
            document.head.appendChild(script);
        }

        // بارگذاری و اضافه کردن تمام دکمه‌های اصلی (فقط یکبار)
        load_and_add_buttons(frm);

        // محاسبه تحلیل نقطه سر به سر اگر کالا وجود دارد
        // ⚠️ DISABLED: Heavy analytics charts - user must click "Show Analytics"
        // if (frm.doc.items && frm.doc.items.length > 0) {
        //     calculate_break_even_analysis(frm);
        //     // render_advanced_analytics(frm); // Moved to On-Demand Button
        // }

        // محاسبه ارز ثانویه اگر فعال باشد
        if (frm.doc.items && frm.doc.items.length > 0) {
            if (frm.doc.enable_multi_currency && frm.doc.currency_exchange_rate > 0) {
                update_secondary_currency_prices(frm);
            }
        }
        // Auto-refresh when items are loaded
        if (frm.doc.items && frm.doc.items.length > 0) {
            frm.refresh_fields();
            // Apply BOM status styling after items are loaded
            setTimeout(() => {
                apply_bom_status_styling(frm);
            }, 500);
        }

        setup_mobile_interface(frm);
        // Adjust prev_items layout for readability
        adjust_prev_items_table_layout(frm);

        // 🔍 راه‌اندازی فیلترهای داینامیک برای تمام جداول
        setTimeout(() => {
            try {
                if (typeof setup_dynamic_filters_for_all_tables === 'function') {
                    setup_dynamic_filters_for_all_tables(frm);
                }
            } catch (e) {
                console.log('ℹ️ Dynamic filters not available:', e.message);
            }
        }, 300);

        // حذف فراخوانی render_dashboard_charts_simple از اینجا
    },

    validate: function (frm) {
        try {
            console.log("🔍 SLDR v5: Starting Aggressive Payload Cleanup...");
            console.log(`🛡️ Items count at validate: ${frm.doc.items ? frm.doc.items.length : 0}`);

            let initial_size = JSON.stringify(frm.doc).length;
            console.log(`📦 INITIAL: ${(initial_size / 1024 / 1024).toFixed(2)} MB (${initial_size} bytes)`);

            // ============ 1. Clear ALL heavy HTML fields on main doc ============
            const html_fields_to_clear = [
                'dashboard_html', 'break_even_chart_html', 'waterfall_chart_html',
                'bubble_chart_html', 'sales_forecast_html', 'roi_analysis_html',
                'product_ranking_html', 'price_comparison_summary'
            ];
            html_fields_to_clear.forEach(f => { if (frm.doc[f]) frm.doc[f] = ""; });

            // ============ 2. Clear heavy text fields in ITEMS table ============
            if (frm.doc.items && frm.doc.items.length > 0) {
                frm.doc.items.forEach(item => {
                    item.items_diff_log = "";
                    item.price_calculation_breakdown = "";
                    item.pricing_breakdown = "";
                    item.step_by_step_calculation = "";
                });
            }

            // ============ 3. Clear heavy text fields in PRODUCT_BUNDLES table ============
            if (frm.doc.product_bundles && frm.doc.product_bundles.length > 0) {
                frm.doc.product_bundles.forEach(bundle => {
                    bundle.bundle_items_html = "";
                    bundle.bundle_items_data = "";
                });
            }

            // ============ 4. Strip ONLY non-critical internal metadata from ALL child tables ============
            const all_tables = [
                'items', 'prev_items', 'product_bundles', 'bulk_pricing_items',
                'manual_item_prices', 'pricing_steps', 'volume_pricing_tiers',
                'customer_tier_discounts', 'material_substitutions',
                'manual_material_prices', 'missing_material_prices'
            ];
            const meta_keys_to_delete = [
                '__checked', '_original_data', '_liked_by', '_comments', '_assign',
                '_user_tags', '__onload'
            ];

            all_tables.forEach(table_name => {
                if (frm.doc[table_name] && frm.doc[table_name].length > 0) {
                    frm.doc[table_name].forEach(row => {
                        meta_keys_to_delete.forEach(key => {
                            if (row[key] !== undefined) delete row[key];
                        });
                    });
                }
            });

            // NOTE: Do NOT strip __unsaved, _dirty etc. from frm.doc itself!
            // Frappe needs these flags to know the form has unsaved changes.

            // ============ 6. Diagnostic: Per-table sizes ============
            let final_size = JSON.stringify(frm.doc).length;
            let table_sizes = [];
            all_tables.forEach(t => {
                if (frm.doc[t] && frm.doc[t].length > 0) {
                    let sz = JSON.stringify(frm.doc[t]).length;
                    table_sizes.push({ table: t, rows: frm.doc[t].length, size_kb: (sz / 1024).toFixed(1) });
                }
            });
            table_sizes.sort((a, b) => parseFloat(b.size_kb) - parseFloat(a.size_kb));
            console.log(`📊 FINAL: ${(final_size / 1024 / 1024).toFixed(2)} MB | Reduction: ${((initial_size - final_size) / 1024).toFixed(1)} KB`);
            console.table(table_sizes);

            if (final_size > 2 * 1024 * 1024) {
                console.warn(`⚠️ WARNING: Payload still large: ${(final_size / 1024 / 1024).toFixed(2)} MB`);
            }
        } catch (e) {
            console.error("❌ Error in validate (SLDR v5):", e);
        }
    },

    // Event handlers برای فیلدهای ارز
    enable_multi_currency: function (frm) {
        if (frm.doc.enable_multi_currency && frm.doc.items && frm.doc.items.length > 0) {
            if (frm.doc.currency_exchange_rate > 0) {
                update_secondary_currency_prices(frm);
            } else {
                frappe.show_alert({
                    message: __('لطفاً نرخ تبدیل ارز را وارد کنید'),
                    indicator: 'orange'
                });
            }
        }
    },

    currency_exchange_rate: function (frm) {
        if (frm.doc.enable_multi_currency && frm.doc.currency_exchange_rate > 0 && frm.doc.items && frm.doc.items.length > 0) {
            update_secondary_currency_prices(frm);
            frappe.show_alert({
                message: __('قیمت‌های ارز ثانویه محاسبه شد'),
                indicator: 'blue'
            });
        }
    },

    secondary_rounding_amount: function (frm) {
        if (frm.doc.enable_multi_currency && frm.doc.currency_exchange_rate > 0 && frm.doc.items && frm.doc.items.length > 0) {
            update_secondary_currency_prices(frm);
        }
    },


    selected_price_type: function (frm) {
        // Auto-calculation disabled as per user request to fix 413 and performance issues
        // handle_price_type_change remains if it just updates UI labels, but calculation is manual
        handle_price_type_change(frm, frm.doc.selected_price_type);

        console.log("selected_price_type changed to:", frm.doc.selected_price_type);
        frm.dirty();
    },

    profit_margin: function (frm) {
        console.log("profit_margin field changed", frm.doc.profit_margin);
        // Auto-calculation disabled per user request
        frm.dirty();
    },

    commission_percentage: function (frm) {
        console.log("commission_percentage field changed", frm.doc.commission_percentage);
        // Auto-calculation disabled per user request
        frm.dirty();
    },

    target_discount_percentage: function (frm) {
        console.log("target_discount_percentage field changed", frm.doc.target_discount_percentage);

        // محاسبه افزایش قیمت مورد نیاز در سمت کلاینت
        // فرمول: اگر تخفیف x% است، افزایش قیمت = x / (100 - x) * 100
        let discount = flt(frm.doc.target_discount_percentage || 0);
        let markup = 0;

        if (discount > 0 && discount < 100) {
            markup = (discount / (100 - discount)) * 100;
        }

        // به‌روزرسانی فیلد افزایش قیمت مورد نیاز (بدون ذخیره در سرور)
        frm.doc.required_markup_percentage = markup;
        frm.refresh_field('required_markup_percentage');

        // محاسبه قیمت نهایی با افزایش
        if (frm.doc.items && frm.doc.items.length > 0) {
            let total_selling = frm.doc.items.reduce((sum, item) => sum + flt(item.selling_price || 0), 0);
            if (total_selling > 0 && discount > 0) {
                frm.doc.final_selling_price_with_markup = total_selling / (1 - discount / 100);
                frm.refresh_field('final_selling_price_with_markup');
            }
        }

        // علامت‌گذاری سند به عنوان تغییر یافته (dirty)
        frm.dirty();

        frappe.show_alert({
            message: __('درصد افزایش قیمت محاسبه شد: ') + markup.toFixed(2) + '%',
            indicator: 'blue'
        });
    },

    compare_with_price_list: function (frm) {
        console.log("compare_with_price_list field changed", frm.doc.compare_with_price_list);
        if (frm.doc.compare_with_price_list && frm.doc.items && frm.doc.items.length > 0) {

            // ⚡ Automatic optimized call (Restored based on User Feedback)
            frappe.call({
                method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.calculate_item_prices_api',
                args: { docname: frm.doc.name },
                freeze: true,
                freeze_message: __('در حال مقایسه قیمت‌ها (اتوماتیک)...')
            }).then(r => {
                if (r.message && r.message.success) {
                    frappe.show_alert({ message: r.message.message, indicator: 'green' });
                    frm.reload_doc();
                }
            });
        }
    },

    prev_price_increase_percent: function (frm) {
        // Recompute all prev_items new_price when global percent changes
        if (!frm.doc.prev_items) return;
        frm.doc.prev_items.forEach(row => {
            row.increase_percent = frm.doc.prev_price_increase_percent || 0;
            row.new_price = compute_new_price(row.prev_price, row.increase_percent, row.rounding_amount || frm.doc.prev_price_rounding_amount || 0);
        });
        frm.refresh_field('prev_items');
    },

    prev_price_rounding_amount: function (frm) {
        // Recompute rounding for all prev_items when global rounding changes
        if (!frm.doc.prev_items) return;
        frm.doc.prev_items.forEach(row => {
            row.rounding_amount = frm.doc.prev_price_rounding_amount || 0;
            row.new_price = compute_new_price(row.prev_price, row.increase_percent || frm.doc.prev_price_increase_percent || 0, row.rounding_amount);
        });
        frm.refresh_field('prev_items');
    },

    fetch_items_button: function (frm) {
        console.log("fetch_items_button clicked (Server-Side Mode)");

        // دریافت مقادیر فیلترها از فرم
        // توجه: این فیلترها باید در فرم وجود داشته باشند
        let item_group = frm.doc.item_group;
        let brand = frm.doc.brand;
        let item_name_filter = frm.doc.item_name_filter;

        frappe.call({
            method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.add_items_server_side',
            args: {
                docname: frm.doc.name,
                item_group: item_group,
                brand: brand,
                name_filter: item_name_filter
            },
            freeze: true,
            freeze_message: __('در حال جستجو و افزودن کالاها در سرور... (بدون محدودیت حجم)'),
            callback: function (r) {
                if (r.message) {
                    if (r.message.count > 0) {
                        frappe.msgprint({
                            title: __('موفق'),
                            message: r.message.message,
                            indicator: 'green'
                        });
                        frm.reload_doc();
                    } else {
                        frappe.msgprint({
                            title: __('نتیجه'),
                            message: r.message.message,
                            indicator: 'orange'
                        });
                    }
                }
            }
        });
    },

    import_prev_price_list_button: function (frm) {
        console.log('import_prev_price_list_button clicked');
        if (!frm.doc.compare_previous_price_list) {
            frappe.msgprint(__('لطفاً ابتدا لیست قیمت مرجع را انتخاب کنید'));
            return;
        }

        frappe.call({
            method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.fetch_prev_price_list_items',
            args: {
                docname: frm.docname,
                prev_price_list: frm.doc.compare_previous_price_list
            },
            freeze: true
        }).then(r => {
            if (r.message) {
                const items = r.message.items || [];
                // Replace prev_items with fetched items
                frm.clear_table('prev_items');
                items.forEach(it => {
                    // Only add if item not exists in Item master
                    let row = frm.add_child('prev_items');
                    row.item_code = it.item_code;
                    row.prev_price = it.price_list_rate;
                    row.increase_percent = frm.doc.prev_price_increase_percent || 0;
                    row.rounding_amount = frm.doc.prev_price_rounding_amount || 0;
                    row.new_price = compute_new_price(row.prev_price, row.increase_percent, row.rounding_amount);
                });
                frm.refresh();
                frappe.msgprint(__('آیتم‌های لیست قیمت قبلی وارد شدند'));
                // adjust layout after rows added
                setTimeout(() => adjust_prev_items_table_layout(frm), 200);
            }
        });
    },

    remove_items_button: function (frm) {
        console.log("remove_items_button clicked");
        remove_filtered_items(frm);
    },

    remove_no_bom_items_button: function (frm) {
        console.log("remove_no_bom_items_button clicked");
        remove_items_without_submitted_bom(frm);
    },

    // فیلتر پیشرفته
    apply_filters_button: function (frm) {
        console.log("apply_filters_button clicked");
        apply_advanced_filters(frm);
    },

    clear_filters_button: function (frm) {
        console.log("clear_filters_button clicked");
        clear_advanced_filters(frm);
    },

    enable_advanced_filter: function (frm) {
        if (frm.doc.enable_advanced_filter) {
            // نمایش پیام راهنما
            frappe.show_alert({
                message: 'فیلتر پیشرفته فعال شد. فیلترهای خود را تنظیم کرده و دکمه "اعمال فیلتر" را بزنید.',
                indicator: 'blue'
            });
        }
    },

    // قیمت‌گذاری دستی
    add_filtered_items_button: function (frm) {
        console.log("add_filtered_items_button clicked");
        // Inline: call server-side method to add filtered items to bulk pricing
        frappe.call({
            method: 'add_bulk_items_server_side',
            doc: frm.doc,
            freeze: true,
            freeze_message: __('در حال افزودن کالاها به لیست دستی...'),
            callback: function (r) {
                if (r.message && r.message.success) {
                    frappe.show_alert({ message: r.message.message, indicator: 'green' });
                    frm.reload_doc();
                } else if (r.message) {
                    frappe.msgprint({ title: __('نتیجه'), message: r.message.message, indicator: 'orange' });
                }
            }
        });
    },

    apply_bulk_pricing_button: function (frm) {
        console.log("apply_bulk_pricing_button clicked");
        // Inline: apply manual prices from manual_item_prices to items table
        if (!frm.doc.manual_item_prices || frm.doc.manual_item_prices.length === 0) {
            frappe.msgprint(__('هیچ قیمت دستی‌ای در جدول manual_item_prices وجود ندارد'));
            return;
        }
        frappe.confirm(
            'آیا می‌خواهید قیمت‌های دستی را به جدول محصولات اعمال کنید؟',
            function () {
                const manual_prices_map = {};
                frm.doc.manual_item_prices.forEach(mp => {
                    manual_prices_map[mp.item_code] = mp;
                });
                let updated_count = 0;
                frm.doc.items.forEach(item => {
                    const mp = manual_prices_map[item.item_code];
                    if (mp) {
                        if (mp.manual_raw_material_cost && mp.manual_raw_material_cost > 0) {
                            item.raw_material_cost = mp.manual_raw_material_cost;
                        }
                        if (mp.manual_operation_cost && mp.manual_operation_cost > 0) {
                            item.operation_cost = mp.manual_operation_cost;
                        }
                        if (mp.manual_overhead_cost && mp.manual_overhead_cost > 0) {
                            item.overhead_cost = mp.manual_overhead_cost;
                        }
                        updated_count++;
                    }
                });
                frm.refresh_field('items');
                frm.dirty();
                frappe.show_alert({
                    message: updated_count + ' کالا با قیمت‌های دستی به‌روزرسانی شد',
                    indicator: updated_count > 0 ? 'green' : 'orange'
                });
            }
        );
    },

    add_to_manual_prices_button: function (frm) {
        console.log("add_to_manual_prices_button clicked");
        // Inline: call server-side API to add bulk items to manual prices
        if (!frm.doc.bulk_pricing_items || frm.doc.bulk_pricing_items.length === 0) {
            frappe.msgprint({ title: 'هشدار', message: 'هیچ آیتمی در جدول bulk_pricing_items وجود ندارد', indicator: 'orange' });
            return;
        }
        frappe.confirm(
            frm.doc.bulk_pricing_items.length + ' آیتم را به جدول قیمت‌های دستی اضافه کنید؟',
            function () {
                frappe.call({
                    method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.add_bulk_items_to_manual_prices_api',
                    args: { docname: frm.doc.name },
                    freeze: true,
                    freeze_message: 'در حال اضافه به جدول قیمت‌های دستی...'
                }).then(response => {
                    if (response && response.message && response.message.success) {
                        frappe.show_alert({ message: response.message.message, indicator: 'green' });
                        frm.reload_doc();
                    } else if (response && response.message) {
                        frappe.msgprint({ title: 'خطا', message: response.message.message || 'خطای نامشخص', indicator: 'red' });
                    }
                }).catch(error => {
                    console.error('Error in add_to_manual_prices:', error);
                    frappe.msgprint({ title: 'خطا', message: 'خطا در اضافه به جدول: ' + (error.message || error), indicator: 'red' });
                });
            }
        );
    },

    apply_prev_prices_to_price_list: function (frm) {
        console.log('apply_prev_prices_to_price_list clicked');
        if (!frm.doc.prev_items || frm.doc.prev_items.length === 0) {
            frappe.msgprint(__('هیچ آیتمی برای اضافه کردن به لیست قیمت وجود ندارد'));
            return;
        }

        let to_apply = frm.doc.prev_items.filter(p => p.include && p.new_price && p.new_price > 0).map(p => ({
            item_code: p.item_code,
            price: p.new_price
        }));

        if (to_apply.length === 0) {
            frappe.msgprint(__('هیچ آیتمی انتخاب نشده یا قیمت جدید معتبر نیست'));
            return;
        }

        // Confirm
        frappe.confirm(__('آیا می‌خواهید قیمت‌های انتخاب‌شده را به لیست قیمت جاری اضافه کنید؟'), function () {
            frappe.call({
                method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.apply_prev_prices_to_price_list',
                args: {
                    docname: frm.docname,
                    to_apply: to_apply,
                    target_price_list: frm.doc.price_list
                },
                freeze: true
            }).then(r => {
                if (r.message && r.message.success) {
                    frappe.show_alert({ message: r.message.message, indicator: 'green' });
                    frm.reload_doc();
                } else {
                    frappe.msgprint(r.message.message || __('خطا در اعمال قیمت‌ها'));
                }
            });
        });
    },

    fetch_bundles_button: function (frm) {
        console.log('fetch_bundles_button clicked');

        frappe.call({
            method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.calculate_product_bundles',
            args: {
                docname: frm.docname
            },
            freeze: true,
            freeze_message: __('در حال دریافت و محاسبه بسته‌های محصولات...')
        }).then(r => {
            if (r.message && r.message.success) {
                frappe.show_alert({
                    message: r.message.message,
                    indicator: 'green'
                });
                frm.reload_doc();
            } else {
                frappe.msgprint({
                    title: __('خطا'),
                    message: r.message && r.message.message ? r.message.message : __('خطا در دریافت بسته‌های محصولات'),
                    indicator: 'red'
                });
            }
        });
    },

    calculate_bundle_prices_button: function (frm) {
        console.log('calculate_bundle_prices_button clicked');
        frappe.call({
            method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.calculate_bundle_prices',
            args: {
                docname: frm.docname
            },
            freeze: true,
            freeze_message: __('در حال محاسبه قیمت بسته‌های محصولات...')
        }).then(r => {
            if (r.message && r.message.success) {
                frappe.show_alert({
                    message: r.message.message,
                    indicator: 'green'
                });
                frm.reload_doc();
            } else {
                frappe.msgprint({
                    title: __('خطا'),
                    message: r.message && r.message.message ? r.message.message : __('خطا در محاسبه قیمت‌ها'),
                    indicator: 'red'
                });
            }
        });
    },

    product_bundles_on_form_rendered: function (frm) {
        setup_bundle_grid_handlers(frm);
    },

    // 📦 دکمه بارگذاری مواد اولیه
    load_raw_materials_button: function (frm) {
        console.log('📦 load_raw_materials_button clicked');

        frappe.confirm(
            __('آیا می‌خواهید مواد اولیه (آیتم‌های بدون BOM) را با قیمت آخرین فاکتور خرید بارگذاری کنید؟<br><br>' +
                '<small>⚠️ توجه: این عملیات جدول فعلی را پاک و با داده‌های جدید پر می‌کند.</small>'),
            function () {
                frappe.call({
                    method: 'load_raw_materials_from_purchases',
                    doc: frm.doc,
                    freeze: true,
                    freeze_message: __('📦 در حال بارگذاری مواد اولیه از آخرین فاکتورهای خرید...'),
                    callback: function (r) {
                        if (r.message && r.message.success) {
                            frappe.show_alert({
                                message: r.message.message,
                                indicator: 'green'
                            });
                            frm.reload_doc();
                        } else {
                            frappe.msgprint({
                                title: __('خطا'),
                                message: r.message ? r.message.message : __('خطا در بارگذاری مواد اولیه'),
                                indicator: 'red'
                            });
                        }
                    }
                });
            }
        );
    },

    // محاسبه تفاوت قیمت هنگام تغییر قیمت دستی
    manual_material_prices_on_form_rendered: function (frm) {
        // Setup event handlers for manual price changes
        frm.fields_dict.manual_material_prices.grid.wrapper.on('change',
            'input[data-fieldname="manual_price"]',
            function (e) {
                const row = $(this).closest('[data-idx]');
                const idx = row.data('idx');
                const item = frm.doc.manual_material_prices[idx - 1];

                if (item) {
                    const manual_price = flt(item.manual_price || 0);
                    const purchase_price = flt(item.last_purchase_price || 0);

                    if (purchase_price > 0) {
                        item.price_difference = manual_price - purchase_price;
                        item.price_difference_percent = ((manual_price - purchase_price) / purchase_price) * 100;
                    }

                    frm.refresh_field('manual_material_prices');
                }
            }
        );
    },

    // 🔍 اعمال فیلتر پیشرفته روی جدول مواد اولیه
    raw_material_apply_filter_button: function (frm) {
        console.log('🔍 raw_material_apply_filter_button clicked');
        // Inline client-side filtering of raw materials
        if (!frm.doc.manual_material_prices || frm.doc.manual_material_prices.length === 0) {
            frappe.show_alert({ message: __('جدول مواد اولیه خالی است'), indicator: 'yellow' });
            return;
        }
        const name_filter = (frm.doc.raw_material_filter_name || '').toLowerCase().trim();
        const group_filter = frm.doc.raw_material_filter_group || '';
        const price_min = flt(frm.doc.raw_material_filter_price_min || 0);
        const price_max = flt(frm.doc.raw_material_filter_price_max || 0);
        const supplier_filter = (frm.doc.raw_material_filter_supplier || '').toLowerCase().trim();

        let visible_count = 0;
        let grid = frm.fields_dict.manual_material_prices.grid;
        grid.grid_rows.forEach(row => {
            let show = true;
            let d = row.doc;
            if (name_filter && !(d.item_name || '').toLowerCase().includes(name_filter) && !(d.item_code || '').toLowerCase().includes(name_filter)) show = false;
            if (group_filter && d.item_group !== group_filter) show = false;
            if (price_min > 0 && flt(d.last_purchase_price) < price_min) show = false;
            if (price_max > 0 && flt(d.last_purchase_price) > price_max) show = false;
            if (supplier_filter && !(d.supplier || '').toLowerCase().includes(supplier_filter)) show = false;
            row.wrapper.toggle(show);
            if (show) visible_count++;
        });
        frappe.show_alert({ message: visible_count + ' مورد نمایش داده شد', indicator: 'green' });
    },

    // ❌ پاک کردن فیلترها
    raw_material_clear_filter_button: function (frm) {
        console.log('❌ raw_material_clear_filter_button clicked');

        // پاک کردن فیلدهای فیلتر
        frm.set_value('raw_material_filter_name', '');
        frm.set_value('raw_material_filter_group', '');
        frm.set_value('raw_material_filter_price_min', 0);
        frm.set_value('raw_material_filter_price_max', 0);
        frm.set_value('raw_material_filter_supplier', '');

        // Inline: show all raw materials (refresh the table)
        if (frm.doc.manual_material_prices && frm.doc.manual_material_prices.length > 0) {
            frm.refresh_field('manual_material_prices');
        }

        frappe.show_alert({
            message: __('فیلترها پاک شد'),
            indicator: 'blue'
        });
    },

    apply_bundle_prices_button: function (frm) {
        console.log('apply_bundle_prices_button clicked');

        if (!frm.doc.product_bundles || frm.doc.product_bundles.length === 0) {
            frappe.msgprint(__('هیچ بسته محصولی برای اعمال وجود ندارد. ابتدا بسته‌ها را محاسبه کنید.'));
            return;
        }

        frappe.confirm(
            __('آیا می‌خواهید قیمت‌های بسته محصولات را به لیست قیمت اعمال کنید؟'),
            function () {
                frappe.call({
                    method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.apply_bundle_prices',
                    args: {
                        docname: frm.docname
                    },
                    freeze: true,
                    freeze_message: __('در حال اعمال قیمت‌ها...')
                }).then(r => {
                    if (r.message && r.message.success) {
                        frappe.show_alert({
                            message: r.message.message,
                            indicator: 'green'
                        });
                        frm.reload_doc();
                    } else {
                        frappe.msgprint({
                            title: __('خطا'),
                            message: r.message.message || __('خطا در اعمال قیمت‌ها'),
                            indicator: 'red'
                        });
                    }
                });
            }
        );
    },

    clear_bulk_pricing_button: function (frm) {
        console.log("clear_bulk_pricing_button clicked");
        // Inline: clear bulk pricing table
        if (!frm.doc.bulk_pricing_items || frm.doc.bulk_pricing_items.length === 0) {
            frappe.show_alert({ message: 'جدول قیمت‌گذاری دستی خالی است', indicator: 'yellow' });
            return;
        }
        frappe.confirm(
            __('آیا مطمئن هستید که می‌خواهید تمام کالاهای جدول قیمت‌گذاری دستی را پاک کنید؟'),
            function () {
                const item_count = frm.doc.bulk_pricing_items.length;
                frm.clear_table('bulk_pricing_items');
                frm.refresh_field('bulk_pricing_items');
                frm.dirty();
                frappe.show_alert({ message: item_count + ' کالا از جدول قیمت‌گذاری دستی پاک شد', indicator: 'blue' });
            }
        );
    },

    select_all_items_button: function (frm) {
        console.log("select_all_items_button clicked");
        // Inline: select all bulk pricing items
        if (!frm.doc.bulk_pricing_items || frm.doc.bulk_pricing_items.length === 0) {
            frappe.show_alert({ message: 'هیچ کالایی در جدول وجود ندارد', indicator: 'yellow' });
            return;
        }
        let changed = 0;
        frm.doc.bulk_pricing_items.forEach(item => {
            if (!item.selected) { item.selected = 1; changed++; }
        });
        frm.refresh_field('bulk_pricing_items');
        frm.dirty();
        frappe.show_alert({ message: changed + ' کالا انتخاب شد', indicator: 'green' });
    },

    deselect_all_items_button: function (frm) {
        console.log("deselect_all_items_button clicked");
        // Inline: deselect all bulk pricing items
        if (!frm.doc.bulk_pricing_items || frm.doc.bulk_pricing_items.length === 0) {
            frappe.show_alert({ message: 'هیچ کالایی در جدول وجود ندارد', indicator: 'yellow' });
            return;
        }
        let changed = 0;
        frm.doc.bulk_pricing_items.forEach(item => {
            if (item.selected) { item.selected = 0; changed++; }
        });
        frm.refresh_field('bulk_pricing_items');
        frm.dirty();
        frappe.show_alert({ message: changed + ' کالا لغو انتخاب شد', indicator: 'blue' });
    },

    // تحلیل مالی - analytics are on-demand via buttons, no auto-trigger
    monthly_fixed_costs: function (frm) {
        frm.dirty();
    },

    target_monthly_revenue: function (frm) {
        frm.dirty();
    },

    load_fixed_costs_button: function (frm) {
        console.log("load_fixed_costs_button clicked");
        // Inline: load fixed costs from accounting
        frappe.show_alert({ message: 'در حال بارگذاری هزینه‌های ثابت از حسابداری...', indicator: 'blue' });
        frappe.call({
            method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.get_automatic_fixed_costs',
            args: { doctype: frm.doc.doctype, name: frm.doc.name },
            callback: function (r) {
                if (r.message !== undefined && r.message > 0) {
                    frm.set_value('monthly_fixed_costs', r.message);
                    frappe.show_alert({ message: 'هزینه‌های ثابت ماهانه بارگذاری شد', indicator: 'green' });
                } else {
                    frappe.msgprint({ title: __('نتیجه'), message: __('هزینه‌های ثابت یافت نشد. مقدار را دستی وارد کنید.'), indicator: 'orange' });
                }
            }
        });
    },

    selected_price_type: function (frm) {
        handle_price_type_change(frm, frm.doc.selected_price_type);

        if (frm.doc.items && frm.doc.items.length > 0) {
            // محاسبه سریع client-side بدون درخواست به سرور
            recalculate_prices_client_side(frm);
            frm.dirty();
        }
    },

    price_rounding_amount: function (frm) {
        console.log("price_rounding_amount field changed", frm.doc.price_rounding_amount);
        // Auto-calculation disabled per user request
        frm.dirty();
    },

    enable_volume_pricing: function (frm) {
        console.log("enable_volume_pricing field changed", frm.doc.enable_volume_pricing);
        if (frm.doc.enable_volume_pricing) {
            show_volume_pricing_setup(frm);
        }
    },

    enable_customer_tier_pricing: function (frm) {
        console.log("enable_customer_tier_pricing field changed", frm.doc.enable_customer_tier_pricing);
        if (frm.doc.enable_customer_tier_pricing) {
            show_customer_tier_setup(frm);
        }
    },

    enable_seasonal_pricing: function (frm) {
        console.log("enable_seasonal_pricing field changed", frm.doc.enable_seasonal_pricing);
        if (frm.doc.enable_seasonal_pricing) {
            calculate_dynamic_seasonal_factors(frm);
        }
    }
});

// Child table events for Auto Price List Item
frappe.ui.form.on('Auto Price List Item', {
    item_code: function (frm, cdt, cdn) {
        // Apply BOM status styling when item code changes
        setTimeout(() => {
            apply_bom_status_styling(frm);
        }, 500);
    },

    items_add: function (frm, cdt, cdn) {
        // Apply BOM status styling when new item is added
        setTimeout(() => {
            apply_bom_status_styling(frm);
        }, 500);
    },

    items_remove: function (frm, cdt, cdn) {
        // Apply BOM status styling when item is removed
        setTimeout(() => {
            apply_bom_status_styling(frm);
        }, 500);
    }
});

// Child table event handlers
frappe.ui.form.on('Auto Price List Product Bundle', {
    product_bundle: function (frm, cdt, cdn) {
        // bundle انتخاب شد - آیتم‌ها از طریق دکمه "دریافت بسته‌ها" لود می‌شن
        // دیگه نیازی به محاسبه دستی نیست
    }
});

// Load button configuration and add buttons dynamically
function load_and_add_buttons(frm) {
    console.log("Loading button configuration...");

    try {
        // Clear existing custom buttons
        frm.clear_custom_buttons();

        // Add all essential buttons directly
        add_all_buttons(frm);

        console.log("✅ Buttons loaded successfully");
    } catch (error) {
        console.error("❌ Error loading buttons:", error);
        frappe.show_alert({
            message: 'خطا در بارگذاری دکمه‌ها: ' + error.message,
            indicator: 'red'
        });
    }
}

function add_all_buttons(frm) {
    console.log("Adding optimized buttons");

    const has_items = frm.doc.items && frm.doc.items.length > 0;
    const selected_price_type = frm.doc.selected_price_type || 'base_price';

    // ═══════════════════════════════════════════════════════════════
    // 🎯 دکمه‌های اصلی (Primary Actions)
    // ═══════════════════════════════════════════════════════════════

    // دکمه اصلی محاسبه بهای تمام شده (Server-Side با Progress)
    frm.add_custom_button(__('🔄 محاسبه بهای تمام شده'), function () {
        if (!frm.doc.items || frm.doc.items.length === 0) {
            frappe.msgprint({ title: 'توجه', message: 'هیچ آیتمی برای محاسبه وجود ندارد', indicator: 'orange' });
            return;
        }

        const items_count = frm.doc.items.length;

        frappe.confirm(
            `⚡ محاسبه بهای تمام شده<br><br>` +
            `<small>تعداد آیتم‌ها: <b>${items_count}</b></small>`,
            function () {
                // ساخت progress dialog
                const progress_dialog = new frappe.ui.Dialog({
                    title: '⚡ محاسبه بهای تمام شده',
                    fields: [{
                        fieldtype: 'HTML',
                        fieldname: 'progress_html',
                        options: `
                            <div id="ultra-fast-progress-container">
                                <div class="progress" style="height: 25px; margin-bottom: 15px;">
                                    <div id="ultra-fast-progress-bar" class="progress-bar progress-bar-striped progress-bar-animated"
                                         role="progressbar" style="width: 0%; background-color: #2185d0;">
                                        <span id="ultra-fast-progress-text" style="color: white; font-weight: bold;">0%</span>
                                    </div>
                                </div>
                                <p id="ultra-fast-status-message" style="text-align: center; font-size: 14px; color: #666;">
                                    شروع محاسبه...
                                </p>
                                <div id="ultra-fast-time-elapsed" style="text-align: center; font-size: 12px; color: #999;">
                                    زمان سپری شده: 0 ثانیه
                                </div>
                            </div>
                        `
                    }],
                    primary_action_label: 'بستن',
                    primary_action: function () {
                        progress_dialog.hide();
                    }
                });
                progress_dialog.show();
                progress_dialog.$wrapper.find('.modal-dialog').css('max-width', '500px');

                // شروع تایمر
                let start_time = Date.now();
                let timer_interval = setInterval(() => {
                    let elapsed = Math.round((Date.now() - start_time) / 1000);
                    $('#ultra-fast-time-elapsed').text(`زمان سپری شده: ${elapsed} ثانیه`);
                }, 1000);

                // گوش دادن به realtime progress
                frappe.realtime.on('costing_progress', function (data) {
                    console.log('📊 Progress:', data);
                    $('#ultra-fast-progress-bar').css('width', data.progress + '%');
                    $('#ultra-fast-progress-text').text(data.progress + '%');
                    $('#ultra-fast-status-message').text(data.message);

                    if (data.progress >= 100) {
                        $('#ultra-fast-progress-bar').removeClass('progress-bar-animated progress-bar-striped');
                        $('#ultra-fast-progress-bar').css('background-color', '#21ba45');
                    }
                });

                // گوش دادن به اتمام background job
                frappe.realtime.on('costing_complete', function (data) {
                    console.log('✅ Complete:', data);
                    clearInterval(timer_interval);
                    frappe.realtime.off('costing_progress');
                    frappe.realtime.off('costing_complete');

                    if (data.success) {
                        $('#ultra-fast-progress-bar').css('width', '100%').css('background-color', '#21ba45');
                        $('#ultra-fast-progress-text').text('✅ کامل شد');
                        $('#ultra-fast-status-message').html(`<span style="color: green; font-weight: bold;">${data.message || 'محاسبه کامل شد'}</span>`);
                        frm.reload_doc();
                    } else {
                        $('#ultra-fast-progress-bar').css('background-color', '#e74c3c');
                        $('#ultra-fast-status-message').html(`<span style="color: red;">${data.message || 'خطا در محاسبه'}</span>`);
                    }
                });

                // فراخوانی متد (async — بدون freeze)
                frappe.call({
                    method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.calculate_full_costing_ultra_fast_api',
                    args: { docname: frm.doc.name },
                    freeze: false,
                    async: true,
                    timeout: 600
                }).then((response) => {
                    if (response && response.message) {
                        const result = response.message;
                        if (result.background) {
                            // Background job — progress updates will come via realtime
                            $('#ultra-fast-status-message').html(
                                `<span style="color: #2185d0; font-weight: bold;">⏳ ${result.message}</span><br>` +
                                `<small>پیشرفت بصورت خودکار نمایش داده میشه...</small>`
                            );
                        } else {
                            // Foreground — done immediately
                            clearInterval(timer_interval);
                            frappe.realtime.off('costing_progress');
                            frappe.realtime.off('costing_complete');

                            if (result.success) {
                                let elapsed = Math.round((Date.now() - start_time) / 1000);
                                $('#ultra-fast-progress-bar').css('width', '100%').css('background-color', '#21ba45')
                                    .removeClass('progress-bar-animated progress-bar-striped');
                                $('#ultra-fast-progress-text').text('✅');
                                $('#ultra-fast-status-message').html(
                                    `<span style="color: green; font-weight: bold;">✅ ${result.message}</span><br>` +
                                    `<small>⏱ ${elapsed} ثانیه</small>`
                                );
                                frm.reload_doc();
                            } else {
                                $('#ultra-fast-progress-bar').css('background-color', '#e74c3c');
                                $('#ultra-fast-status-message').html(`<span style="color: red;">${result.message || 'خطا'}</span>`);
                            }
                        }
                    }
                }).catch((error) => {
                    clearInterval(timer_interval);
                    frappe.realtime.off('costing_progress');
                    frappe.realtime.off('costing_complete');
                    console.error('Error:', error);
                    $('#ultra-fast-progress-bar').css('background-color', '#e74c3c');
                    $('#ultra-fast-status-message').html(`<span style="color: red;">خطا: ${error.message || error}</span>`);
                });
            }
        );
    }, __('⚡ عملیات'));

    // دکمه تست ساده
    frm.add_custom_button(__('🧪 تست محاسبه ساده'), function () {
        frappe.call({
            method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.simple_dynamic_pricing_test',
            args: {
                docname: frm.doc.name
            },
            callback: function (r) {
                if (r.message) {
                    if (r.message.success) {
                        frappe.show_alert({
                            message: r.message.message,
                            indicator: 'green'
                        });
                        frm.refresh();
                    } else {
                        frappe.show_alert({
                            message: r.message.message,
                            indicator: 'red'
                        });
                    }
                }
            }
        });
    }, __('⚡ عملیات'));

    frm.add_custom_button(__('🔄 محاسبه داینامیک قیمت‌ها'), function () {
        // نمایش دیالوگ پیشرفت برای محاسبه داینامیک
        show_dynamic_pricing_progress_dialog(frm);

        // فراخوانی متد سرور با timeout
        frappe.call({
            method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.update_item_prices_with_details_api',
            args: {
                docname: frm.doc.name
            },
            freeze: false,
            timeout: 300000  // 5 دقیقه timeout
        }).then((response) => {
            console.log('✅ Dynamic pricing completed:', response);

            // بستن دیالوگ پیشرفت
            setTimeout(() => {
                hide_dynamic_pricing_progress_dialog();
            }, 2000);

            if (response && response.message) {
                const result = response.message;

                if (result.success) {
                    frappe.show_alert({
                        message: result.message,
                        indicator: 'green'
                    }, 5);

                    // به‌روزرسانی صفحه
                    if (result.refresh_needed) {
                        setTimeout(() => {
                            refresh_content_without_reload(frm);
                        }, 2500);
                    }
                } else {
                    frappe.show_alert({
                        message: result.message || 'خطا در محاسبه قیمت‌ها',
                        indicator: 'red'
                    }, 7);
                }
            }
        }).catch((error) => {
            console.error('Error in dynamic pricing:', error);
            hide_dynamic_pricing_progress_dialog();
            frappe.show_alert({
                message: __('❌ خطا در محاسبه قیمت‌ها: ') + (error.message || 'خطای نامشخص'),
                indicator: 'red'
            }, 7);
        });
    }, __('⚡ عملیات'));

    // 📦 بسته‌های محصولات
    frm.add_custom_button(__('📦 محاسبه قیمت بسته‌ها'), function () {
        calculate_bundle_prices_button(frm);
    }, __('⚡ عملیات'));

    // 📊 تحلیل‌ها
    frm.add_custom_button(__('📊 نمایش تحلیل‌ها'), function () {
        show_analytics_dashboard_button(frm);
    }, __('⚡ عملیات'));

    // ═══════════════════════════════════════════════════════════════
    // 🔧 Manual API Trigger Buttons (No Save Required)
    // ═══════════════════════════════════════════════════════════════

    // 📊 Compare prices with selected price list (Manual trigger)
    frm.add_custom_button(__('📊 مقایسه قیمت‌ها'), function () {
        if (!frm.doc.compare_with_price_list) {
            frappe.msgprint(__('لطفاً ابتدا لیست قیمت مقایسه را انتخاب کنید'));
            return;
        }
        if (!frm.doc.items || frm.doc.items.length === 0) {
            frappe.msgprint(__('ابتدا کالاها را دریافت کنید'));
            return;
        }
        frappe.call({
            method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.calculate_item_prices_api',
            args: { docname: frm.doc.name },
            freeze: true,
            freeze_message: __('در حال مقایسه قیمت‌ها...')
        }).then(r => {
            if (r.message && r.message.success) {
                frappe.show_alert({ message: r.message.message, indicator: 'green' });
                frm.reload_doc();
            } else {
                frappe.msgprint(r.message ? r.message.message : __('خطا در مقایسه قیمت‌ها'));
            }
        });
    }, __('🔧 عملیات API'));

    // 🔄 Recalculate all prices server-side
    frm.add_custom_button(__('🔄 محاسبه مجدد قیمت‌ها'), function () {
        frappe.call({
            method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.recalculate_all_prices_api',
            args: { docname: frm.doc.name },
            freeze: true,
            freeze_message: __('در حال محاسبه مجدد قیمت‌ها در سرور...')
        }).then(r => {
            if (r.message && r.message.success) {
                frappe.show_alert({ message: r.message.message, indicator: 'green' });
                frm.reload_doc();
            } else {
                frappe.msgprint(r.message ? r.message.message : __('خطا در محاسبه قیمت‌ها'));
            }
        });
    }, __('🔧 عملیات API'));

    // 🧹 Clear heavy fields from document (reduces payload size)
    frm.add_custom_button(__('🧹 پاکسازی داده‌های سنگین'), function () {
        frappe.call({
            method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.clear_heavy_fields_api',
            args: { docname: frm.doc.name },
            freeze: true,
            freeze_message: __('در حال پاکسازی...')
        }).then(r => {
            if (r.message && r.message.success) {
                frappe.show_alert({ message: r.message.message, indicator: 'green' });
                frm.reload_doc();
            } else {
                frappe.msgprint(r.message ? r.message.message : __('خطا در پاکسازی'));
            }
        });
    }, __('🔧 عملیات API'));

    // Add missing render_quality_metrics function
    if (!window.render_quality_metrics) {
        window.render_quality_metrics = function () {
            console.log('render_quality_metrics called - placeholder function');
            return;
        };
    }

    // Add improved render_simple_pie_chart function
    if (!window.render_simple_pie_chart) {
        window.render_simple_pie_chart = function (canvas_id, data, title) {
            try {
                const canvas = document.getElementById(canvas_id);
                if (!canvas) {
                    console.warn(`Canvas with id ${canvas_id} not found`);
                    return;
                }

                // Validate and filter data
                if (!data || data.length === 0) {
                    console.warn(`No data provided for chart ${canvas_id}`);
                    return;
                }

                const validData = data.filter(item => item.value > 0);
                if (validData.length === 0) {
                    console.warn(`No valid data (positive values) for chart ${canvas_id}`);
                    return;
                }

                const ctx = canvas.getContext('2d');
                const centerX = canvas.width / 2;
                const centerY = canvas.height / 2;
                const radius = Math.max(10, Math.min(centerX, centerY) - 40);

                // Clear canvas
                ctx.clearRect(0, 0, canvas.width, canvas.height);

                // Calculate total
                const total = validData.reduce((sum, item) => sum + item.value, 0);

                // Draw pie slices
                let currentAngle = -Math.PI / 2;
                const colors = ['#3498db', '#e74c3c', '#f39c12', '#9b59b6', '#1abc9c', '#34495e', '#e67e22', '#95a5a6'];

                validData.forEach((item, index) => {
                    const sliceAngle = (item.value / total) * 2 * Math.PI;

                    ctx.beginPath();
                    ctx.moveTo(centerX, centerY);
                    ctx.arc(centerX, centerY, radius, currentAngle, currentAngle + sliceAngle);
                    ctx.closePath();
                    ctx.fillStyle = colors[index % colors.length];
                    ctx.fill();

                    currentAngle += sliceAngle;
                });

                // Draw title
                if (title) {
                    ctx.fillStyle = '#2c3e50';
                    ctx.font = 'bold 16px Arial';
                    ctx.textAlign = 'center';
                    ctx.fillText(title, centerX, 30);
                }

                console.log(`✅ Chart ${canvas_id} rendered successfully`);

            } catch (error) {
                console.error(`❌ Error rendering chart ${canvas_id}:`, error);
            }
        };
    }

    frm.add_custom_button(__('نمایش داشبورد قیمت‌گذاری'), function () {
        show_pricing_dashboard(frm);
    }, __('⚡ عملیات'));

    // Advanced buttons - always show
    frm.add_custom_button(__('بهینه‌سازی هوشمند قیمت‌ها'), function () {
        ai_optimize_all_prices(frm);
    }, __('🤖 هوش مصنوعی'));

    frm.add_custom_button(__('نظارت بر هزینه‌ها'), function () {
        setup_cost_monitoring(frm);
    }, __('🤖 هوش مصنوعی'));

    frm.add_custom_button(__('تحلیل بازار'), function () {
        show_market_analysis(frm);
    }, __('🤖 هوش مصنوعی'));

    frm.add_custom_button(__('پیشنهادات قیمت‌گذاری'), function () {
        show_pricing_recommendations(frm);
    }, __('🤖 هوش مصنوعی'));

    frm.add_custom_button(__('صادرات داده‌ها'), function () {
        export_pricing_data(frm);
    }, __('📚 داده‌ها'));

    if (has_items) {

        // Combined pricing strategies
        if (selected_price_type === 'combined_discount_installment') {
            frm.add_custom_button(__('استراتژی‌های ترکیبی'), function () {
                show_combined_pricing_strategies(frm);
            }, __('💰 استراتژی'));

            frm.add_custom_button(__('اعمال استراتژی ترکیبی'), function () {
                apply_combined_pricing_strategies(frm);
            }, __('💰 استراتژی'));

            frm.add_custom_button(__('مقایسه استراتژی‌ها'), function () {
                frappe.call({
                    method: 'compare_combined_strategies',
                    doc: frm.doc,
                    callback: function (r) {
                        if (r.message) {
                            show_strategy_comparison_dialog(r.message);
                        }
                    }
                });
            }, __('💰 استراتژی'));
        }

    }

    // Detailed Pricing Breakdown button - always show
    frm.add_custom_button(__('📊 گزارش مرحله‌ای قیمت‌گذاری'), function () {
        show_detailed_pricing_breakdown(frm);
    }, __('📊 گزارشات'));

    frm.add_custom_button(__('🔍 تحلیل مراحل داینامیک'), function () {
        show_pricing_steps_analysis(frm);
    }, __('📊 گزارشات'));

    // Add report buttons
    frm.add_custom_button(__('نمایش تأثیر قیمت‌های دستی'), function () {
        show_manual_price_impact(frm);
    }, __('📊 گزارشات'));

    frm.add_custom_button(__('🔍 نمایش محصولات بدون BOM'), function () {
        show_items_without_bom(frm);
    }, __('📊 گزارشات'));

    // دکمه گزارش مقایسه قیمت
    frm.add_custom_button(__('📊 مقایسه قیمت با لیست مقایسه'), function () {
        show_price_comparison_report(frm);
    }, __('📊 گزارشات'));

    frm.add_custom_button(__('📊 جزئیات هزینه محصولات'), function () {
        show_item_cost_breakdown_dialog(frm);
    }, __('📊 گزارشات'));

    frm.add_custom_button(__('گزارش تغییرات قیمت'), function () {
        show_price_change_report_dialog(frm);
    }, __('📊 گزارشات'));

    // 💱 دکمه گزارش چند ارزی
    if (frm.doc.enable_multi_currency && frm.doc.currency_exchange_rate > 0) {
        frm.add_custom_button(__('💱 گزارش قیمت‌ها به ارز ثانویه'), function () {
            show_secondary_currency_report(frm);
        }, __('📊 گزارشات'));
    }

    // Add material buttons
    add_material_substitution_buttons(frm);
    add_missing_material_buttons(frm);
    // دکمه حذف گروهی آیتم‌های prev_items بر اساس نام کالا
    frm.add_custom_button(__('حذف آیتم‌های قبلی با فیلتر نام'), function () {
        frappe.prompt([
            {
                fieldtype: 'Data',
                label: 'عبارت جستجو در نام کالا (item_code)',
                fieldname: 'name_filter',
                reqd: 1,
                description: 'مثلاً: پارچه'
            }
        ], function (values) {
            remove_filtered_prev_items(frm, values.name_filter);
        }, __('حذف گروهی آیتم‌های قبلی'), __('حذف آیتم‌ها'));
    }, __('⚡ عملیات'));
}
// حذف آیتم‌های prev_items که item_code آن‌ها شامل عبارت جستجو است
function remove_filtered_prev_items(frm, name_filter) {
    if (!frm.doc.prev_items || !name_filter) {
        frappe.msgprint('هیچ آیتمی برای حذف یا عبارت جستجو وارد نشده است.');
        return;
    }
    let removed = 0;
    // حذف از انتها به ابتدا تا indexها به هم نریزد
    for (let i = frm.doc.prev_items.length - 1; i >= 0; i--) {
        let row = frm.doc.prev_items[i];
        if (row.item_code && row.item_code.includes(name_filter)) {
            frm.get_field('prev_items').grid.grid_rows[i].remove();
            removed++;
        }
    }
    frm.refresh_field('prev_items');
    frappe.show_alert(removed > 0 ? `${removed} آیتم حذف شد.` : 'آیتمی مطابق جستجو یافت نشد.');
}

/**
 * 💱 محاسبه و نمایش قیمت‌ها به ارز ثانویه
 * با رندینگ و فرمت مناسب
 */
function update_secondary_currency_prices(frm) {
    if (!frm.doc.enable_multi_currency || !frm.doc.currency_exchange_rate || frm.doc.currency_exchange_rate <= 0) {
        return;
    }

    const exchange_rate = flt(frm.doc.currency_exchange_rate);
    const rounding = flt(frm.doc.secondary_rounding_amount || 1);
    const currency_symbol = frm.doc.secondary_currency || 'USD';

    let total_secondary = 0;
    let items_with_price = 0;

    // محاسبه برای هر آیتم
    (frm.doc.items || []).forEach(item => {
        if (item.selling_price && item.selling_price > 0) {
            // تبدیل به ارز ثانویه
            let secondary_price = item.selling_price / exchange_rate;

            // رند کردن
            if (rounding > 0) {
                secondary_price = Math.ceil(secondary_price / rounding) * rounding;
            }

            // ذخیره در فیلد موقت (برای نمایش)
            item.secondary_currency_price = secondary_price;
            total_secondary += secondary_price;
            items_with_price++;
        }
    });

    // نمایش خلاصه
    if (items_with_price > 0) {
        console.log(`💱 Converted ${items_with_price} prices to ${currency_symbol}`);

        // نمایش در dashboard یا alert
        frm.dashboard.show_progress(
            __('تبدیل ارز'),
            100,
            `${items_with_price} آیتم به ${currency_symbol} تبدیل شد`
        );

        // به‌روزرسانی جدول
        frm.refresh_field('items');
    }
}

/**
 * 💱 نمایش گزارش قیمت‌های ارز ثانویه
 */
function show_secondary_currency_report(frm) {
    if (!frm.doc.enable_multi_currency || !frm.doc.currency_exchange_rate) {
        frappe.msgprint(__('لطفاً ابتدا تنظیمات چند ارزی را فعال کنید'));
        return;
    }

    const exchange_rate = flt(frm.doc.currency_exchange_rate);
    const rounding = flt(frm.doc.secondary_rounding_amount || 1);
    const currency = frm.doc.secondary_currency || 'USD';

    let html = `
        <div style="direction: rtl; text-align: right;">
            <h4>💱 گزارش قیمت‌ها به ${currency}</h4>
            <p><strong>نرخ تبدیل:</strong> 1 ${currency} = ${format_number(exchange_rate)} ریال</p>
            <p><strong>رندینگ:</strong> ${rounding} ${currency}</p>
            <hr>
            <table class="table table-bordered table-striped">
                <thead>
                    <tr>
                        <th>کد کالا</th>
                        <th>نام کالا</th>
                        <th>قیمت فروش (ریال)</th>
                        <th>قیمت فروش (${currency})</th>
                    </tr>
                </thead>
                <tbody>
    `;

    let total_rial = 0;
    let total_secondary = 0;

    (frm.doc.items || []).forEach(item => {
        if (item.selling_price && item.selling_price > 0) {
            let secondary_price = item.selling_price / exchange_rate;
            if (rounding > 0) {
                secondary_price = Math.ceil(secondary_price / rounding) * rounding;
            }

            html += `
                <tr>
                    <td>${item.item_code || '-'}</td>
                    <td>${item.item_name || '-'}</td>
                    <td>${format_number(item.selling_price)}</td>
                    <td><strong>${secondary_price.toFixed(2)} ${currency}</strong></td>
                </tr>
            `;

            total_rial += flt(item.selling_price);
            total_secondary += secondary_price;
        }
    });

    html += `
                </tbody>
                <tfoot>
                    <tr style="font-weight: bold; background: #f5f5f5;">
                        <td colspan="2">مجموع</td>
                        <td>${format_number(total_rial)} ریال</td>
                        <td>${total_secondary.toFixed(2)} ${currency}</td>
                    </tr>
                </tfoot>
            </table>
        </div>
    `;

    frappe.msgprint({
        title: __('💱 گزارش چند ارزی'),
        message: html,
        indicator: 'blue',
        wide: true
    });
}

// Helper function for number formatting
function format_number(num) {
    return new Intl.NumberFormat('fa-IR').format(num || 0);
}

// Removed - replaced with direct button addition

// Removed - integrated into add_all_buttons

function handle_combined_pricing_logic(frm) {
    console.log("Handling combined pricing logic for:", frm.doc.selected_price_type);

    const price_type = frm.doc.selected_price_type;

    // Reset all field requirements first
    frm.set_df_property('target_discount_percentage', 'reqd', 0);
    frm.set_df_property('enable_installment', 'reqd', 0);
    frm.set_df_property('down_payment_percentage', 'reqd', 0);
    frm.set_df_property('number_of_months', 'reqd', 0);
    frm.set_df_property('monthly_interest_rate', 'reqd', 0);

    // Set requirements based on selected price type
    if (price_type === 'discount_only') {
        frm.set_df_property('target_discount_percentage', 'reqd', 1);
        frappe.msgprint({
            title: __('نوع قیمت‌گذاری'),
            message: __('قیمت‌گذاری با تخفیف انتخاب شده است. لطفاً درصد تخفیف هدف را وارد کنید.'),
            indicator: 'blue'
        });
    } else if (price_type === 'installment_only') {
        frm.set_df_property('enable_installment', 'reqd', 1);
        frm.set_df_property('down_payment_percentage', 'reqd', 1);
        frm.set_df_property('number_of_months', 'reqd', 1);
        frm.set_df_property('monthly_interest_rate', 'reqd', 1);
        frm.set_value('enable_installment', 1);
        frappe.msgprint({
            title: __('نوع قیمت‌گذاری'),
            message: __('قیمت‌گذاری قسطی انتخاب شده است. لطفاً تنظیمات قسط را کامل کنید.'),
            indicator: 'blue'
        });
    } else if (price_type === 'combined_discount_installment') {
        // Enable both discount and installment fields
        frm.set_df_property('target_discount_percentage', 'reqd', 1);
        frm.set_df_property('enable_installment', 'reqd', 1);
        frm.set_df_property('down_payment_percentage', 'reqd', 1);
        frm.set_df_property('number_of_months', 'reqd', 1);
        frm.set_df_property('monthly_interest_rate', 'reqd', 1);
        frm.set_value('enable_installment', 1);

        frappe.msgprint({
            title: __('نوع قیمت‌گذاری'),
            message: __('قیمت‌گذاری ترکیبی (تخفیف + قسط) انتخاب شده است. لطفاً تمام تنظیمات را کامل کنید.'),
            indicator: 'orange'
        });

        // Combined pricing strategy dialog removed - only show on button click
    } else {
        // base_price - no special requirements
        frappe.msgprint({
            title: __('نوع قیمت‌گذاری'),
            message: __('قیمت‌گذاری پایه انتخاب شده است. قیمت بر اساس هزینه + حاشیه سود محاسبه می‌شود.'),
            indicator: 'green'
        });
    }

    // Refresh the form to show/hide fields
    frm.refresh();

    // Reload buttons based on new price type
    load_and_add_buttons(frm);

    frm.refresh_fields();
}

// Make prev_items child table columns wider for readability
function adjust_prev_items_table_layout(frm) {
    try {
        const wrapper = $(frm.fields_dict.prev_items.wrapper);
        if (!wrapper || wrapper.length === 0) return;

        // حذف min-width و width سفارشی تا جدول مثل جدول اصلی Frappe نمایش داده شود
        wrapper.find('.grid-row, .grid-static-col, .grid-col').css({
            'padding': '',
            'font-size': '',
            'vertical-align': ''
        });
        wrapper.find('.grid-header-row .grid-col').css({
            'padding': '',
            'font-size': '',
            'background': '',
            'color': '',
            'border-bottom': ''
        });
        wrapper.find('.grid').css({ 'overflow-x': '', 'max-width': '' });
        wrapper.closest('.frappe-control').css({ 'max-width': '' });

        // فیلد فیلتر را فقط فونت و فاصله بده
        if (frm.fields_dict.filter_item_name && frm.fields_dict.filter_item_name.input) {
            $(frm.fields_dict.filter_item_name.input).css({
                'font-size': '14px',
                'padding': '6px'
            });
        }
    } catch (e) {
        console.error('adjust_prev_items_table_layout error', e);
    }
}

// Helper function for currency formatting
function format_currency_safe(amount) {
    if (!amount || amount === 0) return '0';
    return new Intl.NumberFormat('fa-IR').format(amount);
}

// تابع نمایش داشبورد قیمت‌گذاری
function show_pricing_dashboard(frm) {
    if (!frm.doc.items || frm.doc.items.length === 0) {
        frappe.msgprint({
            title: __('توجه'),
            message: __('ابتدا کالاها را دریافت کنید'),
            indicator: 'orange'
        });
        return;
    }

    let dashboard_html = generate_dashboard_html(frm);

    let dialog = new frappe.ui.Dialog({
        title: __('داشبورد قیمت‌گذاری'),
        size: 'extra-large',
        fields: [
            {
                fieldname: 'dashboard_content',
                fieldtype: 'HTML'
            }
        ]
    });

    dialog.fields_dict.dashboard_content.$wrapper.html(dashboard_html);
    dialog.show();

    // رندر نمودارها بعد از نمایش dialog
    setTimeout(() => {
        render_dashboard_charts_in_dialog(frm, dialog);
    }, 300);
}

// تابع رندر نمودارها در داخل dialog
function render_dashboard_charts_in_dialog(frm, dialog) {
    let items = frm.doc.items || [];

    // نمودار توزیع هزینه‌ها
    let costChartEl = dialog.$wrapper.find('#cost_breakdown_chart')[0];
    if (costChartEl && typeof Chart !== 'undefined') {
        let totalRawMaterial = items.reduce((sum, item) => sum + (item.raw_material_cost || 0), 0);
        let totalOperation = items.reduce((sum, item) => sum + (item.operation_cost || 0), 0);
        let totalOverhead = items.reduce((sum, item) => sum + (item.overhead_cost || 0), 0);

        new Chart(costChartEl, {
            type: 'doughnut',
            data: {
                labels: ['مواد اولیه', 'عملیات', 'سربار'],
                datasets: [{
                    data: [totalRawMaterial, totalOperation, totalOverhead],
                    backgroundColor: ['#2196f3', '#ff9800', '#4caf50']
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'توزیع هزینه‌ها'
                    }
                }
            }
        });
    }

    // نمودار حاشیه سود
    let profitChartEl = dialog.$wrapper.find('#profit_margin_chart')[0];
    if (profitChartEl && typeof Chart !== 'undefined') {
        let profitableCount = items.filter(item => (item.profit_amount || 0) > 0).length;
        let lossCount = items.filter(item => (item.profit_amount || 0) <= 0).length;

        new Chart(profitChartEl, {
            type: 'pie',
            data: {
                labels: ['سودآور', 'ضررآور'],
                datasets: [{
                    data: [profitableCount, lossCount],
                    backgroundColor: ['#4caf50', '#f44336']
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'وضعیت سودآوری'
                    }
                }
            }
        });
    }
}

function generate_dashboard_html(frm) {
    console.log("generate_dashboard_html called with items count:", frm.doc.items?.length || 0);
    let items = frm.doc.items || [];
    let total_items = items.length;
    let total_cost = items.reduce((sum, item) => sum + (item.total_cost || 0), 0);
    let total_selling_price = items.reduce((sum, item) => sum + (item.selling_price || 0), 0);
    let total_profit = total_selling_price - total_cost;
    let avg_profit_margin = total_cost > 0 ? (total_profit / total_cost) * 100 : 0;

    // Calculate additional metrics
    let profitable_items = items.filter(item => (item.profit_loss_status === 'سودآور')).length;
    let loss_items = items.filter(item => (item.profit_loss_status === 'ضررآور')).length;
    let total_final_price = items.reduce((sum, item) => sum + (item.final_selected_price || 0), 0);
    let total_installment = items.reduce((sum, item) => sum + (item.total_installment_amount || 0), 0);

    return `
        <div style="padding: 20px; direction: rtl; font-family: 'Vazir', Arial, sans-serif;">
            <div class="row">
                <div class="col-md-12">
                    <h3>داشبورد قیمت‌گذاری</h3>
                </div>
            </div>
            
            <!-- Summary Cards -->
            <div class="row" style="margin-bottom: 30px;">
                <div class="col-md-3">
                    <div class="card" style="background: #e3f2fd; padding: 15px; border-radius: 8px;">
                        <h4 style="color: #1976d2; margin: 0;">${total_items}</h4>
                        <p style="margin: 5px 0 0 0; color: #666;">تعداد کل کالاها</p>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card" style="background: #f3e5f5; padding: 15px; border-radius: 8px;">
                        <h4 style="color: #7b1fa2; margin: 0;">${format_currency_safe(total_cost)}</h4>
                        <p style="margin: 5px 0 0 0; color: #666;">هزینه کل</p>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card" style="background: #e8f5e8; padding: 15px; border-radius: 8px;">
                        <h4 style="color: #388e3c; margin: 0;">${format_currency_safe(total_selling_price)}</h4>
                        <p style="margin: 5px 0 0 0; color: #666;">قیمت فروش کل</p>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card" style="background: #fff3e0; padding: 15px; border-radius: 8px;">
                        <h4 style="color: #f57c00; margin: 0;">${avg_profit_margin.toFixed(1)}%</h4>
                        <p style="margin: 5px 0 0 0; color: #666;">میانگین حاشیه سود</p>
                    </div>
                </div>
            </div>
            
            <!-- Additional Metrics -->
            <div class="row" style="margin-bottom: 30px;">
                <div class="col-md-3">
                    <div class="card" style="background: #e8f5e8; padding: 15px; border-radius: 8px;">
                        <h4 style="color: #4caf50; margin: 0;">${profitable_items}</h4>
                        <p style="margin: 5px 0 0 0; color: #666;">کالاهای سودآور</p>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card" style="background: #ffebee; padding: 15px; border-radius: 8px;">
                        <h4 style="color: #f44336; margin: 0;">${loss_items}</h4>
                        <p style="margin: 5px 0 0 0; color: #666;">کالاهای ضررآور</p>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card" style="background: #f3e5f5; padding: 15px; border-radius: 8px;">
                        <h4 style="color: #9c27b0; margin: 0;">${format_currency_safe(total_final_price)}</h4>
                        <p style="margin: 5px 0 0 0; color: #666;">قیمت نهایی انتخابی</p>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card" style="background: #e1f5fe; padding: 15px; border-radius: 8px;">
                        <h4 style="color: #0277bd; margin: 0;">${format_currency_safe(total_installment)}</h4>
                        <p style="margin: 5px 0 0 0; color: #666;">مجموع قسطی (با بهره)</p>
                    </div>
                </div>
            </div>
            
            <!-- Charts Row -->
            <div class="row">
                <div class="col-md-6">
                    <div class="card" style="padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
                        <div id="cost_breakdown_chart" style="height: 300px;"></div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card" style="padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
                        <div id="profit_margin_chart" style="height: 300px;"></div>
                    </div>
                </div>
            </div>
            
            <div class="row" style="margin-top: 20px;">
                <div class="col-md-12">
                    <div class="card" style="padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
                        <div id="top_items_chart" style="height: 300px;"></div>
                    </div>
                </div>
            </div>
            
            <!-- Profit/Loss Analysis -->
            <div class="row" style="margin-top: 20px;">
                <div class="col-md-6">
                    <div class="card" style="padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
                        <h4>کالاهای پرسود</h4>
                        <div id="top_profitable_table"></div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card" style="padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
                        <h4>کالاهای ضررآور (نیاز به بررسی)</h4>
                        <div id="loss_items_table"></div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function render_dashboard_charts(frm) {
    console.log("render_dashboard_charts called");
    let items = frm.doc.items || [];

    // Cost Breakdown Pie Chart
    render_cost_breakdown_chart(items);

    // Profit Margin Distribution
    render_profit_margin_chart(items);

    // Items Pricing Bar Chart
    render_items_pricing_chart(items);

    // Top Items Table
    render_top_profitable_table(items);

    // Loss Items Table
    render_loss_items_table(items);
}

function render_cost_breakdown_chart(items) {
    console.log("render_cost_breakdown_chart called with items:", items.length);
    let total_raw_material = items.reduce((sum, item) => sum + (item.raw_material_cost || 0), 0);
    let total_operation = items.reduce((sum, item) => sum + (item.operation_cost || 0), 0);
    let total_overhead = items.reduce((sum, item) => sum + (item.overhead_cost || 0), 0);

    let data = [
        {
            labels: ['Raw Materials', 'Operations', 'Overhead'],
            values: [total_raw_material, total_operation, total_overhead],
            type: 'pie',
            marker: {
                colors: ['#ff6b6b', '#4ecdc4', '#45b7d1']
            }
        }
    ];

    let layout = {
        title: 'Cost Components',
        showlegend: true,
        margin: { t: 40, b: 40, l: 40, r: 40 }
    };

    // Use simple HTML chart instead
    let chart_html = `<div style="text-align: center;">`;
    let persian_labels = ['مواد اولیه', 'عملیات', 'سربار'];
    data[0].labels.forEach((label, i) => {
        let percentage = total_raw_material + total_operation + total_overhead > 0 ?
            (data[0].values[i] / (total_raw_material + total_operation + total_overhead) * 100).toFixed(1) : 0;
        chart_html += `<div style="margin: 5px 0; padding: 10px; background: ${data[0].marker.colors[i]}; color: white; border-radius: 5px;">
            ${persian_labels[i]}: ${format_currency(data[0].values[i])} (${percentage}%)
        </div>`;
    });
    chart_html += `</div>`;
    document.getElementById('cost_breakdown_chart').innerHTML = chart_html;
}

function render_profit_margin_chart(items) {
    console.log("render_profit_margin_chart called with items:", items.length);
    let margin_ranges = {
        '0-10%': 0,
        '10-20%': 0,
        '20-30%': 0,
        '30-50%': 0,
        '50%+': 0
    };

    items.forEach(item => {
        if (item.total_cost > 0) {
            let margin = ((item.selling_price - item.total_cost) / item.total_cost) * 100;
            if (margin < 10) margin_ranges['0-10%']++;
            else if (margin < 20) margin_ranges['10-20%']++;
            else if (margin < 30) margin_ranges['20-30%']++;
            else if (margin < 50) margin_ranges['30-50%']++;
            else margin_ranges['50%+']++;
        }
    });

    let data = [
        {
            x: Object.keys(margin_ranges),
            y: Object.values(margin_ranges),
            type: 'bar',
            marker: {
                color: ['#ff9999', '#ffcc99', '#99ff99', '#99ccff', '#cc99ff']
            }
        }
    ];

    let layout = {
        title: 'Items by Profit Margin Range',
        xaxis: { title: 'Profit Margin Range' },
        yaxis: { title: 'Number of Items' },
        margin: { t: 40, b: 60, l: 60, r: 40 }
    };

    // Use simple bar chart HTML
    let max_value = Math.max(...Object.values(margin_ranges));
    let chart_html = `<div style="display: flex; align-items: end; height: 200px; gap: 10px;">`;
    Object.entries(margin_ranges).forEach(([range, count]) => {
        let height = max_value > 0 ? (count / max_value * 180) : 0;
        chart_html += `<div style="text-align: center; flex: 1;">
            <div style="background: #4ecdc4; height: ${height}px; margin-bottom: 5px; border-radius: 3px;"></div>
            <div style="font-size: 12px;">${range}</div>
            <div style="font-size: 10px; color: #666;">${count}</div>
        </div>`;
    });
    chart_html += `</div>`;
    document.getElementById('profit_margin_chart').innerHTML = chart_html;
}

function render_items_pricing_chart(items) {
    console.log("render_items_pricing_chart called with items:", items.length);
    // Show top 10 items by selling price
    let sorted_items = items.slice().sort((a, b) => (b.selling_price || 0) - (a.selling_price || 0)).slice(0, 10);

    let item_names = sorted_items.map(item => item.item_code || 'Unknown');
    let costs = sorted_items.map(item => item.total_cost || 0);
    let selling_prices = sorted_items.map(item => item.selling_price || 0);

    let data = [
        {
            x: item_names,
            y: costs,
            name: 'Total Cost',
            type: 'bar',
            marker: { color: '#ff6b6b' }
        },
        {
            x: item_names,
            y: selling_prices,
            name: 'Selling Price',
            type: 'bar',
            marker: { color: '#4ecdc4' }
        }
    ];

    let layout = {
        title: 'Top 10 Items - Cost vs Selling Price',
        xaxis: { title: 'Items' },
        yaxis: { title: 'Amount' },
        barmode: 'group',
        margin: { t: 40, b: 100, l: 60, r: 40 }
    };

    // Use simple comparison chart
    let chart_html = `<div style="max-height: 300px; overflow-y: auto;">`;
    sorted_items.forEach((item, i) => {
        let cost = costs[i];
        let price = selling_prices[i];
        let max_val = Math.max(cost, price);
        chart_html += `<div style="margin: 10px 0; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
            <div style="font-weight: bold; margin-bottom: 5px;">${item_names[i]}</div>
            <div style="display: flex; gap: 10px; align-items: center;">
                <div style="flex: 1;">
                    <div style="background: #ff6b6b; height: 20px; width: ${max_val > 0 ? (cost / max_val * 100) : 0}%; border-radius: 3px;"></div>
                    <small>Cost: ${format_currency(cost)}</small>
                </div>
                <div style="flex: 1;">
                    <div style="background: #4ecdc4; height: 20px; width: ${max_val > 0 ? (price / max_val * 100) : 0}%; border-radius: 3px;"></div>
                    <small>Price: ${format_currency(price)}</small>
                </div>
            </div>
        </div>`;
    });
    chart_html += `</div>`;
    document.getElementById('items_pricing_chart').innerHTML = chart_html;
}

function render_top_profitable_table(items) {
    console.log("render_top_profitable_table called with items:", items.length);
    // Sort by profit amount
    let sorted_items = items.slice().sort((a, b) => (b.profit_amount || 0) - (a.profit_amount || 0)).slice(0, 10);

    let table_html = `
        <table class="table table-bordered" style="font-size: 12px;">
            <thead>
                <tr>
                    <th>کد کالا</th>
                    <th>هزینه کل</th>
                    <th>قیمت فروش</th>
                    <th>مبلغ سود</th>
                    <th>درصد سود</th>
                </tr>
            </thead>
            <tbody>
    `;

    sorted_items.forEach(item => {
        let profit_percentage = item.total_cost > 0 ? ((item.profit_amount || 0) / item.total_cost) * 100 : 0;
        table_html += `
            <tr>
                <td>${item.item_code || 'نامشخص'}</td>
                <td>${format_currency(item.total_cost || 0)}</td>
                <td>${format_currency(item.selling_price || 0)}</td>
                <td>${format_currency(item.profit_amount || 0)}</td>
                <td>${profit_percentage.toFixed(1)}%</td>
            </tr>
        `;
    });

    table_html += `
            </tbody>
        </table>
    `;

    document.getElementById('top_profitable_table').innerHTML = table_html;
}

function render_loss_items_table(items) {
    console.log("render_loss_items_table called with items:", items.length);
    // Filter loss items
    let loss_items = items.filter(item => item.profit_loss_status === 'ضررآور').slice(0, 10);

    if (loss_items.length === 0) {
        document.getElementById('loss_items_table').innerHTML = '<p style="text-align: center; color: #4caf50;">هیچ کالای ضررآوری یافت نشد! 🎉</p>';
        return;
    }

    let table_html = `
        <table class="table table-bordered" style="font-size: 12px;">
            <thead>
                <tr>
                    <th>کد کالا</th>
                    <th>قیمت بازار</th>
                    <th>هزینه کل</th>
                    <th>مبلغ ضرر</th>
                    <th>وضعیت</th>
                </tr>
            </thead>
            <tbody>
    `;

    loss_items.forEach(item => {
        table_html += `
            <tr style="background-color: #ffebee;">
                <td>${item.item_code || 'نامشخص'}</td>
                <td>${format_currency(item.current_market_price || 0)}</td>
                <td>${format_currency(item.total_cost || 0)}</td>
                <td style="color: #f44336;">${format_currency(Math.abs(item.profit_loss_amount || 0))}</td>
                <td><span style="color: #f44336; font-weight: bold;">ضررآور</span></td>
            </tr>
        `;
    });

    table_html += `
            </tbody>
        </table>
    `;

    document.getElementById('loss_items_table').innerHTML = table_html;
}

function render_pricing_charts(frm) {
    console.log("render_pricing_charts called");
    // Add a small chart widget to the form
    if (frm.doc.items && frm.doc.items.length > 0) {
        let wrapper = $(frm.fields_dict.items.wrapper);
        let chart_wrapper = wrapper.find('.pricing-chart-widget');

        if (chart_wrapper.length === 0) {
            chart_wrapper = $('<div class="pricing-chart-widget" style="margin: 15px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; background: #f9f9f9;"></div>');
            wrapper.prepend(chart_wrapper);
        }

        let total_cost = frm.doc.items.reduce((sum, item) => sum + (item.total_cost || 0), 0);
        let total_selling = frm.doc.items.reduce((sum, item) => sum + (item.selling_price || 0), 0);
        let total_profit = total_selling - total_cost;
        let avg_margin = total_cost > 0 ? (total_profit / total_cost) * 100 : 0;

        chart_wrapper.html(`
            <div style="display: flex; justify-content: space-between; align-items: center; direction: rtl;">
                <div>
                    <strong>خلاصه سریع:</strong>
                    <span style="margin-right: 20px;">هزینه کل: ${format_currency(total_cost)}</span>
                    <span style="margin-right: 20px;">فروش کل: ${format_currency(total_selling)}</span>
                    <span style="margin-right: 20px;">سود کل: ${format_currency(total_profit)}</span>
                    <span style="margin-right: 20px;">میانگین حاشیه: ${avg_margin.toFixed(1)}%</span>
                </div>
                <button class="btn btn-primary btn-sm" onclick="show_pricing_dashboard(cur_frm)">
                    نمایش داشبورد
                </button>
            </div>
        `);
    }
}

function format_currency(amount) {
    console.log("format_currency called with amount:", amount);
    return new Intl.NumberFormat('fa-IR', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(amount || 0);
}

function compute_new_price(prev_price, percent, rounding_amount) {
    prev_price = prev_price || 0;
    percent = percent || 0;
    rounding_amount = rounding_amount || 0;

    let increased = prev_price * (1 + (percent / 100));
    let new_price = increased;
    if (rounding_amount && rounding_amount > 0) {
        new_price = Math.ceil(increased / rounding_amount) * rounding_amount;
    }
    return Math.round(new_price);
}

/**
 * محاسبه قیمت‌ها در سمت کلاینت
 * این تابع قیمت‌ها رو بدون ارسال request به سرور محاسبه میکنه
 * تا از lock شدن دیتابیس جلوگیری بشه
 */
function recalculate_prices_client_side(frm) {
    console.log("🔄 محاسبه client-side قیمت‌ها شروع شد");

    if (!frm.doc.items || frm.doc.items.length === 0) {
        return;
    }

    const profit_margin = flt(frm.doc.profit_margin || 0);
    const commission_percentage = flt(frm.doc.commission_percentage || 0);
    const rounding_amount = flt(frm.doc.price_rounding_amount || 0);
    const target_discount = flt(frm.doc.target_discount_percentage || 0);

    // محاسبه markup اگر تخفیف هدف داریم
    let markup_percentage = 0;
    if (target_discount > 0 && target_discount < 100) {
        markup_percentage = (target_discount / (100 - target_discount)) * 100;
    }

    // پردازش مراحل قیمت‌گذاری اگر وجود داشته باشد
    const has_pricing_steps = frm.doc.pricing_steps && frm.doc.pricing_steps.length > 0;

    frm.doc.items.forEach(function (item, idx) {
        if (!item.item_code) return;

        // شروع با total_cost موجود
        let current_price = flt(item.total_cost || 0);

        if (current_price <= 0) {
            // اگر total_cost صفر است، از selling_price قبلی استفاده کن
            return;
        }

        let steps_description = [];
        steps_description.push(`قیمت تمام شده: ${format_currency_simple(current_price)}`);

        if (has_pricing_steps) {
            // پردازش با مراحل تعریف شده
            let sorted_steps = frm.doc.pricing_steps.slice().sort((a, b) => (a.step_order || 0) - (b.step_order || 0));

            sorted_steps.forEach(function (step, step_idx) {
                let step_type = get_english_type_from_persian_client(step.step_type);
                let new_price = current_price;
                let description = "";

                if (step_type === 'profit_margin' && profit_margin > 0) {
                    new_price = current_price * (1 + profit_margin / 100);
                    description = `سود ${profit_margin}%: +${format_currency_simple(new_price - current_price)}`;
                } else if (step_type === 'target_discount_percentage' && markup_percentage > 0) {
                    new_price = current_price * (1 + markup_percentage / 100);
                    description = `افزایش قیمت ${markup_percentage.toFixed(2)}%: +${format_currency_simple(new_price - current_price)}`;
                } else if (step_type === 'commission_percentage' && commission_percentage > 0) {
                    let commission_amount = current_price * (commission_percentage / 100);
                    new_price = current_price - commission_amount;
                    description = `کمیسیون ${commission_percentage}%: -${format_currency_simple(commission_amount)}`;
                } else if (step_type === 'rounding' && rounding_amount > 0) {
                    new_price = Math.ceil(current_price / rounding_amount) * rounding_amount;
                    description = `رند کردن: ${format_currency_simple(new_price)}`;
                }

                // if (description) {
                //     steps_description.push(`مرحله ${step_idx + 1}: ${description}`);
                // }
                current_price = new_price;
            });
        } else {
            // محاسبه ساده با حاشیه سود
            if (profit_margin > 0) {
                let profit_amount = current_price * (profit_margin / 100);
                current_price = current_price + profit_amount;
                // steps_description.push(`سود ${profit_margin}%: +${format_currency_simple(profit_amount)}`);
            }

            // اعمال markup
            if (markup_percentage > 0) {
                let markup_amount = current_price * (markup_percentage / 100);
                current_price = current_price + markup_amount;
                // steps_description.push(`افزایش قیمت ${markup_percentage.toFixed(2)}%: +${format_currency_simple(markup_amount)}`);
            }

            // رند کردن
            if (rounding_amount > 0) {
                current_price = Math.ceil(current_price / rounding_amount) * rounding_amount;
                // steps_description.push(`رند کردن: ${format_currency_simple(current_price)}`);
            }
        }

        // به‌روزرسانی فیلدهای آیتم
        item.selling_price = current_price;
        item.final_selected_price = current_price;
        item.profit_amount = current_price - flt(item.total_cost || 0);
        item.step_by_step_calculation = ""; // steps_description.join("\n");
    });

    // به‌روزرسانی نمایش جدول
    frm.refresh_field('items');

    console.log("✅ محاسبه client-side قیمت‌ها کامل شد");
}

/**
 * تبدیل نوع فارسی به انگلیسی برای کلاینت
 */
function get_english_type_from_persian_client(persian_type) {
    const persian_to_english = {
        'سود': 'profit_margin',
        'تخفیف': 'target_discount_percentage',
        'افزایش قیمت': 'target_discount_percentage',
        'کمیسیون': 'commission_percentage',
        'بهره قسطی': 'installment_interest',
        'بهره تأخیری': 'deferred_payment_interest',
        'رند کردن': 'rounding'
    };
    return persian_to_english[persian_type] || persian_type || 'unknown';
}

/**
 * فرمت ساده ارز برای نمایش
 */
function format_currency_simple(amount) {
    return new Intl.NumberFormat('fa-IR', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(Math.round(amount || 0));
}

// Recompute new_price for a prev_items row when user edits increase_percent or rounding_amount
frappe.ui.form.on('Auto Price List Prev Item', {
    increase_percent: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        row.new_price = compute_new_price(row.prev_price, row.increase_percent || frm.doc.prev_price_increase_percent || 0, row.rounding_amount || frm.doc.prev_price_rounding_amount || 0);
        frm.refresh_field('prev_items');
    },
    rounding_amount: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        row.new_price = compute_new_price(row.prev_price, row.increase_percent || frm.doc.prev_price_increase_percent || 0, row.rounding_amount || frm.doc.prev_price_rounding_amount || 0);
        frm.refresh_field('prev_items');
    }
});

// Function to highlight loss items in red
function highlight_loss_items(frm) {
    console.log("highlight_loss_items called");
    if (!frm.doc.items || !frm.doc.compare_with_price_list) return;

    setTimeout(() => {
        frm.doc.items.forEach((item, index) => {
            if (item.profit_loss_status === 'ضررآور') {
                let row = $(frm.fields_dict.items.grid.wrapper).find(`[data-idx="${index}"]`);
                row.css('background-color', '#ffebee');
                row.find('.grid-row-check').css('background-color', '#f44336');
            }
        });
    }, 500);
}

// Combined pricing strategies function
function show_combined_pricing_strategies(frm) {
    console.log("show_combined_pricing_strategies called", frm.doc.selected_price_type);

    if (!frm.doc.items || frm.doc.items.length === 0) {
        console.log("No items found for combined pricing");
        frappe.msgprint(__('هیچ کالایی یافت نشد. لطفاً ابتدا کالاها را اضافه کنید.'));
        return;
    }

    let dialog = new frappe.ui.Dialog({
        title: __('استراتژی‌های قیمت‌گذاری ترکیبی'),
        size: 'extra-large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'strategies_html'
            }
        ]
    });

    // Generate strategies for first item as example
    let first_item = frm.doc.items[0];
    if (first_item.selling_price && first_item.total_cost) {
        frappe.call({
            method: 'calculate_combined_pricing_strategies',
            doc: frm.doc,
            args: {
                selling_price: first_item.selling_price,
                total_cost: first_item.total_cost
            },
            callback: function (r) {
                if (r.message) {
                    console.log("Combined pricing strategies received:", r.message);
                    let strategies_html = generate_strategies_html(r.message);
                    dialog.fields_dict.strategies_html.$wrapper.html(strategies_html);
                }
            }
        });
    }

    dialog.show();
}

function generate_strategies_html(strategies) {
    console.log("generate_strategies_html called", strategies);

    let html = `
        <div style="padding: 20px; direction: rtl;">
            <h4>استراتژی‌های قیمت‌گذاری ترکیبی</h4>
            <div class="row">
    `;

    Object.entries(strategies).forEach(([key, strategy]) => {
        html += `
            <div class="col-md-4">
                <div class="card" style="padding: 15px; margin: 10px 0; border: 1px solid #ddd; border-radius: 5px;">
                    <h5>${strategy.name}</h5>
                    <p><strong>قیمت نهایی:</strong> ${format_currency(strategy.final_price)}</p>
                    <p><strong>مزیت مشتری:</strong> ${format_currency(strategy.customer_choice_benefit)}</p>
                    <p><strong>امتیاز:</strong> ${strategy.score?.toFixed(1) || 0}/100</p>
                    <button class="btn btn-primary btn-sm" onclick="apply_strategy('${key}')">
                        اعمال این استراتژی
                    </button>
                </div>
            </div>
        `;
    });

    html += `
            </div>
        </div>
    `;

    return html;
}

function apply_combined_pricing_strategies(frm) {
    console.log("apply_combined_pricing_strategies called");

    let selected_strategy = frm.doc.selected_price_type || 'combined_discount_installment';

    frappe.call({
        method: 'apply_combined_pricing_strategy',
        doc: frm.doc,
        args: {
            strategy_key: selected_strategy
        },
        callback: function (r) {
            if (r.message) {
                console.log("Combined pricing applied successfully");
                frm.reload_doc();
                frappe.show_alert({
                    message: __('استراتژی قیمت‌گذاری ترکیبی اعمال شد'),
                    indicator: 'green'
                });
            }
        }
    });
}

function compare_combined_strategies(frm) {
    console.log("compare_combined_strategies called");

    if (!frm.doc.items || frm.doc.items.length === 0) {
        frappe.msgprint(__('هیچ کالایی یافت نشد.'));
        return;
    }

    // Show comparison dialog
    let dialog = new frappe.ui.Dialog({
        title: __('مقایسه استراتژی‌های قیمت‌گذاری'),
        size: 'extra-large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'comparison_html'
            }
        ]
    });

    let comparison_html = `
        <div style="padding: 20px; direction: rtl;">
            <h4>مقایسه استراتژی‌های مختلف</h4>
            <p>این بخش امکان مقایسه استراتژی‌های مختلف قیمت‌گذاری را فراهم می‌کند.</p>
        </div>
    `;

    dialog.fields_dict.comparison_html.$wrapper.html(comparison_html);
    dialog.show();
}

// AI-powered pricing optimization
function ai_optimize_all_prices(frm) {
    console.log("ai_optimize_all_prices called");
    frappe.show_alert({
        message: __('شروع بهینه‌سازی هوشمند قیمت‌ها...'),
        indicator: 'blue'
    });

    frappe.call({
        method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.ai_optimize_all_items',
        args: {
            docname: frm.docname
        },
        callback: function (r) {
            if (r.message) {
                frm.reload_doc();
                frappe.show_alert({
                    message: __('بهینه‌سازی با موفقیت انجام شد'),
                    indicator: 'green'
                });
                show_optimization_results(r.message);
            }
        }
    });
}

function show_optimization_results(results) {
    console.log("show_optimization_results called with:", results);
    let dialog = new frappe.ui.Dialog({
        title: __('نتایج بهینه‌سازی هوشمند'),
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'results_html'
            }
        ]
    });

    let html = `
        <div style="padding: 20px; direction: rtl;">
            <h4>خلاصه بهینه‌سازی</h4>
            <div class="row">
                <div class="col-md-6">
                    <div class="card" style="padding: 15px; background: #e8f5e8; border-radius: 8px;">
                        <h5 style="color: #388e3c;">کالاهای بهینه‌سازی شده: ${results.optimized_count}</h5>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card" style="padding: 15px; background: #fff3e0; border-radius: 8px;">
                        <h5 style="color: #f57c00;">میانگین بهبود سود: ${results.avg_improvement}%</h5>
                    </div>
                </div>
            </div>
            <br>
            <table class="table table-bordered">
                <thead>
                    <tr>
                        <th>کد کالا</th>
                        <th>قیمت قبلی</th>
                        <th>قیمت بهینه</th>
                        <th>تغییر درصد</th>
                        <th>دلیل</th>
                    </tr>
                </thead>
                <tbody>`;

    results.items.forEach(item => {
        html += `
            <tr>
                <td>${item.item_code}</td>
                <td>${format_currency(item.old_price)}</td>
                <td>${format_currency(item.new_price)}</td>
                <td style="color: ${item.change > 0 ? 'green' : 'red'}">${item.change.toFixed(2)}%</td>
                <td>${item.reason}</td>
            </tr>`;
    });

    html += `
                </tbody>
            </table>
        </div>`;

    dialog.fields_dict.results_html.$wrapper.html(html);
    dialog.show();
}

// function render_bundle_items_html(frm, cdt, cdn) {
//     let row = locals[cdt][cdn];
//     if (!row.bundle_items_data) return;

//     let items = JSON.parse(row.bundle_items_data);
//     if (!items || items.length === 0) return;

//     let html = `
//         <div style="padding: 10px; background: #f9f9f9; border: 1px solid #eee; border-radius: 4px;">
//             <table class="table table-bordered table-sm" style="margin: 0; font-size: 12px;">
//                 <thead>
//                     <tr style="background: #f0f0f0;">
//                         <th>کد کالا</th>
//                         <th>نام کالا</th>
//                         <th>تعداد</th>
//                         <th>هزینه واحد</th>
//                         <th>قیمت واحد</th>
//                         <th>هزینه کل</th>
//                         <th>قیمت کل</th>
//                     </tr>
//                 </thead>
//                 <tbody>
//     `;

//     items.forEach(item => {
//         html += `
//             <tr>
//                 <td>${item.item_code}</td>
//                 <td>${item.item_name}</td>
//                 <td>${item.qty}</td>
//                 <td>${format_currency(item.unit_cost)}</td>
//                 <td>${format_currency(item.unit_selling_price)}</td>
//                 <td>${format_currency(item.total_cost)}</td>
//                 <td>${format_currency(item.total_selling_price)}</td>
//             </tr>
//         `;
//     });

//     html += `
//                 </tbody>
//             </table>
//         </div>
//     `;

//     // Update HTML field
//     frappe.model.set_value(cdt, cdn, 'bundle_items_html', html);
// }


// Cost monitoring setup
function setup_cost_monitoring(frm) {
    console.log("setup_cost_monitoring called");
    frappe.call({
        method: 'setup_cost_monitoring',
        doc: frm.doc,
        callback: function (r) {
            if (r.message && r.message.length > 0) {
                show_cost_alerts(r.message);
            } else {
                frappe.show_alert({
                    message: __('هیچ تغییر قابل توجهی در هزینه‌ها یافت نشد'),
                    indicator: 'green'
                });
            }
        }
    });
}

function show_cost_alerts(alerts) {
    console.log("show_cost_alerts called with alerts:", alerts.length);
    let dialog = new frappe.ui.Dialog({
        title: __('هشدارهای تغییر هزینه'),
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'alerts_html'
            }
        ]
    });

    let html = `
        <div style="padding: 20px; direction: rtl;">
            <h4>تغییرات قابل توجه در هزینه‌ها</h4>
            <table class="table table-bordered">
                <thead>
                    <tr>
                        <th>کد کالا</th>
                        <th>نام کالا</th>
                        <th>هزینه فعلی</th>
                        <th>هزینه قبلی</th>
                        <th>تغییر درصد</th>
                        <th>نوع تغییر</th>
                    </tr>
                </thead>
                <tbody>`;

    alerts.forEach(alert => {
        let color = alert.alert_type === 'increase' ? 'red' : 'green';
        html += `
            <tr style="background-color: ${alert.alert_type === 'increase' ? '#ffebee' : '#e8f5e8'}">
                <td>${alert.item_code}</td>
                <td>${alert.item_name}</td>
                <td>${format_currency(alert.current_cost)}</td>
                <td>${format_currency(alert.previous_cost)}</td>
                <td style="color: ${color}; font-weight: bold;">${alert.cost_change.toFixed(2)}%</td>
                <td>${alert.alert_type === 'increase' ? 'افزایش' : 'کاهش'}</td>
            </tr>`;
    });

    html += `
                </tbody>
            </table>
        </div>`;

    dialog.fields_dict.alerts_html.$wrapper.html(html);
    dialog.show();
}

// Advanced analytics rendering
function render_advanced_analytics(frm) {
    console.log("render_advanced_analytics called");
    if (!frm.doc.items || frm.doc.items.length === 0) return;

    // Add advanced analytics section
    let wrapper = $(frm.fields_dict.items.wrapper);
    let analytics_wrapper = wrapper.find('.advanced-analytics-widget');

    if (analytics_wrapper.length === 0) {
        analytics_wrapper = $('<div class="advanced-analytics-widget" style="margin: 15px 0; padding: 20px; border: 1px solid #ddd; border-radius: 8px; background: #f8f9fa;"></div>');
        wrapper.prepend(analytics_wrapper);
    }

    // Calculate advanced metrics
    let items = frm.doc.items;
    let total_items = items.length;
    let high_margin_items = items.filter(item => {
        if (item.total_cost > 0) {
            let margin = ((item.selling_price - item.total_cost) / item.total_cost) * 100;
            return margin > 30;
        }
        return false;
    }).length;

    let low_margin_items = items.filter(item => {
        if (item.total_cost > 0) {
            let margin = ((item.selling_price - item.total_cost) / item.total_cost) * 100;
            return margin < 15;
        }
        return false;
    }).length;

    let profitable_items = items.filter(item => item.profit_loss_status === 'سودآور').length;
    let loss_items = items.filter(item => item.profit_loss_status === 'ضررآور').length;

    analytics_wrapper.html(`
        <div style="direction: rtl;">
            <h4 style="margin-bottom: 20px; color: #333;">📊 تحلیل پیشرفته قیمت‌گذاری</h4>
            <div class="row">
                <div class="col-md-3">
                    <div class="metric-card" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; border-radius: 10px; text-align: center;">
                        <h3>${total_items}</h3>
                        <p>کل کالاها</p>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="metric-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 15px; border-radius: 10px; text-align: center;">
                        <h3>${high_margin_items}</h3>
                        <p>حاشیه بالا (+30%)</p>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="metric-card" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; padding: 15px; border-radius: 10px; text-align: center;">
                        <h3>${low_margin_items}</h3>
                        <p>حاشیه پایین (-15%)</p>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="metric-card" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); color: white; padding: 15px; border-radius: 10px; text-align: center;">
                        <h3>${profitable_items}/${loss_items}</h3>
                        <p>سودآور/ضررآور</p>
                    </div>
                </div>
            </div>
            <div style="margin-top: 20px; text-align: center;">
                <button class="btn btn-primary btn-sm" onclick="show_market_analysis(cur_frm)" style="margin: 5px;">📈 تحلیل بازار</button>
                <button class="btn btn-success btn-sm" onclick="show_pricing_recommendations(cur_frm)" style="margin: 5px;">💡 پیشنهادات قیمت</button>
                <button class="btn btn-info btn-sm" onclick="export_pricing_data(cur_frm)" style="margin: 5px;">📤 صادرات داده‌ها</button>
            </div>
        </div>
    `);
}

// Real-time updates setup
function setup_real_time_updates(frm) {
    console.log("setup_real_time_updates called");
    // Setup WebSocket or polling for real-time price updates
    if (frm.real_time_interval) {
        clearInterval(frm.real_time_interval);
    }

    frm.real_time_interval = setInterval(() => {
        if (frm.doc.compare_with_price_list) {
            update_market_prices(frm);
        }
    }, 300000); // Update every 5 minutes
}

function update_market_prices(frm) {
    console.log("update_market_prices called");
    frappe.call({
        method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.get_real_time_market_data',
        args: {
            docname: frm.docname,
            item_codes: frm.doc.items.map(item => item.item_code)
        },
        callback: function (r) {
            if (r.message) {
                update_market_indicators(frm, r.message);
            }
        }
    });
}

function update_market_indicators(frm, market_data) {
    console.log("update_market_indicators called with data:", market_data);
    // Update market indicators in the UI
    frm.doc.items.forEach((item, index) => {
        let market_info = market_data[item.item_code];
        if (market_info) {
            let row = $(frm.fields_dict.items.grid.wrapper).find(`[data-idx="${index}"]`);
            let trend_indicator = market_info.trend === 'increasing' ? '📈' :
                market_info.trend === 'decreasing' ? '📉' : '➡️';

            row.find('.grid-row-check').after(`<span class="market-trend" style="margin-left: 5px;">${trend_indicator}</span>`);
        }
    });
}

// Mobile-responsive design
function setup_mobile_interface(frm) {
    console.log("setup_mobile_interface called");
    // Detect mobile device
    let isMobile = window.innerWidth <= 768;

    if (isMobile) {
        // Add mobile-specific styling
        $('head').append(`
            <style>
                .mobile-pricing {
                    font-size: 14px;
                }
                .mobile-pricing .form-column {
                    width: 100% !important;
                }
                .mobile-pricing .grid-row {
                    font-size: 12px;
                }
                .mobile-pricing .btn {
                    padding: 8px 12px;
                    font-size: 12px;
                }
                @media (max-width: 768px) {
                    .form-layout {
                        padding: 10px;
                    }
                    .frappe-control {
                        margin-bottom: 15px;
                    }
                }
            </style>
        `);

        // Add mobile class
        frm.wrapper.addClass('mobile-pricing');

        // Simplify dashboard for mobile
        frm.mobile_dashboard = true;
    }
}

// Additional functions referenced in the code
function show_market_analysis(frm) {
    console.log("show_market_analysis called");
    frappe.msgprint(__('تحلیل بازار در حال توسعه است.'));
}

function show_seasonal_analysis(frm) {
    console.log("show_seasonal_analysis called");
    frappe.msgprint(__('تحلیل فصلی در حال توسعه است.'));
}

function show_ml_insights(frm) {
    console.log("show_ml_insights called");
    frappe.msgprint(__('بینش‌های ML در حال توسعه است.'));
}

function show_advanced_competitor_analysis(frm) {
    console.log("show_advanced_competitor_analysis called");
    frappe.msgprint(__('تحلیل پیشرفته رقبا در حال توسعه است.'));
}

function show_pricing_recommendations(frm) {
    console.log("show_pricing_recommendations called");
    frappe.msgprint(__('پیشنهادات قیمت‌گذاری در حال توسعه است.'));
}

function export_pricing_data(frm) {
    console.log("export_pricing_data called");
    frappe.msgprint(__('صادرات داده‌ها در حال توسعه است.'));
}

function integrate_real_purchase_data(frm) {
    frappe.confirm(
        __('این عملیات داده‌های فاکتور خرید واقعی را در محاسبات قیمت‌گذاری ادغام می‌کند. ادامه می‌دهید؟'),
        function () {
            frappe.call({
                method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.integrate_real_data_for_pricing',
                args: {
                    docname: frm.doc.name
                },
                callback: function (r) {
                    if (r.message && r.message.status === 'success') {
                        frappe.msgprint({
                            title: __('ادغام داده‌های واقعی تکمیل شد'),
                            message: r.message.message,
                            indicator: 'green'
                        });
                        frm.refresh();
                    } else {
                        frappe.msgprint({
                            title: __('ادغام ناموفق'),
                            message: r.message ? r.message.message : 'خطای ناشناخته رخ داد',
                            indicator: 'red'
                        });
                    }
                }
            });
        }
    );
}

function show_purchase_analysis(frm) {
    if (!frm.doc.items || frm.doc.items.length === 0) {
        frappe.msgprint({
            title: '📋 اطلاعات',
            message: 'ابتدا کالاها را دریافت کنید تا تحلیل خرید انجام شود.',
            indicator: 'orange'
        });
        return;
    }

    let dialog = new frappe.ui.Dialog({
        title: __('تحلیل داده‌های خرید'),
        size: 'extra-large',
        fields: [
            {
                fieldtype: 'Select',
                fieldname: 'item_code',
                label: __('انتخاب کالا'),
                options: frm.doc.items.map(item => item.item_code).join('\n'),
                reqd: 1
            },
            {
                fieldtype: 'Button',
                fieldname: 'analyze_btn',
                label: __('تحلیل داده‌های خرید')
            },
            {
                fieldtype: 'HTML',
                fieldname: 'analysis_html'
            }
        ]
    });

    dialog.fields_dict.analyze_btn.$input.click(function () {
        let item_code = dialog.get_value('item_code');
        if (!item_code) {
            frappe.msgprint(__('لطفاً یک کالا انتخاب کنید'));
            return;
        }

        frappe.call({
            method: 'get_real_purchase_costs',
            doc: frm.doc,
            args: {
                item_code: item_code
            },
            callback: function (r) {
                if (r.message) {
                    let html = generate_purchase_analysis_html(r.message);
                    dialog.fields_dict.analysis_html.$wrapper.html(html);
                } else {
                    dialog.fields_dict.analysis_html.$wrapper.html('<p>هیچ داده خریدی برای این کالا یافت نشد</p>');
                }
            }
        });
    });

    dialog.show();
}

function clean_zero_manual_prices(frm) {
    frappe.confirm(
        __('آیا می‌خواهید تمام رکورد‌هایی که همه فیلدهایشان صفر است از جدول قیمت‌های دستی حذف شوند؟'),
        function () {
            frappe.call({
                method: 'clean_zero_manual_prices',
                doc: frm.doc,
                callback: function (r) {
                    if (r.message && r.message.success) {
                        frappe.msgprint({
                            title: __('✅ تمیز کردن کامل شد'),
                            message: r.message.message,
                            indicator: 'green'
                        });
                        frm.refresh();
                    } else {
                        frappe.msgprint({
                            title: __('❌ خطا در تمیز کردن'),
                            message: r.message ? r.message.message : 'خطای ناشناخته',
                            indicator: 'red'
                        });
                    }
                }
            });
        }
    );
}

function generate_purchase_analysis_html(data) {
    let html = `
        <div class="purchase-analysis" style="padding: 15px;">
            <div class="row">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header"><h6>خلاصه خرید</h6></div>
                        <div class="card-body">
                            <table class="table table-sm">
                                <tr><td>کل خریدها:</td><td>${data.total_purchases || 0}</td></tr>
                                <tr><td>کل مقدار:</td><td>${(data.total_quantity || 0).toFixed(2)}</td></tr>
                                <tr><td>کل مبلغ:</td><td>${format_currency(data.total_amount || 0)}</td></tr>
                                <tr><td>نرخ متوسط:</td><td>${format_currency(data.average_rate || 0)}</td></tr>
                                <tr><td>آخرین نرخ:</td><td>${format_currency(data.latest_rate || 0)}</td></tr>
                            </table>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header"><h6>تغییرات قیمت</h6></div>
                        <div class="card-body">
                            <table class="table table-sm">
                                <tr><td>حداقل نرخ:</td><td>${format_currency(data.min_rate || 0)}</td></tr>
                                <tr><td>حداکثر نرخ:</td><td>${format_currency(data.max_rate || 0)}</td></tr>
                                <tr><td>تغییرات نرخ:</td><td>${(data.rate_variance || 0).toFixed(2)}%</td></tr>
                                <tr><td>تأمین‌کنندگان:</td><td>${(data.suppliers || []).length}</td></tr>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="row mt-3">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-header"><h6>خریدهای اخیر</h6></div>
                        <div class="card-body">
                            <div class="table-responsive">
                                <table class="table table-striped">
                                    <thead>
                                        <tr>
                                            <th>تاریخ</th>
                                            <th>فاکتور</th>
                                            <th>تأمین‌کننده</th>
                                            <th>نرخ</th>
                                            <th>مقدار</th>
                                            <th>مبلغ</th>
                                        </tr>
                                    </thead>
                                    <tbody>`;

    if (data.recent_purchases && data.recent_purchases.length > 0) {
        data.recent_purchases.forEach(purchase => {
            html += `
                <tr>
                    <td>${frappe.datetime.str_to_user(purchase.posting_date)}</td>
                    <td>${purchase.invoice_name}</td>
                    <td>${purchase.supplier}</td>
                    <td>${format_currency(purchase.rate)}</td>
                    <td>${purchase.qty}</td>
                    <td>${format_currency(purchase.amount)}</td>
                </tr>`;
        });
    } else {
        html += '<tr><td colspan="6" class="text-center">هیچ خرید اخیری یافت نشد</td></tr>';
    }

    html += `
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>`;

    return html;
}

function show_quotation_insights(frm) {
    console.log("show_quotation_insights called");
    frappe.msgprint(__('بینش‌های پیش‌فاکتور در حال توسعه است.'));
}

function show_volume_pricing_setup(frm) {
    console.log("show_volume_pricing_setup called");
    frappe.msgprint(__('تنظیم قیمت‌گذاری حجمی در حال توسعه است.'));
}

function show_customer_tier_setup(frm) {
    console.log("show_customer_tier_setup called");
    frappe.msgprint(__('تنظیم سطح‌بندی مشتری در حال توسعه است.'));
}

function calculate_dynamic_seasonal_factors(frm) {
    console.log("calculate_dynamic_seasonal_factors called");
    frappe.msgprint(__('محاسبه ضرایب فصلی در حال توسعه است.'));
}

function render_dashboard_charts_simple(frm) {
    // این فانکشن حذف شد - دیگر از refresh فراخوانی نمیشه
    // فقط به صورت دستی از دیالوگ فراخوانی میشه
}

// Volume pricing setup dialog
function show_volume_pricing_setup(frm) {
    console.log("show_volume_pricing_setup called");
    let dialog = new frappe.ui.Dialog({
        title: __('تنظیم قیمت‌گذاری حجمی'),
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'volume_setup_html',
                options: `
                    <div style="padding: 20px; direction: rtl;">
                        <p>قیمت‌گذاری حجمی به شما امکان ارائه تخفیف بر اساس مقدار خرید را می‌دهد.</p>
                        <p>برای فعال‌سازی کامل، سطوح تخفیف را در جدول "سطوح قیمت‌گذاری حجمی" تعریف کنید.</p>
                        <div class="alert alert-info">
                            <strong>نکته:</strong> این تنظیمات در Sales Order و Quotation نیز اعمال خواهد شد.
                        </div>
                    </div>
                `
            }
        ]
    });
    dialog.show();
}

// Customer tier setup dialog
function show_customer_tier_setup(frm) {
    console.log("show_customer_tier_setup called");
    let dialog = new frappe.ui.Dialog({
        title: __('تنظیم قیمت‌گذاری سطح مشتری'),
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'tier_setup_html',
                options: `
                    <div style="padding: 20px; direction: rtl;">
                        <p>سیستم به طور خودکار سطح مشتریان را بر اساس تاریخچه خرید تعیین می‌کند:</p>
                        <ul>
                            <li><strong>VIP:</strong> بیش از 1 میلیارد تومان خرید و 50+ سفارش</li>
                            <li><strong>عمده‌فروش:</strong> بیش از 500 میلیون تومان خرید و 20+ سفارش</li>
                            <li><strong>عادی:</strong> بیش از 100 میلیون تومان خرید یا 10+ سفارش</li>
                            <li><strong>جدید:</strong> سایر مشتریان</li>
                        </ul>
                        <div class="alert alert-success">
                            <strong>مزیت:</strong> تخفیفات به طور خودکار بر اساس وفاداری مشتری اعمال می‌شود.
                        </div>
                    </div>
                `
            }
        ]
    });
    dialog.show();
}

// Dynamic seasonal factors calculation
function calculate_dynamic_seasonal_factors(frm) {
    console.log("calculate_dynamic_seasonal_factors called");
    frappe.call({
        method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.calculate_all_seasonal_factors',
        args: {
            docname: frm.docname
        },
        callback: function (r) {
            if (r.message) {
                show_seasonal_analysis(r.message);
            }
        }
    });
}

function show_seasonal_analysis(seasonal_data) {
    console.log("show_seasonal_analysis called with data:", seasonal_data);
    let dialog = new frappe.ui.Dialog({
        title: __('تحلیل فصلی قیمت‌گذاری'),
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'seasonal_html'
            }
        ]
    });

    let html = `
        <div style="padding: 20px; direction: rtl;">
            <h4>ضرایب فصلی محاسبه شده</h4>
            <table class="table table-bordered">
                <thead>
                    <tr>
                        <th>کد کالا</th>
                        <th>ضریب فصلی</th>
                        <th>توصیه</th>
                        <th>دلیل</th>
                    </tr>
                </thead>
                <tbody>`;

    seasonal_data.forEach(item => {
        let recommendation = item.factor > 10 ? 'افزایش قیمت' :
            item.factor < -10 ? 'کاهش قیمت' : 'بدون تغییر';
        html += `
            <tr>
                <td>${item.item_code}</td>
                <td style="color: ${item.factor > 0 ? 'green' : 'red'}">${item.factor.toFixed(2)}%</td>
                <td>${recommendation}</td>
                <td>${item.reason}</td>
            </tr>`;
    });

    html += `
                </tbody>
            </table>
        </div>`;

    dialog.fields_dict.seasonal_html.$wrapper.html(html);
    dialog.show();
}

// Advanced AI/ML Functions

// Machine Learning Insights
function show_ml_insights(frm) {
    frappe.call({
        method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.get_ml_pricing_insights',
        args: {
            docname: frm.docname
        },
        callback: function (r) {
            if (r.message) {
                display_ml_insights_dialog(r.message);
            }
        }
    });
}

function display_ml_insights_dialog(insights) {
    console.log("display_ml_insights_dialog called with insights:", insights);
    let dialog = new frappe.ui.Dialog({
        title: __('بینش‌های یادگیری ماشین'),
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'ml_insights_html'
            }
        ]
    });

    let status_color = insights.ml_available ? 'green' : 'red';
    let html = `
        <div style="padding: 20px; direction: rtl;">
            <h4>وضعیت کتابخانه‌های یادگیری ماشین</h4>
            <div class="row">
                <div class="col-md-6">
                    <div class="card" style="padding: 15px; background: ${insights.ml_available ? '#e8f5e8' : '#ffebee'}; border-radius: 8px;">
                        <h5 style="color: ${status_color};">Machine Learning: ${insights.ml_available ? '✅ فعال' : '❌ غیرفعال'}</h5>
                        <p>XGBoost: ${insights.xgboost_available ? '✅' : '❌'}</p>
                        <p>SciPy: ${insights.scipy_available ? '✅' : '❌'}</p>
                        <p>Statsmodels: ${insights.statsmodels_available ? '✅' : '❌'}</p>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card" style="padding: 15px; background: #f3e5f5; border-radius: 8px;">
                        <h5 style="color: #7b1fa2;">کالاهای آماده ML: ${insights.items_with_sufficient_data || 0}</h5>
                        <p>${insights.overall_recommendation}</p>
                    </div>
                </div>
            </div>`;

    if (insights.items_suitable_for_ml && insights.items_suitable_for_ml.length > 0) {
        html += `
            <br>
            <h4>کالاهای آماده یادگیری ماشین</h4>
            <table class="table table-bordered">
                <thead>
                    <tr>
                        <th>کد کالا</th>
                        <th>نقاط داده</th>
                        <th>قیمت فعلی</th>
                        <th>هزینه</th>
                        <th>وضعیت ML</th>
                    </tr>
                </thead>
                <tbody>`;

        insights.items_suitable_for_ml.forEach(item => {
            html += `
                <tr>
                    <td>${item.item_code}</td>
                    <td>${item.data_points}</td>
                    <td>${format_currency(item.current_price)}</td>
                    <td>${format_currency(item.cost)}</td>
                    <td><span style="color: green;">✅ آماده</span></td>
                </tr>`;
        });

        html += `</tbody></table>`;
    }

    if (!insights.ml_available) {
        html += `
            <div class="alert alert-warning">
                <strong>نصب کتابخانه‌های مورد نیاز:</strong><br>
                <code>pip install scikit-learn pandas numpy xgboost scipy statsmodels</code>
            </div>`;
    }

    html += `</div>`;

    dialog.fields_dict.ml_insights_html.$wrapper.html(html);
    dialog.show();
}

// Demand Forecasting
function show_demand_forecast(frm, item_code) {
    console.log("show_demand_forecast called for item:", item_code);
    frappe.call({
        method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.get_demand_forecast',
        args: {
            docname: frm.docname,
            item_code: item_code,
            periods: 12
        },
        callback: function (r) {
            if (r.message) {
                display_demand_forecast_dialog(item_code, r.message);
            }
        }
    });
}

function display_demand_forecast_dialog(item_code, forecast_data) {
    console.log("display_demand_forecast_dialog called for item:", item_code, "with data:", forecast_data);
    let dialog = new frappe.ui.Dialog({
        title: __(`پیش‌بینی تقاضا - ${item_code}`),
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'forecast_html'
            }
        ]
    });

    let html = `
        <div style="padding: 20px; direction: rtl;">
            <h4>پیش‌بینی تقاضای 12 ماهه</h4>
            <p><strong>روش محاسبه:</strong> ${forecast_data.method}</p>
            <div id="forecast_chart" style="height: 300px; margin: 20px 0;"></div>
            <table class="table table-bordered">
                <thead>
                    <tr>
                        <th>ماه</th>
                        <th>پیش‌بینی تقاضا</th>
                        <th>توصیه</th>
                    </tr>
                </thead>
                <tbody>`;

    forecast_data.forecast.forEach((value, index) => {
        let month = new Date();
        month.setMonth(month.getMonth() + index);
        let monthName = month.toLocaleDateString('fa-IR', { month: 'long' });

        let recommendation = value > 100 ? 'تقاضای بالا - افزایش موجودی' :
            value > 50 ? 'تقاضای متوسط' : 'تقاضای پایین - کاهش موجودی';

        html += `
            <tr>
                <td>${monthName}</td>
                <td>${Math.round(value)}</td>
                <td>${recommendation}</td>
            </tr>`;
    });

    html += `</tbody></table></div>`;

    dialog.fields_dict.forecast_html.$wrapper.html(html);

    // Simple chart rendering
    setTimeout(() => {
        render_forecast_chart(forecast_data.forecast);
    }, 500);

    dialog.show();
}

function render_forecast_chart(forecast) {
    console.log("render_forecast_chart called with forecast data:", forecast);
    let chart_html = `<div style="display: flex; align-items: end; height: 200px; gap: 5px; padding: 20px; border: 1px solid #ddd; border-radius: 5px;">`;
    let max_value = Math.max(...forecast);

    forecast.forEach((value, index) => {
        let height = max_value > 0 ? (value / max_value * 180) : 0;
        let month = new Date();
        month.setMonth(month.getMonth() + index);
        let monthName = month.toLocaleDateString('fa-IR', { month: 'short' });

        chart_html += `
            <div style="text-align: center; flex: 1;">
                <div style="background: linear-gradient(to top, #4ecdc4, #44a08d); height: ${height}px; margin-bottom: 5px; border-radius: 3px;"></div>
                <div style="font-size: 10px; transform: rotate(-45deg);">${monthName}</div>
                <div style="font-size: 8px; color: #666;">${Math.round(value)}</div>
            </div>`;
    });

    chart_html += `</div>`;
    document.getElementById('forecast_chart').innerHTML = chart_html;
}

// Inventory Optimization
function show_inventory_optimization(frm, item_code) {
    console.log("show_inventory_optimization called for item:", item_code);
    frappe.call({
        method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.get_inventory_optimization',
        args: {
            docname: frm.docname,
            item_code: item_code
        },
        callback: function (r) {
            if (r.message) {
                display_inventory_optimization_dialog(item_code, r.message);
            }
        }
    });
}

function display_inventory_optimization_dialog(item_code, inventory_data) {
    console.log("display_inventory_optimization_dialog called for item:", item_code, "with data:", inventory_data);
    let dialog = new frappe.ui.Dialog({
        title: __(`بهینه‌سازی موجودی - ${item_code}`),
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'inventory_html'
            }
        ]
    });

    let html = `
        <div style="padding: 20px; direction: rtl;">
            <h4>تحلیل موجودی و پیشنهادات</h4>
            <div class="row">
                <div class="col-md-6">
                    <div class="card" style="padding: 15px; background: #e3f2fd; border-radius: 8px;">
                        <h5>موجودی فعلی</h5>
                        <h3 style="color: #1976d2;">${Math.round(inventory_data.current_stock || 0)}</h3>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card" style="padding: 15px; background: #fff3e0; border-radius: 8px;">
                        <h5>نقطه سفارش مجدد</h5>
                        <h3 style="color: #f57c00;">${Math.round(inventory_data.reorder_point || 0)}</h3>
                    </div>
                </div>
            </div>
            <br>
            <div class="row">
                <div class="col-md-6">
                    <div class="card" style="padding: 15px; background: #e8f5e8; border-radius: 8px;">
                        <h5>موجودی ایمنی</h5>
                        <h3 style="color: #388e3c;">${Math.round(inventory_data.safety_stock || 0)}</h3>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card" style="padding: 15px; background: #f3e5f5; border-radius: 8px;">
                        <h5>مقدار سفارش اقتصادی</h5>
                        <h3 style="color: #7b1fa2;">${Math.round(inventory_data.economic_order_qty || 0)}</h3>
                    </div>
                </div>
            </div>
            <br>
            <div class="alert alert-info">
                <strong>توصیه:</strong> ${inventory_data.recommended_action || 'داده کافی موجود نیست'}
            </div>
        </div>`;

    dialog.fields_dict.inventory_html.$wrapper.html(html);
    dialog.show();
}

// Price Elasticity Analysis
function show_price_elasticity_analysis(frm, item_code) {
    console.log("show_price_elasticity_analysis called for item:", item_code);
    frappe.call({
        method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.run_price_elasticity_analysis',
        args: {
            docname: frm.docname,
            item_code: item_code
        },
        callback: function (r) {
            if (r.message) {
                display_price_elasticity_dialog(r.message);
            }
        }
    });
}

function display_price_elasticity_dialog(elasticity_data) {
    console.log("display_price_elasticity_dialog called with data:", elasticity_data);
    let dialog = new frappe.ui.Dialog({
        title: __(`تحلیل کشش قیمت - ${elasticity_data.item_code}`),
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'elasticity_html'
            }
        ]
    });

    let elasticity_color = elasticity_data.category === 'elastic' ? '#f44336' :
        elasticity_data.category === 'inelastic' ? '#4caf50' : '#ff9800';

    let html = `
        <div style="padding: 20px; direction: rtl;">
            <h4>نتایج تحلیل کشش قیمت</h4>
            <div class="row">
                <div class="col-md-6">
                    <div class="card" style="padding: 20px; background: ${elasticity_color}20; border-radius: 8px; border-left: 4px solid ${elasticity_color};">
                        <h5>ضریب کشش قیمت</h5>
                        <h2 style="color: ${elasticity_color};">${elasticity_data.elasticity.toFixed(3)}</h2>
                        <p><strong>تفسیر:</strong> ${elasticity_data.interpretation}</p>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card" style="padding: 20px; background: #e8f5e8; border-radius: 8px;">
                        <h5>پیشنهاد استراتژیک</h5>
                        <p style="font-size: 16px; margin-top: 20px;">${elasticity_data.recommendation}</p>
                    </div>
                </div>
            </div>
            <br>
            <div class="alert alert-info">
                <h5>راهنمای تفسیر:</h5>
                <ul>
                    <li><strong>کشش‌پذیر (|E| > 1):</strong> تغییر قیمت تأثیر زیادی بر تقاضا دارد</li>
                    <li><strong>غیرکشش‌پذیر (|E| < 1):</strong> تغییر قیمت تأثیر کمی بر تقاضا دارد</li>
                    <li><strong>کشش واحد (|E| = 1):</strong> تغییر قیمت و تقاضا متناسب است</li>
                </ul>
            </div>
        </div>`;

    dialog.fields_dict.elasticity_html.$wrapper.html(html);
    dialog.show();
}

// Advanced Competitor Analysis
function show_advanced_competitor_analysis(frm) {
    frappe.call({
        method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.get_advanced_competitor_analysis',
        args: {
            docname: frm.docname
        },
        callback: function (r) {
            if (r.message) {
                display_advanced_competitor_dialog(r.message);
            }
        }
    });
}

// Function to setup Persian translations for select fields
function setup_persian_select_translations(frm) {
    const persian_labels = {
        'base_price': 'قیمت پایه',
        'discount_only': 'فقط تخفیف',
        'installment_only': 'فقط قسطی',
        'combined_discount_installment': 'ترکیبی تخفیف و قسطی'
    };

    // Simple direct DOM manipulation approach
    setTimeout(() => {
        if (frm.fields_dict.selected_price_type) {
            const $select = frm.fields_dict.selected_price_type.$input;

            // Update option text to Persian
            $select.find('option').each(function () {
                const value = $(this).val();
                if (persian_labels[value]) {
                    $(this).text(persian_labels[value]);
                }
            });
        }
    }, 500);

    // Re-apply translations after any form refresh
    if (frm.fields_dict.selected_price_type && frm.fields_dict.selected_price_type.$input) {
        frm.fields_dict.selected_price_type.$input.on('DOMSubtreeModified change', function () {
            setTimeout(() => {
                $(this).find('option').each(function () {
                    const value = $(this).val();
                    if (persian_labels[value]) {
                        $(this).text(persian_labels[value]);
                    }
                });
            }, 100);
        });
    }
}

// Function to show strategy comparison dialog
function show_strategy_comparison_dialog(comparison_data) {
    console.log("Showing strategy comparison dialog", comparison_data);
    let dialog = new frappe.ui.Dialog({
        title: __('مقایسه استراتژی‌ها'),
        size: 'extra-large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'strategy_html'
            }
        ]
    });

    let html = `
        <div style="padding: 20px; direction: rtl;">
            <h4>تحلیل آماری موقعیت بازار</h4>
            <table class="table table-bordered">
                <thead>
                    <tr>
                        <th>کد کالا</th>
                        <th>قیمت ما</th>
                        <th>میانگین بازار</th>
                        <th>میانه بازار</th>
                        <th>انحراف معیار</th>
                        <th>Z-Score</th>
                        <th>موقعیت</th>
                        <th>تعداد رقبا</th>
                    </tr>
                </thead>
                <tbody>`;

    competitor_data.forEach(item => {
        let position_color = item.position === 'بسیار رقابتی' ? '#4caf50' :
            item.position === 'رقابتی' ? '#8bc34a' :
                item.position === 'متوسط' ? '#ff9800' :
                    item.position === 'گران' ? '#ff5722' : '#f44336';

        html += `
            <tr>
                <td>${item.item_code}</td>
                <td>${format_currency(item.our_price)}</td>
                <td>${format_currency(item.market_mean)}</td>
                <td>${format_currency(item.market_median)}</td>
                <td>${format_currency(item.market_std)}</td>
                <td style="color: ${item.z_score < 0 ? 'green' : 'red'}">${item.z_score.toFixed(2)}</td>
                <td><span style="color: ${position_color}; font-weight: bold;">${item.position}</span></td>
                <td>${item.competitor_count}</td>
            </tr>`;
    });

    html += `</tbody></table></div>`;

    dialog.fields_dict.competitor_html.$wrapper.html(html);
    dialog.show();
}

// Enhanced analytics with AI features
function show_market_analysis(frm) {
    let dialog = new frappe.ui.Dialog({
        title: __('تحلیل بازار و هوش مصنوعی'),
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'market_analysis_html',
                options: `
                    <div style="padding: 20px; direction: rtl;">
                        <h4>ابزارهای تحلیل پیشرفته</h4>
                        <div class="row">
                            <div class="col-md-6">
                                <button class="btn btn-primary btn-block" onclick="show_ml_insights(cur_frm)">
                                    🤖 بینش‌های یادگیری ماشین
                                </button>
                            </div>
                            <div class="col-md-6">
                                <button class="btn btn-success btn-block" onclick="show_advanced_competitor_analysis(cur_frm)">
                                    📊 تحلیل پیشرفته رقبا
                                </button>
                            </div>
                        </div>
                        <br>
                        <div class="row">
                            <div class="col-md-12">
                                <h5>تحلیل کالای خاص:</h5>
                                <div class="form-group">
                                    <input type="text" id="analysis_item_code" class="form-control" placeholder="کد کالا را وارد کنید">
                                </div>
                                <div class="btn-group" style="width: 100%;">
                                    <button class="btn btn-info" onclick="analyze_specific_item('forecast')">📈 پیش‌بینی تقاضا</button>
                                    <button class="btn btn-warning" onclick="analyze_specific_item('inventory')">📦 بهینه‌سازی موجودی</button>
                                    <button class="btn btn-danger" onclick="analyze_specific_item('elasticity')">📉 کشش قیمت</button>
                                </div>
                            </div>
                        </div>
                    </div>
                `
            }
        ]
    });
    dialog.show();
}

function analyze_specific_item(analysis_type) {
    console.log("analyze_specific_item called with type:", analysis_type);
    let item_code = document.getElementById('analysis_item_code').value;
    if (!item_code) {
        frappe.msgprint('لطفاً کد کالا را وارد کنید');
        return;
    }

    switch (analysis_type) {
        case 'forecast':
            show_demand_forecast(cur_frm, item_code);
            break;
        case 'inventory':
            show_inventory_optimization(cur_frm, item_code);
            break;
        case 'elasticity':
            show_price_elasticity_analysis(cur_frm, item_code);
            break;
    }
}

function show_pricing_recommendations(frm) {
    frappe.msgprint({
        title: __('پیشنهادات قیمت‌گذاری هوشمند'),
        message: `
            <div style="direction: rtl;">
                <h5>🎯 استراتژی‌های پیشنهادی:</h5>
                <ul>
                    <li><strong>بهینه‌سازی ML:</strong> استفاده از یادگیری ماشین برای قیمت‌گذاری دقیق</li>
                    <li><strong>تحلیل کشش:</strong> بررسی حساسیت مشتریان به تغییرات قیمت</li>
                    <li><strong>پیش‌بینی تقاضا:</strong> برنامه‌ریزی موجودی بر اساس پیش‌بینی</li>
                    <li><strong>قیمت‌گذاری پویا:</strong> تنظیم خودکار قیمت‌ها بر اساس شرایط بازار</li>
                </ul>
                <div class="alert alert-success">
                    <strong>نکته:</strong> برای بهترین نتایج، از تمام ابزارهای هوش مصنوعی موجود استفاده کنید.
                </div>
            </div>
        `,
        indicator: 'blue'
    });
}

function export_pricing_data(frm) {
    console.log("export_pricing_data called");
    // Export comprehensive pricing data
    let export_data = {
        price_list: frm.doc.name,
        items: frm.doc.items,
        summary: {
            total_items: frm.doc.items.length,
            total_cost: frm.doc.items.reduce((sum, item) => sum + (item.total_cost || 0), 0),
            total_revenue: frm.doc.items.reduce((sum, item) => sum + (item.selling_price || 0), 0)
        },
        export_date: new Date().toISOString()
    };

    // Create downloadable file
    let dataStr = JSON.stringify(export_data, null, 2);
    let dataBlob = new Blob([dataStr], { type: 'application/json' });
    let url = URL.createObjectURL(dataBlob);
    let link = document.createElement('a');
    link.href = url;
    link.download = `pricing_data_${frm.doc.name}_${new Date().toISOString().split('T')[0]}.json`;
    link.click();

    frappe.show_alert({
        message: __('داده‌های قیمت‌گذاری صادر شد'),
        indicator: 'green'
    });
}

// Simple HTML/CSS chart functions - no external dependencies
function render_simple_pie_chart(container_id, data, title) {
    console.log("render_simple_pie_chart called for container:", container_id);
    const container = document.getElementById(container_id);
    if (!container) return;

    const total = data.reduce((sum, item) => sum + item.value, 0);
    let cumulativePercentage = 0;

    let html = `
        <div style="text-align: center; margin-bottom: 15px;">
            <h5>${title}</h5>
        </div>
        <div style="display: flex; justify-content: center; margin-bottom: 20px;">
            <div style="width: 200px; height: 200px; border-radius: 50%; background: conic-gradient(`;

    data.forEach((item, index) => {
        const percentage = (item.value / total) * 100;
        const colors = ['#4CAF50', '#FF9800', '#2196F3', '#F44336', '#9C27B0', '#00BCD4'];
        const color = colors[index % colors.length];

        html += `${color} ${cumulativePercentage}% ${cumulativePercentage + percentage}%`;
        if (index < data.length - 1) html += ', ';

        cumulativePercentage += percentage;
    });

    html += `); position: relative;">
                <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); 
                           background: white; width: 100px; height: 100px; border-radius: 50%; 
                           display: flex; align-items: center; justify-content: center; font-weight: bold;">
                    ${format_currency_safe(total)}
                </div>
            </div>
        </div>
        <div style="display: flex; flex-wrap: wrap; justify-content: center; gap: 10px;">`;

    data.forEach((item, index) => {
        const colors = ['#4CAF50', '#FF9800', '#2196F3', '#F44336', '#9C27B0', '#00BCD4'];
        const color = colors[index % colors.length];
        const percentage = ((item.value / total) * 100).toFixed(1);

        html += `
            <div style="display: flex; align-items: center; gap: 5px;">
                <div style="width: 12px; height: 12px; background: ${color}; border-radius: 2px;"></div>
                <span style="font-size: 12px;">${item.label}: ${percentage}%</span>
            </div>`;
    });

    html += `</div>`;
    container.innerHTML = html;
}

function render_simple_bar_chart(container_id, data, title) {
    console.log("render_simple_bar_chart called for container:", container_id);
    const container = document.getElementById(container_id);
    if (!container) return;

    const maxValue = Math.max(...data.map(item => item.value));

    let html = `
        <div style="text-align: center; margin-bottom: 15px;">
            <h5>${title}</h5>
        </div>
        <div style="padding: 20px;">`;

    data.forEach((item, index) => {
        const percentage = (item.value / maxValue) * 100;
        const colors = ['#4CAF50', '#FF9800', '#2196F3', '#F44336', '#9C27B0', '#00BCD4'];
        const color = colors[index % colors.length];

        html += `
            <div style="margin-bottom: 15px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                    <span style="font-size: 12px; font-weight: bold;">${item.label}</span>
                    <span style="font-size: 12px;">${format_currency(item.value)}</span>
                </div>
                <div style="background: #f0f0f0; height: 20px; border-radius: 10px; overflow: hidden;">
                    <div style="background: ${color}; height: 100%; width: ${percentage}%; 
                               border-radius: 10px; transition: width 0.3s ease;"></div>
                </div>
            </div>`;
    });

    html += `</div>`;
    container.innerHTML = html;
}

// Simple dashboard charts without external dependencies
function render_cost_breakdown_chart(frm) {
    if (!frm.doc.items || frm.doc.items.length === 0) {
        return;
    }

    const items = frm.doc.items;

    // محاسبه مقادیر با validation برای جلوگیری از مقادیر منفی
    const total_raw_material = Math.max(0, items.reduce((sum, item) => sum + (item.raw_material_cost || 0), 0));
    const total_electricity = Math.max(0, items.reduce((sum, item) => sum + (item.electricity_cost || 0), 0));
    const total_consumable = Math.max(0, items.reduce((sum, item) => sum + (item.consumable_cost || 0), 0));
    const total_rent = Math.max(0, items.reduce((sum, item) => sum + (item.rent_cost || 0), 0));
    const total_labor = Math.max(0, items.reduce((sum, item) => sum + (item.labor_cost || 0), 0));
    const total_operation = Math.max(0, items.reduce((sum, item) => sum + (item.operation_cost || 0), 0));
    const total_overhead = Math.max(0, items.reduce((sum, item) => sum + (item.overhead_cost || 0), 0));

    let cost_data = [];
    if (total_raw_material > 0) cost_data.push({ label: 'مواد اولیه', value: total_raw_material });
    if (total_electricity > 0) cost_data.push({ label: 'برق', value: total_electricity });
    if (total_consumable > 0) cost_data.push({ label: 'مصرفی', value: total_consumable });
    if (total_rent > 0) cost_data.push({ label: 'اجاره', value: total_rent });
    if (total_labor > 0) cost_data.push({ label: 'نیروی کار', value: total_labor });
    if (total_operation > 0) cost_data.push({ label: 'عملیات', value: total_operation });
    if (total_overhead > 0) cost_data.push({ label: 'سربار', value: total_overhead });

    // Render cost breakdown pie chart
    if (cost_data.length > 0) {
        render_simple_pie_chart('cost_breakdown_chart', cost_data, 'توزیع هزینه‌ها');
    }

    // Prepare profit margin data
    let margin_data = [];
    let high_margin = frm.doc.items.filter(item => (item.profit_margin || 0) > 30).length;
    let medium_margin = frm.doc.items.filter(item => (item.profit_margin || 0) >= 15 && (item.profit_margin || 0) <= 30).length;
    let low_margin = frm.doc.items.filter(item => (item.profit_margin || 0) < 15).length;

    if (high_margin > 0) margin_data.push({ label: 'حاشیه بالا (>30%)', value: high_margin });
    if (medium_margin > 0) margin_data.push({ label: 'حاشیه متوسط (15-30%)', value: medium_margin });
    if (low_margin > 0) margin_data.push({ label: 'حاشیه پایین (<15%)', value: low_margin });

    // Render profit margin bar chart
    if (margin_data.length > 0) {
        render_simple_bar_chart('profit_margin_chart', margin_data, 'توزیع حاشیه سود');
    }

    // Top profitable items
    let sorted_items = frm.doc.items
        .filter(item => (item.profit_margin || 0) > 0)
        .sort((a, b) => (b.profit_margin || 0) - (a.profit_margin || 0))
        .slice(0, 5);

    let top_items_data = sorted_items.map(item => ({
        label: item.item_code || 'نامشخص',
        value: item.profit_margin || 0
    }));

    if (top_items_data.length > 0) {
        render_simple_bar_chart('top_items_chart', top_items_data, 'پرسودترین کالاها (%)');
    }
}

// Combined Pricing Strategy Functions
function show_combined_pricing_strategies(frm) {
    console.log("show_combined_pricing_strategies called (final version)");
    if (!frm.doc.items || frm.doc.items.length === 0) {
        frappe.msgprint(__('هیچ کالایی یافت نشد. لطفاً ابتدا کالاها را اضافه کنید.'));
        return;
    }

    let dialog = new frappe.ui.Dialog({
        title: __('استراتژی‌های قیمت‌گذاری ترکیبی'),
        size: 'extra-large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'strategies_html'
            },
            {
                fieldtype: 'Section Break'
            },
            {
                fieldtype: 'Select',
                fieldname: 'strategy_selection',
                label: __('انتخاب استراتژی'),
                options: [
                    '',
                    'discount_first\nتخفیف ابتدا، سپس قسط',
                    'markup_discount_installment\nافزایش قیمت + تخفیف + قسط',
                    'interest_equivalent_discount\nتخفیف معادل بهره برای پرداخت نقدی'
                ]
            },
            {
                fieldtype: 'Button',
                fieldname: 'apply_strategy',
                label: __('اعمال استراتژی انتخابی')
            }
        ]
    });

    // Generate strategies HTML for the first item as example
    let sample_item = frm.doc.items[0];
    if (sample_item.selling_price && sample_item.total_cost) {
        frappe.call({
            method: 'calculate_combined_pricing_strategies',
            doc: frm.doc,
            args: {
                selling_price: sample_item.selling_price,
                total_cost: sample_item.total_cost
            },
            callback: function (r) {
                if (r.message) {
                    let strategies_html = generate_strategies_html(r.message, sample_item);
                    dialog.fields_dict.strategies_html.$wrapper.html(strategies_html);
                }
            }
        });
    }

    dialog.fields_dict.apply_strategy.$input.click(function () {
        let selected_strategy = dialog.get_value('strategy_selection');
        if (selected_strategy) {
            let strategy_key = selected_strategy.split('\n')[0];
            frappe.call({
                method: 'apply_combined_pricing_strategy',
                doc: frm.doc,
                args: {
                    strategy_key: strategy_key
                },
                callback: function (r) {
                    if (r.message && r.message.status === 'success') {
                        frappe.msgprint(r.message.message);
                        frm.reload_doc();
                    }
                }
            });
            dialog.hide();
        } else {
            frappe.msgprint(__('لطفاً یک استراتژی انتخاب کنید'));
        }
    });

    dialog.show();
}

function show_detailed_pricing_breakdown(frm) {
    if (!frm.doc.items || frm.doc.items.length === 0) {
        frappe.msgprint(__('هیچ کالایی یافت نشد. لطفاً ابتدا کالاها را اضافه کنید.'));
        return;
    }

    let dialog = new frappe.ui.Dialog({
        title: __('🔄 جزئیات قیمت‌گذاری داینامیک'),
        size: 'extra-large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'breakdown_html'
            }
        ]
    });

    // Generate dynamic breakdown HTML for all items
    let breakdown_html = generate_dynamic_pricing_breakdown_html(frm);
    dialog.fields_dict.breakdown_html.$wrapper.html(breakdown_html);

    dialog.show();
}

function generate_dynamic_pricing_breakdown_html(frm) {
    let items = frm.doc.items || [];
    let html = `
        <div class="pricing-breakdown-container" style="direction: rtl; font-family: 'Vazir', Arial, sans-serif;">
            <div class="row">
                <div class="col-md-12">
                    <h4>🔄 تفکیک جزئیات قیمت‌گذاری داینامیک</h4>
                    <p>استراتژی انتخاب شده: <strong>${get_persian_strategy_name(frm.doc.selected_price_type)}</strong></p>
                    <div style="background: #e3f2fd; padding: 10px; border-radius: 5px; margin: 10px 0;">
                        <strong>💡 سیستم داینامیک:</strong> هر مرحله روی نتیجه مرحله قبلی اعمال می‌شود تا قیمت نهایی محاسبه شود.
                    </div>
                </div>
            </div>
    `;

    items.forEach((item, index) => {
        let breakdown = {};
        try {
            breakdown = item.pricing_breakdown ? JSON.parse(item.pricing_breakdown) : {};
        } catch (e) {
            breakdown = {};
        }

        html += `
            <div class="card mb-3">
                <div class="card-header">
                    <h5>${item.item_code} - ${item.item_name || ''}</h5>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-6">
                            <h6>اطلاعات پایه</h6>
                            <table class="table table-sm">
                                <tr><td>هزینه کل:</td><td>${format_currency(item.total_cost || 0)}</td></tr>
                                <tr><td>قیمت فروش پایه:</td><td>${format_currency(item.selling_price || 0)}</td></tr>
                                <tr><td>سود پایه:</td><td>${format_currency(item.profit_amount || 0)}</td></tr>
                            </table>
                        </div>
                        <div class="col-md-6">
                            <h6>قیمت نهایی</h6>
                            <table class="table table-sm">
                                <tr><td>قیمت نهایی انتخاب شده:</td><td><strong>${format_currency(item.final_selected_price || 0)}</strong></td></tr>
                                <tr><td>وضعیت سود/ضرر:</td><td>${item.profit_loss_status || 'نامشخص'}</td></tr>
                                <tr><td>مبلغ سود/ضرر:</td><td>${format_currency(item.profit_loss_amount || 0)}</td></tr>
                            </table>
                        </div>
                    </div>
                    
                    <!-- تفکیک دقیق مبالغ اضافه شده -->
                    <div class="row mt-3">
                        <div class="col-md-12">
                            <h6>🔍 تفکیک دقیق مبالغ اضافه شده</h6>
                            <div class="alert alert-info" style="background: linear-gradient(135deg, #e3f2fd 0%, #f3e5f5 100%); border: none;">
                                <table class="table table-sm mb-0">
                                    <tr><td><strong>مبلغ پایه (هزینه کل):</strong></td><td>${format_currency(item.base_cost_amount || item.total_cost || 0)}</td></tr>
                                    <tr><td><strong>+ مبلغ سود اضافه شده:</strong></td><td class="text-success">+${format_currency(item.profit_added_amount || 0)}</td></tr>
                                    <tr><td><strong>+ مبلغ بهره اضافه شده:</strong></td><td class="text-info">+${format_currency(item.interest_added_amount || 0)}</td></tr>
                                    <tr><td><strong>- مبلغ کسر کمیسیون:</strong></td><td class="text-warning">-${format_currency(item.commission_deduction_amount || 0)}</td></tr>
                                    <tr><td><strong>+ مبلغ افزایش برای تخفیف:</strong></td><td class="text-primary">+${format_currency(item.markup_added_amount || 0)}</td></tr>
                                    <tr><td><strong>+ مبلغ تعدیل رند کردن:</strong></td><td class="text-secondary">+${format_currency(item.rounding_adjustment_amount || 0)}</td></tr>
                                </table>
                            </div>
                        </div>
                    </div>
                    
                    <!-- محاسبه مرحله‌ای داینامیک -->
                    ${item.step_by_step_calculation ? `
                    <div class="row mt-3">
                        <div class="col-md-12">
                            <h6>🔄 محاسبه مرحله‌ای داینامیک</h6>
                            <div class="alert alert-success" style="background: linear-gradient(135deg, #e8f5e8 0%, #f3e5f5 100%); border-left: 4px solid #4caf50;">
                                <div style="font-weight: bold; margin-bottom: 10px; color: #388e3c;">📈 مراحل اعمال شده به ترتیب:</div>
                                <div style="font-family: 'Vazir', Arial, sans-serif; direction: rtl; line-height: 1.8; color: #333;">
                                    ${format_step_by_step_calculation(item.step_by_step_calculation)}
                                </div>
                            </div>
                        </div>
                    </div>
                    ` : ''}
        `;

        // Commission details
        if (item.commission_amount && item.commission_amount > 0) {
            html += `
                <div class="row mt-3">
                    <div class="col-md-12">
                        <h6>جزئیات کمیسیون</h6>
                        <table class="table table-sm">
                            <tr><td>مبلغ کمیسیون:</td><td>${format_currency(item.commission_amount || 0)}</td></tr>
                            <tr><td>سود خالص پس از کمیسیون:</td><td>${format_currency(item.net_profit_after_commission || 0)}</td></tr>
                        </table>
                    </div>
                </div>
            `;
        }

        // Installment details
        if (item.total_installment_amount && item.total_installment_amount > 0) {
            html += `
                <div class="row mt-3">
                    <div class="col-md-12">
                        <h6>جزئیات قسط</h6>
                        <table class="table table-sm">
                            <tr><td>مبلغ پیش پرداخت:</td><td>${format_currency(item.down_payment_amount || 0)}</td></tr>
                            <tr><td>قسط ماهانه:</td><td>${format_currency(item.monthly_payment || 0)}</td></tr>
                            <tr><td>مجموع مبلغ قسط:</td><td>${format_currency(item.total_installment_amount || 0)}</td></tr>
                            <tr><td>مجموع بهره:</td><td>${format_currency(item.total_interest || 0)}</td></tr>
                        </table>
                    </div>
                </div>
            `;
        }

        html += `
                </div>
            </div>
        `;
    });

    html += `</div>`;
    return html;
}

function format_step_by_step_calculation(calculation_text) {
    if (!calculation_text) return '';

    // تقسیم متن به خطوط
    let lines = calculation_text.split('\n');
    let formatted_html = '';

    lines.forEach(line => {
        line = line.trim();
        if (!line) return;

        // بررسی نوع خط
        if (line.includes('→')) {
            // خط مرحله‌ای با قیمت قبل و بعد
            let parts = line.split(':');
            if (parts.length >= 2) {
                let step_number = parts[0].trim();
                let step_details = parts.slice(1).join(':').trim();

                // استخراج قیمت‌ها و تغییر
                let price_match = step_details.match(/([0-9,]+)\s*→\s*([0-9,]+)\s*ریال\s*\(تغییر:\s*([+-][0-9,]+)\)/);
                if (price_match) {
                    let [, price_before, price_after, change] = price_match;
                    let step_name = step_details.split(':')[0].trim();

                    formatted_html += `
                        <div style="margin: 8px 0; padding: 8px; background: rgba(76, 175, 80, 0.1); border-radius: 4px; border-right: 3px solid #4caf50;">
                            <strong>${step_number}</strong>: ${step_name}<br>
                            <span style="color: #666; font-size: 0.9em;">
                                ${price_before} → <strong>${price_after}</strong> ریال 
                                <span style="color: ${change.startsWith('+') ? '#4caf50' : '#f44336'};">(${change})</span>
                            </span>
                        </div>
                    `;
                } else {
                    formatted_html += `<div style="margin: 5px 0; padding: 5px;">${line}</div>`;
                }
            }
        } else if (line.includes('بدون تغییر')) {
            // مرحله بدون تغییر
            let parts = line.split(':');
            if (parts.length >= 2) {
                let step_number = parts[0].trim();
                let step_details = parts.slice(1).join(':').trim();

                formatted_html += `
                    <div style="margin: 8px 0; padding: 8px; background: rgba(158, 158, 158, 0.1); border-radius: 4px; border-right: 3px solid #9e9e9e;">
                        <strong>${step_number}</strong>: ${step_details}
                    </div>
                `;
            }
        } else if (line.startsWith('🎯')) {
            // قیمت نهایی
            formatted_html += `
                <div style="margin: 15px 0 5px 0; padding: 12px; background: linear-gradient(135deg, #2196f3, #21cbf3); color: white; border-radius: 6px; text-align: center; font-weight: bold; font-size: 1.1em;">
                    ${line}
                </div>
            `;
        } else if (line.match(/^\d+\./)) {
            // خطوط عادی با شماره
            formatted_html += `<div style="margin: 5px 0; padding: 5px; background: rgba(33, 150, 243, 0.05); border-radius: 3px;">${line}</div>`;
        } else {
            // سایر خطوط
            formatted_html += `<div style="margin: 3px 0; color: #666;">${line}</div>`;
        }
    });

    return formatted_html;
}

function get_persian_strategy_name(strategy) {
    const strategies = {
        'base_price': 'قیمت پایه',
        'discount_only': 'تخفیف',
        'installment_only': 'قسط',
        'combined_discount_installment': 'ترکیب تخفیف و قسط'
    };
    return strategies[strategy] || strategy;
}

function show_pricing_steps_analysis(frm) {
    if (!frm.doc.items || frm.doc.items.length === 0) {
        frappe.msgprint(__('هیچ کالایی یافت نشد. لطفاً ابتدا کالاها را اضافه کنید.'));
        return;
    }

    let dialog = new frappe.ui.Dialog({
        title: __('🔍 تحلیل مراحل قیمت‌گذاری داینامیک'),
        size: 'extra-large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'analysis_html'
            }
        ]
    });

    // Generate analysis HTML
    let analysis_html = generate_pricing_steps_analysis_html(frm);
    dialog.fields_dict.analysis_html.$wrapper.html(analysis_html);

    dialog.show();
}

function generate_pricing_steps_analysis_html(frm) {
    let items = frm.doc.items || [];
    let pricing_steps = frm.doc.pricing_steps || [];

    let html = `
        <div style="direction: rtl; font-family: 'Vazir', Arial, sans-serif; padding: 20px;">
            <div class="row">
                <div class="col-md-12">
                    <h4>🔍 تحلیل عملکرد مراحل قیمت‌گذاری داینامیک</h4>
                    <div style="background: #e8f5e8; padding: 15px; border-radius: 8px; margin: 15px 0;">
                        <strong>📋 مراحل تعریف شده:</strong> ${pricing_steps.length} مرحله
                        <br><strong>🎯 کالاهای پردازش شده:</strong> ${items.length} کالا
                        <br><strong>⚙️ سیستم:</strong> هر مرحله روی نتیجه مرحله قبلی اعمال می‌شود
                    </div>
                </div>
            </div>
            
            <!-- Steps Overview -->
            <div class="row">
                <div class="col-md-12">
                    <h5>📊 ترتیب و نوع مراحل تعریف شده</h5>
                    <div class="table-responsive">
                        <table class="table table-bordered">
                            <thead style="background: #f8f9fa;">
                                <tr>
                                    <th>ترتیب</th>
                                    <th>نوع مرحله</th>
                                    <th>وضعیت</th>
                                    <th>تأثیر بر قیمت</th>
                                </tr>
                            </thead>
                            <tbody>
    `;

    pricing_steps.sort((a, b) => a.step_order - b.step_order).forEach(step => {
        let impact = '';
        let status = '✅ فعال';

        switch (step.step_type) {
            case 'سود':
                impact = frm.doc.profit_margin ? `+${frm.doc.profit_margin}%` : 'تنظیم نشده';
                status = frm.doc.profit_margin ? '✅ فعال' : '⚠️ غیرفعال';
                break;
            case 'افزایش قیمت':
                impact = frm.doc.required_markup_percentage ? `+${frm.doc.required_markup_percentage}%` : 'خودکار';
                break;
            case 'کمیسیون':
                impact = frm.doc.commission_percentage ? `-${frm.doc.commission_percentage}% از سود` : 'تنظیم نشده';
                status = frm.doc.commission_percentage ? '✅ فعال' : '⚠️ غیرفعال';
                break;
            case 'بهره تأخیری':
                impact = frm.doc.enable_deferred_payment ? `+${frm.doc.deferred_payment_interest_rate}% ماهانه` : 'غیرفعال';
                status = frm.doc.enable_deferred_payment ? '✅ فعال' : '⚠️ غیرفعال';
                break;
            case 'بهره قسطی':
                impact = frm.doc.enable_installment ? `+${frm.doc.monthly_interest_rate}% ماهانه` : 'غیرفعال';
                status = frm.doc.enable_installment ? '✅ فعال' : '⚠️ غیرفعال';
                break;
            case 'تخفیف':
                impact = frm.doc.target_discount_percentage ? `-${frm.doc.target_discount_percentage}%` : 'تنظیم نشده';
                status = frm.doc.target_discount_percentage ? '✅ فعال' : '⚠️ غیرفعال';
                break;
            case 'رند کردن':
                impact = frm.doc.price_rounding_amount ? `رند به ${frm.doc.price_rounding_amount}` : 'تنظیم نشده';
                status = frm.doc.price_rounding_amount ? '✅ فعال' : '⚠️ غیرفعال';
                break;
            default:
                impact = 'نامشخص';
        }

        html += `
            <tr>
                <td style="text-align: center; font-weight: bold;">${step.step_order}</td>
                <td>${step.step_type}</td>
                <td>${status}</td>
                <td>${impact}</td>
            </tr>
        `;
    });

    html += `
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
            
            <!-- Sample Calculation for First Item -->
    `;

    if (items.length > 0) {
        let first_item = items[0];
        html += `
            <div class="row mt-4">
                <div class="col-md-12">
                    <h5>🧮 نمونه محاسبه برای کالای اول: ${first_item.item_code}</h5>
                    <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 4px solid #007bff;">
                        ${first_item.step_by_step_calculation ?
                format_step_by_step_calculation(first_item.step_by_step_calculation) :
                '<p style="color: #666;">محاسبه مرحله‌ای در دسترس نیست</p>'
            }
                    </div>
                </div>
            </div>
        `;
    }

    // Summary Statistics
    let total_cost = items.reduce((sum, item) => sum + (item.total_cost || 0), 0);
    let total_final = items.reduce((sum, item) => sum + (item.final_selected_price || 0), 0);
    let total_profit = items.reduce((sum, item) => sum + (item.profit_amount || 0), 0);
    let total_commission = items.reduce((sum, item) => sum + (item.commission_amount || 0), 0);
    let total_interest = items.reduce((sum, item) => sum + (item.total_interest || 0), 0);

    html += `
            <div class="row mt-4">
                <div class="col-md-12">
                    <h5>📈 خلاصه نتایج کلی</h5>
                    <div class="row">
                        <div class="col-md-3">
                            <div style="background: #e3f2fd; padding: 15px; border-radius: 8px; text-align: center;">
                                <h6 style="color: #1976d2;">هزینه کل</h6>
                                <h4 style="color: #1976d2;">${format_currency(total_cost)}</h4>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div style="background: #e8f5e8; padding: 15px; border-radius: 8px; text-align: center;">
                                <h6 style="color: #388e3c;">قیمت نهایی</h6>
                                <h4 style="color: #388e3c;">${format_currency(total_final)}</h4>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div style="background: #fff3e0; padding: 15px; border-radius: 8px; text-align: center;">
                                <h6 style="color: #f57c00;">کل سود</h6>
                                <h4 style="color: #f57c00;">${format_currency(total_profit)}</h4>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div style="background: #f3e5f5; padding: 15px; border-radius: 8px; text-align: center;">
                                <h6 style="color: #7b1fa2;">کل بهره</h6>
                                <h4 style="color: #7b1fa2;">${format_currency(total_interest)}</h4>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div style="background: #e8f5e8; padding: 20px; border-radius: 8px; margin-top: 20px; text-align: center;">
                <h5 style="color: #388e3c;">✅ سیستم قیمت‌گذاری داینامیک فعال و عملیاتی است</h5>
                <p style="color: #666; margin: 0;">تمام محاسبات بر اساس مراحل تعریف شده و به صورت مرحله‌ای انجام شده است.</p>
            </div>
        </div>
    `;

    return html;
}

function update_prices_with_manual_materials(frm) {
    console.log('🔥 update_prices_with_manual_materials called for doc:', frm.doc.name);

    frappe.confirm(
        'آیا می‌خواهید قیمت‌های تمام آیتم‌ها را با در نظر گیری قیمت‌های دستی مواد اولیه به‌روزرسانی کنید؟',
        function () {
            console.log('🚀 User confirmed, calling backend method...');

            frappe.show_alert({
                message: 'در حال به‌روزرسانی قیمت‌ها...',
                indicator: 'blue'
            });

            // اضافه کردن لاگ‌های بیشتر
            console.log('📋 Document items count:', frm.doc.items ? frm.doc.items.length : 0);
            console.log('📋 Manual material prices count:', frm.doc.manual_material_prices ? frm.doc.manual_material_prices.length : 0);

            frappe.call({
                method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.recalculate_with_manual_prices',
                args: {
                    price_list_name: frm.doc.name
                }
            }).then((response) => {
                console.log('✅ Backend method completed, response:', response);

                if (response && response.message) {
                    const result = response.message;

                    // Check if operation was successful
                    if (!result.success) {
                        frappe.show_alert({
                            title: 'خطا',
                            message: `خطا در به‌روزرسانی: ${result.error || 'خطای نامشخص'}`,
                            indicator: 'red'
                        });
                        return;
                    }

                    let message = `📊 نتایج به‌روزرسانی:
                    • تعداد کل آیتم‌ها: ${result.total_items || 0}
                    • آیتم‌های بررسی شده: ${result.processed_items || 0}
                    • آیتم‌های متأثر: ${result.affected_items || 0}
                    • آیتم‌های به‌روزرسانی شده: ${result.updated_count || 0}
                    • تعداد قیمت‌های دستی: ${result.manual_prices_count || 0}
                    • مواد با قیمت دستی: ${(result.manual_prices || []).join(', ')}`;

                    // اضافه کردن جزئیات تغییرات قیمت
                    if (result.price_changes && result.price_changes.length > 0) {
                        message += '\n\n📈 جزئیات تغییرات قیمت:';
                        result.price_changes.forEach((change, index) => {
                            const costChangeText = change.cost_change >= 0 ? `+${change.cost_change.toLocaleString()}` : change.cost_change.toLocaleString();
                            const priceChangeText = change.price_change >= 0 ? `+${change.price_change.toLocaleString()}` : change.price_change.toLocaleString();
                            const costPercentText = change.cost_percent >= 0 ? `+${change.cost_percent.toFixed(1)}%` : `${change.cost_percent.toFixed(1)}%`;
                            const pricePercentText = change.price_percent >= 0 ? `+${change.price_percent.toFixed(1)}%` : `${change.price_percent.toFixed(1)}%`;

                            message += `\n${index + 1}. ${change.item_name} (${change.item_code})`;
                            message += `\n   💰 هزینه: ${change.old_cost.toLocaleString()} → ${change.new_cost.toLocaleString()} (${costChangeText} | ${costPercentText})`;
                            message += `\n   💵 قیمت: ${change.old_price.toLocaleString()} → ${change.new_price.toLocaleString()} (${priceChangeText} | ${pricePercentText})`;
                        });
                    }

                    console.log(message);

                    // Only refresh if changes were made
                    if (result.refresh_needed && result.updated_count > 0) {
                        console.log('🔄 Changes detected, refreshing UI...');

                        // Force refresh of items table first
                        if (frm.fields_dict.items && frm.fields_dict.items.grid) {
                            console.log('🔄 Refreshing items table...');
                            frm.fields_dict.items.grid.refresh();
                        }

                        // Then reload the entire document to ensure all changes are visible
                        frm.reload_doc().then(() => {
                            console.log('📄 Document reloaded successfully');

                            // Show success message after everything is refreshed
                            setTimeout(() => {
                                // Show detailed results in a dialog if there are price changes
                                if (result.price_changes && result.price_changes.length > 0) {
                                    show_price_changes_dialog(result);
                                } else {
                                    if (result.applied_count > 0) {
                                        frappe.show_alert({
                                            message: result.message,
                                            indicator: 'green'
                                        });

                                        // نمایش گزارش تغییرات قیمت اگر موجود باشد
                                        if (result.price_changes && result.price_changes.length > 0) {
                                            show_price_changes_report(result.price_changes);
                                        }

                                        // Refresh the form to show updated data
                                        frm.fields_dict.items.grid.refresh();
                                        frm.reload_doc();
                                        frm.refresh_field('items');
                                    } else {
                                        frappe.show_alert({
                                            message: result.message,
                                            indicator: 'orange'
                                        });
                                    }
                                }

                                // Force another refresh of items table after reload
                                if (frm.fields_dict.items && frm.fields_dict.items.grid) {
                                    console.log('🔄 Final refresh of items table...');
                                    frm.fields_dict.items.grid.refresh();
                                    frm.refresh_field('items');
                                }
                            }, 500);
                        });
                    } else {
                        // No changes made, just show message
                        frappe.show_alert({
                            message: message,
                            indicator: 'orange'
                        });
                    }
                } else {
                    frappe.show_alert({
                        title: 'خطا',
                        message: 'پاسخی از سرور دریافت نشد یا پاسخ خالی بود',
                        indicator: 'red'
                    });
                }
            }).catch((error) => {
                console.error('❌ Error in recalculate_with_manual_prices:', error);
                frappe.msgprint({
                    title: 'خطا',
                    message: 'خطا در به‌روزرسانی قیمت‌ها: ' + (error.message || error),
                    indicator: 'red'
                });
            });
        },
        function () {
            console.log('❌ User cancelled the operation');
        }
    );
}

function show_price_changes_dialog(result) {
    // Create HTML table for price changes
    let html = `
    <div style="margin: 15px 0;">
        <h4 style="color: #2e7d32; margin-bottom: 15px;">📊 خلاصه به‌روزرسانی</h4>
        <div style="background: #f8f9fa; padding: 10px; border-radius: 5px; margin-bottom: 15px;">
            <p><strong>تعداد کل آیتم‌ها:</strong> ${result.total_items || 0}</p>
            <p><strong>آیتم‌های بررسی شده:</strong> ${result.processed_items || 0}</p>
            <p><strong>آیتم‌های متأثر:</strong> ${result.affected_items || 0}</p>
            <p><strong>آیتم‌های به‌روزرسانی شده:</strong> ${result.updated_count || 0}</p>
            <p><strong>مواد با قیمت دستی:</strong> ${(result.manual_prices || []).join(', ')}</p>
        </div>
        
        <h4 style="color: #1976d2; margin-bottom: 10px;">📈 جزئیات تغییرات قیمت</h4>
        <table class="table table-bordered" style="font-size: 12px;">
            <thead style="background: #e3f2fd;">
                <tr>
                    <th style="width: 25%;">محصول</th>
                    <th style="width: 25%;">هزینه مواد</th>
                    <th style="width: 25%;">قیمت فروش</th>
                    <th style="width: 25%;">تغییرات</th>
                </tr>
            </thead>
            <tbody>`;

    result.price_changes.forEach((change, index) => {
        const costChangeText = change.cost_change >= 0 ? `+${change.cost_change.toLocaleString()}` : change.cost_change.toLocaleString();
        const priceChangeText = change.price_change >= 0 ? `+${change.price_change.toLocaleString()}` : change.price_change.toLocaleString();
        const costPercentText = change.cost_percent >= 0 ? `+${change.cost_percent.toFixed(1)}%` : `${change.cost_percent.toFixed(1)}%`;
        const pricePercentText = change.price_percent >= 0 ? `+${change.price_percent.toFixed(1)}%` : `${change.price_percent.toFixed(1)}%`;

        const costColor = change.cost_change >= 0 ? '#d32f2f' : '#388e3c';
        const priceColor = change.price_change >= 0 ? '#d32f2f' : '#388e3c';

        html += `
        <tr>
            <td>
                <strong>${change.item_name}</strong><br>
                <small style="color: #666;">${change.item_code}</small>
            </td>
            <td>
                <div>${change.old_cost.toLocaleString()} ریال</div>
                <div style="color: #1976d2;"><strong>${change.new_cost.toLocaleString()} ریال</strong></div>
            </td>
            <td>
                <div>${change.old_price.toLocaleString()} ریال</div>
                <div style="color: #1976d2;"><strong>${change.new_price.toLocaleString()} ریال</strong></div>
            </td>
            <td>
                <div style="color: ${costColor}; font-weight: bold;">
                    💰 ${costChangeText} (${costPercentText})
                </div>
                <div style="color: ${priceColor}; font-weight: bold;">
                    💵 ${priceChangeText} (${pricePercentText})
                </div>
            </td>
        </tr>`;
    });

    html += `
            </tbody>
        </table>
    </div>`;

    // Show dialog
    let d = new frappe.ui.Dialog({
        title: '🎉 نتایج به‌روزرسانی قیمت‌ها',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'changes_html',
                options: html
            }
        ],
        size: 'large',
        primary_action_label: 'بستن',
        primary_action: function () {
            d.hide();
        }
    });

    d.show();
}

function show_manual_price_impact(frm) {
    frappe.call({
        method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.get_manual_price_impact',
        args: {
            price_list_name: frm.doc.name
        },
        callback: function (r) {
            if (r.message) {
                let d = new frappe.ui.Dialog({
                    title: 'تأثیر قیمت‌های دستی مواد اولیه',
                    fields: [
                        {
                            fieldtype: 'HTML',
                            fieldname: 'impact_html',
                            options: r.message.html
                        }
                    ],
                    size: 'large'
                });
                d.show();
            }
        }
    });
}

function format_currency(amount) {
    if (!amount || amount === 0) return '0';
    return new Intl.NumberFormat('fa-IR', {
        maximumFractionDigits: 0,
        minimumFractionDigits: 0
    }).format(Math.round(amount));
}

// Function to remove filtered items
function remove_filtered_items(frm) {
    if (!frm.doc.items || frm.doc.items.length === 0) {
        frappe.msgprint(__('هیچ کالایی برای حذف وجود ندارد'));
        return;
    }

    let filters = {
        item_name: frm.doc.remove_item_name_filter,
        item_group: frm.doc.remove_item_group,
        warehouse: frm.doc.remove_warehouse,
        brand: frm.doc.remove_brand
    };

    // Check if at least one filter is provided
    let hasFilter = Object.values(filters).some(value => value && value.trim && value.trim() !== '');
    if (!hasFilter) {
        frappe.msgprint(__('لطفاً حداقل یک فیلتر برای حذف کالاها وارد کنید'));
        return;
    }

    let itemsToRemove = [];
    let itemsToKeep = [];

    frm.doc.items.forEach((item, index) => {
        let shouldRemove = false;

        // Check item name filter
        if (filters.item_name && item.item_name &&
            item.item_name.toLowerCase().includes(filters.item_name.toLowerCase())) {
            shouldRemove = true;
        }

        // Check item group filter
        if (filters.item_group && item.item_group === filters.item_group) {
            shouldRemove = true;
        }

        // Check warehouse filter (assuming warehouse is stored in item)
        if (filters.warehouse && item.warehouse === filters.warehouse) {
            shouldRemove = true;
        }

        // Check brand filter
        if (filters.brand && item.brand === filters.brand) {
            shouldRemove = true;
        }

        if (shouldRemove) {
            itemsToRemove.push(item.item_name || item.item_code);
        } else {
            itemsToKeep.push(item);
        }
    });

    if (itemsToRemove.length === 0) {
        frappe.msgprint(__('هیچ کالایی با فیلترهای مشخص شده یافت نشد'));
        return;
    }

    // Confirm removal
    frappe.confirm(
        __('آیا مطمئن هستید که می‌خواهید {0} کالا را حذف کنید؟<br><br>کالاهای حذف شده:<br>{1}',
            [itemsToRemove.length, itemsToRemove.join('<br>')]),
        function () {
            // Remove items
            frm.clear_table('items');
            itemsToKeep.forEach(item => {
                frm.add_child('items', item);
            });

            frm.refresh_field('items');
            frm.dirty();

            frappe.msgprint({
                title: __('موفق'),
                message: __('تعداد {0} کالا با موفقیت حذف شد', [itemsToRemove.length]),
                indicator: 'green'
            });

            // Clear remove filters
            frm.set_value('remove_item_name_filter', '');
            frm.set_value('remove_item_group', '');
            frm.set_value('remove_warehouse', '');
            frm.set_value('remove_brand', '');
        }
    );
}

// Function to remove items without submitted BOM (both no BOM and unsubmitted BOM)
function remove_items_without_submitted_bom(frm) {
    if (!frm.doc.items || frm.doc.items.length === 0) {
        frappe.msgprint(__('هیچ کالایی برای بررسی وجود ندارد'));
        return;
    }

    // Call Python method to get BOM status
    frappe.call({
        method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.get_items_bom_status',
        args: {
            doctype: frm.doc.doctype,
            name: frm.doc.name
        }
    }).then(r => {
        if (r.message) {
            let itemsWithoutBom = r.message.items_without_bom || [];
            let itemsWithUnsubmittedBom = r.message.items_with_unsubmitted_bom || [];
            let allItemsToRemove = [...itemsWithoutBom, ...itemsWithUnsubmittedBom];

            if (allItemsToRemove.length === 0) {
                frappe.msgprint(__('همه کالاها دارای BOM ارسال شده هستند'));
                return;
            }

            // Create a set of item codes to remove for faster lookup
            let itemsToRemoveSet = new Set(allItemsToRemove.map(item => item.item_code));

            // Filter items to keep only those with submitted BOM
            let itemsToKeep = [];
            frm.doc.items.forEach((item) => {
                if (!itemsToRemoveSet.has(item.item_code)) {
                    itemsToKeep.push(item);
                }
            });

            // Create detailed message
            let redItems = itemsWithoutBom.map(item =>
                `${item.item_name} (بدون BOM)`
            );
            let yellowItems = itemsWithUnsubmittedBom.map(item =>
                `${item.item_name} (BOM ارسال نشده)`
            );
            let detailMessage = [...redItems, ...yellowItems].join('<br>');

            // Confirm removal
            frappe.confirm(
                __('آیا مطمئن هستید که می‌خواهید {0} کالای بدون BOM ارسال شده را حذف کنید؟<br><br>کالاهای حذف شده:<br>{1}',
                    [allItemsToRemove.length, detailMessage]),
                function () {
                    // Remove items
                    frm.clear_table('items');
                    itemsToKeep.forEach(item => {
                        frm.add_child('items', item);
                    });

                    frm.refresh_field('items');
                    frm.dirty();

                    frappe.msgprint({
                        title: __('موفق'),
                        message: __('تعداد {0} کالای بدون BOM ارسال شده با موفقیت حذف شد', [allItemsToRemove.length]),
                        indicator: 'green'
                    });
                }
            );
        } else {
            frappe.msgprint(__('خطا در دریافت وضعیت BOM کالاها'));
        }
    });
}

// Function to remove items without active BOM (old function - kept for compatibility)
function remove_items_without_bom(frm) {
    if (!frm.doc.items || frm.doc.items.length === 0) {
        frappe.msgprint(__('هیچ کالایی برای بررسی وجود ندارد'));
        return;
    }

    // Call Python method to get BOM status - using existing function
    frappe.call({
        method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.get_items_bom_status',
        args: {
            doctype: frm.doc.doctype,
            name: frm.doc.name
        }
    }).then(r => {
        if (r.message && r.message.items_without_bom) {
            let itemsWithoutBom = r.message.items_without_bom;
            let itemsToKeep = [];

            // Create a set of item codes without BOM for faster lookup
            let itemsWithoutBomSet = new Set(itemsWithoutBom.map(item => item.item_code));

            // Filter items to keep only those with BOM
            frm.doc.items.forEach((item) => {
                if (!itemsWithoutBomSet.has(item.item_code)) {
                    itemsToKeep.push(item);
                }
            });

            if (itemsWithoutBom.length === 0) {
                frappe.msgprint(__('همه کالاها دارای BOM فعال و پیش‌فرض هستند'));
                return;
            }

            // Create detailed message
            let detailMessage = itemsWithoutBom.map(item =>
                `${item.item_name} (بدون BOM فعال)`
            ).join('<br>');

            // Confirm removal
            frappe.confirm(
                __('آیا مطمئن هستید که می‌خواهید {0} کالای بدون BOM فعال را حذف کنید؟<br><br>کالاهای حذف شده:<br>{1}',
                    [itemsWithoutBom.length, detailMessage]),
                function () {
                    // Remove items
                    frm.clear_table('items');
                    itemsToKeep.forEach(item => {
                        frm.add_child('items', item);
                    });

                    frm.refresh_field('items');
                    frm.dirty();

                    frappe.msgprint({
                        title: __('موفق'),
                        message: __('تعداد {0} کالای بدون BOM فعال با موفقیت حذف شد', [itemsWithoutBom.length]),
                        indicator: 'green'
                    });
                }
            );
        } else {
            frappe.msgprint(__('خطا در دریافت وضعیت BOM کالاها'));
        }
    });
}

function apply_bom_status_styling(frm) {
    /**
     * اعمال رنگ‌آمیزی به ردیف‌های محصولات بر اساس وضعیت BOM:
     * - قرمز: بدون BOM فعال
     * - زرد: BOM دارند اما ارسال نشده
     * - سبز: BOM ارسال شده
     */
    if (!frm.doc.items || frm.doc.items.length === 0) {
        return;
    }

    // فراخوانی تابع Python برای دریافت وضعیت BOM محصولات
    frappe.call({
        method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.get_items_bom_status',
        args: {
            doctype: frm.doc.doctype,
            name: frm.doc.name
        }
    }).then(r => {
        if (r.message) {
            const items_without_bom = r.message.items_without_bom || [];
            const items_with_unsubmitted_bom = r.message.items_with_unsubmitted_bom || [];

            // ایجاد مجموعه‌های item_code برای جستجوی سریع
            const items_without_bom_set = new Set(
                items_without_bom.map(item => item.item_code)
            );
            const items_with_unsubmitted_bom_set = new Set(
                items_with_unsubmitted_bom.map(item => item.item_code)
            );

            // اعمال استایل به ردیف‌های جدول
            setTimeout(() => {
                const grid = frm.fields_dict.items.grid;
                if (grid && grid.wrapper) {
                    // پیدا کردن تمام ردیف‌های جدول
                    const rows = grid.wrapper.find('.grid-row');

                    rows.each(function (index) {
                        const row = $(this);
                        const item_code_cell = row.find('[data-fieldname="item_code"]');

                        if (item_code_cell.length > 0) {
                            const item_code = item_code_cell.find('input, .static-area').val() ||
                                item_code_cell.find('.static-area').text().trim();

                            // حذف استایل‌های قبلی
                            row.removeClass('bom-status-red bom-status-yellow bom-status-green');
                            row.find('.bom-warning-icon, .bom-success-icon').remove();
                            row.css({
                                'background-color': '',
                                'border-left': ''
                            });

                            if (items_without_bom_set.has(item_code)) {
                                // رنگ قرمز: بدون BOM فعال
                                row.css({
                                    'background-color': '#ffebee',
                                    'border-left': '4px solid #f44336'
                                });
                            } else if (items_with_unsubmitted_bom_set.has(item_code)) {
                                // رنگ زرد: BOM دارد اما ارسال نشده
                                row.css({
                                    'background-color': '#fff8e1',
                                    'border-left': '4px solid #ff9800'
                                });
                            }
                            // محصولات با BOM ارسال شده: بدون رنگ‌بندی (حالت عادی)
                        }
                    });
                }
            }, 100);

            // نمایش پیام اطلاع‌رسانی
            let alertMessages = [];
            if (items_without_bom.length > 0) {
                alertMessages.push(`${items_without_bom.length} محصول BOM ندارند`);
            }
            if (items_with_unsubmitted_bom.length > 0) {
                alertMessages.push(`${items_with_unsubmitted_bom.length} محصول BOM ارسال نشده دارند`);
            }

            if (alertMessages.length > 0) {
                frappe.show_alert({
                    message: alertMessages.join(' | '),
                    indicator: 'orange'
                });
            }
        }
    });
}

function show_items_without_bom(frm) {
    /**
     * نمایش لیست محصولاتی که BOM فعال ندارند
     */
    frappe.call({
        method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.get_items_bom_status',
        args: {
            doctype: frm.doc.doctype,
            name: frm.doc.name
        }
    }).then(r => {
        if (r.message) {
            const data = r.message;
            const items_without_bom = data.items_without_bom || [];

            let html = `
                <div style="padding: 20px; direction: rtl; font-family: 'Vazir', Arial, sans-serif;">
                    <div style="margin-bottom: 20px;">
                        <h3 style="color: #f44336; margin-bottom: 10px;">
                            📋 محصولات بدون BOM فعال
                        </h3>
                        <p style="color: #666; margin-bottom: 20px;">
                            تعداد کل محصولات: <strong>${data.total_items || 0}</strong><br>
                            محصولات بدون BOM: <strong style="color: #f44336;">${items_without_bom.length}</strong>
                        </p>
                    </div>
            `;

            if (items_without_bom.length === 0) {
                html += `
                    <div style="text-align: center; padding: 40px; background: #e8f5e8; border-radius: 8px;">
                        <h4 style="color: #4caf50; margin: 0;">✅ عالی!</h4>
                        <p style="margin: 10px 0 0 0; color: #666;">
                            تمام محصولات دارای BOM فعال هستند
                        </p>
                    </div>
                `;
            } else {
                html += `
                    <div style="background: #ffebee; padding: 15px; border-radius: 8px; border-right: 4px solid #f44336;">
                        <h4 style="color: #f44336; margin: 0 0 15px 0;">⚠️ محصولات نیازمند BOM:</h4>
                        <table style="width: 100%; border-collapse: collapse;">
                            <thead>
                                <tr style="background: #f5f5f5;">
                                    <th style="padding: 10px; border: 1px solid #ddd; text-align: right;">ردیف</th>
                                    <th style="padding: 10px; border: 1px solid #ddd; text-align: right;">کد محصول</th>
                                    <th style="padding: 10px; border: 1px solid #ddd; text-align: right;">نام محصول</th>
                                </tr>
                            </thead>
                            <tbody>
                `;

                items_without_bom.forEach((item, index) => {
                    html += `
                        <tr>
                            <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">${item.idx || index + 1}</td>
                            <td style="padding: 8px; border: 1px solid #ddd; font-family: monospace;">${item.item_code}</td>
                            <td style="padding: 8px; border: 1px solid #ddd;">${item.item_name || '-'}</td>
                        </tr>
                    `;
                });

                html += `
                            </tbody>
                        </table>
                        <div style="margin-top: 15px; padding: 10px; background: #fff3cd; border-radius: 4px;">
                            <strong>💡 توصیه:</strong> برای این محصولات BOM فعال ایجاد کنید تا قیمت‌گذاری دقیق انجام شود.
                        </div>
                    </div>
                `;
            }

            html += `</div>`;

            // نمایش دیالوگ
            let d = new frappe.ui.Dialog({
                title: '🔍 بررسی وضعیت BOM محصولات',
                fields: [
                    {
                        fieldtype: 'HTML',
                        fieldname: 'bom_status_html',
                        options: html
                    }
                ],
                size: 'large',
                primary_action_label: 'بستن',
                primary_action: function () {
                    d.hide();
                },
                secondary_action_label: 'رنگ‌آمیزی مجدد',
                secondary_action: function () {
                    apply_bom_status_styling(frm);
                    frappe.show_alert({
                        message: 'رنگ‌آمیزی ردیف‌ها به‌روزرسانی شد',
                        indicator: 'green'
                    });
                }
            });

            d.show();
        }
    });
}

// توابع جایگزینی مواد
function add_material_substitution_buttons(frm) {
    // دکمه به‌روزرسانی قیمت‌های جایگزینی مواد
    frm.add_custom_button(__('🔄 به‌روزرسانی قیمت‌های جایگزینی'), function () {
        frappe.call({
            method: 'update_material_substitution_prices',
            doc: frm.doc,
            callback: function (r) {
                if (r.message) {
                    // بررسی نوع پاسخ - ممکنه object یا string باشه
                    let msg = typeof r.message === 'object' ?
                        (r.message.message || JSON.stringify(r.message)) : r.message;
                    frappe.msgprint({
                        title: '✅ موفق',
                        message: msg,
                        indicator: 'green'
                    });
                    frm.refresh();
                }
            }
        });
    }, __('عملیات اصلی'));

    // دکمه تحلیل جایگزینی مواد
    frm.add_custom_button(__('📊 تحلیل جایگزینی مواد'), function () {
        frappe.call({
            method: 'get_substitution_analysis',
            doc: frm.doc,
            callback: function (r) {
                if (r.message && !r.message.error) {
                    show_substitution_analysis_dialog(r.message);
                } else {
                    let errorMsg = r.message && r.message.error ? r.message.error : 'خطا در تحلیل جایگزینی مواد';
                    frappe.msgprint({
                        title: '❌ خطا',
                        message: errorMsg,
                        indicator: 'red'
                    });
                }
            }
        });
    }, __('گزارش'));
}

function show_substitution_analysis_dialog(analysis) {
    let dialog = new frappe.ui.Dialog({
        title: '📊 تحلیل جایگزینی مواد',
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'analysis_summary'
            },
            {
                fieldtype: 'HTML',
                fieldname: 'substitutions_table'
            }
        ]
    });

    // خلاصه تحلیل
    let summary_html = `
        <div class="row">
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h3 class="text-primary">${analysis.total_substitutions}</h3>
                        <p>کل جایگزینی‌ها</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h3 class="text-success">${analysis.cost_saving_substitutions}</h3>
                        <p>صرفه‌جویی در هزینه</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h3 class="text-danger">${analysis.cost_increasing_substitutions}</h3>
                        <p>افزایش هزینه</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h3 class="text-info">${format_currency(analysis.total_savings)}</h3>
                        <p>کل صرفه‌جویی</p>
                    </div>
                </div>
            </div>
        </div>
    `;

    // جدول جزئیات
    let table_html = '<table class="table table-striped"><thead><tr>';
    table_html += '<th>کالای اصلی</th><th>کالای جایگزین</th><th>قیمت اصلی</th>';
    table_html += '<th>قیمت جایگزین</th><th>تفاوت قیمت</th><th>درصد صرفه‌جویی</th></tr></thead><tbody>';

    analysis.substitutions_details.forEach(sub => {
        let row_class = sub.savings_percentage > 0 ? 'table-success' :
            sub.savings_percentage < 0 ? 'table-danger' : '';

        table_html += `<tr class="${row_class}">`;
        table_html += `<td>${sub.original_item}</td>`;
        table_html += `<td>${sub.substitute_item}</td>`;
        table_html += `<td>${format_currency(sub.original_price)}</td>`;
        table_html += `<td>${format_currency(sub.substitute_price)}</td>`;
        table_html += `<td>${format_currency(sub.price_difference)}</td>`;
        table_html += `<td>${sub.savings_percentage.toFixed(2)}%</td>`;
        table_html += '</tr>';
    });

    table_html += '</tbody></table>';

    dialog.fields_dict.analysis_summary.$wrapper.html(summary_html);
    dialog.fields_dict.substitutions_table.$wrapper.html(table_html);

    dialog.show();
}

// توابع مواد اولیه بدون قیمت
function add_missing_material_buttons(frm) {
    // دکمه اسکن مواد اولیه بدون قیمت
    frm.add_custom_button(__('🔍 اسکن مواد بدون قیمت'), function () {
        frappe.call({
            method: 'scan_missing_material_prices',
            doc: frm.doc,
            callback: function (r) {
                if (r.message) {
                    frappe.msgprint({
                        title: '🔍 نتیجه اسکن',
                        message: r.message.message,
                        indicator: r.message.missing_count > 0 ? 'orange' : 'green'
                    });
                    frm.refresh();
                }
            }
        });
    }, __('عملیات اصلی'));

    // دکمه اعمال قیمت مواد اولیه بدون هزینه
    frm.add_custom_button(__('اعمال قیمت مواد اولیه بدون هزینه'), function () {
        frappe.call({
            method: 'apply_missing_material_prices',
            doc: frm.doc,
            callback: function (r) {
                if (r.message && r.message.success) {
                    frappe.msgprint({
                        title: '✅ موفق',
                        message: r.message.message,
                        indicator: 'green'
                    });
                    frm.refresh();
                } else {
                    const error_msg = r.message ? r.message.message || r.message.error_details || 'خطای نامشخص' : 'خطا در اعمال قیمت‌های دستی';
                    frappe.msgprint({
                        title: '❌ خطا',
                        message: error_msg,
                        indicator: 'red'
                    });
                }
            },
            error: function (r) {
                frappe.msgprint({
                    title: '❌ خطا',
                    message: 'خطا در ارتباط با سرور: ' + (r.message || 'خطای نامشخص'),
                    indicator: 'red'
                });
            }
        });
    }, __('عملیات اصلی'));
    // دکمه به‌روزرسانی با قیمت‌های دستی
    frm.add_custom_button(__('🔄 به‌روزرسانی با قیمت‌های دستی'), function () {
        update_prices_with_manual_materials(frm);
    }, __('عملیات اصلی'));

    // دکمه پاک کردن رکورد‌های صفر
    frm.add_custom_button(__('🗑️ پاک کردن قیمت‌های صفر'), function () {
        clean_zero_manual_prices(frm);
    }, __('عملیات اصلی'));

    // دکمه گزارش تحلیل هزینه
    frm.add_custom_button(__('📊 گزارش تحلیل هزینه'), function () {
        frappe.set_route('query-report', 'Cost Analysis Report', {
            auto_price_list: frm.doc.name
        });
    }, __('گزارش‌ها'));

    // دکمه گزارش مواد اولیه خام
    frm.add_custom_button(__('🧱 گزارش مواد اولیه خام'), function () {
        frappe.set_route('query-report', 'Raw Materials Report', {
            auto_price_list: frm.doc.name
        });
    }, __('گزارش‌ها'));
}

function show_missing_materials_report(frm) {
    if (!frm.doc.missing_material_prices || frm.doc.missing_material_prices.length === 0) {
        frappe.msgprint({
            title: __('اطلاعات'),
            message: __('هیچ ماده اولیه بدون قیمتی یافت نشد. ابتدا اسکن انجام دهید.'),
            title: '📋 اطلاعات',
            message: 'هیچ ماده اولیه بدون قیمتی یافت نشد. ابتدا اسکن انجام دهید.',
            indicator: 'blue'
        });
        return;
    }

    let dialog = new frappe.ui.Dialog({
        title: '📊 گزارش مواد اولیه بدون قیمت',
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'summary'
            },
            {
                fieldtype: 'HTML',
                fieldname: 'materials_table'
            }
        ]
    });

    // خلاصه آماری
    let total_materials = frm.doc.missing_material_prices.length;
    let materials_with_suggested = frm.doc.missing_material_prices.filter(m => m.suggested_price > 0).length;
    let materials_with_manual = frm.doc.missing_material_prices.filter(m => m.manual_price > 0).length;

    let summary_html = `
        <div class="row">
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h3 class="text-warning">${total_materials}</h3>
                        <p>کل مواد بدون قیمت</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h3 class="text-info">${materials_with_suggested}</h3>
                        <p>دارای قیمت پیشنهادی</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h3 class="text-success">${materials_with_manual}</h3>
                        <p>دارای قیمت دستی</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h3 class="text-danger">${total_materials - materials_with_manual}</h3>
                        <p>نیاز به قیمت‌گذاری</p>
                    </div>
                </div>
            </div>
        </div>
    `;

    // جدول جزئیات
    let table_html = '<table class="table table-striped"><thead><tr>';
    table_html += '<th>کد ماده</th><th>نام ماده</th><th>قیمت فعلی</th><th>قیمت پیشنهادی</th>';
    table_html += '<th>قیمت دستی</th><th>تعداد BOM</th><th>محصولات تأثیرپذیر</th></tr></thead><tbody>';

    frm.doc.missing_material_prices.forEach(material => {
        let row_class = material.manual_price > 0 ? 'table-success' :
            material.suggested_price > 0 ? 'table-info' : 'table-warning';

        table_html += `<tr class="${row_class}">`;
        table_html += `<td>${material.item_code}</td>`;
        table_html += `<td>${material.item_name || ''}</td>`;
        table_html += `<td>${format_currency(material.current_price || 0)}</td>`;
        table_html += `<td>${format_currency(material.suggested_price || 0)}</td>`;
        table_html += `<td><strong>${format_currency(material.manual_price || 0)}</strong></td>`;
        table_html += `<td>${material.bom_usage_count || 0}</td>`;
        table_html += `<td><small>${material.affected_items || ''}</small></td>`;
        table_html += '</tr>';
    });

    table_html += '</tbody></table>';

    dialog.fields_dict.summary.$wrapper.html(summary_html);
    dialog.fields_dict.materials_table.$wrapper.html(table_html);

    dialog.show();
}

// دکمه گزارش تغییرات قیمت
function add_price_change_report_button(frm) {
    frm.add_custom_button(__('گزارش تغییرات قیمت'), function () {
        show_price_change_report_dialog(frm);
    }, __('گزارش'));
}

// نمایش گزارش تغییرات قیمت
function show_price_change_report_dialog(frm) {
    frappe.call({
        method: 'get_price_change_report',
        doc: frm.doc,
        callback: function (r) {
            if (r.message && r.message.success) {
                display_price_change_report(r.message);
            } else {
                frappe.msgprint({
                    title: __('خطا'),
                    message: r.message?.message || 'خطا در تهیه گزارش',
                    indicator: 'red'
                });
            }
        }
    });
}

// نمایش گزارش تغییرات قیمت در دیالوگ
function display_price_change_report(data) {
    let dialog = new frappe.ui.Dialog({
        title: 'گزارش تغییرات قیمت محصولات',
        size: 'extra-large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'summary_stats',
                label: 'آمار کلی'
            },
            {
                fieldtype: 'HTML',
                fieldname: 'price_changes_table',
                label: 'جزئیات تغییرات'
            }
        ],
        primary_action_label: 'بستن',
        primary_action: function () {
            dialog.hide();
        }
    });

    // آمار کلی
    let summary = data.summary;
    let summary_html = `
        <div class="row mb-4">
            <div class="col-md-2">
                <div class="card text-center bg-light">
                    <div class="card-body">
                        <h4 class="text-primary">${summary.total_items}</h4>
                        <p class="mb-0">کل محصولات</p>
                    </div>
                </div>
            </div>
            <div class="col-md-2">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-success">${summary.items_with_changes}</h4>
                        <p class="mb-0">با تغییر قیمت</p>
                    </div>
                </div>
            </div>
            <div class="col-md-2">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-muted">${summary.items_without_changes}</h4>
                        <p class="mb-0">بدون تغییر</p>
                    </div>
                </div>
            </div>
            <div class="col-md-2">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-success">+${format_currency(summary.total_price_increase)}</h4>
                        <p class="mb-0">افزایش قیمت</p>
                    </div>
                </div>
            </div>
            <div class="col-md-2">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-danger">-${format_currency(summary.total_price_decrease)}</h4>
                        <p class="mb-0">کاهش قیمت</p>
                    </div>
                </div>
            </div>
            <div class="col-md-2">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="${summary.net_price_change >= 0 ? 'text-success' : 'text-danger'}">
                            ${summary.net_price_change >= 0 ? '+' : ''}${format_currency(summary.net_price_change)}
                        </h4>
                        <p class="mb-0">تغییر خالص</p>
                    </div>
                </div>
            </div>
        </div>
        <div class="alert alert-info">
            <strong>میانگین درصد تغییر قیمت:</strong> ${summary.average_price_change_percent.toFixed(2)}%
            <br>
            <strong>تعداد مواد دستی:</strong> ${data.manual_materials_count} مورد
        </div>
    `;

    // جدول جزئیات
    let table_html = '<table class="table table-striped table-hover"><thead class="table-dark"><tr>';
    table_html += '<th>کد محصول</th><th>نام محصول</th>';
    table_html += '<th>قیمت پایه</th><th>قیمت فعلی</th><th>تغییر قیمت</th>';
    table_html += '<th>درصد تغییر</th><th>مواد تأثیرگذار</th></tr></thead><tbody>';

    data.report_data.forEach(item => {
        let row_class = '';
        if (item.has_price_change) {
            row_class = item.price_difference > 0 ? 'table-success' : 'table-warning';
        }

        let change_badge = '';
        if (item.has_price_change) {
            let badge_class = item.price_difference > 0 ? 'success' : 'warning';
            change_badge = `<span class="badge bg-${badge_class}">
                ${item.price_difference >= 0 ? '+' : ''}${format_currency(item.price_difference)}
            </span>`;
        } else {
            change_badge = '<span class="badge bg-secondary">بدون تغییر</span>';
        }

        let percent_badge = '';
        if (item.has_price_change) {
            let badge_class = item.price_change_percent > 0 ? 'success' : 'warning';
            percent_badge = `<span class="badge bg-${badge_class}">
                ${item.price_change_percent >= 0 ? '+' : ''}${item.price_change_percent.toFixed(1)}%
            </span>`;
        } else {
            percent_badge = '<span class="badge bg-secondary">0%</span>';
        }

        // مواد تأثیرگذار
        let affected_materials = '';
        if (item.affected_materials && item.affected_materials.length > 0) {
            affected_materials = item.affected_materials.map(mat =>
                `<small class="text-muted">${mat.item_code} (${mat.quantity})</small>`
            ).join('<br>');
        } else {
            affected_materials = '<small class="text-muted">-</small>';
        }

        table_html += `<tr class="${row_class}">`;
        table_html += `<td><strong>${item.item_code}</strong></td>`;
        table_html += `<td>${item.item_name || ''}</td>`;
        table_html += `<td>${format_currency(item.base_selling_price)}</td>`;
        table_html += `<td><strong>${format_currency(item.current_selling_price)}</strong></td>`;
        table_html += `<td>${change_badge}</td>`;
        table_html += `<td>${percent_badge}</td>`;
        table_html += `<td>${affected_materials}</td>`;
        table_html += '</tr>';
    });

    table_html += '</tbody></table>';

    dialog.fields_dict.summary_stats.$wrapper.html(summary_html);
    dialog.fields_dict.price_changes_table.$wrapper.html(table_html);

    dialog.show();
}

// توابع Progress Dialog برای محاسبه داینامیک قیمت
let dynamic_pricing_progress_dialog = null;

function show_dynamic_pricing_progress_dialog(frm) {
    console.log('🚀 نمایش دیالوگ پیشرفت محاسبه داینامیک');

    // ایجاد دیالوگ پیشرفت
    dynamic_pricing_progress_dialog = new frappe.ui.Dialog({
        title: '💰 محاسبه داینامیک قیمت‌ها',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'progress_area'
            }
        ],
        static: true,
        primary_action_label: '❌ لغو عملیات',
        primary_action: function () {
            // لغو عملیات
            frappe.call({
                method: 'frappe.core.doctype.communication.email.cancel_background_job',
                args: {
                    job_name: 'dynamic_pricing_' + frm.doc.name
                },
                callback: function () {
                    frappe.show_alert({
                        message: '⚠️ عملیات لغو شد',
                        indicator: 'orange'
                    });
                    hide_dynamic_pricing_progress_dialog();
                }
            });
        }
    });

    // HTML اولیه
    const initial_html = `
        <div class="dynamic-pricing-progress" style="padding: 20px;">
            <div class="text-center mb-3">
                <i class="fa fa-spinner fa-spin" style="font-size: 48px; color: #5e64ff;"></i>
            </div>
            <h4 class="text-center mb-3">در حال آماده‌سازی...</h4>
            <div class="progress" style="height: 25px;">
                <div class="progress-bar progress-bar-striped progress-bar-animated" 
                     role="progressbar" 
                     style="width: 0%;" 
                     id="dynamic-pricing-progress-bar">0%</div>
            </div>
            <div class="mt-3">
                <p class="text-center text-muted" id="dynamic-pricing-status">شروع محاسبه داینامیک قیمت‌ها...</p>
                <p class="text-center" id="dynamic-pricing-item-info"></p>
                <div class="text-center mt-3">
                    <button class="btn btn-sm btn-warning" onclick="emergency_cancel_pricing()">
                        🚨 لغو اضطراری
                    </button>
                </div>
            </div>
        </div>
    `;

    dynamic_pricing_progress_dialog.fields_dict.progress_area.$wrapper.html(initial_html);
    dynamic_pricing_progress_dialog.show();

    // Listen for real-time updates
    frappe.realtime.on('dynamic_pricing_progress', function (data) {
        update_dynamic_pricing_progress(data);
    });
}

function update_dynamic_pricing_progress(data) {
    if (!dynamic_pricing_progress_dialog) return;

    const progressBar = document.getElementById('dynamic-pricing-progress-bar');
    const statusText = document.getElementById('dynamic-pricing-status');
    const itemInfo = document.getElementById('dynamic-pricing-item-info');

    if (!progressBar || !statusText) return;

    if (data.status === 'started') {
        statusText.innerHTML = `<strong>${data.message}</strong>`;
        progressBar.style.width = '0%';
        progressBar.innerHTML = '0%';
    } else if (data.status === 'calculating_costs') {
        statusText.innerHTML = `<strong>${data.message}</strong>`;
        progressBar.style.width = '10%';
        progressBar.innerHTML = '10%';
        progressBar.className = 'progress-bar progress-bar-striped progress-bar-animated bg-warning';
    } else if (data.status === 'processing') {
        const percentage = data.percentage || 0;
        progressBar.style.width = percentage + '%';
        progressBar.innerHTML = percentage + '%';
        progressBar.className = 'progress-bar progress-bar-striped progress-bar-animated bg-info';

        statusText.innerHTML = `<strong>${data.message}</strong>`;
        if (data.current_item) {
            itemInfo.innerHTML = `
                <small class="text-muted">
                    پردازش ${data.progress} از ${data.total} محصول
                    <br>محصول فعلی: <strong>${data.current_item}</strong>
                </small>
            `;
        }
    } else if (data.status === 'completed') {
        progressBar.style.width = '100%';
        progressBar.innerHTML = '100%';
        progressBar.className = 'progress-bar bg-success';

        statusText.innerHTML = `<strong class="text-success">${data.message}</strong>`;

        if (data.updated_count) {
            itemInfo.innerHTML = `
                <div class="alert alert-success mt-3">
                    <i class="fa fa-check-circle"></i> 
                    ${data.updated_count} محصول با موفقیت به‌روزرسانی شد
                    ${data.errors_count > 0 ? `<br><small class="text-warning">${data.errors_count} خطا رخ داد</small>` : ''}
                </div>
            `;
        }

        // بستن دیالوگ و refresh صفحه بعد از 2 ثانیه
        setTimeout(() => {
            hide_dynamic_pricing_progress_dialog();
            // Refresh فرم برای نمایش قیمت‌های جدید
            if (cur_frm) {
                cur_frm.reload_doc();
            }
            frappe.show_alert({
                message: '✅ قیمت‌ها با موفقیت محاسبه شد',
                indicator: 'green'
            }, 5);
        }, 2000);
    } else if (data.status === 'error') {
        progressBar.className = 'progress-bar bg-danger';
        statusText.innerHTML = `<strong class="text-danger">❌ ${data.message}</strong>`;

        if (data.error) {
            itemInfo.innerHTML = `
                <div class="alert alert-danger mt-3">
                    <small>${data.error}</small>
                </div>
            `;
        }

        // بستن دیالوگ بعد از 3 ثانیه
        setTimeout(() => {
            hide_dynamic_pricing_progress_dialog();
        }, 3000);
    }
}

function hide_dynamic_pricing_progress_dialog() {
    if (dynamic_pricing_progress_dialog) {
        dynamic_pricing_progress_dialog.hide();
        dynamic_pricing_progress_dialog = null;
    }

    // حذف listener
    frappe.realtime.off('dynamic_pricing_progress');
}

// تابع لغو اضطراری
function emergency_cancel_pricing() {
    console.log('🚨 لغو اضطراری محاسبه داینامیک');

    frappe.confirm(
        'آیا مطمئن هستید که می‌خواهید عملیات را لغو کنید؟',
        function () {
            // بستن دیالوگ
            hide_dynamic_pricing_progress_dialog();

            // نمایش پیام لغو
            frappe.show_alert({
                message: '⚠️ عملیات توسط کاربر لغو شد',
                indicator: 'orange'
            });

            // تلاش برای لغو عملیات در سرور
            frappe.call({
                method: 'frappe.core.doctype.data_import.data_import.cancel',
                freeze: false,
                callback: function () {
                    console.log('عملیات لغو شد');
                }
            });
        }
    );
}

// اضافه کردن تابع به window برای دسترسی global
window.emergency_cancel_pricing = emergency_cancel_pricing;

/**
 * محاسبه بهای تمام شده با progress bar
 * استفاده از متد بهینه‌سازی شده
 */
function calculate_full_costing_ultra_fast(frm) {
    console.log('⚡ calculate_full_costing_ultra_fast called');

    if (!frm.doc.items || frm.doc.items.length === 0) {
        frappe.msgprint({
            title: 'توجه',
            message: 'هیچ آیتمی برای محاسبه وجود ندارد',
            indicator: 'orange'
        });
        return;
    }

    const items_count = frm.doc.items.length;

    frappe.confirm(
        `⚡ محاسبه سریع بهای تمام شده<br><br>` +
        `<small>تعداد آیتم‌ها: <b>${items_count}</b><br><br>` +
        `این روش سریع‌تر از روش معمولی است و از:<br>` +
        `• بارگذاری دسته‌ای BOMs<br>` +
        `• بارگذاری یکباره قیمت‌ها<br>` +
        `• حداقل query به دیتابیس<br>` +
        `استفاده می‌کند.</small>`,
        function () {
            // ایجاد progress dialog
            const progress_dialog = new frappe.ui.Dialog({
                title: '⚡ محاسبه سریع بهای تمام شده',
                fields: [
                    {
                        fieldtype: 'HTML',
                        fieldname: 'progress_html',
                        options: `
                            <div id="ultra-fast-progress-container">
                                <div class="progress" style="height: 25px; margin-bottom: 15px;">
                                    <div id="ultra-fast-progress-bar" class="progress-bar progress-bar-striped progress-bar-animated" 
                                         role="progressbar" style="width: 0%; background-color: #2185d0;">
                                        <span id="ultra-fast-progress-text" style="color: white; font-weight: bold;">0%</span>
                                    </div>
                                </div>
                                <p id="ultra-fast-status-message" style="text-align: center; font-size: 14px; color: #666;">
                                    شروع محاسبه...
                                </p>
                                <div id="ultra-fast-time-elapsed" style="text-align: center; font-size: 12px; color: #999;">
                                    زمان سپری شده: 0 ثانیه
                                </div>
                            </div>
                        `
                    }
                ],
                primary_action_label: 'بستن',
                primary_action: function () {
                    progress_dialog.hide();
                }
            });
            progress_dialog.show();
            progress_dialog.$wrapper.find('.modal-dialog').css('max-width', '500px');

            // شروع تایمر
            let start_time = Date.now();
            let timer_interval = setInterval(() => {
                let elapsed = Math.round((Date.now() - start_time) / 1000);
                $('#ultra-fast-time-elapsed').text(`زمان سپری شده: ${elapsed} ثانیه`);
            }, 1000);

            // گوش دادن به realtime updates
            frappe.realtime.on('costing_progress', function (data) {
                console.log('Costing progress:', data);
                $('#ultra-fast-progress-bar').css('width', data.progress + '%');
                $('#ultra-fast-progress-text').text(data.progress + '%');
                $('#ultra-fast-status-message').text(data.message);

                if (data.progress >= 100) {
                    $('#ultra-fast-progress-bar').removeClass('progress-bar-animated progress-bar-striped');
                    $('#ultra-fast-progress-bar').css('background-color', '#21ba45');
                }
            });

            // فراخوانی متد سریع از طریق API
            frappe.call({
                method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.calculate_full_costing_ultra_fast_api',
                args: {
                    docname: frm.doc.name
                },
                freeze: false,
                async: true,
                timeout: 600  // 10 دقیقه timeout
            }).then((response) => {
                console.log('⚡ Ultra fast costing response:', response);

                if (response && response.message) {
                    const result = response.message;

                    if (result.background) {
                        // محاسبه در پس‌زمینه شروع شد
                        $('#ultra-fast-progress-text').text('⏳');
                        $('#ultra-fast-status-message').html(`
                            <span style="color: #2185d0; font-weight: bold;">⏳ ${result.message}</span><br>
                            <small>لطفاً صبر کنید، پیشرفت بصورت خودکار نمایش داده میشه...</small>
                        `);

                        // گوش دادن به رویداد اتمام
                        frappe.realtime.on('costing_complete', function (data) {
                            console.log('⚡ Background costing complete:', data);

                            clearInterval(timer_interval);
                            frappe.realtime.off('costing_progress');
                            frappe.realtime.off('costing_complete');

                            if (data.success) {
                                $('#ultra-fast-progress-bar').css('width', '100%').css('background-color', '#21ba45');
                                $('#ultra-fast-progress-text').text('✅ کامل شد');
                                $('#ultra-fast-status-message').html(`
                                    <span style="color: green; font-weight: bold;">✅ ${data.message}</span>
                                `);

                                setTimeout(() => {
                                    progress_dialog.hide();
                                    frm.reload_doc();
                                }, 2000);
                            } else {
                                $('#ultra-fast-progress-bar').css('background-color', '#db2828');
                                $('#ultra-fast-status-message').html(`
                                    <span style="color: red;">❌ ${data.message}</span>
                                `);
                            }
                        });

                    } else if (result.success) {
                        // نمایش نتیجه موفقیت‌آمیز (محاسبه فوری)
                        clearInterval(timer_interval);
                        frappe.realtime.off('costing_progress');

                        $('#ultra-fast-progress-bar').css('width', '100%').css('background-color', '#21ba45');
                        $('#ultra-fast-progress-text').text('✅ کامل شد');
                        $('#ultra-fast-status-message').html(`
                            <span style="color: green; font-weight: bold;">✅ ${result.message}</span>
                        `);

                        // به‌روزرسانی صفحه بعد از 2 ثانیه
                        setTimeout(() => {
                            progress_dialog.hide();
                            frm.reload_doc();
                        }, 2000);

                    } else {
                        clearInterval(timer_interval);
                        frappe.realtime.off('costing_progress');

                        $('#ultra-fast-progress-bar').css('background-color', '#db2828');
                        $('#ultra-fast-status-message').html(`
                            <span style="color: red;">❌ ${result.message}</span>
                        `);
                    }
                }
            }).catch((error) => {
                console.error('⚡ Error in ultra fast costing:', error);

                // اگر به دلیل timeout خطا داد، ممکنه background job هنوز در حال اجرا باشه
                if (error.statusCode === 0 || error.message?.includes('timeout') || error.message?.includes('EMPTY_RESPONSE')) {
                    $('#ultra-fast-status-message').html(`
                        <span style="color: #2185d0;">⏳ محاسبه در پس‌زمینه ادامه دارد...</span><br>
                        <small>صفحه را refresh نکنید. پیشرفت بصورت خودکار نمایش داده میشه.</small>
                    `);

                    // گوش دادن به رویداد اتمام
                    frappe.realtime.on('costing_complete', function (data) {
                        console.log('⚡ Background costing complete after timeout:', data);

                        clearInterval(timer_interval);
                        frappe.realtime.off('costing_progress');
                        frappe.realtime.off('costing_complete');

                        if (data.success) {
                            $('#ultra-fast-progress-bar').css('width', '100%').css('background-color', '#21ba45');
                            $('#ultra-fast-progress-text').text('✅ کامل شد');
                            $('#ultra-fast-status-message').html(`
                                <span style="color: green; font-weight: bold;">✅ ${data.message}</span>
                            `);

                            setTimeout(() => {
                                progress_dialog.hide();
                                frm.reload_doc();
                            }, 2000);
                        } else {
                            $('#ultra-fast-progress-bar').css('background-color', '#db2828');
                            $('#ultra-fast-status-message').html(`
                                <span style="color: red;">❌ ${data.message}</span>
                            `);
                        }
                    });
                } else {
                    clearInterval(timer_interval);
                    frappe.realtime.off('costing_progress');

                    $('#ultra-fast-progress-bar').css('background-color', '#db2828');
                    $('#ultra-fast-status-message').html(`
                        <span style="color: red;">❌ خطا: ${error.message || String(error)}</span>
                    `);
                }
            });
        }
    );
}

function setup_background_progress_listener(frm) {
    // Listen for realtime progress updates
    frappe.realtime.on('costing_progress', function (data) {
        console.log('📡 Background progress:', data);

        if (data.status === 'started') {
            frappe.show_alert({
                message: '🚀 ' + data.message,
                indicator: 'blue'
            }, 5);
        } else if (data.status === 'completed') {
            frappe.show_alert({
                message: '✅ ' + data.message,
                indicator: 'green'
            }, 5);

            // Reload document
            frm.reload_doc();

            // Stop listening
            frappe.realtime.off('costing_progress');
        } else if (data.status === 'error') {
            frappe.show_alert({
                message: '❌ ' + data.message,
                indicator: 'red'
            }, 10);

            // Stop listening
            frappe.realtime.off('costing_progress');
        }
    });
}

// نمایش dialog با نتایج بهایابی
function show_costing_complete_dialog(frm, result) {
    // به‌روزرسانی صفحه اول
    frm.reload_doc().then(() => {
        // بعد از reload، نمایش dialog با نتایج
        let items = frm.doc.items || [];
        let total_items = items.length;
        let total_cost = items.reduce((sum, item) => sum + (item.total_cost || 0), 0);
        let total_raw_material = items.reduce((sum, item) => sum + (item.raw_material_cost || 0), 0);
        let total_operation = items.reduce((sum, item) => sum + (item.operation_cost || 0), 0);
        let total_overhead = items.reduce((sum, item) => sum + (item.overhead_cost || 0), 0);

        let html = `
            <div style="padding: 20px; direction: rtl; font-family: 'Vazir', Arial, sans-serif;">
                <div style="text-align: center; margin-bottom: 25px;">
                    <div style="font-size: 60px; margin-bottom: 10px;">✅</div>
                    <h2 style="color: #4CAF50; margin-bottom: 10px;">بهایابی با موفقیت انجام شد!</h2>
                    <p style="color: #666;">${result.message || 'محاسبه بهای تمام شده تکمیل شد'}</p>
                </div>
                
                <div style="background: #f8f9fa; padding: 20px; border-radius: 12px; margin-bottom: 20px;">
                    <h4 style="text-align: center; color: #333; margin-bottom: 20px;">📊 خلاصه نتایج</h4>
                    
                    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px;">
                        <div style="background: white; padding: 15px; border-radius: 8px; text-align: center; border-right: 4px solid #2196F3;">
                            <div style="color: #2196F3; font-size: 24px; font-weight: bold;">${total_items}</div>
                            <div style="color: #666; font-size: 14px;">تعداد کالاها</div>
                        </div>
                        <div style="background: white; padding: 15px; border-radius: 8px; text-align: center; border-right: 4px solid #4CAF50;">
                            <div style="color: #4CAF50; font-size: 18px; font-weight: bold;">${format_currency_safe(total_cost)}</div>
                            <div style="color: #666; font-size: 14px;">مجموع هزینه کل</div>
                        </div>
                    </div>
                    
                    <hr style="margin: 20px 0; border: none; border-top: 1px solid #ddd;">
                    
                    <h5 style="text-align: center; color: #555; margin-bottom: 15px;">تفکیک هزینه‌ها</h5>
                    
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">
                        <div style="background: #e3f2fd; padding: 12px; border-radius: 8px; text-align: center;">
                            <div style="color: #1976D2; font-size: 16px; font-weight: bold;">${format_currency_safe(total_raw_material)}</div>
                            <div style="color: #666; font-size: 12px;">💎 مواد اولیه</div>
                        </div>
                        <div style="background: #fff3e0; padding: 12px; border-radius: 8px; text-align: center;">
                            <div style="color: #E65100; font-size: 16px; font-weight: bold;">${format_currency_safe(total_operation)}</div>
                            <div style="color: #666; font-size: 12px;">🔧 عملیات</div>
                        </div>
                        <div style="background: #f3e5f5; padding: 12px; border-radius: 8px; text-align: center;">
                            <div style="color: #7B1FA2; font-size: 16px; font-weight: bold;">${format_currency_safe(total_overhead)}</div>
                            <div style="color: #666; font-size: 12px;">📊 سربار</div>
                        </div>
                    </div>
                </div>
                
                <div style="text-align: center; color: #888; font-size: 12px;">
                    ${result.updated_items ? '✅ ' + result.updated_items + ' کالا محاسبه شد' : ''}
                </div>
            </div>
        `;

        let dialog = new frappe.ui.Dialog({
            title: '🎉 بهایابی تکمیل شد',
            size: 'large',
            fields: [{
                fieldtype: 'HTML',
                fieldname: 'result_html'
            }],
            primary_action_label: __('بستن'),
            primary_action: function () {
                dialog.hide();
            }
        });

        dialog.fields_dict.result_html.$wrapper.html(html);
        dialog.show();
    });
}

function show_item_cost_breakdown_dialog(frm) {
    console.log('📊 show_item_cost_breakdown_dialog called');

    if (!frm.doc.items || frm.doc.items.length === 0) {
        frappe.msgprint(__('هیچ محصولی برای نمایش جزئیات هزینه وجود ندارد'));
        return;
    }

    // ایجاد لیست محصولات برای انتخاب
    let item_options = frm.doc.items.map(item => ({
        label: `${item.item_code} - ${item.item_name || item.item_code}`,
        value: item.item_code
    }));

    let dialog = new frappe.ui.Dialog({
        title: '📊 انتخاب محصول برای نمایش جزئیات هزینه',
        fields: [
            {
                fieldtype: 'Select',
                fieldname: 'selected_item',
                label: 'انتخاب محصول',
                options: item_options,
                reqd: 1
            },
            {
                fieldtype: 'Button',
                fieldname: 'show_breakdown',
                label: 'نمایش جزئیات هزینه'
            }
        ],
        primary_action_label: 'نمایش جزئیات',
        primary_action: function (values) {
            if (values.selected_item) {
                show_item_cost_breakdown(frm, values.selected_item);
                dialog.hide();
            }
        }
    });

    dialog.show();
}

function show_item_cost_breakdown(frm, item_code) {
    console.log('📊 Getting cost breakdown for item:', item_code);

    frappe.show_alert({
        message: 'در حال دریافت جزئیات هزینه...',
        indicator: 'blue'
    });

    frappe.call({
        method: 'get_item_cost_breakdown',
        doc: frm.doc,
        args: {
            item_code: item_code
        }
    }).then((response) => {
        console.log('✅ Cost breakdown response:', response);

        if (response && response.message && response.message.success) {
            const data = response.message;
            display_cost_breakdown_dialog(data);
        } else {
            frappe.msgprint({
                title: 'خطا',
                message: response.message?.message || 'خطا در دریافت جزئیات هزینه',
                indicator: 'red'
            });
        }
    }).catch((error) => {
        console.error('❌ Error getting cost breakdown:', error);
        frappe.msgprint({
            title: 'خطا',
            message: 'خطا در دریافت جزئیات هزینه: ' + (error.message || error),
            indicator: 'red'
        });
    });
}

function display_cost_breakdown_dialog(data) {
    console.log('📊 Displaying comprehensive cost breakdown for:', data.item_code);
    console.log('📊 Full data received:', data);
    console.log('📊 Raw materials count:', data.raw_materials_breakdown?.length || 0);
    console.log('📊 Operations count:', data.operations_breakdown?.length || 0);
    console.log('📊 First raw material:', data.raw_materials_breakdown?.[0]);
    console.log('📊 First operation:', data.operations_breakdown?.[0]);

    // ایجاد HTML برای نمایش جزئیات جامع
    let html = `
        <div style="padding: 20px; direction: rtl; font-family: 'Vazir', Arial, sans-serif;">
            <div style="margin-bottom: 20px; text-align: center;">
                <h2 style="color: #2196F3; margin-bottom: 10px;">
                    📊 گزارش جامع هزینه محصول (تمام سطوح BOM)
                </h2>
                <h3 style="color: #666; margin-bottom: 20px;">
                    ${data.item_code} - ${data.item_name}
                </h3>
                <p style="color: #888; font-size: 14px;">BOM اصلی: ${data.bom_name}</p>
            </div>
            
            <!-- خلاصه هزینه‌ها -->
            <div style="background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); padding: 20px; border-radius: 12px; margin-bottom: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                <h4 style="color: #333; margin-bottom: 20px; text-align: center;">💰 خلاصه کل هزینه‌ها (از تمام سطوح)</h4>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px;">
                    <div style="background: white; padding: 15px; border-radius: 8px; text-align: center;">
                        <div style="color: #4CAF50; font-size: 14px; margin-bottom: 5px;">💎 مواد اولیه (از exploded_items)</div>
                        <div style="font-size: 18px; font-weight: bold;">${format_currency(data.raw_material_cost)}</div>
                    </div>
                    <div style="background: white; padding: 15px; border-radius: 8px; text-align: center;">
                        <div style="color: #2196F3; font-size: 14px; margin-bottom: 5px;">🔧 عملیات (تمام سطوح)</div>
                        <div style="font-size: 18px; font-weight: bold;">${format_currency(data.total_operation_cost)}</div>
                    </div>
                    <div style="background: white; padding: 15px; border-radius: 8px; text-align: center;">
                        <div style="color: #FF9800; font-size: 14px; margin-bottom: 5px;">📊 سربار</div>
                        <div style="font-size: 18px; font-weight: bold;">${format_currency(data.overhead_cost)}</div>
                    </div>
                    <div style="background: #e8f5e8; padding: 15px; border-radius: 8px; text-align: center; grid-column: 1 / -1;">
                        <div style="color: #2E7D32; font-size: 16px; margin-bottom: 5px;">🎯 مجموع کل</div>
                        <div style="font-size: 24px; font-weight: bold; color: #1B5E20;">${format_currency(data.total_cost)}</div>
                    </div>
                </div>
            </div>
            
            <!-- تفکیک هزینه‌های عملیاتی -->
            <div style="background: #fff3e0; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                <h4 style="color: #333; margin-bottom: 15px;">⚡ تفکیک هزینه‌های عملیاتی</h4>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; font-size: 14px;">
                    <div>💡 برق: <strong>${format_currency(data.total_operation_costs.electricity_cost || 0)}</strong></div>
                    <div>🏠 اجاره: <strong>${format_currency(data.total_operation_costs.rent_cost || 0)}</strong></div>
                    <div>👷 کارگر: <strong>${format_currency(data.total_operation_costs.labor_cost || 0)}</strong></div>
                    <div>📦 مصرفی: <strong>${format_currency(data.total_operation_costs.consumable_cost || 0)}</strong></div>
                    <div>🔨 پیمانکاری: <strong>${format_currency(data.total_operation_costs.subcontracting_cost || 0)}</strong></div>
                </div>
            </div>
            
            <!-- جزئیات مواد اولیه -->
            <div style="margin-bottom: 20px;">
                <h4 style="color: #333; margin-bottom: 15px;">💎 جزئیات مواد اولیه</h4>
    `;

    if (data.raw_materials_breakdown && data.raw_materials_breakdown.length > 0) {
        html += `
                <div style="overflow-x: auto;">
                    <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                        <thead>
                            <tr style="background: #f5f5f5; border-bottom: 2px solid #ddd;">
                                <th style="padding: 10px; text-align: right;">کد ماده</th>
                                <th style="padding: 10px; text-align: right;">نام ماده</th>
                                <th style="padding: 10px; text-align: center;">مقدار</th>
                                <th style="padding: 10px; text-align: center;">واحد</th>
                                <th style="padding: 10px; text-align: center;">قیمت واحد</th>
                                <th style="padding: 10px; text-align: center;">قیمت کل</th>
                                <th style="padding: 10px; text-align: center;">منبع قیمت</th>
                            </tr>
                        </thead>
                        <tbody>
        `;

        data.raw_materials_breakdown.forEach((material, index) => {
            const rowColor = index % 2 === 0 ? '#fff' : '#f9f9f9';
            const priceSourceColor = material.price_source === "بدون قیمت" ? '#f44336' :
                material.price_source === "قیمت دستی" ? '#4CAF50' : '#2196F3';

            html += `
                            <tr style="background: ${rowColor}; border-bottom: 1px solid #eee;">
                                <td style="padding: 8px;">${material.item_code}</td>
                                <td style="padding: 8px;">${material.item_name}</td>
                                <td style="padding: 8px; text-align: center;">${material.qty.toFixed(2)}</td>
                                <td style="padding: 8px; text-align: center;">${material.uom}</td>
                                <td style="padding: 8px; text-align: center; direction: ltr;">${format_currency(material.unit_price)}</td>
                                <td style="padding: 8px; text-align: center; direction: ltr; font-weight: bold;">${format_currency(material.total_price)}</td>
                                <td style="padding: 8px; text-align: center;">
                                    <span style="background: ${priceSourceColor}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px;">
                                        ${material.price_source}
                                    </span>
                                </td>
                            </tr>
            `;
        });

        html += `
                        </tbody>
                        <tfoot>
                            <tr style="background: #e8f5e9; font-weight: bold; border-top: 2px solid #4CAF50;">
                                <td colspan="5" style="padding: 12px; text-align: left;">مجموع هزینه مواد اولیه:</td>
                                <td style="padding: 12px; text-align: center; direction: ltr; font-size: 16px;">${format_currency(data.raw_material_cost)}</td>
                                <td></td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
        `;
    } else {
        html += '<p style="color: #666; text-align: center; padding: 20px; background: #f5f5f5; border-radius: 8px;">هیچ ماده اولیه‌ای تعریف نشده است</p>';
    }

    html += '</div>';

    html += `
            <!-- جزئیات تمام عملیات (تمام سطوح) -->
            <div style="margin-bottom: 20px;">
                <h4 style="color: #333; margin-bottom: 15px;">🔧 جزئیات تمام عملیات (از تمام سطوح BOM)</h4>
    `;

    if (data.operations_breakdown && data.operations_breakdown.length > 0) {
        // گروه‌بندی عملیات بر اساس سطح
        const operationsByLevel = {};
        data.operations_breakdown.forEach(operation => {
            const level = operation.level || 0;
            if (!operationsByLevel[level]) {
                operationsByLevel[level] = [];
            }
            operationsByLevel[level].push(operation);
        });

        // نمایش عملیات بر اساس سطح
        Object.keys(operationsByLevel).sort().forEach(level => {
            const levelOperations = operationsByLevel[level];
            const levelColor = level == 0 ? '#e3f2fd' : level == 1 ? '#f3e5f5' : '#e8f5e8';

            html += `
                <div style="margin-bottom: 20px; border: 2px solid #ddd; border-radius: 10px; overflow: hidden;">
                    <div style="background: ${levelColor}; padding: 12px; font-weight: bold; text-align: center;">
                        📋 سطح ${level} ${level == 0 ? '(اصلی)' : '(فرعی)'}
                    </div>
            `;

            levelOperations.forEach((operation, index) => {
                const total_op_cost = Object.values(operation.costs).reduce((sum, cost) => sum + cost, 0);
                const qtyInfo = operation.qty_factor && operation.qty_factor !== 1 ?
                    ` (ضریب مقدار: ${operation.qty_factor})` : '';
                const parentInfo = operation.parent_item ?
                    `<div style="font-size: 12px; color: #666; margin-bottom: 5px;">🔗 جزء: ${operation.parent_item}</div>` : '';

                html += `
                    <div style="border-top: 1px solid #ddd; background: white;">
                        <div style="background: #f8f9fa; padding: 12px; border-bottom: 1px solid #eee;">
                            ${parentInfo}
                            <strong>${operation.operation}</strong>
                            ${operation.workstation ? ` - ${operation.workstation}` : ''}
                            <span style="float: left; color: #666;">
                                ${operation.time_in_mins || 0} دقیقه (${(operation.time_in_hours || 0).toFixed(2)} ساعت)${qtyInfo}
                            </span>
                            <div style="clear: both;"></div>
                            ${operation.bom_name ? `<div style="font-size: 11px; color: #888;">BOM: ${operation.bom_name}</div>` : ''}
                        </div>
                        <div style="padding: 12px;">
                            ${operation.description ? `<p style="color: #666; margin-bottom: 10px; font-style: italic;">${operation.description}</p>` : ''}
                            
                            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px; font-size: 13px; margin-bottom: 10px;">
                                <div style="background: #fff3e0; padding: 8px; border-radius: 4px;">💡 برق: ${format_currency((operation.costs && operation.costs.electricity_cost) || 0)}</div>
                                <div style="background: #e8f5e8; padding: 8px; border-radius: 4px;">🏠 اجاره: ${format_currency((operation.costs && operation.costs.rent_cost) || 0)}</div>
                                <div style="background: #e3f2fd; padding: 8px; border-radius: 4px;">👷 کارگر: ${format_currency((operation.costs && operation.costs.labor_cost) || 0)}</div>
                                <div style="background: #fce4ec; padding: 8px; border-radius: 4px;">📦 مصرفی: ${format_currency((operation.costs && operation.costs.consumable_cost) || 0)}</div>
                                <div style="background: #f3e5f5; padding: 8px; border-radius: 4px;">🔨 پیمانکاری: ${format_currency((operation.costs && operation.costs.subcontracting_cost) || 0)}</div>
                            </div>
                            
                            ${operation.workstation_rates && Object.keys(operation.workstation_rates).length > 0 ? `
                                <div style="margin-top: 10px; padding: 10px; background: #f8f9fa; border-radius: 6px; font-size: 12px; color: #666;">
                                    <strong>📊 نرخ‌های ساعتی workstation:</strong><br>
                                    برق: ${format_currency(operation.workstation_rates.hour_rate_electricity)}/ساعت، 
                                    اجاره: ${format_currency(operation.workstation_rates.hour_rate_rent)}/ساعت، 
                                    کارگر: ${format_currency(operation.workstation_rates.hour_rate_labour)}/ساعت، 
                                    مصرفی: ${format_currency(operation.workstation_rates.hour_rate_consumable)}/ساعت
                                </div>
                            ` : ''}
                            
                            <div style="text-align: left; margin-top: 15px; padding: 10px; background: linear-gradient(90deg, #e3f2fd, #bbdefb); border-radius: 6px;">
                                <strong style="color: #1976d2;">💰 مجموع این عملیات: ${format_currency(total_op_cost)}</strong>
                            </div>
                        </div>
                    </div>
                `;
            });

            html += '</div>';
        });
    } else {
        html += '<p style="color: #666; text-align: center; padding: 20px; background: #f5f5f5; border-radius: 8px;">هیچ عملیاتی در هیچ سطحی تعریف نشده است</p>';
    }

    html += '</div>';

    // نمایش ساختار سطوح BOM
    if (data.bom_levels && data.bom_levels.length > 0) {
        html += `
            <div style="margin-bottom: 20px;">
                <h4 style="color: #333; margin-bottom: 15px;">🏗️ ساختار سطوح BOM</h4>
        `;

        data.bom_levels.forEach(level_info => {
            const indentStyle = `margin-right: ${level_info.level * 20}px;`;
            const levelColor = level_info.level === 0 ? '#e8f5e8' : '#f0f4f8';

            html += `
                <div style="${indentStyle} border: 1px solid #ddd; border-radius: 8px; margin-bottom: 10px; background: ${levelColor};">
                    <div style="padding: 12px;">
                        <strong>📋 سطح ${level_info.level}: ${level_info.item_code}</strong> - ${level_info.item_name}
                        <div style="font-size: 12px; color: #666; margin-top: 5px;">BOM: ${level_info.bom_name}</div>
                        
                        ${level_info.sub_items && level_info.sub_items.length > 0 ? `
                            <div style="margin-top: 10px; font-size: 13px;">
                                <strong>اجزاء:</strong>
                                ${level_info.sub_items.map(sub_item =>
                `<span style="display: inline-block; margin: 2px 5px; padding: 2px 8px; background: white; border-radius: 4px; border: 1px solid #ddd;">
                                        ${sub_item.item_code} ${sub_item.has_bom ? '🔗' : '📦'} (${sub_item.qty})
                                    </span>`
            ).join('')}
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        });

        html += '</div>';
    }

    html += '</div>';

    // نمایش دیالوگ
    let breakdown_dialog = new frappe.ui.Dialog({
        title: `📊 گزارش جامع هزینه: ${data.item_code}`,
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'breakdown_html'
            }
        ],
        size: 'extra-large'
    });

    breakdown_dialog.fields_dict.breakdown_html.$wrapper.html(html);
    breakdown_dialog.show();
}

// ==================== فیلتر و مرتب‌سازی پیشرفته ====================

function apply_advanced_filters(frm) {
    /**
     * اعمال فیلترهای پیشرفته به جدول items
     */
    if (!frm.doc.items || frm.doc.items.length === 0) {
        frappe.msgprint(__('هیچ کالایی برای فیلتر کردن وجود ندارد'));
        return;
    }

    // ذخیره کپی از items اصلی اگر وجود ندارد
    if (!frm._original_items) {
        frm._original_items = JSON.parse(JSON.stringify(frm.doc.items));
    }

    let filtered_items = [...frm._original_items];
    let filter_count = 0;

    // 1. فیلتر نام کالا
    if (frm.doc.filter_item_name && frm.doc.filter_item_name.trim()) {
        const search_terms = frm.doc.filter_item_name.split(',').map(term => term.trim().toLowerCase());
        filtered_items = filtered_items.filter(item => {
            const item_name = (item.item_name || '').toLowerCase();
            const item_code = (item.item_code || '').toLowerCase();
            return search_terms.some(term =>
                item_name.includes(term) || item_code.includes(term)
            );
        });
        filter_count++;
    }

    // 2. فیلتر گروه کالا
    if (frm.doc.filter_item_group && frm.doc.filter_item_group.length > 0) {
        const selected_groups = frm.doc.filter_item_group;
        filtered_items = filtered_items.filter(item =>
            selected_groups.includes(item.item_group)
        );
        filter_count++;
    }

    // 3. فیلتر برند
    if (frm.doc.filter_brand && frm.doc.filter_brand.length > 0) {
        const selected_brands = frm.doc.filter_brand;
        filtered_items = filtered_items.filter(item =>
            selected_brands.includes(item.brand)
        );
        filter_count++;
    }

    // 4. فیلتر انبار
    if (frm.doc.filter_warehouse && frm.doc.filter_warehouse.length > 0) {
        const selected_warehouses = frm.doc.filter_warehouse;
        filtered_items = filtered_items.filter(item =>
            selected_warehouses.includes(item.warehouse)
        );
        filter_count++;
    }

    // 5. فیلتر وضعیت BOM
    if (frm.doc.filter_bom_status) {
        // دریافت وضعیت BOM برای فیلتر کردن
        frappe.call({
            method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.get_items_bom_status',
            args: {
                doctype: frm.doc.doctype,
                name: frm.doc.name
            }
        }).then(r => {
            if (r.message) {
                const items_without_bom = new Set((r.message.items_without_bom || []).map(item => item.item_code));
                const items_with_unsubmitted_bom = new Set((r.message.items_with_unsubmitted_bom || []).map(item => item.item_code));

                if (frm.doc.filter_bom_status === 'بدون BOM') {
                    filtered_items = filtered_items.filter(item => items_without_bom.has(item.item_code));
                } else if (frm.doc.filter_bom_status === 'با BOM ارسال نشده') {
                    filtered_items = filtered_items.filter(item => items_with_unsubmitted_bom.has(item.item_code));
                } else if (frm.doc.filter_bom_status === 'با BOM ارسال شده') {
                    filtered_items = filtered_items.filter(item =>
                        !items_without_bom.has(item.item_code) && !items_with_unsubmitted_bom.has(item.item_code)
                    );
                }

                // ادامه پردازش با مرتب‌سازی
                finish_filtering_and_sorting(frm, filtered_items, filter_count + 1);
            }
        });
        return; // خروج زودهنگام چون async است
    }

    // اگر فیلتر BOM نداشتیم، مستقیماً ادامه می‌دهیم
    finish_filtering_and_sorting(frm, filtered_items, filter_count);
}

function finish_filtering_and_sorting(frm, filtered_items, filter_count) {
    /**
     * تکمیل فیلتر و اعمال مرتب‌سازی
     */

    // 6. مرتب‌سازی
    if (frm.doc.sort_by_field) {
        const sort_field = frm.doc.sort_by_field;
        const sort_order = frm.doc.sort_order || 'صعودی';
        const ascending = sort_order === 'صعودی';

        filtered_items.sort((a, b) => {
            let valueA, valueB;

            switch (sort_field) {
                case 'نام کالا':
                    valueA = (a.item_name || '').toLowerCase();
                    valueB = (b.item_name || '').toLowerCase();
                    break;
                case 'گروه کالا':
                    valueA = (a.item_group || '').toLowerCase();
                    valueB = (b.item_group || '').toLowerCase();
                    break;
                case 'برند':
                    valueA = (a.brand || '').toLowerCase();
                    valueB = (b.brand || '').toLowerCase();
                    break;
                case 'هزینه کل':
                    valueA = parseFloat(a.total_cost || 0);
                    valueB = parseFloat(b.total_cost || 0);
                    break;
                case 'قیمت فروش':
                    valueA = parseFloat(a.selling_price || 0);
                    valueB = parseFloat(b.selling_price || 0);
                    break;
                case 'سود':
                    valueA = parseFloat(a.profit_amount || 0);
                    valueB = parseFloat(b.profit_amount || 0);
                    break;
                case 'درصد سود':
                    valueA = parseFloat(a.profit_percentage || 0);
                    valueB = parseFloat(b.profit_percentage || 0);
                    break;
                default:
                    valueA = (a.item_name || '').toLowerCase();
                    valueB = (b.item_name || '').toLowerCase();
                    // Server-side filter implementation to prevent 413 and lag
                    frappe.call({
                        method: 'apply_filters_server_side',
                        doc: frm.doc,
                        freeze: true,
                        freeze_message: __('در حال اعمال فیلترها (سرور)...'),
                        callback: function (r) {
                            if (r.message && r.message.success) {
                                frappe.show_alert({
                                    message: r.message.message,
                                    indicator: 'green'
                                });
                                frm.reload_doc();
                            }
                        }
                    });
            }
        });

        function clear_advanced_filters(frm) {
            /**
             * پاک کردن تمام فیلترها و بازگردانی items اصلی
             */

            // پاک کردن فیلدهای فیلتر
            frm.set_value('filter_item_name', '');
            frm.set_value('filter_item_group', []);
            frm.set_value('filter_brand', []);
            frm.set_value('filter_warehouse', []);
            frm.set_value('filter_bom_status', '');
            frm.set_value('sort_by_field', '');
            frm.set_value('sort_order', 'صعودی');

            // بازگردانی items اصلی
            if (frm._original_items) {
                frm.clear_table('items');
                frm._original_items.forEach(item => {
                    frm.add_child('items', item);
                });

                frm.refresh_field('items');
                frm.dirty();

                frappe.show_alert({
                    message: `تمام فیلترها پاک شدند - ${frm._original_items.length} کالا نمایش داده می‌شود`,
                    indicator: 'blue'
                });
            } else {
                frappe.show_alert({
                    message: 'هیچ فیلتری برای پاک کردن وجود ندارد',
                    indicator: 'yellow'
                });
            }
        }

        // ==================== قیمت‌گذاری دستی ====================

        function add_filtered_items_to_bulk_pricing(frm) {
            /**
             * اضافه کردن کالاهای فیلتر شده به جدول قیمت‌گذاری دستی
             */
            if (!frm.doc.items || frm.doc.items.length === 0) {
                frappe.msgprint(__('هیچ کالایی در جدول items وجود ندارد'));
                return;
            }

            // فیلتر کردن items بر اساس فیلترهای bulk pricing
            let filtered_items = [...frm.doc.items];
            let filter_count = 0;

            // 1. فیلتر نام کالا
            if (frm.doc.bulk_filter_item_name && frm.doc.bulk_filter_item_name.trim()) {
                const search_terms = frm.doc.bulk_filter_item_name.split(',').map(term => term.trim().toLowerCase());
                filtered_items = filtered_items.filter(item => {
                    const item_name = (item.item_name || '').toLowerCase();
                    const item_code = (item.item_code || '').toLowerCase();
                    return search_terms.some(term =>
                        item_name.includes(term) || item_code.includes(term)
                    );
                });
                filter_count++;
            }

            // 2. فیلتر گروه کالا
            if (frm.doc.bulk_filter_item_group) {
                filtered_items = filtered_items.filter(item =>
                    item.item_group === frm.doc.bulk_filter_item_group
                );
                filter_count++;
            }

            // 3. فیلتر برند
            if (frm.doc.bulk_filter_brand) {
                filtered_items = filtered_items.filter(item =>
                    item.brand === frm.doc.bulk_filter_brand
                );
                filter_count++;
            }

            // 4. فیلتر انبار
            if (frm.doc.bulk_filter_warehouse) {
                filtered_items = filtered_items.filter(item =>
                    item.warehouse === frm.doc.bulk_filter_warehouse
                );
                filter_count++;
            }

            // 5. فیلتر وضعیت BOM
            if (frm.doc.bulk_filter_bom_status) {
                // دریافت وضعیت BOM برای فیلتر کردن
                frappe.call({
                    method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.get_items_bom_status',
                    args: {
                        doctype: frm.doc.doctype,
                        name: frm.doc.name
                    }
                }).then(r => {
                    if (r.message) {
                        const items_without_bom = new Set((r.message.items_without_bom || []).map(item => item.item_code));
                        const items_with_unsubmitted_bom = new Set((r.message.items_with_unsubmitted_bom || []).map(item => item.item_code));

                        if (frm.doc.bulk_filter_bom_status === 'بدون BOM') {
                            filtered_items = filtered_items.filter(item => items_without_bom.has(item.item_code));
                        } else if (frm.doc.bulk_filter_bom_status === 'با BOM ارسال نشده') {
                            filtered_items = filtered_items.filter(item => items_with_unsubmitted_bom.has(item.item_code));
                        } else if (frm.doc.bulk_filter_bom_status === 'با BOM ارسال شده') {
                            filtered_items = filtered_items.filter(item =>
                                !items_without_bom.has(item.item_code) && !items_with_unsubmitted_bom.has(item.item_code)
                            );
                        }

                        // ادامه پردازش
                        finish_adding_bulk_items(frm, filtered_items, filter_count + 1);
                    }
                });
                return; // خروج زودهنگام چون async است
            }

            // function add_filtered_items_to_bulk_pricing(frm) {
            //     // Replaced by server-side logic in 'bulk_pricing_items_on_form_rendered' or button
            //     frappe.call({
            //         method: 'add_bulk_items_server_side',
            //         doc: frm.doc,
            //         freeze: true,
            //         freeze_message: __('در حال جستجو و افزودن کالاها...'),
            //         callback: function(r) {
            //              if (r.message && r.message.success) {
            //                 frappe.show_alert({message: r.message.message, indicator: 'green'});
            //                 frm.reload_doc();
            //              }
            //         }
            //     });
            // }
            function add_filtered_items_to_bulk_pricing(frm) {
                frappe.call({
                    method: 'add_bulk_items_server_side',
                    doc: frm.doc,
                    freeze: true,
                    freeze_message: __('در حال افزودن کالاها به لیست دستی...'),
                    callback: function (r) {
                        if (r.message && r.message.success) {
                            frappe.show_alert({ message: r.message.message, indicator: 'green' });
                            frm.reload_doc();
                        }
                    }
                });
            }

            function finish_adding_bulk_items(frm, filtered_items, filter_count) {
                /**
                 * تکمیل اضافه کردن کالاها به جدول bulk pricing
                 */

                if (filtered_items.length === 0) {
                    frappe.msgprint(__('هیچ کالایی با فیلترهای انتخاب شده پیدا نشد'));
                    return;
                }

                // بررسی کالاهای تکراری
                const existing_items = new Set((frm.doc.bulk_pricing_items || []).map(item => item.item_code));
                let added_count = 0;
                let duplicate_count = 0;

                filtered_items.forEach(item => {
                    if (!existing_items.has(item.item_code)) {
                        const bulk_item = frm.add_child('bulk_pricing_items');
                        bulk_item.selected = 1; // انتخاب پیش‌فرض
                        bulk_item.item_code = item.item_code;
                        bulk_item.item_name = item.item_name;
                        bulk_item.item_group = item.item_group;
                        bulk_item.brand = item.brand;
                        bulk_item.warehouse = item.warehouse;
                        bulk_item.total_cost = item.total_cost || 0;
                        bulk_item.electricity_cost = item.electricity_cost || 0;
                        bulk_item.consumable_cost = item.consumable_cost || 0;
                        bulk_item.rent_cost = item.rent_cost || 0;
                        bulk_item.labor_cost = item.labor_cost || 0;
                        bulk_item.subcontracting_cost = item.subcontracting_cost || 0;
                        bulk_item.overhead_cost = item.overhead_cost || 0;

                        added_count++;
                    } else {
                        duplicate_count++;
                    }
                });

                frm.refresh_field('bulk_pricing_items');
                frm.dirty();

                // نمایش پیام نتیجه
                let message = `${added_count} کالا به جدول قیمت‌گذاری دستی اضافه شد`;
                if (filter_count > 0) {
                    message += ` (${filter_count} فیلتر اعمال شد)`;
                }
                if (duplicate_count > 0) {
                    message += ` - ${duplicate_count} کالا تکراری بود`;
                }

                frappe.show_alert({
                    message: message,
                    indicator: added_count > 0 ? 'green' : 'orange'
                });
            }

            function apply_bulk_pricing_changes(frm) {
                /**
                 * اعمال قیمت‌های دستی از جدول manual_item_prices به جدول items اصلی
                 * و محاسبه مجدد بهای تمام شده
                 */

                if (!frm.doc.manual_item_prices || frm.doc.manual_item_prices.length === 0) {
                    frappe.msgprint(__('هیچ قیمت دستی‌ای در جدول manual_item_prices وجود ندارد'));
                    return;
                }

                frappe.confirm(
                    'آیا می‌خواهید قیمت‌های دستی را به جدول محصولات اعمال کنید؟<br>' +
                    '<small>• قیمت‌های دستی جایگزین قیمت‌های محاسبه شده خواهند شد<br>' +
                    '• بهای تمام شده مجدداً محاسبه خواهد شد</small>',
                    function () {
                        console.log('🚀 User confirmed, applying manual prices...');

                        frappe.show_alert({
                            message: '📊 در حال اعمال قیمت‌های دستی...',
                            indicator: 'blue'
                        });

                        // ایجاد نقشه قیمت‌های دستی
                        const manual_prices_map = {};
                        frm.doc.manual_item_prices.forEach(manual_item => {
                            manual_prices_map[manual_item.item_code] = manual_item;
                        });

                        let updated_count = 0;
                        let updated_items = [];

                        // اعمال قیمت‌های دستی به جدول items
                        frm.doc.items.forEach(item => {
                            const manual_price = manual_prices_map[item.item_code];
                            if (manual_price) {
                                let item_updated = false;

                                // اعمال قیمت‌های دستی
                                if (manual_price.manual_raw_material_cost && manual_price.manual_raw_material_cost > 0) {
                                    item.raw_material_cost = manual_price.manual_raw_material_cost;
                                    item_updated = true;
                                }

                                if (manual_price.manual_operation_cost && manual_price.manual_operation_cost > 0) {
                                    item.operation_cost = manual_price.manual_operation_cost;
                                    item_updated = true;
                                }

                                if (manual_price.manual_overhead_cost && manual_price.manual_overhead_cost > 0) {
                                    item.overhead_cost = manual_price.manual_overhead_cost;
                                    item_updated = true;
                                }

                                // اعمال هزینه‌های جزئی اگر موجود باشند
                                if (manual_price.manual_subcontracting_cost && manual_price.manual_subcontracting_cost > 0) {
                                    item.subcontracting_cost = manual_price.manual_subcontracting_cost;
                                    item_updated = true;
                                }

                                if (manual_price.manual_labor_cost && manual_price.manual_labor_cost > 0) {
                                    item.labor_cost = manual_price.manual_labor_cost;
                                    item_updated = true;
                                }

                                if (manual_price.manual_electricity_cost && manual_price.manual_electricity_cost > 0) {
                                    item.electricity_cost = manual_price.manual_electricity_cost;
                                    item_updated = true;
                                }

                                if (manual_price.manual_consumable_cost && manual_price.manual_consumable_cost > 0) {
                                    item.consumable_cost = manual_price.manual_consumable_cost;
                                    item_updated = true;
                                }

                                if (manual_price.manual_rent_cost && manual_price.manual_rent_cost > 0) {
                                    item.rent_cost = manual_price.manual_rent_cost;
                                    item_updated = true;
                                }

                                // محاسبه مجدد هزینه کل عملیات
                                if (item_updated) {
                                    item.operation_cost = (item.electricity_cost || 0) +
                                        (item.consumable_cost || 0) +
                                        (item.rent_cost || 0) +
                                        (item.labor_cost || 0) +
                                        (item.subcontracting_cost || 0);

                                    // محاسبه مجدد هزینه کل
                                    item.total_cost = (item.raw_material_cost || 0) +
                                        (item.operation_cost || 0) +
                                        (item.overhead_cost || 0);

                                    updated_count++;
                                    updated_items.push(item.item_code);

                                    console.log('✅ Updated ' + item.item_code + ': total_cost=' + item.total_cost.toLocaleString());
                                }
                            }
                        });

                        frm.refresh_field('items');
                        frm.dirty();

                        // نمایش پیام موفقیت
                        frappe.show_alert({
                            message: '✅ ' + updated_count + ' محصول با قیمت‌های دستی به‌روزرسانی شد',
                            indicator: 'green'
                        });

                        // محاسبه مجدد قیمت‌های نهایی
                        console.log('🔄 Recalculating final prices...');
                        frm.call('calculate_item_prices').then(() => {
                            frappe.show_alert({
                                message: '🎯 قیمت‌های نهایی با در نظر گیری قیمت‌های دستی محاسبه شدند',
                                indicator: 'blue'
                            });
                        });
                    }
                );
            }

            function clear_bulk_pricing_table(frm) {
                /**
                 * پاک کردن جدول قیمت‌گذاری دستی
                 */

                if (!frm.doc.bulk_pricing_items || frm.doc.bulk_pricing_items.length === 0) {
                    frappe.show_alert({
                        message: 'جدول قیمت‌گذاری دستی خالی است',
                        indicator: 'yellow'
                    });
                    return;
                }

                frappe.confirm(
                    __('آیا مطمئن هستید که می‌خواهید تمام کالاهای جدول قیمت‌گذاری دستی را پاک کنید؟'),
                    function () {
                        const item_count = frm.doc.bulk_pricing_items.length;
                        frm.clear_table('bulk_pricing_items');
                        frm.refresh_field('bulk_pricing_items');
                        frm.dirty();

                        frappe.show_alert({
                            message: `${item_count} کالا از جدول قیمت‌گذاری دستی پاک شد`,
                            indicator: 'blue'
                        });
                    }
                );
            }

            function select_all_bulk_items(frm, select_value) {
                /**
                 * انتخاب یا لغو انتخاب همه کالاهای bulk pricing
                 */

                if (!frm.doc.bulk_pricing_items || frm.doc.bulk_pricing_items.length === 0) {
                    frappe.show_alert({
                        message: 'هیچ کالایی در جدول قیمت‌گذاری دستی وجود ندارد',
                        indicator: 'yellow'
                    });
                    return;
                }

                let changed_count = 0;
                frm.doc.bulk_pricing_items.forEach(item => {
                    if (item.selected !== select_value) {
                        item.selected = select_value;
                        changed_count++;
                    }
                });

                frm.refresh_field('bulk_pricing_items');
                frm.dirty();

                const action = select_value ? 'انتخاب' : 'لغو انتخاب';
                frappe.show_alert({
                    message: `${changed_count} کالا ${action} شد`,
                    indicator: select_value ? 'green' : 'blue'
                });
            }

            // ==================== تحلیل نقطه سر به سر ====================

            function calculate_break_even_analysis(frm) {
                /**
                 * محاسبه تحلیل نقطه سر به سر و نمودار سودآوری
                 */

                if (!frm.doc.items || frm.doc.items.length === 0) {
                    return;
                }

                // محاسبه آمارهای کلی
                let total_cost = 0;
                let total_selling_price = 0;
                let total_profit = 0;
                let total_markup = 0;

                frm.doc.items.forEach(item => {
                    total_cost += (item.total_cost || 0);
                    total_selling_price += (item.final_selected_price || item.selling_price || 0);
                    const real_profit = (item.final_selected_price || item.selling_price || 0) - (item.total_cost || 0) - (item.required_markup_amount || 0);
                    total_profit += real_profit;
                    total_markup += (item.required_markup_amount || 0);
                });

                // محاسبه میانگین حاشیه سود واقعی (بر اساس هزینه)
                const average_margin = total_cost > 0 ? (total_profit / total_cost) * 100 : 0;

                // محاسبه نقطه سر به سر
                const monthly_fixed_costs = frm.doc.monthly_fixed_costs || 0;
                const break_even_point = average_margin > 0 ? (monthly_fixed_costs / (average_margin / 100)) : 0;

                // محاسبه سود پس از رسیدن به هدف
                const target_revenue = frm.doc.target_monthly_revenue || 0;
                const profit_after_target = target_revenue > break_even_point ?
                    (target_revenue - break_even_point) * (average_margin / 100) : 0;

                // به‌روزرسانی فیلدها
                frm.set_value('break_even_point', break_even_point);
                frm.set_value('profit_after_breakeven', profit_after_target);

                // رندر نمودار
                render_break_even_chart(frm, {
                    break_even_point: break_even_point,
                    target_revenue: target_revenue,
                    monthly_fixed_costs: monthly_fixed_costs,
                    average_margin: average_margin,
                    profit_after_target: profit_after_target
                });
            }

            function render_break_even_chart(frm, data) {
                /**
                 * رندر نمودار نقطه سر به سر
                 */

                const chart_data = [];
                const max_revenue = Math.max(data.target_revenue, data.break_even_point) * 1.5;
                const step = max_revenue / 20;

                // ایجاد داده‌های نمودار
                for (let revenue = 0; revenue <= max_revenue; revenue += step) {
                    const profit = revenue > data.break_even_point ?
                        (revenue - data.break_even_point) * (data.average_margin / 100) - data.monthly_fixed_costs :
                        -data.monthly_fixed_costs;

                    chart_data.push({
                        revenue: revenue / 1000000000, // تبدیل به میلیارد ریال
                        profit: profit / 1000000000,
                        break_even: 0
                    });
                }

                const html = `
        <div class="break-even-analysis" style="padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; margin: 10px 0;">
            <div class="row">
                <div class="col-md-6">
                    <div class="metric-card" style="background: rgba(255,255,255,0.95); padding: 20px; border-radius: 12px; margin-bottom: 15px; box-shadow: 0 8px 32px rgba(0,0,0,0.1);">
                        <h4 style="color: #2c3e50; margin-bottom: 15px; display: flex; align-items: center;">
                            <i class="fa fa-chart-line" style="margin-left: 10px; color: #3498db;"></i>
                            تحلیل نقطه سر به سر
                        </h4>
                        <div class="metric-row" style="display: flex; justify-content: space-between; margin-bottom: 12px; padding: 8px 0; border-bottom: 1px solid #ecf0f1;">
                            <span style="color: #7f8c8d; font-weight: 500;">نقطه سر به سر:</span>
                            <span style="color: #e74c3c; font-weight: bold;">${format_currency(data.break_even_point)} ریال</span>
                        </div>
                        <div class="metric-row" style="display: flex; justify-content: space-between; margin-bottom: 12px; padding: 8px 0; border-bottom: 1px solid #ecf0f1;">
                            <span style="color: #7f8c8d; font-weight: 500;">هدف فروش ماهانه:</span>
                            <span style="color: #3498db; font-weight: bold;">${format_currency(data.target_revenue)} ریال</span>
                        </div>
                        <div class="metric-row" style="display: flex; justify-content: space-between; margin-bottom: 12px; padding: 8px 0; border-bottom: 1px solid #ecf0f1;">
                            <span style="color: #7f8c8d; font-weight: 500;">میانگین حاشیه سود:</span>
                            <span style="color: #27ae60; font-weight: bold;">${data.average_margin.toFixed(1)}%</span>
                        </div>
                        <div class="metric-row" style="display: flex; justify-content: space-between; margin-bottom: 12px; padding: 8px 0;">
                            <span style="color: #7f8c8d; font-weight: 500;">سود پس از رسیدن به هدف:</span>
                            <span style="color: ${data.profit_after_target > 0 ? '#27ae60' : '#e74c3c'}; font-weight: bold;">${format_currency(data.profit_after_target)} ریال</span>
                        </div>
                    </div>
                    
                    <div class="status-card" style="background: rgba(255,255,255,0.95); padding: 20px; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.1);">
                        <h5 style="color: #2c3e50; margin-bottom: 15px;">وضعیت فعلی:</h5>
                        ${data.target_revenue > data.break_even_point ?
                        `<div style="color: #27ae60; font-weight: bold; display: flex; align-items: center;">
                                <i class="fa fa-check-circle" style="margin-left: 8px;"></i>
                                هدف شما بالاتر از نقطه سر به سر است ✅
                            </div>
                            <p style="color: #7f8c8d; margin-top: 10px; font-size: 14px;">
                                با رسیدن به هدف ${format_currency(data.target_revenue)} ریال، 
                                سود ${format_currency(data.profit_after_target)} ریال خواهید داشت.
                            </p>` :
                        `<div style="color: #e74c3c; font-weight: bold; display: flex; align-items: center;">
                                <i class="fa fa-exclamation-triangle" style="margin-left: 8px;"></i>
                                هدف شما کمتر از نقطه سر به سر است ⚠️
                            </div>
                            <p style="color: #7f8c8d; margin-top: 10px; font-size: 14px;">
                                برای سودآوری، باید فروش ماهانه حداقل ${format_currency(data.break_even_point)} ریال باشد.
                            </p>`
                    }
                    </div>
                </div>
                
                <div class="col-md-6">
                    <div class="chart-container" style="background: rgba(255,255,255,0.95); padding: 20px; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.1); height: 280px; overflow: hidden;">
                        <h5 style="color: #2c3e50; margin-bottom: 15px; text-align: center;">نمودار سودآوری</h5>
                        <div style="height: 220px; position: relative;">
                            <canvas id="break-even-chart" width="400" height="200" style="max-width: 100%; max-height: 200px;"></canvas>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="recommendations" style="background: rgba(255,255,255,0.95); padding: 20px; border-radius: 12px; margin-top: 15px; box-shadow: 0 8px 32px rgba(0,0,0,0.1);">
                <h5 style="color: #2c3e50; margin-bottom: 15px; display: flex; align-items: center;">
                    <i class="fa fa-lightbulb" style="margin-left: 10px; color: #f39c12;"></i>
                    توصیه‌های بهبود
                </h5>
                <div class="row">
                    <div class="col-md-4">
                        <div style="text-align: center; padding: 15px;">
                            <i class="fa fa-arrow-up" style="font-size: 24px; color: #27ae60; margin-bottom: 10px;"></i>
                            <h6 style="color: #2c3e50;">افزایش حاشیه سود</h6>
                            <p style="color: #7f8c8d; font-size: 12px;">بهینه‌سازی قیمت‌ها و کاهش هزینه‌ها</p>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div style="text-align: center; padding: 15px;">
                            <i class="fa fa-chart-line" style="font-size: 24px; color: #3498db; margin-bottom: 10px;"></i>
                            <h6 style="color: #2c3e50;">افزایش فروش</h6>
                            <p style="color: #7f8c8d; font-size: 12px;">بازاریابی و توسعه محصولات جدید</p>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div style="text-align: center; padding: 15px;">
                            <i class="fa fa-cut" style="font-size: 24px; color: #e74c3c; margin-bottom: 10px;"></i>
                            <h6 style="color: #2c3e50;">کاهش هزینه‌های ثابت</h6>
                            <p style="color: #7f8c8d; font-size: 12px;">بهینه‌سازی عملیات و منابع</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

                frm.fields_dict.break_even_chart_html.$wrapper.html(html);

                // رندر نمودار با Chart.js
                setTimeout(() => {
                    render_chart_js(chart_data, data);
                }, 100);
            }

            function render_chart_js(chart_data, analysis_data) {
                /**
                 * رندر نمودار با Chart.js
                 */

                const canvas = document.getElementById('break-even-chart');
                if (!canvas) return;

                // تنظیم اندازه ثابت canvas
                canvas.width = 400;
                canvas.height = 200;
                canvas.style.width = '100%';
                canvas.style.height = '200px';
                canvas.style.maxWidth = '400px';
                canvas.style.maxHeight = '200px';

                const ctx = canvas.getContext('2d');

                // پاک کردن نمودار قبلی
                if (window.breakEvenChart) {
                    window.breakEvenChart.destroy();
                }

                window.breakEvenChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: chart_data.map(d => d.revenue.toFixed(1) + 'B'),
                        datasets: [
                            {
                                label: 'سود (میلیارد ریال)',
                                data: chart_data.map(d => d.profit),
                                borderColor: '#27ae60',
                                backgroundColor: 'rgba(39, 174, 96, 0.1)',
                                borderWidth: 3,
                                fill: true,
                                tension: 0.4
                            },
                            {
                                label: 'نقطه سر به سر',
                                data: chart_data.map(d => d.break_even),
                                borderColor: '#e74c3c',
                                backgroundColor: 'transparent',
                                borderWidth: 2,
                                borderDash: [5, 5],
                                pointRadius: 0
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: true,
                        aspectRatio: 2,
                        plugins: {
                            legend: {
                                position: 'top',
                                labels: {
                                    usePointStyle: true,
                                    font: {
                                        family: 'Vazir, sans-serif',
                                        size: 12
                                    }
                                }
                            },
                            tooltip: {
                                mode: 'index',
                                intersect: false,
                                titleFont: {
                                    family: 'Vazir, sans-serif'
                                },
                                bodyFont: {
                                    family: 'Vazir, sans-serif'
                                },
                                callbacks: {
                                    label: function (context) {
                                        if (context.datasetIndex === 0) {
                                            return `سود: ${context.parsed.y.toFixed(2)} میلیارد ریال`;
                                        }
                                        return context.dataset.label;
                                    }
                                }
                            }
                        },
                        scales: {
                            x: {
                                display: true,
                                title: {
                                    display: true,
                                    text: 'فروش (میلیارد ریال)',
                                    font: {
                                        family: 'Vazir, sans-serif',
                                        size: 14
                                    }
                                },
                                ticks: {
                                    font: {
                                        family: 'Vazir, sans-serif'
                                    }
                                }
                            },
                            y: {
                                display: true,
                                title: {
                                    display: true,
                                    text: 'سود (میلیارد ریال)',
                                    font: {
                                        family: 'Vazir, sans-serif',
                                        size: 14
                                    }
                                },
                                ticks: {
                                    font: {
                                        family: 'Vazir, sans-serif'
                                    }
                                }
                            }
                        },
                        interaction: {
                            mode: 'nearest',
                            axis: 'x',
                            intersect: false
                        }
                    }
                });
            }

            // ==================== بارگذاری خودکار هزینه‌های ثابت ====================

            function load_automatic_fixed_costs(frm) {
                /**
                 * بارگذاری خودکار هزینه‌های ثابت ماهانه از حسابداری ERPNext
                 */

                frappe.show_alert({
                    message: 'در حال بارگذاری هزینه‌های ثابت از حسابداری...',
                    indicator: 'blue'
                });

                frappe.call({
                    method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.get_automatic_fixed_costs',
                    args: {
                        doctype: frm.doc.doctype,
                        name: frm.doc.name
                    },
                    callback: function (r) {
                        if (r.message !== undefined) {
                            const fixed_costs = r.message;

                            if (fixed_costs > 0) {
                                // به‌روزرسانی فیلد
                                frm.set_value('monthly_fixed_costs', fixed_costs);

                                // نمایش پیام موفقیت
                                const formatted_amount = format_currency(fixed_costs);
                                frappe.show_alert({
                                    message: `هزینه‌های ثابت ماهانه بارگذاری شد: ${formatted_amount} ریال`,
                                    indicator: 'green'
                                });

                                // محاسبه مجدد تحلیل نقطه سر به سر
                                calculate_break_even_analysis(frm);

                                // نمایش جزئیات در dialog
                                show_fixed_costs_breakdown_dialog(frm, fixed_costs);
                            } else {
                                frappe.confirm(
                                    __('هزینه‌های ثابت یافت نشد. آیا می‌خواهید تنظیمات هزینه‌های ثابت را پیکربندی کنید؟'),
                                    function () {
                                        // باز کردن تنظیمات هزینه‌های ثابت
                                        frappe.set_route('Form', 'Fixed Costs Settings', 'Fixed Costs Settings');
                                    },
                                    function () {
                                        frappe.msgprint({
                                            title: __('راه‌حل‌های جایگزین'),
                                            message: __(`
                                    <div style="padding: 15px;">
                                        <h5>دلایل احتمالی:</h5>
                                        <ul>
                                            <li>حساب‌های هزینه ثابت تعریف نشده‌اند</li>
                                            <li>تراکنش‌های مالی برای ماه گذشته وجود ندارند</li>
                                            <li>تنظیمات هزینه‌های ثابت پیکربندی نشده</li>
                                        </ul>
                                        <h5>راه‌حل‌های پیشنهادی:</h5>
                                        <ul>
                                            <li><strong>تنظیمات هزینه‌های ثابت:</strong> از منو Setup > Fixed Costs Settings</li>
                                            <li><strong>ثبت تراکنش‌ها:</strong> تراکنش‌های مالی ماه گذشته را ثبت کنید</li>
                                            <li><strong>ورود دستی:</strong> مقدار را به صورت دستی وارد کنید</li>
                                        </ul>
                                    </div>
                                `),
                                            indicator: 'yellow'
                                        });
                                    }
                                );
                            }
                        } else {
                            frappe.show_alert({
                                message: 'خطا در بارگذاری هزینه‌های ثابت',
                                indicator: 'red'
                            });
                        }
                    },
                    error: function (err) {
                        console.error('Error loading fixed costs:', err);
                        frappe.show_alert({
                            message: 'خطا در ارتباط با سرور',
                            indicator: 'red'
                        });
                    }
                });
            }

            function show_fixed_costs_breakdown_dialog(frm, total_fixed_costs) {
                /**
                 * نمایش جزئیات هزینه‌های ثابت در dialog
                 */

                const formatted_total = format_currency(total_fixed_costs);

                const dialog = new frappe.ui.Dialog({
                    title: __('جزئیات هزینه‌های ثابت ماهانه'),
                    size: 'large',
                    fields: [
                        {
                            fieldtype: 'HTML',
                            fieldname: 'breakdown_html'
                        }
                    ]
                });

                const html = `
        <div style="padding: 20px;">
            <div class="alert alert-success" style="margin-bottom: 20px;">
                <h4 style="margin-top: 0;">
                    <i class="fa fa-check-circle"></i>
                    هزینه‌های ثابت ماهانه بارگذاری شد
                </h4>
                <h3 style="color: #27ae60; margin: 10px 0;">
                    ${formatted_total} ریال
                </h3>
            </div>
            
            <div class="row">
                <div class="col-md-6">
                    <h5>منابع داده:</h5>
                    <ul>
                        <li>تراکنش‌های مالی ماه گذشته</li>
                        <li>حساب‌های هزینه نوع "Expense"</li>
                        <li>فیلتر بر اساس کلمات کلیدی هزینه ثابت</li>
                    </ul>
                </div>
                <div class="col-md-6">
                    <h5>شامل هزینه‌های:</h5>
                    <ul>
                        <li>اجاره و کرایه املاک</li>
                        <li>حقوق و دستمزد کارکنان</li>
                        <li>بیمه‌ها و مستهلکات</li>
                        <li>هزینه‌های اداری ثابت</li>
                        <li>هزینه‌های مالی و بانکی</li>
                    </ul>
                </div>
            </div>
            
            <div class="alert alert-info" style="margin-top: 20px;">
                <h5>نکات مهم:</h5>
                <ul style="margin-bottom: 0;">
                    <li>این مقدار بر اساس تراکنش‌های واقعی حسابداری محاسبه شده</li>
                    <li>در صورت عدم وجود داده کافی، از میانگین 3 ماه گذشته استفاده می‌شود</li>
                    <li>می‌توانید مقدار را دستی تغییر دهید</li>
                    <li>این مقدار در محاسبه نقطه سر به سر استفاده می‌شود</li>
                </ul>
            </div>
        </div>
    `;

                dialog.fields_dict.breakdown_html.$wrapper.html(html);
                dialog.show();
            }

            // ==================== نمودارهای پیشرفته ====================

            function render_advanced_analytics(frm) {
                /**
                 * رندر تمام نمودارهای پیشرفته
                 */

                if (!frm.doc.items || frm.doc.items.length === 0) {
                    return;
                }

                // رندر نمودار آبشاری
                render_waterfall_chart(frm);

                // رندر نمودار حبابی
                render_bubble_chart(frm);

                // رندر پیش‌بینی فروش
                render_sales_forecast(frm);

                // رندر تحلیل ROI
                render_roi_analysis(frm);

                // رندر رنکینگ محصولات
                render_product_ranking(frm);
            }

            function render_waterfall_chart(frm) {
                /**
                 * نمودار آبشاری تحلیل هزینه‌ها
                 */

                const items = frm.doc.items || [];

                // محاسبه میانگین هزینه‌ها
                let avg_costs = {
                    material: 0,
                    labor: 0,
                    overhead: 0,
                    electricity: 0,
                    rent: 0,
                    subcontracting: 0
                };

                items.forEach(item => {
                    avg_costs.material += (item.total_cost || 0) - (item.labor_cost || 0) - (item.overhead_cost || 0) - (item.electricity_cost || 0) - (item.rent_cost || 0) - (item.subcontracting_cost || 0);
                    avg_costs.labor += (item.labor_cost || 0);
                    avg_costs.overhead += (item.overhead_cost || 0);
                    avg_costs.electricity += (item.electricity_cost || 0);
                    avg_costs.rent += (item.rent_cost || 0);
                    avg_costs.subcontracting += (item.subcontracting_cost || 0);
                });

                Object.keys(avg_costs).forEach(key => {
                    avg_costs[key] = avg_costs[key] / items.length;
                });

                const total_avg_selling = items.reduce((sum, item) => sum + (item.selling_price || 0), 0) / items.length;

                const html = `
        <div class="waterfall-container" style="background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
            <h5 style="text-align: center; margin-bottom: 20px; color: #2c3e50;">تحلیل آبشاری هزینه‌ها (میانگین)</h5>
            <canvas id="waterfall-chart" width="600" height="400"></canvas>
        </div>
    `;

                frm.fields_dict.waterfall_chart_html.$wrapper.html(html);

                setTimeout(() => {
                    render_waterfall_chartjs(avg_costs, total_avg_selling);
                }, 100);
            }

            function render_bubble_chart(frm) {
                /**
                 * نمودار حبابی قیمت vs حجم فروش
                 */

                const items = frm.doc.items || [];

                const html = `
        <div class="bubble-container" style="background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
            <h5 style="text-align: center; margin-bottom: 20px; color: #2c3e50;">قیمت در مقابل حجم فروش</h5>
            <canvas id="bubble-chart" width="600" height="400"></canvas>
        </div>
    `;

                frm.fields_dict.bubble_chart_html.$wrapper.html(html);

                setTimeout(() => {
                    render_bubble_chartjs(items);
                }, 100);
            }

            function render_sales_forecast(frm) {
                /**
                 * پیش‌بینی فروش ماهانه
                 */

                const items = frm.doc.items || [];
                const total_selling_price = items.reduce((sum, item) => sum + (item.selling_price || 0), 0);

                // پیش‌بینی بر اساس روند فعلی
                const monthly_forecast = [];
                const base_monthly = total_selling_price * 0.1; // فرض 10% فروش ماهانه

                for (let i = 1; i <= 12; i++) {
                    const seasonal_factor = 1 + Math.sin((i - 1) * Math.PI / 6) * 0.2; // تغییرات فصلی
                    const growth_factor = 1 + (i * 0.02); // رشد 2% ماهانه
                    monthly_forecast.push({
                        month: i,
                        forecast: base_monthly * seasonal_factor * growth_factor
                    });
                }

                const html = `
        <div class="forecast-container" style="background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
            <h5 style="text-align: center; margin-bottom: 20px; color: #2c3e50;">پیش‌بینی فروش 12 ماه آینده</h5>
            <canvas id="forecast-chart" width="600" height="400"></canvas>
        </div>
    `;

                frm.fields_dict.sales_forecast_html.$wrapper.html(html);

                setTimeout(() => {
                    render_forecast_chartjs(monthly_forecast);
                }, 100);
            }

            function render_roi_analysis(frm) {
                /**
                 * تحلیل ROI محصولات
                 */

                const items = frm.doc.items || [];

                // محاسبه ROI برای هر محصول
                const roi_data = items.map(item => {
                    const investment = item.total_cost || 0;
                    const profit = (item.selling_price || 0) - investment;
                    const roi = investment > 0 ? (profit / investment) * 100 : 0;

                    return {
                        item_name: item.item_name || item.item_code,
                        roi: roi,
                        profit: profit,
                        investment: investment
                    };
                }).sort((a, b) => b.roi - a.roi);

                let table_rows = '';
                roi_data.slice(0, 10).forEach((item, index) => {
                    const roi_color = item.roi > 20 ? '#27ae60' : item.roi > 10 ? '#f39c12' : '#e74c3c';
                    table_rows += `
            <tr>
                <td>${index + 1}</td>
                <td>${item.item_name}</td>
                <td class="text-right">${format_currency(item.investment)}</td>
                <td class="text-right">${format_currency(item.profit)}</td>
                <td class="text-right" style="color: ${roi_color}; font-weight: bold;">${item.roi.toFixed(1)}%</td>
            </tr>
        `;
                });

                const html = `
        <div class="roi-container" style="background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
            <h5 style="text-align: center; margin-bottom: 20px; color: #2c3e50;">تحلیل ROI محصولات (بالاترین 10)</h5>
            <table class="table table-striped">
                <thead>
                    <tr style="background-color: #f8f9fa;">
                        <th>رتبه</th>
                        <th>نام محصول</th>
                        <th class="text-right">سرمایه‌گذاری</th>
                        <th class="text-right">سود</th>
                        <th class="text-right">ROI</th>
                    </tr>
                </thead>
                <tbody>
                    ${table_rows}
                </tbody>
            </table>
        </div>
    `;

                frm.fields_dict.roi_analysis_html.$wrapper.html(html);
            }

            function render_product_ranking(frm) {
                /**
                 * رنکینگ محصولات و فرصت‌های افزایش قیمت
                 */

                const items = frm.doc.items || [];

                // رنکینگ بر اساس حاشیه سود
                const ranking_data = items.map(item => {
                    const cost = item.total_cost || 0;
                    const price = item.selling_price || 0;
                    const margin = cost > 0 ? ((price - cost) / cost) * 100 : 0;
                    const profit = price - cost;

                    // تخمین فرصت افزایش قیمت (بر اساس حاشیه سود پایین)
                    let price_opportunity = 0;
                    if (margin < 15) {
                        price_opportunity = (cost * 0.2) - profit; // هدف 20% حاشیه سود
                    }

                    return {
                        item_name: item.item_name || item.item_code,
                        current_price: price,
                        margin: margin,
                        profit: profit,
                        price_opportunity: Math.max(0, price_opportunity),
                        potential_price: price + Math.max(0, price_opportunity)
                    };
                }).sort((a, b) => b.price_opportunity - a.price_opportunity);

                let ranking_rows = '';
                ranking_data.slice(0, 10).forEach((item, index) => {
                    const margin_color = item.margin > 20 ? '#27ae60' : item.margin > 10 ? '#f39c12' : '#e74c3c';
                    const opportunity_color = item.price_opportunity > 0 ? '#e74c3c' : '#27ae60';

                    ranking_rows += `
            <tr>
                <td>${index + 1}</td>
                <td>${item.item_name}</td>
                <td class="text-right">${format_currency(item.current_price)}</td>
                <td class="text-right" style="color: ${margin_color}; font-weight: bold;">${item.margin.toFixed(1)}%</td>
                <td class="text-right" style="color: ${opportunity_color}; font-weight: bold;">${format_currency(item.price_opportunity)}</td>
                <td class="text-right">${format_currency(item.potential_price)}</td>
            </tr>
        `;
                });

                const html = `
        <div class="ranking-container" style="background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
            <h5 style="text-align: center; margin-bottom: 20px; color: #2c3e50;">رنکینگ فرصت‌های افزایش قیمت</h5>
            <table class="table table-striped">
                <thead>
                    <tr style="background-color: #f8f9fa;">
                        <th>رتبه</th>
                        <th>نام محصول</th>
                        <th class="text-right">قیمت فعلی</th>
                        <th class="text-right">حاشیه سود</th>
                        <th class="text-right">فرصت افزایش</th>
                        <th class="text-right">قیمت پیشنهادی</th>
                    </tr>
                </thead>
                <tbody>
                    ${ranking_rows}
                </tbody>
            </table>
            <div class="alert alert-info" style="margin-top: 15px;">
                <small><strong>نکته:</strong> فرصت‌های افزایش قیمت بر اساس هدف 20% حاشیه سود محاسبه شده‌اند.</small>
            </div>
        </div>
    `;

                frm.fields_dict.product_ranking_html.$wrapper.html(html);
            }

            // ==================== توابع رندر Chart.js ====================

            function render_waterfall_chartjs(costs, selling_price) {
                /**
                 * رندر نمودار آبشاری با Chart.js
                 */

                const canvas = document.getElementById('waterfall-chart');
                if (!canvas) return;

                const ctx = canvas.getContext('2d');

                if (window.waterfallChart) {
                    window.waterfallChart.destroy();
                }

                // Waterfall chart implementation
                const data_points = [
                    { label: 'مواد اولیه', value: costs.material, color: '#3498db' },
                    { label: 'نیروی کار', value: costs.labor, color: '#e74c3c' },
                    { label: 'سربار', value: costs.overhead, color: '#f39c12' },
                    { label: 'برق', value: costs.electricity, color: '#9b59b6' },
                    { label: 'اجاره', value: costs.rent, color: '#1abc9c' },
                    { label: 'پیمانکاری', value: costs.subcontracting, color: '#34495e' }
                ];

                let cumulative = 0;
                const chart_data = [];

                data_points.forEach(point => {
                    if (point.value > 0) {
                        chart_data.push({
                            x: point.label,
                            y: [cumulative, cumulative + point.value],
                            backgroundColor: point.color
                        });
                        cumulative += point.value;
                    }
                });

                // اضافه کردن قیمت فروش
                chart_data.push({
                    x: 'قیمت فروش',
                    y: [0, selling_price],
                    backgroundColor: '#27ae60'
                });

                window.waterfallChart = new Chart(ctx, {
                    type: 'bar',
                    data: {
                        datasets: [{
                            label: 'هزینه‌ها',
                            data: chart_data,
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: {
                                display: false
                            },
                            tooltip: {
                                callbacks: {
                                    label: function (context) {
                                        const value = context.parsed.y[1] - context.parsed.y[0];
                                        return `${context.label}: ${format_currency(value)} ریال`;
                                    }
                                }
                            }
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                ticks: {
                                    callback: function (value) {
                                        return format_currency(value) + ' ریال';
                                    }
                                }
                            }
                        }
                    }
                });
            }

            function render_bubble_chartjs(items) {
                /**
                 * رندر نمودار حبابی با Chart.js
                 */

                const canvas = document.getElementById('bubble-chart');
                if (!canvas) return;

                const ctx = canvas.getContext('2d');

                if (window.bubbleChart) {
                    window.bubbleChart.destroy();
                }

                const bubble_data = items.map(item => {
                    const profit_margin = ((item.selling_price || 0) - (item.total_cost || 0)) / (item.total_cost || 1) * 100;
                    return {
                        x: item.selling_price || 0,
                        y: profit_margin,
                        r: Math.sqrt((item.total_cost || 0) / 1000000) // اندازه حباب بر اساس هزینه
                    };
                });

                window.bubbleChart = new Chart(ctx, {
                    type: 'bubble',
                    data: {
                        datasets: [{
                            label: 'محصولات',
                            data: bubble_data,
                            backgroundColor: 'rgba(52, 152, 219, 0.6)',
                            borderColor: 'rgba(52, 152, 219, 1)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            tooltip: {
                                callbacks: {
                                    label: function (context) {
                                        return `قیمت: ${format_currency(context.parsed.x)} - حاشیه: ${context.parsed.y.toFixed(1)}%`;
                                    }
                                }
                            }
                        },
                        scales: {
                            x: {
                                title: {
                                    display: true,
                                    text: 'قیمت فروش (ریال)'
                                },
                                ticks: {
                                    callback: function (value) {
                                        return format_currency(value);
                                    }
                                }
                            },
                            y: {
                                title: {
                                    display: true,
                                    text: 'حاشیه سود (%)'
                                }
                            }
                        }
                    }
                });
            }

            function render_forecast_chartjs(forecast_data) {
                /**
                 * رندر نمودار پیش‌بینی فروش
                 */

                const canvas = document.getElementById('forecast-chart');
                if (!canvas) return;

                const ctx = canvas.getContext('2d');

                if (window.forecastChart) {
                    window.forecastChart.destroy();
                }

                const months = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
                    'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'];

                window.forecastChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: months,
                        datasets: [{
                            label: 'پیش‌بینی فروش',
                            data: forecast_data.map(d => d.forecast),
                            borderColor: '#27ae60',
                            backgroundColor: 'rgba(39, 174, 96, 0.1)',
                            borderWidth: 3,
                            fill: true,
                            tension: 0.4
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            tooltip: {
                                callbacks: {
                                    label: function (context) {
                                        return `پیش‌بینی: ${format_currency(context.parsed.y)} ریال`;
                                    }
                                }
                            }
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                ticks: {
                                    callback: function (value) {
                                        return format_currency(value) + ' ریال';
                                    }
                                }
                            }
                        }
                    }
                });
            }


            // Function to refresh content without full page reload
            function refresh_content_without_reload(frm) {
                console.log("🔄 Refreshing content without page reload...");

                frappe.show_alert({
                    message: __("در حال بروزرسانی محتوا..."),
                    indicator: "blue"
                });

                // Reload the document data
                frm.reload_doc().then(() => {
                    // Re-render analytics and charts
                    if (frm.doc.items && frm.doc.items.length > 0) {
                        calculate_break_even_analysis(frm);
                        render_advanced_analytics(frm);
                        apply_bom_status_styling(frm);
                    }

                    // Refresh fields
                    frm.refresh_fields();

                    frappe.show_alert({
                        message: __("✅ محتوا با موفقیت بروزرسانی شد"),
                        indicator: "green"
                    });

                    console.log("✅ Content refreshed successfully");
                }).catch((error) => {
                    console.error("❌ Error refreshing content:", error);
                    frappe.show_alert({
                        message: __("❌ خطا در بروزرسانی محتوا"),
                        indicator: "red"
                    });
                });
            }

            // متغیرهای سراسری برای progress dialog
            let progress_dialog = null;
            let progress_id = null;

            function show_progress_dialog() {
                // نمایش progress bar برای محاسبات طولانی
                progress_dialog = new frappe.ui.Dialog({
                    title: '📊 در حال محاسبه بهای تمام شده...',
                    fields: [
                        {
                            fieldtype: 'HTML',
                            fieldname: 'progress_area',
                            options: `
                    <div style="padding: 20px; text-align: center;">
                        <div id="progress_message" style="margin-bottom: 15px; font-size: 14px; color: #666;">
                            🚀 آماده‌سازی برای محاسبه...
                        </div>
                        <div style="background: #f5f5f5; border-radius: 10px; padding: 5px; margin-bottom: 10px;">
                            <div id="progress_bar" style="
                                width: 0%; 
                                height: 25px; 
                                background: linear-gradient(90deg, #4CAF50, #45a049); 
                                border-radius: 8px; 
                                transition: width 0.3s ease;
                                display: flex;
                                align-items: center;
                                justify-content: center;
                                color: white;
                                font-weight: bold;
                                font-size: 12px;
                            ">0%</div>
                        </div>
                        <div id="progress_details" style="font-size: 12px; color: #888;">
                            لطفاً صبر کنید...
                        </div>
                    </div>
                `
                        }
                    ],
                    primary_action_label: 'لغو',
                    primary_action: function () {
                        progress_dialog.hide();
                    }
                });

                progress_dialog.show();

                // شروع لیسنر برای realtime updates
                frappe.realtime.on('pricing_progress', function (data) {
                    update_progress(data.percentage, data.message);
                });
            }

            function update_progress(percentage, message) {
                // به‌روزرسانی progress bar
                if (progress_dialog && progress_dialog.is_visible) {
                    const progress_bar = document.getElementById('progress_bar');
                    const progress_message = document.getElementById('progress_message');
                    const progress_details = document.getElementById('progress_details');

                    if (progress_bar) {
                        progress_bar.style.width = percentage + '%';
                        progress_bar.textContent = Math.round(percentage) + '%';

                        // تغییر رنگ بر اساس پیشرفت
                        if (percentage < 25) {
                            progress_bar.style.background = 'linear-gradient(90deg, #ff9800, #f57c00)';
                        } else if (percentage < 50) {
                            progress_bar.style.background = 'linear-gradient(90deg, #2196f3, #1976d2)';
                        } else if (percentage < 75) {
                            progress_bar.style.background = 'linear-gradient(90deg, #9c27b0, #7b1fa2)';
                        } else {
                            progress_bar.style.background = 'linear-gradient(90deg, #4caf50, #45a049)';
                        }
                    }

                    if (progress_message) {
                        progress_message.innerHTML = message;
                    }

                    if (progress_details) {
                        const now = new Date().toLocaleTimeString('fa-IR');
                        progress_details.innerHTML = `آخرین به‌روزرسانی: ${now}`;
                    }

                    // بستن خودکار وقتی 100% شد
                    if (percentage >= 100) {
                        setTimeout(() => {
                            hide_progress_dialog();
                        }, 1500);
                    }
                }
            }

            function hide_progress_dialog() {
                // بستن progress dialog
                if (progress_dialog) {
                    progress_dialog.hide();
                    progress_dialog = null;
                }

                // حذف لیسنر realtime
                frappe.realtime.off('pricing_progress');
            }

            function add_bulk_items_to_manual_prices(frm) {
                // اضافه آیتم‌های bulk_pricing_items به جدول manual_item_prices
                console.log('📎 add_bulk_items_to_manual_prices called');

                if (!frm.doc.bulk_pricing_items || frm.doc.bulk_pricing_items.length === 0) {
                    frappe.msgprint({
                        title: 'هشدار',
                        message: 'هیچ آیتمی در جدول bulk_pricing_items وجود ندارد',
                        indicator: 'orange'
                    });
                    return;
                }

                frappe.confirm(
                    `آیا می‌خواهید ${frm.doc.bulk_pricing_items.length} آیتم را به جدول قیمت‌های دستی اضافه کنید؟<br><br>` +
                    '<small>این عملیات:<br>' +
                    '• قیمت‌ها را به صورت دائمی ذخیره می‌کند<br>' +
                    '• قابل ویرایش خواهند بود<br>' +
                    '• بر محاسبات BOM اولویت خواهند داشت</small>',
                    function () {
                        console.log('🚀 User confirmed, calling add_bulk_items_to_manual_prices...');

                        frappe.show_alert({
                            message: '📎 در حال اضافه به جدول قیمت‌های دستی...',
                            indicator: 'blue'
                        });

                        // Test if module function is available
                        console.log('🧪 Testing module function availability...');

                        frappe.call({
                            method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.add_bulk_items_to_manual_prices_api',
                            args: {
                                docname: frm.doc.name
                            },
                            freeze: true,
                            freeze_message: 'در حال اضافه به جدول قیمت‌های دستی...'
                        }).then((response) => {
                            console.log('✅ add_bulk_items_to_manual_prices completed, response:', response);

                            if (response && response.message) {
                                const result = response.message;

                                if (result.success) {
                                    frappe.show_alert({
                                        message: result.message,
                                        indicator: 'green'
                                    });

                                    // به‌روزرسانی صفحه
                                    frm.reload_doc().then(() => {
                                        frm.refresh_field('manual_item_prices');
                                        console.log('📄 Document reloaded and manual_item_prices refreshed');
                                    });

                                } else {
                                    frappe.show_alert({
                                        title: 'خطا',
                                        message: result.message || 'خطای نامشخص',
                                        indicator: 'red'
                                    });
                                }
                            } else {
                                frappe.show_alert({
                                    title: 'خطا',
                                    message: 'پاسخی از سرور دریافت نشد',
                                    indicator: 'red'
                                });
                            }
                        }).catch((error) => {
                            console.error('❌ Error in add_bulk_items_to_manual_prices:', error);
                            frappe.msgprint({
                                title: 'خطا',
                                message: 'خطا در اضافه به جدول قیمت‌های دستی: ' + (error.message || error),
                                indicator: 'red'
                            });
                        });
                    },
                    function () {
                        console.log('❌ User cancelled the operation');
                    }
                );
            }

            // ===============================
            // گزارش‌های تحلیلی - Report Functions
            // ===============================

            function show_cost_analysis_report(frm) {
                /**
                 * نمایش گزارش تحلیل هزینه‌ها
                 */

                if (!frm.doc.items || frm.doc.items.length === 0) {
                    frappe.msgprint({
                        title: '📋 اطلاعات',
                        message: 'ابتدا کالاها را دریافت کنید تا گزارش تحلیل هزینه تهیه شود.',
                        indicator: 'orange'
                    });
                    return;
                }

                frappe.show_alert({
                    message: '📊 در حال تهیه گزارش تحلیل هزینه...',
                    indicator: 'blue'
                });

                // تهیه داده‌های گزارش
                let cost_analysis_data = [];
                let total_raw_material = 0;
                let total_operation = 0;
                let total_overhead = 0;
                let total_selling_price = 0;

                frm.doc.items.forEach(item => {
                    const raw_cost = flt(item.raw_material_cost || 0);
                    const op_cost = flt(item.operation_cost || 0);
                    const oh_cost = flt(item.overhead_cost || 0);
                    const selling_price = flt(item.selling_price || 0);

                    cost_analysis_data.push({
                        item_code: item.item_code,
                        item_name: item.item_name || item.item_code,
                        raw_material_cost: raw_cost,
                        operation_cost: op_cost,
                        overhead_cost: oh_cost,
                        total_cost: raw_cost + op_cost + oh_cost,
                        selling_price: selling_price,
                        profit: selling_price - (raw_cost + op_cost + oh_cost),
                        profit_percentage: selling_price > 0 ? ((selling_price - (raw_cost + op_cost + oh_cost)) / selling_price * 100) : 0
                    });

                    total_raw_material += raw_cost;
                    total_operation += op_cost;
                    total_overhead += oh_cost;
                    total_selling_price += selling_price;
                });

                show_cost_analysis_dialog(cost_analysis_data, {
                    total_raw_material,
                    total_operation,
                    total_overhead,
                    total_selling_price,
                    total_profit: total_selling_price - (total_raw_material + total_operation + total_overhead)
                });
            }

            function show_cost_analysis_dialog(data, totals) {
                /**
                 * نمایش دیالوگ گزارش تحلیل هزینه
                 */

                let html_content = `
        <div style="padding: 15px;">
            <h4 style="color: #2c3e50; margin-bottom: 20px;">📊 گزارش تحلیل هزینه‌های تولید</h4>
            
            <!-- خلاصه کلی -->
            <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                <h5 style="color: #495057; margin-bottom: 15px;">📈 خلاصه کلی</h5>
                <div class="row">
                    <div class="col-md-3">
                        <strong>کل مواد اولیه:</strong><br>
                        <span style="color: #e74c3c; font-size: 18px;">${format_currency(totals.total_raw_material)}</span>
                    </div>
                    <div class="col-md-3">
                        <strong>کل عملیات:</strong><br>
                        <span style="color: #f39c12; font-size: 18px;">${format_currency(totals.total_operation)}</span>
                    </div>
                    <div class="col-md-3">
                        <strong>کل سربار:</strong><br>
                        <span style="color: #9b59b6; font-size: 18px;">${format_currency(totals.total_overhead)}</span>
                    </div>
                    <div class="col-md-3">
                        <strong>کل سود:</strong><br>
                        <span style="color: #27ae60; font-size: 18px;">${format_currency(totals.total_profit)}</span>
                    </div>
                </div>
            </div>
            
            <!-- جدول تفصیلی -->
            <div style="max-height: 400px; overflow-y: auto;">
                <table class="table table-striped table-bordered">
                    <thead style="background: #34495e; color: white;">
                        <tr>
                            <th>کد کالا</th>
                            <th>نام کالا</th>
                            <th>مواد اولیه</th>
                            <th>عملیات</th>
                            <th>سربار</th>
                            <th>کل هزینه</th>
                            <th>قیمت فروش</th>
                            <th>سود</th>
                            <th>درصد سود</th>
                        </tr>
                    </thead>
                    <tbody>`;

                data.forEach(item => {
                    const profit_color = item.profit >= 0 ? '#27ae60' : '#e74c3c';
                    html_content += `
            <tr>
                <td><strong>${item.item_code}</strong></td>
                <td>${item.item_name}</td>
                <td style="text-align: right;">${format_currency(item.raw_material_cost)}</td>
                <td style="text-align: right;">${format_currency(item.operation_cost)}</td>
                <td style="text-align: right;">${format_currency(item.overhead_cost)}</td>
                <td style="text-align: right; font-weight: bold;">${format_currency(item.total_cost)}</td>
                <td style="text-align: right; color: #2980b9; font-weight: bold;">${format_currency(item.selling_price)}</td>
                <td style="text-align: right; color: ${profit_color}; font-weight: bold;">${format_currency(item.profit)}</td>
                <td style="text-align: right; color: ${profit_color}; font-weight: bold;">${item.profit_percentage.toFixed(1)}%</td>
            </tr>`;
                });

                html_content += `
                    </tbody>
                </table>
            </div>
        </div>`;

                let dialog = new frappe.ui.Dialog({
                    title: '📊 گزارش تحلیل هزینه‌ها',
                    size: 'extra-large',
                    fields: [
                        {
                            fieldtype: 'HTML',
                            fieldname: 'cost_analysis_html',
                            options: html_content
                        }
                    ],
                    primary_action_label: '📄 خروجی Excel',
                    primary_action: function () {
                        export_cost_analysis_to_excel(data, totals);
                    }
                });

                dialog.show();
            }

            function show_raw_materials_report(frm) {
                /**
                 * نمایش گزارش کامل مواد اولیه خام
                 */

                frappe.show_alert({
                    message: '📊 در حال تهیه گزارش مواد اولیه خام...',
                    indicator: 'blue'
                });

                frm.call('get_raw_materials_report').then((response) => {
                    if (response && response.message) {
                        const result = response.message;

                        if (!result.success) {
                            frappe.msgprint({
                                title: '❌ خطا',
                                message: result.message,
                                indicator: 'red'
                            });
                            return;
                        }

                        show_raw_materials_dialog(result);
                    }
                }).catch((error) => {
                    frappe.msgprint({
                        title: '❌ خطا',
                        message: 'خطا در تهیه گزارش مواد اولیه: ' + (error.message || error),
                        indicator: 'red'
                    });
                });
            }

            function show_raw_materials_dialog(result) {
                /**
                 * نمایش دیالوگ گزارش مواد اولیه
                 */

                let html_content = `
        <div style="padding: 15px;">
            <h4 style="color: #2c3e50; margin-bottom: 20px;">🧱 گزارش مواد اولیه خام</h4>
            
            <!-- آمار کلی -->
            <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                <div class="row">
                    <div class="col-md-4">
                        <strong>تعداد کل مواد:</strong><br>
                        <span style="color: #3498db; font-size: 18px;">${result.total_materials || 0}</span>
                    </div>
                    <div class="col-md-4">
                        <strong>مواد با قیمت:</strong><br>
                        <span style="color: #27ae60; font-size: 18px;">${result.materials_with_price || 0}</span>
                    </div>
                    <div class="col-md-4">
                        <strong>مواد بدون قیمت:</strong><br>
                        <span style="color: #e74c3c; font-size: 18px;">${result.materials_without_price || 0}</span>
                    </div>
                </div>
            </div>`;

                if (result.materials && result.materials.length > 0) {
                    html_content += `
            <div style="max-height: 400px; overflow-y: auto;">
                <table class="table table-striped table-bordered">
                    <thead style="background: #34495e; color: white;">
                        <tr>
                            <th>کد ماده</th>
                            <th>نام ماده</th>
                            <th>واحد</th>
                            <th>قیمت واحد</th>
                            <th>وضعیت</th>
                            <th>استفاده در BOM</th>
                        </tr>
                    </thead>
                    <tbody>`;

                    result.materials.forEach(material => {
                        const status_color = material.rate > 0 ? '#27ae60' : '#e74c3c';
                        const status_text = material.rate > 0 ? 'دارای قیمت' : 'بدون قیمت';

                        html_content += `
                <tr>
                    <td><strong>${material.item_code}</strong></td>
                    <td>${material.item_name || material.item_code}</td>
                    <td>${material.uom || '-'}</td>
                    <td style="text-align: right;">${material.rate > 0 ? format_currency(material.rate) : '-'}</td>
                    <td style="color: ${status_color}; font-weight: bold;">${status_text}</td>
                    <td style="text-align: center;">${material.bom_count || 0}</td>
                </tr>`;
                    });

                    html_content += `
                    </tbody>
                </table>
            </div>`;
                } else {
                    html_content += `
            <div style="text-align: center; padding: 40px; color: #7f8c8d;">
                <i class="fa fa-info-circle" style="font-size: 48px; margin-bottom: 15px;"></i>
                <p>هیچ ماده اولیه‌ای یافت نشد.</p>
            </div>`;
                }

                html_content += `</div>`;

                let dialog = new frappe.ui.Dialog({
                    title: '🧱 گزارش مواد اولیه خام',
                    size: 'extra-large',
                    fields: [
                        {
                            fieldtype: 'HTML',
                            fieldname: 'raw_materials_html',
                            options: html_content
                        }
                    ],
                    primary_action_label: '📄 خروجی Excel',
                    primary_action: function () {
                        export_raw_materials_to_excel(result);
                    }
                });

                dialog.show();
            }

            function export_cost_analysis_to_excel(data, totals) {
                /**
                 * خروجی گزارش تحلیل هزینه به Excel
                 */
                frappe.show_alert({
                    message: '📄 در حال تهیه فایل Excel...',
                    indicator: 'blue'
                });

                // این قسمت می‌تواند با کتابخانه‌های Excel پیاده‌سازی شود
                frappe.msgprint({
                    title: '📄 خروجی Excel',
                    message: 'قابلیت خروجی Excel در نسخه بعدی اضافه خواهد شد.',
                    indicator: 'blue'
                });
            }

            function export_raw_materials_to_excel(result) {
                /**
                 * خروجی گزارش مواد اولیه به Excel
                 */
                frappe.show_alert({
                    message: '📄 در حال تهیه فایل Excel...',
                    indicator: 'blue'
                });

                // این قسمت می‌تواند با کتابخانه‌های Excel پیاده‌سازی شود
                frappe.msgprint({
                    title: '📄 خروجی Excel',
                    message: 'قابلیت خروجی Excel در نسخه بعدی اضافه خواهد شد.',
                    indicator: 'blue'
                });
            }

            // گزارش مقایسه قیمت با لیست قیمت مقایسه
            function show_price_comparison_report(frm) {
                console.log('📊 نمایش گزارش مقایسه قیمت');

                if (!frm.doc.compare_with_price_list) {
                    frappe.msgprint({
                        title: 'خطا',
                        message: 'لطفاً ابتدا لیست قیمت مقایسه را انتخاب کنید',
                        indicator: 'red'
                    });
                    return;
                }

                if (!frm.doc.items || frm.doc.items.length === 0) {
                    frappe.msgprint({
                        title: 'خطا',
                        message: 'هیچ محصولی برای مقایسه وجود ندارد',
                        indicator: 'red'
                    });
                    return;
                }

                frappe.show_alert({
                    message: 'در حال بارگذاری گزارش مقایسه قیمت...',
                    indicator: 'blue'
                });

                // فراخوانی متد سرور برای دریافت داده‌های مقایسه
                frappe.call({
                    method: 'get_price_comparison_data',
                    doc: frm.doc,
                    callback: function (response) {
                        if (response && response.message) {
                            display_price_comparison_dialog(response.message);
                        } else {
                            frappe.msgprint({
                                title: 'خطا',
                                message: 'خطا در دریافت داده‌های مقایسه',
                                indicator: 'red'
                            });
                        }
                    }
                });
            }

            function display_price_comparison_dialog(data) {
                console.log('📊 نمایش دیالوگ مقایسه قیمت', data);

                // محاسبه آمار کلی
                let total_items = data.items.length;
                let increased_count = 0;
                let decreased_count = 0;
                let unchanged_count = 0;
                let total_old_value = 0;
                let total_new_value = 0;

                data.items.forEach(item => {
                    if (item.price_change_percentage > 0) increased_count++;
                    else if (item.price_change_percentage < 0) decreased_count++;
                    else unchanged_count++;

                    total_old_value += item.old_price || 0;
                    total_new_value += item.new_price || 0;
                });

                let overall_change_percentage = total_old_value > 0 ?
                    ((total_new_value - total_old_value) / total_old_value * 100).toFixed(2) : 0;

                // ایجاد HTML برای نمایش
                let html_content = `
        <div style="padding: 15px;">
            <!-- آمار کلی -->
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                        color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                <h3 style="margin: 0 0 15px 0;">📊 خلاصه گزارش مقایسه قیمت</h3>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px;">
                    <div style="text-align: center;">
                        <div style="font-size: 24px; font-weight: bold;">${total_items}</div>
                        <div style="font-size: 12px; opacity: 0.9;">تعداد کل محصولات</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 24px; font-weight: bold; color: #4ade80;">↑ ${increased_count}</div>
                        <div style="font-size: 12px; opacity: 0.9;">افزایش قیمت</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 24px; font-weight: bold; color: #f87171;">↓ ${decreased_count}</div>
                        <div style="font-size: 12px; opacity: 0.9;">کاهش قیمت</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 24px; font-weight: bold; color: #fbbf24;">= ${unchanged_count}</div>
                        <div style="font-size: 12px; opacity: 0.9;">بدون تغییر</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 24px; font-weight: bold; color: ${overall_change_percentage >= 0 ? '#4ade80' : '#f87171'};">
                            ${overall_change_percentage >= 0 ? '+' : ''}${overall_change_percentage}%
                        </div>
                        <div style="font-size: 12px; opacity: 0.9;">تغییر کلی قیمت‌ها</div>
                    </div>
                </div>
            </div>
            
            <!-- جدول مقایسه -->
            <div style="max-height: 400px; overflow-y: auto;">
                <table class="table table-striped table-bordered">
                    <thead style="background: #34495e; color: white; position: sticky; top: 0;">
                        <tr>
                            <th>کد محصول</th>
                            <th>نام محصول</th>
                            <th>قیمت قبلی</th>
                            <th>قیمت جدید</th>
                            <th>تفاوت</th>
                            <th>درصد تغییر</th>
                            <th>وضعیت</th>
                        </tr>
                    </thead>
                    <tbody>`;

                // اضافه کردن ردیف‌ها
                data.items.forEach(item => {
                    let status_icon = '';
                    let status_color = '';
                    let status_text = '';

                    if (item.price_change_percentage > 0) {
                        status_icon = '↑';
                        status_color = '#4ade80';
                        status_text = 'افزایش';
                    } else if (item.price_change_percentage < 0) {
                        status_icon = '↓';
                        status_color = '#f87171';
                        status_text = 'کاهش';
                    } else {
                        status_icon = '=';
                        status_color = '#fbbf24';
                        status_text = 'ثابت';
                    }

                    html_content += `
            <tr>
                <td><strong>${item.item_code}</strong></td>
                <td>${item.item_name || item.item_code}</td>
                <td style="text-align: right;">${format_currency(item.old_price || 0)}</td>
                <td style="text-align: right;">${format_currency(item.new_price || 0)}</td>
                <td style="text-align: right; color: ${item.price_difference >= 0 ? 'green' : 'red'};">
                    ${item.price_difference >= 0 ? '+' : ''}${format_currency(item.price_difference || 0)}
                </td>
                <td style="text-align: center; font-weight: bold; color: ${status_color};">
                    ${status_icon} ${Math.abs(item.price_change_percentage || 0).toFixed(2)}%
                </td>
                <td style="text-align: center;">
                    <span style="background: ${status_color}; color: white; padding: 2px 8px; border-radius: 4px;">
                        ${status_text}
                    </span>
                </td>
            </tr>`;
                });

                html_content += `
                    </tbody>
                </table>
            </div>
            
            <!-- نمودار دایره‌ای -->
            <div style="margin-top: 20px; text-align: center;">
                <canvas id="price_comparison_chart" width="300" height="300"></canvas>
            </div>
        </div>`;

                // ایجاد دیالوگ
                let dialog = new frappe.ui.Dialog({
                    title: `📊 گزارش مقایسه قیمت با: ${data.compare_list_name}`,
                    size: 'extra-large',
                    fields: [
                        {
                            fieldtype: 'HTML',
                            fieldname: 'comparison_html',
                            options: html_content
                        }
                    ],
                    primary_action_label: '📄 خروجی Excel',
                    primary_action: function () {
                        export_price_comparison_to_excel(data);
                    }
                });

                dialog.show();

                // رسم نمودار دایره‌ای
                setTimeout(() => {
                    render_price_comparison_chart('price_comparison_chart', {
                        increased: increased_count,
                        decreased: decreased_count,
                        unchanged: unchanged_count
                    });
                }, 100);
            }

            function render_price_comparison_chart(canvas_id, data) {
                const canvas = document.getElementById(canvas_id);
                if (!canvas) return;

                const ctx = canvas.getContext('2d');
                const centerX = canvas.width / 2;
                const centerY = canvas.height / 2;
                const radius = 100;

                const total = data.increased + data.decreased + data.unchanged;
                if (total === 0) return;

                const segments = [
                    { label: 'افزایش', value: data.increased, color: '#4ade80' },
                    { label: 'کاهش', value: data.decreased, color: '#f87171' },
                    { label: 'ثابت', value: data.unchanged, color: '#fbbf24' }
                ];

                let currentAngle = -Math.PI / 2;

                segments.forEach(segment => {
                    const percentage = segment.value / total;
                    const angle = percentage * 2 * Math.PI;

                    // رسم بخش
                    ctx.beginPath();
                    ctx.arc(centerX, centerY, radius, currentAngle, currentAngle + angle);
                    ctx.lineTo(centerX, centerY);
                    ctx.fillStyle = segment.color;
                    ctx.fill();

                    // رسم برچسب
                    const labelAngle = currentAngle + angle / 2;
                    const labelX = centerX + Math.cos(labelAngle) * (radius * 0.7);
                    const labelY = centerY + Math.sin(labelAngle) * (radius * 0.7);

                    ctx.fillStyle = 'white';
                    ctx.font = 'bold 14px Arial';
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';

                    if (segment.value > 0) {
                        ctx.fillText(`${segment.label}`, labelX, labelY - 10);
                        ctx.fillText(`${segment.value} (${(percentage * 100).toFixed(1)}%)`, labelX, labelY + 10);
                    }

                    currentAngle += angle;
                });
            }

            function export_price_comparison_to_excel(data) {
                frappe.show_alert({
                    message: '📄 در حال تهیه فایل Excel...',
                    indicator: 'blue'
                });

                // TODO: پیاده‌سازی خروجی Excel
                frappe.msgprint({
                    title: '📄 خروجی Excel',
                    message: 'قابلیت خروجی Excel به زودی اضافه خواهد شد.',
                    indicator: 'blue'
                });
            }

            // تنظیم event handler ها برای grid
            function setup_bundle_grid_handlers(frm) {
                if (!frm.fields_dict.product_bundles || !frm.fields_dict.product_bundles.grid) {
                    console.log('Product bundles grid not found');
                    return;
                }

                let grid = frm.fields_dict.product_bundles.grid;

                // Override toggle_view to render HTML when row opens
                grid.grid_rows.forEach(grid_row => {
                    if (!grid_row._html_handler_attached) {
                        let original_toggle_view = grid_row.toggle_view.bind(grid_row);
                        grid_row.toggle_view = function (show, callback) {
                            original_toggle_view(show, callback);
                            // HTML is now rendered server-side and stored in bundle_items_html
                        };
                        grid_row._html_handler_attached = true;
                    }
                });

                console.log('Bundle grid handlers set up');
            }

            // Handler برای نمایش آیتم‌های بسته محصول
            frappe.ui.form.on('Auto Price List Product Bundle', {
                bundle_items_data: function (frm, cdt, cdn) {
                    render_bundle_items_html_delayed(frm, cdt, cdn);
                }
            });

            function render_bundle_items_html_delayed(frm, cdt, cdn) {
                setTimeout(() => {
                    render_bundle_items_html(frm, cdt, cdn);
                }, 150);
            }

            function render_bundle_items_html(frm, cdt, cdn) {
                let row = locals[cdt][cdn];

                if (!row || !row.bundle_items_data) {
                    return;
                }

                try {
                    let items = JSON.parse(row.bundle_items_data);

                    if (!items || items.length === 0) {
                        return;
                    }

                    let html = `
            <div style='margin-top: 10px;'>
                <table class='table table-bordered table-hover' style='margin: 0; font-size: 12px; width: 100%;'>
                    <thead style='background-color: #f5f5f5;'>
                        <tr>
                            <th style='padding: 8px; text-align: right;'>کد کالا</th>
                            <th style='padding: 8px; text-align: right;'>نام کالا</th>
                            <th style='padding: 8px; text-align: center; width: 80px;'>تعداد</th>
                            <th style='padding: 8px; text-align: right;'>هزینه واحد</th>
                            <th style='padding: 8px; text-align: right;'>قیمت واحد</th>
                            <th style='padding: 8px; text-align: right;'>هزینه کل</th>
                            <th style='padding: 8px; text-align: right;'>قیمت کل</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

                    items.forEach(item => {
                        html += `
                <tr>
                    <td style='padding: 8px;'>${item.item_code}</td>
                    <td style='padding: 8px;'>${item.item_name}</td>
                    <td style='padding: 8px; text-align: center;'>${format_number(item.qty, null, 2)}</td>
                    <td style='padding: 8px; text-align: right;'>${format_currency(item.unit_cost, 'IRR')}</td>
                    <td style='padding: 8px; text-align: right;'>${format_currency(item.unit_selling_price, 'IRR')}</td>
                    <td style='padding: 8px; text-align: right;'>${format_currency(item.total_cost, 'IRR')}</td>
                    <td style='padding: 8px; text-align: right;'>${format_currency(item.total_selling_price, 'IRR')}</td>
                </tr>
            `;
                    });

                    html += `
                    </tbody>
                </table>
            </div>
        `;

                    let grid = frm.fields_dict.product_bundles.grid;
                    let grid_row = grid.grid_rows_by_docname[cdn];

                    if (grid_row && grid_row.grid_form) {
                        let html_field = grid_row.grid_form.fields_dict.bundle_items_html;
                        if (html_field && html_field.$wrapper) {
                            html_field.$wrapper.html(html);
                        }
                    }

                } catch (e) {
                    console.error('Error rendering bundle items:', e);
                }
            }

            /**
             * 🔍 اعمال فیلترهای پیشرفته با عملگرهای شرطی روی جدول مواد اولیه
             */
            function apply_raw_material_filters(frm) {
                const filters = {
                    name1: (frm.doc.raw_material_filter_name || '').toLowerCase().trim(),
                    name1_operator: frm.doc.raw_material_filter_name_operator || 'شامل باشد (Like)',
                    name2: (frm.doc.raw_material_filter_name2 || '').toLowerCase().trim(),
                    name2_operator: frm.doc.raw_material_filter_name2_operator || 'شامل نباشد (Not Like)',
                    group: frm.doc.raw_material_filter_group || '',
                    price_min: flt(frm.doc.raw_material_filter_price_min || 0),
                    price_max: flt(frm.doc.raw_material_filter_price_max || 0),
                    supplier: frm.doc.raw_material_filter_supplier || ''
                };

                // اگر همه فیلترها خالی باشند
                if (!filters.name1 && !filters.name2 && !filters.group && !filters.price_min && !filters.price_max && !filters.supplier) {
                    frappe.show_alert({
                        message: __('لطفاً حداقل یک فیلتر را پر کنید'),
                        indicator: 'orange'
                    });
                    return;
                }

                // ذخیره داده‌های اصلی اگر قبلاً ذخیره نشده
                if (!frm._original_raw_materials) {
                    frm._original_raw_materials = JSON.parse(JSON.stringify(frm.doc.manual_material_prices || []));
                }

                /**
                 * تابع کمکی برای اعمال عملگر شرطی
                 */
                function apply_operator(text, search_term, operator) {
                    if (!search_term) return true;

                    const text_lower = (text || '').toLowerCase();

                    switch (operator) {
                        case 'شامل باشد (Like)':
                            return text_lower.includes(search_term);
                        case 'شامل نباشد (Not Like)':
                            return !text_lower.includes(search_term);
                        case 'برابر باشد (=)':
                            return text_lower === search_term;
                        case 'برابر نباشد (!=)':
                            return text_lower !== search_term;
                        default:
                            return text_lower.includes(search_term);
                    }
                }

                // فیلتر کردن
                let filtered = frm._original_raw_materials.filter(item => {
                    let match = true;
                    const item_name = (item.item_name || '').toLowerCase();
                    const item_code = (item.item_code || '').toLowerCase();
                    const combined_text = item_name + ' ' + item_code;

                    // فیلتر نام ۱
                    if (filters.name1 && match) {
                        match = apply_operator(combined_text, filters.name1, filters.name1_operator);
                    }

                    // فیلتر نام ۲
                    if (filters.name2 && match) {
                        match = apply_operator(combined_text, filters.name2, filters.name2_operator);
                    }

                    // فیلتر گروه
                    if (filters.group && match) {
                        match = item.item_group === filters.group;
                    }

                    // فیلتر قیمت حداقل
                    if (filters.price_min > 0 && match) {
                        const price = flt(item.last_purchase_price || item.manual_price || 0);
                        match = price >= filters.price_min;
                    }

                    // فیلتر قیمت حداکثر
                    if (filters.price_max > 0 && match) {
                        const price = flt(item.last_purchase_price || item.manual_price || 0);
                        match = price <= filters.price_max;
                    }

                    // فیلتر تامین‌کننده
                    if (filters.supplier && match) {
                        match = item.last_supplier === filters.supplier;
                    }

                    return match;
                });

                // نمایش نتایج
                frm.doc.manual_material_prices = filtered;
                frm.refresh_field('manual_material_prices');

                frappe.show_alert({
                    message: __(`🔍 ${filtered.length} مورد از ${frm._original_raw_materials.length} یافت شد`),
                    indicator: filtered.length > 0 ? 'green' : 'orange'
                });
            }

            /**
             * ❌ نمایش همه مواد اولیه (پاک کردن فیلتر)
             */
            function show_all_raw_materials(frm) {
                if (frm._original_raw_materials) {
                    frm.doc.manual_material_prices = JSON.parse(JSON.stringify(frm._original_raw_materials));
                    frm.refresh_field('manual_material_prices');

                    // پاک کردن ذخیره اصلی
                    delete frm._original_raw_materials;
                }
            }

            /**
             * 🔍 سیستم فیلتر داینامیک برای جداول
             * مشابه فیلتر List View در ERPNext
             */
            class DynamicTableFilter {
                constructor(frm, table_fieldname, options = {}) {
                    this.frm = frm;
                    this.table_fieldname = table_fieldname;
                    this.filters = [];
                    this.original_data = null;
                    this.container = null;
                    this.options = Object.assign({
                        show_table_selector: false,
                        title: '🔍 فیلتر جدول'
                    }, options);

                    // تعریف فیلدها و عملگرها
                    this.operators = {
                        'like': 'شامل باشد',
                        'not_like': 'شامل نباشد',
                        '=': 'برابر باشد',
                        '!=': 'برابر نباشد',
                        '>': 'بزرگتر از',
                        '<': 'کوچکتر از',
                        '>=': 'بزرگتر یا برابر',
                        '<=': 'کوچکتر یا برابر'
                    };
                }

                /**
                 * گرفتن فیلدهای جدول
                 */
                get_table_fields() {
                    const table_df = this.frm.fields_dict[this.table_fieldname];
                    if (!table_df || !table_df.grid) return [];

                    const doctype = table_df.df.options;
                    const meta = frappe.get_meta(doctype);
                    if (!meta) return [];

                    return meta.fields.filter(f =>
                        !['Section Break', 'Column Break', 'Tab Break', 'HTML'].includes(f.fieldtype) &&
                        f.fieldname !== 'name'
                    ).map(f => ({
                        fieldname: f.fieldname,
                        label: f.label || f.fieldname,
                        fieldtype: f.fieldtype
                    }));
                }

                /**
                 * رندر UI فیلتر
                 */
                render() {
                    const table_field = this.frm.fields_dict[this.table_fieldname];
                    if (!table_field || !table_field.$wrapper) return;

                    // حذف container قبلی
                    table_field.$wrapper.find('.dynamic-filter-container').remove();

                    // ایجاد container فیلتر
                    this.container = $(`
            <div class="dynamic-filter-container" style="
                margin-bottom: 15px;
                padding: 10px;
                background: #f8f9fa;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            ">
                <div class="filter-header" style="
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 10px;
                ">
                    <span style="font-weight: bold; color: #333;">
                        📦 ${this.options.title}
                    </span>
                    <button class="btn btn-xs btn-success add-filter-btn" style="
                        border-radius: 4px;
                        padding: 4px 10px;
                    ">
                        ➕ افزودن فیلتر
                    </button>
                </div>
                <div class="filter-rows"></div>
                <div class="filter-actions" style="
                    display: flex;
                    gap: 8px;
                    margin-top: 10px;
                ">
                    <button class="btn btn-xs btn-primary apply-filters-btn" style="
                        border-radius: 4px;
                        padding: 5px 15px;
                    ">
                        🔍 اعمال فیلترها
                    </button>
                    <button class="btn btn-xs btn-default clear-filters-btn" style="
                        border-radius: 4px;
                        padding: 5px 15px;
                    ">
                        ❌ پاک کردن فیلترها
                    </button>
                </div>
            </div>
        `);

                    // قرار دادن container قبل از جدول
                    table_field.$wrapper.prepend(this.container);

                    // Event handlers
                    this.container.find('.add-filter-btn').on('click', () => this.add_filter_row());
                    this.container.find('.apply-filters-btn').on('click', () => this.apply_filters());
                    this.container.find('.clear-filters-btn').on('click', () => this.clear_filters());
                }

                /**
                 * اضافه کردن یک ردیف فیلتر
                 */
                add_filter_row() {
                    const fields = this.get_table_fields();
                    if (!fields.length) {
                        frappe.show_alert({
                            message: __('فیلدی برای فیلتر یافت نشد'),
                            indicator: 'orange'
                        });
                        return;
                    }

                    const filter_id = frappe.utils.get_random(8);
                    const field_options = fields.map(f =>
                        `<option value="${f.fieldname}" data-fieldtype="${f.fieldtype}">${f.label}</option>`
                    ).join('');

                    const operator_options = Object.entries(this.operators).map(([val, label]) =>
                        `<option value="${val}">${label}</option>`
                    ).join('');

                    const row = $(`
            <div class="filter-row" data-filter-id="${filter_id}" style="
                display: flex;
                gap: 8px;
                align-items: center;
                margin-bottom: 8px;
                padding: 8px;
                background: white;
                border-radius: 4px;
                border: 1px solid #ddd;
            ">
                <button class="btn btn-xs btn-danger remove-filter-btn" style="
                    border-radius: 50%;
                    width: 24px;
                    height: 24px;
                    padding: 0;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                ">×</button>
                <select class="filter-field form-control input-sm" style="
                    width: 150px;
                    border-radius: 4px;
                ">
                    ${field_options}
                </select>
                <select class="filter-operator form-control input-sm" style="
                    width: 120px;
                    border-radius: 4px;
                ">
                    ${operator_options}
                </select>
                <input type="text" class="filter-value form-control input-sm" placeholder="مقدار..." style="
                    flex: 1;
                    min-width: 150px;
                    border-radius: 4px;
                ">
            </div>
        `);

                    row.find('.remove-filter-btn').on('click', () => {
                        row.remove();
                        this.filters = this.filters.filter(f => f.id !== filter_id);
                    });

                    this.container.find('.filter-rows').append(row);
                    this.filters.push({ id: filter_id });
                }

                /**
                 * اعمال فیلترها
                 */
                apply_filters() {
                    const table_data = this.frm.doc[this.table_fieldname];
                    if (!table_data || !table_data.length) {
                        frappe.show_alert({
                            message: __('جدول خالی است'),
                            indicator: 'orange'
                        });
                        return;
                    }

                    // ذخیره داده اصلی
                    if (!this.original_data) {
                        this.original_data = JSON.parse(JSON.stringify(table_data));
                    }

                    // جمع‌آوری فیلترها
                    const active_filters = [];
                    this.container.find('.filter-row').each((i, row) => {
                        const $row = $(row);
                        const field = $row.find('.filter-field').val();
                        const operator = $row.find('.filter-operator').val();
                        const value = $row.find('.filter-value').val().trim();

                        if (field && value) {
                            active_filters.push({ field, operator, value });
                        }
                    });

                    if (!active_filters.length) {
                        frappe.show_alert({
                            message: __('لطفاً حداقل یک فیلتر با مقدار وارد کنید'),
                            indicator: 'orange'
                        });
                        return;
                    }

                    // فیلتر کردن داده‌ها
                    const filtered = this.original_data.filter(row => {
                        return active_filters.every(filter => {
                            const row_value = (row[filter.field] || '').toString().toLowerCase();
                            const filter_value = filter.value.toLowerCase();

                            switch (filter.operator) {
                                case 'like':
                                    return row_value.includes(filter_value);
                                case 'not_like':
                                    return !row_value.includes(filter_value);
                                case '=':
                                    return row_value === filter_value;
                                case '!=':
                                    return row_value !== filter_value;
                                case '>':
                                    return parseFloat(row_value) > parseFloat(filter_value);
                                case '<':
                                    return parseFloat(row_value) < parseFloat(filter_value);
                                case '>=':
                                    return parseFloat(row_value) >= parseFloat(filter_value);
                                case '<=':
                                    return parseFloat(row_value) <= parseFloat(filter_value);
                                default:
                                    return true;
                            }
                        });
                    });

                    // به‌روزرسانی جدول
                    this.frm.doc[this.table_fieldname] = filtered;
                    this.frm.refresh_field(this.table_fieldname);

                    frappe.show_alert({
                        message: __(`🔍 ${filtered.length} مورد از ${this.original_data.length} یافت شد`),
                        indicator: filtered.length > 0 ? 'green' : 'orange'
                    });
                }

                /**
                 * پاک کردن فیلترها
                 */
                clear_filters() {
                    // حذف همه ردیف‌های فیلتر
                    this.container.find('.filter-rows').empty();
                    this.filters = [];

                    // بازگردانی داده اصلی
                    if (this.original_data) {
                        this.frm.doc[this.table_fieldname] = JSON.parse(JSON.stringify(this.original_data));
                        this.frm.refresh_field(this.table_fieldname);
                        this.original_data = null;
                    }

                    frappe.show_alert({
                        message: __('فیلترها پاک شد'),
                        indicator: 'blue'
                    });
                }
            }

            /**
             * 🔧 راه‌اندازی فیلترهای داینامیک برای تمام جداول
             */
            function setup_dynamic_filters_for_all_tables(frm) {
                // لیست جداول مهم که فیلتر می‌خواهند
                const tables_to_filter = [
                    { fieldname: 'items', title: '📦 فیلتر کالاها' },
                    { fieldname: 'manual_material_prices', title: '🔍 فیلتر مواد اولیه' },
                    { fieldname: 'product_bundles', title: '📦 فیلتر بسته‌ها' },
                    { fieldname: 'pricing_steps', title: '📊 فیلتر مراحل قیمت‌گذاری' },
                    { fieldname: 'prev_items', title: '📋 فیلتر آیتم‌های قبلی' }
                ];

                // ذخیره instances در frm
                if (!frm._dynamic_filters) {
                    frm._dynamic_filters = {};
                }
                if (!frm._dynamic_sorters) {
                    frm._dynamic_sorters = {};
                }

                tables_to_filter.forEach(table => {
                    if (frm.fields_dict[table.fieldname]) {
                        // ایجاد filter instance اگر وجود ندارد
                        if (!frm._dynamic_filters[table.fieldname]) {
                            frm._dynamic_filters[table.fieldname] = new DynamicTableFilter(
                                frm,
                                table.fieldname,
                                { title: table.title }
                            );
                        }
                        // رندر filter UI
                        frm._dynamic_filters[table.fieldname].render();

                        // ایجاد sorter instance اگر وجود ندارد
                        if (!frm._dynamic_sorters[table.fieldname]) {
                            frm._dynamic_sorters[table.fieldname] = new DynamicTableSorter(
                                frm,
                                table.fieldname,
                                { title: table.title.replace('فیلتر', 'مرتب‌سازی') }
                            );
                        }
                        // رندر sorter UI
                        frm._dynamic_sorters[table.fieldname].render();
                    }
                });
            }

            /**
             * 📊 سیستم مرتب‌سازی داینامیک برای جداول
             * با قابلیت چندسطحی و drag & drop برای اولویت‌ها
             */
            class DynamicTableSorter {
                constructor(frm, table_fieldname, options = {}) {
                    this.frm = frm;
                    this.table_fieldname = table_fieldname;
                    this.sort_fields = [];
                    this.container = null;
                    this.options = Object.assign({
                        title: '📊 مرتب‌سازی جدول'
                    }, options);
                }

                /**
                 * گرفتن فیلدهای جدول
                 */
                get_table_fields() {
                    const table_df = this.frm.fields_dict[this.table_fieldname];
                    if (!table_df || !table_df.grid) return [];

                    const doctype = table_df.df.options;
                    const meta = frappe.get_meta(doctype);
                    if (!meta) return [];

                    return meta.fields.filter(f =>
                        !['Section Break', 'Column Break', 'Tab Break', 'HTML', 'Table'].includes(f.fieldtype) &&
                        f.fieldname !== 'name'
                    ).map(f => ({
                        fieldname: f.fieldname,
                        label: f.label || f.fieldname,
                        fieldtype: f.fieldtype
                    }));
                }

                /**
                 * رندر UI مرتب‌سازی
                 */
                render() {
                    const table_field = this.frm.fields_dict[this.table_fieldname];
                    if (!table_field || !table_field.$wrapper) return;

                    // حذف container قبلی
                    table_field.$wrapper.find('.dynamic-sorter-container').remove();

                    // ایجاد container مرتب‌سازی
                    this.container = $(`
            <div class="dynamic-sorter-container" style="
                margin-bottom: 10px;
                padding: 10px;
                background: #fff9e6;
                border: 1px solid #f0d070;
                border-radius: 8px;
            ">
                <div class="sorter-header" style="
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 10px;
                ">
                    <span style="font-weight: bold; color: #8a6d00;">
                        📊 ${this.options.title}
                    </span>
                    <button class="btn btn-xs btn-warning add-sort-btn" style="
                        border-radius: 4px;
                        padding: 4px 10px;
                        background: #ffc107;
                        border-color: #ffc107;
                        color: #333;
                    ">
                        ➕ افزودن مرتب‌سازی
                    </button>
                </div>
                <div class="sort-rows" style="
                    min-height: 30px;
                "></div>
                <div class="sorter-actions" style="
                    display: flex;
                    gap: 8px;
                    margin-top: 10px;
                ">
                    <button class="btn btn-xs btn-warning apply-sort-btn" style="
                        border-radius: 4px;
                        padding: 5px 15px;
                        background: #ffc107;
                        border-color: #ffc107;
                        color: #333;
                    ">
                        📊 اعمال مرتب‌سازی
                    </button>
                    <button class="btn btn-xs btn-default clear-sort-btn" style="
                        border-radius: 4px;
                        padding: 5px 15px;
                    ">
                        ❌ پاک کردن
                    </button>
                </div>
                <div class="sort-hint" style="
                    font-size: 11px;
                    color: #888;
                    margin-top: 8px;
                ">
                    💡 ردیف‌های مرتب‌سازی را با درگ و دراپ جابجا کنید (بالا = اولویت بالاتر)
                </div>
            </div>
        `);

                    // قرار دادن بعد از فیلتر
                    const filter_container = table_field.$wrapper.find('.dynamic-filter-container');
                    if (filter_container.length) {
                        filter_container.after(this.container);
                    } else {
                        table_field.$wrapper.prepend(this.container);
                    }

                    // Event handlers
                    this.container.find('.add-sort-btn').on('click', () => this.add_sort_row());
                    this.container.find('.apply-sort-btn').on('click', () => this.apply_sorting());
                    this.container.find('.clear-sort-btn').on('click', () => this.clear_sorting());

                    // فعال‌سازی drag & drop
                    this.enable_drag_drop();
                }

                /**
                 * فعال‌سازی drag & drop برای تغییر اولویت
                 */
                enable_drag_drop() {
                    const sort_rows = this.container.find('.sort-rows');

                    // استفاده از Sortable jQuery UI
                    if (typeof $.fn.sortable !== 'undefined') {
                        sort_rows.sortable({
                            handle: '.drag-handle',
                            axis: 'y',
                            containment: 'parent',
                            tolerance: 'pointer',
                            update: () => {
                                this.update_priorities();
                            }
                        });
                    } else {
                        // Fallback برای وابستگی به HTML5 drag & drop
                        sort_rows.on('dragover', (e) => {
                            e.preventDefault();
                            const afterElement = this.getDragAfterElement(sort_rows[0], e.originalEvent.clientY);
                            const dragging = sort_rows.find('.dragging')[0];
                            if (afterElement == null) {
                                sort_rows.append(dragging);
                            } else {
                                $(afterElement).before(dragging);
                            }
                        });
                    }
                }

                getDragAfterElement(container, y) {
                    const draggableElements = [...container.querySelectorAll('.sort-row:not(.dragging)')];
                    return draggableElements.reduce((closest, child) => {
                        const box = child.getBoundingClientRect();
                        const offset = y - box.top - box.height / 2;
                        if (offset < 0 && offset > closest.offset) {
                            return { offset: offset, element: child };
                        } else {
                            return closest;
                        }
                    }, { offset: Number.NEGATIVE_INFINITY }).element;
                }

                /**
                 * به‌روزرسانی شماره اولویت‌ها
                 */
                update_priorities() {
                    this.container.find('.sort-row').each((i, row) => {
                        $(row).find('.priority-number').text(i + 1);
                    });
                }

                /**
                 * اضافه کردن یک ردیف مرتب‌سازی
                 */
                add_sort_row() {
                    const fields = this.get_table_fields();
                    if (!fields.length) {
                        frappe.show_alert({
                            message: __('فیلدی برای مرتب‌سازی یافت نشد'),
                            indicator: 'orange'
                        });
                        return;
                    }

                    const sort_id = frappe.utils.get_random(8);
                    const priority = this.container.find('.sort-row').length + 1;

                    const field_options = fields.map(f =>
                        `<option value="${f.fieldname}">${f.label}</option>`
                    ).join('');

                    const row = $(`
            <div class="sort-row" data-sort-id="${sort_id}" draggable="true" style="
                display: flex;
                gap: 8px;
                align-items: center;
                margin-bottom: 8px;
                padding: 8px;
                background: white;
                border-radius: 4px;
                border: 1px solid #f0d070;
                cursor: move;
            ">
                <span class="drag-handle" style="
                    cursor: grab;
                    font-size: 16px;
                    color: #ffc107;
                    padding: 0 5px;
                ">☰</span>
                <span class="priority-number" style="
                    background: #ffc107;
                    color: #333;
                    border-radius: 50%;
                    width: 24px;
                    height: 24px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-weight: bold;
                    font-size: 12px;
                ">${priority}</span>
                <select class="sort-field form-control input-sm" style="
                    width: 150px;
                    border-radius: 4px;
                ">
                    ${field_options}
                </select>
                <select class="sort-direction form-control input-sm" style="
                    width: 100px;
                    border-radius: 4px;
                ">
                    <option value="asc">صعودی ⬆️</option>
                    <option value="desc">نزولی ⬇️</option>
                </select>
                <button class="btn btn-xs btn-danger remove-sort-btn" style="
                    border-radius: 50%;
                    width: 24px;
                    height: 24px;
                    padding: 0;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                ">×</button>
            </div>
        `);

                    // Event handlers
                    row.find('.remove-sort-btn').on('click', () => {
                        row.remove();
                        this.update_priorities();
                    });

                    // HTML5 Drag events
                    row.on('dragstart', () => {
                        row.addClass('dragging');
                        row.css('opacity', '0.5');
                    });
                    row.on('dragend', () => {
                        row.removeClass('dragging');
                        row.css('opacity', '1');
                        this.update_priorities();
                    });

                    this.container.find('.sort-rows').append(row);
                }

                /**
                 * اعمال مرتب‌سازی
                 */
                apply_sorting() {
                    const table_data = this.frm.doc[this.table_fieldname];
                    if (!table_data || !table_data.length) {
                        frappe.show_alert({
                            message: __('جدول خالی است'),
                            indicator: 'orange'
                        });
                        return;
                    }

                    // جمع‌آوری تنظیمات مرتب‌سازی
                    const sort_configs = [];
                    this.container.find('.sort-row').each((i, row) => {
                        const $row = $(row);
                        const field = $row.find('.sort-field').val();
                        const direction = $row.find('.sort-direction').val();
                        if (field) {
                            sort_configs.push({ field, direction });
                        }
                    });

                    if (!sort_configs.length) {
                        frappe.show_alert({
                            message: __('لطفاً حداقل یک فیلد برای مرتب‌سازی انتخاب کنید'),
                            indicator: 'orange'
                        });
                        return;
                    }

                    // مرتب‌سازی چندسطحی
                    const sorted = [...table_data].sort((a, b) => {
                        for (const config of sort_configs) {
                            const val_a = a[config.field];
                            const val_b = b[config.field];

                            let compare = 0;

                            // مقایسه بر اساس نوع داده
                            if (typeof val_a === 'number' && typeof val_b === 'number') {
                                compare = val_a - val_b;
                            } else {
                                const str_a = (val_a || '').toString().toLowerCase();
                                const str_b = (val_b || '').toString().toLowerCase();
                                compare = str_a.localeCompare(str_b, 'fa');
                            }

                            // اعمال جهت
                            if (config.direction === 'desc') {
                                compare = -compare;
                            }

                            if (compare !== 0) {
                                return compare;
                            }
                        }
                        return 0;
                    });

                    // به‌روزرسانی جدول
                    this.frm.doc[this.table_fieldname] = sorted;
                    this.frm.refresh_field(this.table_fieldname);

                    frappe.show_alert({
                        message: __(`📊 ${sorted.length} ردیف مرتب شد`),
                        indicator: 'green'
                    });
                }

                /**
                 * پاک کردن مرتب‌سازی
                 */
                clear_sorting() {
                    this.container.find('.sort-rows').empty();

                    frappe.show_alert({
                        message: __('تنظیمات مرتب‌سازی پاک شد'),
                        indicator: 'blue'
                    });
                }
            }

            function show_analytics_dashboard_button(frm) {
                console.log("show_analytics_dashboard_button called");

                frappe.call({
                    method: 'get_analytics_dashboard',
                    doc: frm.doc,
                    callback: function (r) {
                        if (r.message) {
                            let d = new frappe.ui.Dialog({
                                title: __('📊 تحلیل پیشرفته'),
                                fields: [
                                    {
                                        fieldtype: 'HTML',
                                        fieldname: 'analytics_html',
                                    }
                                ],
                                size: 'extra-large'
                            });
                            d.fields_dict.analytics_html.$wrapper.html(r.message);
                            d.show();
                        }
                    }
                });
            }
        }
    }
}
