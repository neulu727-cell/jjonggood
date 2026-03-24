/* === 견적 계산기 === */

const Calc = (() => {
    // 상태
    let breedType = '일반';   // '일반' | '비숑'
    let weightRange = '';      // '0-4', '4-6', '6-8', '8-10'
    let serviceChoice = '위생목욕';
    let clippingLength = '3mm';
    let faceCut = false;

    // 유입 채널 감지
    function detectSource() {
        const ua = navigator.userAgent || '';
        if (/KAKAOTALK/i.test(ua)) return 'kakao';
        if (/NAVER/i.test(ua)) return 'naver';
        return 'web';
    }
    const SOURCE = detectSource();

    function init() {
        updateServiceUI();
        updatePrice();
        updateConsultButtons();
        initTooltip();
    }

    // === 전체위생 칩 툴팁 ===
    function initTooltip() {
        const chip = document.getElementById('chipHygiene');
        if (!chip) return;
        chip.addEventListener('click', () => {
            const tooltip = document.getElementById('hygieneTooltip');
            if (tooltip) tooltip.classList.toggle('show');
        });
    }

    // === 견종 타입 선택 ===
    function selectBreedType(type) {
        breedType = type;
        document.getElementById('breedInput').value = type;
        document.querySelectorAll('.breed-btn').forEach(el => {
            el.classList.toggle('active', el.dataset.breed === type);
        });
        updateServiceUI();
        updatePrice();
    }

    // === 몸무게 구간 선택 ===
    function selectWeight(range) {
        weightRange = range;
        document.querySelectorAll('.weight-btn').forEach(el => {
            el.classList.toggle('active', el.dataset.weight === range);
        });
        updatePrice();
    }

    // === 서비스 선택 ===
    function selectService(svc) {
        serviceChoice = svc;
        document.querySelectorAll('.service-tab').forEach(el => {
            el.classList.toggle('active', el.dataset.service === svc);
        });
        if (svc !== '클리핑') {
            faceCut = false;
        }
        updateServiceUI();
        updatePrice();
    }

    function updateServiceUI() {
        const isClipping = serviceChoice === '클리핑';
        const isSporting = serviceChoice === '스포팅';

        // 클리핑 길이 옵션
        document.getElementById('clippingOptions').style.display = isClipping ? '' : 'none';

        // 스포팅 길이 옵션
        document.getElementById('sportingOptions').style.display = isSporting ? '' : 'none';

        // 스포팅 칩 active 상태 동기화
        if (isSporting) {
            document.querySelectorAll('#sportingOptions .chip').forEach(el => {
                el.classList.toggle('active', el.dataset.length === clippingLength);
            });
        }

        // 얼굴컷/비숑컷 토글
        const subOptions = document.getElementById('clippingSubOptions');
        subOptions.style.display = isClipping ? '' : 'none';

        if (isClipping) {
            // 비숑이면 "비숑컷", 일반이면 "얼굴컷"
            const label = document.getElementById('faceCutLabel');
            label.textContent = breedType === '비숑' ? '비숑컷' : '얼굴컷';

            const hint = document.getElementById('faceCutHint');
            if (faceCut) {
                hint.textContent = breedType === '비숑' ? '→ 클리핑+비숑컷' : '→ 클리핑+얼굴컷';
            } else {
                hint.textContent = '→ 클리핑';
            }

            document.querySelectorAll('#faceCutToggle .toggle-btn').forEach(btn => {
                btn.classList.toggle('active', String(faceCut) === btn.dataset.val);
            });

            // 비숑 + 클리핑(비숑컷X) → 일반과 동일 요금 안내
            const notice = document.getElementById('bichonClippingNotice');
            if (notice) {
                notice.style.display = (breedType === '비숑' && !faceCut) ? '' : 'none';
            }
        }
    }

    // === 클리핑/스포팅 길이 선택 ===
    function selectClipping(len) {
        clippingLength = len;
        document.querySelectorAll('#clippingOptions .chip, #sportingOptions .chip').forEach(el => {
            el.classList.toggle('active', el.dataset.length === len);
        });
        updatePrice();
    }

    // === 얼굴컷 토글 ===
    function setFaceCut(val) {
        faceCut = val;
        updateServiceUI();
        updatePrice();
    }

    // === 가격 계산 (클라이언트) ===
    function calculatePrice() {
        if (!weightRange) {
            return { total: 0, actualService: '', details: [] };
        }

        // 서비스 매핑 (특수견은 일반과 동일)
        const isBichon = breedType === '비숑';
        let actualService;
        if (serviceChoice === '클리핑') {
            if (faceCut) {
                actualService = isBichon ? '클리핑+비숑컷' : '클리핑+얼굴컷';
            } else {
                actualService = '클리핑';
            }
        } else if (serviceChoice === '스포팅') {
            actualService = '스포팅';
        } else {
            actualService = '위생목욕';
        }

        // breed별 요금표에서 조회 (특수견은 일반 요금 기준)
        const tableKey = breedType === '특수' ? '일반' : breedType;
        const breedTable = PRICE_TABLE[tableKey] || PRICE_TABLE['일반'];

        let basePrice = 0;
        const prices = breedTable[weightRange];
        if (prices) {
            basePrice = prices[actualService] || 0;
        }

        let total = basePrice;
        const details = [];

        if (basePrice > 0) {
            details.push(`기본(${actualService}): ${basePrice.toLocaleString()}원`);
        }

        // 클리핑 길이 추가금
        if (serviceChoice === '클리핑') {
            if (clippingLength === '13mm' && SURCHARGES['clipping_13mm']) {
                total += SURCHARGES['clipping_13mm'];
                details.push(`클리핑 13mm: +${SURCHARGES['clipping_13mm'].toLocaleString()}원`);
            } else if (clippingLength === '20mm' && SURCHARGES['clipping_20mm']) {
                total += SURCHARGES['clipping_20mm'];
                details.push(`클리핑 20mm: +${SURCHARGES['clipping_20mm'].toLocaleString()}원`);
            }
        }

        return { total, actualService, details };
    }

    function updatePrice() {
        const { total, details } = calculatePrice();
        const el = document.getElementById('priceAmount');
        const isSpecial = breedType === '특수';

        if (total > 0) {
            el.textContent = isSpecial
                ? `${total.toLocaleString()}원 ~`
                : `${total.toLocaleString()}원`;
            document.getElementById('priceDetail').textContent =
                details.length > 1 ? details.join(' / ') : '';
        } else {
            el.textContent = '0원';
            document.getElementById('priceDetail').textContent = '몸무게를 선택해주세요';
        }

        // 특수견 안내 표시
        const notice = document.getElementById('specialBreedNotice');
        if (notice) notice.style.display = isSpecial ? '' : 'none';
    }

    // === 유입 채널에 따라 버튼 표시 조정 ===
    function updateConsultButtons() {
        const container = document.querySelector('.consult-buttons');
        if (!container) return;

        if (SOURCE === 'kakao') {
            container.innerHTML = `
                <button class="consult-btn kakao single" onclick="Calc.consultVia('kakao')">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M12 3C6.48 3 2 6.58 2 10.9c0 2.78 1.86 5.22 4.65 6.6-.15.53-.96 3.4-.99 3.62 0 0-.02.17.09.23.11.07.24.01.24.01.32-.04 3.7-2.44 4.28-2.86.56.08 1.14.12 1.73.12 5.52 0 10-3.58 10-7.9S17.52 3 12 3z"/></svg>
                    <span>이 견적으로 카톡 상담하기</span>
                </button>`;
        } else if (SOURCE === 'naver') {
            container.innerHTML = `
                <button class="consult-btn naver single" onclick="Calc.consultVia('naver')">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M16.27 10.7L7.4 21h4.47l5.53-6.4V21H21V3h-3.6v7.7zM3 3v18h3.6V13.3L15.47 3H11L5.47 9.4V3H3z"/></svg>
                    <span>이 견적으로 톡톡 상담하기</span>
                </button>`;
        }
    }

    // === 상담 연결 ===
    function consultVia(channel) {
        const breed = document.getElementById('breedInput').value.trim();
        if (!breed) {
            showToast('견종을 선택해주세요');
            return;
        }
        if (!weightRange) {
            showToast('몸무게를 선택해주세요');
            return;
        }

        // weightRange에서 중간값 추출
        const parts = weightRange.split('-');
        const weightKg = (parseFloat(parts[0]) + parseFloat(parts[1])) / 2;

        // 견적 내용을 샵에 전송
        try {
            fetch('/api/grooming-request', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    breed,
                    breed_type: breedType,
                    weight_kg: weightKg,
                    service_choice: serviceChoice,
                    clipping_length: serviceChoice === '클리핑' ? clippingLength : '',
                    face_cut: faceCut,
                    customer_name: '',
                    customer_phone: '',
                    memo: JSON.stringify({ source: SOURCE, consult: channel }),
                }),
            });
        } catch (e) {
            // 전송 실패해도 상담 연결은 진행
        }

        // 인앱 브라우저면 닫기, 일반 브라우저면 채널로 이동
        if (SOURCE === 'kakao') {
            showSentOverlay(() => {
                location.href = 'kakaotalk://inappbrowser/close';
            });
        } else if (SOURCE === 'naver') {
            showSentOverlay(() => {
                history.back();
                setTimeout(() => {
                    const sub = document.querySelector('.sent-sub');
                    if (sub) sub.textContent = '← 뒤로가기를 눌러 대화방으로 돌아가주세요';
                }, 800);
            });
        } else {
            if (channel === 'kakao') {
                window.location.href = SHOP.kakao;
            } else if (channel === 'naver') {
                window.location.href = SHOP.naver;
            } else if (channel === 'phone') {
                window.location.href = 'tel:' + SHOP.phone;
            }
        }
    }

    function showSentOverlay(callback) {
        const overlay = document.createElement('div');
        overlay.className = 'sent-overlay';
        overlay.innerHTML = `
            <div class="sent-check">✓</div>
            <div class="sent-text">견적이 전송되었습니다</div>
            <div class="sent-sub">대화방으로 돌아갑니다...</div>
        `;
        document.body.appendChild(overlay);
        if (callback) setTimeout(callback, 1200);
    }

    function showToast(msg) {
        const el = document.getElementById('toast');
        el.textContent = msg;
        el.style.display = '';
        setTimeout(() => { el.style.display = 'none'; }, 2500);
    }

    // 초기화
    document.addEventListener('DOMContentLoaded', init);

    return {
        selectService,
        selectClipping,
        setFaceCut,
        selectBreedType,
        selectWeight,
        consultVia,
    };
})();
