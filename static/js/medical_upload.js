// --- Global State ---
let pyodideInstance = null;
let isSystemReady = false;
let accessPolicies = [];
let selectedPatientPolicy = null;
let selectedMedicalPolicy = null;

// --- DOM Elements ---
const dom = {
    systemStatus: document.getElementById('system-status'),
    uploadBtn: document.getElementById('upload-btn'),
    logArea: document.getElementById('log-area'),
    patientPolicies: document.getElementById('patient-policies-container'),
    medicalPolicies: document.getElementById('medical-policies-container'),
    formInputs: document.querySelectorAll('input, select, textarea'),
};

// --- Logging Utility ---
function logToPage(message, type = "info") {
    if (!dom.logArea) return;
    const timestamp = new Date().toLocaleTimeString();
    const entry = document.createElement('div');
    entry.className = `log-entry log-${type}`;
    entry.innerHTML = `<span class="timestamp">[${timestamp}]</span> <span class="message">${message}</span>`;
    dom.logArea.appendChild(entry);
    dom.logArea.scrollTop = dom.logArea.scrollHeight;

    // Also log to console for better debugging
    if (type === 'error') {
        console.error(message);
    } else {
        console.log(message);
    }
}

// --- UI Updaters ---
function updateSystemStatus(message, type = 'pending') {
    const statusClasses = { 'pending': 'status-pending', 'success': 'status-success', 'error': 'status-error' };
    const icons = { 'pending': 'fas fa-spinner fa-spin', 'success': 'fas fa-check-circle', 'error': 'fas fa-exclamation-triangle' };
    dom.systemStatus.className = `encryption-status ${statusClasses[type]}`;
    dom.systemStatus.innerHTML = `<i class="${icons[type]}"></i> ${message}`;
}

function setFormDisabled(isDisabled) {
    dom.uploadBtn.disabled = isDisabled;
    dom.formInputs.forEach(input => input.disabled = isDisabled);
}

// --- Web Crypto API Helpers ---
async function generateAesKey() {
    return crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, true, ["encrypt", "decrypt"]);
}

async function aesEncrypt(data, key) {
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const encodedData = new TextEncoder().encode(JSON.stringify(data));
    const encryptedBuffer = await crypto.subtle.encrypt({ name: "AES-GCM", iv: iv }, key, encodedData);
    return {
        iv: Array.from(iv), // IV is needed for decryption
        ciphertext: arrayBufferToBase64(encryptedBuffer)
    };
}

// Encrypt individual field with AES
async function aesEncryptField(value, key, iv) {
    const encodedData = new TextEncoder().encode(value);
    const encryptedBuffer = await crypto.subtle.encrypt({ name: "AES-GCM", iv: iv }, key, encodedData);
    return arrayBufferToBase64(encryptedBuffer);
}

function arrayBufferToBase64(buffer) {
    return btoa(String.fromCharCode.apply(null, new Uint8Array(buffer)));
}

function base64ToArrayBuffer(base64) {
    const binaryString = atob(base64);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes.buffer;
}

function arrayBufferToHexString(buffer) {
    return Array.from(new Uint8Array(buffer)).map(b => b.toString(16).padStart(2, '0')).join('');
}

// --- CSRF Token Helper ---
function getCSRFToken() {
    return document.cookie.match(/csrftoken=([^;]+)/)?.[1];
}

// --- Core Initialization ---
async function initializeSystem() {
    logToPage("Initializing medical record upload system...");
    try {
        await initializePyodideAndCharm();
        await loadAccessPolicies();
        isSystemReady = true;
        logToPage("System initialization complete!", "success");
        checkFormCompletion();
    } catch (error) {
        const errorMessage = error.message || error.toString();
        logToPage(`Fatal initialization error: ${errorMessage}`, "error");
        updateSystemStatus("Lỗi khởi tạo hệ thống", "error");
    }
}

async function initializePyodideAndCharm() {
    logToPage("Loading Pyodide...");
    updateSystemStatus("Đang tải Pyodide...");
    pyodideInstance = await loadPyodide({
        stdout: (text) => logToPage(`[Pyodide] ${text}`),
        stderr: (text) => logToPage(`[Pyodide ERROR] ${text}`, "error"),
    });

    logToPage("Loading micropip...");
    await pyodideInstance.loadPackage("micropip");
    const micropip = pyodideInstance.pyimport("micropip");
    
    const charmWheelURL = "http://localhost:8080/charm_crypto-0.50-cp312-cp312-pyodide_2024_0_wasm32.whl";
    logToPage(`Installing Charm-Crypto from local wheel...`);
    await micropip.install(charmWheelURL);
    logToPage("Charm-Crypto installed successfully!");

    logToPage('Loading public key from session storage...');
    updateSystemStatus("Đang tải public key từ session storage...");
    
    // Get public key from session storage
    const publicKeyDataStr = sessionStorage.getItem('abe_public_key');
    if (!publicKeyDataStr) {
        throw new Error('Public key not found in session storage. Please ensure you have initialized the system.');
    }
    
    const publicKeyData = JSON.parse(publicKeyDataStr);
    logToPage('Public key loaded from session storage successfully');
    logToPage(`Session storage key structure: ${JSON.stringify(Object.keys(publicKeyData))}`);

    logToPage('Setting up Waters11 CP-ABE system with public key from session storage...');
    await pyodideInstance.runPythonAsync(`
from charm.toolbox.pairinggroup import PairingGroup
from charm.schemes.abenc.waters11 import Waters11
import base64

# Initialize ABE system
group = PairingGroup('SS512')
waters_abe = Waters11(group, uni_size=11)

# Verify the uni_size setting
print(f"--> Waters11 initialized with uni_size: {waters_abe.uni_size}")

# Store objects for encryption
globals()['_waters11_abe_scheme'] = waters_abe
globals()['_waters11_group'] = group

print("--> Waters11 system ready for encryption.")
    `);

    const testResult = await pyodideInstance.runPythonAsync(`
result = "SUCCESS"
try:
    # Check for the encryption objects
    _waters11_abe_scheme
    _waters11_group
except NameError as e:
    result = f"FAILED: {str(e)}"
except Exception as e:
    result = f"ERROR: {str(e)}"
result
    `);

    if (testResult !== 'SUCCESS') {
        throw new Error(`Waters11 initialization test failed: ${testResult}`);
    }
    
    // Store public key data for use in encryption
    window.serverPublicKey = publicKeyData;
    updateSystemStatus("Hệ thống mã hóa sẵn sàng", "success");
    logToPage("Waters11 CP-ABE system ready for encryption!");
}

// --- Policy Handling ---
async function loadAccessPolicies() {
    logToPage("Loading access policies from server...");
    const response = await fetch('/api/access-policies/', { headers: { 'X-CSRFToken': getCSRFToken() } });
    if (!response.ok) throw new Error(`Failed to fetch policies: ${response.statusText}`);
    const result = await response.json();
    if (!result.success) throw new Error(`API Error: ${result.message}`);
    accessPolicies = result.data;
    logToPage(`Loaded ${accessPolicies.length} access policies.`);
    renderPolicyOptions();
}

function renderPolicyOptions() {
    const render = (container) => {
        container.innerHTML = accessPolicies.map(policy => `
            <div class="policy-card" data-policy-id="${policy.id}">
                <div class="form-check">
                    <input class="form-check-input" type="checkbox" value="${policy.id}" id="policy_${policy.id}_${container.id}">
                    <label class="form-check-label" for="policy_${policy.id}_${container.id}">
                <h6>${policy.name}</h6>
                <p class="mb-1"><code>${policy.policy_template}</code></p>
                <small class="text-muted">${policy.description}</small>
                    </label>
                </div>
            </div>
        `).join('');
    };
    render(dom.patientPolicies);
    render(dom.medicalPolicies);
    logToPage("Policy options rendered with multi-select capability.");

    dom.patientPolicies.addEventListener('change', (e) => handlePolicySelection(e, 'patient'));
    dom.medicalPolicies.addEventListener('change', (e) => handlePolicySelection(e, 'medical'));
}

function handlePolicySelection(event, type) {
    if (event.target.type !== 'checkbox') return;

    const container = type === 'patient' ? dom.patientPolicies : dom.medicalPolicies;
    const checkedBoxes = container.querySelectorAll('input[type="checkbox"]:checked');
    
    // Get selected policies
    const selectedPolicies = Array.from(checkedBoxes).map(checkbox => {
        const policyId = parseInt(checkbox.value);
        return accessPolicies.find(p => p.id === policyId);
    });
    
    if (type === 'patient') {
        selectedPatientPolicy = selectedPolicies;
    } else {
        selectedMedicalPolicy = selectedPolicies;
    }
    
    // Update visual feedback
    container.querySelectorAll('.policy-card').forEach(card => {
        const checkbox = card.querySelector('input[type="checkbox"]');
        if (checkbox && checkbox.checked) {
            card.classList.add('selected');
        } else {
            card.classList.remove('selected');
        }
    });
    
    const policyNames = selectedPolicies.map(p => p.name).join(', ');
    logToPage(`Selected ${type} policies: [${policyNames}]`);
    checkFormCompletion();
}

// --- Form Validation & Control ---
function checkFormCompletion() {
    const requiredFields = ['patient_id', 'patient_name', 'patient_age', 'patient_gender', 'chief_complaint', 'diagnosis'];
    const allFieldsFilled = requiredFields.every(id => document.getElementById(id).value.trim());
    const policiesSelected = selectedPatientPolicy && selectedPatientPolicy.length > 0 && 
                           selectedMedicalPolicy && selectedMedicalPolicy.length > 0;
    dom.uploadBtn.disabled = !(isSystemReady && allFieldsFilled && policiesSelected);
}

// --- Encryption Core ---
async function encryptAESKeyWithCPABE(aesKeyHex, policy) {
    logToPage(`Encrypting AES key with CP-ABE for policy: ${policy}`);
    
    // Get public key data from session storage
    // Check if the public key data has the expected structure
    if (!window.serverPublicKey) {
        throw new Error('Public key data not found in window.serverPublicKey');
    }
    
    // Handle different possible structures of public key data
    let pkData;
    if (window.serverPublicKey.public_key) {
        pkData = window.serverPublicKey.public_key;
    } else if (window.serverPublicKey.data && window.serverPublicKey.data.public_key) {
        pkData = window.serverPublicKey.data.public_key;
    } else {
        // Assume the entire object is the public key data
        pkData = window.serverPublicKey;
    }
    
    logToPage(`Public key structure: ${JSON.stringify(Object.keys(pkData))}`);
    
    if (!pkData || typeof pkData !== 'object') {
        throw new Error('Invalid public key data structure');
    }
    
    // Get attribute mapping from session storage
    const attributeMappingStr = sessionStorage.getItem('abe_attribute_mapping');
    if (!attributeMappingStr) {
        throw new Error('Attribute mapping not found in session storage');
    }
    
    const attributeMapping = JSON.parse(attributeMappingStr);
    const nameToInt = attributeMapping.name_to_int;
    
    // Convert policy attributes to integers using the mapping
    let convertedPolicy = policy;
    for (const [attrName, attrInt] of Object.entries(nameToInt)) {
        // Use word boundaries to avoid partial matches
        const regex = new RegExp(`\\b${attrName}\\b`, 'gi');
        convertedPolicy = convertedPolicy.replace(regex, attrInt.toString());
    }
    
    logToPage(`Original policy: ${policy}`);
    logToPage(`Converted policy: ${convertedPolicy}`);
    
    let result = await pyodideInstance.runPythonAsync(`
from charm.toolbox.pairinggroup import GT
import base64
import json

final_result = None
try:
    # Use the stored objects
    waters_abe = _waters11_abe_scheme
    group = _waters11_group
    
    # Reconstruct public key from session storage data
    pk_data = ${JSON.stringify(pkData)}
    pk = {}
    
    # Deserialize each component
    from charm.toolbox.pairinggroup import deserialize
    for key, value in pk_data.items():
        if isinstance(value, str):
            # Single element - base64 encoded string
            pk[key] = group.deserialize(base64.b64decode(value))
        elif isinstance(value, int):
            # Single element - direct integer value
            pk[key] = value
        elif isinstance(value, list):
            # List of elements
            pk[key] = []
            for item in value:
                if isinstance(item, str):
                    # Base64 encoded item
                    pk[key].append(group.deserialize(base64.b64decode(item)))
                elif isinstance(item, int):
                    # Direct integer item
                    pk[key].append(item)
                else:
                    # Unknown type, try to deserialize as is
                    pk[key].append(item)
        else:
            # Unknown type, use as is
            pk[key] = value

    # Main encryption logic
    from charm.toolbox.pairinggroup import G1, G2, GT, ZR
    
    # Convert AES key hex to bytes
    aes_key_bytes = bytes.fromhex("${aesKeyHex}")
    
    # Create a consistent seed from the AES key using SHA256
    import hashlib
    key_hash = hashlib.sha256(aes_key_bytes).digest()
    
    # Use first 4 bytes (32 bits) as seed for CP-ABE
    seed = int.from_bytes(key_hash[:4], byteorder='big')
    
    # Create GT message from the seed
    base_gt = group.pair_prod(pk['g1'], pk['g1'])
    gt_message = base_gt ** group.init(ZR, seed)
    
    # ĐÂY LÀ KHÓA SẼ DÙNG CHO WEB CRYPTO
    # Calculate the key that will be used for Web Crypto (same as decryption will derive)
    web_crypto_key_bytes_for_data = hashlib.sha256(group.serialize(gt_message)).digest()
    web_crypto_key_base64_for_data = base64.b64encode(web_crypto_key_bytes_for_data).decode('utf-8')
    
    # Use the converted policy with integer attributes
    policy_str = "${convertedPolicy}"
    
    print(f"Using converted policy: {policy_str}")
    print(f"Original AES key: ${aesKeyHex}")
    print(f"Key hash (4 bytes): {key_hash[:4].hex()}")
    print(f"Seed: {seed}")
    print(f"GT message serialized (first 32 bytes): {group.serialize(gt_message)[:32].hex()}")
    print(f"Derived Web Crypto key: {web_crypto_key_base64_for_data[:50]}...")
    
    # Encrypt the GT message with CP-ABE
    ciphertext = waters_abe.encrypt(pk, gt_message, policy_str)
    print(f"CP-ABE encryption successful")
    
    # Store verification info  
    ciphertext['_key_verification'] = {
        'method': 'sha256_hash',
        'original_key_hash': key_hash.hex()
    }
    
    # Serialize the ciphertext to base64 strings for JSON transport
    serialized = {}
    for key, value in ciphertext.items():
        print(f"Serializing CT key: {key}, type: {type(value)}")
        if str(type(value)) == "<class 'pairing.Element'>" or hasattr(value, 'serialize'):
            # Group element - serialize to bytes then base64
            if str(type(value)) == "<class 'pairing.Element'>":
                element_bytes = group.serialize(value)
            else:
                element_bytes = value.serialize()
            element_b64 = base64.b64encode(element_bytes).decode('utf-8')
            serialized[key] = element_b64
            print(f"  Serialized element to {len(element_b64)} base64 chars")
        elif isinstance(value, (dict, list)):
            # Handle nested structures
            if isinstance(value, dict):
                serialized[key] = {}
                for k, v in value.items():
                    print(f"  Processing dict key: {k}, type: {type(v)}")
                    if str(type(v)) == "<class 'pairing.Element'>" or hasattr(v, 'serialize'):
                        if str(type(v)) == "<class 'pairing.Element'>":
                            element_bytes = group.serialize(v)
                        else:
                            element_bytes = v.serialize()
                        element_b64 = base64.b64encode(element_bytes).decode('utf-8')
                        serialized[key][k] = element_b64
                        print(f"    Serialized to {len(element_b64)} base64 chars")
                    else:
                        serialized[key][k] = str(v)
                        print(f"    Converted to string: {str(v)[:50]}...")
            else:  # list
                serialized[key] = []
                for i, item in enumerate(value):
                    print(f"  Processing list item {i}, type: {type(item)}")
                    if str(type(item)) == "<class 'pairing.Element'>" or hasattr(item, 'serialize'):
                        if str(type(item)) == "<class 'pairing.Element'>":
                            element_bytes = group.serialize(item)
                        else:
                            element_bytes = item.serialize()
                        element_b64 = base64.b64encode(element_bytes).decode('utf-8')
                        serialized[key].append(element_b64)
                        print(f"    Serialized to {len(element_b64)} base64 chars")
                    else:
                        serialized[key].append(str(item))
                        print(f"    Converted to string: {str(item)[:50]}...")
        else:
            # Simple value - convert to string
            serialized[key] = str(value)
            print(f"  Direct string conversion: {str(value)[:50]}...")

    print(f"Final serialized structure keys: {list(serialized.keys())}")
    
    # Return both ABE ciphertext and derived key
    result = {
        "abe_ciphertext": serialized,
        "web_crypto_aes_key_base64": web_crypto_key_base64_for_data
    }
    print(f"Success! Returning result with keys: {list(result.keys())}")
    
except Exception as e:
    print(f"CP-ABE encryption failed: {e}")
    import traceback
    print(f"Traceback: {traceback.format_exc()}")
    result = None

# Serialize to JSON string for JavaScript
json.dumps(result)
    `);
    
    // Debug: log what we received from Python
    logToPage(`JavaScript received result: ${typeof result}`);
    logToPage(`Result is null/undefined: ${result == null}`);
    
    // Parse JSON string from Python
    let parsedResult;
    try {
        parsedResult = JSON.parse(result);
        logToPage(`Parsed result keys: ${Object.keys(parsedResult)}`);
        logToPage(`Has abe_ciphertext: ${!!parsedResult.abe_ciphertext}`);
        logToPage(`Has web_crypto_aes_key_base64: ${!!parsedResult.web_crypto_aes_key_base64}`);
    } catch (e) {
        logToPage(`Failed to parse result as JSON: ${e.message}`, "error");
        throw new Error("Invalid result format from Python");
    }
    
    result = parsedResult;
    
    if (!result || !result.abe_ciphertext || !result.web_crypto_aes_key_base64) {
        throw new Error("CP-ABE encryption failed in Python. Check logs for details.");
    }
    
    // Return both ABE ciphertext and derived key
    return {
        abe_ciphertext: result.abe_ciphertext,
        web_crypto_aes_key_base64: result.web_crypto_aes_key_base64
    };
}

// --- Main Upload Process ---
async function handleUpload() {
    logToPage("--- Starting medical record upload process ---", "success");
    setFormDisabled(true);

    try {
        // 1. Generate random AES keys for patient info and medical records
        logToPage("Generating AES keys for patient info and medical records...");
        const patientAesKey = await generateAesKey();
        const medicalAesKey = await generateAesKey();

        // 2. Generate IVs for each data type
        const patientInfoIV = crypto.getRandomValues(new Uint8Array(12));
        const medicalRecordIV = crypto.getRandomValues(new Uint8Array(12));

        // 3. Export AES keys for CP-ABE encryption
        logToPage("Exporting AES keys for CP-ABE encryption...");
        const patientKeyHex = arrayBufferToHexString(await crypto.subtle.exportKey("raw", patientAesKey));
        const medicalKeyHex = arrayBufferToHexString(await crypto.subtle.exportKey("raw", medicalAesKey));
        
        // 4. Combine multiple policies with OR
        const patientPolicyString = selectedPatientPolicy.length === 1 
            ? selectedPatientPolicy[0].policy_template
            : `(${selectedPatientPolicy.map(p => `(${p.policy_template})`).join(' OR ')})`;
            
        const medicalPolicyString = selectedMedicalPolicy.length === 1
            ? selectedMedicalPolicy[0].policy_template  
            : `(${selectedMedicalPolicy.map(p => `(${p.policy_template})`).join(' OR ')})`;
        
        logToPage(`Combined patient policy: ${patientPolicyString}`);
        logToPage(`Combined medical policy: ${medicalPolicyString}`);
        
        // 5. Encrypt AES keys with CP-ABE and get derived keys for data encryption
        logToPage("Encrypting AES keys with CP-ABE and deriving keys for data encryption...");
        const patientAbeResult = await encryptAESKeyWithCPABE(patientKeyHex, patientPolicyString);
        const medicalAbeResult = await encryptAESKeyWithCPABE(medicalKeyHex, medicalPolicyString);

        const encryptedPatientKeyABE = patientAbeResult.abe_ciphertext;
        const webCryptoPatientAesKeyBase64 = patientAbeResult.web_crypto_aes_key_base64;

        const encryptedMedicalKeyABE = medicalAbeResult.abe_ciphertext;
        const webCryptoMedicalAesKeyBase64 = medicalAbeResult.web_crypto_aes_key_base64;

        logToPage("CP-ABE encryption of AES keys complete.");

        // 6. Import derived keys for Web Crypto data encryption
        logToPage("Importing derived keys for Web Crypto data encryption...");
        const webCryptoPatientAesKeyForData = await crypto.subtle.importKey(
            "raw",
            base64ToArrayBuffer(webCryptoPatientAesKeyBase64),
            { name: "AES-GCM" },
            false, // not exportable
            ["encrypt"]
        );
        const webCryptoMedicalAesKeyForData = await crypto.subtle.importKey(
            "raw",
            base64ToArrayBuffer(webCryptoMedicalAesKeyBase64),
            { name: "AES-GCM" },
            false,
            ["encrypt"]
        );

        // 7. Encrypt patient info fields with derived patient AES key
        logToPage("Encrypting patient info fields with derived AES-GCM key...");
        const patientNameBlob = await aesEncryptField(dom.formInputs[1].value.trim(), webCryptoPatientAesKeyForData, patientInfoIV);
        const patientAgeBlob = await aesEncryptField(dom.formInputs[2].value.trim(), webCryptoPatientAesKeyForData, patientInfoIV);
        const patientGenderBlob = await aesEncryptField(dom.formInputs[3].value.trim(), webCryptoPatientAesKeyForData, patientInfoIV);
        const patientPhoneBlob = await aesEncryptField(dom.formInputs[4].value.trim(), webCryptoPatientAesKeyForData, patientInfoIV);
        
        // 8. Encrypt medical record fields with derived medical AES key
        logToPage("Encrypting medical record fields with derived AES-GCM key...");
        const chiefComplaintBlob = await aesEncryptField(dom.formInputs[5].value.trim(), webCryptoMedicalAesKeyForData, medicalRecordIV);
        const pastMedicalHistoryBlob = await aesEncryptField(dom.formInputs[6].value.trim(), webCryptoMedicalAesKeyForData, medicalRecordIV);
        const diagnosisBlob = await aesEncryptField(dom.formInputs[7].value.trim(), webCryptoMedicalAesKeyForData, medicalRecordIV);
        const statusBlob = await aesEncryptField(dom.formInputs[8].value.trim(), webCryptoMedicalAesKeyForData, medicalRecordIV);
        logToPage("AES encryption of individual fields complete.");

        // 9. Prepare final payload for the server
        const payload = {
            patient_id: dom.formInputs[0].value.trim(), // Unencrypted for easy search/management
            
            // Individual patient info fields (encrypted with derived patient AES key)
            patient_name_blob: patientNameBlob,
            patient_age_blob: patientAgeBlob,
            patient_gender_blob: patientGenderBlob,
            patient_phone_blob: patientPhoneBlob,
            
            // Patient info AES key and IV (key encrypted with CP-ABE)
            patient_info_aes_key_blob: btoa(JSON.stringify(encryptedPatientKeyABE)),
            patient_info_aes_iv_blob: btoa(String.fromCharCode.apply(null, patientInfoIV)),
            
            // Individual medical record fields (encrypted with derived medical AES key)
            chief_complaint_blob: chiefComplaintBlob,
            past_medical_history_blob: pastMedicalHistoryBlob,
            diagnosis_blob: diagnosisBlob,
            status_blob: statusBlob,
            
            // Medical record AES key and IV (key encrypted with CP-ABE)
            medical_record_aes_key_blob: btoa(JSON.stringify(encryptedMedicalKeyABE)),
            medical_record_aes_iv_blob: btoa(String.fromCharCode.apply(null, medicalRecordIV)),
        };
        
        // Log the payload structure for debugging
        logToPage(`Payload structure: ${JSON.stringify(Object.keys(payload))}`);
        logToPage(`Patient ID: ${payload.patient_id}`);
        
        // 10. Send data to the server
        logToPage("Uploading encrypted data to the server...");
        const response = await fetch('/api/upload-medical-record/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRFToken() },
            body: JSON.stringify(payload)
        });

        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.message || `Server returned status ${response.status}`);
        }

        logToPage(`Upload successful! Record ID: ${result.data.id}`, "success");
        alert('Medical record uploaded successfully!');
        if (confirm('Do you want to create another record?')) {
            window.location.reload();
        }

    } catch (error) {
        const errorMessage = error.message || error.toString();
        logToPage(`Upload failed: ${errorMessage}`, "error");
        alert(`An error occurred during upload. Please check the logs for details.`);
    } finally {
        setFormDisabled(false);
        checkFormCompletion();
    }
}

// --- Event Listeners ---
dom.uploadBtn.addEventListener('click', handleUpload);
dom.formInputs.forEach(input => input.addEventListener('input', checkFormCompletion));

// --- Initializer ---
document.addEventListener('DOMContentLoaded', initializeSystem); 