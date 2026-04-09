# Hướng dẫn Triển khai CITMS v3.6 trên Ubuntu 24.04 (Local Machine)

Tài liệu này hướng dẫn chi tiết các bước để thiết lập môi trường phát triển và chạy thử nghiệm hệ thống **CITMS v3.6** trên máy chủ hoặc máy tính cá nhân chạy **Ubuntu 24.04 LTS**.

---

## 1. Giới thiệu
- **Mục đích:** Thiết lập nhanh môi trường CITMS 3.6 để phát triển, kiểm thử tính năng hoặc demo.
- **Yêu cầu phần cứng tối thiểu:**
  - CPU: 2 Cores (Khuyên dùng 4 Cores)
  - RAM: 4GB (Khuyên dùng 8GB để chạy mượt cả Frontend và Backend)
  - Disk: 10GB trống.
- **Thời gian ước tính:** 15 - 20 phút.

---

## 2. Chuẩn bị hệ thống Ubuntu 24.04

Trước khi bắt đầu, hãy đảm bảo hệ thống của bạn đã được cập nhật các gói mới nhất.

```bash
# Cập nhật danh sách gói và nâng cấp hệ thống
sudo apt update && sudo apt upgrade -y

# Cài đặt các công cụ cơ bản
sudo apt install -y curl git build-essential libpq-dev
```

---

## 3. Cài đặt Docker & Docker Compose

Ubuntu 24.04 hỗ trợ Docker qua các repository chính thức. Chúng ta sẽ cài đặt bản Docker Engine mới nhất.

### 3.1 Cài đặt Docker
```bash
# Thêm khóa GPG chính thức của Docker
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Thêm repository vào nguồn Apt
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update

# Cài đặt Docker và các plugin cần thiết
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### 3.2 Cấu hình quyền người dùng (Quan trọng)
Thêm người dùng hiện tại vào nhóm `docker` để có thể chạy lệnh mà không cần `sudo`.

```bash
sudo usermod -aG docker $USER
# LƯU Ý: Bạn cần đăng xuất và đăng nhập lại hoặc restart máy để thay đổi này có hiệu lực.
# Hoặc chạy lệnh sau để áp dụng ngay:
newgrp docker
```

---

## 4. Tải mã nguồn dự án

```bash
cd ~
git clone <URL_KHO_MA_NGUON_CUA_BAN> citms-project
cd citms-project
```

---

## 5. Cấu hình file .env

Sử dụng tệp mẫu để tạo cấu hình môi trường cục bộ.

```bash
cp .env.example .env
```

Mở tệp `.env` bằng `nano` hoặc `vim` để kiểm tra các thông số:
```bash
nano .env
```

**Các biến quan trọng cần chú ý:**
- `POSTGRES_DB=citms_db`
- `DATABASE_URL=postgresql+asyncpg://citms_user:citms_password@db:5432/citms_db`
- `REDIS_URL=redis://redis:6379/0`
- `S3_ENDPOINT=http://minio:9000` (Sử dụng tên service Docker bên trong mạng nội bộ)

---

## 6. Khởi chạy hệ bằng Docker Compose

Hệ thống CITMS v3.6 sử dụng Docker Compose để điều phối 7 dịch vụ chính.

```bash
# Khởi chạy toàn bộ hệ thống ở chế độ chạy ngầm
docker compose up -d --build
```

**Thứ tự khởi động tự động:**
1. `db`: Cơ sở dữ liệu Postgres (kèm extension pg_cron).
2. `redis`: Bộ nhớ đệm và Message Broker.
3. `minio`: Lưu trữ đối tượng (S3 compatible).
4. `api`: Backend FastAPI (Chỉ chạy khi db và redis đã sẵn sàng).
5. `worker` & `beat`: Xử lý tác vụ nền Celery.
6. `event_consumer`: Xử lý sự kiện thời gian thực.

---

## 7. Khởi tạo Database & Dữ liệu

Sau khi các container đã chạy (trạng thái `Up`), chúng ta cần khởi tạo bảng và dữ liệu mẫu.

### 7.1 Chạy Migration (Alembic)
Lệnh này sẽ tạo cấu trúc bảng và bật các extension cần thiết như `uuid-ossp` và `pg_cron`.

```bash
docker exec -it citms_api alembic upgrade head
```

### 7.2 Nạp dữ liệu mẫu (Seed Data)
Nạp các quyền, vai trò (Roles/Permissions) và phòng ban mặc định.

```bash
docker exec -it citms_api python backend/scripts/seed_initial_data.py
```

### 7.3 Tạo tài khoản Super Admin đầu tiên
Thay đổi email và password theo ý muốn của bạn.

```bash
docker exec -it citms_api python backend/scripts/create_super_admin.py \
    --email admin@local.com \
    --password admin123 \
    --username admin \
    --name "Quản trị viên hệ thống"
```

---

## 8. Chạy Frontend (React PWA)

Để phục vụ việc phát triển và debug nhanh nhất, hãy chạy Frontend trực tiếp trên máy host.

```bash
# Cài đặt Node.js 20 (nếu chưa có)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Cài đặt thư viện và chạy dev server
cd ~/citms-project/frontend
npm install
npm run dev
```

---

## 9. Kiểm tra hệ thống sau khi triển khai

Mở trình duyệt và truy cập các địa chỉ sau:

- **Giao diện người dùng:** [http://localhost:5173](http://localhost:5173)
- **Tài liệu API (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Quản trị MinIO (Storage):** [http://localhost:9001](http://localhost:9001)

> **Mẹo test nhanh:** Đăng nhập bẳng `admin@local.com` / `admin123`. Sau đó vào mục **Inventory** để thử Import dữ liệu hoặc vào **Reports** để xem các biểu đồ Materialized View đã được load chưa.

---

## 10. Các lệnh hữu ích khi vận hành

| Lệnh | Mục đích |
| :--- | :--- |
| `docker compose ps` | Kiểm tra trạng thái các container. |
| `docker compose logs -f api` | Xem log trực tiếp của Backend. |
| `docker compose restart api` | Khởi động lại dịch vụ Backend. |
| `docker compose down` | Dừng và xóa các container (giữ lại dữ liệu). |
| `docker compose down -v` | Xóa sạch hệ thống kèm theo toàn bộ dữ liệu database. |

---

## 11. Troubleshooting phổ biến trên Ubuntu 24.04

1. **Lỗi Port 5432 bị chiếm:**
   - Ubuntu có thể tự cài Postgres khi setup. Chạy `sudo systemctl stop postgresql` để giải phóng cổng.
2. **Lỗi Firewall (UFW):**
   - Nếu không truy cập được từ máy khác, hãy mở port: `sudo ufw allow 8000/tcp` và `sudo ufw allow 5173/tcp`.
3. **Lỗi `pg_cron` không hoạt động:**
   - Kiểm tra log của container db: `docker logs citms_db`. Đảm bảo file `Dockerfile.db` đã được build thành công.

---

## 12. Post-Deployment Checklist
- [ ] Truy cập được vào Dashboard.
- [ ] Đăng nhập thành công với tài khoản Super Admin.
- [ ] Upload thử 1 file ảnh (để test kết nối MinIO).
- [ ] Kiểm tra bảng `audit_logs` có dữ liệu khi thực hiện thao tác (test GIN Index).

---
**Status:** CITMS v3.6 Stable Deployment Guide for Ubuntu 24.04
**Tác giả:** Antigravity Solution Architect
