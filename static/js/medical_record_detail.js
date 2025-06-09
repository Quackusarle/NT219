// Global variables
let pyodideInstance = null;
let isSystemInitialized = false;
let encryptedData = null;
const recordId = window.recordId; // Will be set from template

// DOM elements - will be initialized after DOM loads
let decryptBtn, showEncryptedBtn, retryInitBtn, decryptionStatus, decryptedContainer;

// Initialize DOM elements
function initializeDOMElements() {
    decryptBtn = document.getElementById('decrypt-btn');
    showEncryptedBtn = document.getElementById('show-encrypted-btn');
    retryInitBtn = document.getElementById('retry-init-btn');
    decryptionStatus = document.getElementById('decryption-status');
    decryptedContainer = document.getElementById('decrypted-data-container');
    
    if (!decryptBtn || !showEncryptedBtn || !retryInitBtn || !decryptionStatus || !decryptedContainer) {
        console.error('Some DOM elements not found');
        return false;
    }
    return true;
}

// Utility functions
function logStatus(message, type = 'info') {
    console.log(`[${type.toUpperCase()}] ${message}`);
    
    // Check if decryptionStatus element exists
    if (!decryptionStatus) {
        console.warn('decryptionStatus element not found, cannot update UI');
        return;
    }
    
    const icons = {
        'info': 'fas fa-info-circle',
        'success': 'fas fa-check-circle', 
        'error': 'fas fa-exclamation-triangle',
        'warning': 'fas fa-exclamation-triangle'
    };
    
    const classes = {
        'info': 'alert-info',
        'success': 'alert-success',
        'error': 'alert-danger', 
        'warning': 'alert-warning'
    };
    
    decryptionStatus.className = `alert ${classes[type]}`;
    decryptionStatus.innerHTML = `<i class="${icons[type]}"></i> ${message}`;
}

function getCSRFToken() {
    return document.cookie.match(/csrftoken=([^;]+)/)?.[1];
}

function base64ToArrayBuffer(base64) {
    // Fix base64 padding if needed
    const fixedBase64 = fixBase64Padding(base64);
    const binaryString = atob(fixedBase64);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes.buffer;
}

function arrayBufferToBase64(buffer) {
    return btoa(String.fromCharCode.apply(null, new Uint8Array(buffer)));
}

function fixBase64Padding(base64String) {
    // Add padding if needed
    while (base64String.length % 4) {
        base64String += '=';
    }
    return base64String;
}

// Initialize Pyodide and CP-ABE system
async function initializePyodideAndCharm() {
    try {
        console.log('🚀 Initializing Pyodide...');
        pyodideInstance = await loadPyodide();

        console.log('📦 Installing micropip...');
        await pyodideInstance.loadPackage(['micropip']);

        console.log('🔧 Installing charm-crypto...');
        await pyodideInstance.runPython(`
            import micropip
            await micropip.install('charm-crypto==0.50')
        `);

        console.log('🔒 Setting up CP-ABE system...');
        await pyodideInstance.runPython(`
import base64
import json
from charm.toolbox.pairinggroup import PairingGroup, GT
from charm.schemes.abenc.abenc_waters11 import CPabe_waters11
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes
import hashlib

# Initialize pairing group and CP-ABE scheme
group = PairingGroup('SS512')
cpabe = CPabe_waters11(group)

def base64_to_bytes(b64_string):
    """Convert base64 string to bytes"""
    return base64.b64decode(b64_string)

def deserialize_cpabe_object(b64_string):
    """Deserialize CP-ABE object from base64"""
    try:
        obj_bytes = base64_to_bytes(b64_string)
        return group.deserialize(obj_bytes)
    except Exception as e:
        print(f"Deserialization error: {e}")
        raise

def aes_decrypt(key, ciphertext_b64):
    """Decrypt AES-256-GCM encrypted data"""
    try:
        # Decode base64
        encrypted_data = base64_to_bytes(ciphertext_b64)
        
        # Extract components (IV: 12 bytes, Tag: 16 bytes, Ciphertext: rest)
        iv = encrypted_data[:12]
        tag = encrypted_data[-16:]
        ciphertext = encrypted_data[12:-16]
        
        # Create cipher and decrypt
        cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag))
        decryptor = cipher.decryptor()
        plaintext = decryptor.finalize()
        
        return plaintext.decode('utf-8')
    except Exception as e:
        print(f"AES decryption error: {e}")
        raise

def cp_abe_decrypt_key(secret_key_b64, encrypted_key_b64):
    """Decrypt CP-ABE encrypted AES key"""
    try:
        # Deserialize secret key and encrypted key
        secret_key = deserialize_cpabe_object(secret_key_b64)
        encrypted_key = deserialize_cpabe_object(encrypted_key_b64)
        
        # Perform CP-ABE decryption
        decrypted_gt = cpabe.decrypt(encrypted_key, secret_key)
        
        if decrypted_gt is None:
            raise Exception("CP-ABE decryption failed - insufficient attributes")
        
        # Convert GT element to AES key using SHA256
        gt_bytes = group.serialize(decrypted_gt)
        aes_key = hashlib.sha256(gt_bytes).digest()
        
        return aes_key
    except Exception as e:
        print(f"CP-ABE key decryption error: {e}")
        raise

print("✅ CP-ABE system initialized successfully")
        `);

        isSystemInitialized = true;
        console.log('✅ System initialization completed');
        return true;

    } catch (error) {
        console.error('❌ System initialization failed:', error);
        throw error;
    }
}

// Main decryption function
async function performDecryption() {
    try {
        // Get session storage data
        const secretKeyB64 = sessionStorage.getItem('user_secret_key');
        
        if (!secretKeyB64) {
            throw new Error('Không tìm thấy khóa bí mật. Vui lòng đăng nhập lại.');
        }

        console.log('🔑 Found user secret key in session');

        // Fetch medical record data
        const response = await fetch(`/api/medical-records/${window.recordId}/`);
        if (!response.ok) {
            throw new Error(`Failed to fetch record data: ${response.statusText}`);
        }
        
        const recordData = await response.json();
        console.log('📄 Fetched medical record data');

        // Initialize decryption system
        await pyodideInstance.runPython(`
secret_key_b64 = """${secretKeyB64}"""
print("🔑 Secret key loaded")

# Medical record data
patient_info_key_blob = """${recordData.patient_info_aes_key_blob}"""
medical_record_key_blob = """${recordData.medical_record_aes_key_blob}"""

encrypted_fields = {
    'patient_name': """${recordData.patient_name_blob}""",
    'patient_age': """${recordData.patient_age_blob}""",
    'patient_gender': """${recordData.patient_gender_blob}""",
    'patient_phone': """${recordData.patient_phone_blob}""",
    'chief_complaint': """${recordData.chief_complaint_blob}""",
    'past_medical_history': """${recordData.past_medical_history_blob}""",
    'diagnosis': """${recordData.diagnosis_blob}""",
    'status': """${recordData.status_blob}"""
}
        `);

        // Decrypt AES keys
        console.log('🔓 Decrypting CP-ABE keys...');
        const keyDecryptionResult = await pyodideInstance.runPython(`
decryption_results = {}

try:
    # Decrypt patient info AES key
    print("🔓 Decrypting patient info key...")
    patient_info_aes_key = cp_abe_decrypt_key(secret_key_b64, patient_info_key_blob)
    decryption_results['patient_info_key'] = 'success'
    print("✅ Patient info key decrypted")
    
    # Decrypt medical record AES key  
    print("🔓 Decrypting medical record key...")
    medical_record_aes_key = cp_abe_decrypt_key(secret_key_b64, medical_record_key_blob)
    decryption_results['medical_record_key'] = 'success'
    print("✅ Medical record key decrypted")
    
    decryption_results['keys_status'] = 'success'
    
except Exception as e:
    print(f"❌ Key decryption failed: {e}")
    decryption_results['keys_status'] = 'failed'
    decryption_results['error'] = str(e)

decryption_results
        `);

        if (keyDecryptionResult.get('keys_status') !== 'success') {
            throw new Error(keyDecryptionResult.get('error') || 'Key decryption failed');
        }

        // Decrypt field data
        console.log('🔓 Decrypting field data...');
        const fieldDecryptionResult = await pyodideInstance.runPython(`
decrypted_data = {}

try:
    # Patient info fields
    patient_fields = ['patient_name', 'patient_age', 'patient_gender', 'patient_phone']
    for field in patient_fields:
        if encrypted_fields[field]:
            decrypted_data[field] = aes_decrypt(patient_info_aes_key, encrypted_fields[field])
        else:
            decrypted_data[field] = ""
    
    # Medical record fields  
    medical_fields = ['chief_complaint', 'past_medical_history', 'diagnosis', 'status']
    for field in medical_fields:
        if encrypted_fields[field]:
            decrypted_data[field] = aes_decrypt(medical_record_aes_key, encrypted_fields[field])
        else:
            decrypted_data[field] = ""
    
    decrypted_data['status'] = 'success'
    print("✅ All fields decrypted successfully")
    
except Exception as e:
    print(f"❌ Field decryption failed: {e}")
    decrypted_data['status'] = 'failed'
    decrypted_data['error'] = str(e)

decrypted_data
        `);

        if (fieldDecryptionResult.get('status') !== 'success') {
            throw new Error(fieldDecryptionResult.get('error') || 'Field decryption failed');
        }

        // Update UI with decrypted data
        for (const [fieldName, element] of Object.entries(decryptedFields)) {
            const decryptedValue = fieldDecryptionResult.get(fieldName) || '-';
            element.textContent = decryptedValue;
        }

        console.log('✅ Decryption completed successfully');
        showDecryptedData();

    } catch (error) {
        console.error('❌ Decryption failed:', error);
        showError(error.message);
    }
}

// Auto-start decryption when page loads
async function startAutoDecryption() {
    try {
        await initializePyodideAndCharm();
        await performDecryption();
    } catch (error) {
        showError('Khởi tạo hệ thống thất bại: ' + error.message);
    }
}

// Event Listeners
document.addEventListener('DOMContentLoaded', function() {
    // Auto-start decryption
    startAutoDecryption();
    
    // Retry button
    if (retryInitBtn) {
        retryInitBtn.addEventListener('click', function() {
            retryInitBtn.disabled = true;
            retryInitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Đang thử lại...';
            startAutoDecryption();
        });
    }
    
    // Show encrypted data button
    if (showEncryptedBtn) {
        showEncryptedBtn.addEventListener('click', function() {
            showEncryptedData();
        });
    }
});

// Error handling for unhandled promise rejections
window.addEventListener('unhandledrejection', function(event) {
    console.error('Unhandled promise rejection:', event.reason);
    showError('Đã xảy ra lỗi không mong muốn: ' + event.reason);
});

// Display decrypted data
function displayDecryptedData(fields) {
    const elements = {
        'decrypted-patient-name': fields.patient_name || '-',
        'decrypted-patient-age': fields.patient_age || '-',
        'decrypted-patient-gender': fields.patient_gender || '-',
        'decrypted-patient-phone': fields.patient_phone || '-',
        'decrypted-chief-complaint': fields.chief_complaint || '-',
        'decrypted-past-medical-history': fields.past_medical_history || '-',
        'decrypted-diagnosis': fields.diagnosis || '-',
        'decrypted-status': fields.status || '-'
    };
    
    // Update each element if it exists
    for (const [id, value] of Object.entries(elements)) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
    }
    
    if (decryptedContainer) {
        decryptedContainer.style.display = 'block';
    }
}

// Toggle encrypted data view
function toggleEncryptedView() {
    const encryptedSection = document.getElementById('encrypted-data-section');
    if (encryptedSection.style.display === 'none') {
        encryptedSection.style.display = 'block';
        showEncryptedBtn.innerHTML = '<i class="fas fa-eye-slash"></i> Ẩn dữ liệu đã mã hóa';
    } else {
        encryptedSection.style.display = 'none';
        showEncryptedBtn.innerHTML = '<i class="fas fa-eye"></i> Hiển thị dữ liệu đã mã hóa';
    }
}

// Setup event listeners
function setupEventListeners() {
    decryptBtn.addEventListener('click', performDecryption);
    showEncryptedBtn.addEventListener('click', toggleEncryptedView);
    retryInitBtn.addEventListener('click', async () => {
        retryInitBtn.disabled = true;
        retryInitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Đang thử lại...';
        await initializePyodideAndCharm();
        retryInitBtn.disabled = false;
        retryInitBtn.innerHTML = '<i class="fas fa-redo"></i> Thử lại khởi tạo';
    });
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    console.log('Medical record detail page loaded');
    
    // Initialize DOM elements first
    if (!initializeDOMElements()) {
        console.error('Failed to initialize DOM elements');
        return;
    }
    
    // Setup event listeners
    setupEventListeners();
    
    // Wait a bit for Pyodide script to load, then initialize
    setTimeout(async () => {
        try {
            await initializePyodideAndCharm();
        } catch (error) {
            console.error('Failed to initialize decryption system:', error);
            logStatus('Lỗi khởi tạo hệ thống. Vui lòng thử lại.', 'error');
        }
    }, 2000); // Increased timeout to 2 seconds
}); 