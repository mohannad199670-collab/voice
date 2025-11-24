import os
import telebot
import requests
import yt_dlp
import time

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ===========================
# رسالة الترحيب
# ===========================
WELCOME = """
👋✨ أهلاً بك في بوت التفريغ الذكي!

🎧 هذا البوت يقوم بـ:
• تفريغ الصوت
• تفريغ رابط يوتيوب
• تلخيص النص المستخرج
• اكتشاف اللغة تلقائياً

استخدم الأوامر التالية:
🎙 /voice  — تفريغ صوت
🎬 /youtube — تفريغ رابط يوتيوب
📝 /summary — تلخيص آخر نص
ℹ /help — المساعدة

✨ جاهز لخدمتك دائماً يا بطل!
"""

last_text = ""  # نخزن آخر نص لتلخيصه


# ===========================
#   /start
# ===========================
@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(msg, WELCOME)


@bot.message_handler(commands=['help'])
def help_cmd(msg):
    bot.reply_to(msg, WELCOME)


# ===========================
#   /voice تفريغ صوت
# ===========================
@bot.message_handler(commands=['voice'])
def ask_voice(msg):
    bot.reply_to(msg, "🎤 أرسل المقطع الصوتي الآن…")


@bot.message_handler(content_types=['voice', 'audio'])
def handle_audio(message):
    global last_text

    bot.reply_to(message, "⏳ جاري معالجة الصوت…")

    # تحميل الملف من تلغرام
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file_info = bot.get_file(file_id)
    file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_info.file_path}"

    audio_data = requests.get(file_url).content

    # رفع الصوت لـ AssemblyAI
    up = requests.post(
        "https://api.assemblyai.com/v2/upload",
        headers={"authorization": ASSEMBLYAI_API_KEY},
        data=audio_data
    )

    audio_url = up.json()["upload_url"]

    # طلب التفريغ
    trans = requests.post(
        "https://api.assemblyai.com/v2/transcript",
        json={"audio_url": audio_url},
        headers={"authorization": ASSEMBLYAI_API_KEY}
    ).json()

    trans_id = trans["id"]

    # انتظار التفريغ
    status = "queued"
    while status not in ["completed", "error"]:
        check = requests.get(
            f"https://api.assemblyai.com/v2/transcript/{trans_id}",
            headers={"authorization": ASSEMBLYAI_API_KEY}
        ).json()
        status = check["status"]
        time.sleep(2)

    if status == "completed":
        last_text = check["text"]
        bot.reply_to(message, f"📝 النص المستخرج:\n\n{last_text}")
    else:
        bot.reply_to(message, "❌ حدث خطأ أثناء تفريغ الصوت")


# ===========================
#   /youtube تفريغ رابط يوتيوب
# ===========================
@bot.message_handler(commands=['youtube'])
def ask_yt(msg):
    bot.reply_to(msg, "🎬 أرسل رابط الفيديو الآن…")


@bot.message_handler(func=lambda m: "youtube.com" in m.text or "youtu.be" in m.text)
def handle_youtube(msg):
    global last_text
    url = msg.text.strip()

    bot.reply_to(msg, "⏳ جاري تحميل الصوت من يوتيوب…")

    try:
        # استخراج الصوت
        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "noplaylist": True,
            "outtmpl": "yt_audio.%(ext)s"
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        audio_data = open(filename, "rb").read()

        # رفع الصوت
        up = requests.post(
            "https://api.assemblyai.com/v2/upload",
            headers={"authorization": ASSEMBLYAI_API_KEY},
            data=audio_data
        )
        audio_url = up.json()["upload_url"]

        # طلب التفريغ
        trans = requests.post(
            "https://api.assemblyai.com/v2/transcript",
            json={"audio_url": audio_url},
            headers={"authorization": ASSEMBLYAI_API_KEY}
        ).json()

        trans_id = trans["id"]

        status = "queued"
        while status not in ["completed", "error"]:
            check = requests.get(
                f"https://api.assemblyai.com/v2/transcript/{trans_id}",
                headers={"authorization": ASSEMBLYAI_API_KEY}
            ).json()
            status = check["status"]
            time.sleep(2)

        if status == "completed":
            last_text = check["text"]
            bot.reply_to(msg, f"📝 النص المستخرج:\n\n{last_text}")
        else:
            bot.reply_to(msg, "❌ حدث خطأ أثناء تفريغ رابط اليوتيوب")

    except Exception as e:
        bot.reply_to(msg, f"❌ خطأ: {e}")


# ===========================
#   /summary تلخيص النص
# ===========================
@bot.message_handler(commands=['summary'])
def summarize(msg):
    global last_text

    if last_text == "":
        bot.reply_to(msg, "❗ لا يوجد نص لتلخيصه.")
        return

    bot.reply_to(msg, "⏳ جاري تلخيص النص…")

    prompt = (
        "قم بتلخيص النص التالي باحترافية ووضوح وبالعربية:\n\n"
        + last_text
    )

    # استخدام API مجاني مفتوح المصدر (HuggingFace Inference)
    resp = requests.post(
        "https://api-inference.huggingface.co/models/facebook/bart-large-cnn",
        headers={"Authorization": "Bearer hf_mUwLtNWcDlaBCkXXXXXXXX"},  # ضع مفتاحك إذا عندك
        json={"inputs": prompt}
    )

    try:
        summary = resp.json()[0]["summary_text"]
        bot.reply_to(msg, "📘 **التلخيص:**\n\n" + summary)
    except:
        bot.reply_to(msg, "❌ لم أتمكن من تلخيص النص.")


# ===========================
#   تشغيل البوت
# ===========================
bot.infinity_polling()
