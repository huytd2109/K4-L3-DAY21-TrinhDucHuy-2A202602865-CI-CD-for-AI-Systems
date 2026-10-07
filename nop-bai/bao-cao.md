# Báo Cáo Lab Day 21 - CI/CD cho AI Systems

<!--
HƯỚNG DẪN - đọc rồi XÓA TOÀN BỘ các khối chú thích này sau khi điền xong:

  - Giới hạn: KHÔNG QUÁ 1 TRANG A4, tương đương khoảng 450 - 550 từ nội dung.
  - Chỉ điền vào các chỗ ___ và các ô trong bảng. Không thêm mục mới.
  - Viết bằng câu hoàn chỉnh, không gạch đầu dòng cụt lủn.
  - Kiểm tra độ dài sau khi đã xóa hết chú thích:
        wc -w nop-bai/bao-cao.md
    và xem trước bản in bằng cách mở file trên GitHub rồi Ctrl+P / Cmd+P.
-->

| | |
|---|---|
| Họ và tên | ___ |
| MSSV | ___ |
| Lớp / Khóa | K4 |
| Repo GitHub | https://github.com/___/___ |
| Ngày nộp | ___ |

---

## 1. Bộ Siêu Tham Số Đã Chọn và Lý Do

| Lần chạy | n_estimators | learning_rate | max_depth | f1_score | accuracy |
|---|---|---|---|---|---|
| 1 | 100 | 0.1 | 3 | 0.7109 | 0.8780 |
| 2 | 50 | 0.05 | 2 | 0.6051 | 0.8460 |
| 3 | 200 | 0.1 | 5 | 0.7149 | 0.8740 |

**Bộ siêu tham số đã chọn:** `n_estimators=200`, `learning_rate=0.1`, `max_depth=5`.

**Lý do:** Cả ba thí nghiệm dùng 22.361 mẫu train_batch1 và cùng 500 mẫu holdout, với random_state=42. Lần 3 có F1 lớp dương cao nhất, đạt 0,7149 và vượt ngưỡng 0,65; lần 2 chỉ đạt 0,6051. Accuracy cao nhất thuộc lần 1 (0,8780), còn lần 3 đạt 0,8740, cho thấy tối ưu accuracy không đồng nghĩa tối ưu F1 cho lớp thu nhập cao. Cấu hình 50 cây và learning_rate=0,05 có F1 thấp hơn; giảm learning_rate thường cần tăng số cây để bù lại. Tuy nhiên, cả độ sâu cũng thay đổi nên ba lần chạy này chưa cô lập riêng tác động của từng tham số. Các model lưu trong MLflow đã được tải lại và tính lại metrics; model.joblib, report.json và params.yaml đều khớp lần 3.

---

## 2. Vì Sao Ngưỡng Chất Lượng Đặt Trên F1 Chứ Không Phải Accuracy

Lớp thu nhập trên 50K chiếm 24,77% train_batch1 và 24,8% holdout. Nếu luôn dự đoán thu nhập thấp, mô hình vẫn đạt accuracy 75,2% trên holdout nhưng bỏ sót toàn bộ lớp dương. Vì vậy accuracy có thể che lấp khả năng nhận diện nhóm thu nhập cao. F1 lớp dương kết hợp precision và recall, buộc mô hình cân bằng giữa báo nhầm và bỏ sót. Quality Gate yêu cầu F1 đạt ít nhất 0,65 trước khi Release upload model current và restart API. Mã gọi f1_score(y_eval, preds) theo mặc định binary. Weighted F1 chịu ảnh hưởng lớn của lớp đa số; macro F1 tính trung bình hai lớp và không trực tiếp trả lời lớp dương có đạt ngưỡng không. Ngưỡng được kiểm tra trên cùng holdout để so sánh các lần chạy.

<!--
Cần nêu được:
  - Phân bố lớp của tập dữ liệu (tỷ lệ lớp thu nhập > 50K) và hệ quả của nó.
  - Accuracy của một mô hình luôn trả lời "thu nhập thấp" là bao nhiêu, vì sao con số
    đó gây hiểu nhầm.
  - F1 của lớp dương đo điều gì mà accuracy không đo được.
  - Vì sao KHÔNG dùng average="weighted" hay average="macro" khi gọi f1_score.
-->

---

## 3. Khó Khăn Gặp Phải và Cách Giải Quyết

<!-- Nêu 2 - 3 khó khăn thật, mỗi ô một câu ngắn. -->

| Khó khăn | Nguyên nhân | Cách giải quyết |
|---|---|---|
| MLflow không khởi động được. | SQLAlchemy 2.1 bỏ pool class mà MLflow 2.13 dùng. | Giới hạn SQLAlchemy dưới 2.1 và chạy lại. |
| Dữ liệu S3 bị từ chối truy cập. | User AWS ban đầu chưa có quyền với bucket lab. | Dùng role thiết lập và IAM user riêng, giới hạn đúng bucket/prefix. |
| EC2 từ chối t3.micro. | Subnet ban đầu ở us-east-1e không hỗ trợ loại máy này. | Lọc subnet theo API InstanceTypeOfferings trước khi tạo VM. |

---

## 4. So Sánh Bước 2 và Bước 3 (bắt buộc, 2 - 3 câu)

<!-- Lấy số liệu từ bảng ở mục 3.6 của tasks/buoc-3.md. -->

| | f1_score | accuracy |
|---|---|---|
| Bước 2 (chỉ `train_batch1`) | ___ | ___ |
| Bước 3 (thêm `train_batch2`) | ___ | ___ |

**Nhận xét:** ___

<!--
Một câu trả lời trung thực kiểu "f1 giảm 0,01 vì dữ liệu mới cùng phân phối, không mang
thêm thông tin mới" được đánh giá cao hơn kết luận sai rằng thêm dữ liệu luôn tốt hơn.
-->

---

## 5. Phần Bonus Đã Thực Hiện (nếu có)

<!-- Xóa cả mục 5 nếu không làm bonus. Mỗi bonus tối đa 1 dòng. -->

- [ ] Bonus 1 - Tracking MLflow từ xa với DagsHub: ___
- [ ] Bonus 2 - Điều chỉnh ngưỡng quyết định: ___
- [ ] Bonus 3 - Báo cáo precision / recall tự động: ___
- [ ] Bonus 4 - Hoàn trả về phiên bản trước: ___
- [ ] Bonus 5 - Cảnh báo lệch lạc dữ liệu: ___
