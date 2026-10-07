# CP2 trên AWS

Cloud đích: account 026343683449, region us-east-1. Bucket: `income-lab-day21-026343683449`.

## Thành phần

- `scripts/bootstrap_aws.py` tạo tài nguyên riêng có tag Project=income-lab-day21. Script yêu cầu profile `lab16`; kiểm tra account trước khi chạy.
- `deploy/aws/setup-policy.json` chỉ cho thiết lập và truy cập bucket của lab. Policy được sinh bằng IAM Policy Autopilot, sau đó bỏ các quyền KMS, access point, Object Lambda, ACL và Object Lock không dùng.
- `deploy/aws/actions-policy.json` giới hạn GitHub Actions vào dữ liệu DVC và model current trong cùng bucket.
- `deploy/aws/serve-policy.json` chỉ cho EC2 đọc `artifacts/current/model.joblib`. Boto3 dùng instance role, không cần lưu access key trên VM.
- Bucket bật Block Public Access, SSE-S3 và từ chối HTTP. VM dùng IMDSv2, EBS gp3 12 GB mã hóa và CPU credits standard.
- TCP 22 mở cho SSH từ GitHub-hosted runners; TCP 8080 phục vụ API mẫu công khai theo yêu cầu lab. Private key và credential của lab chỉ lưu trong thư mục Git-ignored `.local-cp2/` và GitHub Secrets.

## GitHub Actions

Chuỗi dependency: Unit Test → Train → Quality Gate → Release. Train lưu model dưới dạng GitHub artifact; Release chỉ upload model vào S3 sau khi F1 hữu hạn và thuộc [0.65, 1.0]. Vì vậy F1 thấp không thay thế model current. Release cập nhật serve.py, cài đúng phiên bản runtime, restart systemd và thử /healthz tối đa 12 lần.

Năm repository secrets:

| Secret | Nội dung |
|---|---|
| STORAGE_CREDENTIALS | JSON credential của IAM user riêng cho lab: aws_access_key_id, aws_secret_access_key; có thể thêm aws_session_token |
| ARTIFACT_BUCKET | income-lab-day21-026343683449 |
| SERVER_HOST | IPv4 công khai của EC2 mới |
| SERVER_USER | ubuntu |
| SERVER_SSH_KEY | Private key SSH riêng của lab |

Repository variable `SERVER_HOST_FINGERPRINT` lưu fingerprint SHA256 của host key ECDSA EC2 để khớp thuật toán mà appleboy SCP/SSH chọn. Fingerprint được lấy qua kết nối Ed25519 đã đối chiếu với EC2 console output; không tắt kiểm tra host key.

## Lệnh trên PowerShell

Chỉ chạy bootstrap sau khi phạm vi cloud đã được chấp thuận:

```powershell
$env:AWS_PROFILE = 'lab16'
$env:AWS_DEFAULT_REGION = 'us-east-1'
.\.venv311\Scripts\python.exe scripts/bootstrap_aws.py
.\.venv311\Scripts\python.exe -m pytest tests/ -v

# Credential của IAM user riêng cho DVC, không dùng profile lab16 để truy cập S3.
$storage = Get-Content .local-cp2/storage-credentials.json | ConvertFrom-Json
Remove-Item Env:AWS_PROFILE -ErrorAction SilentlyContinue
$env:AWS_ACCESS_KEY_ID = $storage.aws_access_key_id
$env:AWS_SECRET_ACCESS_KEY = $storage.aws_secret_access_key
.\.venv311\Scripts\python.exe -m dvc push
```

DVC remote `labstore` dùng `s3://income-lab-day21-026343683449/dvc`, region us-east-1; credential cấu hình cục bộ, không commit access key. Chỉ commit ba con trỏ *.csv.dvc, .dvc/config và mã bài.

## Chi phí và bằng chứng

EC2, EBS, IPv4 công khai và S3 có thể phát sinh phí theo mức dùng/điều kiện tài khoản. Sau demo cần kiểm tra các tài nguyên còn chạy; dừng EC2 vẫn có thể còn chi phí lưu EBS. Giá hiện hành: https://aws.amazon.com/ec2/pricing/on-demand/ và https://aws.amazon.com/s3/pricing/.

Chỉ kết luận CP2 hoàn thành sau khi có run GitHub Actions đủ bốn jobs xanh, /healthz và /score trên IP EC2 trả kết quả thật, và dữ liệu DVC/model hiện trong S3. Kiểm thử cục bộ mô phỏng truyền file S3 không thay thế bằng chứng triển khai cloud.

## Kết quả CP2 đã kiểm tra

- EC2 `i-01406a2bbade020aa`, Ubuntu 22.04, IP `98.92.48.82`; systemd `income-api` phục vụ cổng 8080.
- [Run CP2](https://github.com/huytd2109/K4-L3-DAY21-TrinhDucHuy-2A202602865-CI-CD-for-AI-Systems/actions/runs/37574584115) có đủ bốn jobs thành công, bao gồm 9 unit tests. Artifact report: F1 binary 0.7149321267, accuracy 0.8740 trên holdout 500 mẫu.
- Gọi từ máy cục bộ: `/healthz` HTTP 200; hai mẫu `/score` trong đề trả lần lượt `thu_nhap_thap` và `thu_nhap_cao`; input thiếu đặc trưng trả HTTP 400.
- Ba object DVC và model current đã hiện trên S3 Console. Ảnh nộp bài: `02-actions-buoc-2.png`, `04-curl-api.png`, `05a-storage-dvc.png`, `05b-storage-model.png`. Ảnh 04 chụp terminal SSH thật hiển thị qua trình duyệt, với đầu ra trực tiếp từ PTY EC2.
- Private key và AWS credential nằm trong `.local-cp2/` (Git-ignored); không nằm trong commit. Public IP có thể đổi nếu dừng rồi bật EC2, khi đó cần cập nhật secret SERVER_HOST.
