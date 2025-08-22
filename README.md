# CP-ABE for Secure Electronic Health Records

Một hệ thống Proof-of-Concept để quản lý Hồ sơ Sức khỏe Điện tử (EHR) với cơ chế kiểm soát truy cập chi tiết bằng cách sử dụng Mã hóa Dựa trên Thuộc tính (Attribute-Based Encryption) dựa trên scheme Waters'11, được thực thi hoàn toàn phía client.

## Vấn đề

Dữ liệu sức khỏe điện tử (EHR) cực kỳ nhạy cảm. Các hệ thống lưu trữ truyền thống thường gặp khó khăn trong việc thực thi các quy tắc truy cập phức tạp và linh hoạt (ví dụ: "chỉ bác sĩ trong khoa tim mạch mới có thể xem kết quả này"). Hơn nữa, nếu máy chủ bị xâm nhập, toàn bộ dữ liệu có nguy cơ bị lộ.

## Giải pháp

Dự án này đề xuất một kiến trúc zero-trust, trong đó máy chủ không bao giờ có quyền truy cập vào dữ liệu gốc. Toàn bộ quá trình mã hóa và giải mã được thực hiện trực tiếp trên trình duyệt của người dùng cuối.

Chúng tôi sử dụng Ciphertext-Policy Attribute-Based Encryption (CP-ABE), một kỹ thuật mã hóa tiên tiến cho phép người tạo dữ liệu (Data Creator) định nghĩa một chính sách truy cập động và nhúng nó trực tiếp vào bản mã. Chỉ những người dùng (Data Users) có khóa bí mật chứa các thuộc tính thỏa mãn chính sách đó mới có thể giải mã được dữ liệu.

## ✨ Các tính năng chính

- 🔐 **Mã hóa phía Client (End-to-End)**: Dữ liệu được mã hóa trên trình duyệt của người gửi và chỉ được giải mã trên trình duyệt của người nhận. Máy chủ chỉ lưu trữ dữ liệu đã mã hóa (ciphertext).

- 🎯 **Kiểm soát Truy cập Chi tiết**: Cho phép tạo các chính sách truy cập phức tạp và linh hoạt. Ví dụ: `(ROLE:DOCTOR OR ROLE:NURSE) AND DEPARTMENT:CARDIOLOGY`.

- 🛡️ **Kiến trúc Zero-Trust**: Máy chủ không cần được tin tưởng. Ngay cả quản trị viên hệ thống cũng không thể xem được nội dung dữ liệu của bệnh nhân.

- 🌐 **Hệ thống Phân tán**: Tách biệt rõ ràng giữa Auth Center (quản lý danh tính, khóa) và Resource Server (lưu trữ dữ liệu), tăng cường bảo mật và khả năng mở rộng.

- 🔑 **Xác thực Hiện đại**: Sử dụng JSON Web Tokens (JWT) ký bằng thuật toán bất đối xứng (ES256) để xác thực các yêu cầu API một cách an toàn.

- ⚙️ **Mã hóa Lai Hiệu quả**: Kết hợp tốc độ của AES-256-GCM cho dữ liệu lớn và sự linh hoạt của CP-ABE để quản lý khóa.

## 🚀 Cách hoạt động

Để hệ thống vừa an toàn vừa có thể sử dụng được, chúng tôi phân tách rõ ràng giữa metadata (thông tin mô tả, không nhạy cảm) và payload (nội dung chi tiết, nhạy cảm).

- **Metadata (Không mã hóa)**: Bao gồm các thông tin như patient_id, mô tả chung (description), loại dữ liệu (data_type), và ngày tạo. Các thông tin này được lưu ở dạng rõ (plaintext) để phục vụ cho việc tìm kiếm và truy vấn.

- **Payload (Đã mã hóa)**: Bao gồm nội dung thực sự của hồ sơ y tế như thông tin cá nhân và file chứa bệnh án, hướng điều trị,... Phần này luôn được mã hóa.


### 1. Chi tiết Quy trình Mã hóa (Client-Side)

Khi một Data Creator Upload, các bước sau được thực hiện hoàn toàn trên trình duyệt của họ:

1. **Tạo Khóa Mã hóa Dữ liệu (DEK)**: Trình duyệt sử dụng Web Crypto API để tạo một khóa đối xứng AES-256-GCM ngẫu nhiên, sử dụng một lần. Đây là DEK.

2. **Mã hóa Nội dung**: Nội dung chi tiết của hồ sơ (payload) được mã hóa bằng DEK vừa tạo.

3. **Định nghĩa Chính sách Truy cập**: Data Creator chọn các thuộc tính (ví dụ: vai trò, chuyên khoa) để tạo thành một chuỗi chính sách.

4. **Mã hóa DEK bằng CP-ABE**:
   - Trình duyệt sử dụng Public Key (PK) của hệ thống và chính sách truy cập ở trên để mã hóa khóa DEK. Kết quả là một bản mã của DEK (encrypted DEK).
   - Quá trình này được thực hiện bởi thư viện charm-crypto chạy trên Pyodide (WebAssembly).

5. **Gửi lên Server**: Trình duyệt đóng gói và gửi một bundle lên Resource Server, bao gồm:
   - Metadata (không mã hóa).
   - Chính sách truy cập (dạng chuỗi).
   - Bản mã của DEK (encrypted DEK).
   - Bản mã của nội dung (encrypted payload).


### 2. Tìm kiếm Hồ sơ Bệnh nhân

Quá trình tìm kiếm được thiết kế để hiệu quả mà không làm lộ dữ liệu nhạy cảm:

1. Người dùng (Data User) nhập patient_id vào giao diện tìm kiếm.

2. Trình duyệt gửi một yêu cầu API đến Resource Server để tìm tất cả các bản ghi có patient_id tương ứng.

3. Resource Server thực hiện một truy vấn đơn giản trên cơ sở dữ liệu, lọc theo trường patient_id trong phần metadata.

4. Server trả về một danh sách các bản ghi. Mỗi bản ghi trong danh sách này chỉ chứa phần metadata và payload đã mã hóa.

5. Giao diện hiển thị danh sách các mảnh hồ sơ tìm được (ví dụ: "Đơn thuốc tái khám lần 4", "Kết quả xét nghiệm ngày X"). Tại thời điểm này, chưa có bất kỳ hoạt động giải mã nào diễn ra.

### 3. Chi tiết Quy trình Giải mã (Client-Side)

Khi một Data User chọn xem một hồ sơ cụ thể từ danh sách kết quả tìm kiếm:

1. **Tải Dữ liệu Mã hóa**: Data User sẽ phải đáp ứng chính sách ABAC để có thể tải bundle dữ liệu đã mã hóa từ Resource Server.

2. **Giải mã Khóa DEK**:
   - Data User đã tải Secret Key (SK) cá nhân của họ từ Auth Center. SK này chứa các thuộc tính của họ.
   - Trình duyệt sử dụng SK để giải mã encrypted DEK.
   - Đây là bước kiểm soát truy cập cốt lõi: charm-crypto sẽ chỉ giải mã thành công nếu các thuộc tính trong SK của người dùng thỏa mãn chính sách truy cập được lưu cùng hồ sơ. Nếu không, quá trình sẽ thất bại.

3. **Giải mã Nội dung**: Nếu giải mã DEK thành công, trình duyệt sẽ có được khóa AES gốc. Nó tiếp tục dùng Web Crypto API và khóa DEK này để giải mã encrypted payload.

4. **Hiển thị**: Nội dung gốc của hồ sơ được hiển thị cho người dùng.

## 🛠️ Công nghệ sử dụng

| Lĩnh vực | Công nghệ |
|----------|-----------|
| Backend | Python, Django, Django REST Framework |
| Frontend | JavaScript, HTML, CSS |
| Cryptography | charm-crypto (cho CP-ABE - Waters '11 Scheme), Web Crypto API (cho AES-256-GCM) |
| Client-Side Python | Pyodide (Chạy Charm-Crypto trên trình duyệt qua WebAssembly) |
| Authentication | djangorestframework-simplejwt (JWT với thuật toán ES256) |

## Tình trạng Dự án

Đây là đồ án môn học và là một Proof-of-Concept (PoC) chức năng. Dự án đã chứng minh được tính khả thi của việc áp dụng CP-ABE phía client để xây dựng một hệ thống EHR an toàn.

## Các hạn chế và Hướng phát triển

- **Thu hồi Thuộc tính/Khóa**: Chưa triển khai cơ chế thu hồi (revocation) hiệu quả.

- **Bảo vệ Khóa Chủ**: Master Secret Key cần được bảo vệ bằng các giải pháp phần cứng như HSM trong môi trường thực tế.

- **Hiệu suất**: Khởi tạo Pyodide và thực hiện các phép toán CP-ABE trên trình duyệt có thể chậm trên các thiết bị cấu hình thấp.

- **Giao diện Người dùng (UI/UX)**: Giao diện được xây dựng ở mức cơ bản để minh họa luồng hoạt động.
