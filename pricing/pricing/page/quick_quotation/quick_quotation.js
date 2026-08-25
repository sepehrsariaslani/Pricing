frappe.pages['quick-quotation'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'قیمت‌گذاری سریع',
        single_column: true
    });
    
    // ایجاد instance از کلاس صفحه
    new QuickQuotation(page);
};

class QuickQuotation {
    constructor(page) {
        this.page = page;
        this.selected_items = [];
        this.settings = {};
        
        this.make();
        this.setup_buttons();
        this.load_settings();
    }
    
    make() {
        this.page.main.html(`
            <div class="quick-quotation-container" style="padding: 20px; direction: rtl;">
                <!-- بخش جستجو و اضافه کردن کالا -->
                <div class="row" style="margin-bottom: 20px;">
                    <div class="col-md-8">
                        <div class="frappe-control" id="item-search-wrapper"></div>
                    </div>
                    <div class="col-md-2">
                        <div class="frappe-control" id="qty-wrapper"></div>
                    </div>
                    <div class="col-md-2">
                        <button class="btn btn-primary btn-block" id="add-item-btn">
                            <i class="fa fa-plus"></i> افزودن
                        </button>
                    </div>
                </div>
                
                <!-- جدول کالاهای انتخاب شده -->
                <div class="selected-items-section" style="margin-bottom: 20px;">
                    <h4 style="margin-bottom: 15px; border-bottom: 2px solid #5e64ff; padding-bottom: 10px;">
                        <i class="fa fa-shopping-cart"></i> کالاهای انتخاب شده
                    </h4>
                    <div id="items-table-wrapper">
                        <table class="table table-bordered table-hover" id="items-table">
                            <thead style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;">
                                <tr>
                                    <th style="width: 40px;">#</th>
                                    <th>کد کالا</th>
                                    <th>نام کالا</th>
                                    <th style="width: 80px;">تعداد</th>
                                    <th>بهای تمام شده</th>
                                    <th>قیمت فروش</th>
                                    <th>سود</th>
                                    <th>قیمت با تخفیف</th>
                                    <th>قیمت قسطی</th>
                                    <th style="width: 60px;">حذف</th>
                                </tr>
                            </thead>
                            <tbody id="items-tbody">
                                <tr id="empty-row">
                                    <td colspan="10" style="text-align: center; color: #999; padding: 30px;">
                                        <i class="fa fa-info-circle"></i> کالایی انتخاب نشده است
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
                
                <!-- بخش خلاصه و جمع کل -->
                <div class="summary-section" style="background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                    <div class="row">
                        <div class="col-md-3">
                            <div class="summary-card" style="background: white; padding: 15px; border-radius: 8px; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                                <h5 style="color: #666; margin-bottom: 5px;">مجموع بهای تمام شده</h5>
                                <h3 id="total-cost" style="color: #e74c3c; margin: 0;">0</h3>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="summary-card" style="background: white; padding: 15px; border-radius: 8px; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                                <h5 style="color: #666; margin-bottom: 5px;">مجموع قیمت فروش</h5>
                                <h3 id="total-selling" style="color: #3498db; margin: 0;">0</h3>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="summary-card" style="background: white; padding: 15px; border-radius: 8px; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                                <h5 style="color: #666; margin-bottom: 5px;">مجموع سود</h5>
                                <h3 id="total-profit" style="color: #27ae60; margin: 0;">0</h3>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="summary-card" style="background: white; padding: 15px; border-radius: 8px; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                                <h5 style="color: #666; margin-bottom: 5px;">مجموع قسطی</h5>
                                <h3 id="total-installment" style="color: #9b59b6; margin: 0;">0</h3>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- جزئیات قسط -->
                <div class="installment-details" id="installment-details" style="background: #fff3cd; padding: 15px; border-radius: 8px; margin-bottom: 20px; display: none;">
                    <h5 style="color: #856404; margin-bottom: 10px;">
                        <i class="fa fa-calculator"></i> جزئیات پرداخت قسطی
                    </h5>
                    <div class="row">
                        <div class="col-md-3">
                            <strong>پیش پرداخت:</strong> <span id="detail-down-payment">0</span>
                        </div>
                        <div class="col-md-3">
                            <strong>قسط ماهانه:</strong> <span id="detail-monthly-payment">0</span>
                        </div>
                        <div class="col-md-3">
                            <strong>تعداد اقساط:</strong> <span id="detail-months">0</span> ماه
                        </div>
                        <div class="col-md-3">
                            <strong>مجموع بهره:</strong> <span id="detail-total-interest">0</span>
                        </div>
                    </div>
                </div>
                
                <!-- دکمه‌های عملیات -->
                <div class="action-buttons" style="text-align: left;">
                    <button class="btn btn-danger" id="clear-all-btn" style="margin-left: 10px;">
                        <i class="fa fa-trash"></i> پاک کردن همه
                    </button>
                    <button class="btn btn-success" id="create-quotation-btn">
                        <i class="fa fa-file-text"></i> ایجاد پیش‌فاکتور
                    </button>
                    <button class="btn btn-info" id="print-btn" style="margin-right: 10px;">
                        <i class="fa fa-print"></i> چاپ
                    </button>
                </div>
            </div>
        `);
        
        this.setup_fields();
        this.setup_events();
    }
    
    setup_fields() {
        // فیلد جستجوی کالا
        this.item_search = frappe.ui.form.make_control({
            df: {
                fieldname: 'item_code',
                fieldtype: 'Link',
                options: 'Item',
                label: 'جستجوی کالا',
                placeholder: 'کد یا نام کالا را وارد کنید...'
            },
            parent: this.page.main.find('#item-search-wrapper'),
            render_input: true
        });
        
        // فیلد تعداد
        this.qty_field = frappe.ui.form.make_control({
            df: {
                fieldname: 'qty',
                fieldtype: 'Float',
                label: 'تعداد',
                default: 1
            },
            parent: this.page.main.find('#qty-wrapper'),
            render_input: true
        });
        this.qty_field.set_value(1);
    }
    
    setup_events() {
        let me = this;
        
        // دکمه افزودن کالا
        this.page.main.find('#add-item-btn').on('click', () => {
            me.add_item();
        });
        
        // Enter در فیلد جستجو
        this.page.main.find('#item-search-wrapper input').on('keypress', function(e) {
            if (e.which == 13) {
                me.add_item();
            }
        });
        
        // دکمه پاک کردن همه
        this.page.main.find('#clear-all-btn').on('click', () => {
            me.clear_all();
        });
        
        // دکمه ایجاد پیش‌فاکتور
        this.page.main.find('#create-quotation-btn').on('click', () => {
            me.create_quotation();
        });
        
        // دکمه چاپ
        this.page.main.find('#print-btn').on('click', () => {
            me.print_quotation();
        });
    }
    
    setup_buttons() {
        // دکمه تنظیمات
        this.page.set_secondary_action('تنظیمات', () => {
            this.show_settings_dialog();
        }, 'octicon octicon-gear');
    }
    
    load_settings() {
        // بارگذاری تنظیمات از آخرین Auto Price List
        frappe.call({
            method: 'pricing.pricing.page.quick_quotation.quick_quotation.get_auto_price_lists',
            callback: (r) => {
                if (r.message && r.message.length > 0) {
                    this.settings = r.message[0];
                }
            }
        });
    }
    
    add_item() {
        let item_code = this.item_search.get_value();
        let qty = this.qty_field.get_value() || 1;
        
        if (!item_code) {
            frappe.show_alert({
                message: 'لطفاً کالا را انتخاب کنید',
                indicator: 'orange'
            });
            return;
        }
        
        // بررسی تکراری نبودن
        let existing = this.selected_items.find(i => i.item_code === item_code);
        if (existing) {
            existing.qty += qty;
            this.refresh_item_prices();
            return;
        }
        
        // دریافت قیمت کالا
        frappe.call({
            method: 'pricing.pricing.page.quick_quotation.quick_quotation.get_item_price_details',
            args: {
                item_code: item_code,
                qty: qty
            },
            callback: (r) => {
                if (r.message && !r.message.error) {
                    this.selected_items.push(r.message);
                    this.render_items_table();
                    this.update_totals();
                    
                    // پاک کردن فیلدها
                    this.item_search.set_value('');
                    this.qty_field.set_value(1);
                    this.item_search.$input.focus();
                } else {
                    frappe.show_alert({
                        message: r.message.error || 'خطا در دریافت قیمت',
                        indicator: 'red'
                    });
                }
            }
        });
    }
    
    render_items_table() {
        let tbody = this.page.main.find('#items-tbody');
        tbody.empty();
        
        if (this.selected_items.length === 0) {
            tbody.html(`
                <tr id="empty-row">
                    <td colspan="10" style="text-align: center; color: #999; padding: 30px;">
                        <i class="fa fa-info-circle"></i> کالایی انتخاب نشده است
                    </td>
                </tr>
            `);
            return;
        }
        
        let me = this;
        this.selected_items.forEach((item, index) => {
            let prices = item.prices || {};
            let installment = item.installment || {};
            
            let row = $(`
                <tr data-index="${index}">
                    <td>${index + 1}</td>
                    <td><strong>${item.item_code}</strong></td>
                    <td>${item.item_name || ''}</td>
                    <td>
                        <input type="number" class="form-control qty-input" 
                               value="${item.qty}" min="1" style="width: 70px; text-align: center;">
                    </td>
                    <td style="color: #e74c3c;">${this.format_currency(prices.total_cost)}</td>
                    <td style="color: #3498db; font-weight: bold;">${this.format_currency(prices.total_selling_price)}</td>
                    <td style="color: ${prices.total_profit >= 0 ? '#27ae60' : '#e74c3c'};">
                        ${this.format_currency(prices.total_profit)}
                        <small>(${(prices.profit_percentage || 0).toFixed(1)}%)</small>
                    </td>
                    <td style="color: #8e44ad;">${this.format_currency(prices.total_price_with_markup || prices.total_selling_price)}</td>
                    <td style="color: #9b59b6;">${this.format_currency(installment.total_amount || 0)}</td>
                    <td>
                        <button class="btn btn-danger btn-xs remove-item-btn">
                            <i class="fa fa-times"></i>
                        </button>
                    </td>
                </tr>
            `);
            
            // رویداد تغییر تعداد
            row.find('.qty-input').on('change', function() {
                item.qty = parseFloat($(this).val()) || 1;
                me.refresh_item_prices();
            });
            
            // رویداد حذف
            row.find('.remove-item-btn').on('click', function() {
                me.selected_items.splice(index, 1);
                me.render_items_table();
                me.update_totals();
            });
            
            tbody.append(row);
        });
    }
    
    refresh_item_prices() {
        let items = this.selected_items.map(item => ({
            item_code: item.item_code,
            qty: item.qty
        }));
        
        frappe.call({
            method: 'pricing.pricing.page.quick_quotation.quick_quotation.get_multiple_items_prices',
            args: { items: items },
            callback: (r) => {
                if (r.message && r.message.items) {
                    this.selected_items = r.message.items;
                    this.render_items_table();
                    this.update_totals();
                }
            }
        });
    }
    
    update_totals() {
        let totals = {
            cost: 0,
            selling: 0,
            profit: 0,
            installment: 0,
            down_payment: 0,
            monthly_payment: 0,
            interest: 0,
            months: 0
        };
        
        this.selected_items.forEach(item => {
            let prices = item.prices || {};
            let installment = item.installment || {};
            
            totals.cost += prices.total_cost || 0;
            totals.selling += prices.total_selling_price || 0;
            totals.profit += prices.total_profit || 0;
            totals.installment += installment.total_amount || 0;
            totals.down_payment += installment.down_payment || 0;
            totals.monthly_payment += installment.monthly_payment || 0;
            totals.interest += installment.total_interest || 0;
            if (installment.number_of_months) totals.months = installment.number_of_months;
        });
        
        this.page.main.find('#total-cost').text(this.format_currency(totals.cost));
        this.page.main.find('#total-selling').text(this.format_currency(totals.selling));
        this.page.main.find('#total-profit').text(this.format_currency(totals.profit));
        this.page.main.find('#total-installment').text(this.format_currency(totals.installment));
        
        // نمایش جزئیات قسط
        if (totals.installment > 0) {
            this.page.main.find('#installment-details').show();
            this.page.main.find('#detail-down-payment').text(this.format_currency(totals.down_payment));
            this.page.main.find('#detail-monthly-payment').text(this.format_currency(totals.monthly_payment));
            this.page.main.find('#detail-months').text(totals.months);
            this.page.main.find('#detail-total-interest').text(this.format_currency(totals.interest));
        } else {
            this.page.main.find('#installment-details').hide();
        }
    }
    
    clear_all() {
        frappe.confirm('آیا می‌خواهید همه کالاها را پاک کنید؟', () => {
            this.selected_items = [];
            this.render_items_table();
            this.update_totals();
        });
    }
    
    create_quotation() {
        if (this.selected_items.length === 0) {
            frappe.show_alert({
                message: 'هیچ کالایی انتخاب نشده است',
                indicator: 'orange'
            });
            return;
        }
        
        let d = new frappe.ui.Dialog({
            title: 'ایجاد پیش‌فاکتور',
            fields: [
                {
                    fieldname: 'customer',
                    fieldtype: 'Link',
                    options: 'Customer',
                    label: 'مشتری'
                },
                {
                    fieldname: 'price_type',
                    fieldtype: 'Select',
                    label: 'نوع قیمت',
                    options: 'selling_price\nwith_markup\ninstallment',
                    default: 'selling_price'
                }
            ],
            primary_action_label: 'ایجاد',
            primary_action: (values) => {
                frappe.call({
                    method: 'pricing.pricing.page.quick_quotation.quick_quotation.create_quotation_from_items',
                    args: {
                        items: this.selected_items.map(i => ({
                            item_code: i.item_code,
                            qty: i.qty
                        })),
                        customer: values.customer,
                        price_type: values.price_type
                    },
                    callback: (r) => {
                        if (r.message && r.message.success) {
                            frappe.show_alert({
                                message: r.message.message,
                                indicator: 'green'
                            });
                            frappe.set_route('Form', 'Quotation', r.message.quotation);
                        }
                    }
                });
                d.hide();
            }
        });
        d.show();
    }
    
    print_quotation() {
        let me = this;
        let print_html = `
            <div style="direction: rtl; font-family: Tahoma, Arial; padding: 20px;">
                <h2 style="text-align: center; border-bottom: 2px solid #333; padding-bottom: 10px;">
                    پیشنهاد قیمت
                </h2>
                <p style="text-align: left;">تاریخ: ${frappe.datetime.nowdate()}</p>
                
                <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                    <thead>
                        <tr style="background: #333; color: white;">
                            <th style="padding: 10px; border: 1px solid #333;">ردیف</th>
                            <th style="padding: 10px; border: 1px solid #333;">کد کالا</th>
                            <th style="padding: 10px; border: 1px solid #333;">نام کالا</th>
                            <th style="padding: 10px; border: 1px solid #333;">تعداد</th>
                            <th style="padding: 10px; border: 1px solid #333;">قیمت واحد</th>
                            <th style="padding: 10px; border: 1px solid #333;">قیمت کل</th>
                        </tr>
                    </thead>
                    <tbody>
        `;
        
        let total = 0;
        this.selected_items.forEach((item, index) => {
            let prices = item.prices || {};
            let unit_price = prices.unit_selling_price || 0;
            let total_price = prices.total_selling_price || 0;
            total += total_price;
            
            print_html += `
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">${index + 1}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">${item.item_code}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">${item.item_name || ''}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">${item.qty}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: left;">${me.format_currency(unit_price)}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: left;">${me.format_currency(total_price)}</td>
                </tr>
            `;
        });
        
        print_html += `
                    </tbody>
                    <tfoot>
                        <tr style="background: #f5f5f5; font-weight: bold;">
                            <td colspan="5" style="padding: 10px; border: 1px solid #ddd; text-align: left;">جمع کل:</td>
                            <td style="padding: 10px; border: 1px solid #ddd; text-align: left;">${me.format_currency(total)}</td>
                        </tr>
                    </tfoot>
                </table>
            </div>
        `;
        
        let w = window.open();
        w.document.write(print_html);
        w.document.close();
        w.print();
    }
    
    show_settings_dialog() {
        let d = new frappe.ui.Dialog({
            title: 'تنظیمات قیمت‌گذاری',
            fields: [
                {
                    fieldname: 'auto_price_list',
                    fieldtype: 'Link',
                    options: 'Auto Price List',
                    label: 'لیست قیمت خودکار'
                },
                {
                    fieldname: 'profit_margin',
                    fieldtype: 'Percent',
                    label: 'درصد سود',
                    default: 20
                },
                {
                    fieldname: 'target_discount_percentage',
                    fieldtype: 'Percent',
                    label: 'درصد تخفیف هدف'
                }
            ],
            primary_action_label: 'ذخیره',
            primary_action: (values) => {
                this.settings = values;
                d.hide();
                this.refresh_item_prices();
            }
        });
        d.show();
    }
    
    format_currency(value) {
        if (!value) return '0 ریال';
        return new Intl.NumberFormat('fa-IR').format(Math.round(value)) + ' ریال';
    }
}

