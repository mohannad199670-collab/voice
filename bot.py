import os
import telebot
import requests
import yt_dlp
from io import BytesIO

# ============================
# متغيرات البيئة
# ============================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")

if not TELEGRAM_TOKEN or not ASSEMBLYAI_API_KEY:
    raise RuntimeError("يجب ضبط TELEGRAM_TOKEN و ASSEMBLYAI_API_KEY في Koyeb")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ============================
# رسالة ترحيب
# ============================
WELCOME = (
    "👋 أهلاً بك في بوت التفريغ الصوتي!\n\n"
    "🎧 المميزات:\n"
    "• تفريغ الصوت من تيليجرام\n"
    "• تفريغ الصوت من روابط يوتيوب\n"
    "• يدعم العربية تلقائياً\n\n"
    "🎤 أرسل مقطع صوتي أو رابط يوتيوب للبدء."
)

@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(message.chat.id, WELCOME, parse_mode="Markdown")

# ============================
# رفع الصوت إلى AssemblyAI
# ============================
def transcribe_audio_bytes(audio_bytes):
    # رفع الملف
    upload = requests.post(
        "https://api.assemblyai.com/v2/upload",
        headers={"authorization": ASSEMBLYAI_API_KEY},
        data=audio_bytes
    )
    upload.raise_for_status()

    audio_url = upload.json()["upload_url"]

    # إنشاء مهمة التفريغ
    task = requests.post(
        "https://api.assemblyai.com/v2/transcript",
        headers={"authorization": ASSEMBLYAI_API_KEY, "content-type": "application/json"},
        json={"audio_url": audio_url, "language_detection": True}
    )
    task.raise_for_status()
    transcript_id = task.json()["id"]

    # انتظار النتيجة
    while True:
        status = requests.get(
            f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
            headers={"authorization": ASSEMBLYAI_API_KEY}
        ).json()

        if status["status"] == "completed":
            return status.get("text", "")

        if status["status"] == "error":
            return None

# ============================
# تفريغ الصوت من تيليجرام
# ============================
@bot.message_handler(content_types=["voice", "audio"])
def tg_voice(message):
    bot.reply_to(message, "⏳ جاري معالجة الصوت…")

    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file_info = bot.get_file(file_id)
    url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_info.file_path}"

    audio_bytes = requests.get(url).content
    text = transcribe_audio_bytes(audio_bytes)

    if not text:
        bot.reply_to(message, "❌ حدث خطأ أثناء التفريغ.")
        return

    bot.reply_to(message, f"📝 *النص المستخرج:* \n{text}", parse_mode="Markdown")

# ============================
# تفريغ صوت يوتيوب (بدون ملفات)
# ============================
def process_youtube(message):
    link = message.text.strip()
    bot.reply_to(message, "🎥 جاري تحميل الصوت من يوتيوب…")

    try:
        # تخزين الصوت داخل الذاكرة بدون ملفات
        buffer = BytesIO()

        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "noplaylist": True,
            "outtmpl": "-",  # مهم جداً (لا ملفات)
            "logtostderr": False,
            "nopart": True,
            "nocheckcertificate": True,
            "forcejson": False,
            "extract_flat": False,
            "audioformat": "mp3",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192"
            }],
            "progress_hooks": [
                lambda d: buffer.write(
                    open(d["filename"], "rb").read()
                ) if d.get("status") == "finished" else None
            ]
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([link])

        audio_bytes = buffer.getvalue()
        if not audio_bytes:
            bot.reply_to(message, "❌ لم أستطع الحصول على الصوت من يوتيوب.")
            return

        bot.reply_to(message, "⏳ جاري التفريغ…")

        text = transcribe_audio_bytes(audio_bytes)
        if not text:
            bot.reply_to(message, "❌ حدث خطأ أثناء تفريغ رابط اليوتيوب.")
            return

        bot.reply_to(message, f"📝 *النص المستخرج:* \n{text}", parse_mode="Markdown")

    except Exception as e:
        print("YouTube ERROR:", e)
        bot.reply_to(message, "❌ لم أستطع معالجة رابط اليوتيوب. تأكد أن الرابط صحيح.")

# استقبال روابط يوتيوب
@bot.message_handler(regexp=r"(youtu\.be|youtube\.com)")
def yt_handler(message):
    process_youtube(message)

# ============================
# تشغيل البوت
# ============================
bot.infinity_polling()
