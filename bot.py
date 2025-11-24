import os
import telebot
import requests
import yt_dlp

# -------------------------------
# قراءة مفاتيح Koyeb
# -------------------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# -------------------------------
# رسالة ترحيب
# -------------------------------
WELCOME = (
    "👋 أهلاً بك في *بوت التفريغ الصوتي*!\n\n"
    "🎙️ يدعم:\n"
    "• تفريغ الرسائل الصوتية\n"
    "• تفريغ الملفات الصوتية\n"
    "• تفريغ صوت روابط يوتيوب\n"
    "• دعم العربية واكتشاف اللغة تلقائياً\n\n"
    "📌 اختر من الأزرار أو أرسل صوتاً."
)

@bot.message_handler(commands=["start"])
def start(message):
    kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🎧 تفريغ صوت")
    kb.row("🎥 تفريغ يوتيوب")
    bot.send_message(message.chat.id, WELCOME, reply_markup=kb, parse_mode="Markdown")

# -------------------------------
#  دالة تفريغ الصوت عبر Deepgram
# -------------------------------
def deepgram_transcribe(audio_bytes):
    url = "https://api.deepgram.com/v1/listen"
    
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "audio/*"
    }

    params = {
        "smart_format": "true",
        "punctuate": "true",
        "language": "ar",  # العربية
        "detect_language": "true"
    }

    resp = requests.post(url, headers=headers, params=params, data=audio_bytes)

    if resp.status_code != 200:
        print("Deepgram error:", resp.text)
        return None

    try:
        return resp.json()["results"]["channels"][0]["alternatives"][0]["transcript"]
    except:
        return None

# -------------------------------
# معالجة الصوت من تيليجرام
# -------------------------------
@bot.message_handler(content_types=['voice', 'audio'])
def handle_voice(message):
    bot.reply_to(message, "⏳ جاري معالجة الصوت…")

    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file_info = bot.get_file(file_id)
    file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_info.file_path}"

    audio_bytes = requests.get(file_url).content

    text = deepgram_transcribe(audio_bytes)

    if not text:
        bot.reply_to(message, "❌ حدث خطأ أثناء التفريغ.")
        return

    bot.reply_to(message, f"📝 النص المستخرج:\n\n{text}")

# -------------------------------
# تفريغ روابط يوتيوب (بدون تحميل ملف ضخم)
# -------------------------------
def process_youtube(message):
    url = message.text.strip()
    bot.reply_to(message, "⏳ جاري استخراج الصوت من يوتيوب…")

    try:
        ydl_opts = {
            "format": "bestaudio",
            "quiet": True,
            "noplaylist": True,
            "extract_flat": False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info["url"]

        audio_bytes = requests.get(audio_url).content
        text = deepgram_transcribe(audio_bytes)

        if not text:
            bot.reply_to(message, "❌ لم أستطع تفريغ الرابط.")
            return

        bot.reply_to(message, f"🎥 *نص يوتيوب المستخرج:*\n\n{text}", parse_mode="Markdown")

    except Exception as e:
        print("YouTube error:", e)
        bot.reply_to(message, "❌ لم أستطع معالجة رابط يوتيوب.")

@bot.message_handler(func=lambda m: m.text == "🎥 تفريغ يوتيوب")
def ask_yt(message):
    msg = bot.reply_to(message, "🔗 أرسل رابط فيديو يوتيوب:")
    bot.register_next_step_handler(msg, process_youtube)

@bot.message_handler(regexp=r"(youtu\.be|youtube\.com)")
def direct_yt(message):
    process_youtube(message)

# -------------------------------
# زر تفريغ صوت
# -------------------------------
@bot.message_handler(func=lambda m: m.text == "🎧 تفريغ صوت")
def ask_voice(message):
    bot.reply_to(message, "🎤 أرسل المقطع الصوتي الآن.")

# -------------------------------
# تشغيل البوت
# -------------------------------
bot.infinity_polling()
