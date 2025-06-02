from django.core.management.base import BaseCommand
from django.db import transaction
from backend.models import User, Attribute, UserAttribute, AccessPolicy


class Command(BaseCommand):
    help = 'Demo hệ thống CP-ABE đúng theo cấu trúc cây từ ảnh'

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🏥 Demo: CP-ABE đúng theo cấu trúc cây từ ảnh')
        )

        try:
            with transaction.atomic():
                # 1. Tạo policy đúng theo ảnh
                self.create_correct_policy()
                
                # 2. Tạo sample users theo từng nhánh của cây
                self.create_sample_users_by_branches()
                
                # 3. Demo kiểm tra quyền truy cập
                self.demo_access_control()

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Lỗi: {e}')
            )

    def create_correct_policy(self):
        """Tạo policy đúng theo cấu trúc cây từ ảnh"""
        self.stdout.write('\n🔐 Tạo chính sách CP-ABE đúng theo ảnh...')
        
        # Xóa các policy cũ
        AccessPolicy.objects.all().delete()
        
        # Policy đúng theo cấu trúc cây:
        # OR(Family_members, Personal_doctor, AND(OR(Hospital1,Hospital2), OR(Sanatorium,Nurse,Physician), Healthcare_staff, OR(Researcher, M.D., OR(Health_science_centre, Medicine_institute))))
        policy = AccessPolicy.objects.create(
            name='Patient Medical Record Access',
            policy_template='family_members:{{PATIENT_ID}} OR doctor OR ((hospital_1 OR hospital_2) AND (sanatorium OR nurse OR physician) AND healthcare_staff AND (researcher OR md_degree OR (health_science_centre OR medicine_institute)))',
            policy_type='patient_specific',
            description='Chính sách truy cập hồ sơ bệnh nhân theo đúng cấu trúc cây CP-ABE từ ảnh'
        )
        
        self.stdout.write(f'  ✅ Đã tạo policy: {policy.name}')
        self.stdout.write(f'  📝 Template: {policy.policy_template}')

    def create_sample_users_by_branches(self):
        """Tạo users mẫu theo từng nhánh của cây"""
        self.stdout.write('\n👥 Tạo users mẫu theo từng nhánh của cây...')
        
        # Users theo từng nhánh của cây OR
        users_data = [
            # NHÁNH 1: Family_members (có patient_id)
            ('family1@example.com', 'Vợ của BN A', ['family_members'], 'PA1B2C3D4E'),
            ('family2@example.com', 'Con của BN A', ['family_members'], 'PA1B2C3D4E'),
            
            # NHÁNH 2: Personal doctor (không cần điều kiện thêm)
            ('doctor1@example.com', 'BS. Bác sĩ cá nhân', ['doctor'], None),
            
            # NHÁNH 3: AND phức tạp - CẦN TẤT CẢ các điều kiện
            # Phải có: (hospital_1 OR hospital_2) AND (sanatorium OR nurse OR physician) AND healthcare_staff AND (researcher OR md_degree OR (health_science_centre OR medicine_institute))
            
            # 3a. Nhân viên bệnh viện + y tá + healthcare_staff + researcher
            ('complex1@example.com', 'Nhân viên bệnh viện + Y tá + Nghiên cứu', 
             ['hospital_1', 'nurse', 'healthcare_staff', 'researcher'], None),
            
            # 3b. Nhân viên bệnh viện 2 + bác sĩ lâm sàng + healthcare_staff + có bằng MD
            ('complex2@example.com', 'BV2 + BS lâm sàng + MD', 
             ['hospital_2', 'physician', 'healthcare_staff', 'md_degree'], None),
             
            # 3c. Bệnh viện + sanatorium + healthcare_staff + trung tâm y học
            ('complex3@example.com', 'BV1 + Sanatorium + Trung tâm y học', 
             ['hospital_1', 'sanatorium', 'healthcare_staff', 'health_science_centre'], None),
             
            # 3d. Bệnh viện + y tá + healthcare_staff + viện y học  
            ('complex4@example.com', 'BV2 + Y tá + Viện y học', 
             ['hospital_2', 'nurse', 'healthcare_staff', 'medicine_institute'], None),
            
            # USERS KHÔNG ĐỦ ĐIỀU KIỆN
            # Thiếu healthcare_staff
            ('incomplete1@example.com', 'Thiếu healthcare_staff', 
             ['hospital_1', 'nurse', 'researcher'], None),
             
            # Thiếu hospital
            ('incomplete2@example.com', 'Thiếu hospital', 
             ['nurse', 'healthcare_staff', 'researcher'], None),
             
            # Thiếu sanatorium/nurse/physician
            ('incomplete3@example.com', 'Thiếu sanatorium/nurse/physician', 
             ['hospital_1', 'healthcare_staff', 'researcher'], None),
             
            # Thiếu researcher/md_degree/health_science_centre/medicine_institute
            ('incomplete4@example.com', 'Thiếu research components', 
             ['hospital_1', 'nurse', 'healthcare_staff'], None),
            
            # User hoàn toàn không có quyền
            ('unauthorized@example.com', 'Không có quyền', [], None),
        ]
        
        for email, name, attr_names, target_patient_id in users_data:
            # Tạo user
            user, created = User.objects.get_or_create(
                email=email,
                defaults={'first_name': name.split()[0], 'last_name': ' '.join(name.split()[1:])}
            )
            
            if created:
                self.stdout.write(f'  ✅ Tạo user: {name}')
            
            # Xóa attributes cũ
            UserAttribute.objects.filter(user=user).delete()
            
            # Thêm attributes
            for attr_name in attr_names:
                try:
                    attribute = Attribute.objects.get(name=attr_name)
                    UserAttribute.objects.create(
                        user=user,
                        attribute=attribute,
                        patient_id=target_patient_id if attribute.supports_patient_id else None
                    )
                    attr_display = f"{attr_name}:{target_patient_id}" if target_patient_id and attribute.supports_patient_id else attr_name
                    self.stdout.write(f'    📝 + {attr_display}')
                except Attribute.DoesNotExist:
                    self.stdout.write(f'    ⚠️  Attribute không tồn tại: {attr_name}')

    def demo_access_control(self):
        """Demo kiểm tra quyền truy cập theo cấu trúc cây"""
        self.stdout.write('\n🔍 Demo kiểm tra quyền truy cập theo cấu trúc cây...')
        
        # Lấy policy
        policy = AccessPolicy.objects.first()
        if not policy:
            self.stdout.write(self.style.ERROR('❌ Không tìm thấy policy'))
            return
        
        # Render policy cho bệnh nhân A
        patient_id = 'PA1B2C3D4E'
        rendered_policy = policy.render_policy(patient_id=patient_id)
        
        self.stdout.write(f'\n📋 Hồ sơ bệnh nhân: {patient_id}')
        self.stdout.write(f'🔐 Policy: {rendered_policy}')
        
        # Giải thích cấu trúc cây
        self.stdout.write('\n🌳 Cấu trúc cây CP-ABE từ ảnh:')
        self.stdout.write('  OR(')
        self.stdout.write('    1️⃣ family_members:PA1B2C3D4E,')
        self.stdout.write('    2️⃣ doctor,') 
        self.stdout.write('    3️⃣ AND(')
        self.stdout.write('         (hospital_1 OR hospital_2)')
        self.stdout.write('         AND (sanatorium OR nurse OR physician)')
        self.stdout.write('         AND healthcare_staff')
        self.stdout.write('         AND (researcher OR md_degree OR (health_science_centre OR medicine_institute))')
        self.stdout.write('       )')
        self.stdout.write('  )')
        
        # Kiểm tra từng user
        self.stdout.write('\n🎯 Kết quả kiểm tra quyền truy cập:')
        
        for user in User.objects.all():
            user_attributes = []
            for ua in UserAttribute.objects.filter(user=user):
                if ua.patient_id:
                    user_attributes.append(f"{ua.attribute.name}:{ua.patient_id}")
                else:
                    user_attributes.append(ua.attribute.name)
            
            can_access = self.check_access_correct(rendered_policy, user_attributes, patient_id)
            
            status = '✅ CÓ THỂ' if can_access else '❌ KHÔNG THỂ'
            self.stdout.write(f'  {status} {user.get_full_name()}')
            self.stdout.write(f'    📝 Attributes: {", ".join(user_attributes) if user_attributes else "Không có"}')
            
            if can_access:
                reason = self.get_access_reason(user_attributes, patient_id)
                self.stdout.write(f'    💡 Lý do: {reason}')

    def check_access_correct(self, policy, user_attributes, patient_id):
        """Kiểm tra quyền truy cập đúng theo cấu trúc cây"""
        if not user_attributes:
            return False
        
        attr_set = set(user_attributes)
        
        # NHÁNH 1: family_members với patient_id đúng
        if f'family_members:{patient_id}' in attr_set:
            return True
        
        # NHÁNH 2: doctor (đơn giản)
        if 'doctor' in attr_set:
            return True
        
        # NHÁNH 3: AND phức tạp - CẦN TẤT CẢ 4 điều kiện
        # Điều kiện 1: (hospital_1 OR hospital_2)
        has_hospital = 'hospital_1' in attr_set or 'hospital_2' in attr_set
        
        # Điều kiện 2: (sanatorium OR nurse OR physician)
        has_medical_role = any(x in attr_set for x in ['sanatorium', 'nurse', 'physician'])
        
        # Điều kiện 3: healthcare_staff
        has_healthcare_staff = 'healthcare_staff' in attr_set
        
        # Điều kiện 4: (researcher OR md_degree OR (health_science_centre OR medicine_institute))
        has_research = (
            'researcher' in attr_set or 
            'md_degree' in attr_set or 
            'health_science_centre' in attr_set or 
            'medicine_institute' in attr_set
        )
        
        # CẦN TẤT CẢ 4 điều kiện
        return has_hospital and has_medical_role and has_healthcare_staff and has_research

    def get_access_reason(self, user_attributes, patient_id):
        """Trả về lý do được truy cập"""
        attr_set = set(user_attributes)
        
        if f'family_members:{patient_id}' in attr_set:
            return 'Nhánh 1: Thành viên gia đình'
        
        if 'doctor' in attr_set:
            return 'Nhánh 2: Bác sĩ cá nhân'
        
        # Kiểm tra nhánh 3
        has_hospital = 'hospital_1' in attr_set or 'hospital_2' in attr_set
        has_medical_role = any(x in attr_set for x in ['sanatorium', 'nurse', 'physician'])
        has_healthcare_staff = 'healthcare_staff' in attr_set
        has_research = any(x in attr_set for x in ['researcher', 'md_degree', 'health_science_centre', 'medicine_institute'])
        
        if has_hospital and has_medical_role and has_healthcare_staff and has_research:
            hospital_part = 'hospital_1' if 'hospital_1' in attr_set else 'hospital_2'
            medical_part = next(x for x in ['sanatorium', 'nurse', 'physician'] if x in attr_set)
            research_part = next(x for x in ['researcher', 'md_degree', 'health_science_centre', 'medicine_institute'] if x in attr_set)
            return f'Nhánh 3: {hospital_part} + {medical_part} + healthcare_staff + {research_part}'
        
        return 'Không xác định' 