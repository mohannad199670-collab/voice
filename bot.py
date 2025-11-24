import os
import re
import telebot
import requests
import yt_dlp

# ------------------------------------
#  قراءة المتغيرات من Koyeb
# ------------------------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")

if not TELEGRAM_TOKEN or not ASSEMBLYAI_API_KEY:
    raise RuntimeError("يجب ضبط TELEGRAM_TOKEN و ASSEMBLYAI_API_KEY في إعدادات Koyeb")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ------------------------------------
#  رسالة ترحيب
# ------------------------------------
WELCOME = (
    "👋✨ أهلاً وسهلاً بك في *بوت التفريغ الصوتي الاحترافي*!\n\n"
    "🎙️ *المميزات المتاحة:*\n"
    "1️⃣ تفريغ المقاطع الصوتية والرسائل الصوتية (يدعم العربية)\n"
    "2️⃣ تفريغ الصوت من روابط يوتيوب 🎥\n"
    "3️⃣ تلخيص النصوص 📝\n\n"
    "🔧 اختر من الأزرار بالأسفل أو أرسل صوتاً مباشرة."
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
#  دالة تفريغ الصوت عبر AssemblyAI (تستقبل بايتات الصوت)
# ------------------------------------
def transcribe_audio_bytes(audio_bytes):
    # رفع الصوت
    upload_resp = requests.post(
        "https://api.assemblyai.com/v2/upload",
        headers={"authorization": ASSEMBLYAI_API_KEY},
        data=audio_bytes
    )
    upload_resp.raise_for_status()
    audio_url = upload_resp.json()["upload_url"]

    # إنشاء مهمة التفريغ
    task_resp = requests.post(
        "https://api.assemblyai.com/v2/transcript",
        headers={
            "authorization": ASSEMBLYAI_API_KEY,
            "content-type": "application/json"
        },
        json={
            "audio_url": audio_url,
            "language_detection": True  # اكتشاف اللغة تلقائياً (العربية وغيرها)
        }
    )
    task_resp.raise_for_status()
    transcript_id = task_resp.json()["id"]

    # انتظار انتهاء التفريغ
    while True:
        status_resp = requests.get(
            f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
            headers={"authorization": ASSEMBLYAI_API_KEY}
        )
        status_resp.raise_for_status()
        data = status_resp.json()

        if data["status"] == "completed":
            return data.get("text", "")

        if data["status"] == "error":
            return None

# ------------------------------------
#  تلخيص نص بسيط (محلي بدون أي API)
# ------------------------------------
def summarize_text(text, max_sentences=3):
    # تقسيم الجمل اعتماداً على علامات الوقف العربية والإنجليزية
    sentences = re.split(r'(?<=[\.!\؟\?])\s+', text.strip())
    sentences = [s for s in sentences if s.strip()]
    if len(sentences) <= max_sentences:
        return text
    return " ".join(sentences[:max_sentences])

# ------------------------------------
#  /voice (اختياري للتوضيح)
# ------------------------------------
@bot.message_handler(commands=["voice"])
def voice_cmd(message):
    bot.reply_to(message, "🎤 أرسل الآن المقطع الصوتي أو الرسالة الصوتية التي تريد تفريغها.")

# ------------------------------------
#  معالجة المقاطع الصوتية والـ voice
# ------------------------------------
@bot.message_handler(content_types=['voice', 'audio'])
def handle_voice(message):
    bot.reply_to(message, "⏳ جاري معالجة الصوت… انتظر قليلاً.")

    # الحصول على ملف الصوت من تيليجرام
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file_info = bot.get_file(file_id)
    file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_info.file_path}"

    audio_bytes = requests.get(file_url).content

    text = transcribe_audio_bytes(audio_bytes)

    if not text:
        bot.reply_to(message, "❌ حدث خطأ أثناء التفريغ.")
        return

    bot.reply_to(
        message,
        f"🎙 *مقطع صوتي*\n\nالنص المستخرج: 📝\n{text}",
        parse_mode="Markdown"
    )

# ------------------------------------
#  تفريغ رابط يوتيوب (دالة مشتركة)
# ------------------------------------
def process_youtube_url(message):
    url = message.text.strip()

    bot.reply_to(message, "⏳ جاري تحميل الصوت من يوتيوب…")

    try:
        # تحميل أفضل مسار صوت فقط
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": "yt_audio.%(ext)s",
            "quiet": True,
            "noplaylist": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        # قراءة الملف الصوتي كـ bytes
        with open(filename, "rb") as f:
            audio_bytes = f.read()

        # تفريغ الصوت
        text = transcribe_audio_bytes(audio_bytes)

        # حذف الملف بعد الاستخدام
        try:
            os.remove(filename)
        except Exception:
            pass

        if not text:
            bot.reply_to(message, "❌ حدث خطأ أثناء تفريغ رابط اليوتيوب.")
            return

        bot.reply_to(
            message,
            f"🎥 *رابط يوتيوب*\n\nالنص المستخرج: 📝\n{text}",
            parse_mode="Markdown"
        )

    except Exception as e:
        print("YouTube error:", e)
        bot.reply_to(message, "❌ لم أستطع معالجة رابط اليوتيوب. تأكد أن الرابط صحيح وحاول مرة أخرى.")

# عندما يرسل المستخدم رابط يوتيوب مباشرة
@bot.message_handler(regexp=r"(youtube\.com|youtu\.be)")
def direct_youtube(message):
    process_youtube_url(message)

# عندما يضغط زر 🎥 تفريغ يوتيوب
@bot.message_handler(func=lambda m: m.text == "🎥 تفريغ يوتيوب")
def ask_youtube(message):
    msg = bot.reply_to(message, "🔗 أرسل الآن رابط فيديو من يوتيوب:")
    bot.register_next_step_handler(msg, process_youtube_url)

# ------------------------------------
#  تلخيص نص
# ------------------------------------
@bot.message_handler(func=lambda m: m.text == "🎧 تفريغ صوت")
def explain_voice(message):
    bot.reply_to(message, "🎤 أرسل الآن مقطعاً صوتياً أو رسالة صوتية وسأقوم بتفريغه لك.")

@bot.message_handler(func=lambda m: m.text == "📝 تلخيص نص")
def ask_summary(message):
    msg = bot.reply_to(message, "📄 أرسل النص الذي تريد تلخيصه:")
    bot.register_next_step_handler(msg, do_summary)

def do_summary(message):
    text = message.text.strip()
    if not text:
        bot.reply_to(message, "⚠️ النص فارغ.")
        return

    summary = summarize_text(text)
    bot.reply_to(message, f"✨ *ملخص النص:*\n\n{summary}", parse_mode="Markdown")

# ------------------------------------
#  تشغيل البوت
# ------------------------------------
bot.infinity_polling()
