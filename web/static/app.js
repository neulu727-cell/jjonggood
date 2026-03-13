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

    function isPC() { return window.innerWidth >= 900; }

    const WEEKDAYS_KR = ['일','월','화','수','목','금','토'];
    const STATUS_LABEL = { confirmed: '예약', completed: '완료', cancelled: '취소', no_show: '노쇼' };

    // ==================== 초기화 ====================

    function init() {
        const now = new Date();
        currentYear = now.getFullYear();
        currentMonth = now.getMonth() + 1;
        setupSwipe();
        if (isPC()) {
            startClock();
            loadCallSidebar();
            goToday();
            loadBridgeStatus();
        } else {
            loadMonth();
        }
    }

    // ==================== 뷰 전환 ====================

    function showView(view) {
        currentView = view;
        document.querySelectorAll('.nav-item').forEach(el => {
            el.classList.toggle('active', el.dataset.view === view);
        });
        const calSec = document.getElementById('calendarSection');
        const tlSec = document.getElementById('timelineSection');
        const custView = document.getElementById('customerView');

        if (view === 'calendar') {
            if (!isPC()) {
                calSec.style.display = '';
                tlSec.style.display = '';
            }
            custView.style.display = 'none';
        } else if (view === 'customers') {
            if (!isPC()) {
                calSec.style.display = 'none';
                tlSec.style.display = 'none';
            }
            custView.style.display = 'flex';
            document.getElementById('customerSearchInput').focus();
            loadCustomerList('', customerSort);
        }
    }

    // ==================== 월간 캘린더 ====================

    async function loadMonth() {
        updateMonthLabel();
        const grid = document.getElementById('calendarGrid');
        grid.innerHTML = '<div class="loading" style="grid-column:1/-1">불러오는 중</div>';

        try {
            const res = await fetch(`/api/month?y=${currentYear}&m=${currentMonth}`);
            if (!res.ok) { window.location.href = '/login'; return; }
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
            const maxBadges = 2;
            let badgesHtml = '';
            for (let i = 0; i < Math.min(names.length, maxBadges); i++) {
                const entry = names[i];
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
                badgesHtml += `<span class="cal-more">+${names.length - maxBadges}</span>`;
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

        // 모바일: 캘린더 접어서 타임라인 공간 확보
        if (window.innerWidth < 900) {
            document.querySelector('.calendar-section')?.classList.add('collapsed');
        }

        const content = document.getElementById('timelineContent');
        content.innerHTML = _skeletonTimeline();

        try {
            const res = await fetch(`/api/day?date=${dateStr}`);
            if (!res.ok) { window.location.href = '/login'; return; }
            const data = await res.json();
            renderTimeline(data);
        } catch (e) {
            content.innerHTML = '<div class="empty-timeline"><div class="icon">!</div><p>데이터를 불러올 수 없습니다</p><button class="btn-secondary" style="width:auto;margin-top:12px;padding:10px 24px" onclick="App.selectDate(\'' + dateStr + '\')">다시 시도</button></div>';
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
                    ${isPC() ? '' : '<button class="timeline-close" onclick="App.closeTimeline()">&times;</button>'}
                </div>
            </div>
        `;

        if (isPC()) {
            html += renderTimelineGrid(slots, booked, bookedIsStart);
        } else {
            html += renderTimelineList(slots, booked, bookedIsStart);
        }

        content.innerHTML = html;
        updateStatsBar(data);
    }

    function renderTimelineList(slots, booked, bookedIsStart) {
        const isPast = selectedDate < fmtDate(new Date());
        let html = '<div class="timeline-list">';
        const rendered = new Set();
        for (const slot of slots) {
            if (rendered.has(slot)) continue;
            const r = booked[slot];
            if (r) {
                if (bookedIsStart[slot]) {
                    const startLabel = formatTime(r.time);
                    const endLabel = formatTime(r.end_time);
                    const statusCls = r.status || 'confirmed';
                    const TL_LABEL = { confirmed: '예약', completed: '미용완료', cancelled: '취소', no_show: '노쇼' };
                    const statusText = TL_LABEL[statusCls] || statusCls;
                    const breedText = r.breed ? `(${r.breed})` : '';
                    const amtText = r.amount ? `${r.amount.toLocaleString()}원` : '';
                    const furText = r.fur_length ? ` / ${esc(r.fur_length)}` : '';
                    const weightText = r.weight ? `${r.weight}kg` : '';
                    const petMeta = [breedText, weightText].filter(Boolean).join(' · ');
                    const memoText = r.customer_memo ? `<div class="res-memo">${esc(r.customer_memo)}</div>` : '';
                    html += `
                        <div class="res-card" onclick="App.showReservationDetail(${r.id},${r.customer_id})">
                            <div class="res-time-col">
                                <div class="res-time-start">${startLabel}</div>
                                <div class="res-time-end">${endLabel}</div>
                            </div>
                            <div class="res-info">
                                <div class="res-pet">
                                    ${esc(r.pet_name)}
                                    <span class="breed">${esc(petMeta)}</span>
                                </div>
                                <div class="res-service">${esc(r.service)}${furText}${amtText ? ' · ' + amtText : ''}</div>
                                ${memoText}
                            </div>
                            <span class="res-status ${statusCls}">${statusText}</span>
                        </div>`;
                }
                rendered.add(slot);
            } else if (!isPast) {
                html += `
                    <div class="slot-item" onclick="App.onSlotClick('${slot}')">
                        <span class="slot-time">${formatTime(slot)}</span>
                        <span class="slot-label">빈 슬롯</span>
                        <span class="slot-add">+</span>
                    </div>`;
            }
        }
        html += '</div>';
        return html;
    }

    function renderTimelineGrid(slots, booked, bookedIsStart) {
        const isPast = selectedDate < fmtDate(new Date());

        // 과거 날짜: 완료된 예약만 리스트로 표시 (그리드 아닌 리스트)
        if (isPast) {
            return renderTimelineList(slots, booked, bookedIsStart);
        }

        const STATUS_COLORS = {
            confirmed: { bg: '#DBEAFE', border: '#93C5FD', text: '#1E40AF' },
            completed: { bg: '#DCFCE7', border: '#86EFAC', text: '#166534' },
            cancelled: { bg: '#FEE2E2', border: '#FCA5A5', text: '#991B1B' },
            no_show:   { bg: '#FEF3C7', border: '#FDE68A', text: '#92400E' },
        };

        const mid = Math.ceil(slots.length / 2);
        const leftSlots = slots.slice(0, mid);
        const rightSlots = slots.slice(mid);
        const maxRows = Math.max(leftSlots.length, rightSlots.length);

        let html = '<div class="tl-grid">';

        for (let col = 0; col < 2; col++) {
            const colSlots = col === 0 ? leftSlots : rightSlots;
            html += `<div class="tl-col">`;
            const skip = new Set();

            for (let i = 0; i < colSlots.length; i++) {
                if (skip.has(i)) continue;
                const ts = colSlots[i];
                const r = booked[ts];

                if (r) {
                    const isStart = bookedIsStart[ts];
                    let span = 1;
                    for (let j = i + 1; j < colSlots.length; j++) {
                        if (booked[colSlots[j]] === r) { span++; skip.add(j); }
                        else break;
                    }

                    const sc = STATUS_COLORS[r.status] || STATUS_COLORS.confirmed;
                    const height = span * 48 - 2;
                    const weightTag = r.weight ? `${r.weight}kg` : '';
                    const petParts = [r.breed, weightTag].filter(Boolean).join('/');
                    const petInfo = petParts ? `${esc(r.pet_name)}(${esc(petParts)})` : esc(r.pet_name);

                    if (span === 1) {
                        html += `<div class="tl-slot tl-booked" style="height:${height}px;background:${sc.bg};border-color:${sc.border};color:${sc.text}" onclick="App.showReservationDetail(${r.id},${r.customer_id})">
                            <span class="tl-time">${ts}</span>`;
                        if (isStart) {
                            const fur = r.fur_length ? `/${esc(r.fur_length)}` : '';
                            html += `<span class="tl-info">${petInfo} ${esc(r.service)}${fur}</span>`;
                            if (r.amount) html += `<span class="tl-amount">${r.amount.toLocaleString()}</span>`;
                        } else {
                            html += `<span class="tl-info">~ ${petInfo}</span>`;
                        }
                        html += `</div>`;
                    } else {
                        html += `<div class="tl-slot tl-booked tl-merged" style="height:${height}px;background:${sc.bg};border-color:${sc.border};color:${sc.text}" onclick="App.showReservationDetail(${r.id},${r.customer_id})">`;
                        if (isStart) {
                            const [rh, rm] = r.time.split(':').map(Number);
                            const endMin = rh * 60 + rm + r.duration;
                            const endStr = `${String(Math.floor(endMin/60)).padStart(2,'0')}:${String(endMin%60).padStart(2,'0')}`;
                            const fur = r.fur_length ? ` / ${esc(r.fur_length)}` : '';
                            const amtText = r.amount ? `  ${r.amount.toLocaleString()}원` : '';
                            html += `<div class="tl-row"><span class="tl-time">${ts}~${endStr}</span> <span class="tl-info">${petInfo}</span></div>`;
                            html += `<div class="tl-row"><span class="tl-detail">${esc(r.service)}${fur}${amtText}</span></div>`;
                            const memoParts = [];
                            if (r.customer_memo) memoParts.push(r.customer_memo);
                            if (r.request) memoParts.push(r.request);
                            if (memoParts.length) html += `<div class="tl-row"><span class="tl-memo">${esc(memoParts.join(' / '))}</span></div>`;
                        } else {
                            html += `<div class="tl-row"><span class="tl-info">~ ${petInfo}</span></div>`;
                        }
                        html += `</div>`;
                    }
                } else {
                    html += `<div class="tl-slot tl-empty" onclick="App.onSlotClick('${ts}')">
                        <span class="tl-time">${ts}</span>
                        <span class="tl-hint">+ 예약</span>
                    </div>`;
                }
            }
            html += '</div>';
        }

        html += '</div>';
        return html;
    }

    function closeTimeline() {
        selectedDate = null;
        renderCalendar();
        document.querySelector('.calendar-section')?.classList.remove('collapsed');
        document.getElementById('timelineContent').innerHTML =
            '<div class="empty-timeline"><div class="icon">📅</div><p>날짜를 선택하세요</p></div>';
    }

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
                    toast('예약이 이동되었습니다');
                    selectDate(selectedDate);
                    loadMonth();
                } else {
                    toast(result.error || '이동 실패');
                }
            }).catch(() => toast('이동 실패'));
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
            `예약 등록 - ${customer.pet_name}`;

        const svc0 = CONFIG.services[0];
        let serviceGrid = CONFIG.services.map((s, i) =>
            `<button type="button" class="btn-grid-item${i===0?' active':''}" data-field="resService" data-value="${esc(s[0])}" data-dur="${s[1]}" data-price="${s[2]}" onclick="App.selectGridBtn(this)">${esc(s[0])}</button>`
        ).join('');

        let furGrid = `<button type="button" class="btn-grid-item active" data-field="resFurLength" data-value="" onclick="App.selectGridBtn(this)">없음</button>` +
            CONFIG.furLengths.map(f =>
                `<button type="button" class="btn-grid-item" data-field="resFurLength" data-value="${f}" onclick="App.selectGridBtn(this)">${f}</button>`
            ).join('');

        const durations = [30, 60, 90, 120, 150, 180];
        const durLabels = {30:'30분', 60:'1시간', 90:'1시간30분', 120:'2시간', 150:'2시간30분', 180:'3시간'};
        let durGrid = durations.map(d =>
            `<button type="button" class="btn-grid-item${d===svc0[1]?' active':''}" data-field="resDuration" data-value="${d}" onclick="App.selectGridBtn(this)">${durLabels[d]}</button>`
        ).join('');

        const prices = [30000, 40000, 45000, 50000, 55000, 60000, 70000, 80000];
        let priceGrid = prices.map(p =>
            `<button type="button" class="btn-grid-item${p===svc0[2]?' active':''}" data-field="resAmount" data-value="${p}" onclick="App.selectGridBtn(this)">${(p/10000)}만</button>`
        ).join('');

        // 이전 서비스 이력
        let prevHtml = '';
        if (customer.reservations && customer.reservations.length) {
            const recent = customer.reservations.slice(0, 5);
            prevHtml = `
                <div class="prev-services">
                    <button type="button" class="prev-services-toggle" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">
                        이전 서비스 이력 (${customer.reservations.length}건) <span>▼</span>
                    </button>
                    <div class="prev-services-list" style="display:none">
                        ${recent.map(r => `<div class="prev-service-item" onclick="App.applyPrevService('${esc(r.service_type)}',${r.duration},${r.amount||0},'${esc(r.fur_length||'')}')">
                            <span>${esc(r.service_type)} / ${r.duration}분</span>
                            <span>${r.amount ? r.amount.toLocaleString()+'원' : '-'}</span>
                        </div>`).join('')}
                    </div>
                </div>`;
        }

        form.innerHTML = `
            <input type="hidden" id="resCustomerId" value="${customer.id}">
            <input type="hidden" id="resService" value="${esc(svc0[0])}">
            <input type="hidden" id="resDuration" value="${svc0[1]}">
            <input type="hidden" id="resAmount" value="${svc0[2]}">
            <input type="hidden" id="resFurLength" value="">
            <div class="res-form-grid">
                <div class="form-group">
                    <label>고객</label>
                    <input type="text" value="${esc(customer.pet_name)} (${esc(customer.breed || '')}) - ${esc(customer.name || customer.phone_display || '')}" disabled>
                </div>
                <div class="form-group">
                    <label>시간</label>
                    <input type="text" value="${formatTime(pendingSlotTime)} (${pendingSlotTime})" disabled>
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
                    <label>소요시간 <span class="sub-label" id="durLabel">${svc0[1]}분</span></label>
                    <div class="btn-grid">${durGrid}</div>
                </div>
                <div class="form-group res-form-full">
                    <label>금액 <span class="sub-label" id="priceLabel">${svc0[2].toLocaleString()}원</span></label>
                    <div class="btn-grid">${priceGrid}</div>
                </div>
                <div class="form-group">
                    <label>메모</label>
                    <textarea id="resRequest" rows="2" placeholder="요청사항, 메모 등"></textarea>
                </div>
                <div class="res-form-full">
                    <button class="btn-primary" onclick="App.saveReservation()">예약 저장</button>
                </div>
            </div>
        `;
        openSheet('reservationSheet');
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
        if ((field === 'resService' || field === 'editResService') && btn.dataset.dur) {
            const prefix = field.startsWith('edit') ? 'editRes' : 'res';
            document.getElementById(prefix + 'Duration').value = btn.dataset.dur;
            document.getElementById(prefix + 'Amount').value = btn.dataset.price;
            const dur = parseInt(btn.dataset.dur);
            const price = parseInt(btn.dataset.price);
            document.querySelectorAll('[data-field="'+prefix+'Duration"]').forEach(b =>
                b.classList.toggle('active', parseInt(b.dataset.value) === dur));
            document.querySelectorAll('[data-field="'+prefix+'Amount"]').forEach(b =>
                b.classList.toggle('active', parseInt(b.dataset.value) === price));
            const durLabel = document.getElementById('durLabel');
            const priceLabel = document.getElementById('priceLabel');
            if (durLabel) durLabel.textContent = dur + '분';
            if (priceLabel) priceLabel.textContent = price.toLocaleString() + '원';
            return;
        }
        if (field === 'resDuration' || field === 'editResDuration') {
            const durLabel = document.getElementById('durLabel');
            if (durLabel) durLabel.textContent = btn.dataset.value + '분';
        }
        if (field === 'resAmount' || field === 'editResAmount') {
            const priceLabel = document.getElementById('priceLabel');
            if (priceLabel) priceLabel.textContent = parseInt(btn.dataset.value).toLocaleString() + '원';
        }
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
        const data = {
            customer_id: parseInt(document.getElementById('resCustomerId').value),
            date: selectedDate,
            time: pendingSlotTime,
            service_type: document.getElementById('resService').value,
            duration: parseInt(document.getElementById('resDuration').value) || 60,
            amount: parseInt(document.getElementById('resAmount').value) || 0,
            quoted_amount: parseInt(document.getElementById('resAmount').value) || 0,
            payment_method: (document.getElementById('resPaymentMethod') || {}).value || '',
            fur_length: document.getElementById('resFurLength').value,
            request: document.getElementById('resRequest').value.trim(),
        };

        try {
            const res = await fetch('/api/reservation', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
            const result = await res.json();
            if (result.ok) {
                closeSheet('reservationSheet');
                toast('예약이 저장되었습니다');
                selectDate(selectedDate);
                loadMonth(); // 캘린더 뱃지 갱신
            } else {
                toast(result.error || '저장 실패');
            }
        } catch (e) {
            toast('저장 실패');
        }
    }

    // ==================== 통합 상세 (예약+고객) ====================

    // 예약 카드에서 진입: customer API 1회 호출, reservations 배열에서 activeRes 탐색
    async function showReservationDetail(rid, customerId) {
        const content = document.getElementById('unifiedDetailContent');
        content.innerHTML = '<div class="loading">불러오는 중</div>';
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
        content.innerHTML = '<div class="loading">불러오는 중</div>';
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
        const allPets = [{ id: c.id, pet_name: c.pet_name, breed: c.breed, weight: c.weight, memo: c.memo || '' }, ...siblings.map(s => ({...s, memo: s.memo || ''}))];
        const hasSiblings = siblings.length > 0;

        // 헤더: 모든 펫을 한 줄에 나열
        let petsHeaderHtml = allPets.map((p, i) => {
            const w = p.weight ? ' · ' + p.weight + 'kg' : '';
            return `<span class="ud-pet-name">${esc(p.pet_name)}</span><span class="ud-pet-info">${esc(p.breed)}${w}</span>`;
        }).join('<span class="ud-pet-divider">/</span>');
        const addBtnHtml = `<button class="pet-pill pet-pill-add" style="font-size:12px;padding:2px 8px;margin-left:4px;vertical-align:middle" data-phone="${esc(c.phone)}" data-name="${esc(c.name || '')}" onclick="App.addSiblingPet(this.dataset.phone, this.dataset.name)">+</button>`;

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
        const totalSales = completedRes.reduce((sum, r) => sum + (r.amount || 0), 0);
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

        // 강아지별 통합 메모 (컴팩트)
        const memoHtml = allPets.map(p => {
            const petRes = (p.id === c.id) ? (c.reservations || []) : (siblingRes[p.id] || []);
            const resMemoParts = petRes
                .filter(r => r.request || r.groomer_memo)
                .map(r => {
                    const dateShort = r.date.substring(5).replace('-','/');
                    const memo = [r.request, r.groomer_memo].filter(Boolean).join('/');
                    return `${dateShort} ${memo}`;
                });
            const allMemoLines = [];
            if (p.memo) allMemoLines.push(p.memo);
            if (resMemoParts.length) allMemoLines.push(resMemoParts.join('\n'));
            const combined = allMemoLines.join('\n───\n');

            return `<div class="ud-memo-pet">
                <span class="pet-label">${esc(p.pet_name)}</span>
                <button type="button" style="font-size:12px;color:var(--text-light);background:none;border:none;cursor:pointer;padding:2px 6px;vertical-align:middle" onclick="App.toggleMemoEdit(${p.id}, ${c.id})" aria-label="${esc(p.pet_name)} 메모 편집">✎</button>
                <div id="petMemoView_${p.id}" class="memo-text">${combined ? esc(combined) : '<span style="color:var(--text-light);font-size:11px">메모 없음</span>'}</div>
                <div id="petMemoEdit_${p.id}" style="display:none;margin-top:1px">
                    <textarea id="petMemoTA_${p.id}" style="width:100%;min-height:40px;padding:4px 8px;border:1.5px solid var(--primary);border-radius:5px;font-size:13px;font-family:inherit;resize:vertical;box-sizing:border-box">${esc(p.memo)}</textarea>
                    <div style="display:flex;gap:4px;margin-top:3px">
                        <button class="btn-primary-sm" style="padding:3px 10px;font-size:11px" onclick="App.savePetMemo(${p.id}, ${c.id})">저장</button>
                        <button style="padding:3px 10px;font-size:11px;background:none;border:1px solid var(--border-strong);border-radius:5px;cursor:pointer;color:var(--text-light)" onclick="App.toggleMemoEdit(${p.id}, ${c.id})">취소</button>
                    </div>
                </div>
            </div>`;
        }).join('');

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
                const amt = r.amount ? r.amount.toLocaleString() + '원' : '';
                const resMemo = [r.request, r.groomer_memo].filter(Boolean).join(' / ');
                const petTag = hasSiblings ? `<span style="font-size:10px;font-weight:600;color:var(--primary);background:var(--primary-light);padding:1px 5px;border-radius:3px;margin-right:3px">${esc(r._pet)}</span>` : '';
                return `
                    <div class="ud-acc-item${isActive ? ' open active-res' : ''}" id="acc_${r.id}">
                        <button type="button" class="ud-acc-header" onclick="App.toggleHistoryAccordion(${r.id})" aria-expanded="${isActive}" aria-controls="acc_body_${r.id}">
                            <span class="res-status ${r.status}" style="min-width:32px;text-align:center;font-size:11px">${statusLabel}</span>
                            <div style="flex:1;min-width:0">
                                <div style="font-size:12px">${petTag}${dateStr}${timeStr}</div>
                                <div style="font-size:11px;color:var(--text-light)">${esc(r.service_type)}${r.fur_length ? '/'+esc(r.fur_length) : ''}${amt ? ' · '+amt : ''}</div>
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
                                ${r.status === 'completed' ? `<button class="btn-secondary" onclick="App.changeStatus(${r.id},'confirmed')">되돌리기</button>` : ''}
                            </div>
                        </div>
                    </div>`;
            }).join('');
        } else {
            historyHtml = '<p style="text-align:center;color:var(--text-light);padding:8px;font-size:12px">이력 없음</p>';
        }

        content.innerHTML = `
            <div class="ud-header-bar">
                <div class="ud-header-main">
                    ${petsHeaderHtml}${addBtnHtml}
                    <span class="ud-pet-divider">|</span>
                    ${c.name ? `<span class="ud-pet-owner">${esc(c.name)}</span>` : ''}
                    <a href="tel:${c.phone}" class="ud-pet-phone">${esc(c.phone_display)}</a>
                    <button class="ud-edit-link" onclick="App.showCustomerForm_edit(${c.id})" aria-label="고객 정보 수정">수정</button>
                </div>
            </div>
            <div class="unified-grid">
                <div>
                    <div class="ud-stats">
                        <strong>${allReservations.length}</strong>건 이력${totalCount ? ` · 완료 <strong>${totalCount}</strong>건` : ''} · 매출 <strong>${salesText}</strong>
                        ${visitLine ? `<br>${visitLine}` : ''}
                    </div>
                    <div class="ud-memo">
                        <div class="ud-memo-title">메모</div>
                        ${memoHtml || '<span style="color:var(--text-light);font-size:11px">메모 없음</span>'}
                        <div class="ud-quick-memo">
                            <textarea id="quickMemo" rows="1" placeholder="메모 추가"></textarea>
                            <button class="btn-primary-sm" style="flex-shrink:0;padding:6px 12px;font-size:12px" onclick="App.saveQuickMemo(${c.id})">추가</button>
                        </div>
                    </div>
                </div>
                <div>
                    <div class="ud-history-title">이력 (${allReservations.length}건)</div>
                    <div class="ud-history-scroll">
                        ${historyHtml}
                    </div>
                </div>
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

    async function saveQuickMemo(customerId) {
        const newMemo = document.getElementById('quickMemo').value.trim();
        if (!newMemo) { toast('메모를 입력하세요'); return; }

        try {
            const cres = await fetch(`/api/customer/${customerId}`);
            if (!cres.ok) throw new Error('fetch failed');
            const cdata = await cres.json();
            const existing = (cdata.memo || '').trim();
            const memo = existing ? existing + ', ' + newMemo : newMemo;

            const res = await fetch(`/api/customer/${customerId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ memo }),
            });
            const result = await res.json();
            if (result.ok) {
                toast('메모 추가됨');
                cachedCustomers = null;
                _reloadUnifiedDetail(customerId);
            } else {
                toast(result.error || '저장 실패');
            }
        } catch (e) {
            toast('저장 실패');
        }
    }

    async function showEditReservation(rid) {
        try {
            const res = await fetch(`/api/reservation/${rid}`);
            if (!res.ok) { toast('불러오기 실패'); return; }
            const r = await res.json();
            closeSheet('unifiedDetailSheet');

            let serviceGrid = CONFIG.services.map(s =>
                `<button type="button" class="btn-grid-item${s[0]===r.service_type?' active':''}" data-field="editResService" data-value="${esc(s[0])}" data-dur="${s[1]}" data-price="${s[2]}" onclick="App.selectGridBtn(this)">${esc(s[0])}</button>`
            ).join('');
            if (!CONFIG.services.find(s => s[0] === r.service_type)) {
                serviceGrid = `<button type="button" class="btn-grid-item active" data-field="editResService" data-value="${esc(r.service_type)}" onclick="App.selectGridBtn(this)">${esc(r.service_type)}</button>` + serviceGrid;
            }

            let furGrid = `<button type="button" class="btn-grid-item${!r.fur_length?' active':''}" data-field="editResFurLength" data-value="" onclick="App.selectGridBtn(this)">없음</button>` +
                CONFIG.furLengths.map(f =>
                    `<button type="button" class="btn-grid-item${f===r.fur_length?' active':''}" data-field="editResFurLength" data-value="${f}" onclick="App.selectGridBtn(this)">${f}</button>`
                ).join('');

            const durations = [30, 60, 90, 120, 150, 180];
            const durLabels = {30:'30분', 60:'1시간', 90:'1시간30분', 120:'2시간', 150:'2시간30분', 180:'3시간'};
            let durGrid = durations.map(d =>
                `<button type="button" class="btn-grid-item${d===r.duration?' active':''}" data-field="editResDuration" data-value="${d}" onclick="App.selectGridBtn(this)">${durLabels[d]||d+'분'}</button>`
            ).join('');

            const prices = [30000, 40000, 45000, 50000, 55000, 60000, 70000, 80000];
            let priceGrid = prices.map(p =>
                `<button type="button" class="btn-grid-item${p===r.amount?' active':''}" data-field="editResAmount" data-value="${p}" onclick="App.selectGridBtn(this)">${(p/10000)}만</button>`
            ).join('');
            const form = document.getElementById('reservationForm');
            document.getElementById('sheetTitle').textContent = '예약 수정';
            form.innerHTML = `
                <input type="hidden" id="editResId" value="${rid}">
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
                        <label>금액 <span class="sub-label" id="priceLabel">${(r.amount||0).toLocaleString()}원</span></label>
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
                    <div class="form-group">
                        <label>메모</label>
                        <textarea id="editResRequest" rows="2">${esc([r.request, r.groomer_memo].filter(Boolean).join(' / '))}</textarea>
                    </div>
                    <div class="res-form-full">
                        <button class="btn-primary" onclick="App.updateReservation()">수정 저장</button>
                    </div>
                </div>
            `;
            openSheet('reservationSheet');
        } catch (e) {
            toast('불러오기 실패');
        }
    }

    async function updateReservation() {
        const rid = document.getElementById('editResId').value;
        const data = {
            date: document.getElementById('editResDate').value,
            time: document.getElementById('editResTime').value,
            service_type: document.getElementById('editResService').value,
            duration: parseInt(document.getElementById('editResDuration').value) || 60,
            amount: parseInt(document.getElementById('editResAmount').value) || 0,
            quoted_amount: parseInt(document.getElementById('editResAmount').value) || 0,
            payment_method: (document.getElementById('editResPaymentMethod') || {}).value || '',
            fur_length: document.getElementById('editResFurLength').value,
            request: document.getElementById('editResRequest').value.trim(),
            groomer_memo: '',
        };

        try {

            const res = await fetch(`/api/reservation/${rid}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
            const result = await res.json();
            if (result.ok) {
                closeSheet('reservationSheet');
                toast('수정되었습니다');
                if (selectedDate) selectDate(selectedDate);
                loadMonth();
            } else {
                toast(result.error || '수정 실패');
            }
        } catch (e) {
            toast('수정 실패');
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
                    <h3 style="margin:0 0 16px;font-size:17px">결제방법 선택</h3>
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
                toast(`${labels[status]} 처리되었습니다`);
                if (selectedDate) selectDate(selectedDate);
                loadMonth();
            } else {
                toast(result.error || '실패');
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
            container.innerHTML = '<div style="text-align:center;color:#999;padding:40px"><p>고객 목록을 불러올 수 없습니다</p><button class="btn-secondary" style="width:auto;margin-top:12px;padding:10px 24px" onclick="App.loadCustomerList(\'\',App.customerSort)">다시 시도</button></div>';
        }
    }

    async function searchCustomers(keyword) {
        clearTimeout(searchTimer);
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
            container.innerHTML = '<div style="text-align:center;padding:40px 20px"><p style="color:var(--text-light);margin-bottom:12px">검색 결과 없음</p><button class="btn-primary-sm" onclick="App.showNewCustomerForm()" style="padding:10px 20px">+ 신규 고객 등록</button></div>';
            return;
        }

        // 같은 전화번호 펫 수 카운트 (뱃지용)
        const phoneCounts = {};
        for (const c of customers) {
            if (c.phone) phoneCounts[c.phone] = (phoneCounts[c.phone] || 0) + 1;
        }

        container.innerHTML = customers.map((c, i) => {
            const initial = (c.pet_name || '?')[0];
            const meta = [];
            if (c.phone_display) meta.push(c.phone_display);
            if (c.last_visit) meta.push(`마지막 방문: ${c.last_visit}`);
            if (c.visit_count) meta.push(`${c.visit_count}회 방문`);
            const siblingBadge = (phoneCounts[c.phone] || 0) > 1
                ? `<span class="sibling-badge">+${phoneCounts[c.phone] - 1}</span>` : '';
            return `
                <div class="customer-card" data-idx="${i}">
                    <div class="customer-avatar">${esc(initial)}</div>
                    <div class="customer-info">
                        <div class="customer-name">
                            ${esc(c.pet_name)}
                            <span class="breed">${esc(c.breed || '')}</span>
                            ${siblingBadge}
                        </div>
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
        document.getElementById('customerFormTitle').textContent =
            isEdit ? '고객 정보 수정' : '신규 고객 등록';

        const c = customer || {};
        const breedValue = c.breed || '';

        let formHtml;
        if (isEdit) {
            // 수정 폼: 기존 필드 유지
            formHtml = `
                <input type="hidden" id="cfId" value="${c.id}">
                <div class="form-group">
                    <label>전화번호 *</label>
                    <input type="tel" id="cfPhone" value="${esc(c.phone_display || c.phone || '')}" placeholder="010-0000-0000" inputmode="tel" oninput="App.formatPhoneInput(this)">
                </div>
                <input type="hidden" id="cfName" value="${esc(c.name || '')}">
                <div class="form-group">
                    <label>반려동물 이름 *</label>
                    <input type="text" id="cfPetName" value="${esc(c.pet_name || '')}" placeholder="반려동물 이름">
                </div>
                <div class="form-group" style="position:relative">
                    <label>견종 *</label>
                    <input type="text" id="cfBreed" value="${esc(breedValue)}" placeholder="견종" autocomplete="off"
                           oninput="App.onBreedInput(this.value)" onfocus="App.onBreedInput(this.value)"
                           onkeydown="App.onBreedKeydown(event)">
                    <div class="breed-suggestions" id="breedSuggestions" style="display:none"></div>
                </div>
                <div class="form-group">
                    <label>몸무게 (kg)</label>
                    <input type="number" id="cfWeight" value="${c.weight || ''}" step="0.1" placeholder="예: 3.5">
                </div>
                <div class="form-group">
                    <label>메모</label>
                    <textarea id="cfMemo" rows="2" placeholder="알러지, 주의사항 등">${esc(c.memo || '')}</textarea>
                </div>
                <button class="btn-primary" onclick="App.saveCustomer(true, '${typeof onSaved === 'function' ? 'callback' : ''}')">${'수정 저장'}</button>
                <button class="btn-danger" onclick="App.deleteCustomer(${c.id})">삭제</button>
            `;
        } else {
            // 신규 폼: 4개 필드로 간소화
            formHtml = `
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

        // 공백 없으면 전체가 이름
        return { pet_name: val, breed: '' };
    }

    async function saveCustomer(isEdit) {
        let data;
        if (isEdit) {
            data = {
                phone: document.getElementById('cfPhone').value,
                name: document.getElementById('cfName').value,
                pet_name: document.getElementById('cfPetName').value,
                breed: document.getElementById('cfBreed').value,
                weight: document.getElementById('cfWeight').value || null,
                age: '',
                notes: '',
                memo: document.getElementById('cfMemo').value,
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
                toast(isEdit ? '수정되었습니다' : '등록되었습니다');

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
                toast(result.error || '실패');
            }
        } catch (e) {
            toast('실패');
        }
    }

    async function deleteCustomer(cid) {
        if (!confirm('이 고객과 모든 예약을 삭제하시겠습니까?')) return;
        try {
            const res = await fetch(`/api/customer/${cid}`, { method: 'DELETE' });
            const result = await res.json();
            if (result.ok) {
                cachedCustomers = null;
                closeSheet('customerFormSheet');
                closeSheet('unifiedDetailSheet');
                toast('삭제되었습니다');
            }
        } catch (e) {
            toast('삭제 실패');
        }
    }

    function toggleMemoEdit(petId, mainCid) {
        const viewEl = document.getElementById('petMemoView_' + petId);
        const editEl = document.getElementById('petMemoEdit_' + petId);
        if (!viewEl || !editEl) return;
        const isEditing = editEl.style.display !== 'none';
        viewEl.style.display = isEditing ? '' : 'none';
        editEl.style.display = isEditing ? 'none' : '';
        if (!isEditing) {
            const ta = document.getElementById('petMemoTA_' + petId);
            if (ta) ta.focus();
        }
    }

    async function savePetMemo(petId, mainCid) {
        const ta = document.getElementById('petMemoTA_' + petId);
        if (!ta) return;
        const memo = ta.value;
        try {
            const res = await fetch(`/api/customer/${petId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ memo }),
            });
            const result = await res.json();
            if (result.ok) {
                toast('메모 저장됨');
                cachedCustomers = null;
                _reloadUnifiedDetail(mainCid);
            } else {
                toast(result.error || '저장 실패');
            }
        } catch (e) {
            toast('저장 실패');
        }
    }

    function addSiblingPet(phone, name) {
        closeSheet('unifiedDetailSheet');
        showCustomerForm({ phone: phone, phone_display: phone.replace(/(\d{3})(\d{4})(\d{4})/, '$1-$2-$3'), name: name }, (newCustomer) => {
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
            if (!res.ok) { toast('불러오기 실패'); return; }
            const c = await res.json();
            closeSheet('unifiedDetailSheet');
            showCustomerForm(c);
        } catch (e) {
            toast('불러오기 실패');
        }
    }

    // ==================== 전화 관련 ====================

    async function toggleCallHistory() {
        const content = document.getElementById('callHistoryContent');
        content.innerHTML = '<div class="loading">불러오는 중</div>';
        openSheet('callHistorySheet');

        try {
            const res = await fetch('/api/call-history');
            const data = await res.json();
            if (!data.history || !data.history.length) {
                content.innerHTML = '<p style="text-align:center;color:#999;padding:20px">전화 이력 없음</p>';
                return;
            }
            content.innerHTML = data.history.map(h => {
                const name = h.c_pet_name || h.pet_name || '';
                const breed = h.breed || '';
                const time = h.created_at ? h.created_at.substring(5, 16) : '';
                const phone = esc(h.phone || '');
                return `
                    <div class="history-item" onclick="App.closeSheet('callHistorySheet');App.onCallHistoryClick('${phone}')" style="cursor:pointer">
                        <span class="history-date">${esc(time)}</span>
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
            const count = parseInt(badge.textContent || '0') + 1;
            badge.textContent = count;
            badge.style.display = 'flex';
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
                        const amt = r.amount ? ` ${r.amount.toLocaleString()}원` : '';
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
                    <div class="call-phone">${esc(data.phone_display)}</div>
                    <div class="call-customer">${esc(data.pet_name)} (${esc(data.breed)}) - ${esc(data.customer_name)}</div>
                    ${meta ? `<div class="call-customer">${esc(meta)}</div>` : ''}
                    ${recentHtml}
                </div>
                ${actionsHtml}
            `;
        } else {
            content.innerHTML = `
                <div class="call-info-new">
                    <div class="call-phone">${esc(data.phone_display)}</div>
                    <div class="call-customer">미등록 번호</div>
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
            toast('고객 정보 로드 실패');
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
        selectedDate = todayStr;
        showView('calendar');
        loadMonth().then(() => selectDate(todayStr));
    }

    // ==================== 스와이프 ====================

    function setupSwipe() {
        let startX = 0, startY = 0;
        const el = document.querySelector('.calendar-section');
        el.addEventListener('touchstart', e => {
            startX = e.touches[0].clientX;
            startY = e.touches[0].clientY;
        }, { passive: true });
        el.addEventListener('touchend', e => {
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

    function openSheet(id) {
        const overlay = document.getElementById(id);
        overlay.style.display = 'flex';
        const sheet = overlay.querySelector('.bottom-sheet');
        if (sheet) _setupSheetSwipe(overlay, sheet);
    }

    function closeSheet(id) {
        const overlay = document.getElementById(id);
        const sheet = overlay.querySelector('.bottom-sheet');
        if (sheet) {
            sheet.style.transition = 'transform 0.2s ease';
            sheet.style.transform = 'translateY(100%)';
            setTimeout(() => {
                overlay.style.display = 'none';
                sheet.style.transform = '';
                sheet.style.transition = '';
            }, 200);
        } else {
            overlay.style.display = 'none';
        }
    }

    function _setupSheetSwipe(overlay, sheet) {
        let startY = 0, currentY = 0, isDragging = false;
        const handle = sheet.querySelector('.sheet-handle');
        if (!handle || handle._swipeSetup) return;
        handle._swipeSetup = true;

        handle.addEventListener('touchstart', (e) => {
            startY = e.touches[0].clientY;
            isDragging = true;
            sheet.style.transition = 'none';
        }, { passive: true });

        handle.addEventListener('touchmove', (e) => {
            if (!isDragging) return;
            currentY = e.touches[0].clientY - startY;
            if (currentY > 0) {
                sheet.style.transform = `translateY(${currentY}px)`;
            }
        }, { passive: true });

        handle.addEventListener('touchend', () => {
            if (!isDragging) return;
            isDragging = false;
            sheet.style.transition = 'transform 0.2s ease';
            if (currentY > 100) {
                closeSheet(overlay.id);
            } else {
                sheet.style.transform = '';
            }
            currentY = 0;
        }, { passive: true });
    }

    function downloadBackup() {
        window.location.href = '/api/backup';
    }

    function toast(msg) {
        const el = document.createElement('div');
        el.className = 'toast';
        el.textContent = msg;
        document.body.appendChild(el);
        setTimeout(() => el.remove(), 2500);
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
        const date = new Date(data.date + 'T00:00:00');
        const dow = WEEKDAYS_KR[date.getDay()];
        const parts = data.date.split('-');
        dateEl.textContent = parts[1] + '/' + parts[2] + '(' + dow + ')';
        infoEl.textContent = '예약 ' + confirmed + ' 완료 ' + completed;
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
                container.innerHTML = '<p style="text-align:center;color:#999;padding:20px;font-size:13px">전화 이력 없음</p>';
                return;
            }
            container.innerHTML = filtered.map(h => {
                const isKnown = !!(h.c_pet_name || h.pet_name);
                const name = h.c_pet_name || h.pet_name || '';
                const time = h.created_at ? h.created_at.substring(11, 16) : '';
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

    function refresh() {
        loadMonth();
        if (selectedDate) selectDate(selectedDate);
        if (isPC()) loadCallSidebar();
        toast('새로고침');
    }

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
            toast('테스트 실패');
        }
    }

    function onQuickReserve() {
        if (!selectedDate) {
            goToday();
        }
        toast('타임라인에서 빈 슬롯을 선택하세요');
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
        showModeBar('booking', `${customer.pet_name || '고객'} 예약 중 - 날짜 선택 → 빈 슬롯 클릭`);
        showView('calendar');
        if (!selectedDate) goToday();
        toast('캘린더에서 날짜를 선택 후 빈 슬롯을 클릭하세요');
    }

    function enterMoveMode(reservationId, petName) {
        moveMode = { reservationId, petName };
        bookingMode = null;
        closeSheet('unifiedDetailSheet');
        showModeBar('moving', `${petName} 예약 이동 중 - 새 날짜/시간 선택`);
        toast('캘린더에서 날짜를 선택 후 빈 슬롯을 클릭하세요');
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

    return {
        selectDate, closeTimeline, changeMonth, goToday, loadCustomerList,
        get customerSort() { return customerSort; },
        showView, onSlotClick, searchCustomersForSlot,
        showNewCustomerFormForSlot, showNewCustomerForm,
        onServiceChange, saveReservation,
        showReservationDetail, showEditReservation, toggleHistoryAccordion,
        updateReservation, changeStatus,
        searchCustomers, setCustomerSort, showCustomerDetail,
        showCustomerForm_edit, addSiblingPet, toggleMemoEdit, savePetMemo,
        saveCustomer, deleteCustomer, onBreedInput, onBreedKeydown, selectBreed,
        toggleCallHistory, showCallPopup, closeCallPopup,
        reserveFromCall, registerFromCall, downloadBackup,
        openSheet, closeSheet,
        showCustomerForm, showReservationForm, saveQuickMemo,
        changeCallDate, refresh, onQuickReserve, testCall,
        selectGridBtn, applyPrevService,
        onCallHistoryClick, enterBookingMode, enterMoveMode, cancelMode, formatPhoneInput,
        updateBridgeStatus,
        showImportForm, submitImport,
    };
})();
