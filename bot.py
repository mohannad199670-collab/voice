import os
import telebot
import requests
import time
import subprocess
import uuid

# =========================
# متغيرات البيئة
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

if not BOT_TOKEN or not DEEPGRAM_API_KEY:
    raise RuntimeError("❌ يجب ضبط BOT_TOKEN و DEEPGRAM_API_KEY في إعدادات Koyeb")

bot = telebot.TeleBot(BOT_TOKEN)

# =========================
# حسابك أنت فقط (Admin)
# =========================
ADMIN_ID = 604494923

# =========================
# قاعدة بيانات بسيطة
# =========================
users_db = {}   # {user_id: {"used_seconds": xx, "plan_seconds": yy, "username": "@"}}
free_seconds = 120  # دقيقتين مجانا

# =========================
# تحويل الصوت إلى WAV (بدون pydub)
# =========================
def convert_to_wav(input_bytes):
    temp_in = f"/tmp/{uuid.uuid4()}.mp3"
    temp_out = f"/tmp/{uuid.uuid4()}.wav"

    with open(temp_in, "wb") as f:
        f.write(input_bytes)

    subprocess.run([
        "ffmpeg", "-i", temp_in,
        "-ar", "16000", "-ac", "1",
        temp_out, "-y", "-loglevel", "quiet"
    ])

    with open(temp_out, "rb") as f:
        return f.read()

# =========================
# Deepgram تفريغ الصوت عبر
# =========================
def deepgram_transcribe(wav_bytes):
    url = "https://api.deepgram.com/v1/listen"
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "audio/wav"
    }
    response = requests.post(url, headers=headers, data=wav_bytes)
    data = response.json()

    try:
        text = data["results"]["channels"][0]["alternatives"][0]["transcript"]
        return text
    except:
        return None

# =========================
# واجهة الأزرار
# =========================
def main_menu():
    kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🎧 تفريغ صوت")
    kb.row("💳 الاشتراكات", "⚙️ الإعدادات")
    return kb

def subscription_menu():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(
        telebot.types.InlineKeyboardButton("⏱ 1 ساعة — 5$", callback_data="plan_3600"),
        telebot.types.InlineKeyboardButton("⏱ 2 ساعات — 9$", callback_data="plan_7200"),
    )
    kb.add(
        telebot.types.InlineKeyboardButton("⏱ 5 ساعات — 20$", callback_data="plan_18000")
    )
    kb.add(
        telebot.types.InlineKeyboardButton("رجوع ⬅️", callback_data="back_menu")
    )
    return kb

# =========================
# رسالة Start
# =========================
@bot.message_handler(commands=["start"])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or "بدون_يوزر"

    if user_id not in users_db:
        users_db[user_id] = {
            "used_seconds": 0,
            "plan_seconds": 0,
            "username": username
        }

    bot.send_message(
        user_id,
        f"👋 أهلاً بك في *الأسطورة للتفريغ الصوتي*\n\n"
        f"🎙 يدعم العربية تلقائياً\n"
        f"🎁 لديك دقيقتان مجاناً\n"
        f"🆔 ID: `{user_id}`\n"
        f"👤 Username: @{username}\n\n"
        "اختر من القائمة:",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )

# =========================
# زر الاشتراكات
# =========================
@bot.message_handler(func=lambda m: m.text == "💳 الاشتراكات")
def show_plans(message):
    bot.send_message(
        message.chat.id,
        "اختر الخطة المناسبة لك:",
        reply_markup=subscription_menu()
    )

# =========================
# زر الإعدادات
# =========================
@bot.message_handler(func=lambda m: m.text == "⚙️ الإعدادات")
def settings(message):
    user_id = message.from_user.id
    u = users_db[user_id]

    remain = u["plan_seconds"] - u["used_seconds"]
    if remain < 0: remain = 0

    bot.send_message(
        user_id,
        f"⚙️ إعدادات الاشتراك:\n\n"
        f"⏳ الوقت المستخدم: {u['used_seconds']} ثانية\n"
        f"🎁 المتبقي: {remain} ثانية\n"
        f"🆔 ID: `{user_id}`\n"
        f"👤 Username: @{u['username']}",
        parse_mode="Markdown"
    )

# =========================
# استقبال الصوت
# =========================
@bot.message_handler(content_types=['voice', 'audio'])
def handle_voice(message):
    user_id = message.from_user.id
    u = users_db[user_id]

    # التأكد من وجود رصيد وقت
    if u["used_seconds"] >= (free_seconds + u["plan_seconds"]):
        bot.send_message(user_id, "❌ انتهى رصيدك.\n💳 اشترك لإكمال التفريغ.")
        return

    bot.send_message(user_id, "⏳ جاري معالجة الصوت…")

    # جلب الملف
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    info = bot.get_file(file_id)
    url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{info.file_path}"
    file_bytes = requests.get(url).content

    wav_bytes = convert_to_wav(file_bytes)
    text = deepgram_transcribe(wav_bytes)

    if not text:
        bot.send_message(user_id, "❌ فشل التفريغ.")
        return

    # حساب مدة الصوت
    duration = message.voice.duration if message.voice else message.audio.duration
    u["used_seconds"] += duration

    bot.send_message(
        user_id,
        f"🎙 *النص المستخرج:*\n{text}",
        parse_mode="Markdown"
    )

# =========================
# معالجة شراء الباقات
# =========================
@bot.callback_query_handler(func=lambda c: c.data.startswith("plan_"))
def buy_plan(c):
    user_id = c.from_user.id
    plan_seconds = int(c.data.split("_")[1])

    price = {3600: "5$", 7200: "9$", 18000: "20$"}[plan_seconds]

    bot.edit_message_text(
        f"💳 اخترت باقة مدة: {plan_seconds//60} دقيقة\n"
        f"السعر: *{price}*\n\n"
        "طرق الدفع:\n"
        "🔥 USDT (TRC20): `TRWu3vC1GRDwbEymaiPNjXbpUw4wmwSRYa`\n"
        "💰 Payeer: `P1058635648`\n\n"
        "بعد الدفع أرسل لقطة شاشة ليتم تفعيل الباقة.",
        chat_id=user_id,
        message_id=c.message.message_id,
        parse_mode="Markdown"
    )

# =========================
# زر الرجوع
# =========================
@bot.callback_query_handler(func=lambda c: c.data == "back_menu")
def back_menu(c):
    bot.edit_message_text(
        "اختر من القائمة:",
        chat_id=c.from_user.id,
        message_id=c.message.message_id
    )

# =========================
# لوحة تحكم الأدمن
# =========================
@bot.message_handler(commands=["admin"])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return

    total_users = len(users_db)

    bot.send_message(
        ADMIN_ID,
        f"📊 *لوحة التحكم*\n\n"
        f"👥 عدد المشتركين: {total_users}\n",
        parse_mode="Markdown"
    )


# =========================
# تشغيل البوت
# =========================
bot.infinity_polling()
