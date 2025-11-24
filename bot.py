import os
import telebot
import requests
import time
import yt_dlp

# ===========================
# قراءة المتغيرات من Koyeb
# ===========================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

HEADERS = {
    "authorization": ASSEMBLYAI_API_KEY,
    "content-type": "application/json"
}

# ===========================
# تنزيل صوت يوتيوب
# ===========================
def download_youtube_audio(url):
    try:
        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "outtmpl": "audio.%(ext)s"
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        return filename
    except:
        return None


# ===========================
# رفع ملف الصوت إلى AssemblyAI
# ===========================
def upload_to_assemblyai(filename):
    with open(filename, "rb") as f:
        audio_data = f.read()

    upload = requests.post(
        "https://api.assemblyai.com/v2/upload",
        headers={"authorization": ASSEMBLYAI_API_KEY},
        data=audio_data
    )

    if upload.status_code == 200:
        return upload.json()["upload_url"]

    return None


# ===========================
# طلب التفريغ
# ===========================
def transcribe_audio(audio_url):
    data = {
        "audio_url": audio_url,
        "language_detection": True
    }

    res = requests.post(
        "https://api.assemblyai.com/v2/transcript",
        headers=HEADERS,
        json=data
    )

    transcript_id = res.json()["id"]

    status = "queued"
    while status not in ["completed", "error"]:
        time.sleep(2)
        result = requests.get(
            f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
            headers=HEADERS
        ).json()
        status = result["status"]

    return result


# ===========================
# تلخيص النص
# ===========================
def summarize_text(text):
    data = {
        "text": text,
        "summarization_model": "informative",
        "max_output_size": 200
    }
    res = requests.post("https://api.assemblyai.com/v2/summarize",
                        json=data, headers=HEADERS).json()

    return res.get("summary", "❌ لم يتم إنشاء الملخص")


# ===========================
# استقبال رابط اليوتيوب
# ===========================
@bot.message_handler(func=lambda m: True)
def handle_message(message):
    text = message.text

    # هل هو رابط يوتيوب؟
    if text and ("youtube.com" in text or "youtu.be" in text):
        bot.reply_to(message, "🎧 جاري تنزيل الصوت من اليوتيوب…")

        filename = download_youtube_audio(text)
        if not filename:
            bot.reply_to(message, "❌ لم أستطع تنزيل الصوت من اليوتيوب")
            return

        bot.reply_to(message, "📤 جاري رفع الصوت لـ AssemblyAI…")

        audio_url = upload_to_assemblyai(filename)
        if not audio_url:
            bot.reply_to(message, "❌ فشل رفع الملف")
            return

        bot.reply_to(message, "⏳ جاري التفريغ…")

        result = transcribe_audio(audio_url)
        if result["status"] == "error":
            bot.reply_to(message, "❌ حدث خطأ أثناء التفريغ")
            return

        full_text = result["text"]

        bot.send_message(message.chat.id, f"📝 النص الكامل:\n\n{full_text}")

        summary = summarize_text(full_text)
        bot.send_message(message.chat.id, f"✨ الملخص:\n\n{summary}")

        return

    # أي رسالة عادية
    bot.reply_to(message, "أرسل رابط يوتيوب للتفريغ.")


# ===========================
# تشغيل البوت
# ===========================
bot.infinity_polling()
