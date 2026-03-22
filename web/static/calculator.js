/* === 견적 계산기 === */

const Calc = (() => {
    // 상태
    let serviceChoice = '위생목욕';
    let clippingLength = '3mm';
    let faceCut = false;
    let matting = 'none';
    let furLength = '짧다';

    function init() {
        // 견종 자동완성
        const breedInput = document.getElementById('breedInput');
        const dropdown = document.getElementById('breedDropdown');

        breedInput.addEventListener('input', () => {
            const val = breedInput.value.trim().toLowerCase();
            if (!val) { dropdown.style.display = 'none'; return; }
            const matches = BREEDS.filter(b => b.toLowerCase().includes(val));
            if (matches.length === 0) { dropdown.style.display = 'none'; return; }
            dropdown.innerHTML = matches.map(b =>
                `<div class="breed-option" onclick="Calc.selectBreed('${b}')">${b}</div>`
            ).join('');
            dropdown.style.display = '';
        });

        breedInput.addEventListener('blur', () => {
            setTimeout(() => { dropdown.style.display = 'none'; }, 200);
        });

        breedInput.addEventListener('focus', () => {
            if (breedInput.value.trim()) breedInput.dispatchEvent(new Event('input'));
        });

        // 몸무게/견종 변경 시 가격 업데이트
        document.getElementById('weightInput').addEventListener('input', updatePrice);
        breedInput.addEventListener('input', updatePrice);

        // 초기 UI 상태
        updateServiceUI();
        updatePrice();
    }

    // === 서비스 선택 ===
    function selectService(svc) {
        serviceChoice = svc;
        document.querySelectorAll('.service-tab').forEach(el => {
            el.classList.toggle('active', el.dataset.service === svc);
        });
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

        // 얼굴커트 힌트 & 상태
        const hint = document.getElementById('faceCutHint');
        const toggleBtns = document.querySelectorAll('#faceCutToggle .toggle-btn');

        if (serviceChoice === '스포팅') {
            hint.textContent = '스포팅에 이미 포함';
            toggleBtns.forEach(btn => {
                btn.disabled = true;
                btn.classList.remove('active');
            });
            faceCut = false;
        } else if (serviceChoice === '클리핑') {
            hint.textContent = faceCut ? '→ 전체얼컷' : '→ 전체미용';
            toggleBtns.forEach(btn => {
                btn.disabled = false;
                btn.classList.toggle('active', String(faceCut) === btn.dataset.val);
            });
        } else {
            hint.textContent = faceCut ? '+15,000원' : '';
            toggleBtns.forEach(btn => {
                btn.disabled = false;
                btn.classList.toggle('active', String(faceCut) === btn.dataset.val);
            });
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

    // === 견종 선택 ===
    function selectBreed(breed) {
        document.getElementById('breedInput').value = breed;
        document.getElementById('breedDropdown').style.display = 'none';
        updatePrice();
    }

    // === 가격 계산 (클라이언트) ===
    function calculatePrice() {
        const weightStr = document.getElementById('weightInput').value;
        const weightKg = parseFloat(weightStr) || 0;

        // 서비스 매핑
        let actualService;
        if (serviceChoice === '클리핑') {
            actualService = faceCut ? '전체얼컷' : '전체미용';
        } else if (serviceChoice === '스포팅') {
            actualService = '스포팅';
        } else {
            actualService = '위생목욕';
        }

        // base price
        let basePrice = 0;
        if (weightKg > 0) {
            for (const key in PRICE_TABLE) {
                const range = PRICE_TABLE[key];
                if (weightKg >= range.min && weightKg < range.max) {
                    basePrice = range.prices[actualService] || 0;
                    break;
                }
            }
            // 15kg 이상
            if (basePrice === 0 && weightKg >= 15) {
                const last = PRICE_TABLE['13-15'];
                if (last) basePrice = last.prices[actualService] || 0;
            }
            // 1kg 미만
            if (basePrice === 0 && weightKg > 0 && weightKg < 1) {
                const first = PRICE_TABLE['1-3'];
                if (first) basePrice = first.prices[actualService] || 0;
            }
        }

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

        // 위생목욕 + 얼굴커트
        if (serviceChoice === '위생목욕' && faceCut) {
            total += SURCHARGES['face_cut'];
            details.push(`얼굴커트: +${SURCHARGES['face_cut'].toLocaleString()}원`);
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

        return { total, actualService, details };
    }

    function updatePrice() {
        const { total, details } = calculatePrice();
        const el = document.getElementById('priceAmount');
        el.textContent = total > 0 ? `${total.toLocaleString()}원` : '0원';
        document.getElementById('priceDetail').textContent =
            details.length > 1 ? details.join(' / ') : '';
    }

    // === 견적 전송 ===
    async function submitRequest() {
        const breed = document.getElementById('breedInput').value.trim();
        if (!breed) {
            showToast('견종을 입력해주세요');
            return;
        }

        const weightKg = parseFloat(document.getElementById('weightInput').value) || 0;
        const customerName = document.getElementById('customerName').value.trim();
        const customerPhone = document.getElementById('customerPhone').value.trim();
        const memo = document.getElementById('customerMemo').value.trim();

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
        selectBreed,
        submitRequest,
    };
})();
