-- 1. BASIC ROLES
INSERT INTO backend_attribute (name, description, supports_patient_id, created_at) 
VALUES ('patient', 'Bệnh nhân - thuộc tính mặc định', false, NOW())
ON CONFLICT (name) DO NOTHING;

INSERT INTO backend_attribute (name, description, supports_patient_id, created_at) 
VALUES ('family_members', 'Thành viên gia đình - có quyền truy cập dữ liệu bệnh nhân cụ thể', true, NOW())
ON CONFLICT (name) DO NOTHING;

INSERT INTO backend_attribute (name, description, supports_patient_id, created_at) 
VALUES ('doctor', 'Bác sĩ - có quyền truy cập dữ liệu bệnh nhân cụ thể', false, NOW())
ON CONFLICT (name) DO NOTHING;

-- 2. HOSPITAL STAFF
INSERT INTO backend_attribute (name, description, supports_patient_id, created_at) 
VALUES ('hospital_1', 'Nhân viên Bệnh viện 1', false, NOW())
ON CONFLICT (name) DO NOTHING;

INSERT INTO backend_attribute (name, description, supports_patient_id, created_at) 
VALUES ('hospital_2', 'Nhân viên Bệnh viện 2', false, NOW())
ON CONFLICT (name) DO NOTHING;

INSERT INTO backend_attribute (name, description, supports_patient_id, created_at) 
VALUES ('sanatorium', 'Nhân viên Sanatorium', false, NOW())
ON CONFLICT (name) DO NOTHING;

INSERT INTO backend_attribute (name, description, supports_patient_id, created_at) 
VALUES ('nurse', 'Y tá', false, NOW())
ON CONFLICT (name) DO NOTHING;

INSERT INTO backend_attribute (name, description, supports_patient_id, created_at) 
VALUES ('physician', 'Bác sĩ', false, NOW())
ON CONFLICT (name) DO NOTHING;

INSERT INTO backend_attribute (name, description, supports_patient_id, created_at) 
VALUES ('healthcare_staff', 'Nhân viên y tế', false, NOW())
ON CONFLICT (name) DO NOTHING;

-- 3. RESEARCH & ACADEMIC
INSERT INTO backend_attribute (name, description, supports_patient_id, created_at) 
VALUES ('researcher', 'Nhà nghiên cứu', false, NOW())
ON CONFLICT (name) DO NOTHING;

INSERT INTO backend_attribute (name, description, supports_patient_id, created_at) 
VALUES ('md', 'Tiến sĩ Y khoa', false, NOW())
ON CONFLICT (name) DO NOTHING;

INSERT INTO backend_attribute (name, description, supports_patient_id, created_at) 
VALUES ('health_science_centre', 'Trung tâm Khoa học Y tế', false, NOW())
ON CONFLICT (name) DO NOTHING;

INSERT INTO backend_attribute (name, description, supports_patient_id, created_at) 
VALUES ('medicine_institute', 'Viện Y học', false, NOW())
ON CONFLICT (name) DO NOTHING;