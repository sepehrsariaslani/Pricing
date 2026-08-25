function show_enhanced_product_results(product_info) {
    let result_html = `
        <div style="padding: 20px; max-height: 600px; overflow-y: auto;">
            <h3 style="color: #28a745;">✅ کرال محصول موفقیت‌آمیز بود!</h3>
            <hr>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;">
                <div>
                    <h5>📋 اطلاعات اصلی</h5>
                    <p><strong>عنوان:</strong> ${product_info.title || 'نامشخص'}</p>
                    <p><strong>قیمت:</strong> ${format_number(product_info.price)} ${product_info.currency || 'تومان'}</p>
                    <p><strong>برند:</strong> ${product_info.brand || 'نامشخص'}</p>
                    <p><strong>کد محصول:</strong> ${product_info.sku || 'نامشخص'}</p>
                    <p><strong>دسته‌بندی:</strong> ${product_info.category || 'نامشخص'}</p>
                    <p><strong>موجودی:</strong> ${product_info.availability || 'نامشخص'}</p>
                </div>
                
                <div>
                    <h5>⭐ امتیاز و نظرات</h5>
                    <p><strong>امتیاز:</strong> ${product_info.rating || 0}/5</p>
                    <p><strong>تعداد نظرات:</strong> ${format_number(product_info.reviews_count || 0)}</p>
                    <p><strong>طول توضیحات:</strong> ${format_number(product_info.description_length || 0)} کاراکتر</p>
                    <p><strong>امتیاز کیفیت داده:</strong> ${product_info.data_quality_score || 0}%</p>
                    <p><strong>زمان کرال:</strong> ${product_info.crawl_time || 0} ثانیه</p>
                </div>
            </div>
            
            <div style="margin-bottom: 20px;">
                <h5>🔧 مشخصات فنی (${product_info.specifications_count || 0} مورد)</h5>
                ${product_info.specifications && Object.keys(product_info.specifications).length > 0 ? 
                    `<div style="background: #f8f9fa; padding: 10px; border-radius: 5px; max-height: 200px; overflow-y: auto;">
                        ${Object.entries(product_info.specifications).map(([key, value]) => 
                            `<p style="margin: 5px 0;"><strong>${key}:</strong> ${value}</p>`
                        ).join('')}
                    </div>` 
                    : '<p style="color: #6c757d;">مشخصات فنی یافت نشد</p>'
                }
            </div>
            
            <div style="margin-bottom: 20px;">
                <h5>🏷️ کلمات کلیدی SEO (${product_info.keywords_count || 0} مورد)</h5>
                ${product_info.keywords && product_info.keywords.length > 0 ? 
                    `<div style="background: #e3f2fd; padding: 10px; border-radius: 5px;">
                        ${product_info.keywords.map(keyword => 
                            `<span style="background: #2196f3; color: white; padding: 3px 8px; margin: 2px; border-radius: 12px; font-size: 12px; display: inline-block;">${keyword}</span>`
                        ).join('')}
                    </div>` 
                    : '<p style="color: #6c757d;">کلمات کلیدی یافت نشد</p>'
                }
            </div>
            
            <div style="margin-bottom: 20px;">
                <h5>🖼️ تصاویر محصول (${product_info.images_count || 0} مورد)</h5>
                ${product_info.images && product_info.images.length > 0 ? 
                    `<div style="display: flex; gap: 10px; flex-wrap: wrap;">
                        ${product_info.images.map(img => 
                            `<img src="${img}" style="width: 80px; height: 80px; object-fit: cover; border-radius: 5px; border: 1px solid #ddd;" onerror="this.style.display='none'">`
                        ).join('')}
                    </div>` 
                    : '<p style="color: #6c757d;">تصاویر یافت نشد</p>'
                }
            </div>
            
            <div style="margin-bottom: 20px;">
                <h5>🔍 اطلاعات SEO</h5>
                <p><strong>عنوان SEO:</strong> ${product_info.seo_title || 'نامشخص'}</p>
                <p><strong>توضیحات SEO:</strong> ${product_info.seo_description || 'نامشخص'}</p>
            </div>
            
            ${product_info.json_file ? 
                `<div style="text-align: center; padding: 15px; background: #d4edda; border-radius: 5px;">
                    <h5 style="color: #155724;">📁 فایل JSON کامل</h5>
                    <a href="${product_info.json_file}" target="_blank" class="btn btn-success btn-sm">
                        دانلود اطلاعات کامل JSON
                    </a>
                </div>` 
                : ''
            }
        </div>
    `;
    
    let result_dialog = new frappe.ui.Dialog({
        title: __('نتیجه کرال پیشرفته محصول'),
        size: 'extra-large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'result_html',
                options: result_html
            }
        ],
        primary_action_label: __('بستن'),
        primary_action() {
            result_dialog.hide();
        }
    });
    
    result_dialog.show();
}

function show_batch_crawl_results(batch_result) {
    let result_html = `
        <div style="padding: 20px;">
            <h3 style="color: #28a745;">📊 نتیجه کرال دسته‌ای</h3>
            <hr>
            
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 20px;">
                <div style="text-align: center; padding: 15px; background: #e3f2fd; border-radius: 8px;">
                    <h4 style="color: #1976d2; margin: 0;">${format_number(batch_result.total_urls)}</h4>
                    <p style="margin: 5px 0;">کل محصولات</p>
                </div>
                <div style="text-align: center; padding: 15px; background: #e8f5e8; border-radius: 8px;">
                    <h4 style="color: #2e7d32; margin: 0;">${format_number(batch_result.success_count)}</h4>
                    <p style="margin: 5px 0;">موفق</p>
                </div>
                <div style="text-align: center; padding: 15px; background: #ffebee; border-radius: 8px;">
                    <h4 style="color: #c62828; margin: 0;">${format_number(batch_result.failed_count)}</h4>
                    <p style="margin: 5px 0;">ناموفق</p>
                </div>
            </div>
            
            <h5>📋 جزئیات نتایج:</h5>
            <div style="max-height: 400px; overflow-y: auto; border: 1px solid #ddd; border-radius: 5px;">
                <table class="table table-striped" style="margin: 0;">
                    <thead style="background: #f8f9fa;">
                        <tr>
                            <th>وضعیت</th>
                            <th>عنوان محصول</th>
                            <th>قیمت</th>
                            <th>URL</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${batch_result.results.map(result => `
                            <tr>
                                <td>
                                    ${result.status === 'success' ? 
                                        '<span style="color: #28a745;">✅ موفق</span>' : 
                                        '<span style="color: #dc3545;">❌ ناموفق</span>'
                                    }
                                </td>
                                <td>${result.title || 'نامشخص'}</td>
                                <td>${result.price ? format_number(result.price) + ' تومان' : '-'}</td>
                                <td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis;">
                                    <a href="${result.url}" target="_blank" title="${result.url}">
                                        ${result.url.substring(0, 50)}...
                                    </a>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>
    `;
    
    let batch_dialog = new frappe.ui.Dialog({
        title: __('نتیجه کرال دسته‌ای محصولات'),
        size: 'extra-large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'batch_result_html',
                options: result_html
            }
        ],
        primary_action_label: __('بستن'),
        primary_action() {
            batch_dialog.hide();
        }
    });
    
    batch_dialog.show();
}
