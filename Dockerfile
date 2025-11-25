FROM python:3.10-slim

# تثبيت ffmpeg
RUN apt-get update && apt-get install -y ffmpeg

# إعداد مجلد التطبيق
WORKDIR /app

# نقل الملفات
COPY . /app

# تثبيت المتطلبات
RUN pip install --no-cache-dir -r requirements.txt

# تشغيل البوت
CMD ["python", "bot.py"]
