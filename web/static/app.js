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
                badgesHtml += `<span class="cal-badge">${esc(label)}</span>`;
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

        const content = document.getElementById('timelineContent');
        content.innerHTML = '<div class="loading">불러오는 중</div>';

        try {
            const res = await fetch(`/api/day?date=${dateStr}`);
            if (!res.ok) { window.location.href = '/login'; return; }
            const data = await res.json();
            renderTimeline(data);
        } catch (e) {
            content.innerHTML = '<div class="empty-timeline"><div class="icon">!</div><p>데이터를 불러올 수 없습니다</p></div>';
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
        const reservationMap = {};
        const occupiedSlots = new Set();

        for (const r of items) {
            reservationMap[r.time] = r;
            // 해당 예약이 차지하는 슬롯들 계산
            const [sh, sm] = r.time.split(':').map(Number);
            const startMin = sh * 60 + sm;
            const endMin = startMin + r.duration;
            for (let m = startMin; m < endMin; m += CONFIG.slotInterval) {
                const h = Math.floor(m / 60);
                const min = m % 60;
                occupiedSlots.add(`${String(h).padStart(2,'0')}:${String(min).padStart(2,'0')}`);
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
            <div class="timeline-list">
        `;

        for (const slot of slots) {
            const r = reservationMap[slot];
            if (r) {
                const startLabel = formatTime(r.time);
                const endLabel = formatTime(r.end_time);
                const statusCls = r.status || 'confirmed';
                const statusText = STATUS_LABEL[statusCls] || statusCls;
                const breedText = r.breed ? `(${r.breed})` : '';
                const requestText = r.request ? `<div class="res-request">${esc(r.request)}</div>` : '';

                html += `
                    <div class="res-card" onclick="App.showReservationDetail(${r.id})">
                        <div class="res-time-col">
                            <div class="res-time-start">${startLabel}</div>
                            <div class="res-time-end">${endLabel}</div>
                            <div class="res-dot"></div>
                        </div>
                        <div class="res-info">
                            <div class="res-pet">
                                ${esc(r.pet_name)}
                                <span class="breed">${esc(breedText)}</span>
                            </div>
                            <div class="res-service">${esc(r.service)} ${r.duration}분</div>
                            ${requestText}
                        </div>
                        <span class="res-status ${statusCls}">${statusText}</span>
                    </div>
                `;
            } else if (!occupiedSlots.has(slot)) {
                html += `
                    <div class="slot-item" onclick="App.onSlotClick('${slot}')">
                        <span class="slot-time">${formatTime(slot)}</span>
                        <span class="slot-label">빈 슬롯</span>
                        <span class="slot-add">+</span>
                    </div>
                `;
            }
        }

        html += '</div>';
        content.innerHTML = html;
        updateStatsBar(data);
    }

    function closeTimeline() {
        selectedDate = null;
        renderCalendar();
        document.getElementById('timelineContent').innerHTML =
            '<div class="empty-timeline"><div class="icon">📅</div><p>날짜를 선택하세요</p></div>';
    }

    // ==================== 빈 슬롯 클릭 → 고객 선택 → 예약 생성 ====================

    function onSlotClick(timeStr) {
        pendingSlotTime = timeStr;
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
            <div class="form-group">
                <label>고객</label>
                <input type="text" value="${esc(customer.pet_name)} (${esc(customer.breed || '')}) - ${esc(customer.name || customer.phone_display || '')}" disabled>
            </div>
            <div class="form-group">
                <label>시간</label>
                <input type="text" value="${formatTime(pendingSlotTime)} (${pendingSlotTime})" disabled>
            </div>
            ${prevHtml}
            <div class="form-group">
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
            <div class="form-group">
                <label>금액 <span class="sub-label" id="priceLabel">${svc0[2].toLocaleString()}원</span></label>
                <div class="btn-grid">${priceGrid}</div>
            </div>
            <div class="form-group">
                <label>메모</label>
                <textarea id="resRequest" rows="2" placeholder="요청사항, 메모 등"></textarea>
            </div>
            <button class="btn-primary" onclick="App.saveReservation()">예약 저장</button>
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
        if (field === 'resService' && btn.dataset.dur) {
            document.getElementById('resDuration').value = btn.dataset.dur;
            document.getElementById('resAmount').value = btn.dataset.price;
            // 소요시간/금액 버튼도 업데이트
            const dur = parseInt(btn.dataset.dur);
            const price = parseInt(btn.dataset.price);
            document.querySelectorAll('[data-field="resDuration"]').forEach(b =>
                b.classList.toggle('active', parseInt(b.dataset.value) === dur));
            document.querySelectorAll('[data-field="resAmount"]').forEach(b =>
                b.classList.toggle('active', parseInt(b.dataset.value) === price));
            const durLabel = document.getElementById('durLabel');
            const priceLabel = document.getElementById('priceLabel');
            if (durLabel) durLabel.textContent = dur + '분';
            if (priceLabel) priceLabel.textContent = price.toLocaleString() + '원';
        }
        if (field === 'resDuration') {
            const durLabel = document.getElementById('durLabel');
            if (durLabel) durLabel.textContent = btn.dataset.value + '분';
        }
        if (field === 'resAmount') {
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

    // ==================== 예약 상세 ====================

    async function showReservationDetail(rid) {
        const content = document.getElementById('reservationDetailContent');
        content.innerHTML = '<div class="loading">불러오는 중</div>';
        openSheet('reservationDetailSheet');

        try {
            const res = await fetch(`/api/reservation/${rid}`);
            const r = await res.json();

            const statusText = STATUS_LABEL[r.status] || r.status;
            const amountText = r.amount ? `${r.amount.toLocaleString()}원` : '-';

            content.innerHTML = `
                <div class="detail-section">
                    <div class="detail-row">
                        <span class="label">반려동물</span>
                        <span class="value">${esc(r.pet_name)} (${esc(r.breed)})</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">보호자</span>
                        <span class="value">${esc(r.customer_name)} ${esc(r.customer_phone)}</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">날짜/시간</span>
                        <span class="value">${r.date} ${formatTime(r.time)}~${formatTime(r.end_time)}</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">서비스</span>
                        <span class="value">${esc(r.service_type)} (${r.duration}분)</span>
                    </div>
                    ${r.fur_length ? `<div class="detail-row"><span class="label">털 길이</span><span class="value">${esc(r.fur_length)}</span></div>` : ''}
                    <div class="detail-row">
                        <span class="label">금액</span>
                        <span class="value">${amountText}</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">상태</span>
                        <span class="value"><span class="res-status ${r.status}">${statusText}</span></span>
                    </div>
                    ${r.request ? `<div class="detail-row"><span class="label">메모</span><span class="value">${esc(r.request)}</span></div>` : ''}
                    ${r.groomer_memo ? `<div class="detail-row"><span class="label">미용사 메모</span><span class="value">${esc(r.groomer_memo)}</span></div>` : ''}
                </div>

                <div class="detail-section">
                    <h4>수정</h4>
                    <button class="btn-secondary" onclick="App.showEditReservation(${rid})">예약 수정</button>
                </div>

                <div class="detail-section">
                    <h4>상태 변경</h4>
                    ${r.status === 'confirmed' ? `
                        <button class="btn-status green" onclick="App.changeStatus(${rid},'completed')">미용 완료</button>
                        <button class="btn-status red" onclick="App.changeStatus(${rid},'cancelled')">예약 취소</button>
                        <button class="btn-status yellow" onclick="App.changeStatus(${rid},'no_show')">노쇼 처리</button>
                    ` : r.status === 'completed' ? `
                        <button class="btn-status gray" onclick="App.changeStatus(${rid},'confirmed')">되돌리기 (예약중)</button>
                    ` : ''}
                </div>

                <button class="btn-secondary" onclick="App.showCustomerDetail(${r.customer_id})">고객 상세 보기</button>
            `;
        } catch (e) {
            content.innerHTML = '<p style="text-align:center;color:#999;padding:20px">불러오기 실패</p>';
        }
    }

    async function showEditReservation(rid) {
        closeSheet('reservationDetailSheet');

        try {
            const res = await fetch(`/api/reservation/${rid}`);
            const r = await res.json();

            let serviceOptions = CONFIG.services.map(s =>
                `<option value="${s[0]}" ${s[0]===r.service_type?'selected':''}>${s[0]}</option>`
            ).join('');
            // 기존 서비스가 기본 목록에 없으면 추가
            if (!CONFIG.services.find(s => s[0] === r.service_type)) {
                serviceOptions = `<option value="${esc(r.service_type)}" selected>${esc(r.service_type)}</option>` + serviceOptions;
            }

            let furOptions = `<option value="">선택 안함</option>` +
                CONFIG.furLengths.map(f => `<option value="${f}" ${f===r.fur_length?'selected':''}>${f}</option>`).join('');

            const form = document.getElementById('reservationForm');
            document.getElementById('sheetTitle').textContent = '예약 수정';
            form.innerHTML = `
                <input type="hidden" id="editResId" value="${rid}">
                <div class="form-group">
                    <label>날짜</label>
                    <input type="date" id="editResDate" value="${r.date}">
                </div>
                <div class="form-group">
                    <label>시간</label>
                    <input type="time" id="editResTime" value="${r.time}">
                </div>
                <div class="form-group">
                    <label>미용 종류</label>
                    <select id="editResService">${serviceOptions}</select>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>소요시간 (분)</label>
                        <input type="number" id="editResDuration" value="${r.duration}">
                    </div>
                    <div class="form-group">
                        <label>금액 (원)</label>
                        <input type="number" id="editResAmount" value="${r.amount}">
                    </div>
                </div>
                <div class="form-group">
                    <label>털 길이</label>
                    <select id="editResFurLength">${furOptions}</select>
                </div>
                <div class="form-group">
                    <label>요청사항</label>
                    <textarea id="editResRequest" rows="2">${esc(r.request)}</textarea>
                </div>
                <div class="form-group">
                    <label>미용사 메모</label>
                    <textarea id="editResGroomerMemo" rows="2">${esc(r.groomer_memo)}</textarea>
                </div>
                <button class="btn-primary" onclick="App.updateReservation()">수정 저장</button>
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
            fur_length: document.getElementById('editResFurLength').value,
            request: document.getElementById('editResRequest').value.trim(),
            groomer_memo: document.getElementById('editResGroomerMemo').value.trim(),
        };

        try {
            // 메모 별도 저장
            if (data.groomer_memo !== undefined) {
                await fetch(`/api/reservation/${rid}/memo`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ memo: data.groomer_memo }),
                });
                delete data.groomer_memo;
            }

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

    async function changeStatus(rid, status) {
        const labels = { completed: '미용 완료', cancelled: '예약 취소', no_show: '노쇼 처리', confirmed: '되돌리기' };
        if (!confirm(`${labels[status]} 처리하시겠습니까?`)) return;

        try {
            const res = await fetch(`/api/reservation/${rid}/status`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status }),
            });
            const result = await res.json();
            if (result.ok) {
                closeSheet('reservationDetailSheet');
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

    async function searchCustomers(keyword) {
        const container = document.getElementById('customerSearchResults');
        if (!keyword.trim()) {
            container.innerHTML = '<p style="text-align:center;color:#999;padding:40px">이름, 전화번호, 반려동물 이름으로 검색</p>';
            return;
        }
        clearTimeout(searchTimer);
        searchTimer = setTimeout(async () => {
            try {
                const res = await fetch(`/api/customers/search?q=${encodeURIComponent(keyword)}`);
                const data = await res.json();
                renderCustomerList(container, data.customers, (c) => showCustomerDetail(c.id));
            } catch (e) {
                container.innerHTML = '<p style="text-align:center;color:#999;padding:20px">검색 실패</p>';
            }
        }, 300);
    }

    function renderCustomerList(container, customers, onClick) {
        if (!customers.length) {
            container.innerHTML = '<p style="text-align:center;color:#999;padding:20px">검색 결과 없음</p>';
            return;
        }
        container.innerHTML = customers.map(c => {
            const initial = (c.pet_name || '?')[0];
            const meta = [];
            if (c.phone_display) meta.push(c.phone_display);
            if (c.last_visit) meta.push(`마지막 방문: ${c.last_visit}`);
            if (c.visit_count) meta.push(`${c.visit_count}회 방문`);
            return `
                <div class="customer-card" onclick='(${onClick.toString()})(${JSON.stringify(c)})'>
                    <div class="customer-avatar">${esc(initial)}</div>
                    <div class="customer-info">
                        <div class="customer-name">
                            ${esc(c.pet_name)}
                            <span class="breed">${esc(c.breed || '')}</span>
                        </div>
                        <div class="customer-meta">${esc(meta.join(' | '))}</div>
                    </div>
                </div>
            `;
        }).join('');
    }

    function showNewCustomerForm(callback) {
        showCustomerForm(null, callback);
    }

    function showCustomerForm(customer, onSaved) {
        const isEdit = !!customer;
        document.getElementById('customerFormTitle').textContent =
            isEdit ? '고객 정보 수정' : '신규 고객 등록';

        const c = customer || {};
        const breedValue = c.breed || '';

        document.getElementById('customerFormContent').innerHTML = `
            ${isEdit ? `<input type="hidden" id="cfId" value="${c.id}">` : ''}
            <div class="form-group">
                <label>전화번호 *</label>
                <input type="tel" id="cfPhone" value="${esc(c.phone_display || c.phone || '')}" placeholder="010-0000-0000" inputmode="tel">
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
            <div class="form-row">
                <div class="form-group">
                    <label>몸무게 (kg)</label>
                    <input type="number" id="cfWeight" value="${c.weight || ''}" step="0.1" placeholder="예: 3.5">
                </div>
                <div class="form-group">
                    <label>나이</label>
                    <input type="text" id="cfAge" value="${esc(c.age || '')}" placeholder="예: 3살">
                </div>
            </div>
            <div class="form-group">
                <label>특이사항</label>
                <textarea id="cfNotes" rows="2" placeholder="알러지, 주의사항 등">${esc(c.notes || '')}</textarea>
            </div>
            <div class="form-group">
                <label>메모</label>
                <textarea id="cfMemo" rows="2">${esc(c.memo || '')}</textarea>
            </div>
            <button class="btn-primary" onclick="App.saveCustomer(${isEdit}, '${typeof onSaved === 'function' ? 'callback' : ''}')">${isEdit ? '수정 저장' : '등록'}</button>
            ${isEdit ? `<button class="btn-danger" onclick="App.deleteCustomer(${c.id})">삭제</button>` : ''}
        `;

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

    async function saveCustomer(isEdit) {
        const data = {
            phone: document.getElementById('cfPhone').value,
            name: document.getElementById('cfName').value,
            pet_name: document.getElementById('cfPetName').value,
            breed: document.getElementById('cfBreed').value,
            weight: document.getElementById('cfWeight').value || null,
            age: document.getElementById('cfAge').value,
            notes: document.getElementById('cfNotes').value,
            memo: document.getElementById('cfMemo').value,
        };

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
                closeSheet('customerFormSheet');
                closeSheet('customerDetailSheet');
                toast('삭제되었습니다');
            }
        } catch (e) {
            toast('삭제 실패');
        }
    }

    async function showCustomerDetail(cid) {
        const content = document.getElementById('customerDetailContent');
        content.innerHTML = '<div class="loading">불러오는 중</div>';
        openSheet('customerDetailSheet');

        try {
            const res = await fetch(`/api/customer/${cid}`);
            const c = await res.json();

            const stats = c.stats || { count: 0, total: 0, avg: 0 };
            let historyHtml = '';
            if (c.reservations && c.reservations.length) {
                historyHtml = c.reservations.map(r => {
                    const statusLabel = STATUS_LABEL[r.status] || r.status;
                    return `
                        <div class="history-item" onclick="App.showReservationDetail(${r.id}); App.closeSheet('customerDetailSheet')">
                            <span class="history-date">${r.date}</span>
                            <span class="history-service">${esc(r.service_type)}</span>
                            <span class="history-amount">${r.amount ? r.amount.toLocaleString() + '원' : '-'}</span>
                            <span class="history-status res-status ${r.status}">${statusLabel}</span>
                        </div>
                    `;
                }).join('');
            } else {
                historyHtml = '<p style="text-align:center;color:#999;padding:20px">예약 이력 없음</p>';
            }

            content.innerHTML = `
                <div class="detail-section">
                    <div class="detail-row">
                        <span class="label">반려동물</span>
                        <span class="value">${esc(c.pet_name)} (${esc(c.breed)})</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">보호자</span>
                        <span class="value">${esc(c.name || '-')}</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">전화</span>
                        <span class="value"><a href="tel:${c.phone}" style="color:var(--primary)">${esc(c.phone_display)}</a></span>
                    </div>
                    ${c.weight ? `<div class="detail-row"><span class="label">몸무게</span><span class="value">${c.weight}kg</span></div>` : ''}
                    ${c.age ? `<div class="detail-row"><span class="label">나이</span><span class="value">${esc(c.age)}</span></div>` : ''}
                    ${c.notes ? `<div class="detail-row"><span class="label">특이사항</span><span class="value">${esc(c.notes)}</span></div>` : ''}
                    ${c.memo ? `<div class="detail-row"><span class="label">메모</span><span class="value">${esc(c.memo)}</span></div>` : ''}
                    ${c.last_visit ? `<div class="detail-row"><span class="label">마지막 방문</span><span class="value">${c.last_visit}</span></div>` : ''}
                </div>

                <div class="stat-cards">
                    <div class="stat-card">
                        <div class="num">${stats.count}</div>
                        <div class="label">방문 횟수</div>
                    </div>
                    <div class="stat-card">
                        <div class="num">${stats.total ? stats.total.toLocaleString() : 0}</div>
                        <div class="label">총 매출</div>
                    </div>
                    <div class="stat-card">
                        <div class="num">${stats.avg ? stats.avg.toLocaleString() : 0}</div>
                        <div class="label">평균 단가</div>
                    </div>
                </div>

                <div class="detail-section">
                    <h4>예약 이력</h4>
                    ${historyHtml}
                </div>

                <button class="btn-secondary" onclick="App.showCustomerForm_edit(${cid})">정보 수정</button>
            `;
        } catch (e) {
            content.innerHTML = '<p style="text-align:center;color:#999;padding:20px">불러오기 실패</p>';
        }
    }

    async function showCustomerForm_edit(cid) {
        closeSheet('customerDetailSheet');
        try {
            const res = await fetch(`/api/customer/${cid}`);
            const c = await res.json();
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
                return `
                    <div class="history-item">
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

        // 전화 뱃지 업데이트
        const badge = document.getElementById('callBadge');
        const count = parseInt(badge.textContent || '0') + 1;
        badge.textContent = count;
        badge.style.display = 'flex';

        if (data.is_existing) {
            const visitInfo = data.visit_count ? `${data.visit_count}회 방문` : '';
            const lastVisit = data.last_visit ? `마지막: ${data.last_visit}` : '';
            const meta = [visitInfo, lastVisit].filter(Boolean).join(' | ');
            content.innerHTML = `
                <div class="call-info-existing">
                    <div class="call-phone">${esc(data.phone_display)}</div>
                    <div class="call-customer">${esc(data.pet_name)} (${esc(data.breed)}) - ${esc(data.customer_name)}</div>
                    ${meta ? `<div class="call-customer">${esc(meta)}</div>` : ''}
                </div>
                <div class="call-actions">
                    <button class="call-btn-reserve" onclick="App.reserveFromCall(${data.customer_id})">예약하기</button>
                    <button class="call-btn-dismiss" onclick="App.closeCallPopup()">닫기</button>
                </div>
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

    function reserveFromCall(customerId) {
        closeCallPopup();
        // 오늘 날짜 선택 후 빈슬롯 선택 유도
        const now = new Date();
        const todayStr = fmtDate(now);
        selectedDate = todayStr;
        currentYear = now.getFullYear();
        currentMonth = now.getMonth() + 1;
        showView('calendar');
        loadMonth().then(() => selectDate(todayStr));
        toast('날짜에서 빈 슬롯을 선택하세요');
    }

    function registerFromCall(phone) {
        closeCallPopup();
        showView('customers');
        showCustomerForm({ phone: phone, phone_display: phone });
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
        return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    function openSheet(id) {
        document.getElementById(id).style.display = 'flex';
    }

    function closeSheet(id) {
        document.getElementById(id).style.display = 'none';
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
            const res = await fetch('/api/call-history');
            const data = await res.json();
            const history = data.history || [];
            const filtered = history.filter(h => h.created_at && h.created_at.startsWith(targetDate));
            if (!filtered.length) {
                container.innerHTML = '<p style="text-align:center;color:#999;padding:20px;font-size:13px">전화 이력 없음</p>';
                return;
            }
            container.innerHTML = filtered.map(h => {
                const isKnown = !!(h.c_pet_name || h.pet_name);
                const name = h.c_pet_name || h.pet_name || '';
                const time = h.created_at ? h.created_at.substring(11, 16) : '';
                const cls = isKnown ? 'known' : 'unknown';
                return '<div class="call-sidebar-item ' + cls + '">' +
                    '<span class="call-sidebar-time">' + esc(time) + ' ' + (name ? esc(name) : '신규') + '</span>' +
                    '<span class="call-sidebar-phone">' + esc(h.phone_display) + '</span>' +
                    '</div>';
            }).join('');
        } catch (e) {
            container.innerHTML = '<p style="text-align:center;color:#999;padding:12px;font-size:12px">로드 실패</p>';
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

    // 초기화
    init();

    // Public API
    return {
        selectDate, closeTimeline, changeMonth, goToday,
        showView, onSlotClick, searchCustomersForSlot,
        showNewCustomerFormForSlot, showNewCustomerForm,
        onServiceChange, saveReservation,
        showReservationDetail, showEditReservation,
        updateReservation, changeStatus,
        searchCustomers, showCustomerDetail,
        showCustomerForm_edit,
        saveCustomer, deleteCustomer, onBreedInput, onBreedKeydown, selectBreed,
        toggleCallHistory, showCallPopup, closeCallPopup,
        reserveFromCall, registerFromCall, downloadBackup,
        openSheet, closeSheet,
        showCustomerForm, showReservationForm,
        changeCallDate, refresh, onQuickReserve, testCall,
        selectGridBtn, applyPrevService,
    };
})();
