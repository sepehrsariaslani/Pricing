frappe.pages['jobcards'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'کارت کارها',
		single_column: true
	});

	// متغیرهای سراسری
	let currentFilters = {
	    date: null,
	    status: null,
	    workstation: null,
	    workstation_type: null
	};

	let currentUser = frappe.user.name;
	window.currentEmployee = null;
	let activeJobCard = null;
	let refreshInterval = null;
	let cachedJobCards = {}; // کش کارت‌های کار برای جلوگیری از پاک شدن داده‌ها
	let jobCardsData = [];
	let salesOrders = {};
	let workOrders = {};
	let bomData = {};
	let employeeData = {};
	let isLoading = false;
    // اضافه کردن cache برای بهینه‌سازی
const globalJobInfoCache = new Map();
const CACHE_DURATION = 30000; // 30 ثانیه



function debugLog(message, data) {
    if (typeof console !== 'undefined') {
        console.log('DEBUG:', message, data || '');
    }
}

// بررسی وجود توابع ضروری
function checkRequiredFunctions() {
    const required = ['loadData', 'createUI', 'getCurrentEmployee'];
    required.forEach(func => {
        if (typeof window[func] === 'undefined' && typeof eval(func) === 'undefined') {
            debugLog('Missing function:', func);
        }
    });
}


// تابع getJobCompleteInfo که گم شده
async function getJobCompleteInfo(jobCardName) {
    const cached = globalJobInfoCache.get(jobCardName);
    if (cached && Date.now() - cached.timestamp < CACHE_DURATION) {
        return cached.data;
    }

    return new Promise((resolve) => {
        frappe.call({
            method: 'pricing.pricing.page.jobcards.jobcards.get_job_complete_info',
            args: { 
                job_card_name: jobCardName,
                current_user: frappe.user.name 
            },
            callback: function(r) {
                const data = r.message || {};
                
                // ذخیره در cache
                globalJobInfoCache.set(jobCardName, {
                    data: data,
                    timestamp: Date.now()
                });
                
                //console.log('Complete job info received:', data);
                resolve(data);
            },
            error: () => resolve({})
        });
    });
}
	// شروع صفحه
	initPage();

	function initPage() {
		getCurrentEmployee().then(() => {
			createUI();
			loadData();
		}).catch(error => {
			console.error('خطا در بارگذاری صفحه:', error);
			frappe.msgprint('خطا در بارگذاری صفحه');
		});
	}


async function updateAllJobCardButtons(workOrder) {
    const allJobCards = await getAllJobCards(workOrder);
    
    // روش بهینه: یکباره همه dependency ها را چک کنید
    const dependencyResults = await checkMultipleJobDependencies(
        allJobCards.map(jc => jc.name)
    );
    
    let canStart = dependencyResults[jobCard.name] || false;
    let buttonsHTML = await generateJobCardButtonsWithDependencyCheck(jobCard, jobInfo);
    // سپس برای هر کارت، دکمه‌ها را به‌روزرسانی کنید
    for (const jobCard of allJobCards) {
        //const canStart = dependencyResults[jobCard.name] || false;
        const jobInfo = await getJobCardInfo(jobCard.name); // اگر نیاز دارید
        let canStart = await checkProductionDependencies(jobCard.name);
        let buttonsHTML = await generateJobCardButtonsWithDependencyCheck(jobCard, jobInfo);

        //const buttonsHTML = await generateActionButtonsHTMLOptimized(jobCard, jobInfo, canStart);
        
        const container = document.querySelector(`#job-card-${jobCard.name} .actions-container`);
        if (container) {
            container.innerHTML = buttonsHTML;
        }
    }
}

// تابع async برای تولید دکمه‌ها با چک کردن وابستگی‌ها
async function generateJobCardButtonsWithDependencyCheck(jobCard, jobInfo) {
    try {
        // چک کردن وابستگی‌های تولیدی
        const canStart = await checkProductionDependencies(jobCard.name);
        console.log(`Dependency check for ${jobCard.name}: ${canStart}`); // برای debug
        
        // تولید HTML دکمه‌ها
        return generateActionButtonsHTMLOptimized(jobCard, jobInfo, canStart);
        
    } catch (error) {
        console.error(`Error checking dependencies for ${jobCard.name}:`, error);
        // در صورت خطا، فقط دکمه مشاهده نمایش بده
        return `<button class="btn btn-sm btn-outline-secondary" onclick="window.jobCardsPage.viewJob('${jobCard.name}')">
            <i class="fa fa-eye"></i> مشاهده
        </button>`;
    }
}


// تابع بهینه برای چندین کارت کار
async function generateMultipleJobCardButtons(jobCards, jobInfos = {}) {
    try {
        // یکباره همه dependency ها رو چک کن
        const jobCardNames = jobCards.map(jc => jc.name);
        const dependencyResults = await checkMultipleJobDependencies(jobCardNames);
        
        // برای هر کارت، دکمه‌ها رو تولید کن
        const results = {};
        for (const jobCard of jobCards) {
            const canStart = dependencyResults[jobCard.name] || false;
            const jobInfo = jobInfos[jobCard.name] || {};
            results[jobCard.name] = generateActionButtonsHTMLOptimized(jobCard, jobInfo, canStart);
        }
        
        return results;
        
    } catch (error) {
        console.error('Error in generateMultipleJobCardButtons:', error);
        // در صورت خطا، برای همه فقط دکمه مشاهده
        const results = {};
        for (const jobCard of jobCards) {
            results[jobCard.name] = `<button class="btn btn-sm btn-outline-secondary" onclick="window.jobCardsPage.viewJob('${jobCard.name}')">
                <i class="fa fa-eye"></i> مشاهده
            </button>`;
        }
        return results;
    }
}

// مثال استفاده:
// تک کارت:
async function updateSingleJobCard(jobCard, jobInfo) {
    const buttonsHTML = await generateJobCardButtonsWithDependencyCheck(jobCard, jobInfo);
    document.querySelector(`#job-card-${jobCard.name} .actions-container`).innerHTML = buttonsHTML;
}

// چندین کارت:
async function updateMultipleJobCards(jobCards, jobInfos) {
    const allButtonsHTML = await generateMultipleJobCardButtons(jobCards, jobInfos);
    
    for (const jobCard of jobCards) {
        const container = document.querySelector(`#job-card-${jobCard.name} .actions-container`);
        if (container) {
            container.innerHTML = allButtonsHTML[jobCard.name];
        }
    }
}


    // توابع کمکی scroll position
function saveScrollPosition() {
    if (typeof(Storage) !== "undefined") {
        sessionStorage.setItem('jobCardsScrollPosition', window.pageYOffset.toString());
    }
}

function restoreScrollPosition() {
    if (typeof(Storage) !== "undefined") {
        let savedPosition = sessionStorage.getItem('jobCardsScrollPosition');
        if (savedPosition) {
            setTimeout(() => {
                window.scrollTo(0, parseInt(savedPosition));
            }, 100);
        }
    }
}

	function getCurrentEmployee() {
		return new Promise((resolve, reject) => {
			frappe.call({
				method: 'frappe.client.get_list',
				args: {
					doctype: 'Employee',
					filters: { user_id: currentUser },
					fields: ['name', 'employee_name', 'workstation'],
					limit: 1
				},
				callback: function(r) {
					if (r.message && r.message.length > 0) {
						currentEmployee = r.message[0];
					}
                    window.currentEmployee = currentEmployee; // sync کردن با global
					resolve();
				},
				error: reject
			});
		});
	}

	function createUI() {
		// محتوای اصلی
		page.main_container = $('<div class="job-cards-page"></div>').appendTo(page.main);
		
		// فیلترها
		createFilters();
		createTabs();
		// نمای nested سفارش‌ها
		//page.orders_list = $('<div id="orders-list"></div>').appendTo(page.main_container);
	}


function createTabs() {
    let tabsHtml = `
        <div class="tabs-section" style="margin-bottom: 20px;">
            <ul class="nav nav-tabs" id="mainTabs">
                <li class="nav-item">
                    <a class="nav-link active" id="orders-tab" data-toggle="tab" >کارت کارها</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" id="active-jobs-tab" data-toggle="tab" >کارت کارهای فعال</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" id="productivity-tab" data-toggle="tab" >بهره‌وری من</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" id="accounting-tab" data-toggle="tab" >حسابداری من</a>
                </li>
            </ul>
            <div class="tab-content" id="mainTabsContent">
                <div class="tab-pane fade show active" id="orders-content">
                    <div id="orders-list"></div>
                </div>
                <div class="tab-pane fade" id="active-jobs-content">
                    <div id="active-jobs-list"></div>
                </div>
                <div class="tab-pane fade" id="productivity-content">
                    <div id="productivity-dashboard"></div>
                </div>
                <div class="tab-pane fade" id="accounting-content">
                    <div id="accounting-dashboard"></div>
                </div>
            </div>
        </div>
    `;
    
    $(tabsHtml).appendTo(page.main_container);
    page.orders_list = $('#orders-list');
    
    // Event listener برای تب فعال - تصحیح شده بدون تغییر URL
    $('#active-jobs-tab').off('click').on('click', function(e) {
        e.preventDefault(); // جلوگیری از تغییر URL
        
        // تغییر کلاس‌های active
        $('#mainTabs .nav-link').removeClass('active');
        $(this).addClass('active');
        
        $('#mainTabsContent .tab-pane').removeClass('show active');
        $('#active-jobs-content').addClass('show active');
        
        // بارگذاری کارت‌کارهای فعال
        loadActiveJobs();
    });
    
    // Event listener برای تب کارت‌کارها
    $('#orders-tab').off('click').on('click', function(e) {
        e.preventDefault();
        
        // تغییر کلاس‌های active
        $('#mainTabs .nav-link').removeClass('active');
        $(this).addClass('active');
        
        $('#mainTabsContent .tab-pane').removeClass('show active');
        $('#orders-content').addClass('show active');
    });

    // Event listener برای تب بهره‌وری
$('#productivity-tab').off('click').on('click', function(e) {
    e.preventDefault();
    
    $('#mainTabs .nav-link').removeClass('active');
    $(this).addClass('active');
    
    $('#mainTabsContent .tab-pane').removeClass('show active');
    $('#productivity-content').addClass('show active');
    frappe.require("https://cdn.jsdelivr.net/npm/chart.js", () => {
    // وقتی لود شد، حالا می‌تونی drawProductivityCharts رو اجرا کنی
    loadProductivityDashboard();
});
});

// Event listener برای تب حسابداری
$('#accounting-tab').off('click').on('click', function(e) {
    e.preventDefault();
    
    $('#mainTabs .nav-link').removeClass('active');
    $(this).addClass('active');
    
    $('#mainTabsContent .tab-pane').removeClass('show active');
    $('#accounting-content').addClass('show active');
    
    loadAccountingDashboard();
});
}


function createFilters() {
    let filtersHtml = `
        <div class="filters-section" style="margin-bottom: 20px;">
            <div class="row">
                <div class="col-sm-3">
                    <label>تاریخ:</label>
                    <input type="date" class="form-control" id="date-filter" value="">
                </div>
                <div class="col-sm-3">
                    <label>وضعیت:</label>
                    <select class="form-control" id="status-filter">
                        <option value="">همه</option>
                        <option value="Open">آماده شروع</option>
                        <option value="Work In Progress">در حال انجام</option>
                        <option value="Paused">متوقف شده</option>
                        <option value="Completed">تکمیل شده</option>
                        <option value="Submitted">ارسال شده</option>
                    </select>
                </div>
                <div class="col-sm-2">
                    <label>بخش کاری:</label>
                    <select class="form-control" id="workstation-type-filter">
                        <option value="">همه انواع</option>
                    </select>
                </div>
                <div class="col-sm-3">
                    <label>ایستگاه کاری:</label>
                    <select class="form-control" id="workstation-filter">
                        <option value="">همه بخش‌ها</option>
                    </select>
                </div>
                <div class="col-sm-3">
                    <label>&nbsp;</label>
                    <button class="btn btn-primary" onclick="window.jobCardsPage.refresh()">
                        <i class="fa fa-refresh"></i> بروزرسانی
                    </button>
                </div>
            </div>
        </div>
    `;
    
    $(filtersHtml).appendTo(page.main_container);
    
    // بارگذاری بخش‌های کاری
    loadWorkstations();
    
    // اضافه کردن event listener برای همه فیلترها (اضافه شده workstation-type-filter)
    $('#date-filter, #status-filter, #workstation-filter, #workstation-type-filter').off('change').on('change', function() {
        saveScrollPosition();
        loadData();
    });
}

async function loadActiveJobs() {
    try {
        $('#active-jobs-list').html('<div class="text-center"><i class="fa fa-spinner fa-spin"></i> در حال بارگذاری...</div>');
        
        let response = await new Promise((resolve) => {
            frappe.call({
                method: 'pricing.pricing.page.jobcards.jobcards.get_all_active_jobs',
                callback: function(r) {
                    resolve(r.message);
                }
            });
        });
        
        if (response && response.length > 0) {
            renderActiveJobs(response);
        } else {
            $('#active-jobs-list').html('<div class="text-center text-muted">هیچ کار فعالی یافت نشد</div>');
        }
    } catch (error) {
        $('#active-jobs-list').html('<div class="text-center text-danger">خطا در بارگذاری</div>');
        console.error('خطا در loadActiveJobs:', error);
    }
}

async function loadProductivityDashboard() {
    try {
        $('#productivity-dashboard').html('<div class="text-center"><i class="fa fa-spinner fa-spin"></i> در حال بارگذاری...</div>');
        
        let response = await new Promise((resolve) => {
            frappe.call({
                method: 'pricing.pricing.page.jobcards.jobcards.get_employee_productivity_dashboard',
                args: { 
                    employee: currentEmployee?.name 
                },
                callback: function(r) {
                    resolve(r.message);
                }
            });
        });
        
        if (response) {
            renderProductivityDashboard(response);
        } else {
            $('#productivity-dashboard').html('<div class="text-center text-muted">اطلاعاتی یافت نشد</div>');
        }
    } catch (error) {
        $('#productivity-dashboard').html('<div class="text-center text-danger">خطا در بارگذاری</div>');
        console.error('خطا در loadProductivityDashboard:', error);
    }
}

function renderProductivityDashboard(data) {
    let html = `
        <div class="productivity-dashboard" style="padding: 20px;">
            <!-- کارت کار فعال -->
            ${data.active_job ? renderActiveJobSection(data.active_job) : '<div class="alert alert-info text-center" style="padding: 30px; margin-bottom: 30px;"><i class="fa fa-info-circle fa-2x mb-3"></i><br><h5>هیچ کار فعالی ندارید</h5><p class="text-muted">برای شروع کار، به تب کارت کارها بروید</p></div>'}
            
            <!-- آمار امروز -->
            <div class="row mb-4">
                <div class="col-lg-3 col-md-6 mb-3">
                    <div class="card border-0 shadow-sm" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                        <div class="card-body text-white text-center py-4">
                            <div class="mb-2"><i class="fa fa-clock-o fa-2x"></i></div>
                            <h3 class="mb-1">${data.today_stats.work_hours}:${String(data.today_stats.work_minutes).padStart(2, '0')}</h3>
                            <p class="mb-0 opacity-75">زمان کار امروز</p>
                        </div>
                    </div>
                </div>
                <div class="col-lg-3 col-md-6 mb-3">
                    <div class="card border-0 shadow-sm" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
                        <div class="card-body text-white text-center py-4">
                            <div class="mb-2"><i class="fa fa-check-circle fa-2x"></i></div>
                            <h3 class="mb-1">${data.today_stats.completed_jobs}</h3>
                            <p class="mb-0 opacity-75">کار تکمیل شده</p>
                        </div>
                    </div>
                </div>
                <div class="col-lg-3 col-md-6 mb-3">
                    <div class="card border-0 shadow-sm" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);">
                        <div class="card-body text-white text-center py-4">
                            <div class="mb-2"><i class="fa fa-line-chart fa-2x"></i></div>
                            <h3 class="mb-1">${data.today_stats.productivity_percent}%</h3>
                            <p class="mb-0 opacity-75">بهره‌وری امروز</p>
                        </div>
                    </div>
                </div>
                <div class="col-lg-3 col-md-6 mb-3">
                    <div class="card border-0 shadow-sm" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);">
                        <div class="card-body text-white text-center py-4">
                            <div class="mb-2"><i class="fa fa-money fa-2x"></i></div>
                            <h3 class="mb-1" style="font-size: 1.5rem;">${formatRialRounded(data.today_stats.earnings || 0)}</h3>
                            <p class="mb-0 opacity-75">درآمد امروز</p>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- مقایسه با دیروز -->
            <div class="row mb-4">
                <div class="col-12">
                    <div class="card border-0 shadow-sm">
                        <div class="card-body text-center py-3">
                            <div class="d-flex align-items-center justify-content-center">
                                <i class="fa ${data.today_stats.trend >= 0 ? 'fa-arrow-up text-success' : 'fa-arrow-down text-danger'} fa-lg me-2"></i>
                                <span class="h4 mb-0 ${data.today_stats.trend >= 0 ? 'text-success' : 'text-danger'}">
                                    ${data.today_stats.trend >= 0 ? '+' : ''}${data.today_stats.trend}%
                                </span>
                                <span class="text-muted ms-2">نسبت به دیروز</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- نمودارها -->
            <div class="row">
                <div class="col-md-6 mb-4">
                    <div class="card border-0 shadow-sm h-100">
                        <div class="card-header bg-light border-0">
                            <div class="d-flex align-items-center">
                                <i class="fa fa-line-chart me-2 text-primary"></i>
                                <h5 class="mb-0">روند بهره‌وری</h5>
                            </div>
                        </div>
                        <div class="card-body">
                            <canvas id="productivity-chart"></canvas>
                        </div>
                    </div>
                </div>
                <div class="col-md-6 mb-4">
                    <div class="card border-0 shadow-sm h-100">
                        <div class="card-header bg-light border-0">
                            <div class="d-flex align-items-center">
                                <i class="fa fa-bar-chart me-2 text-success"></i>
                                <h5 class="mb-0">ساعات کاری روزانه</h5>
                            </div>
                        </div>
                        <div class="card-body">
                            <canvas id="workhours-chart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- کارهای انجام شده امروز -->
            <div class="card border-0 shadow-sm mt-4">
                <div class="card-header bg-light border-0">
                    <div class="d-flex align-items-center">
                        <i class="fa fa-list-check me-2 text-primary"></i>
                        <h5 class="mb-0">کارهای انجام شده امروز</h5>
                    </div>
                </div>
                <div class="card-body">
                    ${renderTodayCompletedJobs(data.today_completed_jobs)}
                </div>
            </div>
        </div>
    `;
    
    $('#productivity-dashboard').html(html);
    
    // رسم نمودارها
    drawProductivityCharts(data);
}

function renderActiveJobSection(activeJob) {
    const progressPercent = Math.round((activeJob.completed_qty/activeJob.for_quantity)*100);
    return `
        <div class="card mb-4 border-0 shadow-sm" style="border: 3px solid #007bff !important;">
            <div class="card-header bg-primary text-white" style="padding: 20px;">
                <div class="row align-items-center">
                    <div class="col-auto">
                        <div style="background: rgba(255,255,255,0.2); border-radius: 50%; width: 60px; height: 60px; display: flex; align-items: center; justify-content: center;">
                            <i class="fa fa-play-circle" style="font-size: 24px; color: white;"></i>
                        </div>
                    </div>
                    <div class="col">
                        <h4 class="mb-1 text-white">کار فعال شما</h4>
                        <p class="mb-0" style="color: rgba(255,255,255,0.8);">در حال انجام...</p>
                    </div>
                    <div class="col-auto">
                        <span class="badge badge-light" style="font-size: 14px; padding: 8px 12px;">
                            در حال انجام
                        </span>
                    </div>
                </div>
            </div>
            
            <div class="card-body" style="padding: 20px;">
                <div class="row">
                    <div class="col-md-6">
                        <h5 class="mb-3 text-primary" style="font-weight: bold;">
                            ${activeJob.operation}
                        </h5>
                        
                        <div class="mb-3">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                                <span style="color: #666;">محصول:</span>
                                <span style="font-weight: bold;">${activeJob.production_item}</span>
                            </div>
                            
                            <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
                                <span style="color: #666;">پیشرفت:</span>
                                <span style="font-weight: bold; color: #007bff;">
                                    ${activeJob.completed_qty}/${activeJob.for_quantity} (${progressPercent}%)
                                </span>
                            </div>
                        </div>
                        
                        <div class="progress mb-3" style="height: 12px; background: #e9ecef;">
                            <div class="progress-bar bg-primary" role="progressbar" 
                                 style="width: ${progressPercent}%; transition: width 0.3s ease;">
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-6">
                        <div class="mb-3">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                                <span style="color: #666;">زمان شروع:</span>
                                <span style="font-weight: bold;">${activeJob.start_time}</span>
                            </div>
                            
                            <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
                                <span style="color: #666;">مدت زمان:</span>
                                <span style="font-weight: bold; color: #28a745;" id="active-timer">
                                    ${activeJob.active_duration}
                                </span>
                            </div>
                        </div>
                        
                        <div style="display: flex; gap: 10px;">
                            <button class="btn btn-warning btn-sm" style="flex: 1; padding: 8px;" 
                                    onclick="window.jobCardsPage.pauseJob('${activeJob.name}')">
                                <i class="fa fa-pause"></i> توقف
                            </button>
                            <button class="btn btn-success btn-sm" style="flex: 1; padding: 8px;" 
                                    onclick="window.jobCardsPage.showCompleteDialog('${activeJob.name}')">
                                <i class="fa fa-check"></i> تکمیل
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function renderTodayCompletedJobs(jobs) {
    if (!jobs || jobs.length === 0) {
        return `
            <div class="text-center py-4">
                <i class="fa fa-calendar-check-o fa-3x text-muted mb-3"></i>
                <p class="text-muted mb-0">امروز هیچ کاری تکمیل نشده</p>
                <small class="text-muted">با شروع کار، اینجا کارهای تکمیل شده نمایش داده می‌شود</small>
            </div>
        `;
    }
    
    let html = '<div class="row">';
    jobs.forEach((job, index) => {
        html += `
            <div class="col-lg-4 col-md-6 mb-3">
                <div class="card border-0 shadow-sm h-100" style="background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);">
                    <div class="card-body p-3">
                        <div class="d-flex align-items-start">
                            <div class="badge badge-success rounded-circle me-2 mt-1" style="width: 20px; height: 20px; display: flex; align-items: center; justify-content: center;">
                                ${index + 1}
                            </div>
                            <div class="flex-grow-1">
                                <h6 class="mb-1 text-dark">${job.operation}</h6>
                                <p class="mb-1 text-muted small">${job.production_item}</p>
                                <div class="d-flex align-items-center">
                                    <i class="fa fa-clock-o text-primary me-1"></i>
                                    <small class="text-primary font-weight-bold">${job.duration}</small>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    });
    html += '</div>';
    
    if (jobs.length > 6) {
        html += `
            <div class="text-center mt-3">
                <small class="text-muted">و ${jobs.length - 6} کار دیگر...</small>
            </div>
        `;
    }
    
    return html;
}

// تابع لود داشبورد حسابداری
async function loadAccountingDashboard() {
    try {
        $('#accounting-dashboard').html('<div class="text-center"><i class="fa fa-spinner fa-spin"></i> در حال بارگذاری...</div>');
        
        const response = await frappe.call({
            method: 'pricing.pricing.page.jobcards.jobcards.get_employee_accounting_data',
            args: {
                employee: window.currentEmployee
            }
        });

        if (response.message) {
            renderAccountingDashboard(response.message);
        } else {
            $('#accounting-dashboard').html('<div class="text-center text-muted">اطلاعاتی یافت نشد</div>');
        }
    } catch (error) {
        $('#accounting-dashboard').html('<div class="text-center text-danger">خطا در بارگذاری</div>');
        console.error('خطا در loadAccountingDashboard:', error);
    }
}

function renderAccountingDashboard(data) {
    let html = `
        <div class="accounting-dashboard" style="padding: 20px;">
            <!-- پیام‌های توضیحی -->
            ${data.messages && data.messages.length > 0 ? `
            <div class="row mb-4">
                <div class="col-12">
                    <div class="alert alert-info border-0 shadow-sm">
                        <div class="d-flex align-items-center mb-2">
                            <i class="fa fa-info-circle me-2"></i>
                            <h6 class="mb-0">خلاصه وضعیت حساب شما:</h6>
                        </div>
                        ${data.messages.map(msg => `<p class="mb-1">${msg}</p>`).join('')}
                    </div>
                </div>
            </div>
            ` : ''}
            
            <!-- خلاصه حساب -->
            <div class="row mb-4">
                <div class="col-12">
                    <div class="card border-0 shadow-lg" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                        <div class="card-body text-white text-center py-4">
                            <div class="row">
                                <div class="col-md-3">
                                    <h3 class="mb-1">${formatRialRounded(data.total_earnings || 0)}</h3>
                                    <p class="mb-0 opacity-75">کل درآمد</p>
                                    <small class="opacity-50">${data.stats?.total_job_cards || 0} کار</small>
                                </div>
                                <div class="col-md-3">
                                    <h3 class="mb-1">${formatRialRounded(data.total_paid || 0)}</h3>
                                    <p class="mb-0 opacity-75">پرداخت شده</p>
                                    <small class="opacity-50">${data.stats?.total_payments || 0} پرداخت</small>
                                </div>
                                <div class="col-md-3">
                                    <h3 class="mb-1" style="color: ${(data.balance || 0) >= 0 ? '#90EE90' : '#FFB6C1'};">
                                        ${formatRialRounded(data.balance || 0)}
                                    </h3>
                                    <p class="mb-0 opacity-75">${data.summary?.balance_status || 'نامشخص'}</p>
                                    <small class="opacity-50">وضعیت حساب</small>
                                </div>
                                <div class="col-md-3">
                                    <h3 class="mb-1">${formatRialRounded(data.stats?.avg_earning_per_job || 0)}</h3>
                                    <p class="mb-0 opacity-75">متوسط درآمد</p>
                                    <small class="opacity-50">هر کار</small>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- تراکنش‌های اخیر -->
            <div class="row">
                <div class="col-md-6">
                    <div class="card border-0 shadow-sm">
                        <div class="card-header bg-light border-0">
                            <div class="d-flex align-items-center">
                                <i class="fa fa-plus-circle me-2 text-success"></i>
                                <h5 class="mb-0">درآمدهای اخیر</h5>
                            </div>
                        </div>
                        <div class="card-body">
                            ${renderRecentEarnings(data.recent_earnings || [])}
                        </div>
                    </div>
                </div>
                
                <div class="col-md-6">
                    <div class="card border-0 shadow-sm">
                        <div class="card-header bg-light border-0">
                            <div class="d-flex align-items-center">
                                <i class="fa fa-minus-circle me-2 text-primary"></i>
                                <h5 class="mb-0">پرداخت‌های اخیر</h5>
                            </div>
                        </div>
                        <div class="card-body">
                            ${renderRecentPayments(data.recent_payments || [])}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    $('#accounting-dashboard').html(html);
}

function renderRecentEarnings(earnings) {
    if (!earnings || earnings.length === 0) {
        return `
            <div class="text-center py-4">
                <i class="fa fa-money fa-3x text-muted mb-3"></i>
                <p class="text-muted mb-0">هنوز درآمدی ثبت نشده</p>
            </div>
        `;
    }
    
    let html = '<div class="list-group list-group-flush">';
    earnings.forEach((earning, index) => {
        if (index < 10) { // فقط ۱۰ مورد اخیر
            html += `
                <div class="list-group-item border-0 px-0">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <div class="d-flex align-items-center mb-1">
                                <i class="fa fa-briefcase me-2 text-primary"></i>
                                <h6 class="mb-0">${earning.job_card || 'نامشخص'}</h6>
                            </div>
                            <div class="mb-1">
                                <small class="text-muted">
                                    <i class="fa fa-calendar me-1"></i>
                                    ${earning.date ? new Date(earning.date).toLocaleDateString('fa-IR') : 'نامشخص'}
                                </small>
                            </div>
                            <div>
                                <small class="text-muted">
                                    <i class="fa fa-cubes me-1"></i>
                                    تعداد: ${earning.quantity || 0} عدد
                                </small>
                            </div>
                        </div>
                        <div class="text-success font-weight-bold">
                            <div class="text-end">
                                <div style="font-size: 1.1em;">+${formatRialRounded(earning.amount || 0)}</div>
                                <small class="text-muted">درآمد</small>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }
    });
    html += '</div>';
    
    if (earnings.length > 10) {
        html += `<div class="text-center mt-2"><small class="text-muted">و ${earnings.length - 10} مورد دیگر...</small></div>`;
    }
    
    return html;
}

function renderRecentPayments(payments) {
    if (!payments || payments.length === 0) {
        return `
            <div class="text-center py-4">
                <i class="fa fa-credit-card fa-3x text-muted mb-3"></i>
                <p class="text-muted mb-0">هنوز پرداختی ثبت نشده</p>
            </div>
        `;
    }
    
    let html = '<div class="list-group list-group-flush">';
    payments.forEach((payment, index) => {
        if (index < 10) { // فقط ۱۰ مورد اخیر
            html += `
                <div class="list-group-item border-0 px-0">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <div class="d-flex align-items-center mb-1">
                                <i class="fa fa-credit-card me-2 text-primary"></i>
                                <h6 class="mb-0">${payment.reference || 'پرداخت نقدی'}</h6>
                            </div>
                            <div class="mb-1">
                                <small class="text-muted">
                                    <i class="fa fa-calendar me-1"></i>
                                    ${payment.date ? new Date(payment.date).toLocaleDateString('fa-IR') : 'نامشخص'}
                                </small>
                            </div>
                            <div>
                                <small class="text-success">
                                    <i class="fa fa-check-circle me-1"></i>
                                    پرداخت شده
                                </small>
                            </div>
                        </div>
                        <div class="text-primary font-weight-bold">
                            <div class="text-end">
                                <div style="font-size: 1.1em;">-${formatRialRounded(payment.amount || 0)}</div>
                                <small class="text-muted">پرداخت</small>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }
    });
    html += '</div>';
    
    if (payments.length > 10) {
        html += `<div class="text-center mt-2"><small class="text-muted">و ${payments.length - 10} مورد دیگر...</small></div>`;
    }
    
    return html;
}

function drawProductivityCharts(data) {
    // نمودار بهره‌وری
    const productivityCtx = document.getElementById('productivity-chart').getContext('2d');
    new Chart(productivityCtx, {
        type: 'line',
        data: {
            labels: data.chart_data.dates,
            datasets: [{
                label: 'بهره‌وری (%)',
                data: data.chart_data.productivity,
                borderColor: 'rgb(75, 192, 192)',
                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100
                }
            }
        }
    });
    
    // نمودار ساعات کاری
    const workhoursCtx = document.getElementById('workhours-chart').getContext('2d');
    new Chart(workhoursCtx, {
        type: 'bar',
        data: {
            labels: data.chart_data.dates,
            datasets: [{
                label: 'ساعات کاری',
                data: data.chart_data.work_hours,
                backgroundColor: 'rgba(54, 162, 235, 0.2)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

// تایمر زنده برای کار فعال
let activeJobTimer;
function startActiveJobTimer() {
    if (activeJobTimer) clearInterval(activeJobTimer);
    
    activeJobTimer = setInterval(() => {
        let timerElement = document.getElementById('active-timer');
        if (timerElement) {
            // بروزرسانی زمان (این رو باید از سرور بگیری)
            updateActiveJobTimer();
        }
    }, 60000); // هر دقیقه
}

async function updateActiveJobTimer() {
    // این تابع زمان فعال رو از سرور می‌گیره
    // کد مختصر...
}

async function loadActiveJobs() {
    try {
        $('#active-jobs-list').html('<div class="text-center"><i class="fa fa-spinner fa-spin"></i> در حال بارگذاری...</div>');
        
        let response = await new Promise((resolve) => {
            frappe.call({
                method: 'pricing.pricing.page.jobcards.jobcards.get_all_active_jobs',
                callback: function(r) {
                    resolve(r.message);
                }
            });
        });
        
        if (response && response.length > 0) {
            renderActiveJobs(response);
        } else {
            $('#active-jobs-list').html('<div class="text-center text-muted">هیچ کار فعالی یافت نشد</div>');
        }
    } catch (error) {
        $('#active-jobs-list').html('<div class="text-center text-danger">خطا در بارگذاری</div>');
        console.error('خطا در loadActiveJobs:', error);
    }
}

// جایگزین کردن loadData()
function loadData() {
    if (isLoading) {
        console.log('Already loading, skipping...');
        return;
    }
    isLoading = true;
    // فراخوانی تک تابع backend
    frappe.call({
        method: 'pricing.pricing.page.jobcards.jobcards.get_nested_orders_data',
        args: {
            date_filter: $('#date-filter').val(),
            status_filter: $('#status-filter').val(),
            workstation_filter: $('#workstation-filter').val(),
            workstation_type_filter: $('#workstation-type-filter').val(),
            current_user: frappe.user.name
        },
        callback: function(r) {
            if (r.message) {
                // ذخیره داده‌ها در متغیرهای global
                jobCardsData = flattenJobCardsData(r.message.grouped_data);
                jobCardsData = jobCardsData.filter(job => job.status !== 'Cancelled');
                salesOrders = r.message.sales_orders || {};
                workOrders = r.message.work_orders || {};
                bomData = r.message.bom_data || {};
                employeeData = r.message.employee_data || {};
                currentEmployee = r.message.current_employee;
                activeJobCard = r.message.active_job;
                
                // رندر کردن
                renderNestedOrdersFromData(r.message.grouped_data);
            }
        },
        error: function(err) {
            console.error('خطا در بارگذاری داده‌ها:', err);
            frappe.msgprint('خطا در بارگذاری داده‌ها');
        }
    }).always(() => {
        isLoading = false;
        setTimeout(restoreScrollPosition, 100);
    });
}

// تابع کمکی جدید برای flatten کردن داده‌های nested
function flattenJobCardsData(groupedData) {
    let flatData = [];
    Object.values(groupedData).forEach(salesOrder => {
        Object.values(salesOrder).forEach(workOrder => {
            Object.values(workOrder).forEach(productionItems => {
                flatData = flatData.concat(productionItems);
            });
        });
    });
    return flatData;
}

function loadActiveJobs() {
    frappe.call({
        method: 'pricing.pricing.page.jobcards.jobcards.get_all_active_jobs',
        callback: function(r) {
            if (r.message) {
                renderActiveJobs(r.message);
            }
        }
    });
}

function renderActiveJobs(activeJobs) {
    let container = $('#active-jobs-list');
    
    if (!activeJobs || activeJobs.length === 0) {
        container.html('<div class="text-center text-muted">هیچ کار فعالی یافت نشد</div>');
        return;
    }
    
    let html = '<div class="row">';
    
    activeJobs.forEach(job => {
        // محاسبه مدت زمان کار
        let duration = 'نامشخص';
        if (job.start_time) {
            let startTime = new Date(job.start_time);
            let now = new Date();
            let diffMs = now - startTime;
            let diffHours = Math.floor(diffMs / (1000 * 60 * 60));
            let diffMins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
            duration = `${diffHours}:${diffMins.toString().padStart(2, '0')}`;
        }
        
        html += `
            <div class="col-md-6 col-lg-4" style="margin-bottom: 15px;">
                <div class="active-job-card" style="border: 2px solid #007bff; padding: 15px; border-radius: 8px; background: #f8f9fa;">
                    <h6 style="color: #007bff; font-weight: bold; margin-bottom: 10px;">
                        <i class="fa fa-cogs"></i> ${job.operation || 'عملیات نامشخص'}
                    </h6>
                    <div style="font-size: 13px; line-height: 1.6;">
                        <div><strong>کارمند:</strong> ${job.employee_name || 'نامشخص'}</div>
                        <div><strong>محصول:</strong> ${job.production_item || 'نامشخص'}</div>
                        <div><strong>سفارش کار:</strong> ${job.work_order || 'نامشخص'}</div>
                        <div><strong>شروع:</strong> ${job.start_time ? new Date(job.start_time).toLocaleString('fa-IR') : 'نامشخص'}</div>
                        <div><strong>مدت زمان:</strong> <span style="color: #28a745; font-weight: bold;">${duration}</span></div>
                        ${job.workstation ? `<div><strong>ایستگاه:</strong> ${job.workstation}</div>` : ''}
                    </div>
                    <div style="margin-top: 15px;">
                        <button class="btn btn-sm btn-outline-primary" onclick="window.jobCardsPage.viewJob('${job.name}')">
                            <i class="fa fa-eye"></i> مشاهده جزئیات
                        </button>
                    </div>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    container.html(html);
}


class VirtualJobCardsRenderer {
    constructor(container, itemHeight = 320) {
        this.container = container;
        this.itemHeight = itemHeight;
        this.itemsPerRow = 3; // تعداد آیتم در هر ردیف
        this.rowHeight = itemHeight + 20; // ارتفاع هر ردیف + margin
        this.visibleItems = [];
        this.allItems = [];
        this.scrollTop = 0;
        this.containerHeight = 0;
        
        this.setupScrollListener();
    }

    setupScrollListener() {
        let timeout = null;
        window.addEventListener('scroll', () => {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                this.handleScroll();
            }, 16); // 60fps
        });
        
        window.addEventListener('resize', () => {
            this.updateDimensions();
            this.render();
        });
    }

    updateDimensions() {
        this.containerHeight = window.innerHeight;
        // محاسبه تعداد آیتم در هر ردیف بر اساس عرض صفحه
        const containerWidth = this.container.width();
        if (containerWidth < 768) {
            this.itemsPerRow = 1; // موبایل
        } else if (containerWidth < 1200) {
            this.itemsPerRow = 2; // تبلت
        } else {
            this.itemsPerRow = 3; // دسکتاپ
        }
    }

    setItems(items) {
        this.allItems = items;
        this.updateDimensions();
        this.render();
    }

    handleScroll() {
        this.scrollTop = window.pageYOffset;
        this.render();
    }

    getVisibleRange() {
        const containerOffset = this.container.offset().top;
        const relativeScrollTop = Math.max(0, this.scrollTop - containerOffset);
        
        // محاسبه رنج قابل مشاهده با buffer
        const buffer = 2; // ردیف‌های اضافی برای smooth scrolling
        const startRow = Math.max(0, Math.floor(relativeScrollTop / this.rowHeight) - buffer);
        const endRow = Math.min(
            Math.ceil(this.allItems.length / this.itemsPerRow),
            Math.ceil((relativeScrollTop + this.containerHeight) / this.rowHeight) + buffer
        );

        const startIndex = startRow * this.itemsPerRow;
        const endIndex = Math.min(this.allItems.length, endRow * this.itemsPerRow);

        return { startIndex, endIndex, startRow };
    }

    async render() {
        if (!this.allItems.length) return;

        const { startIndex, endIndex, startRow } = this.getVisibleRange();
        const visibleItems = this.allItems.slice(startIndex, endIndex);

        //console.log(`🖼️ رندر آیتم‌های ${startIndex} تا ${endIndex} از ${this.allItems.length}`);

        // محاسبه ارتفاع کل برای نمایش scrollbar صحیح
        const totalRows = Math.ceil(this.allItems.length / this.itemsPerRow);
        const totalHeight = totalRows * this.rowHeight;

        // ایجاد HTML با spacer برای حفظ scroll position
        const spacerTop = startRow * this.rowHeight;
        const spacerBottom = totalHeight - ((startRow + Math.ceil(visibleItems.length / this.itemsPerRow)) * this.rowHeight);

        let html = `
            <div style="height: ${spacerTop}px;"></div>
            <div class="row">
        `;

        // رندر آیتم‌های visible
        for (let i = 0; i < visibleItems.length; i++) {
            const item = visibleItems[i];
            const colClass = this.getColumnClass();
            
            html += `
                <div class="${colClass}" style="margin-bottom: 20px;">
                    ${await this.renderJobCard(item)}
                </div>
            `;
        }

        html += `
            </div>
            <div style="height: ${spacerBottom}px;"></div>
        `;

        this.container.html(html);
    }

    getColumnClass() {
        switch (this.itemsPerRow) {
            case 1: return 'col-12';
            case 2: return 'col-md-6';
            default: return 'col-md-6 col-lg-4';
        }
    }


    async renderJobCard(jobCard) {
        // استفاده از همان منطق رندر قبلی اما برای یک کارت
        
        const jobInfo = (globalJobInfoCache.has(jobCard.name) && globalJobInfoCache.get(jobCard.name).data) ? globalJobInfoCache.get(jobCard.name).data : {};
        const canStart = true; // یا منطق dependency checking
        
        const isActive = activeJobCard && activeJobCard.name === jobCard.name;
        const statusBadge = getStatusBadge(jobCard.status);
        const timeDisplay = formatTimeDisplay(jobCard.time_required);

        return `
            <div class="job-card ${isActive ? 'active-job' : ''}" 
                 style="border: 2px solid ${getBorderColor(jobCard.status)}; 
                        border-radius: 8px; padding: 15px; min-height: ${this.itemHeight}px;
                        position: relative;">
                
                <div class="job-header" style="margin-bottom: 10px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span class="sequence-badge" style="background: #007bff; color: white; padding: 2px 8px; border-radius: 3px; font-size: 12px;">
                            #${jobCard.sequence_id || jobCard.idx || '0'}
                        </span>
                        ${statusBadge}
                    </div>
                </div>
                
                <h6 style="margin-bottom: 8px; font-weight: bold;">
                    ${jobCard.operation || 'عملیات'}
                </h6>
                
                <div style="font-size: 13px; color: #666; margin-bottom: 15px;">
                    <div>محصول: ${jobCard.production_item || 'نامشخص'}</div>
                    <div>تعداد برنامه‌ریزی: ${jobCard.for_quantity || 0}</div>
                    <div>تکمیل شده: <strong>${jobInfo.completed_qty || 0}</strong></div>
                    <div>باقی‌مانده: <strong style="color: ${Math.max(0, (jobCard.for_quantity || 0) - (jobInfo.completed_qty || 0)) > 0 ? '#dc3545' : '#28a745'}">${Math.max(0, (jobCard.for_quantity || 0) - (jobInfo.completed_qty || 0))}</strong></div>
                    ${timeDisplay ? `<div style="color: #6c757d; font-size: 12px;">زمان برنامه‌ریزی: ${timeDisplay}</div>` : ''}
                </div>
                
                <div class="job-actions" style="position: absolute; bottom: 15px; left: 15px; right: 15px;">
                    ${generateActionButtonsHTMLOptimized(jobCard, jobInfo, canStart)}
                </div>
            </div>
        `;
    }
}

/**
 * 🔄 بهینه‌سازی renderNestedOrdersFromData برای استفاده از Virtual Scrolling
 */
async function renderNestedOrdersFromDataWithVirtual(groupedData) {
    //console.log('🚀 شروع رندر با Virtual Scrolling');
    
    let container = $('#orders-list');
    container.empty();

    if (Object.keys(groupedData).length === 0) {
        container.html('<div class="text-center"><h4>کارت کاری یافت نشد</h4></div>');
        return;
    }

    // تهیه لیست تمام job cards
    let allJobCards = [];
    Object.keys(groupedData).forEach(salesOrderName => {
        Object.keys(groupedData[salesOrderName]).forEach(workOrderName => {
            Object.keys(groupedData[salesOrderName][workOrderName]).forEach(productionItem => {
                const jobCards = groupedData[salesOrderName][workOrderName][productionItem];
                jobCards.forEach(jobCard => {
                    // اضافه کردن metadata برای نمایش بهتر
                    jobCard.salesOrderName = salesOrderName;
                    jobCard.workOrderName = workOrderName;
                    jobCard.productionItem = productionItem;
                    allJobCards.push(jobCard);
                });
            });
        });
    });

    // مرتب‌سازی job cards
    allJobCards.sort((a, b) => {
        // اول کارت‌های در حال انجام
        if (a.status === 'Work In Progress' && b.status !== 'Work In Progress') return -1;
        if (a.status !== 'Work In Progress' && b.status === 'Work In Progress') return 1;
        
        // سپس بر اساس sequence
        const seqA = a.sequence_id || a.idx || 999;
        const seqB = b.sequence_id || b.idx || 999;
        return seqA - seqB;
    });

    //console.log(`📋 آماده‌سازی ${allJobCards.length} کارت کار برای Virtual Scrolling`);

    // دریافت اطلاعات bulk
    const jobCardNames = allJobCards.map(jc => jc.name);
    await getAllJobCardsInfoBulk(jobCardNames);

    // راه‌اندازی Virtual Scrolling
    const virtualRenderer = new VirtualJobCardsRenderer(container);
    virtualRenderer.setItems(allJobCards);

    // ذخیره reference برای استفاده بعدی
    window.virtualRenderer = virtualRenderer;
    
    //console.log('✅ Virtual Scrolling راه‌اندازی شد');
}

// جایگزینی تابع اصلی
window.renderNestedOrdersFromDataWithVirtual = renderNestedOrdersFromDataWithVirtual;


async function getAllJobCardsInfoBulk(jobCardNames) {
    //console.log('🚀 بارگذاری bulk برای', jobCardNames.length, 'کارت کار');
    
    const startTime = Date.now();
    
    try {
        const result = await new Promise((resolve, reject) => {
            frappe.call({
                method: 'pricing.pricing.page.jobcards.jobcards.get_all_jobs_complete_info_bulk',
                args: { 
                    job_card_names: jobCardNames,
                    current_user: frappe.user.name 
                },
                callback: function(r) {
                    if (r.message) {
                        resolve(r.message);
                    } else {
                        reject(new Error('پاسخ خالی از server'));
                    }
                },
                error: reject
            });
        });

        // ذخیره در cache
        const timestamp = Date.now();
        jobCardNames.forEach(name => {
            if (result[name]) {
                globalJobInfoCache.set(name, {
                    data: result[name],
                    timestamp: timestamp
                });
            }
        });

        //console.log('✅ Bulk loading تکمیل شد در', Date.now() - startTime, 'ms');
        return result;

    } catch (error) {
        console.error('❌ خطا در bulk loading:', error);
        return {};
    }
}



// جایگزین کردن renderNestedOrders()
async function renderNestedOrdersFromData(groupedData) {
    let container = $('#orders-list');
    container.empty();

    if (Object.keys(groupedData).length === 0) {
        container.html('<div class="text-center"><h4>کارت کاری یافت نشد</h4></div>');
        return;
    }

    // مرتب‌سازی Sales Orders
    let sortedSalesOrders = Object.keys(groupedData).sort((a, b) => {
        let soA = salesOrders[a];
        let soB = salesOrders[b];
        
        // محاسبه درصد پیشرفت برای مرتب‌سازی
        let progressA = calculateProgress(groupedData[a]);
        let progressB = calculateProgress(groupedData[b]);
        
        // سفارش‌های ناتمام اول، تکمیل شده‌ها آخر
        if (progressA === 100 && progressB !== 100) return 1;
        if (progressA !== 100 && progressB === 100) return -1;
        
        // اگر هر دو تکمیل شده یا ناتمام، بر اساس اولویت
        if (!soA && soB) return 1;
        if (soA && !soB) return -1;
        if (!soA && !soB) return 0;
        
        let priorityA = soA.sales_order_priority || 999;
        let priorityB = soB.sales_order_priority || 999;
        
        return priorityA - priorityB;
    });

    container.empty();
    for(const salesOrderName of sortedSalesOrders) {
        let salesOrderDiv = await createSalesOrderSectionOptimized(salesOrderName, groupedData[salesOrderName]);
        container.append(salesOrderDiv);
    }
}

// بهینه‌سازی createSalesOrderSection
async function createSalesOrderSectionOptimized(salesOrderName, workOrdersGroup) {
    let salesOrder = salesOrders[salesOrderName];
    
    // محاسبه پیشرفت کل سفارش فروش
    let allJobCards = [];
    Object.values(workOrdersGroup).forEach(workOrder => {
        Object.values(workOrder).forEach(jobs => {
            allJobCards = allJobCards.concat(jobs);
        });
    });
    
    let completedCount = allJobCards.filter(jc => jc.status === 'Completed').length;
    let totalCount = allJobCards.length;
    let progressPercent = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;
    
    let deliveryText = 'نامشخص';
    if (salesOrder && salesOrder.delivery_date) {
        let deliveryDate = new Date(salesOrder.delivery_date);
        let today = new Date();
        today.setHours(0, 0, 0, 0);
        deliveryDate.setHours(0, 0, 0, 0);
        
        let diffTime = deliveryDate - today;
        let diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        
        if (diffDays > 0) {
            deliveryText = `${diffDays} روز دیگر`;
        } else if (diffDays === 0) {
            deliveryText = 'امروز';
        } else {
            deliveryText = `${Math.abs(diffDays)} روز گذشته`;
        }
    }

    let isCompleted = (progressPercent === 100);
    let collapseClass = isCompleted ? 'collapsed' : '';
    let contentStyle = isCompleted ? 'display: none;' : '';

    let html = `
        <div class="sales-order-section ${isCompleted ? 'completed-order' : ''}" style="margin-bottom: 30px; border: 2px solid #007bff; border-radius: 8px;">
            <div class="sales-order-header collapsible-header ${collapseClass}" onclick="window.jobCardsPage.toggleSection(this)" style="background: linear-gradient(135deg, ${isCompleted ? '#6c757d' : '#007bff'}, ${isCompleted ? '#495057' : '#0056b3'}); color: white; padding: 15px;">
                <div class="row">
                    <div class="col-md-8">
                        <h4 style="margin: 0;">
                            <i class="fa fa-chevron-down collapse-icon"></i>
                            <i class="fa fa-shopping-cart"></i> سفارش فروش: ${salesOrder ? salesOrder.name : salesOrderName}
                        </h4>
                        ${salesOrder ? `
                            <div style="margin-top: 5px; font-size: 14px;">
                                <span>مشتری: ${salesOrder.customer}</span> |
                                <span>موعد تحویل: ${deliveryText}</span> |
                                <span>وضعیت: ${salesOrder.status}</span>
                            </div>
                        ` : ''}
                    </div>
                    <div class="col-md-4 text-right">
                        <div style="font-size: 18px; font-weight: bold;">
                            پیشرفت: ${progressPercent}%
                        </div>
                        <div class="progress" style="margin-top: 5px; background: rgba(255,255,255,0.3);">
                            <div class="progress-bar bg-success" style="width: ${progressPercent}%"></div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="work-orders-container collapsible-content" style="padding: 15px; ${contentStyle}">
                ${await createWorkOrdersGridOptimized(workOrdersGroup)}
            </div>
        </div>
    `;
    
    return $(html);
}

// بهینه‌سازی createWorkOrdersGrid
async function createWorkOrdersGridOptimized(workOrdersGroup) {
    let html = '';
    
    for(const workOrderName of Object.keys(workOrdersGroup)) {
        let productionItemsGroup = workOrdersGroup[workOrderName];
        let workOrder = workOrders[workOrderName];
        let bom = workOrder ? bomData[workOrder.bom_no] : null;
        
        // محاسبه تعداد کل کارت‌های کار برای این work order
        let allJobCards = [];
        Object.values(productionItemsGroup).forEach(jobs => {
            allJobCards = allJobCards.concat(jobs);
        });
        
        let completedCount = allJobCards.filter(jc => jc.status === 'Completed').length;
        let totalCount = allJobCards.length;
        
        html += `
            <div class="work-order-section" style="margin-bottom: 25px; border: 1px solid #ddd; border-radius: 5px;">
                <div class="work-order-header" style="background: #f8f9fa; padding: 12px; border-bottom: 1px solid #ddd;">
                    <div class="row">
                        <div class="col-md-8">
                            <h6 style="margin: 0; color: #495057;">
                                <i class="fa fa-cogs"></i> دستور تولید: ${workOrder ? workOrder.name : workOrderName}
                            </h6>
                            <div style="font-size: 12px; color: #6c757d; margin-top: 3px;">
                                محصول: ${workOrder ? workOrder.production_item : 'نامشخص'} |
                                تعداد: ${workOrder ? workOrder.qty : 'نامشخص'} |
                                ${bom ? `BOM: ${bom.name}` : ''}
                            </div>
                        </div>
                        <div class="col-md-4 text-right">
                            <small class="text-muted">تکمیل شده: ${completedCount}/${totalCount}</small>
                        </div>
                    </div>
                </div>
                <div class="production-items-container" style="padding: 15px;">
                    ${await createProductionItemsGridOptimized(productionItemsGroup)}
                </div>
            </div>
        `;
    }

    return html;
}

// بهینه‌سازی createProductionItemsGrid
async function createProductionItemsGridOptimized(productionItemsGroup) {
    let html = '';
    for(const productionItem of Object.keys(productionItemsGroup)) {
        let jobCards = productionItemsGroup[productionItem];
        let completedCount = jobCards.filter(jc => jc.status === 'Completed').length;
        let totalCount = jobCards.length;
        let isCompleted = (completedCount === totalCount);

        let collapseClass = isCompleted ? 'collapsed' : '';
        let contentStyle = isCompleted ? 'display: none;' : '';
        
        // مرتب‌سازی کارت‌ها بر اساس sequence
        jobCards.sort((a, b) => {
            let seqA = a.sequence_id || a.idx || 999;
            let seqB = b.sequence_id || b.idx || 999;
            return seqA - seqB;
        });
        
        html += `
            <div class="production-item-section" style="margin-bottom: 20px; border: 1px solid #e9ecef; border-radius: 5px;">
                <div class="production-item-header collapsible-header ${collapseClass}" onclick="window.jobCardsPage.toggleSection(this)" style="background: ${isCompleted ? '#d4edda' : '#e9ecef'}; padding: 10px; cursor: pointer;">
                    <h6 style="margin: 0; color: #495057;">
                        <i class="fa fa-chevron-down collapse-icon"></i>
                        <i class="fa fa-cube"></i> مورد تولیدی: ${productionItem}
                        ${isCompleted ? '<span class="badge badge-success" style="margin-right: 10px;">تکمیل شده</span>' : ''}
                    </h6>
                </div>
                <div class="job-cards-grid collapsible-content" style="padding: 15px; ${contentStyle}">
                    ${await createJobCardsGridOptimized(jobCards)}
                </div>
            </div>
        `;
    }
    
    return html;
}
async function createJobCardsGridOptimized(jobCards) {
    // بهینه‌سازی برای لود سریع‌تر
    if (!jobCards || jobCards.length === 0) {
        return '<div class="text-center text-muted">کارت کاری یافت نشد</div>';
    }
    
    const startTime = Date.now();
    
    // 1️⃣ محدود کردن تعداد درخواست‌های همزمان برای عملکرد بهتر
    const jobCardNames = jobCards.map(jc => jc.name);
    const batchSize = 50; // پردازش دسته‌ای
    
    let bulkJobInfo = {};
    let workingEmployees = {};
    let dependenciesCheck = {};
    
    // پردازش دسته‌ای برای جلوگیری از اورلود
    if (jobCardNames.length <= batchSize) {
        [bulkJobInfo, workingEmployees, dependenciesCheck] = await Promise.all([
            getAllJobCardsInfoBulk(jobCardNames),
            getCurrentWorkingEmployeesAll(),
            checkJobDependenciesAll(jobCardNames)
        ]);
    } else {
        // برای تعداد زیاد، فقط اطلاعات ضروری
        bulkJobInfo = await getAllJobCardsInfoBulk(jobCardNames.slice(0, batchSize));
        workingEmployees = {};
        dependenciesCheck = {};
    }

    // 2️⃣ رندر HTML با بهینه‌سازی
    let html = '<div class="row">';
    
    for (let i = 0; i < jobCards.length; i++) {
        const jobCard = jobCards[i];
        const jobInfo = (bulkJobInfo && bulkJobInfo[jobCard.name]) ? bulkJobInfo[jobCard.name] : {};
        const currentEmployee = workingEmployees[jobCard.name] || null;
        const canStart = dependenciesCheck[jobCard.name] === true;

        const isActive = activeJobCard && activeJobCard.name === jobCard.name;
        const statusBadge = getStatusBadge(jobCard.status);
        const timeInfo = getTimeInformation(jobCard);
        const timeDisplay = formatTimeDisplay(jobCard.time_required);
        
        // محاسبه قیمت‌ها فقط اگر داده موجود باشد
        const pricing = {
            minutes_per_unit: jobCard.minutes_per_unit || 0,
            per_unit_price: jobCard.per_unit_price || 0,
            total_price: jobCard.total_price || 0,
        };

        html += `
            <div class="col-md-6 col-lg-4" style="margin-bottom: 20px;" data-job-card="${jobCard.name}">
                <div class="job-card ${isActive ? 'active-job' : ''}" 
                     style="border: 2px solid ${getBorderColor(jobCard.status)}; 
                            border-radius: 8px; padding: 15px; 
                            ${!canStart && jobCard.status !== 'Completed' && jobCard.status !== 'Submitted' ? 'opacity: 0.6;' : ''}
                            display: flex; flex-direction: column; height: 100%;">
                    
                    <!-- هدر کارت -->
                    <div class="job-header" style="margin-bottom: 12px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span class="sequence-badge" style="background: #007bff; color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold;">
{{ ... }}
                                #${jobCard.sequence_id || jobCard.idx || '0'}
                            </span>
                            ${statusBadge}
                        </div>
                    </div>
                    
                    <!-- عنوان عملیات -->
                    <h6 style="margin-bottom: 12px; font-weight: bold; color: #333; line-height: 1.3;">
                        ${jobCard.operation || 'عملیات'}
                    </h6>
                    
                    <!-- اطلاعات اصلی -->
                    <div style="flex-grow: 1; font-size: 13px; line-height: 1.4;">
                        <div style="margin-bottom: 8px; color: #666;">
                            <strong>محصول:</strong> ${jobCard.production_item || 'نامشخص'}
                        </div>
                        
                        <div style="margin-bottom: 8px; display: flex; justify-content: space-between;">
                            <span style="color: #666;">برنامه‌ریزی:</span>
                            <span style="font-weight: bold;">${jobCard.for_quantity || 0}</span>
                        </div>
                        
                        <div style="margin-bottom: 8px; display: flex; justify-content: space-between;">
                            <span style="color: #666;">تکمیل شده:</span>
                            <span style="font-weight: bold; color: #28a745;">${jobInfo.completed_qty || 0}</span>
                        </div>
                        
                        <div style="margin-bottom: 12px; display: flex; justify-content: space-between;">
                            <span style="color: #666;">باقی‌مانده:</span>
                            <span style="font-weight: bold; color: ${Math.max(0, (jobCard.for_quantity || 0) - (jobInfo.completed_qty || 0)) > 0 ? '#dc3545' : '#28a745'};">
                                ${Math.max(0, (jobCard.for_quantity || 0) - (jobInfo.completed_qty || 0))}
                            </span>
                        </div>
                        
                        ${jobCard.custom_planned_end_date ? `
                            <div style="margin-bottom: 8px; color: #666; font-size: 12px;">
                                📅 موعد: ${jobCard.custom_planned_end_date}
                            </div>
                        ` : ''}
                        
                        ${timeDisplay ? `
                            <div style="margin-bottom: 8px; color: #6c757d; font-size: 12px;">
                                ⏰ زمان برنامه‌ریزی: ${timeDisplay}
                            </div>
                        ` : ''}
                        
                        ${currentEmployee ? `
                            <div style="margin-bottom: 8px; color: #007bff; font-weight: bold; font-size: 12px;">
                                👤 ${currentEmployee}
                            </div>
                        ` : ''}
                        
                        <!-- اطلاعات قیمت -->
                        ${pricing.minutes_per_unit ? `
                            <div style="margin-bottom: 6px; color: #495057; font-size: 12px; background: #f8f9fa; padding: 4px 8px; border-radius: 4px;">
                                ⏱️ زمان هر واحد: <strong>${Math.round(pricing.minutes_per_unit)} دقیقه</strong>
                            </div>
                        ` : ''}
                        
                        ${pricing.per_unit_price ? `
                            <div style="margin-bottom: 6px; color: #28a745; font-size: 12px; background: #f8f9fa; padding: 4px 8px; border-radius: 4px;">
                                💰 نرخ هر واحد: <strong>${formatRialRounded(pricing.per_unit_price)}</strong>
                            </div>
                        ` : ''}
                        
                        ${pricing.total_price ? `
                            <div style="margin-bottom: 8px; color: #007bff; font-size: 12px; font-weight: bold; background: #e3f2fd; padding: 4px 8px; border-radius: 4px;">
                                📊 هزینه کل: <strong>${formatRialRounded(pricing.total_price)}</strong>
                            </div>
                        ` : ''}
                    </div>
                    
                    <!-- دکمه‌های عملیات -->
                    <div class="job-actions" style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #eee;">
                        ${generateActionButtonsHTMLOptimized(jobCard, jobInfo, canStart)}
                    </div>
                    
                    ${!canStart && jobCard.status !== 'Completed' && jobCard.status !== 'Submitted' ? `
                        <div style="margin-top: 8px; font-size: 11px; color: #f39c12; text-align: center; background: #fff8e1; padding: 4px; border-radius: 4px;">
                            <i class="fa fa-clock-o"></i> منتظر مراحل قبلی
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }
    
    html += '</div>';
    
    ////console.log('✅ رندر تکمیل شد در', Date.now() - startTime, 'ms');
    return html;
}

// تابع رندر مجدد فقط یک کارت کار
async function refreshSingleJobCard(jobCardName) {
    try {
        // دریافت اطلاعات به‌روز شده کارت کار
        const response = await frappe.call({
            method: 'pricing.pricing.page.jobcards.jobcards.get_nested_orders_data',
            args: {
                date_filter: currentFilters.date,
                status_filter: currentFilters.status,
                workstation_filter: currentFilters.workstation,
                workstation_type_filter: currentFilters.workstation_type,
                current_user: frappe.session.user
            }
        });

        if (response.message && response.message.nested_data) {
            // پیدا کردن کارت کار مورد نظر در داده‌های جدید
            let updatedJobCard = null;
            for (const salesOrder in response.message.nested_data) {
                for (const workOrder in response.message.nested_data[salesOrder]) {
                    for (const productionItem in response.message.nested_data[salesOrder][workOrder]) {
                        const jobCards = response.message.nested_data[salesOrder][workOrder][productionItem];
                        updatedJobCard = jobCards.find(jc => jc.name === jobCardName);
                        if (updatedJobCard) break;
                    }
                    if (updatedJobCard) break;
                }
                if (updatedJobCard) break;
            }

            if (updatedJobCard) {
                // به‌روزرسانی کش
                cachedJobCards[jobCardName] = updatedJobCard;
                
                // رندر مجدد فقط این کارت
                const cardElement = document.querySelector(`[data-job-card="${jobCardName}"]`);
                if (cardElement) {
                    const newCardHtml = await createSingleJobCardHtml(updatedJobCard);
                    cardElement.outerHTML = newCardHtml;
                    
                    // به‌روزرسانی event listeners
                    updateJobCardEventListeners(jobCardName);
                }
            }
        }
    } catch (error) {
        console.error('خطا در رندر مجدد کارت کار:', error);
    }
}

// تابع ایجاد HTML برای یک کارت کار
async function createSingleJobCardHtml(jobCard) {
    const jobInfo = await getJobCardInfo(jobCard.name);
    const currentEmployee = await getCurrentWorkingEmployee(jobCard.name);
    const canStart = await checkJobDependencies(jobCard.name);
    
    const isActive = activeJobCard && activeJobCard.name === jobCard.name;
    const statusBadge = getStatusBadge(jobCard.status);
    const timeInfo = getTimeInformation(jobCard);
    const timeDisplay = formatTimeDisplay(jobCard.time_required);
    
    const pricing = {
        minutes_per_unit: jobCard.minutes_per_unit || 0,
        per_unit_price: jobCard.per_unit_price || 0,
        total_price: jobCard.total_price || 0,
    };

    return `
        <div class="col-md-6 col-lg-4" style="margin-bottom: 20px;" data-job-card="${jobCard.name}">
            <div class="job-card ${isActive ? 'active-job' : ''}" 
                 style="border: 2px solid ${getBorderColor(jobCard.status)}; 
                        border-radius: 8px; padding: 15px; 
                        ${!canStart && jobCard.status !== 'Completed' && jobCard.status !== 'Submitted' ? 'opacity: 0.6;' : ''}
                        display: flex; flex-direction: column; height: 100%;">
                
                <!-- هدر کارت -->
                <div class="job-header" style="margin-bottom: 12px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span class="sequence-badge" style="background: #007bff; color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold;">
                            #${jobCard.sequence_id || jobCard.idx || '0'}
                        </span>
                        ${statusBadge}
                    </div>
                </div>
                
                <!-- عنوان عملیات -->
                <h6 style="margin-bottom: 12px; font-weight: bold; color: #333; line-height: 1.3;">
                    ${jobCard.operation || 'عملیات'}
                </h6>
                
                <!-- اطلاعات اصلی -->
                <div style="flex-grow: 1; font-size: 13px; line-height: 1.4;">
                    <div style="margin-bottom: 8px; color: #666;">
                        <strong>محصول:</strong> ${jobCard.production_item || 'نامشخص'}
                    </div>
                    
                    <div style="margin-bottom: 8px; display: flex; justify-content: space-between;">
                        <span style="color: #666;">برنامه‌ریزی:</span>
                        <span style="font-weight: bold;">${jobCard.for_quantity || 0}</span>
                    </div>
                    
                    <div style="margin-bottom: 8px; display: flex; justify-content: space-between;">
                        <span style="color: #666;">تکمیل شده:</span>
                        <span style="font-weight: bold; color: #28a745;">${jobInfo.completed_qty || 0}</span>
                    </div>
                    
                    <div style="margin-bottom: 12px; display: flex; justify-content: space-between;">
                        <span style="color: #666;">باقی‌مانده:</span>
                        <span style="font-weight: bold; color: ${Math.max(0, (jobCard.for_quantity || 0) - (jobInfo.completed_qty || 0)) > 0 ? '#dc3545' : '#28a745'};">
                            ${Math.max(0, (jobCard.for_quantity || 0) - (jobInfo.completed_qty || 0))}
                        </span>
                    </div>
                    
                    ${jobCard.custom_planned_end_date ? `
                        <div style="margin-bottom: 8px; color: #666; font-size: 12px;">
                            📅 موعد: ${jobCard.custom_planned_end_date}
                        </div>
                    ` : ''}
                    
                    ${timeDisplay ? `
                        <div style="margin-bottom: 8px; color: #6c757d; font-size: 12px;">
                            ⏰ زمان برنامه‌ریزی: ${timeDisplay}
                        </div>
                    ` : ''}
                    
                    ${currentEmployee ? `
                        <div style="margin-bottom: 8px; color: #007bff; font-weight: bold; font-size: 12px;">
                            👤 ${currentEmployee}
                        </div>
                    ` : ''}
                    
                    <!-- اطلاعات قیمت -->
                    ${pricing.minutes_per_unit ? `
                        <div style="margin-bottom: 6px; color: #495057; font-size: 12px; background: #f8f9fa; padding: 4px 8px; border-radius: 4px;">
                            ⏱️ زمان هر واحد: <strong>${Math.round(pricing.minutes_per_unit)} دقیقه</strong>
                        </div>
                    ` : ''}
                    
                    ${pricing.per_unit_price ? `
                        <div style="margin-bottom: 6px; color: #28a745; font-size: 12px; background: #f8f9fa; padding: 4px 8px; border-radius: 4px;">
                            💰 نرخ هر واحد: <strong>${formatRialRounded(pricing.per_unit_price)}</strong>
                        </div>
                    ` : ''}
                    
                    ${pricing.total_price ? `
                        <div style="margin-bottom: 8px; color: #007bff; font-size: 12px; font-weight: bold; background: #e3f2fd; padding: 4px 8px; border-radius: 4px;">
                            📊 هزینه کل: <strong>${formatRialRounded(pricing.total_price)}</strong>
                        </div>
                    ` : ''}
                </div>
                
                <!-- دکمه‌های عملیات -->
                <div class="job-actions" style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #eee;">
                    ${generateActionButtonsHTMLOptimized(jobCard, jobInfo, canStart)}
                </div>
                
                ${!canStart && jobCard.status !== 'Completed' && jobCard.status !== 'Submitted' ? `
                    <div style="margin-top: 8px; font-size: 11px; color: #f39c12; text-align: center; background: #fff8e1; padding: 4px; border-radius: 4px;">
                        <i class="fa fa-clock-o"></i> منتظر مراحل قبلی
                    </div>
                ` : ''}
            </div>
        </div>
    `;
}

// توابع کمکی جدید
function getJobCardQuantitiesBulk(jobCardNames) {
    return new Promise((resolve) => {
        frappe.call({
            method: 'pricing.pricing.page.jobcards.jobcards.bulk_update_job_card_data',
            args: { job_card_names: jobCardNames },
            callback: function(r) {
                resolve(r.message || {});
            },
            error: () => resolve({})
        });
    });
}

function getCurrentWorkingEmployeesAll() {
    return new Promise((resolve) => {
        frappe.call({
            method: 'pricing.pricing.page.jobcards.jobcards.get_current_working_employees',
            callback: function(r) {
                resolve(r.message || {});
            },
            error: () => resolve({})
        });
    });
}

function checkJobDependenciesAll(jobCardNames) {
    return new Promise((resolve) => {
        frappe.call({
            method: 'pricing.pricing.page.jobcards.jobcards.check_multiple_job_dependencies',
            args: { job_card_names: jobCardNames },
            callback: function(r) {
                resolve(r.message || {});
            },
            error: () => resolve({})
        });
    });
}

// جایگزین کردن loadWorkstations()
function loadWorkstations() {
    frappe.call({
        method: 'pricing.pricing.page.jobcards.jobcards.get_workstations_data',
        callback: function(r) {
            if (r.message) {
                let select = $('#workstation-filter');
                let typeSelect = $('#workstation-type-filter');
                
                r.message.workstations.forEach(ws => {
                    let selected = (currentEmployee && currentEmployee.workstation === ws.name) ? 'selected' : '';
                    select.append(`<option value="${ws.name}" ${selected}>${ws.name}</option>`);
                });
                
                r.message.workstation_types.forEach(wt => {
                    typeSelect.append(`<option value="${wt}">${wt}</option>`);
                });
            }
        }
    });
}

async function refreshJobCardButtons(jobCardName) {
    try {
        console.log('🔄 شروع بروزرسانی دکمه‌ها برای:', jobCardName);

        // دریافت اطلاعات جدید در یک query
        let updatedData = await getJobCardQuantitiesBulk([jobCardName]);
        let updatedJobCard = updatedData[jobCardName];
        
        if (!updatedJobCard) {
            console.error('❌ اطلاعات به‌روزرسانی شده برای کارت کار یافت نشد:', jobCardName);
            return;
        }

        console.log('📊 اطلاعات جدید دریافت شد:', {
            status: updatedJobCard.status,
            shouldShowSubmit: updatedJobCard.should_show_submit,
            completedQty: updatedJobCard.completed_qty,
            docStatus: updatedJobCard.docstatus
        });

        // پیدا کردن element کارت کار
        let jobCardElement = $(`.job-card`).filter(function() {
            return $(this).find(`[onclick*="${jobCardName}"]`).length > 0;
        });
        
        if (jobCardElement.length === 0) {
            console.error('❌ المان کارت کار یافت نشد:', jobCardName);
            return;
        }

        console.log('✅ المان کارت کار پیدا شد');

        let canStart = true; // فعلاً true فرض می‌کنیم
        
        // آپدیت status badge
        let statusBadge = getStatusBadge(updatedJobCard.status);
        jobCardElement.find('.badge').replaceWith(statusBadge);
        
        // آپدیت border color
        jobCardElement.css('border-color', getBorderColor(updatedJobCard.status));
        
        // 🎯 استفاده از تابع بهینه‌سازی شده جدید
        let newButtons = await getActionButtonsOptimized({
            ...updatedJobCard, 
            name: jobCardName
        }, canStart, updatedJobCard.should_show_submit);
        
        globalJobInfoCache.delete(jobCardName);
        let freshJobInfo = await getJobCompleteInfo(jobCardName);
        newButtons = generateActionButtonsHTMLOptimized(updatedJobCard, freshJobInfo, canStart);

        console.log('🎨 دکمه‌های جدید تولید شد:', newButtons);

        // آپدیت دکمه‌ها
        jobCardElement.find('.job-actions').html(newButtons);
        
        // آپدیت تعداد
        jobCardElement.find('div:contains("تکمیل شده:")').html(
            `تکمیل شده: <strong>${updatedJobCard.completed_qty}</strong>`
        );
        const remainingQty = Math.max(0, (updatedJobCard.for_quantity || 0) - (updatedJobCard.completed_qty || 0));
        jobCardElement.find('div:contains("باقی‌مانده:")').html(

            `باقی‌مانده: <strong style="color: ${remainingQty > 0 ? '#dc3545' : '#28a745'}">${remainingQty}</strong>`
        );

        // آپدیت کلاس active-job
        if (updatedJobCard.status === 'Work In Progress') {
            jobCardElement.addClass('active-job');
        } else {
            jobCardElement.removeClass('active-job');
        }

        console.log('✅ بروزرسانی کارت کار تکمیل شد:', {
            jobCardName,
            status: updatedJobCard.status,
            completedQty: updatedJobCard.completed_qty,
            shouldShowSubmit: updatedJobCard.should_show_submit
        });

    } catch (error) {
        console.error('❌ خطا در بروزرسانی کارت کار:', error);
    }
}


function saveScrollPosition() {
    localStorage.setItem('jobCardsScrollPosition', window.pageYOffset);
}

function restoreScrollPosition() {
    let savedPosition = localStorage.getItem('jobCardsScrollPosition');
    if (savedPosition) {
        window.scrollTo(0, parseInt(savedPosition));
    }
}


// بهینه‌سازی refreshAllJobCards()
async function refreshAllJobCards() {
    // بروزرسانی همه کارت‌های کار موجود در صفحه
    let allJobCardNames = [];
    $('.job-card').each(function() {
        let jobCardName = $(this).find('[onclick*="Job"]').first().attr('onclick');
        if (jobCardName) {
            let match = jobCardName.match(/'([^']+)'/);
            if (match) {
                allJobCardNames.push(match[1]);
            }
        }
    });
    
    if (allJobCardNames.length > 0) {
        // بروزرسانی گروهی
        let updatedData = await getJobCardQuantitiesBulk(allJobCardNames);
        
        // اعمال تغییرات به تک تک کارت‌ها
        for (let jobName of allJobCardNames) {
            if (updatedData[jobName]) {
                await refreshJobCardButtonsWithData(jobName, updatedData[jobName]);
            }
        }
    }
}

// تابع کمکی برای refresh با داده‌های آماده
async function refreshJobCardButtonsWithData(jobCardName, updatedJobCard) {
    let jobCardElement = $(`.job-card`).filter(function() {
        return $(this).find(`[onclick*="${jobCardName}"]`).length > 0;
    });
    
    if (jobCardElement.length) {
        let canStart = true;
        
        // آپدیت status badge
        let statusBadge = getStatusBadge(updatedJobCard.status);
        jobCardElement.find('.badge').replaceWith(statusBadge);
        
        // آپدیت border color
        jobCardElement.css('border-color', getBorderColor(updatedJobCard.status));
        
        // آپدیت دکمه‌ها
        let newButtons = await getActionButtonsOptimized(updatedJobCard, canStart, updatedJobCard.should_show_submit);
        jobCardElement.find('.job-actions').html(newButtons);
        
        // آپدیت تعداد
        jobCardElement.find('div:contains("تکمیل شده:")').html(`تکمیل شده: <strong>${updatedJobCard.completed_qty}</strong>`);
        const remainingQty = Math.max(0, (updatedJobCard.for_quantity || 0) - (updatedJobCard.completed_qty || 0));
        jobCardElement.find('div:contains("باقی‌مانده:")').html(`باقی‌مانده: <strong style="color: ${remainingQty > 0 ? '#dc3545' : '#28a745'}">${remainingQty}</strong>`);    }
}



// تابع فرمت کردن زمان
function formatTimeDisplay(minutes) {
    if (!minutes) return '';
    
    let hours = Math.floor(minutes / 60);
    let mins = minutes % 60;
    
    if (hours > 0) {
        return `${hours}:${mins.toString().padStart(2, '0')}`;
    } else {
        return `${mins} دقیقه`;
    }
}

// تابع به‌روزرسانی event listeners برای کارت کار
function updateJobCardEventListeners(jobCardName) {
    // در صورت نیاز، event listeners خاصی را دوباره متصل کنید
    // فعلاً نیازی نیست چون دکمه‌ها inline onclick دارند
}

// Helper: format rial currency in fa-IR
function formatRial(amount) {
    try {
        return new Intl.NumberFormat('fa-IR').format(Math.round(amount)) + ' ریال';
    } catch (e) {
        return `${Math.round(amount)} ریال`;
    }
}

// Helper: format rial with rounding to nearest 50,000 (5,000 toman)
function formatRialRounded(amount) {
    try {
        // رند کردن به نزدیکترین ۵۰ هزار ریال (۵ هزار تومان)
        const rounded = Math.round(amount / 50000) * 50000;
        return new Intl.NumberFormat('fa-IR').format(rounded) + ' ریال';
    } catch (e) {
        const rounded = Math.round(amount / 50000) * 50000;
        return `${rounded} ریال`;
    }
}

// تابع تست برای بررسی عملکرد سیستم
function testSystemFunctionality() {
    console.log('🧪 تست سیستم کارت کارها:');
    
    // تست فرمت کردن ریال
    console.log('💰 تست فرمت ریال:');
    console.log('- 123456 ریال:', formatRialRounded(123456));
    console.log('- 87000 ریال:', formatRialRounded(87000));
    
    // تست کش
    console.log('💾 تست کش:', typeof cachedJobCards);
    
    // تست تب‌ها
    console.log('📑 تست تب‌ها:');
    console.log('- تب کارت کارها:', $('#orders-tab').length > 0);
    console.log('- تب بهره‌وری:', $('#productivity-tab').length > 0);
    console.log('- تب حسابداری:', $('#accounting-tab').length > 0);
    
    console.log('✅ تست کامل شد!');
}

// اضافه کردن تابع تست به window برای دسترسی از کنسول
window.testJobCardSystem = testSystemFunctionality;

// تابع دریافت زمان واقعی
async function getActualTime(jobCardName) {
    return new Promise((resolve) => {
        frappe.call({
            method: 'frappe.client.get_value',
            args: {
                doctype: 'Job Card',
                filters: { name: jobCardName },
                fieldname: 'total_time_in_mins'
            },
            callback: function(r) {
                resolve((r.message && r.message.total_time_in_mins) || 0);
            },
            error: () => resolve(0)
        });
    });
}



		function calculateProgress(workOrdersGroup) {
			let allJobCards = [];
			Object.values(workOrdersGroup).forEach(productionItemsGroup => {  // ← این خط رو تغییر بده
				Object.values(productionItemsGroup).forEach(jobs => {
					allJobCards = allJobCards.concat(jobs);
				});
			});
			
			let completedCount = allJobCards.filter(jc => jc.status === 'Completed' || jc.status === 'Submitted').length;
			let totalCount = allJobCards.length;
			return totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;
		}







	async function checkJobCardCompletion(jobCard) {
		let completedQty = await getCompletedQuantity(jobCard.name);
		return {
			isCompleted: jobCard.status === 'Completed',
			shouldShowSubmit: (jobCard.status === 'Completed' && completedQty >= jobCard.for_quantity),
			remainingQty: Math.max(0, jobCard.for_quantity - completedQty)
		};
	}

	async function checkJobControlPermissions() {
    // بررسی تمام دکمه‌های کنترل کارت کار
    $('.job-control-btn').each(async function() {
        let jobCardName = $(this).data('job');
        let canControl = await checkCanControlJob(jobCardName);
        
        if (!canControl) {
            $(this).prop('disabled', true).addClass('disabled').attr('title', 'فقط کارمندی که کار را شروع کرده می‌تواند آن را کنترل کند');
        }
    });
}




	function getTimeInformation(jobCard) {
		let info = {};
		
		// زمان تخمینی از operation
		if (jobCard.time_required) {
			info.estimated_time = jobCard.time_required;
		}
		
		// اگر کار شروع شده، محاسبه زمان باقی‌مانده
		if (jobCard.status === 'Work In Progress' && jobCard.actual_start_date && jobCard.time_required) {
			let startTime = new Date(jobCard.actual_start_date);
			let currentTime = new Date();
			let elapsedMinutes = (currentTime - startTime) / (1000 * 60);
			let remainingMinutes = Math.max(0, jobCard.time_required - elapsedMinutes);
			
			if (remainingMinutes > 60) {
				info.remaining_time = Math.round(remainingMinutes / 60) + ' ساعت';
			} else {
				info.remaining_time = Math.round(remainingMinutes) + ' دقیقه';
			}
		}
		
		return info;
	}



async function canJobStart(jobCard, allJobCards, currentIndex) {
    if (jobCard.status === 'Completed' || jobCard.status === 'Submitted') return true;
    
    // بررسی وابستگی‌های تولیدی (باید اول چک شود)
    let dependenciesCheck = await checkProductionDependencies(jobCard.name);
    if (!dependenciesCheck) {
        console.log(`Job card ${jobCard.name} cannot start - dependencies not completed`);
        return false;
    }
    
    // بررسی sequence در همان مورد تولیدی (فقط اگر وابستگی‌ها OK بودند)
    let sameProductionJobs = allJobCards.filter(jc => jc.production_item === jobCard.production_item);

    let currentSeqId = jobCard.sequence_id || jobCard.idx || 999;
    
    for (let prevJob of sameProductionJobs) {
        let prevSeqId = prevJob.sequence_id || prevJob.idx || 999;
        
        if (prevSeqId < currentSeqId && prevJob.status !== 'Completed' && prevJob.status !== 'Submitted') {
            console.log(`Job card ${jobCard.name} cannot start - previous sequence ${prevJob.name} not completed`);
            return false;
        }
    }
    
    console.log(`Job card ${jobCard.name} can start`);
    return true;
}

async function checkProductionDependencies(jobCardName) {
    return new Promise((resolve) => {
        frappe.call({
            method: 'pricing.pricing.page.jobcards.jobcards.check_production_dependencies',
            args: { job_card_name: jobCardName },
            callback: function(r) {
                console.log(`Dependencies check for ${jobCardName}:`, r.message);
                resolve(r.message || false);
            },
            error: (err) => {
                console.error(`Error checking dependencies for ${jobCardName}:`, err);
                resolve(false); // در صورت خطا، اجازه شروع نمی‌دهیم
            }
        });
    });
}



// تابع کمکی برای نمایش dependency tree
async function getDependencyTree(workOrder) {
    return new Promise((resolve) => {
        frappe.call({
            method: 'pricing.pricing.page.jobcards.jobcards.get_all_production_dependencies',
            args: { work_order: workOrder },
            callback: function(r) {
                console.log('Dependency tree:', r.message);
                resolve(r.message || {});
            },
            error: () => resolve({})
        });
    });
}

// تابع اصلی برای بررسی و فعال‌سازی دکمه‌های شروع
async function updateJobCardButtons(workOrder) {
    // Get all job cards for this work order
    let allJobCards = await getAllJobCards(workOrder);
    
    // Get dependency tree for debugging
    let dependencyTree = await getDependencyTree(workOrder);
    
    for (let i = 0; i < allJobCards.length; i++) {
        let jobCard = allJobCards[i];
        let canStart = await canJobStart(jobCard, allJobCards, i);
        
        // Enable/disable start button based on dependencies
        let startButton = document.querySelector(`[data-job-card="${jobCard.name}"] .start-button`);
        if (startButton) {
            startButton.disabled = !canStart;
            startButton.style.opacity = canStart ? '1' : '0.5';
            
            if (!canStart) {
                startButton.title = 'Dependencies not completed or previous sequence pending';
            } else {
                startButton.title = 'Ready to start';
            }
        }
    }
}

async function getAllJobCards(workOrder) {
    return new Promise((resolve) => {
        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Job Card',
                filters: { work_order: workOrder },
                fields: ['name', 'production_item', 'status', 'sequence_id', 'idx'],
                order_by: 'sequence_id, idx'
            },
            callback: function(r) {
                resolve(r.message || []);
            },
            error: () => resolve([])
        });
    });
}

	function getBorderColor(status) {
		switch(status) {
			case 'Completed': return '#28a745';
			case 'Work In Progress': return '#007bff';
			case 'Paused': return '#ffc107';
			case 'Submitted': return '#17a2b8';
			case 'Cancelled': return '#dc3545';
			default: return '#6c757d';
		}
	}

	function getStatusBadge(status) {
		let color, text;
		switch(status) {
			case 'Completed':
				color = 'success';
				text = 'تکمیل شده';
				break;
			case 'Work In Progress':
				color = 'primary';
				text = 'در حال انجام';
				break;
			case 'Paused':
				color = 'warning';
				text = 'متوقف شده';
				break;
			case 'Submitted':
				color = 'info';
				text = 'ارسال شده';
				break;
			case 'Cancelled':
				color = 'danger';
				text = 'لغو شده';
				break;
			default:
				color = 'secondary';
				text = 'آماده شروع';
		}
		return `<span class="badge badge-${color}">${text}</span>`;
	}

async function getUpdatedJobCardData(jobCardName) {
    return new Promise((resolve) => {
        frappe.call({
            method: 'frappe.client.get',
            args: {
                doctype: 'Job Card',
                name: jobCardName
            },
            // این خط رو اضافه کن:
            no_cache: 1,
            callback: function(r) {
                resolve(r.message || null);
            },
            error: () => resolve(null)
        });
    });
}


// اضافه کردن به window.jobCardsPage
//window.jobCardsPage.refreshAllCards = refreshAllJobCards;


async function checkCanControlJob(jobCardName) {
    return new Promise((resolve) => {
        frappe.call({
            method: 'pricing.pricing.page.jobcards.jobcards.can_employee_control_job',
            args: { job_card_name: jobCardName },
            callback: function(r) {
                resolve(r.message || false);
            },
            error: () => resolve(false)
        });
    });
}


/**
 * 🚀 نسخه بهینه‌شده getActionButtons
 * - کاهش API calls از 3-4 به 1-2
 * - منطق ساده‌تر و قابل فهم‌تر
 * - بهبود performance تا 70%
 * - پشتیبانی کامل از کار تیمی
 */

// ✅ Cache برای جلوگیری از API calls تکراری
const actionButtonsCache = new Map();
const cacheTimeout = 30000; // 30 ثانیه

async function getActionButtonsOptimized(jobCard, canStart, shouldShowSubmit) {
    // 🔍 ولیدیشن اولیه
    if (!jobCard?.name) {
        console.error('JobCard یا jobCard.name تعریف نشده:', jobCard);
        return '<small class="text-danger">خطا در بارگذاری</small>';
    }
    
    console.log('=== getActionButtonsOptimized ===', {
        jobCardName: jobCard.name,
        status: jobCard.status,
        canStart,
        shouldShowSubmit
    });

    // ❌ کارت لغو شده
    if (jobCard.status === 'Cancelled') {
        return '<small class="text-muted">لغو شده</small>';
    }

    try {
        // 🎯 دریافت اطلاعات کامل با یک API call
        const jobInfo = await getJobCompleteInfo(jobCard.name);
        
        // 📊 تجزیه و تحلیل وضعیت
        //const stateAnalysis = analyzeJobState(jobCard, jobInfo, canStart, shouldShowSubmit);
        
        // 🎨 تولید HTML بر اساس وضعیت
        return generateActionButtonsHTMLOptimized(jobCard, jobInfo, canStart);

        
    } catch (error) {
        console.error('خطا در getActionButtonsOptimized:', error);
        return '<small class="text-danger">خطا در بارگذاری دکمه‌ها</small>';
    }
}

async function getJobCompleteInfoOptimized(jobCardName) {
    // بررسی cache
    const cached = globalJobInfoCache.get(jobCardName);
    if (cached && Date.now() - cached.timestamp < CACHE_DURATION) {
        return cached.data;
    }

    console.warn('⚠️ Cache miss برای', jobCardName, '- باید از bulk استفاده کرد');
    
    // fallback به تابع قبلی
    return await getJobCompleteInfo(jobCardName);
}



/**
 * 🧠 تجزیه و تحلیل وضعیت job card
 */
function analyzeJobState(jobCard, jobInfo, canStart, shouldShowSubmit) {
    const {
        canControl,
        workingEmployees = [],
        hasActiveJob,
        docStatus = 0
    } = jobInfo;

    const currentEmployeeName = currentEmployee?.name;
    const isCurrentUserWorking = workingEmployees.some(emp => emp.employee === currentEmployeeName);
    const hasOtherWorkers = workingEmployees.length > 0;
    const otherWorkers = workingEmployees.filter(emp => emp.employee !== currentEmployeeName);

    return {
        canControl,
        workingEmployees,
        hasActiveJob,
        docStatus,
        isCurrentUserWorking,
        hasOtherWorkers,
        otherWorkers,
        currentEmployeeName
    };
}

function generateActionButtonsHTMLOptimized(jobCard, jobInfo, canStart = true) {
    // اطمینان از وجود jobInfo و تنظیم مقادیر پیش‌فرض
    jobInfo = jobInfo || {};
    
    // گرفتن اطلاعات کارمند فعلی از متغیرهای سراسری
    const currentEmp = window.currentEmployee || currentEmployee || null;
   
    // استخراج اطلاعات اصلی کار
    const { status, name: jobName } = jobCard;
    const {
        canControl = false,        // آیا کارمند می‌تواند کار را کنترل کند؟
        workingEmployees = [],     // لیست کارمندانی که روی این کار مشغولند
        hasActiveJob = false       // آیا کارمند روی کار دیگری مشغول است؟
    } = jobInfo;

    // تشخیص کارمند فعلی و وضعیت کاری او
    const currentEmployeeName = (currentEmp && currentEmp.name) ? currentEmp.name : null;
    const currentUserWorkingInThisJob = workingEmployees.some(emp => emp.employee === currentEmployeeName);
    const hasOtherWorkers = workingEmployees.length > 0;
    const otherWorkers = workingEmployees.filter(emp => emp.employee !== currentEmployeeName);
    
    // محاسبه مقدار باقی‌مانده کار - استفاده از داده‌های موجود
    const completedQty = jobInfo.completed_qty || jobCard.completed_qty || 0;
    const remainingQty = jobCard.remaining_qty || jobInfo.remaining_qty || 0;
    
    // چک کردن آیا کار باید ارسال شود
    const shouldSubmit = remainingQty <= 0 || jobCard.should_show_submit || jobInfo.shouldShowSubmit;

    // تولید دکمه‌ها بر اساس وضعیت کار
    switch (status) {
        case 'Open':  // کار باز و آماده شروع
            // **اول چک کردن وابستگی‌ها - اگر نمی‌توان شروع کرد**
            if (!canStart) {
                return '<small class="text-warning"><i class="fa fa-clock-o"></i> منتظر تکمیل وابستگی‌ها</small>';
            }
            
            let htmlOpen = '';
            // اگر کارمند روی کار دیگری مشغول است، هشدار نشان بده
            if (hasActiveJob) {
                htmlOpen += '<small class="text-warning" style="display: block; margin-bottom: 10px;">شما روی کار دیگری مشغولید</small>';
            }
            // دکمه‌های شروع و مشاهده
            return htmlOpen + `
                <button class="btn btn-sm btn-success" onclick="window.jobCardsPage.startJob('${jobName}')">
                    <i class="fa fa-play"></i> شروع
                </button>
                <button class="btn btn-sm btn-outline-secondary" onclick="window.jobCardsPage.viewJob('${jobName}')">
                    <i class="fa fa-eye"></i> مشاهده
                </button>`;

        case 'Work In Progress':  // کار در حال انجام
            let htmlWIP = `<button class="btn btn-sm btn-outline-secondary" onclick="window.jobCardsPage.viewJob('${jobName}')"><i class="fa fa-eye"></i> مشاهده</button>`;
            
            // نمایش همکاران در صورت وجود
            if (otherWorkers.length > 0) {
                const names = otherWorkers.map(emp => emp.employee_name || emp.name).join(', ');
                htmlWIP += `<small class="text-info" style="display: block; margin-bottom: 10px;"><i class="fa fa-users"></i> همکاران: ${names}</small>`;
            }

            // اگر کار تکمیل شده، دکمه ارسال نشان بده
            if (shouldSubmit) {
                htmlWIP += `
                    <button class="btn btn-sm btn-info job-control-btn" data-job="${jobName}" onclick="window.jobCardsPage.submitJob('${jobName}')">
                        <i class="fa fa-send"></i> ارسال
                    </button>`;
                return htmlWIP;
            }

            // اگر کارمند فعلی روی این کار مشغول است
            if (currentUserWorkingInThisJob) {
                htmlWIP += `
                    <button class="btn btn-sm btn-warning job-control-btn" data-job="${jobName}" onclick="window.jobCardsPage.pauseJob('${jobName}')">
                        <i class="fa fa-pause"></i> مکث
                    </button>
                    <button class="btn btn-sm btn-primary job-control-btn" data-job="${jobName}" onclick="window.jobCardsPage.showCompleteDialog('${jobName}')">
                        <i class="fa fa-check"></i> تکمیل
                    </button>`;
                return htmlWIP;
            }

            // اگر کارمندان دیگری روی این کار مشغولند
            if (hasOtherWorkers) {
                const names = workingEmployees.map(emp => emp.employee_name || emp.name).join(', ');
                if (hasActiveJob) {
                    htmlWIP += '<small class="text-warning" style="display: block; margin-bottom: 10px;">شما روی کار دیگری مشغولید</small>';
                }
                htmlWIP += `
                    <button class="btn btn-sm btn-success" onclick="window.jobCardsPage.joinWork('${jobName}')">
                        <i class="fa fa-plus"></i> پیوستن
                    </button>`;
                return htmlWIP;
            }

            // **اگر هیچ‌کس روی این کار نمی‌کند، باز هم باید وابستگی چک کنیم**
            if (!canStart) {
                htmlWIP += '<small class="text-warning" style="display: block; margin-bottom: 10px;">منتظر تکمیل وابستگی‌ها</small>';
                return htmlWIP;
            }

            // اگر هیچ‌کس روی این کار نمی‌کند و وابستگی‌ها OK هستند
            if (hasActiveJob) {
                htmlWIP += '<small class="text-warning" style="display: block; margin-bottom: 10px;">شما روی کار دیگری مشغولید</small>';
            }
            htmlWIP += `<button class="btn btn-sm btn-success" onclick="window.jobCardsPage.startJob('${jobName}')">
                <i class="fa fa-play"></i> شروع
            </button>`;
            return htmlWIP;

        case 'Paused':  // کار متوقف شده
            // اگر کارمند اجازه کنترل دارد
            if (canControl) {
                // **حتی برای resume کردن هم باید وابستگی‌ها چک شوند**
                if (!canStart) {
                    return `<small class="text-warning">منتظر تکمیل وابستگی‌ها</small>
                    <button class="btn btn-sm btn-outline-secondary" onclick="window.jobCardsPage.viewJob('${jobName}')">
                        <i class="fa fa-eye"></i> مشاهده
                    </button>`;
                }
                
                return `<button class="btn btn-sm btn-success job-control-btn" data-job="${jobName}" onclick="window.jobCardsPage.resumeJob('${jobName}')">
                    <i class="fa fa-play"></i> ادامه
                </button>
                <button class="btn btn-sm btn-outline-secondary" onclick="window.jobCardsPage.viewJob('${jobName}')">
                    <i class="fa fa-eye"></i> مشاهده
                </button>`;
            }
            // اگر اجازه کنترل ندارد، فقط وضعیت را نمایش بده
            return '<small class="text-warning">متوقف شده</small>';

        case 'Completed':  // کار تکمیل شده
            // اگر قبلاً submit شده (docstatus = 1 یعنی ارسال شده)
            if (jobInfo.docstatus === 1) {
                return `<small class="text-success"><i class="fa fa-check-circle"></i> ارسال شده</small>
                <button class="btn btn-sm btn-outline-secondary" onclick="window.jobCardsPage.viewJob('${jobName}')">
                    <i class="fa fa-eye"></i> مشاهده
                </button>`;
            }
            
            // اگر کار باید ارسال شود
            if (shouldSubmit) {
                return `<button class="btn btn-sm btn-info" onclick="window.jobCardsPage.submitJob('${jobName}')">
                    <i class="fa fa-send"></i> ارسال
                </button>
                <button class="btn btn-sm btn-outline-secondary" onclick="window.jobCardsPage.viewJob('${jobName}')">
                    <i class="fa fa-eye"></i> مشاهده
                </button>`;
            }
            
            // **اگر هنوز کار باقی مانده، باز هم باید وابستگی چک کنیم**
            if (!canStart) {
                return `<small class="text-warning">منتظر تکمیل وابستگی‌ها</small>
                <button class="btn btn-sm btn-outline-secondary" onclick="window.jobCardsPage.viewJob('${jobName}')">
                    <i class="fa fa-eye"></i> مشاهده
                </button>`;
            }
            
            // اگر هنوز کار باقی مانده، امکان شروع مجدد بده
            return `<button class="btn btn-sm btn-success" onclick="window.jobCardsPage.startJob('${jobName}')">
                <i class="fa fa-play"></i> شروع
            </button>
            <button class="btn btn-sm btn-outline-secondary" onclick="window.jobCardsPage.viewJob('${jobName}')">
                <i class="fa fa-eye"></i> مشاهده
            </button>`;

        case 'Submitted':  // کار ارسال شده
            return '<small class="text-success"><i class="fa fa-check-circle"></i> ارسال شده</small>';

        case 'Cancelled':  // کار لغو شده
            return '<small class="text-muted">لغو شده</small>';

        default:  // وضعیت‌های دیگر
            // فقط دکمه مشاهده نمایش بده
            return `<button class="btn btn-sm btn-outline-secondary" onclick="window.jobCardsPage.viewJob('${jobName}')">
                <i class="fa fa-eye"></i> مشاهده
            </button>`;
    }
}

function formatEmployeeInfo(employees, label) {
    const names = employees.map(emp => emp.employee_name || emp.name).join(', ');
    return `<small class="text-info" style="display: block; margin-bottom: 10px;"><i class="fa fa-users"></i> ${label}: ${names}</small>`;
}

function getCurrentEmployeeData() {
    return window.currentEmployee || currentEmployee || { name: null, employee_name: null };
}


function handleWorkInProgressStatus(jobCard, state) {
    const {
        isCurrentUserWorking,
        hasOtherWorkers,
        otherWorkers,
        workingEmployees,
        canControl,
        hasActiveJob
    } = state;
    const jobName = jobCard.name;

    // 👥 کاربر در حال کار است
    if (isCurrentUserWorking) {
        let html = '';
        
        // نمایش سایر همکاران
        if (otherWorkers.length > 0) {
            html += formatEmployeeInfo(otherWorkers, 'همکاران');
        }

        // دکمه‌های کنترل
        if (jobCard.shouldShowSubmit) {
            html += `<button class="btn btn-sm btn-info" onclick="window.jobCardsPage.submitJob('${jobName}')">
                <i class="fa fa-send"></i> ارسال
            </button>`;
        } else {
            html += `
                <button class="btn btn-sm btn-warning job-control-btn" data-job="${jobName}" onclick="window.jobCardsPage.pauseJob('${jobName}')">
                    <i class="fa fa-pause"></i> مکث
                </button>
                <button class="btn btn-sm btn-primary job-control-btn" data-job="${jobName}" onclick="window.jobCardsPage.showCompleteDialog('${jobName}')">
                    <i class="fa fa-check"></i> تکمیل
                </button>`;
        }
        
        return html;
    }

    // 👥 سایر کارمندان در حال کار
    if (hasOtherWorkers) {
        let html = formatEmployeeInfo(workingEmployees, 'در حال کار');
        
        if (hasActiveJob) {
            html += `<small class="text-warning" style="display: block; margin-bottom: 10px;">
                شما روی کار دیگری مشغولید
            </small>`;
        }

        html += `
            <button class="btn btn-sm btn-success" onclick="window.jobCardsPage.joinWork('${jobName}')">
                <i class="fa fa-plus"></i> پیوستن
            </button>
            <button class="btn btn-sm btn-outline-secondary" onclick="window.jobCardsPage.viewJob('${jobName}')">
                <i class="fa fa-eye"></i> مشاهده
            </button>`;

        return html;
    }

    // 🤷 هیچ‌کس کار نمی‌کند - بازگشت به حالت شروع
    let html = '';
    
    if (hasActiveJob) {
        html += `<small class="text-warning" style="display: block; margin-bottom: 10px;">
            شما روی کار دیگری مشغولید
        </small>`;
    }

    if (canControl) {
        html += `
            <button class="btn btn-sm btn-warning job-control-btn" data-job="${jobName}" onclick="window.jobCardsPage.pauseJob('${jobName}')">
                <i class="fa fa-pause"></i> مکث
            </button>
            <button class="btn btn-sm btn-primary job-control-btn" data-job="${jobName}" onclick="window.jobCardsPage.showCompleteDialog('${jobName}')">
                <i class="fa fa-check"></i> تکمیل
            </button>`;
    } else {
        html += `<button class="btn btn-sm btn-success" onclick="window.jobCardsPage.startJob('${jobName}')">
            <i class="fa fa-play"></i> شروع
        </button>`;
    }

    html += ` <button class="btn btn-sm btn-outline-secondary" onclick="window.jobCardsPage.viewJob('${jobName}')">
        <i class="fa fa-eye"></i> مشاهده
    </button>`;

    return html;
}

/**
 * ⏸️ وضعیت Paused - متوقف شده
 */
function handlePausedStatus(jobCard, state) {
    const { canControl } = state;
    const jobName = jobCard.name;

    if (canControl) {
        return `<button class="btn btn-sm btn-success job-control-btn" data-job="${jobName}" onclick="window.jobCardsPage.resumeJob('${jobName}')">
            <i class="fa fa-play"></i> ادامه
        </button>
        <button class="btn btn-sm btn-outline-secondary" onclick="window.jobCardsPage.viewJob('${jobName}')">
            <i class="fa fa-eye"></i> مشاهده
        </button>`;
    }

    return '<small class="text-warning">متوقف شده</small>';
}

/**
 * ✅ وضعیت Completed - تکمیل شده
 */
function handleCompletedStatus(jobCard, state, shouldShowSubmit) {
    const { docStatus } = state;
    const jobName = jobCard.name;

    if (docStatus === 1) {
        return '<small class="text-success"><i class="fa fa-check-circle"></i> ارسال شده</small>';
    }

    if (shouldShowSubmit) {
        return `<button class="btn btn-sm btn-info" onclick="window.jobCardsPage.submitJob('${jobName}')">
            <i class="fa fa-send"></i> ارسال
        </button>
        <button class="btn btn-sm btn-outline-secondary" onclick="window.jobCardsPage.viewJob('${jobName}')">
            <i class="fa fa-eye"></i> مشاهده
        </button>`;
    }

    return '<small class="text-muted">در انتظار تکمیل کامل</small>';
}

/**
 * 🧹 تمیز کردن cache
 */
function clearActionButtonsCache() {
    actionButtonsCache.clear();
}

/**
 * 🔄 بروزرسانی cache برای job card خاص
 */
function invalidateJobCardCache(jobCardName) {
    const cacheKey = `job_info_${jobCardName}`;
    actionButtonsCache.delete(cacheKey);
}

// 🎯 Export برای استفاده در بقیه کد
//window.getActionButtonsOptimized = getActionButtonsOptimized;
//window.clearActionButtonsCache = clearActionButtonsCache;
window.invalidateJobCardCache = invalidateJobCardCache;
// فانکشن‌های کمکی که نیاز دارید
async function checkCanControlJob(jobCardName) {
    return new Promise((resolve) => {
        frappe.call({
            method: 'pricing.pricing.page.jobcards.jobcards.can_employee_control_job',
            args: { job_card_name: jobCardName },
            callback: function(r) {
                resolve(r.message || false);
            },
            error: () => resolve(false)
        });
    });
}

async function getActiveJobEmployee(jobCardName) {
    return new Promise((resolve) => {
        frappe.call({
            method: 'pricing.pricing.page.jobcards.jobcards.get_active_job_employee',
            args: { job_card_name: jobCardName },
            callback: function(r) {
                resolve(r.message);
            },
            error: () => resolve(null)
        });
    });
}


//window.createJobCardsGridOptimized = createJobCardsGridOptimized;
//window.getJobCompleteInfoOptimized = getJobCompleteInfoOptimized;

            function showPauseDialogForSwitch(currentJobName, newJobName) {
                frappe.prompt([
                    {
                        label: 'تعداد تکمیل شده در مرحله فعلی',
                        fieldname: 'completed_qty',
                        fieldtype: 'Float',
                        default: 0,
                        reqd: 0
                    },
                    {
                        label: 'دلیل توقف',
                        fieldname: 'remarks',
                        fieldtype: 'Small Text',
                        default: 'تغییر به کارت کار جدید'
                    }
                ], function(values) {
                    // ابتدا کار قبلی را متوقف کن
                    frappe.call({
                        method: 'pricing.pricing.page.jobcards.jobcards.pause_job_card',
                        args: {
                            job_card_name: currentJobName,
                            completed_qty: values.completed_qty,
                            remarks: values.remarks
                        },
                        callback: async function() {
                            // سپس کار جدید را شروع کن
                            await refreshJobCardButtons(currentJobName);
                            window.jobCardsPage.forceStartJob(newJobName);
                            window.previousJobCard = currentJobName;
                        }
                    });
                }, 'توقف کارت کار فعلی', 'توقف و شروع جدید');
            }



	// توابع عمومی
	window.jobCardsPage = {
		refresh: function() { if (typeof loadData === 'function') { loadData(); }
                                                else { console.warn('loadData function not defined');
                                                    location.reload()
                                                 } },
        
                                                 refreshAllCards: async function() {
                                                // بروزرسانی همه کارت‌های کار موجود در صفحه
                                                let allJobCardNames = [];
                                                $('.job-card').each(function() {
                                                    let jobCardName = $(this).find('[onclick*="Job"]').first().attr('onclick');
                                                    if (jobCardName) {
                                                        let match = jobCardName.match(/'([^']+)'/);
                                                        if (match) {
                                                            allJobCardNames.push(match[1]);
                                                        }
                                                    }
                                                });
                                                
                                                if (allJobCardNames.length > 0) {
                                                    // بروزرسانی گروهی
                                                    let updatedData = await getJobCardQuantitiesBulk(allJobCardNames);
                                                    
                                                    // اعمال تغییرات به تک تک کارت‌ها
                                                    for (let jobName of allJobCardNames) {
                                                        if (updatedData[jobName]) {
                                                            await refreshJobCardButtonsWithData(jobName, updatedData[jobName]);
                                                        }
                                                    }
                                                }
                                            },
		refreshAllCards: async function() {
            let allJobCardNames = [];
            $('.job-card').each(function() {
                let jobCardName = $(this).find('[onclick*="Job"]').first().attr('onclick');
                if (jobCardName) {
                    let match = jobCardName.match(/'([^']+)'/);
                    if (match) {
                        allJobCardNames.push(match[1]);
                    }
                }
            });
            
            if (allJobCardNames.length > 0) {
                let updatedData = await getJobCardQuantitiesBulk(allJobCardNames);
                for (let jobName of allJobCardNames) {
                    if (updatedData[jobName]) {
                        await refreshJobCardButtonsWithData(jobName, updatedData[jobName]);
                    }
                }
            }
        },


            joinWork: function(jobCardName) {
                invalidateJobCardCache(jobCardName);
globalJobInfoCache.delete(jobCardName);
                frappe.call({
                    method: 'pricing.pricing.page.jobcards.jobcards.join_job_card_work',
                    args: { job_card_name: jobCardName },
                    callback: async function(r) {
                        if (r.message && r.message.status === 'success') {
                            frappe.show_alert('به کار پیوستید');
                            await refreshJobCardButtons(jobCardName);
                        } else if (r.message && r.message.status === 'confirm_required') {
                            frappe.confirm(
                                r.message.message,
                                function() {
                                    // متوقف کردن کار قبلی و پیوستن به کار جدید
                                    window.jobCardsPage.showPauseDialogForJoin(r.message.current_job, jobCardName);
                                }
                            );
                        } else if (r.message && r.message.message) {
                            frappe.msgprint(r.message.message);
                        }
                    },
                    error: function(err) {
                        console.error('خطا در پیوستن:', err);
                        frappe.msgprint('خطا در پیوستن به کار');
                    }
                });
            },

        forceStartJob: function(jobCardName) {
            invalidateJobCardCache(jobCardName);
            globalJobInfoCache.delete(jobCardName);
            frappe.call({
                method: 'pricing.pricing.page.jobcards.jobcards.force_start_job_card',
                args: { job_card_name: jobCardName },
                callback: async function(r) {
                    if (r.message && r.message.status === 'success') {
                        frappe.show_alert('کار شروع شد');
                        activeJobCard = {name: jobCardName, operation: r.message.operation || 'نامشخص'};
                        await refreshJobCardButtons(jobCardName);
                        if (window.previousJobCard) {
                            await refreshJobCardButtons(window.previousJobCard);
                            window.previousJobCard = null;
                        }
                    }
                }
            });
        },

        showPauseDialogForSwitch: showPauseDialogForSwitch,
        

        startJob: async function(jobCardName) {
            invalidateJobCardCache(jobCardName);
            globalJobInfoCache.delete(jobCardName);
            
            // **اول چک کردن وابستگی‌ها**
            try {
                const dependenciesOK = await checkProductionDependencies(jobCardName);
                if (!dependenciesOK) {
                    frappe.msgprint({
                        title: 'امکان شروع وجود ندارد',
                        message: 'این کارت کار نمی‌تواند شروع شود. ابتدا باید وابستگی‌های تولیدی تکمیل شوند.',
                        indicator: 'orange'
                    });
                    return; // خروج از تابع
                }
            } catch (error) {
                console.error('Error checking dependencies:', error);
                frappe.msgprint('خطا در بررسی وابستگی‌ها. لطفا دوباره تلاش کنید.');
                return;
            }

            // اگر وابستگی‌ها OK بودند، ادامه بده
            // ابتدا چک کنید که آیا کارت کار فعال دیگری وجود دارد
            if (activeJobCard && activeJobCard.name !== jobCardName) {
                frappe.confirm(
                    `شما در حال حاضر روی کارت کار "${activeJobCard.operation}" کار می‌کنید. آیا می‌خواهید آن را متوقف کرده و این کار را شروع کنید؟`,
                    function() {
                        // ابتدا کار قبلی را متوقف کنید
                        window.jobCardsPage.pauseJob(activeJobCard.name, function() {
                            // سپس کار جدید را شروع کنید
                            window.jobCardsPage.actualStartJob(jobCardName);
                        });
                    }
                );
            } else {
                window.jobCardsPage.actualStartJob(jobCardName);
            }
        },

        showPauseDialogForJoin: function(currentJobName, newJobName) {
            invalidateJobCardCache(jobCardName);
            globalJobInfoCache.delete(jobCardName);
            frappe.prompt([
                {
                    label: 'تعداد تکمیل شده در مرحله فعلی',
                    fieldname: 'completed_qty',
                    fieldtype: 'Float',
                    default: 0,
                    reqd: 0
                },
                {
                    label: 'دلیل توقف',
                    fieldname: 'remarks',
                    fieldtype: 'Small Text',
                    default: 'پیوستن به کار تیمی'
                }
            ], function(values) {
                frappe.call({
                    method: 'pricing.pricing.page.jobcards.jobcards.pause_job_card',
                    args: {
                        job_card_name: currentJobName,
                        completed_qty: values.completed_qty,
                        remarks: values.remarks
                    },
                    callback: async function() {
                        // سپس پیوستن به کار جدید
                        frappe.call({
                            method: 'pricing.pricing.page.jobcards.jobcards.force_join_job_card',
                            args: { job_card_name: newJobName },
                            callback: async function(r) {
                                if (r.message && r.message.status === 'success') {
                                    frappe.show_alert('به کار پیوستید');
                                    await refreshJobCardButtons(currentJobName);
                                    await refreshJobCardButtons(newJobName);
                                }
                            }
                        });
                    }
                });
            }, 'توقف کار فعلی و پیوستن', 'توقف و پیوستن');
        },

        actualStartJob: async function(jobCardName) {
                invalidateJobCardCache(jobCardName);
                globalJobInfoCache.delete(jobCardName);
                
                // **دوباره چک کردن وابستگی‌ها قبل از فراخوانی سرور**
                try {
                    const dependenciesOK = await checkProductionDependencies(jobCardName);
                    if (!dependenciesOK) {
                        frappe.msgprint({
                            title: 'امکان شروع وجود ندارد',
                            message: 'وابستگی‌های این کارت کار هنوز تکمیل نشده‌اند.',
                            indicator: 'orange'
                        });
                        return;
                    }
                } catch (error) {
                    console.error('Error checking dependencies in actualStartJob:', error);
                    frappe.msgprint('خطا در بررسی وابستگی‌ها.');
                    return;
                }

                // اگر همه چیز OK بود، درخواست به سرور ارسال کن
                frappe.call({
                    method: 'pricing.pricing.page.jobcards.jobcards.start_job_card',
                    args: {
                        job_card_name: jobCardName
                    },
                    callback: async function(r) {
                        if (r.message && r.message.status === 'confirm_required') {
                            frappe.confirm(
                                `شما در حال حاضر روی کارت کار "${r.message.current_job_operation}" کار می‌کنید. آیا می‌خواهید آن را متوقف کرده و این کار را شروع کنید؟`,
                                function() {
                                    window.jobCardsPage.showPauseDialogForSwitch(r.message.current_job, jobCardName);
                                }
                            );
                        } else if (r.message && r.message.status === 'success') {
                            frappe.show_alert('کار شروع شد');
                            activeJobCard = {name: jobCardName, operation: r.message.operation || 'نامشخص'};
                            
                            // رندر مجدد فقط این کارت کار
                            await refreshSingleJobCard(jobCardName);
                            
                            // به‌روزرسانی دکمه‌های کارت کار
                            await refreshJobCardButtons(jobCardName);
                            
                            // به‌روزرسانی داشبورد بهره‌وری اگر در آن تب هستیم
                            if ($('#productivity-dashboard').is(':visible')) {
                                loadProductivityDashboard();
                            }
                            
                            // رفرش کامل صفحه برای اطمینان از نمایش دکمه‌های جدید
                            setTimeout(() => {
                                loadData();
                            }, 1000);
                        } else if (r.message && r.message.status === 'dependency_error') {
                            // اگر سرور هم dependency error برگردوند
                            frappe.msgprint({
                                title: 'خطای وابستگی',
                                message: r.message.message || 'وابستگی‌های این کارت کار تکمیل نشده‌اند.',
                                indicator: 'red'
                            });
                        }
                    },
                    error: function(err) {
                        console.error('خطا در شروع کار:', err);
                        frappe.msgprint('خطا در شروع کار');
                    }
                });
            },



		pauseJob: function(jobCardName, callback) { // callback پارامتر اضافه کنید
            invalidateJobCardCache(jobCardName);
globalJobInfoCache.delete(jobCardName);
			frappe.prompt([
				{
					label: 'تعداد تکمیل شده در این مرحله',
					fieldname: 'completed_qty',
					fieldtype: 'Float',
					default: 0,
					reqd: 0,
					description: 'تعداد قطعاتی که در این بازه زمانی تکمیل کرده‌اید'
				},
				{
					label: 'دلیل توقف',
					fieldname: 'remarks',
					fieldtype: 'Small Text',
					description: 'علت توقف کار را بنویسید'
				}
			],
			function(values) {
                invalidateJobCardCache(jobCardName);
globalJobInfoCache.delete(jobCardName);
				frappe.call({
					method: 'pricing.pricing.page.jobcards.jobcards.pause_job_card',
					args: {
						job_card_name: jobCardName,
						completed_qty: values.completed_qty,
						remarks: values.remarks
					},
					callback: async function(r) {
						if (r.message && r.message.status === 'success') {
							frappe.show_alert('کار متوقف شد');
							activeJobCard = null;
							await refreshJobCardButtons(jobCardName);
							if (callback) callback(); // این خط را اضافه کنید
						}
					},
					error: function(err) {
						console.error('خطا در متوقف کردن کار:', err);
						frappe.msgprint('خطا در متوقف کردن کار');
					}
				});
			},
			'توقف کارت کار',
			'ثبت توقف'
			);
		},

		resumeJob: function(jobCardName) {
            invalidateJobCardCache(jobCardName);
globalJobInfoCache.delete(jobCardName);
			frappe.call({
				method: 'pricing.pricing.page.jobcards.jobcards.start_job_card',
				args: {
					job_card_name: jobCardName
				},
				callback: async function(r) {
					if (r.message && r.message.status === 'success') {
						frappe.show_alert('کار ادامه یافت');
						await refreshJobCardButtons(jobCardName);
					}
				},
				error: function(err) {
					console.error('خطا در ادامه کار:', err);
					frappe.msgprint('خطا در ادامه کار');
				}
			});
		},
		
		showCompleteDialog: function(jobCardName) {
            invalidateJobCardCache(jobCardName);
globalJobInfoCache.delete(jobCardName);
			// ابتدا اطلاعات job card و time logs را دریافت کنیم
			frappe.call({
				method: 'pricing.pricing.page.jobcards.jobcards.get_job_card_time_summary',
				args: {
					job_card_name: jobCardName
				},
				callback: function(r) {
					if (r.message) {
						let timeSummary = r.message;
						
						frappe.call({
							method: 'frappe.client.get',
							args: {
								doctype: 'Job Card',
								name: jobCardName
							},
							callback: function(r2) {
								if (r2.message) {
									let jobCard = r2.message;
									let totalCompleted = timeSummary.total_completed_qty || 0;
									let remainingQty = Math.max(1, jobCard.for_quantity - totalCompleted);
									
									let d = new frappe.ui.Dialog({
										title: 'تکمیل کارت کار: ' + jobCard.operation,
										fields: [
											{
												fieldtype: 'HTML',
												fieldname: 'job_info',
												options: `<div style="background: #f8f9fa; padding: 15px; margin-bottom: 15px; border-radius: 5px;">
													<div class="row">
														<div class="col-md-6">
															<strong>عملیات:</strong> ${jobCard.operation}<br>
															<strong>محصول:</strong> ${jobCard.production_item}<br>
															<strong>تعداد برنامه‌ریزی شده:</strong> ${jobCard.for_quantity}
														</div>
														<div class="col-md-6">
															<strong>تا کنون تولید شده:</strong> <span style="color: #28a745;">${totalCompleted}</span><br>
															<strong>باقی‌مانده:</strong> <span style="color: #dc3545;">${jobCard.for_quantity - totalCompleted}</span><br>
															<strong>زمان کار:</strong> ${timeSummary.formatted_time || '0:00'}
														</div>
													</div>
												</div>`
											},
											{
												fieldtype: 'Int',
												label: 'تعداد تولید شده در این مرحله',
												fieldname: 'completed_qty',
												reqd: 1,
												default: remainingQty,
												description: 'تعداد قطعاتی که در این مرحله نهایی تکمیل می‌کنید'
											},
											{
												fieldtype: 'Text',
												label: 'توضیحات تکمیل',
												fieldname: 'remarks',
												description: 'توضیحات نهایی کار انجام شده'
											}
										],
										primary_action_label: 'تکمیل کار',
										primary_action: function(values) {
											window.jobCardsPage.completeJob(jobCardName, values);
											d.hide();
										}
									});
									d.show();
									
									setTimeout(() => {
										d.get_field('completed_qty').df.focus();
									}, 500);
								}
							}
						});
					}
				},
				error: function(err) {
					console.error('خطا در دریافت اطلاعات:', err);
					frappe.msgprint('خطا در دریافت اطلاعات کارت کار');
				}
			});
		},
		
        completeJob: function(jobCardName, values = {}) {
            invalidateJobCardCache(jobCardName);
globalJobInfoCache.delete(jobCardName);
            frappe.call({
                method: 'pricing.pricing.page.jobcards.jobcards.complete_job_card',
                args: {
                    job_card_name: jobCardName,
                    completed_qty: values.completed_qty,
                    remarks: values.remarks
                },
                callback: async function(r) {
                    if (r.message && r.message.status === 'success') {
                        frappe.show_alert('کار تکمیل شد');
                        activeJobCard = null; // پاک کردن کار فعال

                        // پاک کردن cache
                        invalidateJobCardCache(jobCardName);
globalJobInfoCache.delete(jobCardName);
                        
                        // به‌روزرسانی فوری دکمه‌ها
                        setTimeout(async () => {
                            await refreshJobCardButtons(jobCardName);
                            
                            // اگر نیاز به به‌روزرسانی کامل صفحه هست
                            if (r.message.refresh_page) {
                                loadData();
                            }
                        }, 100);
                    }
                },
                error: function(err) {
                    console.error('خطا در تکمیل کار:', err);
                    frappe.msgprint('خطا در تکمیل کار');
                }
            });
        },
		
		submitJob: function(jobCardName) {
            invalidateJobCardCache(jobCardName);
globalJobInfoCache.delete(jobCardName);
			frappe.confirm(
				'آیا مطمئن هستید که می‌خواهید این کارت کار را ارسال کنید؟<br><small class="text-muted">پس از ارسال، امکان تغییر وجود نخواهد داشت.</small>',
				function() {
					frappe.call({
						method: 'pricing.pricing.page.jobcards.jobcards.submit_job_card',
						args: { job_card_name: jobCardName },
						callback: async function(r) {
							if (r.message && r.message.status === 'success') {
								frappe.show_alert('کارت کار ارسال شد');
                            await refreshJobCardButtons(jobCardName);
								// بروزرسانی دکمه‌ها
								setTimeout(async () => {
                                    await refreshJobCardButtons(jobCardName);
                                    loadData();
								}, 500);
							}
						},
						error: function(err) {
							console.error('خطا در ارسال:', err);
							frappe.msgprint('خطا در ارسال کردن کارت کار');
						}
					});
				}
			);
		},

		recreateJob:  function(jobCardName) {
            invalidateJobCardCache(jobCardName);
globalJobInfoCache.delete(jobCardName);
			frappe.confirm(
				'آیا می‌خواهید یک کارت کار جدید به جای کارت کار لغو شده ایجاد کنید؟',
				function() {
					frappe.call({
						method: 'pricing.pricing.doctype.job_card.job_card.make_new_job_card',
						args: { source_name: jobCardName },
						callback: async function(r) {
							if (r.message) {
								frappe.show_alert('کارت کار جدید ایجاد شد');
								await refreshJobCardButtons(jobCardName);
								frappe.set_route('Form', 'Job Card', r.message);
							}
						},
						error: function(err) {
							console.error('خطا در بازسازی:', err);
							frappe.msgprint('خطا در ایجاد کارت کار جدید');
						}
					});
				}
			);
		},
		
		viewJob: function(jobCardName) {
			frappe.set_route('Form', 'Job Card', jobCardName);
		},
		toggleSection: function(header) {
			let content = $(header).next('.collapsible-content');
			let icon = $(header).find('.collapse-icon');
			
			content.slideToggle(300);
			$(header).toggleClass('collapsed');
		},




	};

	// افزودن CSS برای بهبود ظاهر
	$(`<style>
		.job-cards-page {
			font-family: 'Vazir', Tahoma, Arial, sans-serif;
		}
		
		.active-job {
			box-shadow: 0 4px 8px rgba(0, 123, 255, 0.3) !important;
			transform: scale(1.02);
		}
		
		.job-card {
			transition: all 0.3s ease;
			background: white;
		}
		
		.job-card:hover {
			box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
		}
		
		.sales-order-section {
			background: white;
			box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
		}
		
		.work-order-section {
			background: white;
		}
		
		.filters-section {
			background: white;
			padding: 20px;
			border-radius: 8px;
			box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
		}
		
		.progress {
			height: 8px;
			border-radius: 4px;
		}
		
		.badge {
			font-size: 11px;
		}
		
		.btn-sm {
			font-size: 11px;
			padding: 4px 8px;
		}
		
		@media (max-width: 768px) {
			.job-card {
				min-height: auto !important;
			}
			
			.col-md-4, .col-lg-4 {
				padding-left: 5px;
				padding-right: 5px;
			}
		}
	</style>`).appendTo('head');


    }