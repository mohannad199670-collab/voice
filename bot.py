import os
import telebot
import requests

# -----------------------------
#  📌 قراءة المفاتيح من Koyeb
# -----------------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")

if not TELEGRAM_TOKEN:
    raise RuntimeError("❌ يجب ضبط TELEGRAM_TOKEN داخل Koyeb")

if not ASSEMBLYAI_API_KEY:
    raise RuntimeError("❌ يجب ضبط ASSEMBLYAI_API_KEY داخل Koyeb")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# -----------------------------
#  📌 استقبال المقاطع الصوتية
# -----------------------------
@bot.message_handler(content_types=['voice', 'audio'])
def handle_voice(message):
    file_id = message.voice.file_id if message.voice else message.audio.file_id

    # تنزيل ملف الصوت
    file_info = bot.get_file(file_id)
    file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_info.file_path}"

    bot.reply_to(message, "⏳ جاري تفريغ الصوت… انتظر قليلاً")

    # رفع ملف الصوت لـ AssemblyAI
    upload_url = "https://api.assemblyai.com/v2/upload"
    headers = {"authorization": ASSEMBLYAI_API_KEY}

    audio_data = requests.get(file_url).content
    up = requests.post(upload_url, headers=headers, data=audio_data)

    audio_url = up.json()["upload_url"]

    # إنشاء طلب تفريغ
    endpoint = "https://api.assemblyai.com/v2/transcript"
    json_data = {"audio_url": audio_url}
    headers = {
        "authorization": ASSEMBLYAI_API_KEY,
        "content-type": "application/json"
    }

    trans = requests.post(endpoint, json=json_data, headers=headers).json()
    transcript_id = trans["id"]

    # انتظار انتهاء التفريغ
    status = "queued"
    while status not in ["completed", "error"]:
        check = requests.get(f"{endpoint}/{transcript_id}", headers=headers).json()
        status = check["status"]

    # إرسال النص
    if status == "completed":
        text = check["text"]
        bot.reply_to(message, f"📝 النص المستخرج:\n\n{text}")
    else:
        bot.reply_to(message, "❌ حدث خطأ أثناء التفريغ")


# -----------------------------
#  📌 تشغيل البوت
# -----------------------------
bot.infinity_polling()
