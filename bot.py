import telebot
from telebot import types
import os
import json
import requests

# ==========================
#  المتغيرات من Koyeb
# ==========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN or not DEEPGRAM_API_KEY:
    raise RuntimeError("❌ يجب ضبط BOT_TOKEN و DEEPGRAM_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN)

# ملف المستخدمين
DATA_FILE = "users.json"
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f, ensure_ascii=False, indent=4)


def load_users():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_users(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# ==========================
#  لوحة بداية
# ==========================
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🎧 تفريغ صوت", "📄 الاشتراكات")
    kb.row("⚙️ الإعدادات")
    return kb


# ==========================
#  طرق الدفع (بايير بدون سمايل)
# ==========================
USDT_ADDR = "TRWu3vC1GRDwbEymaiPNjXbpUw4wmwSRYa"
PAYEER_ADDR = "P1058635648"


def payment_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("USDT (TRC20) 🔥", callback_data="pay_usdt"),
        types.InlineKeyboardButton("بايير", callback_data="pay_payeer")
    )
    return kb


def payment_message():
    return (
        f"💵 طرق الدفع:\n\n"
        f"🔥 USDT (TRC20):\n`{USDT_ADDR}`\n\n"
        f"💰 Payeer:\n`{PAYEER_ADDR}`\n\n"
        f"بعد الدفع أرسل لقطة شاشة ليتم التفعيل."
    )


# ==========================
#  /start
# ==========================
@bot.message_handler(commands=["start"])
def start(message):
    uid = str(message.from_user.id)
    users = load_users()

    if uid not in users:
        users[uid] = {"used": 0, "paid": 0}
        save_users(users)

    bot.send_message(
        message.chat.id,
        "👋 أهلاً بك في **الأسطورة للتفريغ الصوتي**!\n"
        "🎙 يدعم العربية + اكتشاف اللغة تلقائياً\n"
        "🎁 لديك دقيقتان مجاناً",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )


# ==========================
#  الاشتراكات
# ==========================
@bot.message_handler(func=lambda m: m.text == "📄 الاشتراكات")
def subs(message):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔘 باقة 60 دقيقة – 5$", callback_data="plan60"))
    bot.send_message(message.chat.id, "اختر الباقة:", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data == "plan60")
def plan60(call):
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="اختر طريقة الدفع:",
        reply_markup=payment_keyboard()
    )


@bot.callback_query_handler(func=lambda c: c.data == "pay_usdt")
def payusdt(call):
    bot.send_message(call.message.chat.id, payment_message(), parse_mode="Markdown")


@bot.callback_query_handler(func=lambda c: c.data == "pay_payeer")
def paypayeer(call):
    bot.send_message(call.message.chat.id, payment_message(), parse_mode="Markdown")


# ==========================
#  لوحة تحكم الأدمن
# ==========================
@bot.message_handler(func=lambda m: m.text == "⚙️ الإعدادات")
def settings(message):
    if message.from_user.id != ADMIN_ID:
        return bot.send_message(message.chat.id, "❌ غير مسموح")

    users = load_users()
    total_users = len(users)
    used = sum(u["used"] for u in users.values())
    paid = sum(u["paid"] for u in users.values())

    bot.send_message(
        message.chat.id,
        f"🛠 **لوحة الأدمن**\n\n"
        f"👥 المستخدمين: {total_users}\n"
        f"⏱ الوقت المستخدم: {used} ثانية\n"
        f"🎁 الوقت المدفوع المتبقي: {paid} ثانية\n\n"
        f"لإضافة وقت:\n`/add_time user_id دقائق`",
        parse_mode="Markdown"
    )


# ==========================
#  إضافة وقت
# ==========================
@bot.message_handler(commands=["add_time"])
def add_time(message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        _, uid, minutes = message.text.split()
        uid = str(uid)
        minutes = int(minutes)
    except:
        return bot.reply_to(message, "❌ صيغة خاطئة")

    users = load_users()
    if uid not in users:
        return bot.reply_to(message, "❌ المستخدم غير موجود")

    users[uid]["paid"] += minutes * 60
    save_users(users)
    bot.reply_to(message, f"✔ تمت إضافة {minutes} دقيقة.")


# ==========================
#  تفريغ الصوت — Deepgram REST API
# ==========================
def transcribe_audio(audio_bytes):
    url = "https://api.deepgram.com/v1/listen"

    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "audio/ogg"
    }

    params = {
        "punctuate": "true",
        "detect_language": "true",
        "multilingual": "true",
        "smart_format": "true"
    }

    response = requests.post(url, headers=headers, params=params, data=audio_bytes)

    data = response.json()

    try:
        return data["results"]["channels"][0]["alternatives"][0]["transcript"]
    except:
        return None


# ==========================
#  استقبال الصوت
# ==========================
@bot.message_handler(content_types=["voice"])
def voice_handler(message):
    uid = str(message.from_user.id)
    users = load_users()

    duration = message.voice.duration
    free_limit = 120

    paid = users[uid]["paid"]
    used = users[uid]["used"]
    available = free_limit + paid - used

    if duration > available:
        return bot.reply_to(message, "❌ ليس لديك وقت كافٍ.")

    bot.reply_to(message, "⏳ جاري التفريغ...")

    # تحميل الملف
    file_info = bot.get_file(message.voice.file_id)
    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
    audio_bytes = requests.get(file_url).content

    # تفريغ
    text = transcribe_audio(audio_bytes)

    if not text:
        return bot.reply_to(message, "❌ لم أستطع تفريغ الصوت.")

    # تحديث الوقت
    users[uid]["used"] += duration
    save_users(users)

    bot.send_message(
        message.chat.id,
        f"📄 النص المستخرج:\n{text}\n\n⏱ المدة المصروفة: {duration} ثانية"
    )


# ==========================
#  تشغيل البوت
# ==========================
print("Bot is running...")
bot.infinity_polling(skip_pending=True, timeout=60)
