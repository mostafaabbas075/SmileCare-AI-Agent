const API_BASE = "http://localhost:8000/api/v1";

let currentNav = 'nav-today';
let dailyData = null;
let currentTargetDate = null;
let servicesData = [];
let offersData = [];
let usersData = [];

// ── Auth Fetch Wrapper ───────────────────────────────────────────────────────
async function adminFetch(url, options = {}) {
    const token = localStorage.getItem("access_token");

    if (!token) {
        showLoginModal();
        return { ok: false, status: 401 };
    }

    options.headers = {
        ...options.headers,
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json"
    };

    try {
        const res = await fetch(url, options);

        if (res.status === 401) {
            logoutUser(false);
            alert("انتهت صلاحية جلسة الدخول. يرجى تسجيل الدخول مجدداً.");
            showLoginModal();
            return res;
        }

        return res;
    } catch (e) {
        console.error("Network Fetch Error:", e);
        return { ok: false, status: 500 };
    }
}

// ── Authentication & Session Management ─────────────────────────────────────
function showLoginModal() {
    const loginModal = document.getElementById("login-modal");
    if (loginModal) {
        loginModal.classList.remove("hidden");
        loginModal.classList.add("flex");
    }
}

async function loginUser(username, password, clinicSlug = 'main-clinic') {
    try {
        const res = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                clinic_slug: clinicSlug, 
                username: username, 
                password: password 
            })
        });

        const data = await res.json();
        if (res.ok) {
            localStorage.setItem("access_token", data.access_token);
            localStorage.setItem("user_name", data.full_name);
            localStorage.setItem("user_role", data.role);
            localStorage.setItem("clinic_id", data.clinic_id);
            localStorage.setItem("clinic_name", data.clinic_name);
            localStorage.setItem("clinic_slug", clinicSlug);

            alert(`أهلاً بك يا ${data.full_name}! 👋\nعيادة: ${data.clinic_name}`);
            
            const loginModal = document.getElementById("login-modal");
            if (loginModal) {
                loginModal.classList.add("hidden");
                loginModal.classList.remove("flex");
            }
            
            window.location.reload();
        } else {
            alert(data.detail || "اسم المستخدم أو كلمة السر أو معرف العيادة غير صحيح.");
        }
    } catch (e) {
        alert("تعذر الاتصال بالخادم. تأكد من تشغيل الباك إند.");
    }
}

function logoutUser(reload = true) {
    localStorage.removeItem("access_token");
    localStorage.removeItem("user_name");
    localStorage.removeItem("user_role");
    localStorage.removeItem("clinic_id");
    localStorage.removeItem("clinic_name");
    localStorage.removeItem("clinic_slug");
    if (reload) {
        window.location.reload();
    }
}

// ── Navigation Switcher ──────────────────────────────────────────────────────
function navSwitch(secId) {
    currentNav = secId;
    document.querySelectorAll('.nav-section').forEach(el => el.classList.add('hidden'));
    document.querySelectorAll('.sidebar-btn').forEach(el => el.classList.remove('active', 'text-white'));

    const targetSec = document.getElementById(secId);
    if (targetSec) targetSec.classList.remove('hidden');

    const targetBtn = document.getElementById('btn-' + secId);
    if (targetBtn) targetBtn.classList.add('active', 'text-white');

    loadCurrentView();
}

function loadCurrentView() {
    if (!localStorage.getItem("access_token")) {
        showLoginModal();
        return;
    }

    // تحديث بيانات الهوية في الشريط العلوي والجانبي
    const clinicName = localStorage.getItem("clinic_name");
    const clinicSlug = localStorage.getItem("clinic_slug");
    const userName = localStorage.getItem("user_name");
    const userRole = localStorage.getItem("user_role");

    const sidebarNameElem = document.getElementById("sidebar-clinic-name");
    const sidebarSlugElem = document.getElementById("sidebar-clinic-slug");
    const userDisplayElem = document.getElementById("current-user-display");

    if (sidebarNameElem && clinicName) sidebarNameElem.innerText = clinicName;
    if (sidebarSlugElem && clinicSlug) sidebarSlugElem.innerText = `معرف: ${clinicSlug}`;
    if (userDisplayElem && userName) userDisplayElem.innerText = `${userName} (${userRole || 'Admin'})`;

    if (currentNav === 'nav-today') fetchDailyAppointments(currentTargetDate);
    if (currentNav === 'nav-history') fetchHistory();
    if (currentNav === 'nav-patients') fetchPatients();
    if (currentNav === 'nav-services') { fetchServices(); fetchOffers(); }
    if (currentNav === 'nav-settings') fetchClinicSettings();
    if (currentNav === 'nav-users') fetchUsers();
}

// 1. Fetch Daily Appointments
async function fetchDailyAppointments(targetDateStr = null) {
    try {
        let url = `${API_BASE}/admin/appointments/daily`;
        if (targetDateStr) url += `?target_date=${targetDateStr}`;

        const res = await adminFetch(url);
        if (!res.ok) return;
        dailyData = await res.json();

        currentTargetDate = dailyData.target_date;
        renderDailyHeaderAndStats();
        renderDailyTable();
    } catch (err) {
        console.error("Error loading daily appointments:", err);
    }
}

function renderDailyHeaderAndStats() {
    const displayElem = document.getElementById('display-date-str');
    if (displayElem) displayElem.innerText = `${dailyData.day_of_week} - ${dailyData.target_date}`;

    const isWorking = dailyData.is_working_day;
    const badge = document.getElementById('working-day-badge');
    const banner = document.getElementById('closed-banner');

    if (badge && banner) {
        if (isWorking) {
            badge.innerText = "يوم عمل نشط 🟢";
            badge.className = "px-3 py-1 rounded-lg text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30";
            banner.classList.add('hidden');
        } else {
            badge.innerText = "العيادة مغلقة 🔴";
            badge.className = "px-3 py-1 rounded-lg text-xs font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30";
            banner.classList.remove('hidden');
        }
    }

    const st = dailyData.stats;
    const cap = dailyData.capacity;
    if (document.getElementById('stat-total')) {
        document.getElementById('stat-total').innerText = st.total;
        document.getElementById('stat-pending').innerText = st.pending;
        document.getElementById('stat-arrived').innerText = st.arrived;
        document.getElementById('stat-completed').innerText = st.completed;
        document.getElementById('stat-cancelled').innerText = st.cancelled;
        document.getElementById('stat-noshow').innerText = st.no_show;
        document.getElementById('stat-capacity').innerText = `${cap.booked_count} / ${cap.daily_capacity} (${cap.remaining_capacity} متبقي)`;
    }
}

function renderDailyTable() {
    const tbody = document.getElementById('today-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (!dailyData || !dailyData.appointments.length) {
        tbody.innerHTML = '<tr><td colspan="8" class="p-6 text-center text-slate-500">لا توجد حجوزات مسجلة لهذا اليوم.</td></tr>';
        return;
    }

    const showCompleted = document.getElementById('show-completed-toggle')?.checked || false;

    const visibleAppointments = dailyData.appointments.filter(a => {
        if (showCompleted) return true;
        return ['pending', 'scheduled', 'confirmed', 'arrived'].includes(a.status);
    });

    if (!visibleAppointments.length) {
        tbody.innerHTML = '<tr><td colspan="8" class="p-6 text-center text-slate-500">تم إكمال/معالجة كافة الحالات النشطة لهذا اليوم! 🎉</td></tr>';
        return;
    }

    visibleAppointments.forEach(a => {
        let statusBadge = 'bg-slate-700 text-slate-300';
        if (['pending', 'scheduled', 'confirmed'].includes(a.status)) statusBadge = 'bg-blue-500/20 text-blue-400 border border-blue-500/30';
        if (a.status === 'arrived') statusBadge = 'bg-purple-500/20 text-purple-300 border border-purple-500/30';
        if (a.status === 'completed') statusBadge = 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30';
        if (a.status === 'cancelled') statusBadge = 'bg-amber-500/20 text-amber-400 border border-amber-500/30';
        if (a.status === 'no_show') statusBadge = 'bg-rose-500/20 text-rose-400 border border-rose-500/30';

        tbody.innerHTML += `
            <tr class="hover:bg-slate-700/30 transition">
                <td class="p-4 font-bold text-white">${a.patient_name}</td>
                <td class="p-4 font-mono text-slate-300">${a.patient_phone}</td>
                <td class="p-4 text-emerald-400 font-medium">${a.service_name}</td>
                <td class="p-4 text-amber-300 font-mono text-[10px] leading-tight max-w-[150px] whitespace-pre-wrap">${a.notes || '—'}</td>
                <td class="p-4 text-slate-300 font-mono">${a.appointment_date}</td>
                <td class="p-4 text-slate-400 font-mono text-[11px]">${a.booked_at}</td>
                <td class="p-4"><span class="px-2 py-1 rounded-lg text-[10px] font-bold ${statusBadge}">${a.status}</span></td>
                <td class="p-4 text-center">
                    <div class="flex items-center justify-center gap-1.5">
                        <button onclick="updateStatusWithConfirm('${a.id}', 'arrived', '${a.patient_name}')" title="وصل العيادة" class="px-2 py-1 bg-purple-600 hover:bg-purple-500 text-white rounded font-bold text-[11px] transition shadow">وصل 🛬</button>
                        <button onclick="updateStatusWithConfirm('${a.id}', 'completed', '${a.patient_name}')" title="إكمال الكشف" class="px-2 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded font-bold text-[11px] transition shadow">تم الكشف ✅</button>
                        <button onclick="updateStatusWithConfirm('${a.id}', 'cancelled', '${a.patient_name}')" title="إلغاء الحجز" class="px-2 py-1 bg-amber-600 hover:bg-amber-500 text-white rounded font-bold text-[11px] transition shadow">إلغاء ❌</button>
                        <button onclick="updateStatusWithConfirm('${a.id}', 'no_show', '${a.patient_name}')" title="غائب" class="px-2 py-1 bg-rose-600 hover:bg-rose-500 text-white rounded font-bold text-[11px] transition shadow">غائب 🚫</button>
                        <button onclick="showAuditModal('${a.id}')" title="سجل التعديلات" class="px-2 py-1 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded font-bold text-[11px] transition shadow">📜</button>
                    </div>
                </td>
            </tr>
        `;
    });
}

function navigateWorkingDay(direction) {
    if (!dailyData) return;
    if (direction === 'prev') fetchDailyAppointments(dailyData.prev_working_day);
    if (direction === 'today') fetchDailyAppointments(dailyData.today_date);
    if (direction === 'next') fetchDailyAppointments(dailyData.next_working_day);
}

function jumpToClosestWorkingDay() {
    if (dailyData && dailyData.closest_future_working_day) {
        fetchDailyAppointments(dailyData.closest_future_working_day);
    }
}

async function updateStatusWithConfirm(apptId, newStatus, patientName) {
    const labels = {
        'arrived': 'تسجيل وصول المريض إلى العيادة؟ 🛬',
        'completed': 'إكمال الكشف لهذا المريض وإخفاؤه من قائمة الانتظار؟ ✅',
        'cancelled': 'إلغاء / تأجيل هذا الحجز؟ ❌',
        'no_show': 'تسجيل المريض كـ (غائب / لم يحضر)؟ 🚫'
    };

    const confirmMsg = `هل أنت متأكد من ${labels[newStatus] || 'تغيير الحالة؟'}\nالمريض: ${patientName}`;
    if (!confirm(confirmMsg)) return;

    try {
        const res = await adminFetch(`${API_BASE}/admin/appointments/${apptId}/status?new_status=${newStatus}`, { method: 'PATCH' });
        if (res.ok) {
            loadCurrentView();
        } else {
            alert("حدث خطأ أثناء تحديث الحالة.");
        }
    } catch (e) {
        alert("حدث خطأ أثناء الاتصال بالخادم.");
    }
}

// 2. Fetch History Log
async function fetchHistory() {
    const dFrom = document.getElementById('hist-date-from')?.value;
    const dTo = document.getElementById('hist-date-to')?.value;
    const dType = document.getElementById('hist-date-type')?.value || "appointment_date";
    const st = document.getElementById('hist-status')?.value || "all";
    const search = document.getElementById('hist-search')?.value.trim() || "";

    try {
        let url = `${API_BASE}/admin/appointments/history?date_type=${dType}&status_filter=${st}&search=${search}`;
        if (dFrom) url += `&date_from=${dFrom}`;
        if (dTo) url += `&date_to=${dTo}`;

        const res = await adminFetch(url);
        if (!res.ok) return;
        const data = await res.json();

        const tbody = document.getElementById('history-tbody');
        if (!tbody) return;
        tbody.innerHTML = '';

        if (!data.length) {
            tbody.innerHTML = '<tr><td colspan="8" class="p-6 text-center text-slate-500">لا توجد سجلات مطابقة للبحث.</td></tr>';
            return;
        }

        data.forEach(h => {
            let statusBadge = 'bg-slate-700 text-slate-300';
            if (['pending', 'scheduled', 'confirmed'].includes(h.status)) statusBadge = 'bg-blue-500/20 text-blue-400 border border-blue-500/30';
            if (h.status === 'arrived') statusBadge = 'bg-purple-500/20 text-purple-300 border border-purple-500/30';
            if (h.status === 'completed') statusBadge = 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30';
            if (h.status === 'cancelled') statusBadge = 'bg-amber-500/20 text-amber-400 border border-amber-500/30';
            if (h.status === 'no_show') statusBadge = 'bg-rose-500/20 text-rose-400 border border-rose-500/30';

            tbody.innerHTML += `
                <tr class="hover:bg-slate-700/30 transition">
                    <td class="p-4 font-bold text-white">${h.patient_name}</td>
                    <td class="p-4 font-mono text-slate-300">${h.patient_phone}</td>
                    <td class="p-4 text-emerald-400 font-medium">${h.service_name}</td>
                    <td class="p-4 text-amber-300 font-mono text-[10px] leading-tight max-w-[150px] whitespace-pre-wrap">${h.notes || '—'}</td>
                    <td class="p-4 text-slate-300 font-mono">${h.appointment_date}</td>
                    <td class="p-4 text-slate-400 font-mono text-[11px]">${h.booked_at}</td>
                    <td class="p-4"><span class="px-2 py-1 rounded-lg text-[10px] font-bold ${statusBadge}">${h.status}</span></td>
                    <td class="p-4 text-center">
                        <button onclick="showAuditModal('${h.id}')" class="px-3 py-1 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded font-bold transition">
                            عرض الـ Timeline 📜
                        </button>
                    </td>
                </tr>
            `;
        });
    } catch (err) { console.error("History fetch error:", err); }
}

async function showAuditModal(apptId) {
    try {
        const res = await adminFetch(`${API_BASE}/admin/appointments/${apptId}/audit-trail`);
        if (!res.ok) return;
        const logs = await res.json();

        const timeline = document.getElementById('audit-timeline');
        if (!timeline) return;
        timeline.innerHTML = '';

        logs.forEach(log => {
            timeline.innerHTML += `
                <div class="p-3 bg-slate-800 rounded-lg border border-slate-700/80">
                    <div class="flex justify-between items-center mb-1">
                        <span class="font-bold text-emerald-400 text-xs">${log.action}</span>
                        <span class="text-[10px] text-slate-500 font-mono">${log.timestamp}</span>
                    </div>
                    <p class="text-xs text-slate-300">${log.details}</p>
                </div>
            `;
        });

        const modal = document.getElementById('audit-modal');
        if (modal) {
            modal.classList.remove('hidden');
            modal.classList.add('flex');
        }
    } catch (e) { alert("تعذر جلب سجل العمليات"); }
}

function closeAuditModal() {
    const modal = document.getElementById('audit-modal');
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }
}

// 3. Patients Management
async function fetchPatients() {
    try {
        const res = await adminFetch(`${API_BASE}/admin/patients?_t=${new Date().getTime()}`);
        if (!res.ok) return;
        const patients = await res.json();

        const navPatientsSec = document.getElementById('nav-patients');
        if (!navPatientsSec) return;

        const nowUtc = new Date();
        const activePatients = [];
        const bannedPatients = [];

        patients.forEach(p => {
            const isManual = p.is_blacklisted === true;
            const isNoShow = p.is_no_show_banned === true || p.no_show_count >= 3 || (p.banned_until && new Date(p.banned_until) > nowUtc);

            if (isManual || isNoShow) {
                bannedPatients.push({ ...p, isManual, isNoShow });
            } else {
                activePatients.push(p);
            }
        });

        navPatientsSec.innerHTML = `
            <div class="space-y-8">
                <!-- 1. Active Patients Table -->
                <div>
                    <div class="flex items-center justify-between mb-4">
                        <h2 class="text-xl font-bold text-white flex items-center gap-2">
                            <span>المرضى النشطون 🟢</span>
                            <span class="text-xs font-mono bg-emerald-500/20 text-emerald-400 px-2.5 py-0.5 rounded-full border border-emerald-500/30 font-bold">${activePatients.length}</span>
                        </h2>
                    </div>
                    <div class="overflow-x-auto bg-slate-800/80 rounded-xl border border-slate-700/80 shadow-xl">
                        <table class="w-full text-right text-sm">
                            <thead class="bg-slate-900/60 text-slate-400 font-bold border-b border-slate-700">
                                <tr>
                                    <th class="p-4">اسم المريض</th>
                                    <th class="p-4">رقم الهاتف</th>
                                    <th class="p-4 text-center">عدد مرات الغياب</th>
                                    <th class="p-4">الحالة</th>
                                    <th class="p-4 text-center">الإجراءات</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-slate-700/50">
                                ${activePatients.length === 0 ? `
                                    <tr><td colspan="5" class="p-6 text-center text-slate-500">لا يوجد مرضى نشطون حالياً.</td></tr>
                                ` : activePatients.map(p => `
                                    <tr class="hover:bg-slate-700/30 transition">
                                        <td class="p-4 font-bold text-white">${p.name}</td>
                                        <td class="p-4 font-mono text-slate-300">${p.phone}</td>
                                        <td class="p-4 text-amber-400 font-bold font-mono text-center">${p.no_show_count}</td>
                                        <td class="p-4"><span class="px-2.5 py-1 bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-lg text-xs font-bold">نشط 🟢</span></td>
                                        <td class="p-4 text-center">
                                            <button onclick="toggleBlacklist('${p.id}', true)" title="إضافة المريض للبلاك ليست" class="px-3 py-1.5 bg-rose-900/70 hover:bg-rose-800 text-rose-200 border border-rose-700 rounded-lg text-xs font-bold transition shadow">حظر يدوي 🚫</button>
                                        </td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- 2. Blacklisted Patients Table -->
                <div>
                    <div class="flex items-center justify-between mb-4">
                        <h2 class="text-xl font-bold text-rose-400 flex items-center gap-2">
                            <span>قائمة المحظورين والبلاك ليست 🚫</span>
                            <span class="text-xs font-mono bg-rose-500/20 text-rose-400 px-2.5 py-0.5 rounded-full border border-rose-500/30 font-bold">${bannedPatients.length}</span>
                        </h2>
                    </div>
                    <div class="overflow-x-auto bg-slate-800/80 rounded-xl border border-rose-900/40 shadow-xl">
                        <table class="w-full text-right text-sm">
                            <thead class="bg-rose-950/50 text-rose-300 font-bold border-b border-rose-900/40">
                                <tr>
                                    <th class="p-4">اسم المريض</th>
                                    <th class="p-4">رقم الهاتف</th>
                                    <th class="p-4 text-center">عدد مرات الغياب</th>
                                    <th class="p-4">سبب الحظر</th>
                                    <th class="p-4 text-center">الإجراءات</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-slate-700/50">
                                ${bannedPatients.length === 0 ? `
                                    <tr><td colspan="5" class="p-6 text-center text-slate-500">قائمة الحظر فارغة حالياً. 🎉</td></tr>
                                ` : bannedPatients.map(p => {
                                    let statusBadge = '';
                                    if (p.isManual && p.isNoShow) {
                                        statusBadge = '<span class="px-2.5 py-1 bg-rose-500/20 text-rose-400 border border-rose-500/30 rounded-lg text-xs font-bold">محظور (يدوي + غياب) ⛔</span>';
                                    } else if (p.isManual) {
                                        statusBadge = '<span class="px-2.5 py-1 bg-rose-500/20 text-rose-400 border border-rose-500/30 rounded-lg text-xs font-bold">محظور يدوي (بلاك ليست) 🚫</span>';
                                    } else {
                                        statusBadge = '<span class="px-2.5 py-1 bg-amber-500/20 text-amber-400 border border-amber-500/30 rounded-lg text-xs font-bold">محظور لتكرار الغياب ⚠️</span>';
                                    }

                                    const unbanBtn = p.isManual
                                        ? `<button onclick="toggleBlacklist('${p.id}', false)" title="فك الحظر اليدوي" class="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-bold transition shadow">فك البلاك ليست 🔓</button>`
                                        : '';

                                    const resetBtn = p.no_show_count > 0 || p.isNoShow
                                        ? `<button onclick="resetNoShowCount('${p.id}')" title="تصفير عداد الغياب" class="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-bold transition shadow">تصفير الغياب 🔄</button>`
                                        : '';

                                    return `
                                        <tr class="hover:bg-rose-950/20 transition">
                                            <td class="p-4 font-bold text-white">${p.name}</td>
                                            <td class="p-4 font-mono text-slate-300">${p.phone}</td>
                                            <td class="p-4 text-amber-400 font-bold font-mono text-center">${p.no_show_count}</td>
                                            <td class="p-4">${statusBadge}</td>
                                            <td class="p-4 text-center">
                                                <div class="flex items-center justify-center gap-2">
                                                    ${unbanBtn}
                                                    ${resetBtn}
                                                </div>
                                            </td>
                                        </tr>
                                    `;
                                }).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        `;
    } catch (e) {
        console.error("Error fetching patients:", e);
    }
}

async function toggleBlacklist(pId, shouldBlock) {
    const actionText = shouldBlock ? "إضافة المريض للبلاك ليست ونقله لقائمة الحظر" : "فك الحظر عن المريض وإعادته للنشطين";
    if (!confirm(`هل أنت متأكد من ${actionText}؟`)) return;

    try {
        const res = await adminFetch(`${API_BASE}/admin/patients/${pId}/blacklist?is_blacklisted=${shouldBlock}`, { 
            method: 'PATCH' 
        });

        if (res.ok) {
            await fetchPatients();
        } else {
            alert("حدث خطأ أثناء تغيير حالة الحظر اليدوي.");
        }
    } catch (e) { 
        alert("تعذر الاتصال بالخادم."); 
    }
}

async function resetNoShowCount(pId) {
    if (!confirm("هل أنت متأكد من تصفير عداد الغياب لهذا المريض؟")) return;
    try {
        const res = await adminFetch(`${API_BASE}/admin/patients/${pId}/reset-no-show?new_count=0`, { method: 'PATCH' });
        if (res.ok) await fetchPatients();
    } catch (e) { alert("تعذر الاتصال بالخادم."); }
}

// 4. Services & Offers CRUD
async function fetchServices() {
    try {
        const res = await adminFetch(`${API_BASE}/admin/services`);
        if (!res.ok) return;
        servicesData = await res.json();
        renderServicesTable();
    } catch (e) { console.error("Fetch services error:", e); }
}

function renderServicesTable() {
    const tbody = document.getElementById('services-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (!servicesData.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="p-6 text-center text-slate-500">لا توجد خدمات مضافة حالياً. اضغط "إضافة خدمة جديدة".</td></tr>';
        return;
    }

    servicesData.forEach(s => {
        const activeBadge = s.is_active ? 
            '<span class="px-2 py-1 bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-lg font-bold">مفعلة</span>' : 
            '<span class="px-2 py-1 bg-rose-500/20 text-rose-400 border border-rose-500/30 rounded-lg font-bold">معطلة</span>';

        tbody.innerHTML += `
            <tr class="hover:bg-slate-700/30 transition">
                <td class="p-4 font-bold text-white">${s.name}</td>
                <td class="p-4 text-slate-400 max-w-xs truncate">${s.description || '—'}</td>
                <td class="p-4 font-bold text-emerald-400 font-mono">${s.price} ج.م</td>
                <td class="p-4 text-slate-300 font-mono">${s.duration} دقيقة</td>
                <td class="p-4">${activeBadge}</td>
                <td class="p-4 text-center">
                    <div class="flex items-center justify-center gap-2">
                        <button onclick="openEditServiceModal('${s.id}')" title="تعديل السعر والبيانات" class="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-bold transition">
                            تعديل ✏️
                        </button>
                        <button onclick="toggleServiceActive('${s.id}')" title="تفعيل/تعطيل" class="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded-lg font-bold border border-slate-600 transition">
                            ${s.is_active ? 'تعطيل ⏸️' : 'تفعيل 🟢'}
                        </button>
                        <button onclick="deleteService('${s.id}', '${s.name}')" title="حذف الخدمة" class="px-3 py-1.5 bg-rose-900/60 hover:bg-rose-800 text-rose-200 rounded-lg font-bold border border-rose-700 transition">
                            حذف 🗑️
                        </button>
                    </div>
                </td>
            </tr>
        `;
    });
}

// ── Offers Management Integration
async function fetchOffers() {
    try {
        const res = await adminFetch(`${API_BASE}/admin/offers`);
        if (!res.ok) return;
        offersData = await res.json();
        renderOffersSection();
    } catch (e) { console.error("Error fetching offers:", e); }
}

function renderOffersSection() {
    const navServicesSec = document.getElementById('nav-services');
    if (!navServicesSec) return;

    let offersWrapper = document.getElementById('offers-wrapper-sec');
    if (!offersWrapper) {
        offersWrapper = document.createElement('div');
        offersWrapper.id = 'offers-wrapper-sec';
        offersWrapper.className = 'mt-10 pt-8 border-t border-slate-700/80';
        navServicesSec.appendChild(offersWrapper);
    }

    offersWrapper.innerHTML = `
        <div class="flex items-center justify-between mb-4">
            <h2 class="text-xl font-bold text-amber-400 flex items-center gap-2">
                <span>إدارة العروض والخصومات الخاصة 🎁</span>
                <span class="text-xs font-mono bg-amber-500/20 text-amber-400 px-2.5 py-0.5 rounded-full border border-amber-500/30 font-bold">${offersData.length}</span>
            </h2>
            <button onclick="promptCreateOffer()" class="px-4 py-2 bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400 text-white rounded-xl text-xs font-bold transition shadow-lg flex items-center gap-1.5">
                <span>إضافة عرض/خصم جديد ➕</span>
            </button>
        </div>
        <div class="overflow-x-auto bg-slate-800/80 rounded-xl border border-amber-900/30 shadow-xl">
            <table class="w-full text-right text-sm">
                <thead class="bg-amber-950/30 text-amber-300 font-bold border-b border-amber-900/30">
                    <tr>
                        <th class="p-4">عنوان العرض</th>
                        <th class="p-4">الخدمة المتعلقة</th>
                        <th class="p-4">السعر الأصلي</th>
                        <th class="p-4">السعر بعد الخصم</th>
                        <th class="p-4">الحالة</th>
                        <th class="p-4 text-center">الإجراءات</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-slate-700/50">
                    ${offersData.length === 0 ? `
                        <tr><td colspan="6" class="p-6 text-center text-slate-500">لا توجد عروض أو خصومات مضافة حالياً. البوت سيخبر المرضى بعدم وجود عروض.</td></tr>
                    ` : offersData.map(o => `
                        <tr class="hover:bg-amber-950/10 transition">
                            <td class="p-4 font-bold text-white">${o.title}</td>
                            <td class="p-4 text-slate-300">${o.service_name || 'كشف عام'}</td>
                            <td class="p-4 font-mono text-slate-400 line-through">${o.original_price} ج.م</td>
                            <td class="p-4 font-mono text-amber-400 font-bold">${o.offer_price} ج.م</td>
                            <td class="p-4">${o.is_active ? '<span class="px-2 py-1 bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-lg text-xs font-bold">مفعل 🟢</span>' : '<span class="px-2 py-1 bg-rose-500/20 text-rose-400 border border-rose-500/30 rounded-lg text-xs font-bold">معطل ⏸️</span>'}</td>
                            <td class="p-4 text-center">
                                <div class="flex items-center justify-center gap-2">
                                    <button onclick="toggleOfferActive('${o.id}')" class="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded-lg text-xs font-bold transition">
                                        ${o.is_active ? 'تعطيل ⏸️' : 'تفعيل 🟢'}
                                    </button>
                                    <button onclick="deleteOffer('${o.id}')" class="px-3 py-1.5 bg-rose-900/60 hover:bg-rose-800 text-rose-200 rounded-lg text-xs font-bold transition">
                                        حذف 🗑️
                                    </button>
                                </div>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
}

async function promptCreateOffer() {
    const title = prompt("أدخل عنوان العرض (مثال: عرض كشف الأسنان الشامل):");
    if (!title) return;

    const serviceName = prompt("اسم الخدمة المتعلقة بالعرض (مثال: كشف أسنان):", "كشف أسنان") || "كشف أسنان";
    const originalPrice = parseFloat(prompt("السعر الأصلي للخدمة قبل الخصم (ج.م):", "900"));
    if (isNaN(originalPrice)) return;

    const offerPrice = parseFloat(prompt("السعر بعد الخصم (ج.م):", "700"));
    if (isNaN(offerPrice)) return;

    const description = prompt("وصف مختصر للعرض (اختياري):", "خصم خاص لفترة محدودة") || "";

    try {
        const res = await adminFetch(`${API_BASE}/admin/offers`, {
            method: 'POST',
            body: JSON.stringify({
                title,
                service_name: serviceName,
                original_price: originalPrice,
                offer_price: offerPrice,
                description
            })
        });

        if (res.ok) {
            alert("تم إضافة العرض بنجاح! 🎉 البوت سيخبر به المرضى فوراً.");
            fetchOffers();
        }
    } catch (e) { alert("حدث خطأ أثناء إضافة العرض."); }
}

async function toggleOfferActive(offerId) {
    try {
        const res = await adminFetch(`${API_BASE}/admin/offers/${offerId}/toggle-active`, { method: 'PATCH' });
        if (res.ok) fetchOffers();
    } catch (e) { alert("تعذر تغيير حالة العرض."); }
}

async function deleteOffer(offerId) {
    if (!confirm("هل أنت متأكد من حذف هذا العرض نهائياً؟")) return;
    try {
        const res = await adminFetch(`${API_BASE}/admin/offers/${offerId}`, { method: 'DELETE' });
        if (res.ok) fetchOffers();
    } catch (e) { alert("تعذر حذف العرض."); }
}

function openServiceModal() {
    document.getElementById('service-id').value = '';
    document.getElementById('service-name').value = '';
    document.getElementById('service-description').value = '';
    document.getElementById('service-price').value = '';
    document.getElementById('service-duration').value = '30';
    document.getElementById('service-modal-title').innerText = '➕ إضافة خدمة جديدة';

    const modal = document.getElementById('service-modal');
    if (modal) {
        modal.classList.remove('hidden');
        modal.classList.add('flex');
    }
}

function openEditServiceModal(serviceId) {
    const service = servicesData.find(s => s.id === serviceId);
    if (!service) return;

    document.getElementById('service-id').value = service.id;
    document.getElementById('service-name').value = service.name;
    document.getElementById('service-description').value = service.description || '';
    document.getElementById('service-price').value = service.price;
    document.getElementById('service-duration').value = service.duration;
    document.getElementById('service-modal-title').innerText = '✏️ تعديل بيانات الخدمة';

    const modal = document.getElementById('service-modal');
    if (modal) {
        modal.classList.remove('hidden');
        modal.classList.add('flex');
    }
}

function closeServiceModal() {
    const modal = document.getElementById('service-modal');
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }
}

async function saveService(event) {
    event.preventDefault();

    const serviceId = document.getElementById('service-id').value;
    const name = document.getElementById('service-name').value.trim();
    const description = document.getElementById('service-description').value.trim();
    const price = parseFloat(document.getElementById('service-price').value);
    const duration = parseInt(document.getElementById('service-duration').value);

    const payload = { name, description, price, duration };

    try {
        let res;
        if (serviceId) {
            res = await adminFetch(`${API_BASE}/admin/services/${serviceId}`, {
                method: 'PUT',
                body: JSON.stringify(payload)
            });
        } else {
            res = await adminFetch(`${API_BASE}/admin/services`, {
                method: 'POST',
                body: JSON.stringify(payload)
            });
        }

        if (res.ok) {
            closeServiceModal();
            fetchServices();
        } else {
            alert("حدث خطأ أثناء حفظ بيانات الخدمة.");
        }
    } catch (e) { alert("حدث خطأ أثناء الاتصال بالخادم."); }
}

async function toggleServiceActive(serviceId) {
    try {
        const res = await adminFetch(`${API_BASE}/admin/services/${serviceId}/toggle-active`, { method: 'PATCH' });
        if (res.ok) fetchServices();
    } catch (e) { alert("حدث خطأ أثناء التعديل"); }
}

async function deleteService(serviceId, serviceName) {
    if (!confirm(`هل أنت متأكد من حذف خدمة "${serviceName}" نهائياً؟`)) return;

    try {
        const res = await adminFetch(`${API_BASE}/admin/services/${serviceId}`, { method: 'DELETE' });
        if (res.ok) fetchServices();
    } catch (e) { alert("حدث خطأ في الخادم."); }
}

// 5. Clinic Settings Fetch & Save
async function fetchClinicSettings() {
    try {
        const res = await adminFetch(`${API_BASE}/admin/clinic/config`);
        if (!res.ok) return;
        const cfg = await res.json();

        // أيام العمل
        const checkboxes = document.querySelectorAll('input[name="cfg-working-day"]');
        checkboxes.forEach(cb => {
            cb.checked = cfg.working_days_indices.includes(parseInt(cb.value));
        });

        // ساعات العمل والسعة والتوقيت
        if (document.getElementById('cfg-daily-capacity')) {
            document.getElementById('cfg-daily-capacity').value = cfg.daily_capacity;
            if (document.getElementById('cfg-opening-time')) document.getElementById('cfg-opening-time').value = cfg.opening_time || "16:00";
            if (document.getElementById('cfg-closing-time')) document.getElementById('cfg-closing-time').value = cfg.closing_time || "22:00";
            document.getElementById('cfg-timezone').value = cfg.timezone;

            const pol = cfg.no_show_policy;
            document.getElementById('cfg-ban-1').value = pol[1] ? pol[1].ban_days : 0;
            document.getElementById('cfg-ban-2').value = pol[2] ? pol[2].ban_days : 7;
            document.getElementById('cfg-ban-3').value = pol[3] ? pol[3].ban_days : 30;
            document.getElementById('cfg-ban-4').value = pol[4] ? pol[4].ban_days : 365;
        }

    } catch (e) { console.error("Error fetching clinic settings:", e); }
}

async function saveClinicSettings(event) {
    event.preventDefault();

    const workingDays = [];
    document.querySelectorAll('input[name="cfg-working-day"]:checked').forEach(cb => {
        workingDays.push(parseInt(cb.value));
    });

    if (!workingDays.length) {
        alert("يرجى اختيار يوم عمل واحد على الأقل للعيادة.");
        return;
    }

    const payload = {
        working_days: workingDays,
        daily_capacity: parseInt(document.getElementById('cfg-daily-capacity').value),
        opening_time: document.getElementById('cfg-opening-time')?.value || "16:00",
        closing_time: document.getElementById('cfg-closing-time')?.value || "22:00",
        timezone: document.getElementById('cfg-timezone').value.trim(),
        ban_days_first_noshow: parseInt(document.getElementById('cfg-ban-1').value),
        ban_days_second_noshow: parseInt(document.getElementById('cfg-ban-2').value),
        ban_days_third_noshow: parseInt(document.getElementById('cfg-ban-3').value),
        ban_days_repeated_noshow: parseInt(document.getElementById('cfg-ban-4').value),
    };

    try {
        const res = await adminFetch(`${API_BASE}/admin/clinic/config`, {
            method: 'PUT',
            body: JSON.stringify(payload)
        });

        if (res.ok) {
            alert("تم حفظ إعدادات ومواعيد العيادة بنجاح! 🎉");
            fetchClinicSettings();
        } else {
            alert("حدث خطأ أثناء حفظ الإعدادات.");
        }
    } catch (e) {
        alert("تعذر الاتصال بالخادم.");
    }
}

// 6. User Management (Admin Only)
async function fetchUsers() {
    try {
        const res = await adminFetch(`${API_BASE}/admin/users`);
        if (!res.ok) return;
        usersData = await res.json();
        renderUsersTable();
    } catch (e) { console.error("Error fetching users:", e); }
}

function renderUsersTable() {
    const tbody = document.getElementById('users-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (!usersData.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="p-6 text-center text-slate-500">لا يوجد مستخدمون مسجلون.</td></tr>';
        return;
    }

    usersData.forEach(u => {
        tbody.innerHTML += `
            <tr class="hover:bg-slate-700/30 transition">
                <td class="p-4 font-bold text-white">${u.full_name}</td>
                <td class="p-4 font-mono text-slate-300">${u.username}</td>
                <td class="p-4"><span class="px-2 py-1 rounded-lg text-[10px] font-bold bg-blue-500/20 text-blue-400 border border-blue-500/30">${u.role}</span></td>
                <td class="p-4">${u.is_active ? '<span class="text-emerald-400 font-bold">نشط</span>' : '<span class="text-rose-400 font-bold">معطل</span>'}</td>
                <td class="p-4 text-center">
                    <div class="flex items-center justify-center gap-2">
                        <button onclick="promptChangePassword('${u.id}', '${u.username}')" title="تغيير كلمة السر" class="px-3 py-1 bg-amber-600 hover:bg-amber-500 text-white rounded text-xs font-bold transition shadow">
                            تغيير كلمة السر 🔑
                        </button>
                        <button onclick="toggleUserActive('${u.id}')" title="تفعيل/تعطيل" class="px-3 py-1 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded text-xs font-bold transition shadow">
                            ${u.is_active ? 'تعطيل ⏸️' : 'تفعيل 🟢'}
                        </button>
                        <button onclick="deleteUser('${u.id}', '${u.username}')" title="حذف الحساب نهائياً" class="px-3 py-1 bg-rose-900/60 hover:bg-rose-800 text-rose-200 rounded text-xs font-bold border border-rose-700 transition shadow">
                            حذف 🗑️
                        </button>
                    </div>
                </td>
            </tr>
        `;
    });
}

async function promptChangePassword(userId, username) {
    const newPass = prompt(`أدخل كلمة السر الجديدة للمستخدم: (${username})`);
    if (!newPass) return;

    try {
        const res = await adminFetch(`${API_BASE}/admin/users/${userId}/change-password`, {
            method: 'POST',
            body: JSON.stringify({ new_password: newPass })
        });
        const data = await res.json();
        alert(data.message || "تم تغيير كلمة السر بنجاح.");
    } catch (e) { alert("حدث خطأ أثناء تغيير كلمة السر."); }
}

async function toggleUserActive(userId) {
    try {
        const res = await adminFetch(`${API_BASE}/admin/users/${userId}/toggle-active`, { method: 'PATCH' });
        if (res.ok) fetchUsers();
    } catch (e) { alert("حدث خطأ في التعديل."); }
}

async function deleteUser(userId, username) {
    if (!confirm(`هل أنت متأكد من حذف حساب "${username}" نهائياً من النظام؟\nلا يمكن التراجع عن هذا الإجراء.`)) return;

    try {
        const res = await adminFetch(`${API_BASE}/admin/users/${userId}`, { method: 'DELETE' });
        const data = await res.json();
        
        if (res.ok) {
            alert(data.message || "تم حذف الحساب بنجاح.");
            fetchUsers();
        } else {
            alert(data.detail || "حدث خطأ أثناء حذف الحساب.");
        }
    } catch (e) {
        alert("تعذر الاتصال بالخادم.");
    }
}

// ── Initial Load Control ─────────────────────────────────────────────────────
if (localStorage.getItem("access_token")) {
    loadCurrentView();
} else {
    showLoginModal();
}