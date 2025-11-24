import os
import telebot
import requests
import yt_dlp

# ------------------------------------
#  قراءة المتغيرات من Koyeb
# ------------------------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ------------------------------------
#  رسالة ترحيب
# ------------------------------------
WELCOME = (
    "👋✨ أهلاً وسهلاً بك في *بوت التفريغ الصوتي الاحترافي*!\n\n"
    "🎙️ *المميزات المتاحة:*\n"
    "1️⃣ تفريغ الصوت العربي واللغات الأخرى تلقائياً\n"
    "2️⃣ تفريغ روابط يوتيوب 🎥\n"
    "3️⃣ تلخيص النص ✨\n\n"
    "🔧 *اختر أمراً من الأسفل أو أرسل صوتاً مباشرة:*"
)


# ------------------------------------
#  /start
# ------------------------------------
@bot.message_handler(commands=["start"])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🎧 تفريغ صوت", "🎥 تفريغ يوتيوب")
    markup.row("📝 تلخيص نص")

    bot.send_message(
        message.chat.id,
        WELCOME,
        reply_markup=markup,
        parse_mode="Markdown"
    )

# ------------------------------------
#  دالة تفريغ بواسطة AssemblyAI
# ------------------------------------
def transcribe_audio(audio_url):
    # رفع الصوت
    upload = requests.post(
        "https://api.assemblyai.com/v2/upload",
        headers={"authorization": ASSEMBLYAI_API_KEY},
        data=requests.get(audio_url).content
    ).json()

    audio_upload_url = upload["upload_url"]

    # طلب التفريغ
    task = requests.post(
        "https://api.assemblyai.com/v2/transcript",
        headers={"authorization": ASSEMBLYAI_API_KEY},
        json={
            "audio_url": audio_upload_url,
            "language_detection": True,      # اكتشاف اللغة تلقائياً
            "language_code": "ar",           # دعم العربية
            "auto_chapters": False
        }
    ).json()

    transcript_id = task["id"]

    # انتظار انتهاء التفريغ
    while True:
        status = requests.get(
            f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
            headers={"authorization": ASSEMBLYAI_API_KEY}
        ).json()

        if status["status"] == "completed":
            return status["text"]

        if status["status"] == "error":
            return None


# ------------------------------------
#  تلخيص النص
# ------------------------------------
def summarize_text(text):
    response = requests.post(
        "https://api.assemblyai.com/v2/summarize",
        headers={
            "authorization": ASSEMBLYAI_API_KEY,
            "content-type": "application/json"
        },
        json={
            "text": text,
            "context": "general",
            "sentences": 3
        }
    ).json()

    return response.get("summary", None)


# ------------------------------------
#  تفريغ صوت (voice / audio)
# ------------------------------------
@bot.message_handler(content_types=['voice', 'audio'])
def process_voice(message):
    bot.reply_to(message, "⏳ جاري تحميل الصوت ومعالجته…")

    file_id = message.voice.file_id if message.voice else message.audio.file_id
    info = bot.get_file(file_id)

    file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{info.file_path}"

    text = transcribe_audio(file_url)

    if not text:
        bot.reply_to(message, "❌ حدث خطأ أثناء التفريغ")
        return

    bot.reply_to(message, f"📝 النص المستخرج:\n{text}")


# ------------------------------------
#  تفريغ رابط يوتيوب
# ------------------------------------
@bot.message_handler(regexp=r"(youtube\.com|youtu\.be)")
def process_youtube(message):
    url = message.text.strip()

    bot.reply_to(message, "⏳ جاري تحميل الصوت من يوتيوب…")

    try:
        # استخراج الصوت
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'outtmpl': 'audio.mp3'
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        audio_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{info.file_path}"

        # لكن الطريقة الصحيحة: نرفع الملف بأنفسنا
        audio_data = open("audio.mp3", "rb").read()

        upload = requests.post(
            "https://api.assemblyai.com/v2/upload",
            headers={"authorization": ASSEMBLYAI_API_KEY},
            data=audio_data
        ).json()

        text = transcribe_audio(upload["upload_url"])

        if not text:
            bot.reply_to(message, "❌ حدث خطأ أثناء تفريغ اليوتيوب")
            return

        bot.reply_to(message, f"📝 النص المستخرج:\n{text}")

    except Exception as e:
        print(e)
        bot.reply_to(message, "❌ لم أستطع معالجة رابط اليوتيوب")


# ------------------------------------
#  تلخيص نص
# ------------------------------------
@bot.message_handler(func=lambda msg: msg.text == "📝 تلخيص نص")
def ask_for_text(message):
    bot.reply_to(message, "📄 أرسل النص الذي تريد تلخيصه:")

@bot.message_handler(func=lambda msg: True)
def summarize_handler(message):
    if message.reply_to_message and "أرسل النص" in message.reply_to_message.text:
        summary = summarize_text(message.text)
        if summary:
            bot.reply_to(message, f"✨ ملخص النص:\n\n{summary}")
        else:
            bot.reply_to(message, "❌ حدث خطأ أثناء التلخيص")

# ------------------------------------
#  تشغيل البوت
# ------------------------------------
bot.infinity_polling()
