/**
 * Dashboard JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('Dashboard loaded');
    
    // Check ABE key status on page load
    checkKeyStatus();
});

/**
 * Check and display ABE key status
 */
async function checkKeyStatus() {
    const keyStatusDiv = document.getElementById('key-status');
    
    if (!keyStatusDiv) return;
    
    try {
        // Show loading state
        updateKeyStatus('loading', 'Đang kiểm tra trạng thái key...');
        
        // Check if key exists in session storage
        const storedKey = getStoredABEKey();
        
        if (storedKey) {
            updateKeyStatus('success', 'Secret Key đã sẵn sàng', storedKey.attributes);
            return;
        }
        
        // Try to get key from server
        const response = await fetch('/api/abe/session-key/');
        const data = await response.json();
        
        if (data.success) {
            // Store in session storage
            sessionStorage.setItem('abe_secret_key', JSON.stringify(data.data));
            updateKeyStatus('success', 'Secret Key đã được tải', data.data.attributes);
        } else {
            updateKeyStatus('error', 'Không thể tải Secret Key', null, data.message);
        }
        
    } catch (error) {
        console.error('Error checking key status:', error);
        updateKeyStatus('error', 'Lỗi kết nối', null, 'Không thể kết nối đến server');
    }
}

/**
 * Update key status display
 */
function updateKeyStatus(type, message, attributes = null, detail = null) {
    const keyStatusDiv = document.getElementById('key-status');
    if (!keyStatusDiv) return;
    
    let badgeClass, icon;
    
    switch (type) {
        case 'success':
            badgeClass = 'bg-success';
            icon = 'fas fa-check-circle';
            break;
        case 'loading':
            badgeClass = 'bg-secondary';
            icon = 'fas fa-spinner fa-spin';
            break;
        case 'error':
            badgeClass = 'bg-danger';
            icon = 'fas fa-exclamation-triangle';
            break;
        default:
            badgeClass = 'bg-info';
            icon = 'fas fa-info-circle';
    }
    
    let html = `
        <span class="badge ${badgeClass}">
            <i class="${icon}"></i> ${message}
        </span>
    `;
    
    if (attributes && attributes.length > 0) {
        html += `
            <div class="mt-2">
                <small class="text-muted">Attributes: </small>
                ${attributes.map(attr => `<span class="badge bg-primary me-1">${attr}</span>`).join('')}
            </div>
        `;
    }
    
    if (detail) {
        html += `
            <div class="mt-1">
                <small class="text-muted">${detail}</small>
            </div>
        `;
    }
    
    keyStatusDiv.innerHTML = html;
}

/**
 * Get stored ABE key from session storage
 */
function getStoredABEKey() {
    try {
        const stored = sessionStorage.getItem('abe_secret_key');
        return stored ? JSON.parse(stored) : null;
    } catch (error) {
        console.error('Error getting stored ABE key:', error);
        return null;
    }
}

/**
 * Refresh secret key
 */
async function refreshKey() {
    try {
        updateKeyStatus('loading', 'Đang tạo Secret Key mới...');
        
        const response = await fetch('/api/abe/secret-key/');
        const data = await response.json();
        
        if (data.success) {
            // Update session storage
            sessionStorage.setItem('abe_secret_key', JSON.stringify(data.data));
            updateKeyStatus('success', 'Secret Key đã được làm mới', data.data.attributes);
            showNotification('Secret Key đã được làm mới thành công!', 'success');
        } else {
            updateKeyStatus('error', 'Không thể tạo Secret Key', null, data.message);
            showNotification('Lỗi: ' + data.message, 'danger');
        }
        
    } catch (error) {
        console.error('Error refreshing key:', error);
        updateKeyStatus('error', 'Lỗi kết nối', null, 'Không thể kết nối đến server');
        showNotification('Lỗi kết nối đến server', 'danger');
    }
}

/**
 * Show public key information
 */
async function showPublicKey() {
    try {
        const response = await fetch('/api/abe/public-key/');
        const data = await response.json();
        
        if (data.success) {
            const modalTitle = document.getElementById('modalTitle');
            const modalBody = document.getElementById('modalBody');
            
            modalTitle.textContent = 'Public Key Information';
            modalBody.innerHTML = `
                <div class="alert alert-info">
                    <i class="fas fa-info-circle"></i>
                    Public Key được sử dụng để mã hóa dữ liệu. Key này có thể chia sẻ công khai.
                </div>
                <div class="text-break">
                    <strong>Public Key Data:</strong>
                    <pre class="bg-light p-2 mt-2" style="max-height: 300px; overflow-y: auto; font-size: 0.8rem;">
${JSON.stringify(data.public_key, null, 2)}
                    </pre>
                </div>
            `;
            
            // Show modal
            const modal = new bootstrap.Modal(document.getElementById('infoModal'));
            modal.show();
        } else {
            showNotification('Không thể lấy Public Key: ' + data.message, 'danger');
        }
        
    } catch (error) {
        console.error('Error getting public key:', error);
        showNotification('Lỗi kết nối đến server', 'danger');
    }
}

/**
 * Check if user can decrypt a specific policy
 */
function checkDecryptAccess(dataId, policy) {
    const storedKey = getStoredABEKey();
    
    if (!storedKey || !storedKey.attributes) {
        showNotification('Chưa có Secret Key. Vui lòng làm mới key.', 'warning');
        return;
    }
    
    // Simple policy check - check if user has any attribute mentioned in policy
    const userAttributes = storedKey.attributes;
    const canDecrypt = userAttributes.some(attr => 
        policy.toLowerCase().includes(attr.toLowerCase())
    );
    
    const modalTitle = document.getElementById('modalTitle');
    const modalBody = document.getElementById('modalBody');
    
    modalTitle.textContent = 'Kiểm tra quyền giải mã';
    
    if (canDecrypt) {
        modalBody.innerHTML = `
            <div class="alert alert-success">
                <i class="fas fa-check-circle"></i>
                <strong>Bạn CÓ THỂ giải mã file này!</strong>
            </div>
            <div>
                <strong>Policy cần thiết:</strong> ${policy}
            </div>
            <div class="mt-2">
                <strong>Attributes của bạn:</strong>
                <div class="mt-1">
                    ${userAttributes.map(attr => `<span class="badge bg-primary me-1">${attr}</span>`).join('')}
                </div>
            </div>
        `;
    } else {
        modalBody.innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-times-circle"></i>
                <strong>Bạn KHÔNG THỂ giải mã file này!</strong>
            </div>
            <div>
                <strong>Policy cần thiết:</strong> ${policy}
            </div>
            <div class="mt-2">
                <strong>Attributes của bạn:</strong>
                <div class="mt-1">
                    ${userAttributes.map(attr => `<span class="badge bg-secondary me-1">${attr}</span>`).join('')}
                </div>
            </div>
            <div class="mt-2">
                <small class="text-muted">
                    Bạn cần có ít nhất một attribute phù hợp với policy để có thể giải mã.
                </small>
            </div>
        `;
    }
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('infoModal'));
    modal.show();
}

/**
 * Show notification
 */
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    notification.style.cssText = 'top: 100px; right: 20px; z-index: 9999; min-width: 300px;';
    
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(notification);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.classList.remove('show');
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.remove();
                }
            }, 150);
        }
    }, 5000);
}

// Export functions for global use
window.refreshKey = refreshKey;
window.showPublicKey = showPublicKey;
window.checkKeyStatus = checkKeyStatus;
window.checkDecryptAccess = checkDecryptAccess; 