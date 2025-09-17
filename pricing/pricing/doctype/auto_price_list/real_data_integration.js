// Real Data Integration Functions for Auto Price List

function integrate_real_purchase_data(frm) {
    frappe.confirm(
        __('This will integrate real purchase invoice data into your pricing calculations. Continue?'),
        function() {
            frappe.call({
                method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.integrate_real_data_for_pricing',
                args: {
                    docname: frm.doc.name
                },
                callback: function(r) {
                    if (r.message && r.message.status === 'success') {
                        frappe.msgprint({
                            title: __('Real Data Integration Complete'),
                            message: r.message.message,
                            indicator: 'green'
                        });
                        frm.refresh();
                    } else {
                        frappe.msgprint({
                            title: __('Integration Failed'),
                            message: r.message ? r.message.message : 'Unknown error occurred',
                            indicator: 'red'
                        });
                    }
                }
            });
        }
    );
}

function show_purchase_analysis(frm) {
    let dialog = new frappe.ui.Dialog({
        title: __('Purchase Data Analysis'),
        size: 'extra-large',
        fields: [
            {
                fieldtype: 'Select',
                fieldname: 'item_code',
                label: __('Select Item'),
                options: frm.doc.items.map(item => item.item_code).join('\n'),
                reqd: 1
            },
            {
                fieldtype: 'Button',
                fieldname: 'analyze_btn',
                label: __('Analyze Purchase Data')
            },
            {
                fieldtype: 'HTML',
                fieldname: 'analysis_html'
            }
        ]
    });

    dialog.fields_dict.analyze_btn.$input.click(function() {
        let item_code = dialog.get_value('item_code');
        if (!item_code) {
            frappe.msgprint(__('Please select an item'));
            return;
        }

        frappe.call({
            method: 'get_real_purchase_costs',
            doc: frm.doc,
            args: {
                item_code: item_code
            },
            callback: function(r) {
                if (r.message) {
                    let html = generate_purchase_analysis_html(r.message);
                    dialog.fields_dict.analysis_html.$wrapper.html(html);
                } else {
                    dialog.fields_dict.analysis_html.$wrapper.html('<p>No purchase data found for this item</p>');
                }
            }
        });
    });

    dialog.show();
}

function generate_purchase_analysis_html(data) {
    let html = `
        <div class="purchase-analysis">
            <div class="row">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header"><h6>Purchase Summary</h6></div>
                        <div class="card-body">
                            <table class="table table-sm">
                                <tr><td>Total Purchases:</td><td>${data.total_purchases}</td></tr>
                                <tr><td>Total Quantity:</td><td>${data.total_quantity.toFixed(2)}</td></tr>
                                <tr><td>Total Amount:</td><td>${frappe.format(data.total_amount, {fieldtype: 'Currency'})}</td></tr>
                                <tr><td>Average Rate:</td><td>${frappe.format(data.average_rate, {fieldtype: 'Currency'})}</td></tr>
                                <tr><td>Latest Rate:</td><td>${frappe.format(data.latest_rate, {fieldtype: 'Currency'})}</td></tr>
                            </table>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header"><h6>Price Variance</h6></div>
                        <div class="card-body">
                            <table class="table table-sm">
                                <tr><td>Min Rate:</td><td>${frappe.format(data.min_rate, {fieldtype: 'Currency'})}</td></tr>
                                <tr><td>Max Rate:</td><td>${frappe.format(data.max_rate, {fieldtype: 'Currency'})}</td></tr>
                                <tr><td>Rate Variance:</td><td>${data.rate_variance.toFixed(2)}%</td></tr>
                                <tr><td>Suppliers:</td><td>${data.suppliers.length}</td></tr>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="row mt-3">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-header"><h6>Recent Purchases</h6></div>
                        <div class="card-body">
                            <div class="table-responsive">
                                <table class="table table-striped">
                                    <thead>
                                        <tr>
                                            <th>Date</th>
                                            <th>Invoice</th>
                                            <th>Supplier</th>
                                            <th>Rate</th>
                                            <th>Quantity</th>
                                            <th>Amount</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${data.recent_purchases.map(purchase => `
                                            <tr>
                                                <td>${frappe.datetime.str_to_user(purchase.posting_date)}</td>
                                                <td>${purchase.invoice_name}</td>
                                                <td>${purchase.supplier}</td>
                                                <td>${frappe.format(purchase.rate, {fieldtype: 'Currency'})}</td>
                                                <td>${purchase.qty}</td>
                                                <td>${frappe.format(purchase.amount, {fieldtype: 'Currency'})}</td>
                                            </tr>
                                        `).join('')}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    return html;
}

function show_quotation_insights(frm) {
    let dialog = new frappe.ui.Dialog({
        title: __('Quotation Insights'),
        size: 'extra-large',
        fields: [
            {
                fieldtype: 'Select',
                fieldname: 'item_code',
                label: __('Select Item'),
                options: frm.doc.items.map(item => item.item_code).join('\n'),
                reqd: 1
            },
            {
                fieldtype: 'Button',
                fieldname: 'analyze_btn',
                label: __('Analyze Quotations')
            },
            {
                fieldtype: 'HTML',
                fieldname: 'insights_html'
            }
        ]
    });

    dialog.fields_dict.analyze_btn.$input.click(function() {
        let item_code = dialog.get_value('item_code');
        if (!item_code) {
            frappe.msgprint(__('Please select an item'));
            return;
        }

        frappe.call({
            method: 'get_quotation_analysis',
            doc: frm.doc,
            args: {
                item_code: item_code
            },
            callback: function(r) {
                if (r.message) {
                    let html = generate_quotation_insights_html(r.message);
                    dialog.fields_dict.insights_html.$wrapper.html(html);
                } else {
                    dialog.fields_dict.insights_html.$wrapper.html('<p>No quotation data found for this item</p>');
                }
            }
        });
    });

    dialog.show();
}

function generate_quotation_insights_html(data) {
    let win_rate_class = data.win_rate >= 70 ? 'success' : data.win_rate >= 40 ? 'warning' : 'danger';
    
    let html = `
        <div class="quotation-insights">
            <div class="row">
                <div class="col-md-4">
                    <div class="card text-center">
                        <div class="card-body">
                            <h2 class="text-${win_rate_class}">${data.win_rate.toFixed(1)}%</h2>
                            <p>Win Rate</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card text-center">
                        <div class="card-body">
                            <h2 class="text-primary">${data.total_quotations}</h2>
                            <p>Total Quotations</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card text-center">
                        <div class="card-body">
                            <h2 class="text-info">${frappe.format(data.optimal_price_range.recommended, {fieldtype: 'Currency'})}</h2>
                            <p>Recommended Price</p>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="row mt-3">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header"><h6>Price Analysis</h6></div>
                        <div class="card-body">
                            <table class="table table-sm">
                                <tr><td>Average Quoted:</td><td>${frappe.format(data.average_quoted_rate, {fieldtype: 'Currency'})}</td></tr>
                                <tr><td>Average Won:</td><td>${frappe.format(data.average_won_rate, {fieldtype: 'Currency'})}</td></tr>
                                <tr><td>Average Lost:</td><td>${frappe.format(data.average_lost_rate, {fieldtype: 'Currency'})}</td></tr>
                                <tr><td>Price Range (Won):</td><td>${frappe.format(data.optimal_price_range.min, {fieldtype: 'Currency'})} - ${frappe.format(data.optimal_price_range.max, {fieldtype: 'Currency'})}</td></tr>
                            </table>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header"><h6>Performance Metrics</h6></div>
                        <div class="card-body">
                            <table class="table table-sm">
                                <tr><td>Won Quotations:</td><td>${data.won_quotations}</td></tr>
                                <tr><td>Lost Quotations:</td><td>${data.lost_quotations}</td></tr>
                                <tr><td>Unique Customers:</td><td>${data.customers.length}</td></tr>
                                <tr><td>Success Rate:</td><td><span class="badge badge-${win_rate_class}">${data.win_rate.toFixed(1)}%</span></td></tr>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="row mt-3">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-header"><h6>Recent Quotations</h6></div>
                        <div class="card-body">
                            <div class="table-responsive">
                                <table class="table table-striped">
                                    <thead>
                                        <tr>
                                            <th>Date</th>
                                            <th>Quotation</th>
                                            <th>Customer</th>
                                            <th>Rate</th>
                                            <th>Status</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${data.recent_quotations.map(quotation => `
                                            <tr>
                                                <td>${frappe.datetime.str_to_user(quotation.transaction_date)}</td>
                                                <td>${quotation.quotation_name}</td>
                                                <td>${quotation.customer}</td>
                                                <td>${frappe.format(quotation.rate, {fieldtype: 'Currency'})}</td>
                                                <td><span class="badge badge-${quotation.status === 'Ordered' ? 'success' : quotation.status === 'Lost' ? 'danger' : 'warning'}">${quotation.status}</span></td>
                                            </tr>
                                        `).join('')}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    return html;
}
