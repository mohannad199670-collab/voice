import telebot
from telebot import types
import os
import json
import time
import requests
from deepgram import Deepgram

# ==========================
# المتغيرات من Koyeb
# ==========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN or not DEEPGRAM_API_KEY:
    raise RuntimeError("❌ يجب ضبط BOT_TOKEN و DEEPGRAM_API_KEY في إعدادات Koyeb")

bot = telebot.TeleBot(BOT_TOKEN)
dg = Deepgram(DEEPGRAM_API_KEY)

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
# لوحة البداية
# ==========================
def main_menu():
    menu = types.ReplyKeyboardMarkup(resize_keyboard=True)
    menu.row("🎧 تفريغ صوت", "📄 الاشتراكات")
    menu.row("⚙️ الإعدادات")
    return menu

# ==========================
# طرق الدفع (بايير بدون سمايل)
# ==========================
def payment_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("USDT (TRC20) 🔥", callback_data="pay_usdt"),
        types.InlineKeyboardButton("بايير", callback_data="pay_payeer")
    )
    return kb

USDT_ADDR = "TRWu3vC1GRDwbEymaiPNjXbpUw4wmwSRYa"
PAYEER_ADDR = "P1058635648"

def payment_message():
    return (
        f"💵 طرق الدفع:\n\n"
        f"🔥 USDT (TRC20):\n`{USDT_ADDR}`\n\n"
        f"💰 Payeer:\n`{PAYEER_ADDR}`\n\n"
        f"بعد الدفع أرسل لقطة شاشة ليتم تفعيل الباقة."
    )

# ==========================
# /start
# ==========================
@bot.message_handler(commands=["start"])
def start(message):
    user_id = str(message.from_user.id)
    users = load_users()

    if user_id not in users:
        users[user_id] = {"used": 0, "paid": 0}
        save_users(users)

    bot.send_message(
        message.chat.id,
        "👋 أهلاً بك في الأسطورة للتفريغ الصوتي!\n"
        "🎙 يدعم العربية واللغات الأخرى تلقائياً.\n"
        "🎁 لديك دقيقتان مجاناً.",
        reply_markup=main_menu()
    )

# ==========================
# الاشتراكات
# ==========================
@bot.message_handler(func=lambda m: m.text == "📄 الاشتراكات")
def subs(message):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔘 باقة 60 دقيقة – 5$", callback_data="plan60"))
    bot.send_message(message.chat.id, "اختر الباقة:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "plan60")
def plan60(call):
    msg = (
        "اخترت باقة ٦٠ دقيقة.\nالسعر: **5$**.\n\n"
        "اختر طريقة الدفع:"
    )
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=msg,
        reply_markup=payment_keyboard(),
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda c: c.data == "pay_usdt")
def pay_usdt(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, payment_message(), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data == "pay_payeer")
def pay_payeer(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, payment_message(), parse_mode="Markdown")

# ==========================
# لوحة التحكم للأدمن
# ==========================
@bot.message_handler(func=lambda m: m.text == "⚙️ الإعدادات")
def settings(message):
    if message.from_user.id != ADMIN_ID:
        return bot.send_message(message.chat.id, "❌ غير مسموح")

    users = load_users()
    total_users = len(users)
    total_used = sum(u["used"] for u in users.values())
    total_paid = sum(u["paid"] for u in users.values())

    bot.send_message(
        message.chat.id,
        f"🛠 لوحة تحكم الأدمن\n\n"
        f"👥 عدد المستخدمين: {total_users}\n"
        f"⏱ الوقت المستخدم: {total_used} ثانية\n"
        f"🎁 الوقت المدفوع المتبقي: {total_paid} ثانية\n\n"
        f"لإضافة وقت:\n`/add_time user_id دقائق`\n"
        f"مثال:\n`/add_time 123456789 60`",
        parse_mode="Markdown"
    )

# ==========================
# إضافة وقت
# ==========================
@bot.message_handler(commands=["add_time"])
def addtime(message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        _, uid, mins = message.text.split()
        uid = str(uid)
        mins = int(mins)
    except:
        return bot.reply_to(message, "❌ صيغة خاطئة")

    users = load_users()

    if uid not in users:
        return bot.reply_to(message, "❌ المستخدم غير موجود")

    users[uid]["paid"] += mins * 60
    save_users(users)

    bot.reply_to(message, f"✔ تمت إضافة {mins} دقيقة للمستخدم.")

# ==========================
# استقبال الصوت + التفريغ
# ==========================
@bot.message_handler(content_types=["voice"])
def voice_handler(message):
    user_id = str(message.from_user.id)
    users = load_users()

    duration = message.voice.duration
    free_limit = 120
    paid = users[user_id]["paid"]
    used = users[user_id]["used"]
    available = free_limit + paid - used

    if duration > available:
        return bot.reply_to(message, "❌ ليس لديك وقت كافٍ.")

    bot.reply_to(message, "⏳ جاري التفريغ...")

    # تحميل الصوت
    file_info = bot.get_file(message.voice.file_id)
    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
    audio = requests.get(file_url).content

    # ========= Deepgram =========
    try:
        response = dg.transcription.prerecorded(
            {
                "buffer": audio,
                "mimetype": "audio/ogg"
            },
            {
                "punctuate": True,
                "model": "general",
                "language": "ar",
                "detect_language": True,
                "multilingual": True
            }
        )

        text = response["results"]["channels"][0]["alternatives"][0]["transcript"]

    except Exception as e:
        bot.reply_to(message, "❌ خطأ أثناء التفريغ.")
        print("Deepgram Error:", e)
        return
    # ============================

    users[user_id]["used"] += duration
    save_users(users)

    bot.send_message(
        message.chat.id,
        f"📄 النص المستخرج:\n{text}\n\n"
        f"⏱ تم احتساب {duration} ثانية"
    )

# ==========================
# تشغيل البوت
# ==========================
print("Bot is running...")
bot.infinity_polling(skip_pending=True, timeout=60)
