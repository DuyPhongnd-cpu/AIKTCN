FROM python:3.11-slim
WORKDIR /app

# Cài đặt thư viện hệ thống cần thiết cho PostgreSQL & build
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5050

# Chạy Gunicorn chuẩn Enterprise ổn định không bao giờ sập
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5050", "--timeout", "180", "app:app"]
