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
        
        // Try to get key from server session
        const response = await fetch('/api/abe/session-key/', {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Store in session storage
            sessionStorage.setItem('abe_secret_key', JSON.stringify(data.data));
            window.abeSystem.secretKey = data.data;
            updateKeyStatus('success', `Secret Key đã được tải (${data.source})`, data.data.attributes);
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
        
        const response = await fetch('/api/abe/secret-key/', {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Update session storage
            sessionStorage.setItem('abe_secret_key', JSON.stringify(data.data));
            window.abeSystem.secretKey = data.data;
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
        const response = await fetch('/api/abe/public-key/', {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            const modalTitle = document.getElementById('modalTitle');
            const modalBody = document.getElementById('modalBody');
            
            modalTitle.textContent = 'Waters11 Public Key Information';
            modalBody.innerHTML = `
                <div class="alert alert-info">
                    <i class="fas fa-info-circle"></i>
                    Waters11 Public Key và Attribute Mapping được sử dụng để mã hóa dữ liệu.
                </div>
                
                <h6>Scheme Information:</h6>
                <div class="bg-light p-2 mb-3">
                    <small>
                        <strong>Type:</strong> ${data.data.scheme_info.type}<br>
                        <strong>Universe Size:</strong> ${data.data.scheme_info.uni_size}
                    </small>
                </div>
                
                <h6>Attribute Mapping:</h6>
                <div class="bg-light p-2 mb-3" style="max-height: 150px; overflow-y: auto;">
                    <small>
                        ${Object.entries(data.data.attribute_mapping.name_to_int)
                          .map(([name, int]) => `<span class="badge bg-primary me-1">${name}:${int}</span>`)
                          .join('')}
                    </small>
                </div>
                
                <h6>Public Key Data:</h6>
                <div class="text-break">
                    <pre class="bg-light p-2 mt-2" style="max-height: 200px; overflow-y: auto; font-size: 0.75rem;">
${JSON.stringify(data.data.public_key, null, 2)}
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

// Helper function to get CSRF token
function getCSRFToken() {
    const name = 'csrftoken';
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
} 