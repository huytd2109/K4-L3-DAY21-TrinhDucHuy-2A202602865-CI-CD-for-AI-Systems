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

Repository variable `SERVER_HOST_FINGERPRINT` lưu fingerprint SHA256 public host key EC2 để kiểm tra máy chủ SSH.

## Lệnh trên PowerShell

Chỉ chạy bootstrap sau khi phạm vi cloud đã được chấp thuận:

```powershell
$env:AWS_PROFILE = 'lab16'
$env:AWS_DEFAULT_REGION = 'us-east-1'
.\.venv311\Scripts\python.exe scripts/bootstrap_aws.py
.\.venv311\Scripts\python.exe -m pytest tests/ -v
```

DVC remote `labstore` dùng `s3://income-lab-day21-026343683449/dvc`, region us-east-1; credential cấu hình cục bộ, không commit access key. Chỉ commit ba con trỏ *.csv.dvc, .dvc/config và mã bài.

## Chi phí và bằng chứng

EC2, EBS, IPv4 công khai và S3 có thể phát sinh phí theo mức dùng/điều kiện tài khoản. Sau demo cần kiểm tra các tài nguyên còn chạy; dừng EC2 vẫn có thể còn chi phí lưu EBS. Giá hiện hành: https://aws.amazon.com/ec2/pricing/on-demand/ và https://aws.amazon.com/s3/pricing/.

Chỉ kết luận CP2 hoàn thành sau khi có run GitHub Actions đủ bốn jobs xanh, /healthz và /score trên IP EC2 trả kết quả thật, và dữ liệu DVC/model hiện trong S3. Kiểm thử cục bộ mô phỏng truyền file S3 không thay thế bằng chứng triển khai cloud.
