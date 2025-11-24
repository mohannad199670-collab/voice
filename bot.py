import os
import re
import telebot
import requests
import yt_dlp

# ------------------------------------
# قراءة المتغيرات من Koyeb
# ------------------------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")

if not TELEGRAM_TOKEN or not ASSEMBLYAI_API_KEY:
    raise RuntimeError("يجب ضبط TELEGRAM_TOKEN و ASSEMBLYAI_API_KEY في إعدادات Koyeb")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# رسالة ترحيب
WELCOME = (
    "👋✨ أهلاً وسهلاً بك في *بوت التفريغ الصوتي الاحترافي*!\n\n"
    "🎙️ *المميزات:*\n"
    "1️⃣ تفريغ الرسائل الصوتية والمقاطع (يدعم العربية)\n"
    "2️⃣ تفريغ الصوت من يوتيوب 🎥 — بدون أي ملفات\n\n"
    "🔧 اختر من الأزرار بالأسفل أو أرسل صوتاً مباشرة."
)

# /start
@bot.message_handler(commands=["start"])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🎧 تفريغ صوت", "🎥 تفريغ يوتيوب")

    bot.send_message(
        message.chat.id,
        WELCOME,
        reply_markup=markup,
        parse_mode="Markdown"
    )

# ------------------------------------
#  دالة تفريغ الصوت عبر AssemblyAI
# ------------------------------------
def transcribe_audio_bytes(audio_bytes):
    # رفع الملف
    upload = requests.post(
        "https://api.assemblyai.com/v2/upload",
        headers={"authorization": ASSEMBLYAI_API_KEY},
        data=audio_bytes
    )
    upload.raise_for_status()
    audio_url = upload.json()["upload_url"]

    # إنشاء مهمة تفريغ
    transcript = requests.post(
        "https://api.assemblyai.com/v2/transcript",
        headers={
            "authorization": ASSEMBLYAI_API_KEY,
            "content-type": "application/json"
        },
        json={
            "audio_url": audio_url,
            "language_detection": True
        }
    )

    transcript.raise_for_status()
    tid = transcript.json()["id"]

    # انتظار النتيجة
    while True:
        status = requests.get(
            f"https://api.assemblyai.com/v2/transcript/{tid}",
            headers={"authorization": ASSEMBLYAI_API_KEY}
        )
        status.raise_for_status()
        data = status.json()

        if data["status"] == "completed":
            return data.get("text", "")

        if data["status"] == "error":
            return None

# ------------------------------------
#  زر تفريغ صوت
# ------------------------------------
@bot.message_handler(func=lambda m: m.text == "🎧 تفريغ صوت")
def ask_voice(message):
    bot.reply_to(message, "🎤 أرسل الآن المقطع الصوتي أو الرسالة الصوتية.")

# ------------------------------------
#  معالجة المقاطع الصوتية
# ------------------------------------
@bot.message_handler(content_types=['voice', 'audio'])
def handle_voice(message):
    bot.reply_to(message, "⏳ جاري معالجة الصوت…")

    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file_info = bot.get_file(file_id)
    url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_info.file_path}"

    audio_bytes = requests.get(url).content

    text = transcribe_audio_bytes(audio_bytes)

    if not text:
        bot.reply_to(message, "❌ حدث خطأ أثناء التفريغ.")
        return

    bot.reply_to(
        message,
        f"🎙 *مقطع صوتي*\n\n📝 النص المستخرج:\n{text}",
        parse_mode="Markdown"
    )

# ------------------------------------
#  دالة تفريغ يوتيوب بدون ملفات
# ------------------------------------
def process_youtube_url(message):
    url = message.text.strip()

    bot.reply_to(message, "⏳ جاري تحميل الصوت من يوتيوب…")

    try:
        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "noplaylist": True
        }

        # استخراج معلومات الصوت بدون تنزيل
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        # رابط مباشر لمسار الصوت
        audio_url = info.get("url")
        if not audio_url:
            bot.reply_to(message, "❌ لم أستطع الحصول على رابط الصوت.")
            return

        # تحميل الصوت مباشرة في الذاكرة
        audio_bytes = requests.get(audio_url).content

        # تفريغ النص
        text = transcribe_audio_bytes(audio_bytes)

        if not text:
            bot.reply_to(message, "❌ حدث خطأ أثناء التفريغ.")
            return

        bot.reply_to(
            message,
            f"🎥 *تفريغ يوتيوب*\n\n📝 النص المستخرج:\n{text}",
            parse_mode="Markdown"
        )

    except Exception as e:
        print("YouTube Error:", e)
        bot.reply_to(message, "❌ لم أستطع معالجة رابط اليوتيوب. تأكد من أنه صحيح.")

# استقبال روابط يوتيوب مباشرة
@bot.message_handler(regexp=r"(youtube\.com|youtu\.be)")
def direct_youtube(message):
    process_youtube_url(message)

# زر تفريغ يوتيوب
@bot.message_handler(func=lambda m: m.text == "🎥 تفريغ يوتيوب")
def ask_youtube(message):
    msg = bot.reply_to(message, "🔗 أرسل رابط فيديو من يوتيوب:")
    bot.register_next_step_handler(msg, process_youtube_url)

# ------------------------------------
# تشغيل البوت
# ------------------------------------
bot.infinity_polling()
