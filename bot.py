import os
import telebot
import requests
import time
import yt_dlp
import re
import language_tool_python

# =============[ المتغيرات ]=============
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
tool = language_tool_python.LanguageTool('ar')  # مصحح لغوي عربي

HEADERS = {
    "authorization": ASSEMBLYAI_API_KEY,
    "content-type": "application/json"
}

user_text_memory = {}  # ذاكرة النصوص للمستخدمين


# =============[ قائمة الأوامر ]=============
def menu_keyboard():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(
        telebot.types.InlineKeyboardButton("🎧 تفريغ صوت", callback_data="transcribe_audio"),
        telebot.types.InlineKeyboardButton("📺 تفريغ يوتيوب", callback_data="transcribe_yt")
    )
    kb.add(
        telebot.types.InlineKeyboardButton("✨ تلخيص النص", callback_data="summarize"),
        telebot.types.InlineKeyboardButton("✏️ تصحيح النص", callback_data="correct")
    )
    kb.add(
        telebot.types.InlineKeyboardButton("🗑️ حذف النص", callback_data="delete")
    )
    return kb


# =============[ رسالة الترحيب ]=============
@bot.message_handler(commands=['start', 'menu'])
def start_cmd(message):
    welcome = (
        "👋✨ <b>أهلاً وسهلاً بك في بوت التفريغ الصوتي واليوتيوب!</b>\n\n"
        "🎧 <b>هذا البوت يساعدك في:</b>\n"
        "• تفريغ المقاطع الصوتية بدقة عالية\n"
        "• استخراج النص من روابط اليوتيوب تلقائياً\n"
        "• تلخيص النصوص الطويلة ✨\n"
        "• تصحيح الأخطاء الإملائية والنحوية ✏️\n"
        "• حذف النصوص وإدارتها بسهولة 🗑️\n\n"
        "🔽 <b>اختر ما تريد فعله من القائمة:</b>"
    )

    bot.send_message(
        message.chat.id,
        welcome,
        reply_markup=menu_keyboard(),
        parse_mode="HTML"
    )


# =============[ تنزيل صوت من يوتيوب ]=============
def download_youtube_audio(url):
    try:
        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192"
            }],
            "outtmpl": "audio.%(ext)s"
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        return "audio.mp3"
    except Exception as e:
        print("Error:", e)
        return None


# =============[ رفع الصوت لـ AssemblyAI ]=============
def upload_audio(filename):
    try:
        with open(filename, "rb") as f:
            data = f.read()

        res = requests.post(
            "https://api.assemblyai.com/v2/upload",
            headers={"authorization": ASSEMBLYAI_API_KEY},
            data=data
        )
        return res.json().get("upload_url")
    except:
        return None


# =============[ تفريغ صوت ]=============
def transcribe(audio_url):
    data = {
        "audio_url": audio_url,
        "language_detection": True
    }
    res = requests.post(
        "https://api.assemblyai.com/v2/transcript",
        json=data,
        headers=HEADERS
    )
    tid = res.json()["id"]

    status = "queued"
    while status not in ["completed", "error"]:
        time.sleep(2)
        check = requests.get(
            f"https://api.assemblyai.com/v2/transcript/{tid}",
            headers=HEADERS
        ).json()
        status = check["status"]

    return check if status == "completed" else None


# =============[ تلخيص نص ]=============
def summarize_text(text):
    data = {
        "text": text,
        "summarization_model": "informative",
        "max_output_size": 200
    }
    res = requests.post(
        "https://api.assemblyai.com/v2/summarize",
        json=data,
        headers=HEADERS
    ).json()
    return res.get("summary", "❌ لم يتم التلخيص")


# =============[ تصحيح نص ]=============
def correct_text(text):
    matches = tool.check(text)
    return language_tool_python.utils.correct(text, matches)


# =============[ استقبال صوت ]=============
@bot.message_handler(content_types=['voice', 'audio'])
def process_audio(message):
    bot.reply_to(message, "🎧 جاري معالجة الصوت…")

    file_id = message.voice.file_id if message.voice else message.audio.file_id
    info = bot.get_file(file_id)
    url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{info.file_path}"

    content = requests.get(url).content
    open("audio_user.mp3", "wb").write(content)

    audio_url = upload_audio("audio_user.mp3")
    bot.send_message(message.chat.id, "⏳ جاري التفريغ…")

    result = transcribe(audio_url)
    if not result:
        bot.reply_to(message, "❌ حدث خطأ أثناء التفريغ")
        return

    text = result["text"]
    user_text_memory[message.chat.id] = text

    bot.send_message(message.chat.id, f"📝 النص المستخرج:\n\n{text}")


# =============[ استقبال رابط يوتيوب ]=============
@bot.message_handler(func=lambda m: m.text and ("youtube.com" in m.text or "youtu.be" in m.text))
def yt_message(message):
    url = message.text.strip()
    bot.send_message(message.chat.id, "📥 جاري تحميل صوت اليوتيوب…")

    filename = download_youtube_audio(url)
    if not filename:
        bot.reply_to(message, "❌ فشل تنزيل الصوت")
        return

    bot.send_message(message.chat.id, "📤 جاري رفع الصوت…")
    audio_url = upload_audio(filename)

    bot.send_message(message.chat.id, "⏳ جاري التفريغ…")
    result = transcribe(audio_url)

    if not result:
        bot.reply_to(message, "❌ فشل التفريغ")
        return

    text = result["text"]
    user_text_memory[message.chat.id] = text

    bot.send_message(message.chat.id, f"📝 النص:\n\n{text}")


# =============[ أزرار القائمة ]=============
@bot.callback_query_handler(func=lambda call: True)
def menu_actions(call):
    chat_id = call.message.chat.id

    if call.data == "summarize":
        if chat_id not in user_text_memory:
            bot.send_message(chat_id, "⚠️ لا يوجد نص لتلخيصه")
            return
        summary = summarize_text(user_text_memory[chat_id])
        bot.send_message(chat_id, f"✨ الملخص:\n\n{summary}")

    elif call.data == "correct":
        if chat_id not in user_text_memory:
            bot.send_message(chat_id, "⚠️ لا يوجد نص لتصحيحه")
            return
        corrected = correct_text(user_text_memory[chat_id])
        bot.send_message(chat_id, f"✏️ التصحيح:\n\n{corrected}")

    elif call.data == "delete":
        user_text_memory.pop(chat_id, None)
        bot.send_message(chat_id, "🗑️ تم حذف النص من الذاكرة")

    else:
        bot.answer_callback_query(call.id, "اختر من القائمة")


# =============[ تشغيل البوت ]=============
bot.infinity_polling()
