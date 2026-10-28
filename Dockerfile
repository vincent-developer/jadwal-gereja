FROM python:3.11-alpine

# Set working directory
WORKDIR /usr/src/app

# (Opsional) Install bash atau timezone jika script butuh waktu lokal yang presisi
RUN apk add --no-cache tzdata
ENV TZ=Asia/Jakarta

# Copy file requirements (jika ada) dan install
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy seluruh script Python
COPY . .

# Copy file crontab ke tempat yang dibaca oleh sistem Alpine
COPY crontab /etc/crontabs/root

# Berikan hak akses eksekusi ke script (opsional tapi disarankan)
RUN chmod +x scripts/generate_organist_schedule.py

# Jalankan daemon cron di foreground (-f) dengan log level 8 (-d 8)
CMD ["crond", "-f", "-d", "8"]