document.addEventListener('DOMContentLoaded', () => {
    // 1. Injetar Sino na Navbar
    const navRight = document.querySelector('.nav-right');
    if (navRight) {
        const bellHtml = `
            <div id="notif-container" style="position: relative; margin-right: 15px; cursor: pointer;" onclick="openNotifModal()">
                <div style="background: transparent; border: none; font-size: 20px;">🔔</div>
                <span id="notif-badge" style="display: none; position: absolute; top: -5px; right: -8px; background: #dc3545; color: white; border-radius: 50%; padding: 2px 6px; font-size: 11px; font-weight: bold; box-shadow: 0 0 0 2px var(--primary-blue);">0</span>
            </div>
        `;
        navRight.insertAdjacentHTML('afterbegin', bellHtml);
    }

    // 2. Injetar Modal no Body
    const modalHtml = `
        <div id="notif-modal" class="modal" style="display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 9999; justify-content: center; align-items: center;">
            <div class="modal-content" style="background: white; padding: 20px; border-radius: 8px; width: 90%; max-width: 450px; max-height: 80vh; overflow-y: auto; position: relative;">
                <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #ddd; padding-bottom: 10px; margin-bottom: 10px;">
                    <h3 style="margin: 0;">Central de Notificações</h3>
                    <button onclick="closeNotifModal()" style="background: transparent; border: none; font-size: 24px; cursor: pointer;">&times;</button>
                </div>
                <div id="notif-list" style="font-size: 14px;">Carregando...</div>
            </div>
        </div>
    `;
    document.body.insertAdjacentHTML('beforeend', modalHtml);

    // 3. Buscar Notificações periodicamente
    fetchNotificacoes();
    setInterval(fetchNotificacoes, 60000); // 1 minuto
});

function fetchNotificacoes() {
    fetch('/api/notificacoes')
        .then(res => {
            if (!res.ok) throw new Error('Não logado');
            return res.json();
        })
        .then(data => {
            if (data.error) return;
            const badge = document.getElementById('notif-badge');
            if (badge) {
                if (data.nao_lidas > 0) {
                    badge.innerText = data.nao_lidas > 99 ? '+99' : data.nao_lidas;
                    badge.style.display = 'block';
                } else {
                    badge.style.display = 'none';
                }
            }
            
            const list = document.getElementById('notif-list');
            if (list && data.notificacoes) {
                if (data.notificacoes.length > 0) {
                    list.innerHTML = data.notificacoes.map(n => {
                        const dateStr = new Date(n.data_criacao).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
                        return `
                            <div style="padding: 12px 10px; border-bottom: 1px solid #eee; ${n.lida ? 'opacity: 0.7;' : 'background: rgba(58, 110, 165, 0.05); font-weight: bold; border-left: 3px solid #3A6EA5;'}">
                                <div style="font-size: 11px; color: #888; margin-bottom: 4px;">${dateStr}</div>
                                <div>${n.mensagem}</div>
                            </div>
                        `;
                    }).join('');
                } else {
                    list.innerHTML = '<div style="text-align: center; color: #888; padding: 30px;">Pronto! Você não tem novas notificações.</div>';
                }
            }
        }).catch(err => console.log(err));
}

function openNotifModal() {
    const modal = document.getElementById('notif-modal');
    if (modal) modal.style.display = 'flex';
    
    // Marcar como lidas se houver badge
    const badge = document.getElementById('notif-badge');
    if (badge && badge.style.display !== 'none') {
        fetch('/api/ler_notificacoes', {method: 'POST'})
            .then(() => {
                badge.style.display = 'none';
                // Remove negrito visualmente apos um tempinho
                setTimeout(fetchNotificacoes, 2000); 
            });
    }
}
function closeNotifModal() {
    const modal = document.getElementById('notif-modal');
    if (modal) modal.style.display = 'none';
}
