/**
 * Base JavaScript - Common functions for all pages
 */

// Global variables
window.abeSystem = {
    publicKey: null,
    secretKey: null,
    attributeMapping: null,
    schemeInfo: null
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
        // Auto-load public key and mappings
        loadPublicKeyAndMappings();
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
        
        // Load attribute mapping from session storage
        const attributeMappingData = sessionStorage.getItem('abe_attribute_mapping');
        if (attributeMappingData) {
            window.abeSystem.attributeMapping = JSON.parse(attributeMappingData);
            console.log('ABE attribute mapping loaded from session');
        }
        
        // Load scheme info from session storage
        const schemeInfoData = sessionStorage.getItem('abe_scheme_info');
        if (schemeInfoData) {
            window.abeSystem.schemeInfo = JSON.parse(schemeInfoData);
            console.log('ABE scheme info loaded from session:', window.abeSystem.schemeInfo);
        }
        
    } catch (error) {
        console.error('Error loading ABE keys:', error);
    }
}

/**
 * Load public key and mappings automatically
 */
async function loadPublicKeyAndMappings() {
    try {
        // Check if already loaded
        if (window.abeSystem.publicKey && window.abeSystem.attributeMapping) {
            return;
        }
        
        const data = await getPublicKey();
        if (data) {
            console.log('Public key and mappings loaded automatically');
        }
    } catch (error) {
        console.error('Error auto-loading public key:', error);
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
            const result = await response.json();
            if (result.success) {
                // Store in session storage - consistent data access
                sessionStorage.setItem('abe_secret_key', JSON.stringify(result.data));
                window.abeSystem.secretKey = result.data;
                console.log('Secret key retrieved and stored');
                return result.data;
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
            const result = await response.json();
            if (result.success) {
                // Store in session storage - Waters11 format
                sessionStorage.setItem('abe_public_key', JSON.stringify(result.data.public_key));
                sessionStorage.setItem('abe_attribute_mapping', JSON.stringify(result.data.attribute_mapping));
                sessionStorage.setItem('abe_scheme_info', JSON.stringify(result.data.scheme_info));
                
                window.abeSystem.publicKey = result.data.public_key;
                window.abeSystem.attributeMapping = result.data.attribute_mapping;
                window.abeSystem.schemeInfo = result.data.scheme_info;
                
                console.log('Waters11 public key and mappings retrieved and stored');
                console.log('Scheme info:', result.data.scheme_info);
                return result.data;
            }
        }
        throw new Error('Failed to get public key');
    } catch (error) {
        console.error('Error getting public key:', error);
        return null;
    }
}

/**
 * Get session secret key from server
 */
async function getSessionSecretKey() {
    try {
        const response = await fetch('/api/abe/session-key/', {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                // Store in session storage
                sessionStorage.setItem('abe_secret_key', JSON.stringify(result.data));
                window.abeSystem.secretKey = result.data;
                console.log('Session secret key retrieved:', result.source);
                return result.data;
            }
        }
        throw new Error('Failed to get session secret key');
    } catch (error) {
        console.error('Error getting session secret key:', error);
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
 * Debug function to show ABE system status
 */
function debugABESystem() {
    console.log('=== ABE System Debug ===');
    console.log('Public Key:', !!window.abeSystem.publicKey);
    console.log('Secret Key:', !!window.abeSystem.secretKey);
    console.log('Attribute Mapping:', !!window.abeSystem.attributeMapping);
    console.log('Scheme Info:', window.abeSystem.schemeInfo);
    
    if (window.abeSystem.secretKey) {
        console.log('User Attributes:', window.abeSystem.secretKey.attributes);
    }
    
    console.log('=== Session Storage ===');
    for (let i = 0; i < sessionStorage.length; i++) {
        const key = sessionStorage.key(i);
        if (key.startsWith('abe_')) {
            console.log(`${key}: ${!!sessionStorage.getItem(key)}`);
        }
    }
    console.log('=== End Debug ===');
} 

// Make functions globally available
window.getSecretKey = getSecretKey;
window.getPublicKey = getPublicKey;
window.getSessionSecretKey = getSessionSecretKey;
window.debugABESystem = debugABESystem; 