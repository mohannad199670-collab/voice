# نستخدم نسخة بايثون 3.11 لأنها مستقرة وفيها مكتبة الصوت جاهزة
FROM python:3.11-slim

# تنزيل تحديثات النظام وتثبيت FFmpeg الضروري جداً
RUN apt-get update && \
    apt-get install -y ffmpeg git && \
    rm -rf /var/lib/apt/lists/*

# تجهيز مجلد العمل
WORKDIR /app

# نسخ ملفات المكتبات وتثبيتها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات البوت
COPY . .

# أمر تشغيل البوت (تأكد ان اسم ملفك bot.py)
CMD ["python", "bot.py"]
