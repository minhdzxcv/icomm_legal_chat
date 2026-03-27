FROM python:3.10-slim

WORKDIR /app

# Copy file yêu cầu và cài đặt
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --default-timeout=1000 --retries 20 -r requirements.txt

# Copy toàn bộ code và dữ liệu
COPY . .

# Run API by default.
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
