/* === SSE 전화 알림 리스너 === */

(function() {
    let eventSource = null;
    let reconnectTimer = null;

    function connect() {
        if (eventSource) {
            eventSource.close();
        }

        eventSource = new EventSource('/api/call-stream');

        eventSource.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'incoming_call') {
                    App.showCallPopup(data);
                    // 브라우저 알림 (권한 있을 때)
                    if (Notification.permission === 'granted') {
                        const title = data.is_existing
                            ? `${data.pet_name} (${data.breed})`
                            : '미등록 번호';
                        new Notification('전화 수신', {
                            body: `${data.phone_display}\n${title}`,
                            icon: '/static/icon-192.png',
                            tag: 'incoming-call',
                        });
                    }
                }
            } catch (e) {
                // 하트비트 등 무시
            }
        };

        eventSource.onerror = function() {
            eventSource.close();
            // 5초 후 재연결
            clearTimeout(reconnectTimer);
            reconnectTimer = setTimeout(connect, 5000);
        };
    }

    // 알림 권한 요청
    if ('Notification' in window && Notification.permission === 'default') {
        // 사용자 인터랙션 후 요청
        document.addEventListener('click', function requestNotif() {
            Notification.requestPermission();
            document.removeEventListener('click', requestNotif);
        }, { once: true });
    }

    // SSE 연결 시작
    connect();
})();
