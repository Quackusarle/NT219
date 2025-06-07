INSERT INTO backend_accesspolicy (name, policy_template, policy_type, description, created_at, updated_at) VALUES

-- MEDICAL STAFF ACCESS
('Medical Staff Only', 
 'doctor OR physician OR nurse', 
 'static',
 'Chỉ nhân viên y tế có thể truy cập',
 NOW(), NOW()),

-- HOSPITAL ACCESS
('Hospital Staff', 
 '(hospital_1 OR hospital_2 OR sanatorium) AND (doctor OR nurse OR physician OR healthcare_staff)', 
 'static',
 'Nhân viên bệnh viện có chức vụ y tế',
 NOW(), NOW()),

-- RESEARCH ACCESS  
('Research Access',
 '(researcher OR md) AND (health_science_centre OR medicine_institute)',
 'static', 
 'Nhà nghiên cứu tại các viện nghiên cứu',
 NOW(), NOW()),

-- COMBINED ACCESS
('Medical or Research',
 'doctor OR physician OR ((researcher OR md) AND (health_science_centre OR medicine_institute))',
 'static',
 'Bác sĩ hoặc nhà nghiên cứu y tế',
 NOW(), NOW());