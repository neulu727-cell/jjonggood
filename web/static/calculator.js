/* === 견적 계산기 === */

const Calc = (() => {
    // 상태
    let breedType = '일반';   // '일반' | '특수'
    let weightRange = '';      // '1-3', '3-5', ... (선택 안 하면 빈 문자열)
    let serviceChoice = '위생목욕';
    let clippingLength = '3mm';
    let faceCut = false;
    let matting = 'none';
    let furLength = '짧다';

    function init() {
        updateServiceUI();
        updatePrice();
    }

    // === 견종 타입 선택 ===
    function selectBreedType(type) {
        breedType = type;
        document.getElementById('breedInput').value = type;
        document.querySelectorAll('.breed-btn').forEach(el => {
            el.classList.toggle('active', el.dataset.breed === type);
        });
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
        // 서비스 바꾸면 faceCut 초기화
        if (svc !== '클리핑') {
            faceCut = false;
        }
        updateServiceUI();
        updatePrice();
    }

    function updateServiceUI() {
        // 클리핑 옵션 표시
        document.getElementById('clippingOptions').style.display =
            serviceChoice === '클리핑' ? '' : 'none';

        // 털길이 옵션 (위생목욕만)
        document.getElementById('furLengthRow').style.display =
            serviceChoice === '위생목욕' ? '' : 'none';

        // 얼굴커트: 클리핑 선택 시만 표시
        const faceCutRow = document.getElementById('faceCutRow');
        if (serviceChoice === '클리핑') {
            faceCutRow.style.display = '';
            const hint = document.getElementById('faceCutHint');
            hint.textContent = faceCut ? '→ 전체얼컷' : '→ 전체미용';
            document.querySelectorAll('#faceCutToggle .toggle-btn').forEach(btn => {
                btn.classList.toggle('active', String(faceCut) === btn.dataset.val);
            });
        } else {
            faceCutRow.style.display = 'none';
        }
    }

    // === 클리핑 길이 선택 ===
    function selectClipping(len) {
        clippingLength = len;
        document.querySelectorAll('#clippingOptions .chip').forEach(el => {
            el.classList.toggle('active', el.dataset.length === len);
        });
        updatePrice();
    }

    // === 얼굴커트 토글 ===
    function setFaceCut(val) {
        faceCut = val;
        updateServiceUI();
        updatePrice();
    }

    // === 엉킴 정도 ===
    function setMatting(val) {
        matting = val;
        document.querySelectorAll('#mattingToggle .toggle-btn').forEach(el => {
            el.classList.toggle('active', el.dataset.val === val);
        });
        updatePrice();
    }

    // === 털길이 ===
    function setFurLength(val) {
        furLength = val;
        document.querySelectorAll('#furLengthToggle .toggle-btn').forEach(el => {
            el.classList.toggle('active', el.dataset.val === val);
        });
        updatePrice();
    }

    // === 가격 계산 (클라이언트) ===
    function calculatePrice() {
        // 특수견종은 "상담 필요"
        if (breedType === '특수') {
            return { total: 0, actualService: '', details: [], isSpecial: true };
        }

        // 몸무게 미선택
        if (!weightRange) {
            return { total: 0, actualService: '', details: [], isSpecial: false };
        }

        // 서비스 매핑
        let actualService;
        if (serviceChoice === '클리핑') {
            actualService = faceCut ? '전체얼컷' : '전체미용';
        } else if (serviceChoice === '스포팅') {
            actualService = '스포팅';
        } else {
            actualService = '위생목욕';
        }

        // base price from weight range
        const rangeData = PRICE_TABLE[weightRange];
        let basePrice = rangeData ? (rangeData.prices[actualService] || 0) : 0;

        let total = basePrice;
        const details = [];

        if (basePrice > 0) {
            details.push(`기본(${actualService}): ${basePrice.toLocaleString()}원`);
        }

        // 클리핑 길이 추가금
        if (serviceChoice === '클리핑') {
            if (clippingLength === '1.3cm') {
                total += SURCHARGES['clipping_1.3cm'];
                details.push(`클리핑 1.3cm: +${SURCHARGES['clipping_1.3cm'].toLocaleString()}원`);
            } else if (clippingLength === '2cm') {
                total += SURCHARGES['clipping_2cm'];
                details.push(`클리핑 2cm: +${SURCHARGES['clipping_2cm'].toLocaleString()}원`);
            }
        }

        // 엉킴
        if (matting === 'light') {
            total += SURCHARGES['matting_light'];
            details.push(`엉킴(조금): +${SURCHARGES['matting_light'].toLocaleString()}원`);
        } else if (matting === 'heavy') {
            total += SURCHARGES['matting_heavy'];
            details.push(`엉킴(심함): +${SURCHARGES['matting_heavy'].toLocaleString()}원`);
        }

        // 털길이 (위생목욕만)
        if (serviceChoice === '위생목욕') {
            if (furLength === '중간') {
                total += SURCHARGES['fur_medium'];
                details.push(`털길이(중간): +${SURCHARGES['fur_medium'].toLocaleString()}원`);
            } else if (furLength === '길다') {
                total += SURCHARGES['fur_long'];
                details.push(`털길이(길다): +${SURCHARGES['fur_long'].toLocaleString()}원`);
            }
        }

        return { total, actualService, details, isSpecial: false };
    }

    function updatePrice() {
        const { total, details, isSpecial } = calculatePrice();
        const el = document.getElementById('priceAmount');
        if (isSpecial) {
            el.textContent = '상담 필요';
            document.getElementById('priceDetail').textContent = '비숑, 대형견 등은 상담 후 안내드립니다';
        } else if (total > 0) {
            el.textContent = `${total.toLocaleString()}원`;
            document.getElementById('priceDetail').textContent =
                details.length > 1 ? details.join(' / ') : '';
        } else {
            el.textContent = '0원';
            document.getElementById('priceDetail').textContent = '몸무게를 선택해주세요';
        }
    }

    // === 견적 전송 ===
    async function submitRequest() {
        const breed = document.getElementById('breedInput').value.trim();
        if (!breed) {
            showToast('견종을 선택해주세요');
            return;
        }
        if (!weightRange && breedType !== '특수') {
            showToast('몸무게를 선택해주세요');
            return;
        }

        // weightRange에서 중간값 추출 (예: '3-5' → 4)
        let weightKg = 0;
        if (weightRange) {
            const parts = weightRange.split('-');
            weightKg = (parseFloat(parts[0]) + parseFloat(parts[1])) / 2;
        }

        const customerName = document.getElementById('customerName').value.trim();
        const customerPhone = document.getElementById('customerPhone').value.trim();
        const memo = document.getElementById('customerMemo').value.trim();

        const { total } = calculatePrice();

        const btn = document.getElementById('submitBtn');
        btn.disabled = true;
        btn.textContent = '전송 중...';

        try {
            const resp = await fetch('/api/grooming-request', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    breed,
                    weight_kg: weightKg,
                    service_choice: serviceChoice,
                    clipping_length: serviceChoice === '클리핑' ? clippingLength : '',
                    face_cut: faceCut,
                    matting,
                    fur_length: serviceChoice === '위생목욕' ? furLength : '',
                    customer_name: customerName,
                    customer_phone: customerPhone,
                    memo,
                }),
            });

            const data = await resp.json();
            const resultEl = document.getElementById('submitResult');
            resultEl.style.display = '';

            if (resp.ok && data.ok) {
                resultEl.className = 'submit-result success';
                resultEl.textContent = '견적 요청이 성공적으로 전송되었습니다!';
                showToast('전송 완료!');
            } else {
                resultEl.className = 'submit-result error';
                resultEl.textContent = data.error || '전송에 실패했습니다.';
            }
        } catch (e) {
            const resultEl = document.getElementById('submitResult');
            resultEl.style.display = '';
            resultEl.className = 'submit-result error';
            resultEl.textContent = '네트워크 오류가 발생했습니다.';
        } finally {
            btn.disabled = false;
            btn.textContent = '이 견적요청서를 전송하시겠습니까?';
        }
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
        setMatting,
        setFurLength,
        selectBreedType,
        selectWeight,
        submitRequest,
    };
})();
