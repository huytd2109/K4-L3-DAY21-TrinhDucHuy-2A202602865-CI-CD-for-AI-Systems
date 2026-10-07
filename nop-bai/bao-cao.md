# Báo Cáo Lab Day 21 - CI/CD cho AI Systems

| | |
|---|---|
| Họ và tên | Trịnh Đức Huy |
| MSSV | 2A202602865 |
| Lớp / Khóa | K4 |
| Repo GitHub | https://github.com/huytd2109/K4-L3-DAY21-TrinhDucHuy-2A202602865-CI-CD-for-AI-Systems |
| Ngày nộp | 07/10/2026 |

---

## 1. Bộ Siêu Tham Số Đã Chọn và Lý Do

| Lần chạy | n_estimators | learning_rate | max_depth | f1_score | accuracy |
|---|---|---|---|---|---|
| 1 | 100 | 0.1 | 3 | 0.7109 | 0.8780 |
| 2 | 50 | 0.05 | 2 | 0.6051 | 0.8460 |
| 3 | 200 | 0.1 | 5 | 0.7149 | 0.8740 |

**Bộ siêu tham số đã chọn:** `n_estimators=200`, `learning_rate=0.1`, `max_depth=5`.

**Lý do:** Ba thí nghiệm dùng 22.361 mẫu và cùng holdout 500 mẫu, với random_state=42. Lần 3 đạt F1 lớp dương cao nhất (0,7149), vượt ngưỡng 0,65; lần 2 chỉ đạt 0,6051. Accuracy cao nhất thuộc lần 1 (0,8780), cho thấy tối ưu accuracy không đồng nghĩa tối ưu F1. Giảm learning_rate thường cần tăng số cây; tuy nhiên ba cấu hình đồng thời thay đổi độ sâu nên chưa cô lập tác động từng tham số. Tại Bước 1, model, report và params khớp lần 3; sau Bước 3, model/report cục bộ được đồng bộ từ artifact CI mới.

---

## 2. Vì Sao Ngưỡng Chất Lượng Đặt Trên F1 Chứ Không Phải Accuracy

Lớp thu nhập trên 50K chiếm 24,77% dữ liệu Bước 2 và 24,8% holdout. Luôn dự đoán thu nhập thấp vẫn đạt accuracy 75,2%, nhưng bỏ sót toàn bộ lớp dương. F1 lớp dương kết hợp precision và recall, cân bằng báo nhầm và bỏ sót. Quality Gate yêu cầu F1 ít nhất 0,65 trước khi upload model current và restart API. Mã gọi f1_score(y_eval, preds) theo mặc định binary. Weighted F1 chịu ảnh hưởng của lớp đa số; macro F1 trung bình hai lớp nên không trực tiếp đo lớp dương. Các lần chạy dùng cùng holdout để so sánh.

---

## 3. Khó Khăn Gặp Phải và Cách Giải Quyết

| Khó khăn | Nguyên nhân | Cách giải quyết |
|---|---|---|
| MLflow không khởi động được. | SQLAlchemy 2.1 bỏ pool class mà MLflow 2.13 dùng. | Giới hạn SQLAlchemy dưới 2.1 và chạy lại. |
| Dữ liệu S3 bị từ chối truy cập. | User AWS ban đầu chưa có quyền với bucket lab. | Dùng role thiết lập và IAM user riêng, giới hạn đúng bucket/prefix. |
| EC2 từ chối t3.micro. | Subnet ban đầu ở us-east-1e không hỗ trợ loại máy này. | Lọc subnet theo API InstanceTypeOfferings trước khi tạo VM. |

---

## 4. So Sánh Bước 2 và Bước 3 (bắt buộc, 2 - 3 câu)

| | f1_score | accuracy |
|---|---|---|
| Bước 2 (22.361 mẫu) | 0.7149 | 0.8740 |
| Bước 3 (44.722 mẫu) | 0.7354 | 0.8820 |

**Nhận xét:** F1 tăng 0.0205 điểm, accuracy tăng 0.0080 điểm. Hai batch cùng phân phối nên thêm mẫu không bảo đảm cải thiện mạnh. Commit dữ liệu đã tự kích hoạt bốn jobs và cập nhật model trên EC2.
