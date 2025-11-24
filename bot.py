import os
import telebot
import requests
import yt_dlp
from io import BytesIO

# ============================
# متغيرات البيئة
# ============================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GLADIA_API_KEY = os.getenv("GLADIA_API_KEY")

if not TELEGRAM_TOKEN or not GLADIA_API_KEY:
    raise RuntimeError("يجب ضبط TELEGRAM_TOKEN و GLADIA_API_KEY داخل Koyeb")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ============================
# رسالة الترحيب
# ============================
WELCOME = (
    "👋 أهلاً بك في بوت التفريغ الصوتي (Gladia)!\n\n"
    "🎧 المميزات:\n"
    "• تفريغ الصوت من تيليجرام\n"
    "• تفريغ الصوت من روابط يوتيوب\n"
    "• يدعم العربية تلقائياً\n\n"
    "🎤 أرسل صوتاً أو رابط يوتيوب الآن."
)

@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(message.chat.id, WELCOME, parse_mode="Markdown")


# ============================
# رفع الصوت إلى Gladia
# ============================
def transcribe_gladia(audio_bytes):
    files = {
        "audio": ("audio.mp3", audio_bytes, "audio/mpeg")
    }
    headers = {
        "x-gladia-key": GLADIA_API_KEY
    }
    data = {
        "language_behaviour": "automatic single language",   # يكتشف العربية تلقائياً
        "output_format": "json",
        "enable_noise_reduction": True
    }

    response = requests.post(
        "https://api.gladia.io/audio/text/audio-transcription",
        headers=headers,
        files=files,
        data=data
    )

    try:
        result = response.json()
        text = result["result"]["transcription"]
        return text

    except Exception:
        return None


# ============================
# تفريغ صوت تيليجرام
# ============================
@bot.message_handler(content_types=["voice", "audio"])
def tg_voice(message):
    bot.reply_to(message, "⏳ جاري معالجة الصوت…")

    file_id = message.voice.file_id if message.voice else message.audio.file_id
    info = bot.get_file(file_id)
    file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{info.file_path}"

    audio_bytes = requests.get(file_url).content
    text = transcribe_gladia(audio_bytes)

    if not text:
        bot.reply_to(message, "❌ حدث خطأ أثناء التفريغ.")
        return

    bot.reply_to(message, f"📝 *النص المستخرج:* \n{text}", parse_mode="Markdown")


# ============================
# تفريغ رابط يوتيوب (بدون ملفات)
# ============================
def process_youtube(message):
    url = message.text.strip()
    bot.reply_to(message, "🎥 جاري استخراج الصوت من يوتيوب…")

    try:
        buffer = BytesIO()

        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "noplaylist": True,
            "outtmpl": "-",  # مهم (لا ملفات)
            "forcejson": False,
            "nocheckcertificate": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192"
            }],
            "progress_hooks": [
                lambda d: buffer.write(open(d["filename"], "rb").read())
                if d.get("status") == "finished" else None
            ]
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        audio_bytes = buffer.getvalue()

        if not audio_bytes:
            bot.reply_to(message, "❌ لم أستطع استخراج الصوت من يوتيوب.")
            return

        bot.reply_to(message, "⏳ جاري التفريغ…")

        text = transcribe_gladia(audio_bytes)

        if not text:
            bot.reply_to(message, "❌ حدث خطأ أثناء التفريغ من Gladia.")
            return

        bot.reply_to(message, f"📝 *النص المستخرج:* \n{text}", parse_mode="Markdown")

    except Exception as e:
        print("YouTube ERROR:", e)
        bot.reply_to(message, "❌ لم أستطع معالجة رابط اليوتيوب. جرب رابطاً آخر.")


# استقبال روابط يوتيوب مباشرة
@bot.message_handler(regexp=r"(youtu\.be|youtube\.com)")
def yt_handler(message):
    process_youtube(message)

# ============================
# تشغيل البوت
# ============================
bot.infinity_polling()
