# 📚 LEGAL RAG CHATBOT (AI TƯ VẤN PHÁP LUẬT)

Dự án RAG (Retrieval-Augmented Generation) xây dựng Chatbot tư vấn Pháp lý Việt Nam, có khả năng tra cứu, giải đáp pháp luật và **Khai phá Xung đột Pháp lệnh** (Conflict Analysis) chuyên sâu dựa trên nguyên tắc *Lex Superior* & *Lex Posterior*.

---

## 🛠️ HƯỚNG DẪN CÀI ĐẶT VÀ CHẠY DỰ ÁN TRÊN MÁY LOCAL KHÔNG DÙNG DOCKER (WINDDOWS/MAC/LINUX)

**Yêu cầu môi trường:**
- Python 3.10 trở lên.
- Node.js (v18+) để chạy Frontend.

### BƯỚC 1: ĐỒNG BỘ DỮ LIỆU BỘ NHỚ (DATA)
Do CSDL Data Pháp luật quá lớn nên không lưu trữ trên Github. Bạn sẽ nhận được thư mục `data` gửi kèm bên ngoài.
1. Giải nén thư mục `data`.
2. Đặt thư mục `data` vào **NẰM NGAY MẶT NGOÀI CÙNG** của thư mục dự án (Ngang hàng với file `api.py`).
*Ví dụ: `icomm_legal_chat/data/legal_chunks.parquet`*

### BƯỚC 2: KHỞI ĐỘNG MÁY CHỦ BACKEND (AI ENGINE & FASTAPI)
Mở Terminal ở thư mục gốc của dự án (`icomm_legal_chat`).

**Nếu bạn dùng Windows (PowerShell):**
Chỉ cần chạy 2 file Script tiện lượng đã được viết sẵn:
```powershell
# 1. Cài đặt môi trường ảo và tải thư viện tự động
.\setup.ps1

# 2. Bật máy chủ API (Mặc định Port 8000)
.\run_api.ps1
```

**Nếu bạn dùng Mac/Linux (Hoặc gõ tay):**
```bash
# Tạo môi trường và cài cắm (Cài bản CPU hoặc GPU tùy máy)
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Chạy Server
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```
*Lưu ý: Quá trình bật Backend lần đầu tiên có thể tốn vài chục giây để Model HuggingFace tự động tải tệp tin Cache (Qwen 0.5B và MiniLM) vào bộ nhớ.*

### BƯỚC 3: KHỞI ĐỘNG GIAO DIỆN FRONTEND (VITE/REACT)
Mở một Tab Terminal thứ 2 (Để song song với cái Backend đang bật). Di chuyển vào thư mục `frontend`:
```bash
cd frontend

# Cài đặt thư viện lõi của React
npm install

# Bật giao diện (Mặc định ở Port 5173 hoặc 3000)
npm run dev
```

**👉 Hoàn tất! Bạn truy cập vào `http://localhost:5173` trên trình duyệt để trải nghiệm Bot!**

---

## 🚀 HƯỚNG DẪN CHẠY BẰNG DOCKER (PRODUCTION READY)

Nếu máy Server của bạn môi trường chuẩn hóa, bạn không cần chạy lệnh lẻ tẻ. Dự án đã cung cấp sẵn hệ thống Docker Compose:

**▶ Chạy phiên bản CPU thông thường:**
```bash
docker-compose up --build -d
```

**▶ Chạy phiên bản tận dụng GPU NVIDIA (Mượt nhất):**
Đảm bảo máy chủ (Host) đã cài `nvidia-container-toolkit`. Sau đó gõ:
```bash
docker compose -f docker-compose.gpu.yml up -d --build
```
Hệ thống Frontend sẽ hiển thị sẵn sàng ở cổng `http://localhost:3000`.

---

## 📌 TÍNH NĂNG ĐẶC BIỆT CẦN ĐÁNH GIÁ (TESTING GUIDE)

Khi duyệt Code, xin lưu ý dự án áp dụng **Cấu trúc RAG 3 Lớp Tiên tiến**:
1. Khăc phục "Fragmented Chunking": Backend có ngầm sử dụng hàm `_collect_related_chunks` tự động rà quét các Khoản/Điểm lân cận nếu Vector chỉ bắt trúng 1 Điều duy nhất để tăng ngữ cảnh Luật.
2. Quét Vector Đa Chiều với **MMR (Maximal Marginal Relevance)**.
3. Giải quyết Xung đột Pháp Lệnh (Conflict Analysis): LLM được tiêm cấu trúc rà soát đối chiếu bằng Nguyên tắc Thuộc Hệ (Luật > Nghị định) thay vì đọ chữ thô thông thường. 
4. Hệ thống nhận diện File PDF tự động kích hoạt **Tesseract OCR OCR-Vie** làm phương án cứu cánh nều phát hiện đây là PDF Scan rỗng.
