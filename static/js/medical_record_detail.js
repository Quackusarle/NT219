// Auto-decryption medical record detail script

let pyodideInstance = null;
let encryptedData = null;
const recordId = window.recordId;

function showResult(message, type = 'info') {
    const loadingOverlay = document.getElementById('loading-overlay');
    const decryptionResult = document.getElementById('decryption-result');
    const statusCard = document.getElementById('status-card');
    const statusTitle = document.getElementById('status-title');
    const statusMessage = document.getElementById('status-message');
    const retryDecryptBtn = document.getElementById('retry-decrypt-btn');
    
    if (loadingOverlay) loadingOverlay.style.display = 'none';
    if (decryptionResult) decryptionResult.style.display = 'block';
    
    const icons = {
        'info': 'fas fa-info-circle',
        'success': 'fas fa-check-circle', 
        'error': 'fas fa-exclamation-triangle'
    };
    
    const classes = {
        'info': 'alert-info',
        'success': 'alert-success',
        'error': 'alert-danger'
    };
    
    const cardClasses = {
        'success': 'border-success',
        'error': 'border-danger',
        'info': 'border-info'
    };
    
    if (statusTitle) {
        statusTitle.innerHTML = `<i class="${icons[type]}"></i> ${type === 'success' ? 'Giải mã thành công' : type === 'error' ? 'Giải mã thất bại' : 'Kết quả giải mã'}`;
    }
    
    if (statusMessage) {
        statusMessage.className = `alert ${classes[type]}`;
        statusMessage.innerHTML = `<i class="${icons[type]}"></i> ${message}`;
    }
    
    if (statusCard) {
        statusCard.className = `card ${cardClasses[type]}`;
    }
    
    if (retryDecryptBtn) {
        retryDecryptBtn.style.display = type === 'error' ? 'inline-block' : 'none';
    }
}

function getCSRFToken() {
    return document.cookie.match(/csrftoken=([^;]+)/)?.[1];
}

function base64ToArrayBuffer(base64) {
    const fixedBase64 = fixBase64Padding(base64);
    const binaryString = atob(fixedBase64);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes.buffer;
}

function fixBase64Padding(base64String) {
    while (base64String.length % 4) {
        base64String += '=';
    }
    return base64String;
}

async function initializeDecryptionSystem() {
    let retryCount = 0;
    const maxRetries = 5;
    
    while (typeof loadPyodide === 'undefined' && retryCount < maxRetries) {
        await new Promise(resolve => setTimeout(resolve, 1000));
        retryCount++;
    }
    
    if (typeof loadPyodide === 'undefined') {
        throw new Error('Không thể tải Pyodide. Vui lòng kiểm tra kết nối internet.');
    }
    
    pyodideInstance = await loadPyodide({
        stdout: (text) => console.log(`[Pyodide] ${text}`),
        stderr: (text) => console.error(`[Pyodide ERROR] ${text}`),
    });

    await pyodideInstance.loadPackage("micropip");
    const micropip = pyodideInstance.pyimport("micropip");
    
    const charmWheelURL = "http://localhost:8080/charm_crypto-0.50-cp312-cp312-pyodide_2024_0_wasm32.whl";
    await micropip.install(charmWheelURL);

    await pyodideInstance.runPythonAsync(`
from charm.toolbox.pairinggroup import PairingGroup
from charm.schemes.abenc.waters11 import Waters11
import base64

group = PairingGroup('SS512')
waters_abe = Waters11(group, uni_size=11)

globals()['_waters11_abe_scheme'] = waters_abe
globals()['_waters11_group'] = group
    `);
}

async function fetchEncryptedData() {
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
    return encryptedData;
}

async function decryptCPABEKey(encryptedKeyBase64) {
    const secretKeyStr = sessionStorage.getItem('abe_secret_key');
    if (!secretKeyStr) {
        throw new Error('Không tìm thấy khóa bí mật. Vui lòng đăng nhập lại.');
    }
    
    const secretKeyData = JSON.parse(secretKeyStr);
    const publicKeyStr = sessionStorage.getItem('abe_public_key');
    if (!publicKeyStr) {
        throw new Error('Không tìm thấy khóa công khai. Vui lòng đăng nhập lại.');
    }
    
    const publicKeyData = JSON.parse(publicKeyStr);
    
    // Get attribute mapping from session storage
    const attributeMappingStr = sessionStorage.getItem('abe_attribute_mapping');
    if (!attributeMappingStr) {
        throw new Error('Không tìm thấy attribute mapping. Vui lòng đăng nhập lại.');
    }
    
    const attributeMapping = JSON.parse(attributeMappingStr);
    const nameToInt = attributeMapping.name_to_int;

    // Decrypt in Python using the robust approach from the old file
    const result = await pyodideInstance.runPythonAsync(`
import base64
import json
import hashlib

result = None
try:
    waters_abe = _waters11_abe_scheme
    group = _waters11_group
    
    # Get attribute mapping for conversion
    name_to_int_mapping = ${JSON.stringify(nameToInt)}
    
    # Reconstruct secret key with robust handling
    sk_data = ${JSON.stringify(secretKeyData)}
    sk = {}
    
    for key, value in sk_data.items():
        if key == 'attributes' and isinstance(value, list):
            # Convert string attributes to string integers for Waters11
            attr_list = []
            for attr in value:
                if isinstance(attr, str) and attr in name_to_int_mapping:
                    converted = str(name_to_int_mapping[attr])
                    attr_list.append(converted)
                elif isinstance(attr, int):
                    attr_list.append(str(attr))
                elif isinstance(attr, str) and attr.isdigit():
                    attr_list.append(attr)
                else:
                    try:
                        converted = str(int(attr))
                        attr_list.append(converted)
                    except:
                        pass
            
            sk['attributes'] = attr_list
            sk['attr_list'] = attr_list
        elif key == 'secret_key' and isinstance(value, dict):
            # Process secret key components
            for sk_component_key, sk_component_value in value.items():
                if isinstance(sk_component_value, str):
                    try:
                        sk[sk_component_key] = group.deserialize(base64.b64decode(sk_component_value))
                    except Exception as e:
                        raise e
                elif isinstance(sk_component_value, list):
                    sk[sk_component_key] = []
                    for item in sk_component_value:
                        if isinstance(item, str):
                            try:
                                sk[sk_component_key].append(group.deserialize(base64.b64decode(item)))
                            except Exception as e:
                                sk[sk_component_key].append(item)
                        else:
                            sk[sk_component_key].append(item)
                elif isinstance(sk_component_value, dict):
                    sk[sk_component_key] = {}
                    for k, v in sk_component_value.items():
                        if isinstance(v, str):
                            try:
                                sk[sk_component_key][k] = group.deserialize(base64.b64decode(v))
                            except Exception as e:
                                sk[sk_component_key][k] = v
                        else:
                            sk[sk_component_key][k] = v
                else:
                    sk[sk_component_key] = sk_component_value
        elif key in ['user_email', 'attribute_integers']:
            sk[key] = value
        elif isinstance(value, str):
            try:
                sk[key] = group.deserialize(base64.b64decode(value))
            except Exception as e:
                sk[key] = value
        elif isinstance(value, list):
            sk[key] = [group.deserialize(base64.b64decode(item)) if isinstance(item, str) else item for item in value]
        else:
            sk[key] = value
    
    # Reconstruct public key
    pk_data = ${JSON.stringify(publicKeyData.public_key || publicKeyData.data?.public_key || publicKeyData)}
    pk = {}
    
    for key, value in pk_data.items():
        if isinstance(value, str):
            pk[key] = group.deserialize(base64.b64decode(value))
        elif isinstance(value, int):
            pk[key] = value
        elif isinstance(value, list):
            pk[key] = []
            for item in value:
                if isinstance(item, str):
                    pk[key].append(group.deserialize(base64.b64decode(item)))
                elif isinstance(item, int):
                    pk[key].append(item)
                else:
                    pk[key].append(item)
        else:
            pk[key] = value
    
    # Reconstruct ciphertext
    ct_str = "${encryptedKeyBase64}"
    
    # Fix base64 padding if needed
    ct_str_fixed = ct_str
    padding_needed = len(ct_str_fixed) % 4
    if padding_needed:
        ct_str_fixed += '=' * (4 - padding_needed)
    
    # Decode and parse ciphertext
    try:
        decoded_bytes = base64.b64decode(ct_str_fixed)
        decoded_str = decoded_bytes.decode('utf-8')
        ct_data = json.loads(decoded_str)
    except Exception as decode_error:
        raise decode_error
    
    ct = {}
    non_crypto_fields = {'policy', 'attribute_list', '_key_verification'}
    
    for key, value in ct_data.items():
        if key in non_crypto_fields:
            if key == 'policy':
                policy_str = str(value).strip()
                try:
                    policy_obj = waters_abe.util.createPolicy(policy_str)
                    ct[key] = policy_obj
                except Exception as e:
                    ct[key] = policy_str
            elif key == '_key_verification':
                ct[key] = value
            else:
                ct[key] = str(value)
        elif isinstance(value, str):
            try:
                value_fixed = value
                padding_needed = len(value_fixed) % 4
                if padding_needed:
                    value_fixed += '=' * (4 - padding_needed)
                
                ct[key] = group.deserialize(base64.b64decode(value_fixed))
            except Exception as e:
                raise e
        elif isinstance(value, dict):
            ct[key] = {}
            for k, v in value.items():
                if isinstance(v, str):
                    try:
                        v_fixed = v
                        padding_needed = len(v_fixed) % 4
                        if padding_needed:
                            v_fixed += '=' * (4 - padding_needed)
                        
                        ct[key][k] = group.deserialize(base64.b64decode(v_fixed))
                    except Exception as e:
                        ct[key][k] = str(v)
                else:
                    ct[key][k] = str(v)
        elif isinstance(value, list):
            ct[key] = []
            for item in value:
                if isinstance(item, str):
                    try:
                        item_fixed = item
                        padding_needed = len(item_fixed) % 4
                        if padding_needed:
                            item_fixed += '=' * (4 - padding_needed)
                        
                        deserialized = group.deserialize(base64.b64decode(item_fixed))
                        ct[key].append(deserialized)
                    except Exception as e:
                        ct[key].append(str(item))
                else:
                    ct[key].append(str(item))
        else:
            ct[key] = str(value)
    
    # Decrypt
    decrypted_gt = waters_abe.decrypt(pk, ct, sk)
    
    # Convert GT element back to AES key using SHA256
    gt_bytes = group.serialize(decrypted_gt)
    derived_key = hashlib.sha256(gt_bytes).digest()
    
    result = base64.b64encode(derived_key).decode('utf-8')

except Exception as decrypt_error:
    error_msg = str(decrypt_error)
    if "Policy not satisfied" in error_msg:
        result = f"ERROR:POLICY_NOT_SATISFIED"
    elif "Invalid element type" in error_msg:
        result = f"ERROR:INVALID_ELEMENT"
    else:
        result = f"ERROR: {error_msg}"

result
    `);
    
    if (result.startsWith('ERROR:')) {
        const errorType = result.substring(6);
        if (errorType === 'POLICY_NOT_SATISFIED') {
            throw new Error('Bạn không có đủ quyền để truy cập dữ liệu này. Policy không được thỏa mãn với các thuộc tính hiện tại của bạn.');
        } else if (errorType === 'INVALID_ELEMENT') {
            throw new Error('Lỗi xử lý dữ liệu mã hóa. Có thể dữ liệu đã bị hỏng hoặc không tương thích.');
        } else {
            throw new Error(errorType);
        }
    }
    
    return result;
}

async function decryptAESField(encryptedDataBase64, keyBase64, ivBase64) {
    const keyBytes = base64ToArrayBuffer(keyBase64);
    const ivBytes = base64ToArrayBuffer(ivBase64);
    const encryptedBytes = base64ToArrayBuffer(encryptedDataBase64);
    
    const cryptoKey = await crypto.subtle.importKey(
        'raw',
        keyBytes,
        { name: 'AES-GCM' },
        false,
        ['decrypt']
    );
    
    const decryptedArrayBuffer = await crypto.subtle.decrypt(
        { name: 'AES-GCM', iv: ivBytes },
        cryptoKey,
        encryptedBytes
    );
    
    const decoder = new TextDecoder('utf-8');
    return decoder.decode(decryptedArrayBuffer);
}

async function performDecryption() {
    try {
        await initializeDecryptionSystem();
        await fetchEncryptedData();
        
        const decryptedFields = {};
        let patientDataDecrypted = false;
        let medicalDataDecrypted = false;
        
        // Try to decrypt patient info
        try {
            const patientKeyBase64 = await decryptCPABEKey(encryptedData.patient_info_aes_key_blob);
            
            const patientFields = ['patient_name', 'patient_age', 'patient_gender', 'patient_phone'];
            for (const field of patientFields) {
                const encryptedField = encryptedData[`${field}_blob`];
                if (encryptedField) {
                    decryptedFields[field] = await decryptAESField(
                        encryptedField,
                        patientKeyBase64,
                        encryptedData.patient_info_aes_iv_blob
                    );
                }
            }
            patientDataDecrypted = true;
        } catch (error) {
            console.log('Cannot decrypt patient info:', error.message);
            const patientFields = ['patient_name', 'patient_age', 'patient_gender', 'patient_phone'];
            patientFields.forEach(field => {
                decryptedFields[field] = "❌ Không có quyền truy cập";
            });
        }
        
        // Try to decrypt medical record
        try {
            const medicalKeyBase64 = await decryptCPABEKey(encryptedData.medical_record_aes_key_blob);
            
            const medicalFields = ['chief_complaint', 'past_medical_history', 'diagnosis', 'status'];
            for (const field of medicalFields) {
                const encryptedField = encryptedData[`${field}_blob`];
                if (encryptedField) {
                    decryptedFields[field] = await decryptAESField(
                        encryptedField,
                        medicalKeyBase64,
                        encryptedData.medical_record_aes_iv_blob
                    );
                }
            }
            medicalDataDecrypted = true;
        } catch (error) {
            console.log('Cannot decrypt medical record:', error.message);
            const medicalFields = ['chief_complaint', 'past_medical_history', 'diagnosis', 'status'];
            medicalFields.forEach(field => {
                decryptedFields[field] = "❌ Không có quyền truy cập";
            });
        }
        
        // Display results
        displayDecryptedData(decryptedFields);
        
        if (patientDataDecrypted && medicalDataDecrypted) {
            showResult('✅ Giải mã hoàn tất! Bạn có quyền truy cập tất cả dữ liệu.', 'success');
        } else if (patientDataDecrypted || medicalDataDecrypted) {
            showResult('⚠️ Giải mã một phần thành công. Bạn chỉ có quyền truy cập một số dữ liệu.', 'info');
        } else {
            showResult('❌ Không thể giải mã dữ liệu. Bạn không có quyền truy cập với các thuộc tính hiện tại.', 'error');
        }
        
    } catch (error) {
        console.error('Decryption failed:', error);
        showResult(error.message, 'error');
    }
}

function displayDecryptedData(fields) {
    const decryptedContainer = document.getElementById('decrypted-data-container');
    if (decryptedContainer) {
        decryptedContainer.style.display = 'block';
    }
    
    const patientFields = {
        'patient_name': 'decrypted-patient-name',
        'patient_age': 'decrypted-patient-age', 
        'patient_gender': 'decrypted-patient-gender',
        'patient_phone': 'decrypted-patient-phone'
    };
    
    for (const [field, elementId] of Object.entries(patientFields)) {
        const element = document.getElementById(elementId);
        if (element && fields[field]) {
            element.textContent = fields[field];
        }
    }
    
    const medicalFields = {
        'chief_complaint': 'decrypted-chief-complaint',
        'past_medical_history': 'decrypted-past-medical-history',
        'diagnosis': 'decrypted-diagnosis',
        'status': 'decrypted-status'
    };
    
    for (const [field, elementId] of Object.entries(medicalFields)) {
        const element = document.getElementById(elementId);
        if (element && fields[field]) {
            element.textContent = fields[field];
        }
    }
}



document.addEventListener('DOMContentLoaded', function() {
    const retryDecryptBtn = document.getElementById('retry-decrypt-btn');
    
    if (retryDecryptBtn) {
        retryDecryptBtn.addEventListener('click', performDecryption);
    }
    
    // Auto-start decryption
    performDecryption();
}); 