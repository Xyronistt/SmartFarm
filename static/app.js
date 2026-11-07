let knownPendingIds = new Set();

async function checkPendingDevices() {
    try {
        const res = await fetch('/api/devices');
        const data = await res.json();
        data.devices.forEach(dev => {
            if (dev.status === 'pending' && !knownPendingIds.has(dev.device_id)) {
                knownPendingIds.add(dev.device_id);
                showToast(`Обнаружен новый модуль: ${dev.name} (${dev.subtype})`);
            }
        });
    } catch (e) {
        console.error("Ошибка опроса автообнаружения:", e);
    }
}

function showToast(message) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerHTML = `
        <div style="flex: 1;">
            <div style="font-weight: 600; font-size: 12px; color: #0f172a;">Auto-Discovery</div>
            <div style="color: #64748b;">${message}</div>
        </div>
        <a href="/devices/" class="btn btn-success" style="padding: 6px 12px;">Настроить</a>
    `;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        toast.style.transition = 'all .3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 7000);
}

setInterval(checkPendingDevices, 5000);