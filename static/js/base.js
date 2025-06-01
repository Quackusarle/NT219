/**
 * Base JavaScript - Common functions for all pages
 */

// Global variables
window.abeSystem = {
    publicKey: null,
    secretKey: null,
    sessionKey: null
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('Base JS loaded');
    initializeABESystem();
});

/**
 * Initialize ABE system
 */
function initializeABESystem() {
    // Check if user is authenticated
    if (document.querySelector('[data-user-authenticated="true"]')) {
        loadABEKeys();
    }
}

/**
 * Load ABE keys from session storage
 */
function loadABEKeys() {
    try {
        // Load secret key from session storage
        const secretKeyData = sessionStorage.getItem('abe_secret_key');
        if (secretKeyData) {
            window.abeSystem.secretKey = JSON.parse(secretKeyData);
            console.log('ABE secret key loaded from session');
        }
        
        // Load public key from session storage
        const publicKeyData = sessionStorage.getItem('abe_public_key');
        if (publicKeyData) {
            window.abeSystem.publicKey = JSON.parse(publicKeyData);
            console.log('ABE public key loaded from session');
        }
        
    } catch (error) {
        console.error('Error loading ABE keys:', error);
    }
}

/**
 * Get ABE secret key from server
 */
async function getSecretKey() {
    try {
        const response = await fetch('/api/abe/secret-key/', {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            if (data.success) {
                // Store in session storage
                sessionStorage.setItem('abe_secret_key', JSON.stringify(data.secret_key));
                window.abeSystem.secretKey = data.secret_key;
                console.log('Secret key retrieved and stored');
                return data.secret_key;
            }
        }
        throw new Error('Failed to get secret key');
    } catch (error) {
        console.error('Error getting secret key:', error);
        return null;
    }
}

/**
 * Get ABE public key from server
 */
async function getPublicKey() {
    try {
        const response = await fetch('/api/abe/public-key/', {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            if (data.success) {
                // Store in session storage
                sessionStorage.setItem('abe_public_key', JSON.stringify(data.public_key));
                window.abeSystem.publicKey = data.public_key;
                console.log('Public key retrieved and stored');
                return data.public_key;
            }
        }
        throw new Error('Failed to get public key');
    } catch (error) {
        console.error('Error getting public key:', error);
        return null;
    }
}

/**
 * Get CSRF token from cookie
 */
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

/**
 * Show notification
 */
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    // Add to page
    document.body.appendChild(notification);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}

/**
 * Debug function to show all session storage
 */
function debugSessionStorage() {
    console.log('=== Session Storage Debug ===');
    for (let i = 0; i < sessionStorage.length; i++) {
        const key = sessionStorage.key(i);
        const value = sessionStorage.getItem(key);
        console.log(`${key}: ${value}`);
    }
    console.log('=== End Debug ===');
} 