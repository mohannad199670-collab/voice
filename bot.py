import os
import telebot
import requests
import time
import re

# ----------------------------------------
#  🔑 قراءة المفاتيح من Koyeb
# ----------------------------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")

if not TELEGRAM_TOKEN:
    raise RuntimeError("❌ متغير TELEGRAM_TOKEN غير موجود داخل Koyeb")
if not ASSEMBLYAI_API_KEY:
    raise RuntimeError("❌ متغير ASSEMBLYAI_API_KEY غير موجود داخل Koyeb")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

ASSEMBLY_HEADERS = {
    "authorization": ASSEMBLYAI_API_KEY,
    "content-type": "application/json"
}


# ----------------------------------------
#  📌 دالة تلخيص النص
# ----------------------------------------
def summarize_text(text):
    try:
        url = "https://api.assemblyai.com/v2/summarize"
        data = {
            "text": text,
            "summarization_model": "informative",
            "max_output_size": 200
        }
        response = requests.post(url, json=data, headers=ASSEMBLY_HEADERS).json()
        return response.get("summary", "❌ لم ينجح التلخيص")
    except:
        return "❌ حدث خطأ أثناء التلخيص"


# ----------------------------------------
#  📌 دالة تفريغ رابط يوتيوب
# ----------------------------------------
def transcribe_youtube(url):
    bot_msg = "📺 تم استلام رابط اليوتيوب… جاري التفريغ ⏳"

    # إرسال رابط اليوتيوب مباشرة لـ AssemblyAI
    transcript_request = {
        "audio_url": url,
        "language_detection": True
    }

    bot_msg = bot_msg + "\n\n🔄 جاري الاتصال بواجهة التحويل…"
    trans = requests.post(
        "https://api.assemblyai.com/v2/transcript",
        json=transcript_request,
        headers=ASSEMBLY_HEADERS
    ).json()

    transcript_id = trans["id"]

    # الانتظار لحين انتهاء المعالجة
    status = "queued"
    while status not in ["completed", "error"]:
        time.sleep(2)
        check = requests.get(
            f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
            headers=ASSEMBLY_HEADERS
        ).json()
        status = check["status"]

    if status == "error":
        return None, None

    return check["text"], check.get("language_code", "غير معروف")


# ----------------------------------------
#  📌 استقبال الصوتيات + الروابط
# ----------------------------------------
@bot.message_handler(func=lambda m: True, content_types=['text', 'voice', 'audio'])
def handle_all(message):
    text_msg = message.text or ""

    # -------------------------------------------------
    #  🔥 إذا كان المستخدم أرسل رابط يوتيوب
    # -------------------------------------------------
    youtube_regex = r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/\S+"

    if re.search(youtube_regex, text_msg):
        yt_url = re.findall(youtube_regex, text_msg)
        url = text_msg.strip()

        bot.reply_to(message, "📺 **تم استلام رابط اليوتيوب… جاري المعالجة ⏳**")

        transcript, lang = transcribe_youtube(url)
        if not transcript:
            bot.reply_to(message, "❌ حدث خطأ أثناء تفريغ رابط اليوتيوب")
            return

        bot.send_message(
            message.chat.id,
            f"📝 **النص المستخرج من اليوتيوب:**\n\n{transcript}",
            parse_mode="Markdown"
        )

        summary = summarize_text(transcript)

        bot.send_message(
            message.chat.id,
            f"✨ **ملخص الفيديو:**\n\n{summary}",
            parse_mode="Markdown"
        )
        return

    # -------------------------------------------------
    #  🎧 إذا كان صوت (Voice أو Audio)
    # -------------------------------------------------
    if message.content_type in ['voice', 'audio']:

        bot.reply_to(message, "🎧 جاري معالجة الصوت ⏳")

        file_id = message.voice.file_id if message.voice else message.audio.file_id
        file_info = bot.get_file(file_id)
        file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_info.file_path}"

        audio_content = requests.get(file_url).content
        upload_res = requests.post(
            "https://api.assemblyai.com/v2/upload",
            headers={"authorization": ASSEMBLYAI_API_KEY},
            data=audio_content
        ).json()

        audio_url = upload_res["upload_url"]

        transcript_request = {
            "audio_url": audio_url,
            "language_detection": True
        }

        trans = requests.post(
            "https://api.assemblyai.com/v2/transcript",
            json=transcript_request,
            headers=ASSEMBLY_HEADERS
        ).json()

        transcript_id = trans["id"]

        status = "queued"
        while status not in ["completed", "error"]:
            time.sleep(2)
            check = requests.get(
                f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
                headers=ASSEMBLY_HEADERS
            ).json()
            status = check["status"]

        if status == "error":
            bot.reply_to(message, "❌ حدث خطأ أثناء التفريغ")
            return

        text = check["text"]
        lang = check.get("language_code", "غير معروف")

        bot.send_message(
            message.chat.id,
            f"📝 **النص المستخرج:**\n\n{text}",
            parse_mode="Markdown"
        )

        summary = summarize_text(text)

        bot.send_message(
            message.chat.id,
            f"✨ **الملخص:**\n\n{summary}",
            parse_mode="Markdown"
        )


# ----------------------------------------
#  🚀 تشغيل البوت
# ----------------------------------------
bot.infinity_polling()
