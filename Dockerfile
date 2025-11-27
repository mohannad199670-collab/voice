# نستخدم نسخة بايثون 3.11 لأنها مستقرة وتدعم مكتبات الصوت بدون مشاكل
FROM python:3.11-slim

# تحديث النظام وتثبيت ffmpeg الضروري
RUN apt-get update && \
    apt-get install -y ffmpeg git && \
    rm -rf /var/lib/apt/lists/*

# إعداد مجلد العمل داخل السيرفر
WORKDIR /app

# نسخ ملف المتطلبات وتثبيتها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات البوت
COPY . .

# أمر تشغيل البوت (تأكد أن اسم ملفك bot.py)
CMD ["python", "bot.py"]
