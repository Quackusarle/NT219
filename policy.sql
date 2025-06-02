INSERT INTO backend_accesspolicy (name, policy_template, policy_type, description, created_at, updated_at)
VALUES (
    'Patient Medical Record Access',
    'patient:{{PATIENT_ID}} OR family_members:{{PATIENT_ID}} OR doctor OR ((hospital_1 OR hospital_2 OR sanatorium) AND (nurse OR physician OR healthcare_staff) OR ((researcher OR md) AND (health_science_centre OR medicine_institute)))',
    'patient_specific',
    'Chính sách truy cập hồ sơ bệnh nhân theo đúng cấu trúc cây CP-ABE từ ảnh: Family_members HOẶC Personal_doctor HOẶC (Hospital AND Sanatorium AND Healthcare_staff AND Research)',
    NOW(), NOW()
);