// Global variables
let pyodideInstance = null;
let isSystemReady = false;
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
async function initializeDecryptionSystem() {
    try {
        logStatus("Đang khởi tạo hệ thống giải mã...", "info");
        
        // Check if Pyodide is available with retry logic
        let retryCount = 0;
        const maxRetries = 5;
        
        while (typeof loadPyodide === 'undefined' && retryCount < maxRetries) {
            console.log(`Waiting for Pyodide to load... (attempt ${retryCount + 1}/${maxRetries})`);
            await new Promise(resolve => setTimeout(resolve, 1000));
            retryCount++;
        }
        
        if (typeof loadPyodide === 'undefined') {
            throw new Error('Pyodide chưa được tải sau nhiều lần thử. Vui lòng kiểm tra kết nối internet và làm mới trang.');
        }
        
        // Load Pyodide
        pyodideInstance = await loadPyodide({
            stdout: (text) => console.log(`[Pyodide] ${text}`),
            stderr: (text) => console.error(`[Pyodide ERROR] ${text}`),
        });

        // Load micropip and charm-crypto
        await pyodideInstance.loadPackage("micropip");
        const micropip = pyodideInstance.pyimport("micropip");
        
        const charmWheelURL = "http://localhost:8080/charm_crypto-0.50-cp312-cp312-pyodide_2024_0_wasm32.whl";
        await micropip.install(charmWheelURL);

        // Initialize Waters11 system
        await pyodideInstance.runPythonAsync(`
from charm.toolbox.pairinggroup import PairingGroup
from charm.schemes.abenc.waters11 import Waters11
import base64

# Initialize ABE system
group = PairingGroup('SS512')
waters_abe = Waters11(group, uni_size=11)

# Store objects for decryption
globals()['_waters11_abe_scheme'] = waters_abe
globals()['_waters11_group'] = group

print("--> Waters11 system ready for decryption.")
        `);

        isSystemReady = true;
        logStatus("Hệ thống giải mã đã sẵn sàng!", "success");
        if (decryptBtn) decryptBtn.disabled = false;
        if (retryInitBtn) retryInitBtn.style.display = 'none';
        
    } catch (error) {
        logStatus(`Lỗi khởi tạo hệ thống: ${error.message}`, "error");
        console.error("Initialization error:", error);
        
        // Provide alternative message and show retry button
        if (decryptionStatus) {
            decryptionStatus.innerHTML += `
                <br><small class="text-muted">
                    <strong>Gợi ý:</strong> Hãy thử làm mới trang hoặc kiểm tra kết nối internet. 
                    Chức năng giải mã cần tải thư viện Pyodide từ CDN.
                </small>
            `;
        }
        if (retryInitBtn) retryInitBtn.style.display = 'inline-block';
    }
}

// Fetch encrypted medical record data
async function fetchEncryptedData() {
    try {
        logStatus("Đang tải dữ liệu đã mã hóa...", "info");
        
        const response = await fetch(`/api/medical-record/${recordId}/`, {
            headers: { 'X-CSRFToken': getCSRFToken() }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        if (!result.success) {
            throw new Error(result.message);
        }
        
        encryptedData = result.data;
        logStatus("Dữ liệu đã mã hóa đã được tải!", "success");
        return encryptedData;
        
    } catch (error) {
        logStatus(`Lỗi tải dữ liệu: ${error.message}`, "error");
        throw error;
    }
}

// Decrypt CP-ABE encrypted AES key
async function decryptCPABEKey(encryptedKeyBase64) {
    try {
        console.log('=== DECRYPT CP-ABE KEY DEBUG START ===');
        console.log('Input encryptedKeyBase64 type:', typeof encryptedKeyBase64);
        console.log('Input encryptedKeyBase64 length:', encryptedKeyBase64 ? encryptedKeyBase64.length : 'null');
        console.log('Input encryptedKeyBase64 first 50 chars:', encryptedKeyBase64 ? encryptedKeyBase64.substring(0, 50) : 'null');
        
        // Get secret key from session storage
        const secretKeyStr = sessionStorage.getItem('abe_secret_key');
        console.log('Secret key from session storage:', secretKeyStr ? 'EXISTS' : 'NULL');
        if (!secretKeyStr) {
            throw new Error('Secret key không tồn tại trong session storage');
        }
        
        const secretKeyData = JSON.parse(secretKeyStr);
        console.log('Secret key data keys:', Object.keys(secretKeyData));
        console.log('Secret key attributes:', secretKeyData.attributes);
        console.log('Secret key attribute_integers:', secretKeyData.attribute_integers);
        
        // Get public key from session storage
        const publicKeyStr = sessionStorage.getItem('abe_public_key');
        console.log('Public key from session storage:', publicKeyStr ? 'EXISTS' : 'NULL');
        if (!publicKeyStr) {
            throw new Error('Public key không tồn tại trong session storage');
        }
        
        const publicKeyData = JSON.parse(publicKeyStr);
        console.log('Public key data structure:', Object.keys(publicKeyData));
        
        // Get attribute mapping from session storage
        const attributeMappingStr = sessionStorage.getItem('abe_attribute_mapping');
        console.log('Attribute mapping from session storage:', attributeMappingStr ? 'EXISTS' : 'NULL');
        if (!attributeMappingStr) {
            throw new Error('Attribute mapping không tồn tại trong session storage');
        }
        
        const attributeMapping = JSON.parse(attributeMappingStr);
        const nameToInt = attributeMapping.name_to_int;
        console.log('Name to int mapping:', nameToInt);
        
        console.log('About to call Python decryption...');
        
        // Decrypt in Python
        const result = await pyodideInstance.runPythonAsync(`
import base64
import json
from charm.toolbox.pairinggroup import GT, G1, G2, ZR

result = None
try:
    print("=== PYTHON DECRYPTION DEBUG START ===")
    waters_abe = _waters11_abe_scheme
    group = _waters11_group
    print("Waters11 scheme and group loaded successfully")
    
    # Get attribute mapping for conversion
    name_to_int_mapping = ${JSON.stringify(nameToInt)}
    print(f"Name to int mapping: {name_to_int_mapping}")
    
    # Reconstruct secret key
    sk_data = ${JSON.stringify(secretKeyData)}
    print(f"Secret key data keys: {list(sk_data.keys())}")
    print(f"Secret key attributes: {sk_data.get('attributes', 'NOT FOUND')}")
    print(f"Secret key attribute_integers: {sk_data.get('attribute_integers', 'NOT FOUND')}")
    
    sk = {}
    
    for key, value in sk_data.items():
        print(f"Processing SK key: {key}, type: {type(value)}")
        if key == 'attributes' and isinstance(value, list):
            print(f"Converting attributes: {value}")
            # Convert string attributes to string integers for Waters11 (it expects string attributes)
            attr_list = []
            for attr in value:
                print(f"  Processing attribute: {attr} (type: {type(attr)})")
                if isinstance(attr, str) and attr in name_to_int_mapping:
                    converted = str(name_to_int_mapping[attr])  # Convert to string
                    attr_list.append(converted)
                    print(f"    Converted '{attr}' to string '{converted}'")
                elif isinstance(attr, int):
                    attr_list.append(str(attr))  # Convert to string
                    print(f"    Converted integer {attr} to string '{str(attr)}'")
                elif isinstance(attr, str) and attr.isdigit():
                    attr_list.append(attr)  # Already a string digit
                    print(f"    Kept string digit: '{attr}'")
                else:
                    # If attribute not in mapping, try to convert directly
                    try:
                        converted = str(int(attr))
                        attr_list.append(converted)
                        print(f"    Direct conversion '{attr}' to string '{converted}'")
                    except:
                        print(f"    Warning: Could not convert attribute '{attr}' to integer")
            
            # Store both 'attributes' and 'attr_list' for compatibility
            sk['attributes'] = attr_list
            sk['attr_list'] = attr_list
            print(f"    Final attr_list (strings): {attr_list}")
        elif key == 'secret_key' and isinstance(value, dict):
            print(f"  Processing secret_key dict with {len(value)} components")
            # This is the actual secret key components that need deserialization
            # Don't nest them under 'secret_key', put them directly in sk for Waters11
            for sk_component_key, sk_component_value in value.items():
                print(f"    Processing SK component: {sk_component_key}, type: {type(sk_component_value)}")
                if isinstance(sk_component_value, str):
                    try:
                        sk[sk_component_key] = group.deserialize(base64.b64decode(sk_component_value))
                        print(f"      Successfully deserialized {sk_component_key}")
                    except Exception as e:
                        print(f"      ERROR deserializing {sk_component_key}: {e}")
                        raise e
                elif isinstance(sk_component_value, list):
                    sk[sk_component_key] = []
                    for i, item in enumerate(sk_component_value):
                        if isinstance(item, str):
                            try:
                                sk[sk_component_key].append(group.deserialize(base64.b64decode(item)))
                                print(f"        Successfully deserialized {sk_component_key}[{i}]")
                            except Exception as e:
                                print(f"        ERROR deserializing {sk_component_key}[{i}]: {e}")
                                sk[sk_component_key].append(item)
                        else:
                            sk[sk_component_key].append(item)
                elif isinstance(sk_component_value, dict):
                    # Handle nested dict (like 'K' component)
                    sk[sk_component_key] = {}
                    for k, v in sk_component_value.items():
                        if isinstance(v, str):
                            try:
                                sk[sk_component_key][k] = group.deserialize(base64.b64decode(v))
                                print(f"        Successfully deserialized {sk_component_key}[{k}]")
                            except Exception as e:
                                print(f"        ERROR deserializing {sk_component_key}[{k}]: {e}")
                                sk[sk_component_key][k] = v
                        else:
                            sk[sk_component_key][k] = v
                else:
                    sk[sk_component_key] = sk_component_value
        elif key in ['user_email', 'attribute_integers']:
            print(f"  Skipping metadata field: {key}")
            # These are metadata fields, not cryptographic components
            sk[key] = value
        elif isinstance(value, str):
            print(f"  Deserializing string value for key: {key}")
            try:
                sk[key] = group.deserialize(base64.b64decode(value))
                print(f"    Successfully deserialized {key}")
            except Exception as e:
                print(f"    ERROR deserializing {key}: {e}")
                # If it fails, it might be a plain string
                sk[key] = value
        elif isinstance(value, list):
            print(f"  Processing list for key: {key}")
            sk[key] = [group.deserialize(base64.b64decode(item)) if isinstance(item, str) else item for item in value]
        else:
            print(f"  Direct assignment for key: {key}")
            sk[key] = value
    
    print(f"Final secret key structure: {list(sk.keys())}")
    print(f"Final secret key attributes: {sk.get('attributes', 'NOT FOUND')}")
    
    # Reconstruct public key
    pk_data = ${JSON.stringify(publicKeyData.public_key || publicKeyData.data?.public_key || publicKeyData)}
    print(f"Public key data keys: {list(pk_data.keys())}")
    pk = {}
    
    for key, value in pk_data.items():
        print(f"Processing PK key: {key}, value type: {type(value)}")
        if isinstance(value, str):
            print(f"  Deserializing string value for PK key: {key}")
            pk[key] = group.deserialize(base64.b64decode(value))
        elif isinstance(value, int):
            print(f"  Direct integer assignment for PK key: {key}")
            pk[key] = value
        elif isinstance(value, list):
            print(f"  Processing list for PK key: {key}, length: {len(value)}")
            pk[key] = []
            for i, item in enumerate(value):
                print(f"    Item {i}: type {type(item)}")
                if isinstance(item, str):
                    pk[key].append(group.deserialize(base64.b64decode(item)))
                elif isinstance(item, int):
                    pk[key].append(item)
                else:
                    pk[key].append(item)
        else:
            print(f"  Direct assignment for PK key: {key}")
            pk[key] = value
    
    print(f"Final public key structure: {list(pk.keys())}")
    
    # Reconstruct ciphertext
    ct_str = "${encryptedKeyBase64}"
    print(f"=== CIPHERTEXT RECONSTRUCTION ===")
    print(f"Original ciphertext string length: {len(ct_str)}")
    print(f"Original ciphertext type: {type(ct_str)}")
    print(f"First 100 chars: {ct_str[:100]}")
    print(f"Last 50 chars: {ct_str[-50:]}")
    
    # Check if it's valid base64
    import re
    base64_pattern = re.compile(r'^[A-Za-z0-9+/]*={0,2}$')
    is_valid_base64 = base64_pattern.match(ct_str)
    print(f"Is valid base64 pattern: {is_valid_base64 is not None}")
    
    # Fix base64 padding if needed
    ct_str_fixed = ct_str
    padding_needed = len(ct_str_fixed) % 4
    if padding_needed:
        ct_str_fixed += '=' * (4 - padding_needed)
        print(f"Added {4 - padding_needed} padding characters")
    
    print(f"Fixed ciphertext string length: {len(ct_str_fixed)}")
    print(f"Fixed string ends with: {ct_str_fixed[-10:]}")
    
    # Try to decode base64
    try:
        decoded_bytes = base64.b64decode(ct_str_fixed)
        print(f"Base64 decode successful, got {len(decoded_bytes)} bytes")
        decoded_str = decoded_bytes.decode('utf-8')
        print(f"UTF-8 decode successful, got {len(decoded_str)} characters")
        print(f"Decoded string first 100 chars: {decoded_str[:100]}")
        ct_data = json.loads(decoded_str)
        print(f"JSON parse successful, got {len(ct_data)} keys: {list(ct_data.keys())}")
    except Exception as decode_error:
        print(f"ERROR in base64/JSON decode: {decode_error}")
        print(f"Error type: {type(decode_error)}")
        raise decode_error
    
    ct = {}
    # Define which fields should NOT be deserialized (they are plain strings)
    non_crypto_fields = {'policy', 'attribute_list', '_key_verification'}
    
    for key, value in ct_data.items():
        print(f"Processing CT key: {key}, value type: {type(value)}")
        
        if key in non_crypto_fields:
            print(f"  Processing non-crypto field: {key} = {value}")
            if key == 'policy':
                # Parse policy string into policy object using Waters11 util
                policy_str = str(value).strip()
                print(f"    Parsing policy string: '{policy_str}'")
                try:
                    # Use Waters11's util to parse the policy string
                    policy_obj = waters_abe.util.createPolicy(policy_str)
                    ct[key] = policy_obj
                    print(f"    Successfully parsed policy to object: {type(policy_obj)}")
                except Exception as e:
                    print(f"    ERROR parsing policy: {e}")
                    # Keep as string as fallback
                    ct[key] = policy_str
            elif key == '_key_verification':
                # This is metadata, store as is without any deserialization
                ct[key] = value
                print(f"    Stored verification metadata as-is: {type(value)}")
            else:
                ct[key] = str(value)
        elif isinstance(value, str):
            print(f"  Deserializing string value for CT key: {key}")
            try:
                # Fix base64 padding if needed
                value_fixed = value
                padding_needed = len(value_fixed) % 4
                if padding_needed:
                    value_fixed += '=' * (4 - padding_needed)
                
                ct[key] = group.deserialize(base64.b64decode(value_fixed))
                print(f"    Successfully deserialized {key}")
            except Exception as e:
                print(f"    ERROR deserializing {key}: {e}")
                raise e
        elif isinstance(value, dict):
            print(f"  Processing dict for CT key: {key}")
            ct[key] = {}
            for k, v in value.items():
                print(f"    Processing sub-key: {k}, type: {type(v)}")
                if isinstance(v, str):
                    try:
                        # Fix base64 padding if needed
                        v_fixed = v
                        padding_needed = len(v_fixed) % 4
                        if padding_needed:
                            v_fixed += '=' * (4 - padding_needed)
                        
                        ct[key][k] = group.deserialize(base64.b64decode(v_fixed))
                        print(f"      Successfully deserialized {k}")
                    except Exception as e:
                        print(f"      ERROR deserializing {k}: {e}")
                        ct[key][k] = str(v)
                else:
                    ct[key][k] = str(v)
        elif isinstance(value, list):
            print(f"  Processing list for CT key: {key}, length: {len(value)}")
            ct[key] = []
            for i, item in enumerate(value):
                print(f"    Item {i}: type {type(item)}")
                if isinstance(item, str):
                    try:
                        # Fix base64 padding if needed
                        item_fixed = item
                        padding_needed = len(item_fixed) % 4
                        if padding_needed:
                            item_fixed += '=' * (4 - padding_needed)
                        
                        deserialized = group.deserialize(base64.b64decode(item_fixed))
                        ct[key].append(deserialized)
                        print(f"      Successfully deserialized item {i}")
                    except Exception as e:
                        print(f"      ERROR deserializing item {i}: {e}")
                        ct[key].append(str(item))
                else:
                    ct[key].append(str(item))
        else:
            print(f"  Direct string conversion for CT key: {key}")
            ct[key] = str(value)
    
    print(f"Final ciphertext structure: {list(ct.keys())}")
    
    # Debug: Print policy and attributes
    print(f"=== FINAL DECRYPTION ATTEMPT ===")
    print(f"Ciphertext policy: {ct.get('policy', 'No policy found')}")
    print(f"Secret key attributes (converted to integers): {sk.get('attributes', 'No attributes found')}")
    print(f"Secret key keys: {list(sk.keys())}")
    print(f"Ciphertext keys: {list(ct.keys())}")
    
    # Check if we have all required components
    required_sk_keys = ['attributes']
    required_ct_keys = ['policy']
    
    missing_sk = [k for k in required_sk_keys if k not in sk]
    missing_ct = [k for k in required_ct_keys if k not in ct]
    
    if missing_sk:
        print(f"WARNING: Missing secret key components: {missing_sk}")
    if missing_ct:
        print(f"WARNING: Missing ciphertext components: {missing_ct}")
    
    # Decrypt - correct parameter order: (public_key, ciphertext, secret_key)
    print("Attempting Waters11 decryption...")
    decrypted_gt = waters_abe.decrypt(pk, ct, sk)
    print(f"Decryption successful! GT element type: {type(decrypted_gt)}")
    
    # Convert GT element back to AES key
    print("Converting GT element back to original AES key...")
    
    # Use the EXACT same approach as in encryption:
    # derived_key = SHA256(serialize(gt_message))
    
    # Serialize the GT element to get consistent bytes
    gt_bytes = group.serialize(decrypted_gt)
    print(f"GT serialized to {len(gt_bytes)} bytes")
    print(f"GT element bytes (first 32): {gt_bytes[:32].hex()}")
    
    # Use SHA256 to get exactly 32 bytes for AES-256 (same as encryption)
    import hashlib
    derived_key = hashlib.sha256(gt_bytes).digest()
    print(f"Derived key using SHA256 of GT element")
    print(f"Derived key length: {len(derived_key)} bytes")
    print(f"Derived key bytes (first 16): {derived_key[:16].hex()}")
    
    result = base64.b64encode(derived_key).decode('utf-8')
    print(f"Final AES key (base64): {result[:50]}...")
    
    # Check verification info for debugging
    verification_info = ct_data.get('_key_verification')
    if verification_info and verification_info.get('method') == 'sha256_hash':
        original_key_hash = verification_info.get('original_key_hash')
        print(f"Original key hash for reference: {original_key_hash}")
        print(f"Note: Derived key should work since it matches encryption process")
    else:
        print("No verification info available")
    
    print(f"Key derivation complete - this should now match encryption process")

except Exception as decrypt_error:
    print(f"DECRYPTION ERROR: {decrypt_error}")
    print(f"Error type: {type(decrypt_error)}")
    import traceback
    print(f"Traceback: {traceback.format_exc()}")
    result = f"ERROR: {str(decrypt_error)}"

result
        `);
        
        console.log('Python result type:', typeof result);
        console.log('Python result length:', result ? result.length : 'null');
        console.log('Python result first 100 chars:', result ? result.substring(0, 100) : 'null');
        
        if (result.startsWith('ERROR:')) {
            console.error('Python returned error:', result);
            throw new Error(result.substring(7));
        }
        
        console.log('CP-ABE decryption successful!');
        console.log('=== DECRYPT CP-ABE KEY DEBUG END ===');
        return result;
        
    } catch (error) {
        console.error("=== CP-ABE DECRYPTION ERROR ===");
        console.error("Error type:", typeof error);
        console.error("Error message:", error.message);
        console.error("Error stack:", error.stack);
        console.error("Full error object:", error);
        console.error("=== END ERROR DEBUG ===");
        throw error;
    }
}

// Decrypt AES encrypted field
async function decryptAESField(encryptedDataBase64, keyBase64, ivBase64) {
    try {
        console.log("=== AES DECRYPTION DEBUG ===");
        console.log("Encrypted data (base64):", encryptedDataBase64 ? encryptedDataBase64.substring(0, 50) + "..." : "null");
        console.log("Key (base64):", keyBase64 ? keyBase64.substring(0, 20) + "..." : "null");
        console.log("IV (base64):", ivBase64 ? ivBase64.substring(0, 20) + "..." : "null");
        
        // Convert base64 to ArrayBuffer
        const encryptedData = base64ToArrayBuffer(encryptedDataBase64);
        const keyBytes = base64ToArrayBuffer(keyBase64);
        const iv = base64ToArrayBuffer(ivBase64);
        
        console.log("Encrypted data length:", encryptedData.byteLength);
        console.log("Key length:", keyBytes.byteLength);
        console.log("IV length:", iv.byteLength);
        
        // Import AES key
        const cryptoKey = await crypto.subtle.importKey(
            "raw",
            keyBytes,
            { name: "AES-GCM" },
            false,
            ["decrypt"]
        );
        console.log("AES key imported successfully");
        
        // Decrypt
        console.log("Attempting AES-GCM decryption...");
        const decryptedBuffer = await crypto.subtle.decrypt(
            { name: "AES-GCM", iv: iv },
            cryptoKey,
            encryptedData
        );
        console.log("AES decryption successful! Decrypted length:", decryptedBuffer.byteLength);
        
        // Convert to string
        const decryptedText = new TextDecoder().decode(decryptedBuffer);
        console.log("Decrypted text length:", decryptedText.length);
        console.log("Decrypted text preview:", decryptedText.substring(0, 50));
        console.log("=== AES DECRYPTION DEBUG END ===");
        return decryptedText;
        
    } catch (error) {
        console.error("=== AES DECRYPTION ERROR ===");
        console.error("Error type:", error.constructor.name);
        console.error("Error message:", error.message);
        console.error("Error code:", error.code);
        console.error("Full error:", error);
        console.error("=== END AES ERROR DEBUG ===");
        throw error;
    }
}

// Main decryption function
async function performDecryption() {
    try {
        if (!isSystemReady) {
            throw new Error('Hệ thống chưa sẵn sàng');
        }
        
        if (decryptBtn) decryptBtn.disabled = true;
        logStatus("Đang thực hiện giải mã...", "info");
        
        // Fetch encrypted data if not already loaded
        if (!encryptedData) {
            await fetchEncryptedData();
        }
        
        const decryptedFields = {};
        let patientDataDecrypted = false;
        let medicalDataDecrypted = false;
        
        try {
            // Try to decrypt patient info
            logStatus("Đang giải mã khóa AES cho thông tin bệnh nhân...", "info");
            const patientAESKey = await decryptCPABEKey(encryptedData.patient_info_aes_key_blob);
            
            console.log("=== ENCRYPTED DATA STRUCTURE DEBUG ===");
            console.log("Patient data keys:", Object.keys(encryptedData).filter(k => k.includes('patient')));
            console.log("Patient name blob length:", encryptedData.patient_name_blob ? encryptedData.patient_name_blob.length : 'null');
            console.log("Patient IV blob length:", encryptedData.patient_info_aes_iv_blob ? encryptedData.patient_info_aes_iv_blob.length : 'null');
            console.log("Patient name blob sample:", encryptedData.patient_name_blob ? encryptedData.patient_name_blob.substring(0, 50) : 'null');
            console.log("Patient IV blob sample:", encryptedData.patient_info_aes_iv_blob ? encryptedData.patient_info_aes_iv_blob.substring(0, 30) : 'null');
            console.log("=== END STRUCTURE DEBUG ===");
            
            // Decrypt patient info fields
            if (encryptedData.patient_name_blob) {
                decryptedFields.patient_name = await decryptAESField(
                    encryptedData.patient_name_blob,
                    patientAESKey,
                    encryptedData.patient_info_aes_iv_blob
                );
            }
            
            if (encryptedData.patient_age_blob) {
                decryptedFields.patient_age = await decryptAESField(
                    encryptedData.patient_age_blob,
                    patientAESKey,
                    encryptedData.patient_info_aes_iv_blob
                );
            }
            
            if (encryptedData.patient_gender_blob) {
                decryptedFields.patient_gender = await decryptAESField(
                    encryptedData.patient_gender_blob,
                    patientAESKey,
                    encryptedData.patient_info_aes_iv_blob
                );
            }
            
            if (encryptedData.patient_phone_blob) {
                decryptedFields.patient_phone = await decryptAESField(
                    encryptedData.patient_phone_blob,
                    patientAESKey,
                    encryptedData.patient_info_aes_iv_blob
                );
            }
            
            patientDataDecrypted = true;
            logStatus("Thông tin bệnh nhân đã được giải mã thành công!", "success");
            
        } catch (error) {
            console.log("Không thể giải mã thông tin bệnh nhân:", error.message);
            decryptedFields.patient_name = "❌ Không có quyền truy cập";
            decryptedFields.patient_age = "❌ Không có quyền truy cập";
            decryptedFields.patient_gender = "❌ Không có quyền truy cập";
            decryptedFields.patient_phone = "❌ Không có quyền truy cập";
        }
        
        try {
            // Try to decrypt medical record
            logStatus("Đang giải mã khóa AES cho hồ sơ y tế...", "info");
            const medicalAESKey = await decryptCPABEKey(encryptedData.medical_record_aes_key_blob);
            
            // Decrypt medical record fields
            if (encryptedData.chief_complaint_blob) {
                decryptedFields.chief_complaint = await decryptAESField(
                    encryptedData.chief_complaint_blob,
                    medicalAESKey,
                    encryptedData.medical_record_aes_iv_blob
                );
            }
            
            if (encryptedData.past_medical_history_blob) {
                decryptedFields.past_medical_history = await decryptAESField(
                    encryptedData.past_medical_history_blob,
                    medicalAESKey,
                    encryptedData.medical_record_aes_iv_blob
                );
            }
            
            if (encryptedData.diagnosis_blob) {
                decryptedFields.diagnosis = await decryptAESField(
                    encryptedData.diagnosis_blob,
                    medicalAESKey,
                    encryptedData.medical_record_aes_iv_blob
                );
            }
            
            if (encryptedData.status_blob) {
                decryptedFields.status = await decryptAESField(
                    encryptedData.status_blob,
                    medicalAESKey,
                    encryptedData.medical_record_aes_iv_blob
                );
            }
            
            medicalDataDecrypted = true;
            logStatus("Hồ sơ y tế đã được giải mã thành công!", "success");
            
        } catch (error) {
            console.log("Không thể giải mã hồ sơ y tế:", error.message);
            decryptedFields.chief_complaint = "❌ Không có quyền truy cập";
            decryptedFields.past_medical_history = "❌ Không có quyền truy cập";
            decryptedFields.diagnosis = "❌ Không có quyền truy cập";
            decryptedFields.status = "❌ Không có quyền truy cập";
        }
        
        // Display results
        displayDecryptedData(decryptedFields);
        
        if (patientDataDecrypted && medicalDataDecrypted) {
            logStatus("✅ Giải mã hoàn tất! Bạn có quyền truy cập tất cả dữ liệu.", "success");
        } else if (patientDataDecrypted || medicalDataDecrypted) {
            logStatus("⚠️ Giải mã một phần thành công. Bạn chỉ có quyền truy cập một số dữ liệu.", "warning");
        } else {
            logStatus("❌ Không thể giải mã dữ liệu. Bạn không có quyền truy cập.", "error");
        }
        
    } catch (error) {
        logStatus(`Lỗi giải mã: ${error.message}`, "error");
        console.error("Decryption error:", error);
    } finally {
        if (decryptBtn) decryptBtn.disabled = false;
    }
}

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
        await initializeDecryptionSystem();
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
            await initializeDecryptionSystem();
        } catch (error) {
            console.error('Failed to initialize decryption system:', error);
            logStatus('Lỗi khởi tạo hệ thống. Vui lòng thử lại.', 'error');
        }
    }, 2000); // Increased timeout to 2 seconds
}); 