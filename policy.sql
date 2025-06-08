INSERT INTO backend_accesspolicy (name, policy_template, description, created_at, updated_at) VALUES

-- DOCTOR ACCESS
('Only doctor', 
 'doctor', 
 'Chỉ bác sĩ được phép truy cập',
 NOW(), NOW()),

-- HOSPITAL STAFF ACCESS
('Hospital Staff', 
 '(hospital_1 OR hospital_2 OR sanatorium) AND (nurse OR physician OR healthcare_staff)', 
 'Nhân viên bệnh viện có chức vụ y tế',
 NOW(), NOW()),

-- RESEARCH ACCESS  
('Research Access',
 '(researcher OR md) AND (health_science_centre OR medicine_institute)',
 'Nhà nghiên cứu tại các viện nghiên cứu',
 NOW(), NOW()),