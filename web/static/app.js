/* === 애견미용샵 예약관리 웹앱 === */

const App = (() => {
    // 상태
    let currentYear, currentMonth;
    let selectedDate = null;
    let monthData = { counts: {}, names: {} };
    let currentView = 'calendar';
    let pendingSlotTime = null; // 빈슬롯 클릭 시 선택된 시간
    let pendingSlotCustomer = null;
    let searchTimer = null;
    let callSidebarDate = null;
    // 북킹모드: 고객 선택 후 날짜→빈슬롯 클릭으로 예약
    let bookingMode = null; // { customer: {...} } or null
    // 이동모드: 기존 예약의 날짜/시간 변경
    let moveMode = null; // { reservationId, petName } or null
    // 통합 상세: 현재 열려 있는 activeRes ID (메모 저장 후 복원용)
    let _unifiedActiveResId = null;
    // 매출관리
    let salesYear, salesMonth;
    let salesData = null;

    function isPC() { return window.innerWidth >= 900; }

    const WEEKDAYS_KR = ['일','월','화','수','목','금','토'];
    const STATUS_LABEL = { confirmed: '🕐 예약', completed: '✅ 완료', cancelled: '❌ 취소', no_show: '⚠️ 노쇼' };

    // ==================== 초기화 ====================

    function init() {
        const now = new Date();
        currentYear = now.getFullYear();
        currentMonth = now.getMonth() + 1;
        setupSwipe();
        if (isPC()) {
            startClock();
            // PC: 캘린더만 표시, 타임라인/수신기록 숨김
            document.getElementById('timelineSection').style.display = 'none';
            document.getElementById('callSidebar').style.display = 'none';
            goToday();
            loadBridgeStatus();
            loadGoogleStatus();
            // 자동 DB 백업 (로딩 후 2초 뒤)
            setTimeout(_tryAutoBackup, 2000);
        } else {
            loadMonth();
        }
    }

    // ==================== 자동 DB 백업 (File System Access API) ====================

    let _backupDirHandle = null;

    async function _tryAutoBackup() {
        if (!isPC()) return;
        if (!('showDirectoryPicker' in window)) return;

        const today = new Date().toISOString().slice(0, 10);
        const lastBackup = localStorage.getItem('lastBackupDate');
        if (lastBackup === today) return; // 오늘 이미 백업함

        // 저장된 디렉토리 핸들이 있는지 확인
        if (_backupDirHandle) {
            // 권한 확인
            const perm = await _backupDirHandle.queryPermission({ mode: 'readwrite' });
            if (perm === 'granted') {
                await _doAutoBackup();
                return;
            }
        }

        // IndexedDB에서 핸들 복원 시도
        try {
            const handle = await _getStoredDirHandle();
            if (handle) {
                const perm = await handle.queryPermission({ mode: 'readwrite' });
                if (perm === 'granted') {
                    _backupDirHandle = handle;
                    await _doAutoBackup();
                    return;
                }
                // 권한 만료 → 재요청
                const req = await handle.requestPermission({ mode: 'readwrite' });
                if (req === 'granted') {
                    _backupDirHandle = handle;
                    await _doAutoBackup();
                    return;
                }
            }
        } catch (e) { /* 복원 실패 */ }

        // 핸들 없음 → 사용자에게 물어보기
        _showBackupPrompt();
    }

    function _showBackupPrompt() {
        const bar = document.createElement('div');
        bar.className = 'backup-prompt';
        bar.innerHTML = `
            <span>💾 DB 자동백업 폴더를 설정하시겠습니까?</span>
            <button onclick="App.setupBackupFolder()" class="backup-prompt-btn yes">설정</button>
            <button onclick="this.parentElement.remove();localStorage.setItem('lastBackupDate',new Date().toISOString().slice(0,10))" class="backup-prompt-btn no">오늘은 건너뛰기</button>
        `;
        document.body.appendChild(bar);
    }

    async function setupBackupFolder() {
        document.querySelector('.backup-prompt')?.remove();
        try {
            const dirHandle = await window.showDirectoryPicker({ mode: 'readwrite' });
            _backupDirHandle = dirHandle;
            await _storeDirHandle(dirHandle);
            await _doAutoBackup();
            toast('백업 폴더 설정 완료! 앞으로 자동 백업됩니다', 'success');
        } catch (e) {
            if (e.name !== 'AbortError') toast('폴더 설정 실패', 'error');
        }
    }

    async function _doAutoBackup() {
        try {
            const res = await fetch('/api/backup?format=json');
            if (!res.ok) return;
            const data = await res.json();
            const dateStr = new Date().toISOString().slice(0, 10);
            const filename = `backup_${dateStr}.json`;
            const jsonStr = JSON.stringify(data, null, 2);

            const fileHandle = await _backupDirHandle.getFileHandle(filename, { create: true });
            const writable = await fileHandle.createWritable();
            await writable.write(jsonStr);
            await writable.close();

            localStorage.setItem('lastBackupDate', dateStr);
        } catch (e) {
            // 권한 문제 등으로 실패 시 조용히 실패
            console.warn('Auto backup failed:', e);
        }
    }

    // IndexedDB에 디렉토리 핸들 저장/복원
    function _openBackupDB() {
        return new Promise((resolve, reject) => {
            const req = indexedDB.open('jjonggood_backup', 1);
            req.onupgradeneeded = () => req.result.createObjectStore('handles');
            req.onsuccess = () => resolve(req.result);
            req.onerror = () => reject(req.error);
        });
    }

    async function _storeDirHandle(handle) {
        const db = await _openBackupDB();
        const tx = db.transaction('handles', 'readwrite');
        tx.objectStore('handles').put(handle, 'backupDir');
    }

    async function _getStoredDirHandle() {
        const db = await _openBackupDB();
        return new Promise((resolve) => {
            const tx = db.transaction('handles', 'readonly');
            const req = tx.objectStore('handles').get('backupDir');
            req.onsuccess = () => resolve(req.result || null);
            req.onerror = () => resolve(null);
        });
    }

    // ==================== 뷰 전환 ====================

    function showView(view) {
        currentView = view;
        document.querySelectorAll('.nav-item').forEach(el => {
            el.classList.toggle('active', el.dataset.view === view);
        });
        // 열린 시트 모두 닫기 (즉시)
        document.querySelectorAll('.bottom-sheet-overlay').forEach(el => {
            if (el.style.display !== 'none') {
                el.style.display = 'none';
                const sh = el.querySelector('.bottom-sheet');
                if (sh) { sh.style.transform = ''; sh.style.transition = ''; }
                if (el.id && _closeTimers[el.id]) {
                    clearTimeout(_closeTimers[el.id]);
                    delete _closeTimers[el.id];
                }
            }
        });
        const calSec = document.getElementById('calendarSection');
        const tlSec = document.getElementById('timelineSection');
        const custView = document.getElementById('customerView');
        const salesView = document.getElementById('salesView');
        const requestsView = document.getElementById('requestsView');
        const leftPanel = document.querySelector('.left-panel');

        if (view === 'calendar') {
            calSec.style.display = '';
            if (leftPanel) leftPanel.style.display = '';
            tlSec.style.display = 'none';
            custView.style.display = 'none';
            salesView.style.display = 'none';
            if (requestsView) requestsView.style.display = 'none';
            // collapsed/split-view 해제 + 선택 초기화
            document.querySelector('.main-content')?.classList.remove('split-view');
            document.querySelector('.calendar-section')?.classList.remove('collapsed');
            selectedDate = null;
            loadMonth();
        } else if (view === 'timeline') {
            // PC 전용: 타임라인 전체 화면 (nav에서 calendar 활성 유지)
            document.querySelectorAll('.nav-item').forEach(el => {
                el.classList.toggle('active', el.dataset.view === 'calendar');
            });
            calSec.style.display = 'none';
            if (leftPanel) leftPanel.style.display = 'none';
            tlSec.style.display = 'flex';
            custView.style.display = 'none';
            salesView.style.display = 'none';
            if (requestsView) requestsView.style.display = 'none';
        } else if (view === 'customers') {
            if (!isPC()) {
                calSec.style.display = 'none';
                tlSec.style.display = 'none';
            } else {
                calSec.style.display = 'none';
                tlSec.style.display = 'none';
                if (leftPanel) leftPanel.style.display = 'none';
            }
            custView.style.display = 'flex';
            salesView.style.display = 'none';
            if (requestsView) requestsView.style.display = 'none';
            loadCustomerList('', customerSort);
        } else if (view === 'sales') {
            calSec.style.display = 'none';
            tlSec.style.display = 'none';
            if (leftPanel) leftPanel.style.display = 'none';
            custView.style.display = 'none';
            salesView.style.display = 'flex';
            if (requestsView) requestsView.style.display = 'none';
            if (!salesData) {
                const now = new Date();
                salesYear = now.getFullYear();
                salesMonth = now.getMonth() + 1;
            }
            loadSalesMonth();
        } else if (view === 'requests') {
            calSec.style.display = 'none';
            tlSec.style.display = 'none';
            if (leftPanel) leftPanel.style.display = 'none';
            custView.style.display = 'none';
            salesView.style.display = 'none';
            if (requestsView) requestsView.style.display = 'flex';
            loadGroomingRequests();
        }
    }

    // ==================== 월간 캘린더 ====================

    async function loadMonth() {
        updateMonthLabel();
        const grid = document.getElementById('calendarGrid');
        // 이미 렌더링된 캘린더가 있으면 스켈레톤 생략 (깜빡임 방지)
        if (!grid.querySelector('.cal-cell')) {
            grid.innerHTML = '<div class="loading" style="grid-column:1/-1;padding:20px"></div>';
        }

        try {
            const res = await fetch(`/api/month?y=${currentYear}&m=${currentMonth}`);
            if (!res.ok) { toast('서버 연결 실패', 'error'); return; }
            monthData = await res.json();
        } catch (e) {
            monthData = { counts: {}, names: {} };
        }
        renderCalendar();
    }

    function updateMonthLabel() {
        document.getElementById('monthLabel').textContent =
            `${currentYear}.${String(currentMonth).padStart(2,'0')}`;
    }

    function renderCalendar() {
        const grid = document.getElementById('calendarGrid');
        const today = new Date();
        const todayStr = fmtDate(today);

        const firstDay = new Date(currentYear, currentMonth - 1, 1).getDay();
        const lastDate = new Date(currentYear, currentMonth, 0).getDate();

        let html = '';
        for (let i = 0; i < firstDay; i++) {
            html += '<div class="cal-cell empty"></div>';
        }

        for (let d = 1; d <= lastDate; d++) {
            const dateStr = `${currentYear}-${String(currentMonth).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
            const dow = (firstDay + d - 1) % 7;
            const isToday = dateStr === todayStr;
            const isSelected = dateStr === selectedDate;

            let cls = 'cal-cell';
            if (isToday) cls += ' today';
            if (isSelected) cls += ' selected';
            if (dow === 0) cls += ' sunday';
            if (dow === 6) cls += ' saturday';

            const names = monthData.names[dateStr] || [];
            const maxBadges = 4;
            let badgesHtml = '';
            for (let i = 0; i < Math.min(names.length, maxBadges); i++) {
                const entry = names[i];
                if (entry.is_boss) {
                    const reason = entry.service_type || '휴무';
                    const label = '휴무(' + (reason.length > 3 ? reason.substring(0,3) + '..' : reason) + ')';
                    badgesHtml += `<span class="cal-badge boss">${esc(label)}</span>`;
                    continue;
                }
                let label = entry.pet_name;
                if (entry.breed) {
                    const b = entry.breed.length > 2 ? entry.breed.substring(0,2) + '..' : entry.breed;
                    label += `(${b})`;
                }
                if (label.length > 8) label = label.substring(0, 7) + '..';
                const statusCls = entry.status === 'completed' ? 'completed' : 'confirmed';
                badgesHtml += `<span class="cal-badge ${statusCls}">${esc(label)}</span>`;
            }
            if (names.length > maxBadges) {
                const overflow = names.length - maxBadges;
                // 5마리 이하: 보통 크기, 6~8: 작게, 9+: 더 작게
                const sizeClass = overflow <= 5 ? '' : overflow <= 8 ? 'sm' : 'xs';
                badgesHtml += `<span class="cal-dogs ${sizeClass}">${'🐕'.repeat(overflow)}</span>`;
            }

            html += `<div class="${cls}" onclick="App.selectDate('${dateStr}')">
                <span class="cal-day">${d}</span>
                <div class="cal-badges">${badgesHtml}</div>
            </div>`;
        }
        grid.innerHTML = html;
    }

    // ==================== 날짜 선택 → 타임라인 ====================

    async function selectDate(dateStr) {
        selectedDate = dateStr;
        renderCalendar();

        // 북킹/이동모드: 날짜 선택 시 바로 시간 선택 시트 열기
        if (bookingMode || moveMode) {
            showTimeSlotPicker();
            return;
        }

        // 모바일: 캘린더 접기 / PC: 좌우 분할
        if (isPC()) {
            document.querySelector('.main-content')?.classList.add('split-view');
        } else {
            document.querySelector('.calendar-section')?.classList.add('collapsed');
        }
        document.getElementById('timelineSection').style.display = 'flex';

        const content = document.getElementById('timelineContent');
        content.innerHTML = _skeletonTimeline();

        try {
            const res = await fetch(`/api/day?date=${dateStr}`);
            if (!res.ok) { toast('서버 연결 실패', 'error'); return; }
            const data = await res.json();
            renderTimeline(data);
        } catch (e) {
            content.innerHTML = '<div class="empty-timeline"><span class="empty-emoji" aria-hidden="true">🌧️</span><p class="empty-title">연결이 불안정해요</p><p>잠시 후 다시 시도해주세요</p><button class="empty-cta" onclick="App.selectDate(\'' + dateStr + '\')">다시 시도</button></div>';
        }
        document.getElementById('timelineSection').scrollTop = 0;
    }

    function renderTimeline(data) {
        const content = document.getElementById('timelineContent');
        const date = new Date(data.date + 'T00:00:00');
        const dow = WEEKDAYS_KR[date.getDay()];
        const parts = data.date.split('-');
        const dateLabel = `${parts[1]}/${parts[2]}(${dow})`;
        const items = data.reservations || [];

        // 타임슬롯 생성 (빈 슬롯 + 예약)
        const slots = generateTimeSlots();
        const booked = {};       // slot -> reservation
        const bookedIsStart = {}; // slot -> bool (예약 시작 슬롯 여부)

        for (const r of items) {
            const [sh, sm] = r.time.split(':').map(Number);
            const startMin = sh * 60 + sm;
            const nSlots = Math.max(1, Math.ceil(r.duration / CONFIG.slotInterval));
            for (let s = 0; s < nSlots; s++) {
                const t = startMin + s * CONFIG.slotInterval;
                const ts = `${String(Math.floor(t/60)).padStart(2,'0')}:${String(t%60).padStart(2,'0')}`;
                if (slots.includes(ts)) {
                    booked[ts] = r;
                    bookedIsStart[ts] = (s === 0);
                }
            }
        }

        let html = `
            <div class="timeline-header">
                <div>
                    <span class="timeline-date">${dateLabel}</span>
                    <span class="timeline-count">${items.length}건</span>
                </div>
                <div class="timeline-actions">
                    <button class="btn-boss-schedule" onclick="App.showBossScheduleForm()" title="휴무/일정 등록">🏖️</button>
                    <button class="timeline-close" onclick="App.closeTimeline()">&times;</button>
                </div>
            </div>
        `;

        // PC에서 동그라미 시간표
        if (isPC() && items.length > 0) {
            html += _renderClockChart(slots, booked, items);
        }

        // 예약 내역만 표시 (빈 슬롯 제거)
        html += renderReservationList(items);

        content.innerHTML = html;
        updateStatsBar(data);
    }

    function renderReservationList(items) {
        if (!items || !items.length) {
            return `<div class="empty-timeline">
                <span class="empty-emoji" aria-hidden="true">🐾</span>
                <p class="empty-title">예약이 없어요!</p>
                <p>이 날짜에 첫 예약을 등록해보세요</p>
                <button class="empty-cta" onclick="App.onQuickReserveForDate()">✂️ 예약 등록하기</button>
                <button class="empty-cta boss-cta" onclick="App.showBossScheduleForm()" style="margin-top:8px">🏖️ 휴무/일정 등록</button>
                <p class="mobile-only" style="font-size:12px;margin-top:24px">↓ 아래로 스와이프하면 캘린더로 돌아갑니다</p>
            </div>`;
        }
        const TL_LABEL = { confirmed: '🕐 예약', completed: '✅ 완료', cancelled: '❌ 취소', no_show: '⚠️ 노쇼' };
        let html = '<div class="timeline-list">';
        for (const r of items) {
            const isBoss = r.customer_id === CONFIG.bossCustomerId;
            const startLabel = formatTime(r.time);
            const endLabel = formatTime(r.end_time);
            const statusCls = r.status || 'confirmed';
            const statusText = TL_LABEL[statusCls] || statusCls;

            if (isBoss) {
                const reason = r.service || '휴무';
                const memoSrc = r.groomer_memo || '';
                const memoText = memoSrc ? `<div class="res-memo">${esc(memoSrc)}</div>` : '';
                html += `
                    <div class="res-card boss-schedule ${statusCls}" onclick="App.showReservationDetail(${r.id},${r.customer_id})">
                        <div class="res-time-col">
                            <div class="res-time-start">${startLabel}</div>
                            <div class="res-time-end">${endLabel}</div>
                        </div>
                        <div class="res-info">
                            <div class="res-pet">🏖️ 휴무 <span class="breed">(${esc(reason)})</span></div>
                            ${memoText}
                        </div>
                        <span class="res-status boss">휴무</span>
                    </div>`;
                continue;
            }

            const breedText = r.breed ? `(${r.breed})` : '';
            const amtText = r.amount === -1 ? '미정' : r.amount ? `${r.amount.toLocaleString()}원` : '';
            const furText = r.fur_length ? ` / ${esc(r.fur_length)}` : '';
            const weightText = r.weight ? `${r.weight}kg` : '';
            const petMeta = [breedText, weightText].filter(Boolean).join(' · ');
            const memoSrc = r.customer_memo || r.groomer_memo || r.request || '';
            const memoText = memoSrc ? `<div class="res-memo">${esc(memoSrc)}</div>` : '';
            html += `
                <div class="res-card ${statusCls}" onclick="App.showReservationDetail(${r.id},${r.customer_id})">
                    <div class="res-time-col">
                        <div class="res-time-start">${startLabel}</div>
                        <div class="res-time-end">${endLabel}</div>
                    </div>
                    <div class="res-info">
                        <div class="res-pet">
                            ${r.keyring === false ? '<span class="keyring-dot">🔑</span>' : ''}${esc(r.pet_name)}
                            <span class="breed">${esc(petMeta)}</span>
                        </div>
                        <div class="res-service">${esc(r.service)}${furText}${amtText ? ' · ' + amtText : ''}</div>
                        ${memoText}
                    </div>
                    <span class="res-status ${statusCls}">${statusText}</span>
                </div>`;
        }
        html += '</div>';
        return html;
    }

    function closeTimeline() {
        selectedDate = null;
        renderCalendar();
        document.querySelector('.main-content')?.classList.remove('split-view');
        document.querySelector('.calendar-section')?.classList.remove('collapsed');
        document.getElementById('timelineSection').style.display = 'none';
    }

    // 모바일 타임라인 스와이프 다운 → 캘린더로 복귀
    (function setupTimelineSwipe() {
        const tl = document.getElementById('timelineSection');
        if (!tl) return;
        let startY = 0, currentY = 0, dragging = false;
        tl.addEventListener('touchstart', (e) => {
            if (isPC()) return;
            startY = e.touches[0].clientY;
            currentY = 0;
            dragging = false;
        }, { passive: true });
        tl.addEventListener('touchmove', (e) => {
            if (isPC()) return;
            const dy = e.touches[0].clientY - startY;
            if (tl.scrollTop <= 0 && dy > 10 && !dragging) {
                dragging = true;
            }
            if (dragging && dy > 0) {
                currentY = dy;
                tl.style.transition = 'none';
                tl.style.transform = `translateY(${Math.min(dy, 200)}px)`;
                tl.style.opacity = Math.max(0.3, 1 - dy / 300);
                e.preventDefault();
            }
        }, { passive: false });
        tl.addEventListener('touchend', () => {
            if (!dragging) return;
            dragging = false;
            if (currentY > 80) {
                tl.style.transition = 'transform 0.2s, opacity 0.2s';
                tl.style.transform = 'translateY(100%)';
                tl.style.opacity = '0';
                setTimeout(() => {
                    tl.style.transform = '';
                    tl.style.opacity = '';
                    tl.style.transition = '';
                    closeTimeline();
                }, 200);
            } else {
                tl.style.transition = 'transform 0.2s, opacity 0.2s';
                tl.style.transform = '';
                tl.style.opacity = '';
            }
            currentY = 0;
        }, { passive: true });
    })();

    // ==================== 빈 슬롯 클릭 → 고객 선택 → 예약 생성 ====================

    function onSlotClick(timeStr) {
        pendingSlotTime = timeStr;

        // 이동모드: 기존 예약의 날짜/시간만 변경
        if (moveMode) {
            const rid = moveMode.reservationId;
            const petName = moveMode.petName;
            if (!confirm(`${petName} 예약을 ${selectedDate} ${formatTime(timeStr)}로 이동하시겠습니까?`)) return;
            fetch(`/api/reservation/${rid}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ date: selectedDate, time: timeStr }),
            }).then(r => r.json()).then(result => {
                if (result.ok) {
                    toast('예약이 이동되었습니다', 'success');
                    selectDate(selectedDate);
                    loadMonth();
                } else {
                    toast(result.error || '이동 실패', 'error');
                }
            }).catch(() => toast('이동 실패', 'error'));
            moveMode = null;
            hideModeBar();
            return;
        }

        // 북킹모드: 이미 선택된 고객으로 바로 예약 폼
        if (bookingMode) {
            pendingSlotCustomer = bookingMode.customer;
            bookingMode = null;
            hideModeBar();
            showReservationForm(pendingSlotCustomer);
            return;
        }

        // 일반: 고객 선택 시트 열기
        openSheet('customerSelectSheet');
        document.getElementById('slotCustomerSearch').value = '';
        document.getElementById('slotCustomerResults').innerHTML =
            '<p style="text-align:center;color:#999;padding:20px">고객을 검색하세요</p>';
        setTimeout(() => document.getElementById('slotCustomerSearch').focus(), 300);
    }

    function onBookedSlotClick() {
        toast('예약불가 — 이미 예약이 있는 시간입니다', 'error');
    }

    async function searchCustomersForSlot(keyword) {
        const container = document.getElementById('slotCustomerResults');
        if (!keyword.trim()) {
            container.innerHTML = '<p style="text-align:center;color:#999;padding:20px">고객을 검색하세요</p>';
            return;
        }
        clearTimeout(searchTimer);
        searchTimer = setTimeout(async () => {
            try {
                const res = await fetch(`/api/customers/search?q=${encodeURIComponent(keyword)}`);
                const data = await res.json();
                renderCustomerList(container, data.customers, (c) => {
                    pendingSlotCustomer = c;
                    closeSheet('customerSelectSheet');
                    showReservationForm(c);
                });
            } catch (e) {
                container.innerHTML = '<p style="text-align:center;color:#999;padding:20px">검색 실패</p>';
            }
        }, 300);
    }

    function showNewCustomerFormForSlot() {
        closeSheet('customerSelectSheet');
        showCustomerForm(null, (newCustomer) => {
            pendingSlotCustomer = newCustomer;
            showReservationForm(newCustomer);
        });
    }

    function showReservationForm(customer) {
        const form = document.getElementById('reservationForm');
        document.getElementById('sheetTitle').textContent =
            `✂️ 예약 등록 - ${customer.pet_name}`;

        const svc0 = CONFIG.services[0];
        let serviceGrid = `<button type="button" class="btn-grid-item active" data-field="resService" data-value="방문상담 후 결정" data-dur="0" data-price="0" onclick="App.selectGridBtn(this)">방문상담 후 결정</button>`;
        serviceGrid += CONFIG.services.map(s =>
            `<button type="button" class="btn-grid-item" data-field="resService" data-value="${esc(s[0])}" data-dur="${s[1]}" data-price="${s[2]}" onclick="App.selectGridBtn(this)">${esc(s[0])}</button>`
        ).join('');

        let furGrid = `<button type="button" class="btn-grid-item active" data-field="resFurLength" data-value="" onclick="App.selectGridBtn(this)">없음</button>` +
            CONFIG.furLengths.map(f =>
                `<button type="button" class="btn-grid-item" data-field="resFurLength" data-value="${f}" onclick="App.selectGridBtn(this)">${f}</button>`
            ).join('');

        const durations = [30, 60, 90, 120, 150, 180];
        const durLabels = {30:'30분', 60:'1시간', 90:'1시간30분', 120:'2시간', 150:'2시간30분', 180:'3시간'};
        let durGrid = durations.map(d =>
            `<button type="button" class="btn-grid-item" data-field="resDuration" data-value="${d}" onclick="App.selectGridBtn(this)" disabled style="opacity:0.4">${durLabels[d]}</button>`
        ).join('');

        const prices = [30000,35000,40000,45000,50000,55000,60000,65000,70000,75000,80000,85000,90000,95000,100000];
        let priceGrid = prices.map(p => {
            const label = p % 10000 === 0 ? `${p/10000}만` : `${Math.floor(p/10000)}만${(p%10000)/1000}천`;
            return `<button type="button" class="btn-grid-item" data-field="resAmount" data-value="${p}" onclick="App.selectGridBtn(this)">${label}</button>`;
        }).join('');
        priceGrid += `<button type="button" class="btn-grid-item" data-field="resAmount" data-value="0" onclick="App.showCustomAmount('resAmount')">기타</button>`;
        priceGrid += `<button type="button" class="btn-grid-item" data-field="resAmount" data-value="-1" onclick="App.selectGridBtn(this)">미정</button>`;

        // 이전 서비스 불러오기 버튼 + 이력
        let prevHtml = '';
        if (customer.reservations && customer.reservations.length) {
            const last = customer.reservations[0];
            const lastLabel = `${esc(last.service_type)}${last.fur_length ? ' / '+esc(last.fur_length) : ''} / ${last.amount === -1 ? '미정' : last.amount ? last.amount.toLocaleString()+'원' : '-'}`;
            const recent = customer.reservations.slice(0, 5);
            prevHtml = `
                <div class="prev-services">
                    <button type="button" class="btn-load-prev" onclick="App.applyPrevService('${esc(last.service_type)}',${last.duration},${last.amount||0},'${esc(last.fur_length||'')}')">
                        🔄 지난 예약 불러오기 <span class="prev-summary">${lastLabel}</span>
                    </button>
                    <button type="button" class="prev-services-toggle" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">
                        이전 이력 더보기 (${customer.reservations.length}건) <span>▼</span>
                    </button>
                    <div class="prev-services-list" style="display:none">
                        ${recent.map(r => `<div class="prev-service-item" onclick="App.applyPrevService('${esc(r.service_type)}',${r.duration},${r.amount||0},'${esc(r.fur_length||'')}')">
                            <span>${esc(r.service_type)} / ${r.duration}분</span>
                            <span>${r.amount === -1 ? '미정' : r.amount ? r.amount.toLocaleString()+'원' : '-'}</span>
                        </div>`).join('')}
                    </div>
                </div>`;
        }

        form.innerHTML = `
            <input type="hidden" id="resCustomerId" value="${customer.id}">
            <input type="hidden" id="resService" value="방문상담 후 결정">
            <input type="hidden" id="resDuration" value="0">
            <input type="hidden" id="resAmount" value="0">
            <input type="hidden" id="resFurLength" value="">
            <div class="res-form-grid">
                <div class="form-group res-form-full">
                    <label>고객</label>
                    <div class="res-customer-info">
                        <div class="res-customer-main">${esc(customer.pet_name)} <span class="breed">${esc(customer.breed || '')}</span> <span class="customer-sub">- ${esc(customer.name || customer.phone_display || '')}</span></div>
                        ${customer.weight || customer.notes ? `<div class="res-customer-detail">${[customer.weight ? customer.weight + 'kg' : '', customer.notes || ''].filter(Boolean).map(esc).join(' · ')}</div>` : ''}
                    </div>
                </div>
                <div class="form-group">
                    <label>시간</label>
                    <input type="text" value="${formatTime(pendingSlotTime)}" disabled>
                </div>
                ${prevHtml ? `<div class="res-form-full">${prevHtml}</div>` : ''}
                <div class="form-group res-form-full">
                    <label>미용 종류</label>
                    <div class="btn-grid">${serviceGrid}</div>
                </div>
                <div class="form-group">
                    <label>털 길이</label>
                    <div class="btn-grid">${furGrid}</div>
                </div>
                <div class="form-group">
                    <label>소요시간 <span class="sub-label" id="durLabel">-</span></label>
                    <div class="btn-grid">${durGrid}</div>
                </div>
                <div class="form-group res-form-full">
                    <label>금액 <span class="sub-label" id="priceLabel">-</span></label>
                    <div class="btn-grid">${priceGrid}</div>
                </div>
                <div class="form-group res-form-full">
                    <label>메모 <span class="sub-label">(이 고객의 통합 메모)</span></label>
                    <textarea id="resMemo" rows="3" placeholder="메모">${esc(customer.memo || '')}</textarea>
                </div>
                <div class="res-form-full">
                    <button class="btn-primary" onclick="App.saveReservation()">예약 저장</button>
                </div>
            </div>
        `;
        openSheet('reservationSheet');
        _setupFormDirtyTracking();
    }

    function _setupFormDirtyTracking() {
        const form = document.getElementById('reservationForm');
        if (!form) return;
        form.dataset.dirty = '0';
        form.addEventListener('input', () => { form.dataset.dirty = '1'; }, { once: true });
        form.addEventListener('click', (e) => {
            if (e.target.classList.contains('btn-grid-item')) form.dataset.dirty = '1';
        });
    }

    function selectGridBtn(btn) {
        const field = btn.dataset.field;
        // 같은 그룹의 active 해제
        btn.parentElement.querySelectorAll('.btn-grid-item').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        // hidden input 업데이트
        const input = document.getElementById(field);
        if (input) input.value = btn.dataset.value;
        // 서비스 선택 시 연동
        if ((field === 'resService' || field === 'editResService') && btn.dataset.dur !== undefined) {
            const prefix = field.startsWith('edit') ? 'editRes' : 'res';
            const isConsult = btn.dataset.value === '방문상담 후 결정';
            document.getElementById(prefix + 'Duration').value = btn.dataset.dur;
            document.getElementById(prefix + 'Amount').value = btn.dataset.price;
            const dur = parseInt(btn.dataset.dur);
            const price = parseInt(btn.dataset.price);
            document.querySelectorAll('[data-field="'+prefix+'Duration"]').forEach(b => {
                b.classList.toggle('active', parseInt(b.dataset.value) === dur);
                b.disabled = isConsult;
                b.style.opacity = isConsult ? '0.4' : '';
            });
            document.querySelectorAll('[data-field="'+prefix+'Amount"]').forEach(b => {
                b.classList.toggle('active', parseInt(b.dataset.value) === price);
            });
            const durLabel = document.getElementById('durLabel');
            const priceLabel = document.getElementById('priceLabel');
            if (durLabel) durLabel.textContent = isConsult ? '-' : dur + '분';
            if (priceLabel) priceLabel.textContent = isConsult ? '-' : price.toLocaleString() + '원';
            return;
        }
        if (field === 'resDuration' || field === 'editResDuration') {
            const durLabel = document.getElementById('durLabel');
            if (durLabel) durLabel.textContent = btn.dataset.value + '분';
        }
        if (field === 'resAmount' || field === 'editResAmount') {
            const priceLabel = document.getElementById('priceLabel');
            const v = parseInt(btn.dataset.value);
            if (priceLabel) priceLabel.textContent = v === -1 ? '미정' : v.toLocaleString() + '원';
        }
    }

    function showCustomAmount(fieldId) {
        const val = prompt('금액을 입력하세요 (숫자만)', '');
        if (val === null) return;
        const num = parseInt(val.replace(/[^0-9]/g, ''));
        if (!num || num <= 0) return;
        document.getElementById(fieldId).value = num;
        // 모든 금액 버튼 active 해제
        document.querySelectorAll(`[data-field="${fieldId}"]`).forEach(b => b.classList.remove('active'));
        const priceLabel = document.getElementById('priceLabel');
        if (priceLabel) priceLabel.textContent = num.toLocaleString() + '원';
    }

    function applyPrevService(service, duration, amount, furLength) {
        document.getElementById('resService').value = service;
        document.getElementById('resDuration').value = duration;
        document.getElementById('resAmount').value = amount;
        document.getElementById('resFurLength').value = furLength;
        // 버튼 active 상태 업데이트
        document.querySelectorAll('[data-field="resService"]').forEach(b =>
            b.classList.toggle('active', b.dataset.value === service));
        document.querySelectorAll('[data-field="resDuration"]').forEach(b =>
            b.classList.toggle('active', parseInt(b.dataset.value) === duration));
        document.querySelectorAll('[data-field="resAmount"]').forEach(b =>
            b.classList.toggle('active', parseInt(b.dataset.value) === amount));
        document.querySelectorAll('[data-field="resFurLength"]').forEach(b =>
            b.classList.toggle('active', b.dataset.value === furLength));
        const durLabel = document.getElementById('durLabel');
        const priceLabel = document.getElementById('priceLabel');
        if (durLabel) durLabel.textContent = duration + '분';
        if (priceLabel) priceLabel.textContent = amount.toLocaleString() + '원';
        // 이전 서비스 리스트 접기
        const list = document.querySelector('.prev-services-list');
        if (list) list.style.display = 'none';
        toast(service + ' 적용');
    }

    function onServiceChange() {
        // legacy - 버튼 그리드 방식에서는 selectGridBtn이 대신 처리
    }

    async function saveReservation() {
        if (!selectedDate || !pendingSlotTime) {
            toast('날짜와 시간을 선택해주세요', 'error');
            return;
        }
        const memoText = document.getElementById('resMemo').value.trim();
        const customerId = parseInt(document.getElementById('resCustomerId').value);
        const data = {
            customer_id: customerId,
            date: selectedDate,
            time: pendingSlotTime,
            service_type: document.getElementById('resService').value,
            duration: Number(document.getElementById('resDuration').value) || 0,
            amount: parseInt(document.getElementById('resAmount').value) ?? 0,
            quoted_amount: parseInt(document.getElementById('resAmount').value) ?? 0,
            payment_method: (document.getElementById('resPaymentMethod') || {}).value || '',
            fur_length: document.getElementById('resFurLength').value,
            request: '',
            groomer_memo: memoText,
        };
        if (memoText.length > 500) {
            if (!confirm(`메모가 ${memoText.length}자입니다. 500자까지만 저장됩니다. 계속하시겠습니까?`)) return;
        }

        try {
            const res = await fetch('/api/reservation', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
            const result = await res.json();
            if (result.ok) {
                // 통합 메모: 기다리지 않고 백그라운드 동기화
                fetch(`/api/customer/${customerId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ memo: memoText }),
                }).then(() => { cachedCustomers = null; });
                // 즉시 화면 갱신
                closeSheet('reservationSheet', true);
                toast('예약이 저장되었습니다', 'success');
                selectDate(selectedDate);
                loadMonth();
            } else {
                toast(result.error || '저장 실패', 'error');
            }
        } catch (e) {
            toast('저장 실패', 'error');
        }
    }

    // ==================== 통합 상세 (예약+고객) ====================

    // 예약 카드에서 진입: customer API 1회 호출, reservations 배열에서 activeRes 탐색
    async function showReservationDetail(rid, customerId) {
        const content = document.getElementById('unifiedDetailContent');
        content.innerHTML = '<div style="padding:16px">' + _skeletonCustomerList() + '</div>';
        document.getElementById('unifiedDetailTitle').textContent = '상세';
        openSheet('unifiedDetailSheet');

        try {
            // customerId가 없으면 reservation API로 한 번만 조회
            if (!customerId) {
                const rRes = await fetch(`/api/reservation/${rid}`);
                if (!rRes.ok) throw new Error('reservation fetch failed');
                const r = await rRes.json();
                customerId = r.customer_id;
            }
            const cRes = await fetch(`/api/customer/${customerId}`);
            if (!cRes.ok) throw new Error('customer fetch failed');
            const c = await cRes.json();
            // reservations 배열에서 해당 rid 찾기
            const allRes = c.reservations || [];
            const sibRes = c.sibling_reservations || {};
            let activeRes = allRes.find(r => r.id === rid);
            if (!activeRes) {
                for (const sId of Object.keys(sibRes)) {
                    activeRes = (sibRes[sId] || []).find(r => r.id === rid);
                    if (activeRes) break;
                }
            }
            renderUnifiedDetail(c, activeRes || null);
        } catch (e) {
            content.innerHTML = '<p style="text-align:center;color:#999;padding:20px">불러오기 실패</p>';
        }
    }

    // 고객 목록에서 진입: customer API만
    async function showCustomerDetail(cid) {
        const content = document.getElementById('unifiedDetailContent');
        content.innerHTML = '<div style="padding:16px">' + _skeletonCustomerList() + '</div>';
        document.getElementById('unifiedDetailTitle').textContent = '상세';
        openSheet('unifiedDetailSheet');

        try {
            const res = await fetch(`/api/customer/${cid}`);
            if (!res.ok) throw new Error('customer fetch failed');
            const c = await res.json();
            renderUnifiedDetail(c, null);
        } catch (e) {
            content.innerHTML = '<p style="text-align:center;color:#999;padding:20px">불러오기 실패</p>';
        }
    }

    function renderUnifiedDetail(c, activeRes) {
        _unifiedActiveResId = activeRes ? activeRes.id : null;
        const content = document.getElementById('unifiedDetailContent');
        const siblings = c.siblings || [];
        const allPets = [{ id: c.id, pet_name: c.pet_name, breed: c.breed, weight: c.weight, age: c.age || '', memo: c.memo || '' }, ...siblings.map(s => ({...s, age: s.age || '', memo: s.memo || ''}))];
        const hasSiblings = siblings.length > 0;

        // 헤더: 모든 펫을 한 줄에 나열 (견종 · 체중 · 나이)
        let petsHeaderHtml = allPets.map((p, i) => {
            const w = p.weight ? ' · ' + p.weight + 'kg' : '';
            const a = p.age ? ' · ' + p.age + (p.age.includes('살') ? '' : '살') : '';
            return `<span class="ud-pet-name">${esc(p.pet_name)}</span><span class="ud-pet-info">${esc(p.breed)}${w}${a}</span>`;
        }).join('<span class="ud-pet-divider">/</span>');
        const addBtnHtml = `<button class="pet-pill pet-pill-add" style="font-size:12px;padding:2px 8px;margin-left:4px;vertical-align:middle" data-phone="${esc(c.phone)}" data-name="${esc(c.name || '')}" data-channel="${esc(c.channel || '')}" onclick="App.addSiblingPet(this.dataset.phone, this.dataset.name, this.dataset.channel)">+</button>`;

        // 모든 예약 이력 합치기
        const siblingRes = c.sibling_reservations || {};
        let allReservations = (c.reservations || []).map(r => ({...r, _pet: c.pet_name}));
        for (const s of siblings) {
            const sRes = siblingRes[s.id] || [];
            allReservations = allReservations.concat(sRes.map(r => ({...r, _pet: s.pet_name})));
        }
        allReservations.sort((a, b) => (b.date + b.time).localeCompare(a.date + a.time));

        // 통계: 전체 예약 기준으로 합산
        const completedRes = allReservations.filter(r => r.status === 'completed');
        const totalCount = completedRes.length;
        const totalSales = completedRes.reduce((sum, r) => sum + (r.amount > 0 ? r.amount : 0), 0);
        const firstVisit = allReservations.length ? allReservations[allReservations.length - 1].date : null;
        const lastVisit = allReservations.length ? allReservations[0].date : null;
        const daysSinceLast = lastVisit ? Math.floor((Date.now() - new Date(lastVisit + 'T00:00:00')) / 86400000) : null;
        const cycleDays = (totalCount > 1 && firstVisit && lastVisit)
            ? Math.round((new Date(lastVisit+'T00:00:00') - new Date(firstVisit+'T00:00:00')) / 86400000 / (totalCount - 1)) : null;

        const salesText = totalSales ? totalSales.toLocaleString() + '원' : '0원';
        let visitLine = '';
        const vp = [];
        if (firstVisit) vp.push(`첫 ${firstVisit.substring(5)}`);
        if (lastVisit) vp.push(`최근 ${lastVisit.substring(5)}${daysSinceLast !== null ? `(${daysSinceLast}일전)` : ''}`);
        if (cycleDays) vp.push(`주기 ${cycleDays}일`);
        if (vp.length) visitLine = vp.join(' · ');

        // 통합 메모: 형제 공유 (아무 펫 눌러도 같은 메모)
        const sharedMemo = allPets.map(p => p.memo || '').find(m => m) || '';
        const allPetIds = allPets.map(p => p.id).join(',');
        const memoHtml = `
            <div class="ud-merged-memo" id="mergedMemoView_${c.id}" onclick="App.startMemoEdit(${c.id})" title="클릭하여 편집">
                <div class="memo-text clickable">${esc(sharedMemo) || '<span class="memo-empty">메모를 입력하세요</span>'}</div>
            </div>
            <div id="mergedMemoEdit_${c.id}" style="display:none">
                <textarea id="memoTA_${c.id}" class="memo-edit-ta" rows="3">${esc(sharedMemo)}</textarea>
                <div style="display:flex;gap:4px;margin-top:4px">
                    <button class="btn-primary-sm" style="padding:6px 14px;font-size:13px" onclick="App.saveMergedMemo(${c.id}, '${allPetIds}')">저장</button>
                    <button class="btn-cancel-sm" onclick="App.cancelMemoEdit(${c.id})">취소</button>
                </div>
            </div>`;

        // 아코디언 이력 (모든 예약 표시, activeRes는 자동 펼침+강조)
        const activeResId = activeRes ? activeRes.id : null;
        let historyHtml = '';
        if (allReservations.length) {
            historyHtml = allReservations.map(r => {
                const isActive = r.id === activeResId;
                const statusLabel = STATUS_LABEL[r.status] || r.status;
                const d = new Date(r.date + 'T00:00:00');
                const dow = WEEKDAYS_KR[d.getDay()];
                const dateStr = `${r.date.substring(5).replace('-','.')}(${dow})`;
                const timeStr = r.time ? ' ' + formatTime(r.time) : '';
                const amt = r.amount === -1 ? '미정' : r.amount ? r.amount.toLocaleString() + '원' : '';
                const resMemo = r.groomer_memo || r.request || '';
                const isLegacyMemo = resMemo && !r.customer_memo; // 과거 데이터: groomer_memo만 있는 경우
                const petTag = hasSiblings ? `<span style="font-size:12px;font-weight:600;color:var(--primary);background:var(--primary-light);padding:2px 6px;border-radius:4px;margin-right:4px">${esc(r._pet)}</span>` : '';
                return `
                    <div class="ud-acc-item${isActive ? ' open active-res' : ''}" id="acc_${r.id}">
                        <button type="button" class="ud-acc-header" onclick="App.toggleHistoryAccordion(${r.id})" aria-expanded="${isActive}" aria-controls="acc_body_${r.id}">
                            <span class="res-status ${r.status}" style="min-width:36px;text-align:center;font-size:12px">${statusLabel}</span>
                            <div style="flex:1;min-width:0">
                                <div style="font-size:14px;font-weight:500">${petTag}${dateStr}${timeStr}</div>
                                <div style="font-size:13px;color:var(--text-light)">${esc(r.service_type)}${r.fur_length ? '/'+esc(r.fur_length) : ''}${amt ? ' · '+amt : ''}</div>
                            </div>
                            <span class="arrow">&#8250;</span>
                        </button>
                        <div class="ud-acc-body" id="acc_body_${r.id}">
                            <div class="detail-row"><span class="label">서비스</span><span class="value">${esc(r.service_type)} ${r.duration||''}분${r.fur_length ? ' / '+esc(r.fur_length) : ''}</span></div>
                            <div class="detail-row"><span class="label">금액</span><span class="value">${amt||'-'}${r.payment_method ? ' ('+esc(r.payment_method)+')' : ''}</span></div>
                            ${resMemo ? `<div class="detail-row"><span class="label">메모</span><span class="value">${esc(resMemo)}</span></div>` : ''}
                            <div class="acc-actions">
                                <button class="btn-secondary" onclick="App.showEditReservation(${r.id})">수정</button>
                                ${r.status === 'confirmed' ? `
                                    <button class="btn-status yellow" data-pet="${esc(r._pet||c.pet_name)}" onclick="App.enterMoveMode(${r.id},this.dataset.pet)">날짜변경</button>
                                    <button class="btn-status green" onclick="App.changeStatus(${r.id},'completed')">완료</button>
                                ` : ''}
                            </div>
                        </div>
                    </div>`;
            }).join('');
        } else {
            historyHtml = '<div style="text-align:center;color:var(--text-light);padding:20px 8px;font-size:13px">✨ 첫 방문 고객이에요!</div>';
        }

        content.innerHTML = `
            <div class="ud-header-bar">
                <div class="ud-header-main">
                    ${petsHeaderHtml}${addBtnHtml}
                    <span class="ud-pet-divider">|</span>
                    <a href="tel:${c.phone}" class="ud-pet-phone">${esc(c.phone_display)}</a>
                    ${c.phone2 ? `<a href="tel:${c.phone2}" class="ud-pet-phone ud-phone-sub" title="보조연락처">${esc(c.phone2_display)}</a>` : ''}
                    <button class="keyring-badge ${c.keyring ? 'given' : 'not-given'}" onclick="App.toggleKeyring(${c.id}, ${!c.keyring})">${c.keyring ? '🔑 증정완료' : '🔑 키링 미증정!'}</button>
                    <button class="ud-edit-link" onclick="App.showCustomerForm_edit(${c.id})" aria-label="고객 정보 수정">수정</button>
                    <button class="ud-edit-link ud-photo-link" onclick="App.showRefPhotos(${c.id})" aria-label="참고사진">📷</button>
                </div>
            </div>
            <div class="ud-memo-banner">
                <div class="ud-memo-banner-header">
                    <span class="ud-memo-banner-icon">✏️</span> 메모
                </div>
                ${memoHtml}
            </div>
            <div class="ud-stats">
                <strong>${allReservations.length}</strong>건 이력${totalCount ? ` · 완료 <strong>${totalCount}</strong>건` : ''} · 매출 <strong>${salesText}</strong>
                ${visitLine ? `<br>${visitLine}` : ''}
            </div>
            <div class="ud-history-title">🐾 이력 (${allReservations.length}건)</div>
            <div class="ud-history-scroll">
                ${historyHtml}
            </div>
        `;
    }

    // 통합 상세 새로고침 (activeRes 유지)
    async function _reloadUnifiedDetail(customerId) {
        try {
            const cRes = await fetch(`/api/customer/${customerId}`);
            if (!cRes.ok) throw new Error('reload failed');
            const c = await cRes.json();
            let activeRes = null;
            if (_unifiedActiveResId) {
                const allRes = c.reservations || [];
                const sibRes = c.sibling_reservations || {};
                activeRes = allRes.find(r => r.id === _unifiedActiveResId);
                if (!activeRes) {
                    for (const sId of Object.keys(sibRes)) {
                        activeRes = (sibRes[sId] || []).find(r => r.id === _unifiedActiveResId);
                        if (activeRes) break;
                    }
                }
            }
            renderUnifiedDetail(c, activeRes || null);
        } catch (e) { /* 무시 — 이미 toast 표시됨 */ }
    }

    function toggleHistoryAccordion(rid) {
        const el = document.getElementById('acc_' + rid);
        if (!el) return;
        el.classList.toggle('open');
        const btn = el.querySelector('.ud-acc-header');
        if (btn) btn.setAttribute('aria-expanded', el.classList.contains('open'));
    }


    async function showEditReservation(rid) {
        try {
            const res = await fetch(`/api/reservation/${rid}`);
            if (!res.ok) { toast('불러오기 실패', 'error'); return; }
            const r = await res.json();
            closeSheet('unifiedDetailSheet');

            let serviceGrid = CONFIG.services.map(s =>
                `<button type="button" class="btn-grid-item${s[0]===r.service_type?' active':''}" data-field="editResService" data-value="${esc(s[0])}" data-dur="${s[1]}" data-price="${s[2]}" onclick="App.selectGridBtn(this)">${esc(s[0])}</button>`
            ).join('');
            serviceGrid += `<button type="button" class="btn-grid-item${'방문상담 후 결정'===r.service_type?' active':''}" data-field="editResService" data-value="방문상담 후 결정" data-dur="0" data-price="0" onclick="App.selectGridBtn(this)">방문상담 후 결정</button>`;
            if (!CONFIG.services.find(s => s[0] === r.service_type) && r.service_type !== '방문상담 후 결정') {
                serviceGrid = `<button type="button" class="btn-grid-item active" data-field="editResService" data-value="${esc(r.service_type)}" onclick="App.selectGridBtn(this)">${esc(r.service_type)}</button>` + serviceGrid;
            }

            let furGrid = `<button type="button" class="btn-grid-item${!r.fur_length?' active':''}" data-field="editResFurLength" data-value="" onclick="App.selectGridBtn(this)">없음</button>` +
                CONFIG.furLengths.map(f =>
                    `<button type="button" class="btn-grid-item${f===r.fur_length?' active':''}" data-field="editResFurLength" data-value="${f}" onclick="App.selectGridBtn(this)">${f}</button>`
                ).join('');

            const isConsult = r.service_type === '방문상담 후 결정';
            const disAttr = isConsult ? ' disabled style="opacity:0.4"' : '';
            const durations = [30, 60, 90, 120, 150, 180];
            const durLabels = {30:'30분', 60:'1시간', 90:'1시간30분', 120:'2시간', 150:'2시간30분', 180:'3시간'};
            let durGrid = durations.map(d =>
                `<button type="button" class="btn-grid-item${d===r.duration?' active':''}" data-field="editResDuration" data-value="${d}" onclick="App.selectGridBtn(this)"${disAttr}>${durLabels[d]||d+'분'}</button>`
            ).join('');

            const prices = [30000,35000,40000,45000,50000,55000,60000,65000,70000,75000,80000,85000,90000,95000,100000];
            const priceActive = !prices.includes(r.amount) && r.amount > 0;
            let priceGrid = prices.map(p => {
                const label = p % 10000 === 0 ? `${p/10000}만` : `${Math.floor(p/10000)}만${(p%10000)/1000}천`;
                return `<button type="button" class="btn-grid-item${p===r.amount?' active':''}" data-field="editResAmount" data-value="${p}" onclick="App.selectGridBtn(this)">${label}</button>`;
            }).join('');
            priceGrid += `<button type="button" class="btn-grid-item${priceActive?' active':''}" data-field="editResAmount" data-value="0" onclick="App.showCustomAmount('editResAmount')">기타</button>`;
            priceGrid += `<button type="button" class="btn-grid-item${r.amount===-1?' active':''}" data-field="editResAmount" data-value="-1" onclick="App.selectGridBtn(this)">미정</button>`;
            const form = document.getElementById('reservationForm');
            document.getElementById('sheetTitle').textContent = '✏️ 예약 수정';
            form.innerHTML = `
                <input type="hidden" id="editResId" value="${rid}">
                <input type="hidden" id="editResCustId" value="${r.customer_id}">
                <input type="hidden" id="editResService" value="${esc(r.service_type)}">
                <input type="hidden" id="editResDuration" value="${r.duration}">
                <input type="hidden" id="editResAmount" value="${r.amount}">
                <input type="hidden" id="editResFurLength" value="${esc(r.fur_length || '')}">
                <div class="res-form-grid">
                    <div class="form-group">
                        <label>날짜</label>
                        <input type="date" id="editResDate" value="${r.date}">
                    </div>
                    <div class="form-group">
                        <label>시간</label>
                        <input type="time" id="editResTime" value="${r.time}">
                    </div>
                    <div class="form-group res-form-full">
                        <label>미용 종류</label>
                        <div class="btn-grid">${serviceGrid}</div>
                    </div>
                    <div class="form-group">
                        <label>털 길이</label>
                        <div class="btn-grid">${furGrid}</div>
                    </div>
                    <div class="form-group">
                        <label>소요시간 <span class="sub-label" id="durLabel">${r.duration}분</span></label>
                        <div class="btn-grid">${durGrid}</div>
                    </div>
                    <div class="form-group res-form-full">
                        <label>금액 <span class="sub-label" id="priceLabel">${r.amount===-1?'미정':(r.amount||0).toLocaleString()+'원'}</span></label>
                        <div class="btn-grid">${priceGrid}</div>
                    </div>
                    <div class="form-group">
                        <label>결제방법</label>
                        <input type="hidden" id="editResPaymentMethod" value="${esc(r.payment_method || '')}">
                        <div class="btn-grid">
                            <button type="button" class="btn-grid-item${r.payment_method==='카드'?' active':''}" data-field="editResPaymentMethod" data-value="카드" onclick="App.selectGridBtn(this)">카드</button>
                            <button type="button" class="btn-grid-item${r.payment_method==='현금'?' active':''}" data-field="editResPaymentMethod" data-value="현금" onclick="App.selectGridBtn(this)">현금</button>
                        </div>
                    </div>
                    <div class="form-group res-form-full">
                        <label>메모 <span class="sub-label">(이 고객의 통합 메모)</span></label>
                        <textarea id="editResMemo" rows="3">${esc(r.customer_memo || r.groomer_memo || r.request || '')}</textarea>
                    </div>
                    <div class="res-form-full">
                        <button class="btn-primary" onclick="App.updateReservation()">수정 저장</button>
                    </div>
                    <div class="res-form-full" style="margin-top:8px">
                        <button class="btn-danger" onclick="App.deleteReservation(${rid})">예약 삭제</button>
                    </div>
                </div>
            `;
            openSheet('reservationSheet');
            _setupFormDirtyTracking();
        } catch (e) {
            toast('불러오기 실패', 'error');
        }
    }

    async function updateReservation() {
        const rid = document.getElementById('editResId').value;
        const memoText = document.getElementById('editResMemo').value.trim();
        const data = {
            date: document.getElementById('editResDate').value,
            time: document.getElementById('editResTime').value,
            service_type: document.getElementById('editResService').value,
            duration: Number(document.getElementById('editResDuration').value) || 0,
            amount: parseInt(document.getElementById('editResAmount').value) ?? 0,
            quoted_amount: parseInt(document.getElementById('editResAmount').value) ?? 0,
            payment_method: (document.getElementById('editResPaymentMethod') || {}).value || '',
            fur_length: document.getElementById('editResFurLength').value,
            request: '',
            groomer_memo: memoText,
        };
        if (memoText.length > 500) {
            if (!confirm(`메모가 ${memoText.length}자입니다. 500자까지만 저장됩니다. 계속하시겠습니까?`)) return;
        }

        try {
            const res = await fetch(`/api/reservation/${rid}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
            const result = await res.json();
            if (result.ok) {
                // 통합 메모: 기다리지 않고 백그라운드 동기화
                const custId = document.getElementById('editResCustId')?.value;
                if (custId) {
                    fetch(`/api/customer/${custId}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ memo: memoText }),
                    }).then(() => { cachedCustomers = null; });
                }
                // 즉시 화면 갱신
                closeSheet('reservationSheet', true);
                toast('수정되었습니다', 'success');
                if (selectedDate) selectDate(selectedDate);
                loadMonth();
                if (custId) {
                    showReservationDetail(parseInt(rid), parseInt(custId));
                }
            } else {
                toast(result.error || '수정 실패', 'error');
            }
        } catch (e) {
            toast('수정 실패', 'error');
        }
    }

    async function deleteReservation(rid) {
        if (!confirm('이 예약만 삭제합니다.\n(고객 정보는 유지됩니다)\n\n삭제하시겠습니까?')) return;
        try {
            const res = await fetch(`/api/reservation/${rid}`, { method: 'DELETE' });
            const result = await res.json();
            if (result.ok) {
                toast('예약이 삭제되었습니다');
                closeSheet('reservationSheet');
                closeSheet('unifiedDetailSheet');
                if (selectedDate) selectDate(selectedDate);
                loadMonth();
            } else {
                toast(result.error || '삭제 실패', 'error');
            }
        } catch (e) {
            toast('삭제 실패', 'error');
        }
    }

    async function changeStatus(rid, status, paymentMethod) {
        const labels = { completed: '미용 완료', cancelled: '예약 취소', no_show: '노쇼 처리', confirmed: '되돌리기' };

        // 미용 완료 시 결제방법 선택 팝업
        if (status === 'completed' && !paymentMethod) {
            const overlay = document.createElement('div');
            overlay.className = 'bottom-sheet-overlay';
            overlay.style.zIndex = '200';
            overlay.innerHTML = `
                <div class="bottom-sheet" style="max-width:340px;padding:24px;text-align:center">
                    <h3 style="margin:0 0 16px;font-size:17px">💳 결제방법 선택</h3>
                    <div style="display:flex;gap:10px">
                        <button class="btn-grid-item" style="flex:1;padding:16px;font-size:16px" onclick="this.closest('.bottom-sheet-overlay').remove(); App.changeStatus(${rid},'completed','카드')">카드</button>
                        <button class="btn-grid-item" style="flex:1;padding:16px;font-size:16px" onclick="this.closest('.bottom-sheet-overlay').remove(); App.changeStatus(${rid},'completed','현금')">현금</button>
                    </div>
                    <button style="margin-top:12px;background:none;border:none;color:var(--text-light);cursor:pointer;font-size:13px" onclick="this.closest('.bottom-sheet-overlay').remove()">취소</button>
                </div>
            `;
            document.body.appendChild(overlay);
            return;
        }

        if (status !== 'completed' && !confirm(`${labels[status]} 처리하시겠습니까?`)) return;

        try {
            const body = { status };
            if (paymentMethod) body.payment_method = paymentMethod;

            const res = await fetch(`/api/reservation/${rid}/status`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const result = await res.json();
            if (result.ok) {
                closeSheet('unifiedDetailSheet');
                toast(`${labels[status]} 처리되었습니다`, 'success');
                if (selectedDate) selectDate(selectedDate);
                loadMonth();
            } else {
                toast(result.error || '실패', 'error');
            }
        } catch (e) {
            toast('실패');
        }
    }

    // ==================== 고객 관리 ====================

    let customerSort = 'name';
    let cachedCustomers = null;

    function sortCustomers(customers, sort) {
        const arr = [...customers];
        if (sort === 'recent') {
            arr.sort((a, b) => (b.last_visit || '').localeCompare(a.last_visit || ''));
        } else {
            arr.sort((a, b) => (a.pet_name || '').localeCompare(b.pet_name || '', 'ko'));
        }
        return arr;
    }

    async function loadCustomerList(keyword, sort) {
        const container = document.getElementById('customerSearchResults');
        const q = (keyword || '').trim();
        const s = sort || customerSort;

        // 검색어 없고 캐시 있으면 서버 요청 없이 정렬만
        if (!q && cachedCustomers) {
            renderCustomerList(container, sortCustomers(cachedCustomers, s), (c) => App.showCustomerDetail(c.id));
            return;
        }

        container.innerHTML = _skeletonCustomerList();
        try {
            const res = await fetch(`/api/customers/search?q=${encodeURIComponent(q)}&sort=${s}`);
            const data = await res.json();
            if (!q) cachedCustomers = data.customers;
            renderCustomerList(container, data.customers, (c) => App.showCustomerDetail(c.id));
        } catch (e) {
            container.innerHTML = '<div style="text-align:center;padding:30px 20px"><span class="empty-emoji" aria-hidden="true">🌧️</span><p style="color:#999;margin-bottom:12px">고객 목록을 불러올 수 없습니다</p><button class="btn-secondary" style="width:auto;margin-top:12px;padding:10px 24px" onclick="App.loadCustomerList(\'\',App.customerSort)">다시 시도</button></div>';
        }
    }

    async function searchCustomers(keyword) {
        clearTimeout(searchTimer);
        const clearBtn = document.getElementById('searchClear');
        if (clearBtn) clearBtn.style.display = (keyword || '').trim() ? 'flex' : 'none';
        if (!(keyword || '').trim()) {
            loadCustomerList('', customerSort);
            return;
        }
        searchTimer = setTimeout(() => loadCustomerList(keyword, customerSort), 300);
    }

    function setCustomerSort(sort) {
        customerSort = sort;
        document.querySelectorAll('.sort-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.sort === sort);
        });
        const keyword = document.getElementById('customerSearchInput').value;
        loadCustomerList(keyword, sort);
    }

    function renderCustomerList(container, customers, onClick) {
        if (!customers.length) {
            container.innerHTML = '<div style="text-align:center;padding:30px 20px"><span class="empty-emoji" aria-hidden="true">🐾</span><p style="color:var(--text-light);margin-bottom:12px">아직 등록된 친구가 없어요</p><button class="btn-primary-sm" onclick="App.showNewCustomerForm()" style="padding:10px 20px">🐾 신규 고객 등록</button></div>';
            return;
        }

        // 같은 전화번호 반려견 그룹 (이름 표시용)
        const phonePets = {};
        for (const c of customers) {
            if (c.phone) {
                if (!phonePets[c.phone]) phonePets[c.phone] = [];
                phonePets[c.phone].push({ pet_name: c.pet_name, breed: c.breed || '' });
            }
        }

        container.innerHTML = customers.map((c, i) => {
            const initial = (c.pet_name || '?')[0];
            const ac = avatarColor(c.pet_name);
            const meta = [];
            if (c.phone_display) meta.push(c.phone_display);
            if (c.last_visit) meta.push(`마지막 방문: ${c.last_visit}`);
            if (c.visit_count) meta.push(`${c.visit_count}회 방문`);
            // 같은 집 다른 반려견 표시
            const siblings = (phonePets[c.phone] || []).filter(p => p.pet_name !== c.pet_name);
            const siblingHtml = siblings.map(s =>
                `<span class="sibling-tag">${esc(s.pet_name)}<span class="breed">${esc(s.breed)}</span></span>`
            ).join('');
            // 몸무게·메모 라인
            const petDetail = [];
            if (c.weight) petDetail.push(`${c.weight}kg`);
            if (c.notes) petDetail.push(c.notes);
            if (c.memo) petDetail.push(c.memo);
            const detailHtml = petDetail.length
                ? `<div class="customer-detail">${esc(petDetail.join(' · '))}</div>` : '';

            return `
                <div class="customer-card" data-idx="${i}">
                    <div class="customer-avatar" style="background:${ac.bg};color:${ac.fg}">${esc(initial)}</div>
                    <div class="customer-info">
                        <div class="customer-name">
                            ${esc(c.pet_name)}
                            <span class="breed">${esc(c.breed || '')}</span>
                            ${siblingHtml}
                        </div>
                        ${detailHtml}
                        <div class="customer-meta">${esc(meta.join(' | '))}</div>
                    </div>
                </div>
            `;
        }).join('');

        // 이벤트 위임으로 클릭 처리
        container.onclick = (e) => {
            const card = e.target.closest('.customer-card[data-idx]');
            if (card) onClick(customers[parseInt(card.dataset.idx)]);
        };
    }

    function showNewCustomerForm(callback) {
        showCustomerForm(null, callback);
    }

    function showCustomerForm(customer, onSaved) {
        const isEdit = !!(customer && customer.id);
        const isSibling = !!(customer && customer._isSibling);
        document.getElementById('customerFormTitle').textContent =
            isEdit ? '✏️ 고객 정보 수정' : (isSibling ? '🐾 형제견 추가' : '🐾 신규 고객 등록');

        const c = customer || {};
        const breedValue = c.breed || '';

        let formHtml;
        if (isSibling) {
            // 형제견 추가: 간소화 폼 (전화번호/유입경로 자동, 이름+몸무게만)
            formHtml = `
                <input type="hidden" id="cfChannel" value="${esc(c.channel || '')}">
                <input type="hidden" id="cfPhone" value="${esc(c.phone || '')}">
                <input type="hidden" id="cfName" value="${esc(c.name || '')}">
                <div style="padding:8px 0 12px;color:var(--text-light);font-size:13px">
                    📞 ${esc(c.phone_display || c.phone || '')} 의 형제견을 추가합니다
                </div>
                <div class="form-group">
                    <label>이름 견종 *</label>
                    <input type="text" id="cfPetBreed" value="" placeholder="예: 루미 말티푸" autocomplete="off" autofocus>
                </div>
                <div class="form-group">
                    <label>몸무게 (kg)</label>
                    <input type="number" id="cfWeight" value="" step="0.1" placeholder="예: 3.5">
                </div>
                <button class="btn-primary" onclick="App.saveCustomer(false, '${typeof onSaved === 'function' ? 'callback' : ''}')">형제견 등록</button>
            `;
        } else if (isEdit) {
            // 수정 폼: 신규와 동일한 필드 구조
            const petBreedVal = [c.pet_name, c.breed].filter(Boolean).join(' ');
            formHtml = `
                <input type="hidden" id="cfId" value="${c.id}">
                <div class="form-group">
                    <label>유입경로</label>
                    <input type="hidden" id="cfChannel" value="${esc(c.channel || '')}">
                    <div class="btn-grid channel-grid">
                        ${['방문','카카오채널','카톡채팅','네이버톡톡','전화','인스타DM','문자'].map(ch =>
                            `<button type="button" class="btn-grid-item${ch===(c.channel||'')?' active':''}" onclick="App.selectChannel(this,'${ch}')">${ch}</button>`
                        ).join('')}
                    </div>
                </div>
                <div class="form-group">
                    <label>전화번호 *</label>
                    <input type="tel" id="cfPhone" value="${esc(c.phone_display || c.phone || '')}" placeholder="010-0000-0000" inputmode="tel" oninput="App.formatPhoneInput(this)">
                </div>
                <input type="hidden" id="cfName" value="${esc(c.name || '')}">
                <div class="form-group">
                    <label>이름 견종 *</label>
                    <input type="text" id="cfPetBreed" value="${esc(petBreedVal)}" placeholder="예: 루미 말티푸" autocomplete="off">
                </div>
                <div class="form-group">
                    <label>몸무게 (kg)</label>
                    <input type="number" id="cfWeight" value="${c.weight || ''}" step="0.1" placeholder="예: 3.5">
                </div>
                <div class="form-group">
                    <label>보조연락처</label>
                    <input type="tel" id="cfPhone2" value="${esc(c.phone2_display || c.phone2 || '')}" placeholder="보조 연락처" inputmode="tel" oninput="App.formatPhoneInput(this)">
                </div>
                <div class="form-group">
                    <label>메모</label>
                    <textarea id="cfMemo" rows="2" placeholder="알러지, 주의사항 등">${esc(c.memo || '')}</textarea>
                </div>
                <div class="form-group">
                    <label>참고사진</label>
                    <div id="cfPhotoPreview" class="photo-preview-grid"></div>
                    <button type="button" class="btn-outline" onclick="App.addRefPhoto(${c.id})">📷 참고사진 추가</button>
                    <input type="file" id="cfPhotoInput" accept="image/*" style="display:none" onchange="App.handlePhotoSelect(this, ${c.id})">
                </div>
                <button class="btn-primary" onclick="App.saveCustomer(true, '${typeof onSaved === 'function' ? 'callback' : ''}')">${'수정 저장'}</button>
                <button class="btn-danger" onclick="App.deleteCustomer(${c.id})">삭제</button>
            `;
        } else {
            // 신규 폼: 유입경로 + 기본 필드
            formHtml = `
                <div class="form-group">
                    <label>유입경로</label>
                    <input type="hidden" id="cfChannel" value="">
                    <div class="btn-grid channel-grid">
                        ${['방문','카카오채널','카톡채팅','네이버톡톡','전화','인스타DM','문자'].map(ch =>
                            `<button type="button" class="btn-grid-item" onclick="App.selectChannel(this,'${ch}')">${ch}</button>`
                        ).join('')}
                    </div>
                </div>
                <div class="form-group">
                    <label>전화번호 *</label>
                    <input type="tel" id="cfPhone" value="${esc(c.phone_display || c.phone || '')}" placeholder="010-0000-0000" inputmode="tel" oninput="App.formatPhoneInput(this)">
                </div>
                <input type="hidden" id="cfName" value="${esc(c.name || '')}">
                <div class="form-group">
                    <label>이름 견종 *</label>
                    <input type="text" id="cfPetBreed" value="${esc(c.pet_name ? (c.pet_name + (c.breed ? ' ' + c.breed : '')) : '')}" placeholder="예: 루미 말티푸" autocomplete="off">
                </div>
                <div class="form-group">
                    <label>몸무게 (kg)</label>
                    <input type="number" id="cfWeight" value="${c.weight || ''}" step="0.1" placeholder="예: 3.5">
                </div>
                <div class="form-group">
                    <label>메모</label>
                    <textarea id="cfMemo" rows="2" placeholder="알러지, 주의사항 등">${esc(c.memo || '')}</textarea>
                </div>
                <button class="btn-primary" onclick="App.saveCustomer(false, '${typeof onSaved === 'function' ? 'callback' : ''}')">${'등록'}</button>
            `;
        }

        document.getElementById('customerFormContent').innerHTML = formHtml;

        // onSaved 콜백 저장
        window._customerFormCallback = onSaved || null;
        openSheet('customerFormSheet');
    }

    let breedSelIndex = -1;

    function onBreedInput(value) {
        breedSelIndex = -1;
        const container = document.getElementById('breedSuggestions');
        if (!value.trim()) {
            container.style.display = 'none';
            return;
        }
        const matches = CONFIG.breeds.filter(b =>
            b.toLowerCase().includes(value.toLowerCase())
        ).slice(0, 6);

        if (!matches.length) {
            container.style.display = 'none';
            return;
        }
        container.innerHTML = matches.map(b =>
            `<div class="breed-suggestion" onclick="App.selectBreed('${esc(b)}')">${esc(b)}</div>`
        ).join('');
        container.style.display = 'block';
    }

    function selectBreed(value) {
        document.getElementById('cfBreed').value = value;
        document.getElementById('breedSuggestions').style.display = 'none';
        breedSelIndex = -1;
    }

    function onBreedKeydown(e) {
        const container = document.getElementById('breedSuggestions');
        if (container.style.display === 'none') return;
        const items = container.querySelectorAll('.breed-suggestion');
        if (!items.length) return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            breedSelIndex = Math.min(breedSelIndex + 1, items.length - 1);
            items.forEach((el, i) => el.classList.toggle('active', i === breedSelIndex));
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            breedSelIndex = Math.max(breedSelIndex - 1, 0);
            items.forEach((el, i) => el.classList.toggle('active', i === breedSelIndex));
        } else if (e.key === 'Enter' && breedSelIndex >= 0) {
            e.preventDefault();
            selectBreed(items[breedSelIndex].textContent);
        } else if (e.key === 'Tab') {
            e.preventDefault();
            const idx = breedSelIndex >= 0 ? breedSelIndex : 0;
            selectBreed(items[idx].textContent);
        } else if (e.key === 'Escape') {
            container.style.display = 'none';
            breedSelIndex = -1;
        }
    }

    function selectChannel(btn, value) {
        btn.parentElement.querySelectorAll('.btn-grid-item').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById('cfChannel').value = value;
    }

    function _parsePetBreed(input) {
        const val = (input || '').trim();
        if (!val) return { pet_name: '', breed: '' };

        // CONFIG.breeds를 길이 긴 순으로 정렬하여 매칭
        const sortedBreeds = [...CONFIG.breeds].sort((a, b) => b.length - a.length);
        for (const breed of sortedBreeds) {
            if (val.length > breed.length && val.endsWith(breed)) {
                const petPart = val.slice(0, val.length - breed.length).trim();
                if (petPart) return { pet_name: petPart, breed: breed };
            }
            // 공백 구분자로도 체크
            const suffix = ' ' + breed;
            if (val.endsWith(suffix)) {
                const petPart = val.slice(0, val.length - suffix.length).trim();
                if (petPart) return { pet_name: petPart, breed: breed };
            }
        }

        // 매칭 안 되면 마지막 공백 기준 분리
        const lastSpace = val.lastIndexOf(' ');
        if (lastSpace > 0) {
            return { pet_name: val.slice(0, lastSpace).trim(), breed: val.slice(lastSpace + 1).trim() };
        }

        // 공백 없으면 견종만 입력한 것으로 판단 → "무명 견종"
        // 한글 1~4글자인 경우 견종으로 간주
        if (/^[가-힣]{1,4}$/.test(val)) {
            return { pet_name: '무명', breed: val };
        }
        return { pet_name: val, breed: '' };
    }

    async function saveCustomer(isEdit) {
        let data;
        if (isEdit) {
            const parsedEdit = _parsePetBreed(document.getElementById('cfPetBreed').value);
            data = {
                phone: document.getElementById('cfPhone').value,
                name: document.getElementById('cfName').value,
                pet_name: parsedEdit.pet_name,
                breed: parsedEdit.breed,
                weight: document.getElementById('cfWeight').value || null,
                age: '',
                notes: '',
                memo: document.getElementById('cfMemo').value,
                channel: (document.getElementById('cfChannel') || {}).value || '',
                phone2: (document.getElementById('cfPhone2') || {}).value || '',
            };
        } else {
            const parsed = _parsePetBreed(document.getElementById('cfPetBreed').value);
            data = {
                phone: document.getElementById('cfPhone').value,
                name: document.getElementById('cfName').value,
                pet_name: parsed.pet_name,
                breed: parsed.breed,
                weight: document.getElementById('cfWeight').value || null,
                age: '',
                notes: '',
                memo: document.getElementById('cfMemo').value,
                channel: (document.getElementById('cfChannel') || {}).value || '',
            };
        }

        try {
            let url = '/api/customer';
            let method = 'POST';
            if (isEdit) {
                const cid = document.getElementById('cfId').value;
                url = `/api/customer/${cid}`;
                method = 'PUT';
            }
            const res = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
            const result = await res.json();

            if (result.ok || result.id) {
                cachedCustomers = null;
                closeSheet('customerFormSheet');
                const baseMsg = isEdit ? '수정되었습니다' : '등록되었습니다';
                if (result.google_synced) {
                    const syncName = result.google_contact_name || '';
                    toast(baseMsg + (syncName ? ` (Google 동기화: ${syncName})` : ' (Google 동기화 완료)'), 'success');
                } else if (result.google_msg) {
                    toast(baseMsg, 'success');
                    setTimeout(() => toast('Google 동기화 실패: ' + result.google_msg, 'error'), 1500);
                } else {
                    toast(baseMsg, 'success');
                }
                // 고객 목록 자동 갱신
                if (currentView === 'customers') loadCustomerList('', customerSort);

                if (window._customerFormCallback) {
                    // 새로 생성된 고객 정보 가져오기
                    const cid = result.id || document.getElementById('cfId')?.value;
                    if (cid) {
                        const cres = await fetch(`/api/customer/${cid}`);
                        const cdata = await cres.json();
                        window._customerFormCallback(cdata);
                    }
                    window._customerFormCallback = null;
                }
            } else {
                toast(result.error || '실패', 'error');
            }
        } catch (e) {
            toast('실패');
        }
    }

    async function deleteCustomer(cid) {
        if (!confirm('⚠️ 이 고객과 모든 예약 이력이 삭제됩니다.\n(복구 불가)\n\n정말 삭제하시겠습니까?')) return;
        try {
            const res = await fetch(`/api/customer/${cid}`, { method: 'DELETE' });
            const result = await res.json();
            if (result.ok) {
                cachedCustomers = null;
                closeSheet('customerFormSheet');
                closeSheet('unifiedDetailSheet');
                toast('삭제되었습니다', 'success');
                // 고객 목록 갱신
                if (currentView === 'customers') loadCustomerList('', customerSort);
                // 캘린더 데이터도 갱신 (삭제된 고객 예약 반영)
                loadMonth();
            }
        } catch (e) {
            toast('삭제 실패', 'error');
        }
    }

    function startMemoEdit(mainCid) {
        const viewEl = document.getElementById('mergedMemoView_' + mainCid);
        const editEl = document.getElementById('mergedMemoEdit_' + mainCid);
        if (!viewEl || !editEl) return;
        viewEl.style.display = 'none';
        editEl.style.display = '';
        const ta = document.getElementById('mergedMemoTA_' + mainCid);
        if (ta) ta.focus();
    }

    function cancelMemoEdit(mainCid) {
        const viewEl = document.getElementById('mergedMemoView_' + mainCid);
        const editEl = document.getElementById('mergedMemoEdit_' + mainCid);
        if (!viewEl || !editEl) return;
        viewEl.style.display = '';
        editEl.style.display = 'none';
    }

    async function saveMergedMemo(mainCid, allPetIdsStr) {
        const ta = document.getElementById('memoTA_' + mainCid);
        if (!ta) return;
        const memo = ta.value.trim();
        const petIds = allPetIdsStr ? allPetIdsStr.split(',').map(Number) : [mainCid];
        try {
            for (const id of petIds) {
                await fetch(`/api/customer/${id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ memo }),
                });
            }
            toast('메모 저장됨', 'success');
            cachedCustomers = null;
            _reloadUnifiedDetail(mainCid);
        } catch (e) {
            toast('저장 실패', 'error');
        }
    }

    async function toggleKeyring(cid, value) {
        try {
            const res = await fetch(`/api/customer/${cid}/keyring`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ keyring: value }),
            });
            if (!res.ok) throw new Error();
            toast(value ? '키링 증정 완료' : '키링 미증정으로 변경', 'success');
            cachedCustomers = null;
            _reloadUnifiedDetail(cid);
        } catch (e) {
            toast('변경 실패', 'error');
        }
    }

    function addSiblingPet(phone, name, channel) {
        closeSheet('unifiedDetailSheet');
        showCustomerForm({ phone: phone, phone_display: phone.replace(/(\d{3})(\d{4})(\d{4})/, '$1-$2-$3'), name: name, channel: channel || '', _isSibling: true }, (newCustomer) => {
            // 형제펫 추가 후 새 펫의 상세로 진입 (통합 페이지에서 전체 가족 보임)
            if (newCustomer && newCustomer.id) {
                _reloadUnifiedDetail(newCustomer.id);
                openSheet('unifiedDetailSheet');
            }
        });
    }

    async function showCustomerForm_edit(cid) {
        try {
            const res = await fetch(`/api/customer/${cid}`);
            if (!res.ok) { toast('불러오기 실패', 'error'); return; }
            const c = await res.json();
            closeSheet('unifiedDetailSheet');
            showCustomerForm(c);
            _loadEditFormPhotos(cid);
        } catch (e) {
            toast('불러오기 실패', 'error');
        }
    }

    // ==================== 전화 관련 ====================

    async function toggleCallHistory() {
        const content = document.getElementById('callHistoryContent');
        content.innerHTML = '<div style="padding:0 16px">' + _skeletonCustomerList() + '</div>';
        openSheet('callHistorySheet');

        try {
            const res = await fetch('/api/call-history');
            const data = await res.json();
            if (!data.history || !data.history.length) {
                content.innerHTML = '<div class="empty-timeline" style="padding:30px 10px"><span class="empty-emoji" aria-hidden="true" style="font-size:40px">🐕</span><p style="font-size:13px">아직 전화가 없어요</p></div>';
                return;
            }
            content.innerHTML = data.history.map(h => {
                const name = h.c_pet_name || h.pet_name || '';
                const breed = h.breed || '';
                const datePart = h.created_at ? h.created_at.substring(5, 10) : '';
                const timePart = h.created_at ? formatTime(h.created_at.substring(11, 16)) : '';
                const phone = esc(h.phone || '');
                return `
                    <div class="history-item" onclick="App.closeSheet('callHistorySheet');App.onCallHistoryClick('${phone}')" style="cursor:pointer">
                        <span class="history-date">${esc(datePart)} ${esc(timePart)}</span>
                        <span class="history-service">${esc(h.phone_display)} ${name ? esc(name) : '(미등록)'}</span>
                        ${breed ? `<span class="history-amount">${esc(breed)}</span>` : ''}
                    </div>
                `;
            }).join('');
        } catch (e) {
            content.innerHTML = '<p style="text-align:center;color:#999;padding:20px">불러오기 실패</p>';
        }
    }

    function showCallPopup(data) {
        const popup = document.getElementById('callPopup');
        const content = document.getElementById('callPopupContent');

        // 전화 뱃지 업데이트 (SSE 수신 시에만 - type이 있을 때)
        if (data.type === 'incoming_call') {
            const badge = document.getElementById('callBadge');
            if (badge) {
                const count = parseInt(badge.textContent || '0') + 1;
                badge.textContent = count;
                badge.style.display = 'flex';
            }
        }

        if (data.is_existing) {
            const visitInfo = data.visit_count ? `${data.visit_count}회 방문` : '';
            const lastVisit = data.last_visit ? `마지막: ${data.last_visit}` : '';
            const meta = [visitInfo, lastVisit].filter(Boolean).join(' | ');
            let recentHtml = '';
            if (data.recent_reservations && data.recent_reservations.length) {
                const statusLabel = { confirmed: '예약', completed: '완료', cancelled: '취소', no_show: '노쇼' };
                recentHtml = '<div class="call-recent"><div class="call-recent-title">최근 이력</div>' +
                    data.recent_reservations.map(r => {
                        const st = statusLabel[r.status] || r.status;
                        const amt = r.amount === -1 ? ' 미정' : r.amount ? ` ${r.amount.toLocaleString()}원` : '';
                        return `<div class="call-recent-item"><span>${esc(r.date)}</span><span>${esc(r.service)}${amt}</span><span class="call-recent-status ${r.status}">${st}</span></div>`;
                    }).join('') + '</div>';
            }

            // 멀티펫: pets 배열이 2마리 이상이면 펫별 버튼 표시
            const pets = data.pets || [];
            let actionsHtml;
            if (pets.length > 1) {
                actionsHtml = '<div class="call-pet-buttons">' +
                    pets.map(p =>
                        `<button class="call-btn-reserve call-btn-pet" onclick="App.reserveFromCall(${p.id})">${esc(p.pet_name)} (${esc(p.breed)}) 예약</button>`
                    ).join('') +
                    '</div>' +
                    '<div class="call-actions"><button class="call-btn-dismiss" onclick="App.closeCallPopup()">닫기</button></div>';
            } else {
                actionsHtml = `<div class="call-actions">
                    <button class="call-btn-reserve" onclick="App.reserveFromCall(${data.customer_id})">예약하기</button>
                    <button class="call-btn-dismiss" onclick="App.closeCallPopup()">닫기</button>
                </div>`;
            }

            content.innerHTML = `
                <div class="call-info-existing">
                    <div class="call-phone">📞 ${esc(data.phone_display)}</div>
                    <div class="call-customer">🐾 ${esc(data.pet_name)} (${esc(data.breed)}) - ${esc(data.customer_name)}</div>
                    ${meta ? `<div class="call-customer">${esc(meta)}</div>` : ''}
                    ${recentHtml}
                </div>
                ${actionsHtml}
            `;
        } else {
            content.innerHTML = `
                <div class="call-info-new">
                    <div class="call-phone">📞 ${esc(data.phone_display)}</div>
                    <div class="call-customer">🆕 미등록 번호</div>
                </div>
                <div class="call-actions">
                    <button class="call-btn-reserve" onclick="App.registerFromCall('${esc(data.phone)}')">신규 등록</button>
                    <button class="call-btn-dismiss" onclick="App.closeCallPopup()">닫기</button>
                </div>
            `;
        }
        popup.style.display = 'flex';

        // 10초 후 자동 닫기
        clearTimeout(window._callPopupTimer);
        window._callPopupTimer = setTimeout(() => closeCallPopup(), 10000);
    }

    function closeCallPopup() {
        document.getElementById('callPopup').style.display = 'none';
        clearTimeout(window._callPopupTimer);
    }

    async function reserveFromCall(customerId) {
        closeCallPopup();
        try {
            const res = await fetch(`/api/customer/${customerId}`);
            const c = await res.json();
            enterBookingMode(c);
        } catch (e) {
            toast('고객 정보 로드 실패', 'error');
        }
    }

    function registerFromCall(phone) {
        closeCallPopup();
        // 고객 등록 후 콜백에서 북킹모드 진입
        showCustomerForm({ phone: phone, phone_display: phone }, (newCustomer) => {
            enterBookingMode(newCustomer);
        });
    }

    // ==================== 월 이동 ====================

    function changeMonth(delta) {
        currentMonth += delta;
        if (currentMonth > 12) { currentMonth = 1; currentYear++; }
        if (currentMonth < 1) { currentMonth = 12; currentYear--; }
        selectedDate = null;
        loadMonth();
    }

    function goToday() {
        const now = new Date();
        currentYear = now.getFullYear();
        currentMonth = now.getMonth() + 1;
        const todayStr = fmtDate(now);
        // showView 대신 직접 뷰 전환 (loadMonth 중복 방지)
        currentView = 'calendar';
        document.querySelectorAll('.nav-item').forEach(el => {
            el.classList.toggle('active', el.dataset.view === 'calendar');
        });
        document.querySelectorAll('.bottom-sheet-overlay').forEach(el => {
            if (el.style.display !== 'none' && el.id) closeSheet(el.id, true);
        });
        const calSec = document.getElementById('calendarSection');
        const tlSec = document.getElementById('timelineSection');
        const custView = document.getElementById('customerView');
        const salesView = document.getElementById('salesView');
        const leftPanel = document.querySelector('.left-panel');
        calSec.style.display = '';
        if (leftPanel) leftPanel.style.display = '';
        tlSec.style.display = 'none';
        custView.style.display = 'none';
        salesView.style.display = 'none';
        document.querySelector('.main-content')?.classList.remove('split-view');
        document.querySelector('.calendar-section')?.classList.remove('collapsed');
        selectedDate = todayStr;
        if (isPC()) {
            loadMonth();
        } else {
            loadMonth().then(() => selectDate(todayStr));
        }
    }

    // ==================== 스와이프 ====================

    function setupSwipe() {
        let startX = 0, startY = 0;
        const el = document.querySelector('.calendar-section');
        el.addEventListener('touchstart', e => {
            if (isPC()) return;
            startX = e.touches[0].clientX;
            startY = e.touches[0].clientY;
        }, { passive: true });
        el.addEventListener('touchend', e => {
            if (isPC()) return;
            const dx = e.changedTouches[0].clientX - startX;
            const dy = e.changedTouches[0].clientY - startY;
            if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5) {
                if (dx > 0) changeMonth(-1);
                else changeMonth(1);
            }
        }, { passive: true });
    }

    // ==================== 유틸 ====================

    function formatPhoneInput(input) {
        let digits = input.value.replace(/\D/g, '');
        if (digits.length > 11) digits = digits.slice(0, 11);
        let formatted = digits;
        if (digits.length >= 8) {
            formatted = digits.slice(0, 3) + '-' + digits.slice(3, 7) + '-' + digits.slice(7);
        } else if (digits.length >= 4) {
            formatted = digits.slice(0, 3) + '-' + digits.slice(3);
        }
        const cursor = input.selectionStart;
        const prevLen = input.value.length;
        input.value = formatted;
        const diff = formatted.length - prevLen;
        input.setSelectionRange(cursor + diff, cursor + diff);
    }

    const AVATAR_COLORS = [
        { bg: '#EEF2FF', fg: '#4F46E5' }, // 인디고
        { bg: '#FEF3C7', fg: '#D97706' }, // 앰버
        { bg: '#DCFCE7', fg: '#16A34A' }, // 그린
        { bg: '#FFE4E6', fg: '#E11D48' }, // 로즈
        { bg: '#E0E7FF', fg: '#4338CA' }, // 바이올렛
        { bg: '#FEE2E2', fg: '#DC2626' }, // 레드
        { bg: '#DBEAFE', fg: '#2563EB' }, // 블루
        { bg: '#F3E8FF', fg: '#9333EA' }, // 퍼플
        { bg: '#CCFBF1', fg: '#0D9488' }, // 틸
        { bg: '#FFF7ED', fg: '#EA580C' }, // 오렌지
    ];
    function avatarColor(name) {
        let h = 0;
        for (let i = 0; i < (name || '').length; i++) h = ((h << 5) - h + name.charCodeAt(i)) | 0;
        return AVATAR_COLORS[Math.abs(h) % AVATAR_COLORS.length];
    }

    function _skeletonTimeline() {
        let html = '<div style="padding:16px">';
        for (let i = 0; i < 6; i++) {
            html += '<div class="skeleton-slot"><div class="skeleton skeleton-time"></div><div class="skeleton skeleton-bar"></div></div>';
        }
        return html + '</div>';
    }

    function _skeletonCustomerList() {
        let html = '';
        for (let i = 0; i < 8; i++) {
            html += '<div class="skeleton-card"><div class="skeleton skeleton-avatar"></div><div class="skeleton-lines"><div class="skeleton skeleton-line" style="width:' + (60 + Math.random()*30) + '%"></div><div class="skeleton skeleton-line"></div></div></div>';
        }
        return html;
    }

    function _slotDiff(a, b) {
        const [ah, am] = a.split(':').map(Number);
        const [bh, bm] = b.split(':').map(Number);
        return (bh * 60 + bm) - (ah * 60 + am);
    }
    function _slotAdd(slot, minutes) {
        const [h, m] = slot.split(':').map(Number);
        const total = h * 60 + m + minutes;
        return `${String(Math.floor(total/60)).padStart(2,'0')}:${String(total%60).padStart(2,'0')}`;
    }

    function _renderClockChart(slots, booked, items) {
        const cx = 80, cy = 80, r = 62, rInner = 38, rLabel = 74;
        const total = slots.length;
        if (!total) return '';

        // 시작/끝 시간 (분 단위)
        const [sh, sm] = slots[0].split(':').map(Number);
        const [eh, em] = slots[total-1].split(':').map(Number);
        const startMin = sh * 60 + sm;
        const endMin = eh * 60 + em + CONFIG.slotInterval;
        const span = endMin - startMin;

        function arcPath(startFrac, endFrac, outerR, innerR) {
            const s = (startFrac * 360 - 90) * Math.PI / 180;
            const e = (endFrac * 360 - 90) * Math.PI / 180;
            const largeArc = (endFrac - startFrac) > 0.5 ? 1 : 0;
            const x1 = cx + outerR * Math.cos(s), y1 = cy + outerR * Math.sin(s);
            const x2 = cx + outerR * Math.cos(e), y2 = cy + outerR * Math.sin(e);
            const x3 = cx + innerR * Math.cos(e), y3 = cy + innerR * Math.sin(e);
            const x4 = cx + innerR * Math.cos(s), y4 = cy + innerR * Math.sin(s);
            return `M${x1},${y1} A${outerR},${outerR} 0 ${largeArc} 1 ${x2},${y2} L${x3},${y3} A${innerR},${innerR} 0 ${largeArc} 0 ${x4},${y4} Z`;
        }

        let arcs = '';
        // 빈 슬롯 (연한 배경)
        const freeColor = '#E8F5E9';
        const bookedColor = '#4F46E5';
        const bossColor = '#EF4444';
        const completedColor = '#22C55E';

        for (let i = 0; i < total; i++) {
            const slotTime = slots[i];
            const [th, tm] = slotTime.split(':').map(Number);
            const min = th * 60 + tm;
            const frac1 = (min - startMin) / span;
            const frac2 = (min - startMin + CONFIG.slotInterval) / span;
            const res = booked[slotTime];
            let color = freeColor;
            if (res) {
                const isBoss = res.customer_id === CONFIG.bossCustomerId;
                color = isBoss ? bossColor : res.status === 'completed' ? completedColor : bookedColor;
            }
            arcs += `<path d="${arcPath(frac1, frac2, r, rInner)}" fill="${color}" stroke="#fff" stroke-width="1"/>`;
        }

        // 시간 라벨 (정시만)
        let labels = '';
        const hours = new Set();
        for (const s of slots) {
            const [h] = s.split(':').map(Number);
            hours.add(h);
        }
        // 마지막 시간도 추가
        hours.add(Math.floor(endMin / 60));
        for (const h of hours) {
            const min = h * 60;
            if (min < startMin || min > endMin) continue;
            const frac = (min - startMin) / span;
            const ang = (frac * 360 - 90) * Math.PI / 180;
            const lx = cx + rLabel * Math.cos(ang);
            const ly = cy + rLabel * Math.sin(ang);
            const hLabel = h < 12 ? `오전${h}` : h === 12 ? `오후12` : `오후${h-12}`;
            labels += `<text x="${lx}" y="${ly}" text-anchor="middle" dominant-baseline="central" font-size="8" fill="#94A3B8" font-weight="500">${hLabel}</text>`;
        }

        // 중앙 텍스트
        const bookedCount = items.filter(r => r.customer_id !== CONFIG.bossCustomerId).length;
        const freeCount = slots.filter(s => !booked[s]).length;
        const freeHrs = (freeCount * CONFIG.slotInterval / 60);
        const freeLabel = freeHrs % 1 === 0 ? freeHrs + '시간' : freeHrs.toFixed(1) + '시간';

        return `<div class="clock-chart-wrap">
            <svg viewBox="0 0 160 160" class="clock-chart">
                ${arcs}${labels}
                <text x="${cx}" y="${cy - 8}" text-anchor="middle" font-size="11" font-weight="700" fill="#1E293B">${bookedCount}건</text>
                <text x="${cx}" y="${cy + 8}" text-anchor="middle" font-size="10" fill="#64748B">빈 ${freeLabel}</text>
            </svg>
            <div class="clock-legend">
                <span><i style="background:${bookedColor}"></i>예약</span>
                <span><i style="background:${completedColor}"></i>완료</span>
                <span><i style="background:${bossColor}"></i>휴무</span>
                <span><i style="background:${freeColor};border:1px solid #C8E6C9"></i>빈시간</span>
            </div>
        </div>`;
    }

    function generateTimeSlots() {
        const slots = [];
        const [sh, sm] = CONFIG.businessStart.split(':').map(Number);
        const [eh, em] = CONFIG.businessEnd.split(':').map(Number);
        let current = sh * 60 + sm;
        const last = eh * 60 + em;
        while (current <= last) {
            const h = Math.floor(current / 60);
            const m = current % 60;
            slots.push(`${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`);
            current += CONFIG.slotInterval;
        }
        return slots;
    }

    function formatTime(timeStr) {
        if (!timeStr) return '';
        const [h, m] = timeStr.split(':').map(Number);
        const period = h < 12 ? '오전' : '오후';
        const h12 = h === 0 ? 12 : h > 12 ? h - 12 : h;
        return `${period} ${h12}:${String(m).padStart(2, '0')}`;
    }

    function fmtDate(d) {
        return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
    }

    function esc(s) {
        if (!s) return '';
        return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
    }

    const _closeTimers = {};

    function openSheet(id) {
        if (_closeTimers[id]) {
            clearTimeout(_closeTimers[id]);
            delete _closeTimers[id];
        }
        const overlay = document.getElementById(id);
        overlay.style.display = 'flex';
        const sheet = overlay.querySelector('.bottom-sheet');
        if (sheet) {
            sheet.style.transform = '';
            sheet.style.transition = '';
            _setupSheetSwipe(overlay, sheet);
        }
    }

    function closeSheet(id, force) {
        const overlay = document.getElementById(id);
        // 미저장 경고: reservationSheet에서 폼 변경 감지
        if (!force && id === 'reservationSheet') {
            const form = document.getElementById('reservationForm');
            if (form && form.dataset.dirty === '1') {
                if (!confirm('수정 사항이 저장되지 않았습니다. 닫으시겠습니까?')) return;
            }
        }
        const sheet = overlay.querySelector('.bottom-sheet');
        if (sheet) {
            sheet.style.transition = 'transform 0.2s ease';
            sheet.style.transform = 'translateY(100%)';
            _closeTimers[id] = setTimeout(() => {
                overlay.style.display = 'none';
                sheet.style.transform = '';
                sheet.style.transition = '';
                delete _closeTimers[id];
            }, 200);
        } else {
            overlay.style.display = 'none';
        }
    }

    function _setupSheetSwipe(overlay, sheet) {
        if (sheet._swipeSetup) return;
        sheet._swipeSetup = true;

        let startY = 0, currentY = 0, isDragging = false, dragSource = '';

        // 헤더 + 핸들 영역에서 드래그 시작
        const header = sheet.querySelector('.sheet-header') || sheet.querySelector('.sheet-handle');
        if (header) {
            header.classList.add('sheet-drag-area');
            header.addEventListener('touchstart', (e) => {
                if (isPC()) return;
                startY = e.touches[0].clientY;
                isDragging = true;
                dragSource = 'header';
                sheet.style.transition = 'none';
            }, { passive: true });
        }

        // 시트 본문: 스크롤이 맨 위일 때만 아래 스와이프로 닫기
        sheet.addEventListener('touchstart', (e) => {
            if (isPC()) return;
            if (isDragging) return;
            if (sheet.scrollTop <= 0) {
                startY = e.touches[0].clientY;
                dragSource = 'body';
            }
        }, { passive: true });

        sheet.addEventListener('touchmove', (e) => {
            if (isPC()) return;
            if (dragSource === 'header' && isDragging) {
                currentY = e.touches[0].clientY - startY;
                if (currentY > 0) {
                    sheet.style.transform = `translateY(${currentY}px)`;
                }
                return;
            }
            if (dragSource === 'body' && sheet.scrollTop <= 0) {
                currentY = e.touches[0].clientY - startY;
                if (currentY > 30 && !isDragging) {
                    isDragging = true;
                    sheet.style.transition = 'none';
                }
                if (isDragging && currentY > 0) {
                    e.preventDefault();
                    sheet.style.transform = `translateY(${currentY}px)`;
                }
            }
        }, { passive: false });

        sheet.addEventListener('touchend', () => {
            if (!isDragging) { currentY = 0; dragSource = ''; return; }
            isDragging = false;
            sheet.style.transition = 'transform 0.2s ease';
            if (currentY > 80) {
                closeSheet(overlay.id);
            } else {
                sheet.style.transform = '';
            }
            currentY = 0;
            dragSource = '';
        }, { passive: true });

        // 오버레이 배경 탭으로 닫기
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                closeSheet(overlay.id);
            }
        });
    }

    function downloadBackup() {
        window.location.href = '/api/backup';
    }

    function copyIntakeForm() {
        const text = `안녕하세요~ 쫑긋입니다!

간단하게 적어주시면 상담 도와드릴게요.

견종:
몸무게:
미용 스타일 & 사진:
희망 날짜/시간:

재방문 고객님은 날짜/시간만 알려주세요.`;

        navigator.clipboard.writeText(text).then(() => {
            toast('예약 양식이 복사되었습니다!');
        }).catch(() => {
            // fallback for older browsers
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
            toast('예약 양식이 복사되었습니다!');
        });
    }

    function toast(msg, type) {
        const prefix = type === 'success' ? '✅ ' : type === 'error' ? '❌ ' : '';
        const el = document.createElement('div');
        el.className = 'toast' + (type ? ' toast-' + type : '');
        el.setAttribute('role', 'alert');
        el.textContent = prefix + msg;
        document.body.appendChild(el);
        setTimeout(() => {
            el.style.transition = 'opacity 0.3s ease';
            el.style.opacity = '0';
            setTimeout(() => el.remove(), 300);
        }, 2200);
    }

    // ==================== PC 전용 ====================

    function startClock() {
        const el = document.getElementById('pcClock');
        if (!el) return;
        function tick() {
            const now = new Date();
            el.textContent = String(now.getHours()).padStart(2,'0') + ':' + String(now.getMinutes()).padStart(2,'0');
        }
        tick();
        setInterval(tick, 30000);
    }

    function updateStatsBar(data) {
        if (!isPC()) return;
        const dateEl = document.getElementById('statsDate');
        const infoEl = document.getElementById('statsInfo');
        if (!dateEl || !infoEl) return;
        const items = data.reservations || [];
        const confirmed = items.filter(r => r.status === 'confirmed').length;
        const completed = items.filter(r => r.status === 'completed').length;
        const todaySales = items.filter(r => r.status === 'completed' && r.amount > 0)
            .reduce((sum, r) => sum + r.amount, 0);
        const date = new Date(data.date + 'T00:00:00');
        const dow = WEEKDAYS_KR[date.getDay()];
        const parts = data.date.split('-');
        dateEl.textContent = parts[1] + '/' + parts[2] + '(' + dow + ')';
        let info = '예약 ' + confirmed + ' 완료 ' + completed;
        if (todaySales > 0) info += ' · ' + todaySales.toLocaleString() + '원';
        infoEl.textContent = info;
    }

    async function loadCallSidebar() {
        if (!isPC()) return;
        const container = document.getElementById('callSidebarList');
        if (!container) return;
        const targetDate = callSidebarDate || fmtDate(new Date());
        const dateLabel = document.getElementById('callSidebarDate');
        if (dateLabel) {
            dateLabel.textContent = (targetDate === fmtDate(new Date())) ? '오늘' : targetDate.substring(5);
        }
        try {
            const res = await fetch(`/api/call-history?date=${targetDate}`);
            const data = await res.json();
            const filtered = data.history || [];
            if (!filtered.length) {
                container.innerHTML = '<div class="empty-timeline" style="padding:30px 10px"><span class="empty-emoji" aria-hidden="true" style="font-size:40px">🐕</span><p style="font-size:13px">아직 전화가 없어요</p></div>';
                return;
            }
            container.innerHTML = filtered.map(h => {
                const isKnown = !!(h.c_pet_name || h.pet_name);
                const name = h.c_pet_name || h.pet_name || '';
                const rawTime = h.created_at ? h.created_at.substring(11, 16) : '';
                const time = rawTime ? formatTime(rawTime) : '';
                const cls = isKnown ? 'known' : 'unknown';
                const phone = esc(h.phone || '');
                return '<div class="call-sidebar-item ' + cls + '" onclick="App.onCallHistoryClick(\'' + phone + '\')">' +
                    '<span class="call-sidebar-time">' + esc(time) + ' ' + (name ? esc(name) : '신규') + '</span>' +
                    '<span class="call-sidebar-phone">' + esc(h.phone_display) + '</span>' +
                    '</div>';
            }).join('');
        } catch (e) {
            console.error('call-sidebar load error:', e);
            container.innerHTML = '<p style="text-align:center;color:#999;padding:12px;font-size:12px">로드 실패: ' + esc(e.message) + '</p>';
        }
    }

    function changeCallDate(delta) {
        const current = callSidebarDate ? new Date(callSidebarDate + 'T00:00:00') : new Date();
        current.setDate(current.getDate() + delta);
        callSidebarDate = fmtDate(current);
        loadCallSidebar();
    }

    function refresh(silent) {
        loadMonth();
        if (selectedDate) selectDate(selectedDate);
        if (isPC()) loadCallSidebar();
        if (!silent) toast('새로고침');
    }

    // ── 다른 기기 변경 감지 (폴링) ──
    let _lastUpdateTs = 0;
    (function pollUpdates() {
        const INTERVAL = 15000; // 15초
        async function check() {
            try {
                const res = await fetch('/api/last-update');
                if (!res.ok) return;
                const data = await res.json();
                if (_lastUpdateTs && data.ts > _lastUpdateTs) {
                    refresh(true); // 조용히 새로고침
                }
                _lastUpdateTs = data.ts;
            } catch (e) { /* 네트워크 오류 무시 */ }
        }
        check(); // 초기값 세팅
        setInterval(check, INTERVAL);
    })();

    async function testCall() {
        const phone = prompt('테스트 전화번호 입력:', '01084247395');
        if (!phone) return;
        try {
            const res = await fetch('/api/incoming-call?key=' + encodeURIComponent(CONFIG.taskerKey || ''), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ phone: phone }),
            });
            const result = await res.json();
            if (result.ok) {
                toast('테스트 전화 발신: ' + phone);
                if (isPC()) loadCallSidebar();
            } else {
                toast('실패: ' + (result.error || ''));
            }
        } catch (e) {
            toast('테스트 실패', 'error');
        }
    }

    function onQuickReserve() {
        // 항상 날짜 선택부터 시작
        showDatePicker();
    }

    function onQuickReserveForDate() {
        // 빈 타임라인에서 호출: 이미 선택된 날짜로 바로 시간 선택
        if (!selectedDate) selectedDate = fmtDate(new Date());
        showTimeSlotPicker();
    }

    let _datePickerOffset = 0; // 0 = 이번달~, 1 = 다음달~, ...

    function showDatePicker(monthOffset) {
        if (monthOffset !== undefined) _datePickerOffset = monthOffset;
        else _datePickerOffset = 0;
        _renderDatePicker();
    }

    async function _renderDatePicker() {
        const today = new Date();
        const todayStr = fmtDate(today);
        // 표시할 월 계산
        const baseMonth = new Date(today.getFullYear(), today.getMonth() + _datePickerOffset, 1);
        const year = baseMonth.getFullYear();
        const month = baseMonth.getMonth(); // 0-based
        const monthLabel = `${year}.${String(month + 1).padStart(2, '0')}`;

        // 월의 첫날, 마지막날
        const firstDay = new Date(year, month, 1);
        const lastDay = new Date(year, month + 1, 0);

        // 해당 월의 휴무일 데이터 가져오기
        let pickerNames = {};
        if (year === currentYear && (month + 1) === currentMonth) {
            pickerNames = monthData.names || {};
        } else {
            try {
                const res = await fetch(`/api/month?y=${year}&m=${month + 1}`);
                if (res.ok) { const d = await res.json(); pickerNames = d.names || {}; }
            } catch (e) { /* ignore */ }
        }

        // 휴무일 세트 구성
        const bossDates = new Set();
        for (const [dateStr, entries] of Object.entries(pickerNames)) {
            if (entries.some(e => e.is_boss)) bossDates.add(dateStr);
        }

        let html = `<p style="font-size:14px;color:var(--text-secondary);margin-bottom:12px;font-weight:600">📅 날짜를 선택하세요</p>`;

        // 월 네비게이션
        html += `<div style="display:flex;align-items:center;justify-content:center;gap:16px;margin-bottom:10px">`;
        if (_datePickerOffset > 0) {
            html += `<button onclick="App.changePickerMonth(-1)" style="font-size:18px;background:none;border:none;cursor:pointer;padding:4px 8px;color:var(--text)">‹</button>`;
        } else {
            html += `<span style="width:30px"></span>`;
        }
        html += `<span style="font-size:16px;font-weight:700;min-width:80px;text-align:center">${monthLabel}</span>`;
        html += `<button onclick="App.changePickerMonth(1)" style="font-size:18px;background:none;border:none;cursor:pointer;padding:4px 8px;color:var(--text)">›</button>`;
        html += `</div>`;

        // 요일 헤더
        html += '<div class="date-picker-grid" style="margin-bottom:4px">';
        for (const dow of WEEKDAYS_KR) {
            const cls = dow === '일' ? 'sun' : dow === '토' ? 'sat' : '';
            html += `<div class="date-pick-dow-header ${cls}">${dow}</div>`;
        }
        html += '</div>';

        // 날짜 그리드
        html += '<div class="date-picker-grid">';
        // 빈 칸 (첫째 날 요일까지)
        for (let i = 0; i < firstDay.getDay(); i++) {
            html += `<div></div>`;
        }
        for (let day = 1; day <= lastDay.getDate(); day++) {
            const d = new Date(year, month, day);
            const dateStr = fmtDate(d);
            const isPast = dateStr < todayStr;
            const isToday = dateStr === todayStr;
            const isSun = d.getDay() === 0;
            const isSat = d.getDay() === 6;
            const dowCls = isSun ? 'sun' : isSat ? 'sat' : '';
            const isBoss = bossDates.has(dateStr);

            if (isPast) {
                html += `<button class="date-pick-btn disabled ${dowCls}" disabled>
                    <span class="date-pick-day">${day}</span>
                </button>`;
            } else {
                html += `<button class="date-pick-btn ${dowCls}${isToday ? ' today' : ''}${isBoss ? ' boss-day' : ''}" onclick="App.onDatePick('${dateStr}')">
                    <span class="date-pick-day">${day}</span>
                    ${isBoss ? '<span class="date-pick-dow" style="color:#EF4444">🏖️</span>' : (isToday ? '<span class="date-pick-dow">오늘</span>' : '')}
                </button>`;
            }
        }
        html += '</div>';

        document.getElementById('timeSlotContent').innerHTML = html;
        openSheet('timeSlotSheet');
    }

    function changePickerMonth(dir) {
        _datePickerOffset += dir;
        if (_datePickerOffset < 0) _datePickerOffset = 0;
        _renderDatePicker();
    }

    function onDatePick(dateStr) {
        selectedDate = dateStr;
        showTimeSlotPicker();
    }

    async function showTimeSlotPicker() {
        const slots = generateTimeSlots();
        const COLS = 4;

        // 기존 예약 조회 → 슬롯별 매핑
        let existingRes = [];
        const slotMap = {}; // slot -> { res, isFirst }
        try {
            const res = await fetch(`/api/day?date=${selectedDate}`);
            if (res.ok) {
                const data = await res.json();
                existingRes = data.reservations || [];
                for (const r of existingRes) {
                    const [sh, sm] = r.time.split(':').map(Number);
                    const startMin = sh * 60 + sm;
                    const nSlots = Math.max(1, Math.ceil(r.duration / CONFIG.slotInterval));
                    for (let s = 0; s < nSlots; s++) {
                        const t = startMin + s * CONFIG.slotInterval;
                        const ts = `${String(Math.floor(t/60)).padStart(2,'0')}:${String(t%60).padStart(2,'0')}`;
                        if (slots.includes(ts)) {
                            slotMap[ts] = { res: r, isFirst: s === 0, resId: r.id };
                        }
                    }
                }
            }
        } catch (e) { /* 네트워크 오류 시 빈 슬롯으로 진행 */ }

        // 그리드 렌더링 — 예약된 칸 합치기
        let slotHtml = '<div class="time-slot-grid">';
        const rendered = new Set();

        for (let row = 0; row * COLS < slots.length; row++) {
            const rowStart = row * COLS;
            const rowEnd = Math.min(rowStart + COLS, slots.length);
            let col = rowStart;

            while (col < rowEnd) {
                const slot = slots[col];

                if (rendered.has(slot)) { col++; continue; }

                const info = slotMap[slot];
                if (info) {
                    // 같은 예약의 연속 슬롯 수 계산 (이 행 내에서)
                    let span = 0;
                    for (let j = col; j < rowEnd; j++) {
                        const si = slotMap[slots[j]];
                        if (si && si.resId === info.resId) {
                            span++;
                            rendered.add(slots[j]);
                        } else break;
                    }

                    const r = info.res;
                    const isBoss = r.customer_phone === 'BOSS';
                    const bossClass = isBoss ? ' boss-block' : '';
                    const nameLabel = isBoss ? '🏖️ 휴무' : esc(r.pet_name);
                    if (info.isFirst) {
                        slotHtml += `<div class="time-slot-btn booked-block${bossClass}" style="grid-column:span ${span}" onclick="App.onBookedSlotClick()">
                            <span class="booked-time">${formatTime(r.time)}~${formatTime(r.end_time)}</span>
                            <span class="booked-name">${nameLabel}</span>
                        </div>`;
                    } else {
                        slotHtml += `<div class="time-slot-btn booked-block${bossClass} cont" style="grid-column:span ${span}" onclick="App.onBookedSlotClick()">
                            <span class="booked-time">${formatTime(r.time)}~${formatTime(r.end_time)}</span>
                            <span class="booked-name">${nameLabel}</span>
                        </div>`;
                    }
                    col += span;
                } else {
                    // 빈 슬롯
                    slotHtml += `<button class="time-slot-btn" onclick="App.onSlotClick('${slot}');App.closeSheet('timeSlotSheet')">${formatTime(slot)}</button>`;
                    col++;
                }
            }
        }
        slotHtml += '</div>';

        document.getElementById('timeSlotContent').innerHTML = `
            <p style="font-size:14px;color:var(--text-secondary);margin-bottom:12px;font-weight:600">
                📅 ${selectedDate} — 시간을 선택하세요
                <button onclick="App.showDatePicker()" style="margin-left:8px;font-size:12px;color:var(--primary);background:var(--primary-light);border:none;border-radius:6px;padding:3px 8px;cursor:pointer">날짜변경</button>
            </p>
            ${slotHtml}
        `;
        openSheet('timeSlotSheet');
    }

    // ==================== 수신기록 클릭 ====================

    async function onCallHistoryClick(phone) {
        if (!phone) return;
        const unknownPopup = {
            phone: phone,
            phone_display: phone.replace(/(\d{3})(\d{4})(\d{4})/, '$1-$2-$3'),
            is_existing: false,
        };
        try {
            const res = await fetch(`/api/customer/by-phone?phone=${encodeURIComponent(phone)}`);
            const data = await res.json();
            const c = data.customer;
            if (c && c.id) {
                showCallPopup({
                    phone: phone,
                    phone_display: c.phone_display || phone,
                    is_existing: true,
                    customer_id: c.id,
                    customer_name: c.name || '',
                    pet_name: c.pet_name || '',
                    breed: c.breed || '',
                    visit_count: c.visit_count || 0,
                    last_visit: c.last_visit || '',
                    recent_reservations: c.recent_reservations || [],
                    pets: data.pets || [],
                });
            } else {
                showCallPopup(unknownPopup);
            }
        } catch (e) {
            showCallPopup(unknownPopup);
        }
    }

    // ==================== 북킹모드 / 이동모드 ====================

    function showModeBar(type, text) {
        const bar = document.getElementById('modeBar');
        const textEl = document.getElementById('modeBarText');
        bar.className = 'mode-bar ' + type;
        textEl.textContent = text;
        bar.style.display = 'flex';
    }

    function hideModeBar() {
        document.getElementById('modeBar').style.display = 'none';
    }

    function enterBookingMode(customer) {
        bookingMode = { customer };
        moveMode = null;
        showModeBar('booking', `✂️ ${customer.pet_name || '고객'} 예약 중 — 날짜 선택 → 시간 선택`);
        showView('calendar');
        if (!selectedDate) goToday();
        toast('캘린더에서 날짜를 선택하세요');
    }

    function enterMoveMode(reservationId, petName) {
        moveMode = { reservationId, petName };
        bookingMode = null;
        closeSheet('unifiedDetailSheet');
        showModeBar('moving', `🐕 ${petName} 예약 이동 중 — 날짜 선택 → 시간 선택`);
        toast('캘린더에서 날짜를 선택하세요');
    }

    function cancelMode() {
        bookingMode = null;
        moveMode = null;
        hideModeBar();
        toast('취소되었습니다');
    }

    // 초기화
    init();

    // Public API
    // ==================== ADB Bridge 상태 ====================

    let _bridgeStatusTimer = null;

    function loadBridgeStatus() {
        fetch('/api/bridge-status', {credentials: 'same-origin'})
            .then(r => r.ok ? r.json() : null)
            .then(data => { if (data) updateBridgeStatus(data); })
            .catch(() => updateBridgeStatus({alive: false, status: 'unknown'}));
    }

    function updateBridgeStatus(data) {
        const el = document.getElementById('bridgeStatus');
        if (!el) return;

        // 타이머 리셋: 90초간 업데이트 없으면 자동으로 꺼짐 표시
        clearTimeout(_bridgeStatusTimer);
        _bridgeStatusTimer = setTimeout(() => {
            _setBridgeIndicator(el, 'dead');
        }, 90000);

        if (data.alive && data.status === 'ok') {
            _setBridgeIndicator(el, 'alive');
        } else if (data.alive && data.status === 'no_device') {
            _setBridgeIndicator(el, 'no_device');
        } else {
            _setBridgeIndicator(el, 'dead');
        }
    }

    function _setBridgeIndicator(el, state) {
        if (state === 'alive') {
            el.style.background = '#065F46';
            el.style.color = '#34D399';
            el.innerHTML = '&#9679; ADB 감시중';
        } else if (state === 'no_device') {
            el.style.background = '#78350F';
            el.style.color = '#FCD34D';
            el.innerHTML = '&#9679; 기기 없음';
        } else {
            el.style.background = '#7F1D1D';
            el.style.color = '#FCA5A5';
            el.innerHTML = '&#9679; ADB 꺼짐';
        }
    }

    // ==================== 데이터 임포트 ====================

    function showImportForm() {
        document.getElementById('importResult').style.display = 'none';
        document.getElementById('importFile').value = '';
        document.getElementById('importBtn').disabled = false;
        document.getElementById('importBtn').textContent = '임포트 실행';
        openSheet('importSheet');
    }

    async function submitImport() {
        const file = document.getElementById('importFile').files[0];
        if (!file) {
            toast('파일을 선택하세요');
            return;
        }

        if (!confirm('기존 데이터가 모두 삭제됩니다. 계속하시겠습니까?')) return;

        const btn = document.getElementById('importBtn');
        btn.disabled = true;
        btn.textContent = '처리 중...';
        const resultEl = document.getElementById('importResult');
        resultEl.style.display = 'none';

        const formData = new FormData();
        formData.append('datafile', file);

        try {
            const res = await fetch('/api/import-data', {
                method: 'POST',
                body: formData,
            });
            const data = await res.json();
            if (data.ok) {
                resultEl.style.background = '#064E3B';
                resultEl.style.color = '#6EE7B7';
                let msg = `고객 ${data.customers_count}명, 예약 ${data.reservations_count}건 등록 완료`;
                if (data.errors && data.errors.length) {
                    msg += `<br><br><strong>알림 (${data.errors.length}건):</strong><br>` +
                        data.errors.map(e => '- ' + esc(e)).join('<br>');
                }
                resultEl.innerHTML = msg;
                resultEl.style.display = 'block';
                // 캘린더 새로고침
                loadMonth();
                if (selectedDate) selectDate(selectedDate);
            } else {
                resultEl.style.background = '#7F1D1D';
                resultEl.style.color = '#FCA5A5';
                resultEl.textContent = data.error || '임포트 실패';
                resultEl.style.display = 'block';
            }
        } catch (e) {
            resultEl.style.background = '#7F1D1D';
            resultEl.style.color = '#FCA5A5';
            resultEl.textContent = '임포트 실패: ' + e.message;
            resultEl.style.display = 'block';
        } finally {
            btn.disabled = false;
            btn.textContent = '임포트 실행';
        }
    }

    // ==================== 매출관리 ====================

    async function loadSalesMonth() {
        document.getElementById('salesMonthLabel').textContent =
            `${salesYear}.${String(salesMonth).padStart(2,'0')}`;
        const body = document.getElementById('salesBody');
        body.innerHTML = '<div style="padding:16px">' + _skeletonTimeline() + '</div>';
        try {
            const res = await fetch(`/api/sales/month?y=${salesYear}&m=${salesMonth}`);
            if (!res.ok) { toast('서버 연결 실패', 'error'); return; }
            salesData = await res.json();
            renderSalesView();
        } catch (e) {
            body.innerHTML = '<div class="empty-timeline"><span class="empty-emoji" aria-hidden="true">🌧️</span><p class="empty-title">연결이 불안정해요</p><p>잠시 후 다시 시도해주세요</p></div>';
        }
    }

    function renderSalesView() {
        const body = document.getElementById('salesBody');
        let html = '';
        html += renderSalesSummary();
        html += renderSalesCalendar();
        html += renderSalesStats();
        body.innerHTML = html;
    }

    function _changeTag(cur, prev) {
        if (!prev || prev === 0) return '';
        const diff = cur - prev;
        if (diff === 0) return '';
        const pct = Math.round(Math.abs(diff) / prev * 100);
        if (diff > 0) return `<span class="sales-change up">▲ ${pct}%</span>`;
        return `<span class="sales-change down">▼ ${pct}%</span>`;
    }

    function renderSalesSummary() {
        const s = salesData.summary;
        const p = salesData.prev_summary || {};
        return `<div class="sales-summary">
            <div class="sales-card">
                <div class="sales-card-label">💰 총 매출</div>
                <div class="sales-card-value">${s.total_sales.toLocaleString()}원</div>
                ${_changeTag(s.total_sales, p.total_sales)}
            </div>
            <div class="sales-card">
                <div class="sales-card-label">✅ 완료 건수</div>
                <div class="sales-card-value">${s.completed_cnt}건</div>
                ${_changeTag(s.completed_cnt, p.completed_cnt)}
            </div>
            <div class="sales-card">
                <div class="sales-card-label">🐾 건당 평균</div>
                <div class="sales-card-value">${s.avg_amount.toLocaleString()}원</div>
                ${_changeTag(s.avg_amount, p.avg_amount)}
            </div>
        </div>`;
    }

    function _abbreviateAmount(n) {
        if (n >= 10000) {
            const man = Math.floor(n / 10000);
            const rest = n % 10000;
            if (rest >= 1000) {
                return `${man}만${Math.floor(rest/1000)}천`;
            }
            return rest > 0 ? `${man}만${rest.toLocaleString()}` : `${man}만`;
        }
        return n.toLocaleString();
    }

    function renderSalesCalendar() {
        const daily = salesData.daily;
        const firstDay = new Date(salesYear, salesMonth - 1, 1).getDay();
        const lastDate = new Date(salesYear, salesMonth, 0).getDate();
        const today = new Date();
        const todayStr = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;

        let html = '<div class="sales-calendar-section"><div class="weekday-row"><span>일</span><span>월</span><span>화</span><span>수</span><span>목</span><span>금</span><span>토</span></div><div class="calendar-grid">';

        for (let i = 0; i < firstDay; i++) {
            html += '<div class="cal-cell empty"></div>';
        }

        for (let d = 1; d <= lastDate; d++) {
            const dateStr = `${salesYear}-${String(salesMonth).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
            const dow = (firstDay + d - 1) % 7;
            let cls = 'cal-cell';
            if (dateStr === todayStr) cls += ' today';
            if (dow === 0) cls += ' sunday';
            if (dow === 6) cls += ' saturday';

            const info = daily[dateStr];
            let badgeHtml = '';
            if (info) {
                badgeHtml = `<div class="cal-badges"><span class="cal-badge completed">${_abbreviateAmount(info.total)}</span>`;
                if (info.cnt > 1) badgeHtml += `<span class="cal-more">${info.cnt}건</span>`;
                badgeHtml += '</div>';
            }

            html += `<div class="${cls}" onclick="App.showSalesDayDetail('${dateStr}')"><div class="cal-day">${d}</div>${badgeHtml}</div>`;
        }

        html += '</div></div>';
        return html;
    }

    function renderSalesStats() {
        const DOW_NAMES = ['일','월','화','수','목','금','토'];
        let html = '<div class="stats-grid">';

        // 견종별 매출/방문
        if (salesData.breeds && salesData.breeds.length) {
            html += '<div class="stats-section"><div class="stats-title">🐕 견종별 매출</div><div class="stats-list">';
            salesData.breeds.forEach((b, i) => {
                const pct = salesData.summary.total_sales ? Math.round(b.total / salesData.summary.total_sales * 100) : 0;
                html += `<div class="stats-row">
                    <span class="stats-rank">${i+1}</span>
                    <span class="stats-name">${esc(b.breed)}</span>
                    <span class="stats-detail">${b.visit_cnt}회 &middot; ${b.total.toLocaleString()}원 <span class="stats-pct">${pct}%</span></span>
                </div>`;
            });
            html += '</div></div>';
        }

        // 반려동물별 방문 TOP
        if (salesData.top_pets.length) {
            html += '<div class="stats-section"><div class="stats-title">🏆 반려동물별 방문 TOP 10</div><div class="stats-list">';
            salesData.top_pets.forEach((p, i) => {
                html += `<div class="stats-row" onclick="App.showCustomerDetail(${p.customer_id})" style="cursor:pointer">
                    <span class="stats-rank">${i+1}</span>
                    <span class="stats-name">${esc(p.pet_name)}<span class="stats-breed"> ${esc(p.breed)}</span></span>
                    <span class="stats-detail">${p.visit_cnt}회 &middot; ${p.visit_sales.toLocaleString()}원</span>
                </div>`;
            });
            html += '</div></div>';
        }

        // 서비스별 매출
        if (salesData.services && salesData.services.length) {
            html += '<div class="stats-section"><div class="stats-title">✂️ 서비스별 매출</div><div class="stats-list">';
            salesData.services.forEach(s => {
                html += `<div class="stats-row">
                    <span class="stats-name">${esc(s.service)}</span>
                    <span class="stats-detail">${s.cnt}건 &middot; ${s.total.toLocaleString()}원 (평균 ${s.avg.toLocaleString()}원)</span>
                </div>`;
            });
            html += '</div></div>';
        }

        // 결제수단별
        if (salesData.payment.length) {
            html += '<div class="stats-section"><div class="stats-title">💳 결제수단별</div><div class="stats-list">';
            salesData.payment.forEach(p => {
                const pct = salesData.summary.total_sales ? Math.round(p.total / salesData.summary.total_sales * 100) : 0;
                html += `<div class="stats-row">
                    <span class="stats-name">${esc(p.method)}</span>
                    <span class="stats-detail">${p.cnt}건 &middot; ${p.total.toLocaleString()}원 <span class="stats-pct">${pct}%</span></span>
                </div>`;
            });
            html += '</div></div>';
        }

        // 요일별 매출
        if (salesData.by_dow && salesData.by_dow.length) {
            html += '<div class="stats-section"><div class="stats-title">📅 요일별 매출</div><div class="stats-list">';
            const maxTotal = Math.max(...salesData.by_dow.map(d => d.total));
            salesData.by_dow.forEach(d => {
                const barW = maxTotal ? Math.round(d.total / maxTotal * 100) : 0;
                html += `<div class="stats-row dow-row">
                    <span class="stats-dow">${DOW_NAMES[d.dow]}</span>
                    <div class="stats-bar-wrap"><div class="stats-bar-fill" style="width:${barW}%"></div></div>
                    <span class="stats-detail">${d.cnt}건 &middot; ${d.total.toLocaleString()}원</span>
                </div>`;
            });
            html += '</div></div>';
        }

        html += '</div>';
        return html;
    }

    function changeSalesMonth(delta) {
        salesMonth += delta;
        if (salesMonth > 12) { salesMonth = 1; salesYear++; }
        else if (salesMonth < 1) { salesMonth = 12; salesYear--; }
        salesData = null;
        loadSalesMonth();
    }

    async function showSalesDayDetail(dateStr) {
        const d = new Date(dateStr + 'T00:00:00');
        const dow = WEEKDAYS_KR[d.getDay()];
        const parts = dateStr.split('-');
        const dateLabel = `${parts[1]}/${parts[2]}(${dow})`;

        try {
            const res = await fetch(`/api/day?date=${dateStr}`);
            const data = await res.json();
            const items = (data.reservations || []).filter(r => r.status === 'completed' && r.amount > 0);

            let html = `<div class="sheet-handle"></div><div class="sheet-header"><h3>📅 ${dateLabel} 매출 상세</h3><button class="sheet-close" onclick="App.closeSheet('salesDaySheet')" aria-label="닫기">&times;</button></div>`;
            html += '<div class="sheet-body">';

            if (!items.length) {
                html += '<div class="empty-timeline" style="padding:30px"><span class="empty-emoji" aria-hidden="true">🐾</span><p class="empty-title">매출 내역이 없어요</p></div>';
            } else {
                let total = 0;
                html += '<div class="sales-day-list">';
                for (const r of items) {
                    total += r.amount || 0;
                    const timeStr = r.time ? formatTime(r.time) : '';
                    const pm = r.payment_method || '-';
                    html += `<div class="sales-day-item" onclick="App.showReservationDetail(${r.id},${r.customer_id})">
                        <div class="sales-day-pet">${esc(r.pet_name)} <span class="breed">${esc(r.breed || '')}</span></div>
                        <div class="sales-day-info">${timeStr} · ${esc(r.service)} · ${esc(pm)}</div>
                        <div class="sales-day-amount">${(r.amount || 0).toLocaleString()}원</div>
                    </div>`;
                }
                html += '</div>';
                html += `<div class="sales-day-total">합계 <strong>${total.toLocaleString()}원</strong> (${items.length}건)</div>`;
            }
            html += '</div>';

            const sheet = document.getElementById('salesDaySheet');
            const sheetInner = sheet.querySelector('.bottom-sheet');
            sheetInner._swipeSetup = false;
            sheetInner.innerHTML = html;
            openSheet('salesDaySheet');
        } catch (e) {
            toast('불러오기 실패', 'error');
        }
    }

    function goTodaySales() {
        const now = new Date();
        salesYear = now.getFullYear();
        salesMonth = now.getMonth() + 1;
        salesData = null;
        loadSalesMonth();
    }

    // ==================== Google 연락처 연동 ====================

    function loadGoogleStatus() {
        fetch('/google/status', {credentials: 'same-origin'})
            .then(r => r.ok ? r.json() : null)
            .then(data => {
                const el = document.getElementById('googleStatus');
                if (!el || !data) return;
                if (data.connected) {
                    el.style.background = '#065F46';
                    el.style.color = '#34D399';
                    el.innerHTML = '&#9679; Google 연동됨';
                } else {
                    el.style.background = '#374151';
                    el.style.color = '#9CA3AF';
                    el.innerHTML = '&#9679; Google';
                }
            })
            .catch(() => {});
    }

    // ==================== 견적 요청 (SSE + 알림) ====================

    let _sseSource = null;
    let _pendingRequestCount = 0;

    function initGroomingSSE() {
        if (_sseSource) return;
        _sseSource = new EventSource('/api/grooming-requests/stream');
        _sseSource.onmessage = function(e) {
            try {
                const data = JSON.parse(e.data);
                if (data.type === 'init') {
                    _pendingRequestCount = data.pending_count;
                    updateRequestBadge();
                } else if (data.type === 'new_request') {
                    _pendingRequestCount++;
                    updateRequestBadge();
                    showBrowserNotification(data);
                    if (currentView === 'requests') loadGroomingRequests();
                }
            } catch (err) {}
        };
        _sseSource.onerror = function() {
            _sseSource.close();
            _sseSource = null;
            setTimeout(initGroomingSSE, 5000);
        };
    }

    function updateRequestBadge() {
        const cnt = _pendingRequestCount;
        const navBadge = document.getElementById('requestsNavBadge');
        const inlineBadge = document.getElementById('requestsBadgeInline');
        if (navBadge) {
            navBadge.textContent = cnt;
            navBadge.style.display = cnt > 0 ? '' : 'none';
        }
        if (inlineBadge) {
            inlineBadge.textContent = cnt;
            inlineBadge.style.display = cnt > 0 ? '' : 'none';
        }
    }

    function showBrowserNotification(data) {
        if (!('Notification' in window)) return;
        if (Notification.permission === 'default') {
            Notification.requestPermission();
            return;
        }
        if (Notification.permission !== 'granted') return;
        const title = '새 견적 요청';
        const body = `${data.breed || ''} / ${data.actual_service || data.service_type || ''} / ${(data.estimated_price || 0).toLocaleString()}원${data.customer_name ? ' - ' + data.customer_name : ''}`;
        new Notification(title, { body, icon: '/static/icons/icon-192.png' });
    }

    async function loadGroomingRequests() {
        const filter = document.getElementById('requestsFilter');
        const status = filter ? filter.value : 'pending';
        const body = document.getElementById('requestsBody');
        body.innerHTML = '<div class="loading" style="padding:20px"></div>';

        try {
            const url = status ? `/api/grooming-requests?status=${status}` : '/api/grooming-requests';
            const res = await fetch(url, { credentials: 'same-origin' });
            const rows = await res.json();
            if (!rows.length) {
                body.innerHTML = '<div style="text-align:center;padding:40px;color:#999;font-size:14px">요청이 없습니다</div>';
                return;
            }
            body.innerHTML = rows.map(r => renderRequestCard(r)).join('');
        } catch (e) {
            body.innerHTML = '<div style="text-align:center;padding:40px;color:#EF4444;font-size:14px">로딩 실패</div>';
        }
    }

    function renderRequestCard(r) {
        const statusLabels = { pending: '⏳ 대기중', confirmed: '✅ 확인됨', dismissed: '🚫 무시됨' };
        const statusClass = r.status === 'pending' ? 'pending' : r.status === 'confirmed' ? 'confirmed' : 'dismissed';
        const created = r.created_at || '';
        const options = [];
        if (r.clipping_length) options.push(`클리핑 ${r.clipping_length}`);
        if (r.face_cut) options.push('얼굴커트');
        if (r.matting && r.matting !== 'none') options.push(`엉킴: ${r.matting === 'light' ? '조금' : '심함'}`);
        if (r.fur_length) options.push(`털: ${r.fur_length}`);

        // 채널 정보 파싱
        let channelBadge = '';
        const memo = r.memo || '';
        try {
            const meta = JSON.parse(memo);
            const sourceIcons = { kakao: '💬 카톡', naver: '🟢 톡톡', web: '🌐 웹' };
            const consultIcons = { kakao: '카톡상담', naver: '톡톡상담', phone: '📞 전화상담' };
            const src = sourceIcons[meta.source] || '';
            const con = consultIcons[meta.consult] || '';
            if (src || con) channelBadge = `<span class="req-channel">${src}${src && con ? ' → ' : ''}${con}</span>`;
        } catch (e) {
            // memo가 JSON이 아닌 경우 (이전 데이터) 그냥 표시
            if (memo && !memo.startsWith('{')) channelBadge = `<div class="req-memo">${memo}</div>`;
        }

        return `<div class="request-card ${statusClass}">
            <div class="req-top">
                <span class="req-status ${statusClass}">${statusLabels[r.status] || r.status}</span>
                ${channelBadge}
                <span class="req-time">${created}</span>
            </div>
            <div class="req-info">
                <div class="req-main">
                    <strong>${r.breed || ''}</strong>
                    <span>${r.weight ? r.weight + 'kg' : ''}</span>
                    <span class="req-service">${r.actual_service || r.service_type}</span>
                </div>
                <div class="req-price">${(r.estimated_price || 0).toLocaleString()}원</div>
            </div>
            ${options.length ? `<div class="req-options">${options.join(' · ')}</div>` : ''}
            ${r.status === 'pending' ? `<div class="req-actions">
                <button class="req-btn confirm" onclick="App.updateRequestStatus(${r.id}, 'confirmed')">✅ 확인</button>
                <button class="req-btn dismiss" onclick="App.updateRequestStatus(${r.id}, 'dismissed')">🚫 무시</button>
            </div>` : ''}
        </div>`;
    }

    async function updateRequestStatus(id, status) {
        try {
            await fetch(`/api/grooming-requests/${id}/status`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({ status }),
            });
            if (status === 'confirmed' || status === 'dismissed') {
                _pendingRequestCount = Math.max(0, _pendingRequestCount - 1);
                updateRequestBadge();
            }
            loadGroomingRequests();
        } catch (e) {
            toast('상태 변경 실패', 'error');
        }
    }

    // SSE 시작 (init에서 호출)
    setTimeout(initGroomingSSE, 1000);
    // 브라우저 알림 권한 요청
    if ('Notification' in window && Notification.permission === 'default') {
        setTimeout(() => Notification.requestPermission(), 3000);
    }

    function toggleGoogle() {
        fetch('/google/status', {credentials: 'same-origin'})
            .then(r => r.json())
            .then(data => {
                if (data.connected) {
                    const choice = prompt('Google 연락처 자동 동기화 중입니다.\n(고객 등록/수정 시 자동 반영)\n\n1: 증분 동기화 (미동기화 고객만)\n2: 연동 해제\n3: 전체 동기화 (시간 오래 걸림)\n\n번호를 입력하세요:');
                    if (choice === '1') {
                        _runGoogleSync('/google/sync-incremental', '증분');
                    } else if (choice === '3') {
                        if (confirm('전체 고객을 5명씩 나눠서 동기화합니다.\n진행하시겠습니까?')) {
                            _runGoogleBatchSync();
                        }
                    } else if (choice === '2') {
                        if (confirm('Google 연동을 해제하시겠습니까?\n자동 동기화가 중단됩니다.')) {
                            fetch('/google/disconnect', {method: 'POST', credentials: 'same-origin'})
                                .then(() => loadGoogleStatus());
                        }
                    }
                } else {
                    if (confirm('Google 연락처를 연동하시겠습니까?\n연동하면 고객 등록/수정 시 자동으로 연락처가 동기화됩니다.')) {
                        window.location.href = '/google/connect';
                    }
                }
            });
    }

    function _runGoogleSync(url, label) {
        const el = document.getElementById('googleStatus');
        if (el) el.innerHTML = '&#9679; ' + label + ' 동기화중...';

        // JSON 응답인 경우 (동기화할 고객 없음)
        fetch(url, {credentials: 'same-origin'}).then(r => {
            const ct = r.headers.get('content-type') || '';
            if (ct.includes('application/json')) {
                return r.json().then(d => {
                    toast(d.message || '완료', 'success');
                    loadGoogleStatus();
                });
            }
            // SSE 응답 → EventSource로 재연결
            const sse = new EventSource(url);
            sse.onmessage = function(e) {
                try {
                    const ev = JSON.parse(e.data);
                    if (ev.type === 'start') {
                        if (el) el.innerHTML = '&#9679; 0/' + ev.total;
                    } else if (ev.type === 'progress') {
                        if (el) el.innerHTML = '&#9679; ' + ev.i + '/' + ev.total;
                        toast((ev.ok ? '✓ ' : '✗ ') + ev.name, ev.ok ? 'success' : 'error');
                    } else if (ev.type === 'done') {
                        sse.close();
                        let msg = label + ' 동기화 완료: 성공 ' + ev.success + '건, 실패 ' + ev.fail + '건';
                        if (ev.synced_names && ev.synced_names.length) {
                            msg += '\n\n동기화된 연락처:\n' + ev.synced_names.join(', ');
                        }
                        if (ev.errors && ev.errors.length) {
                            msg += '\n\n실패:\n' + ev.errors.join('\n');
                        }
                        alert(msg);
                        loadGoogleStatus();
                    }
                } catch (err) {}
            };
            sse.onerror = function() {
                sse.close();
                if (el) el.innerHTML = '&#9679; Google 연동됨';
                toast('서버 연결이 끊어졌습니다. 서버에서는 계속 진행 중일 수 있습니다.', 'error');
                loadGoogleStatus();
            };
        }).catch(() => {
            // fetch 자체 실패 시 SSE로 바로 시도
            const sse = new EventSource(url);
            sse.onmessage = function(e) {
                try {
                    const ev = JSON.parse(e.data);
                    if (ev.type === 'done') {
                        sse.close();
                        alert(label + ' 동기화 완료: 성공 ' + ev.success + '건, 실패 ' + ev.fail + '건');
                        loadGoogleStatus();
                    } else if (ev.type === 'progress' && el) {
                        el.innerHTML = '&#9679; ' + ev.i + '/' + ev.total;
                    }
                } catch (err) {}
            };
            sse.onerror = function() { sse.close(); loadGoogleStatus(); };
        });
    }

    async function _runGoogleBatchSync() {
        const el = document.getElementById('googleStatus');
        const BATCH_SIZE = 5;
        let offset = 0;
        let totalSuccess = 0, totalFail = 0;
        let allNames = [], allErrors = [];

        if (el) el.innerHTML = '&#9679; 전체 동기화 준비중...';

        while (true) {
            try {
                const res = await fetch('/google/sync-batch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify({ offset, limit: BATCH_SIZE }),
                });
                const data = await res.json();
                if (data.error) { toast(data.error, 'error'); break; }

                for (const r of data.results) {
                    if (r.ok) { totalSuccess++; allNames.push(r.name); }
                    else { totalFail++; allErrors.push(r.name + ': ' + r.error); }
                    toast((r.ok ? '✓ ' : '✗ ') + r.name, r.ok ? 'success' : 'error');
                }

                if (el) el.innerHTML = '&#9679; ' + Math.min(offset + BATCH_SIZE, data.total) + '/' + data.total;

                if (data.done) break;
                offset += BATCH_SIZE;
            } catch (e) {
                toast('동기화 중 오류 발생', 'error');
                break;
            }
        }

        let msg = '전체 동기화 완료: 성공 ' + totalSuccess + '건, 실패 ' + totalFail + '건';
        if (allNames.length) msg += '\n\n동기화된 연락처:\n' + allNames.join(', ');
        if (allErrors.length) msg += '\n\n실패:\n' + allErrors.slice(0, 5).join('\n');
        alert(msg);
        loadGoogleStatus();
    }

    // ==================== 고객 변경이력 ====================

    let _historyOffset = 0;

    async function showCustomerHistory() {
        _historyOffset = 0;
        openSheet('historySheet');
        await _loadHistory(false);
    }

    async function _loadHistory(append) {
        const content = document.getElementById('historyContent');
        if (!append) content.innerHTML = '<p style="text-align:center;color:#999;padding:40px">불러오는 중...</p>';
        try {
            const res = await fetch(`/api/customers/history?offset=${_historyOffset}&limit=50`);
            const data = await res.json();
            const items = data.history || [];

            const ACTION_LABEL = { create: '🆕 등록', update: '✏️ 수정', delete: '🗑️ 삭제' };
            const FIELD_LABEL = { memo: '메모', phone: '전화', pet_name: '이름', breed: '견종', weight: '몸무게', channel: '유입경로', phone2: '보조연락처', name: '보호자명', notes: '메모' };

            let html = '';
            if (!append) html = '';

            if (!items.length && !append) {
                content.innerHTML = '<p style="text-align:center;color:#999;padding:40px">변경이력이 없습니다</p>';
                return;
            }

            let lastDate = '';
            for (const h of items) {
                const dateStr = h.created_at.split(' ')[0];
                if (dateStr !== lastDate) {
                    html += `<div class="history-date-divider">${dateStr}</div>`;
                    lastDate = dateStr;
                }
                const label = ACTION_LABEL[h.action] || h.action;
                const pet = h.pet_name ? `${esc(h.pet_name)}` : `#${h.customer_id}`;
                const field = FIELD_LABEL[h.field_name] || h.field_name;

                let detail = '';
                if (h.action === 'create') {
                    detail = `<span class="history-new">${esc(h.new_value)}</span>`;
                } else if (h.action === 'update') {
                    const oldShort = h.old_value.length > 30 ? h.old_value.substring(0, 30) + '..' : h.old_value;
                    const newShort = h.new_value.length > 30 ? h.new_value.substring(0, 30) + '..' : h.new_value;
                    detail = `<span class="history-field">${field}</span> <span class="history-old">${esc(oldShort)}</span> → <span class="history-new">${esc(newShort)}</span>`;
                } else if (h.action === 'delete') {
                    detail = `<span class="history-old">${esc(h.old_value)}</span>`;
                }

                html += `<div class="history-item">
                    <span class="history-action">${label}</span>
                    <span class="history-pet">${pet}</span>
                    <div class="history-detail">${detail}</div>
                    <span class="history-time">${h.created_at.split(' ')[1] || ''}</span>
                </div>`;
            }

            if (items.length >= 50) {
                html += `<button class="btn-load-more" onclick="App.loadMoreHistory()">더 보기</button>`;
            }

            if (append) {
                const btn = content.querySelector('.btn-load-more');
                if (btn) btn.remove();
                content.insertAdjacentHTML('beforeend', html);
            } else {
                content.innerHTML = html;
            }
            _historyOffset += items.length;
        } catch (e) {
            if (!append) content.innerHTML = '<p style="text-align:center;color:#999;padding:40px">불러오기 실패</p>';
        }
    }

    async function loadMoreHistory() {
        await _loadHistory(true);
    }

    // ==================== 사장 휴무/일정 ====================

    function showBossScheduleForm() {
        if (!CONFIG.bossCustomerId) { toast('사장 계정이 없습니다', 'error'); return; }
        const date = selectedDate || fmtDate(new Date());

        const durations = [30, 60, 90, 120, 150, 180, 210, 240];
        const durLabels = {30:'30분', 60:'1시간', 90:'1시간30분', 120:'2시간', 150:'2시간30분', 180:'3시간', 210:'3시간30분', 240:'4시간'};

        const slots = generateTimeSlots();
        let timeOptions = slots.map(s => `<option value="${s}">${formatTime(s)}</option>`).join('');

        const form = document.getElementById('reservationForm');
        document.getElementById('sheetTitle').textContent = '🏖️ 휴무/일정 등록';
        form.innerHTML = `
            <input type="hidden" id="bossDate" value="${date}">
            <div class="res-form-grid">
                <div class="form-group">
                    <label>날짜</label>
                    <input type="date" id="bossDateInput" value="${date}" onchange="document.getElementById('bossDate').value=this.value">
                </div>
                <div class="form-group">
                    <label>유형</label>
                    <input type="hidden" id="bossType" value="allday">
                    <div class="btn-grid">
                        <button type="button" class="btn-grid-item active" onclick="App.selectBossType(this,'allday')">종일 휴무</button>
                        <button type="button" class="btn-grid-item" onclick="App.selectBossType(this,'time')">시간대 지정</button>
                    </div>
                </div>
                <div id="bossTimeSection" style="display:none" class="form-group">
                    <label>시작 시간</label>
                    <select id="bossStartTime" class="form-select">${timeOptions}</select>
                </div>
                <div id="bossDurSection" style="display:none" class="form-group">
                    <label>소요시간</label>
                    <div class="btn-grid">
                        ${durations.map(d => `<button type="button" class="btn-grid-item${d===120?' active':''}" data-field="bossDuration" data-value="${d}" onclick="App.selectGridBtn(this)">${durLabels[d]}</button>`).join('')}
                    </div>
                    <input type="hidden" id="bossDuration" value="120">
                </div>
                <div class="res-form-full">
                    <button class="btn-primary" onclick="App.saveBossSchedule()">등록</button>
                </div>
            </div>
        `;
        openSheet('reservationSheet');
    }

    function selectBossType(btn, type) {
        btn.parentElement.querySelectorAll('.btn-grid-item').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById('bossType').value = type;
        document.getElementById('bossTimeSection').style.display = type === 'time' ? '' : 'none';
        document.getElementById('bossDurSection').style.display = type === 'time' ? '' : 'none';
    }

    async function saveBossSchedule() {
        const date = document.getElementById('bossDate').value;
        const type = document.getElementById('bossType').value;

        let time, duration;
        if (type === 'allday') {
            time = CONFIG.businessStart;
            // 종일: 영업시간 전체
            const [sh, sm] = CONFIG.businessStart.split(':').map(Number);
            const [eh, em] = CONFIG.businessEnd.split(':').map(Number);
            duration = (eh * 60 + em) - (sh * 60 + sm);
        } else {
            time = document.getElementById('bossStartTime').value;
            duration = parseInt(document.getElementById('bossDuration').value) || 120;
        }

        try {
            const res = await fetch('/api/reservation', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    customer_id: CONFIG.bossCustomerId,
                    date: date,
                    time: time,
                    service_type: type === 'allday' ? '휴무' : '일정',
                    duration: duration,
                    amount: 0,
                    quoted_amount: 0,
                }),
            });
            const result = await res.json();
            if (result.ok) {
                closeSheet('reservationSheet', true);
                toast('휴무/일정이 등록되었습니다', 'success');
                selectDate(date);
                loadMonth();
            } else {
                toast(result.error || '등록 실패', 'error');
            }
        } catch (e) {
            toast('등록 실패', 'error');
        }
    }

    // ==================== 참고사진 ====================

    function addRefPhoto(cid) {
        document.getElementById('cfPhotoInput').click();
    }

    async function handlePhotoSelect(input, cid) {
        if (!input.files || !input.files[0]) return;
        const file = input.files[0];
        if (file.size > 10 * 1024 * 1024) { toast('10MB 이하 사진만 가능합니다', 'error'); return; }

        toast('사진 업로드 중...');
        try {
            const base64 = await _compressImage(file, 1200, 0.75);
            const res = await fetch(`/api/customer/${cid}/photos`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image_data: base64 }),
            });
            const result = await res.json();
            if (result.ok) {
                toast('사진이 추가되었습니다', 'success');
                _loadEditFormPhotos(cid);
            } else {
                toast(result.error || '업로드 실패', 'error');
            }
        } catch (e) {
            toast('업로드 실패', 'error');
        }
        input.value = '';
    }

    function _compressImage(file, maxSize, quality) {
        return new Promise((resolve) => {
            const reader = new FileReader();
            reader.onload = (e) => {
                const img = new Image();
                img.onload = () => {
                    const canvas = document.createElement('canvas');
                    let w = img.width, h = img.height;
                    if (w > maxSize || h > maxSize) {
                        if (w > h) { h = Math.round(h * maxSize / w); w = maxSize; }
                        else { w = Math.round(w * maxSize / h); h = maxSize; }
                    }
                    canvas.width = w; canvas.height = h;
                    canvas.getContext('2d').drawImage(img, 0, 0, w, h);
                    resolve(canvas.toDataURL('image/jpeg', quality));
                };
                img.src = e.target.result;
            };
            reader.readAsDataURL(file);
        });
    }

    async function _loadEditFormPhotos(cid) {
        const container = document.getElementById('cfPhotoPreview');
        if (!container) return;
        try {
            const res = await fetch(`/api/customer/${cid}/photos`);
            const data = await res.json();
            const photos = data.photos || [];
            if (!photos.length) { container.innerHTML = ''; return; }
            container.innerHTML = photos.map(p => `
                <div class="photo-thumb-wrap">
                    <img src="${p.image_data}" class="photo-thumb" onclick="App.viewPhoto('${p.image_data.replace(/'/g, "\\'")}')">
                    <button class="photo-delete-btn" onclick="App.deleteRefPhoto(${cid}, ${p.id})">&times;</button>
                </div>
            `).join('');
        } catch (e) { /* ignore */ }
    }

    async function deleteRefPhoto(cid, photoId) {
        if (!confirm('이 사진을 삭제하시겠습니까?')) return;
        try {
            const res = await fetch(`/api/customer/${cid}/photo/${photoId}`, { method: 'DELETE' });
            const result = await res.json();
            if (result.ok) {
                toast('삭제됨', 'success');
                _loadEditFormPhotos(cid);
            } else {
                toast('삭제 실패', 'error');
            }
        } catch (e) { toast('삭제 실패', 'error'); }
    }

    async function showRefPhotos(cid) {
        try {
            const res = await fetch(`/api/customer/${cid}/photos`);
            const data = await res.json();
            const photos = data.photos || [];
            if (!photos.length) { toast('등록된 참고사진이 없습니다'); return; }

            const form = document.getElementById('reservationForm');
            document.getElementById('sheetTitle').textContent = '📷 참고사진';
            form.innerHTML = `
                <div class="photo-gallery">
                    ${photos.map(p => `
                        <div class="photo-gallery-item">
                            <img src="${p.image_data}" onclick="App.viewPhoto(this.src)" loading="lazy">
                            <span class="photo-date">${p.created_at || ''}</span>
                        </div>
                    `).join('')}
                </div>
            `;
            openSheet('reservationSheet');
        } catch (e) { toast('사진 불러오기 실패', 'error'); }
    }

    function viewPhoto(src) {
        const overlay = document.createElement('div');
        overlay.className = 'photo-viewer-overlay';
        overlay.innerHTML = `<img src="${src}" class="photo-viewer-img"><button class="photo-viewer-close" onclick="this.parentElement.remove()">&times;</button>`;
        overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
        document.body.appendChild(overlay);
    }

    return {
        selectDate, closeTimeline, changeMonth, goToday, loadCustomerList,
        get customerSort() { return customerSort; },
        showView, onSlotClick, onBookedSlotClick, searchCustomersForSlot,
        showNewCustomerFormForSlot, showNewCustomerForm,
        onServiceChange, saveReservation,
        showReservationDetail, showEditReservation, deleteReservation, toggleHistoryAccordion,
        updateReservation, changeStatus,
        searchCustomers, setCustomerSort, showCustomerDetail,
        showCustomerForm_edit, addSiblingPet, startMemoEdit, cancelMemoEdit, saveMergedMemo, toggleKeyring,
        saveCustomer, deleteCustomer, onBreedInput, onBreedKeydown, selectBreed,
        toggleCallHistory, showCallPopup, closeCallPopup,
        reserveFromCall, registerFromCall, downloadBackup, copyIntakeForm,
        openSheet, closeSheet,
        showCustomerForm, showReservationForm, selectChannel,
        changeCallDate, refresh, onQuickReserve, onQuickReserveForDate, showTimeSlotPicker, showDatePicker, onDatePick, changePickerMonth, testCall,
        selectGridBtn, applyPrevService,
        onCallHistoryClick, enterBookingMode, enterMoveMode, cancelMode, formatPhoneInput,
        updateBridgeStatus,
        showImportForm, submitImport,
        changeSalesMonth, goTodaySales, showSalesDayDetail, showCustomAmount,
        toggleGoogle,
        loadGroomingRequests, updateRequestStatus,
        showBossScheduleForm, selectBossType, saveBossSchedule,
        showCustomerHistory, loadMoreHistory,
        addRefPhoto, handlePhotoSelect, deleteRefPhoto, showRefPhotos, viewPhoto,
        setupBackupFolder,
    };
})();

/* === PWA 설치 배너 === */
(function() {
    let deferredPrompt = null;

    // 30일 이내 닫았으면 표시 안 함
    function isDismissed() {
        const ts = localStorage.getItem('pwa_dismiss');
        if (!ts) return false;
        return Date.now() - Number(ts) < 30 * 24 * 60 * 60 * 1000;
    }

    // 이미 standalone(설치됨)이면 표시 안 함
    function isStandalone() {
        return window.matchMedia('(display-mode: standalone)').matches
            || navigator.standalone === true;
    }

    function createBanner(isIOS) {
        if (isDismissed() || isStandalone()) return;
        if (document.getElementById('pwaBanner')) return;

        const banner = document.createElement('div');
        banner.id = 'pwaBanner';
        banner.style.cssText = 'position:fixed;bottom:70px;left:50%;transform:translateX(-50%);' +
            'background:#4F46E5;color:#fff;padding:10px 16px;border-radius:24px;' +
            'font-size:13px;font-weight:600;display:flex;align-items:center;gap:10px;' +
            'box-shadow:0 4px 20px rgba(79,70,229,.4);z-index:9999;max-width:calc(100% - 32px);' +
            'animation:pwSlideUp .4s ease';

        if (isIOS) {
            banner.innerHTML =
                '<span>🐾 홈 화면에 추가하면 앱처럼 사용할 수 있어요</span>' +
                '<span style="font-size:11px;opacity:.8;white-space:nowrap">공유 ➜ 홈 화면에 추가</span>' +
                '<button id="pwaDismiss" style="background:none;border:none;color:#fff;font-size:18px;cursor:pointer;padding:0 0 0 4px">&times;</button>';
        } else {
            banner.innerHTML =
                '<span>🐾 홈 화면에 추가하면 더 빠르게 사용할 수 있어요</span>' +
                '<button id="pwaInstall" style="background:#fff;color:#4F46E5;border:none;border-radius:16px;padding:6px 14px;font-size:12px;font-weight:700;cursor:pointer;white-space:nowrap">설치</button>' +
                '<button id="pwaDismiss" style="background:none;border:none;color:#fff;font-size:18px;cursor:pointer;padding:0 0 0 4px">&times;</button>';
        }

        // Animation keyframes
        if (!document.getElementById('pwaStyle')) {
            const style = document.createElement('style');
            style.id = 'pwaStyle';
            style.textContent = '@keyframes pwSlideUp{from{opacity:0;transform:translateX(-50%) translateY(20px)}to{opacity:1;transform:translateX(-50%) translateY(0)}}';
            document.head.appendChild(style);
        }

        document.body.appendChild(banner);

        // 닫기
        document.getElementById('pwaDismiss').onclick = function() {
            localStorage.setItem('pwa_dismiss', String(Date.now()));
            banner.remove();
        };

        // 설치 버튼 (Android/Desktop)
        var installBtn = document.getElementById('pwaInstall');
        if (installBtn && deferredPrompt) {
            installBtn.onclick = function() {
                deferredPrompt.prompt();
                deferredPrompt.userChoice.then(function() {
                    deferredPrompt = null;
                    banner.remove();
                });
            };
        }
    }

    // Android/Desktop: beforeinstallprompt
    window.addEventListener('beforeinstallprompt', function(e) {
        e.preventDefault();
        deferredPrompt = e;
        // 30초 후 배너 표시
        setTimeout(function() { createBanner(false); }, 30000);
    });

    // iOS: beforeinstallprompt 미지원, 수동 안내
    var isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    if (isIOS && !isStandalone()) {
        setTimeout(function() { createBanner(true); }, 30000);
    }
})();
