import os
import json
import requests
import telebot
from telebot import types

# ==========================
# المتغيرات من Koyeb
# ==========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "deepgram/whisper-large-v3")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN or not OPENROUTER_API_KEY:
    raise RuntimeError("❌ يجب ضبط BOT_TOKEN و OPENROUTER_API_KEY في إعدادات Koyeb")

bot = telebot.TeleBot(BOT_TOKEN)

# ==========================
# ملف تخزين المستخدمين
# ==========================
DATA_FILE = "users.json"

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f, ensure_ascii=False, indent=2)


def load_users():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_users(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def ensure_user(uid: str, username: str | None = None):
    users = load_users()
    if uid not in users:
        users[uid] = {
            "used": 0,
            "paid": 0,
            "username": username or ""
        }
        save_users(users)
    return users


# ==========================
# لوحة البداية
# ==========================
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🎧 تفريغ صوت", "📄 الاشتراكات")
    kb.row("⚙️ الإعدادات")
    return kb


# ==========================
# بيانات الدفع
# ==========================
USDT_ADDR = "TRWu3vC1GRDwbEymaiPNjXbpUw4wmwSRYa"
PAYEER_ADDR = "P1058635648"

def payment_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("USDT (TRC20)", callback_data="pay_usdt"),
        types.InlineKeyboardButton("بايير", callback_data="pay_payeer"),
    )
    return kb


USDT_MESSAGE = (
    "USDT (TRC20)\n\n"
    f"{USDT_ADDR}\n\n"
    "بعد الدفع يرجى إرسال لقطة شاشة."
)

PAYEER_MESSAGE = (
    "💰 Payeer:\n\n"
    f"{PAYEER_ADDR}\n\n"
    "بعد الدفع يرجى إرسال لقطة شاشة."
)


# ==========================
# رسالة /start
# ==========================
@bot.message_handler(commands=["start"])
def cmd_start(message):
    uid = str(message.from_user.id)
    username = message.from_user.username or ""
    ensure_user(uid, username)

    bot.send_message(
        message.chat.id,
        "👋 أهلاً بك في الأسطورة للتفريغ الصوتي!\n\n"
        "🎙 يدعم العربية + كشف اللغة تلقائي.\n"
        "🎁 لديك 120 ثانية مجانية.\n\n"
        "اختر من القائمة أو أرسل صوتًا مباشرة.",
        reply_markup=main_menu(),
    )


# ==========================
# الاشتراكات
# ==========================
@bot.message_handler(func=lambda m: m.text == "📄 الاشتراكات")
def show_plans(message):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🕐 باقة 60 دقيقة – 5$", callback_data="plan_60"))
    kb.add(types.InlineKeyboardButton("🕑 باقة 120 دقيقة – 9$", callback_data="plan_120"))
    kb.add(types.InlineKeyboardButton("🕔 باقة 300 دقيقة – 20$", callback_data="plan_300"))
    bot.send_message(message.chat.id, "💳 اختر الباقة:", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data in ("plan_60", "plan_120", "plan_300"))
def on_plan_selected(call):
    plans = {
        "plan_60": "اخترت باقة 60 دقيقة مقابل 5$.\n\nاختر طريقة الدفع:",
        "plan_120": "اخترت باقة 120 دقيقة مقابل 9$.\n\nاختر طريقة الدفع:",
        "plan_300": "اخترت باقة 300 دقيقة مقابل 20$.\n\nاختر طريقة الدفع:"
    }

    bot.edit_message_text(
        plans[call.data],
        call.message.chat.id,
        call.message.message_id,
        reply_markup=payment_keyboard(),
    )


@bot.callback_query_handler(func=lambda c: c.data == "pay_usdt")
def pay_usdt(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, USDT_MESSAGE)


@bot.callback_query_handler(func=lambda c: c.data == "pay_payeer")
def pay_payeer(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, PAYEER_MESSAGE)


# ==========================
# لوحة تحكم الأدمن
# ==========================
@bot.message_handler(func=lambda m: m.text == "⚙️ الإعدادات")
def panel(message):
    if message.from_user.id != ADMIN_ID:
        return bot.send_message(message.chat.id, "❌ غير مسموح.")

    users = load_users()
    total_users = len(users)
    total_used = sum(u["used"] for u in users.values())
    total_paid = sum(u["paid"] for u in users.values())

    bot.send_message(
        message.chat.id,
        f"🛠 لوحة التحكم\n\n"
        f"👥 المستخدمين: {total_users}\n"
        f"⏳ الوقت المستخدم: {total_used} ثانية\n"
        f"🎁 الوقت المدفوع المتبقي: {total_paid} ثانية\n\n"
        "لإضافة وقت:\n"
        "<code>/add_time user_id دقائق</code>",
        parse_mode="HTML",
    )


@bot.message_handler(commands=["add_time"])
def add_time(message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        _, uid, minutes = message.text.split()
        minutes = int(minutes)
    except:
        return bot.reply_to(message, "❌ صيغة غير صحيحة.")

    users = load_users()
    if uid not in users:
        return bot.reply_to(message, "❌ المستخدم غير موجود.")

    users[uid]["paid"] += minutes * 60
    save_users(users)

    bot.reply_to(message, f"✔ تمت إضافة {minutes} دقيقة.")


# ==========================
# OpenRouter تفريغ صوت
# ==========================
def transcribe_audio(audio_bytes: bytes) -> str | None:

    url = "https://openrouter.ai/api/v1/audio/transcriptions"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}"
    }

    files = {
        "file": ("audio.ogg", audio_bytes)
    }

    data = {
        "model": OPENROUTER_MODEL,
        "language": "ar",         # العربية
        "detect_language": True   # كشف تلقائي
    }

    try:
        r = requests.post(url, headers=headers, data=data, files=files)
        result = r.json()
        return result.get("text")
    except Exception as e:
        print("OpenRouter error:", e)
        return None


# ==========================
# 🎧 تفريغ صوت
# ==========================
FREE_LIMIT = 120

@bot.message_handler(func=lambda m: m.text == "🎧 تفريغ صوت")
def info(message):
    bot.reply_to(message, "🎙 أرسل مقطعًا صوتيًا الآن.\n🎁 لديك 120 ثانية مجانية.")


@bot.message_handler(content_types=["voice", "audio"])
def handle_audio(message):
    uid = str(message.from_user.id)
    username = message.from_user.username or ""
    users = ensure_user(uid, username)

    # معرفة المدة والملف
    if message.content_type == "voice":
        duration = message.voice.duration
        file_id = message.voice.file_id
    else:
        duration = message.audio.duration or 0
        file_id = message.audio.file_id

    used = users[uid]["used"]
    paid = users[uid]["paid"]

    available = FREE_LIMIT + paid - used

    if duration > available:
        return bot.reply_to(
            message,
            f"❌ الوقت غير كافٍ.\n⏳ المتبقي: {available} ثانية.\n"
            "📄 اشترِ باقة لزيادة الرصيد."
        )

    wait_msg = bot.reply_to(message, "⏳ جاري التفريغ…")

    # تحميل الملف من تيليجرام
    try:
        f = bot.get_file(file_id)
        url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{f.file_path}"
        audio_bytes = requests.get(url).content
    except:
        return bot.edit_message_text("❌ خطأ أثناء تحميل الصوت.", wait_msg.chat.id, wait_msg.message_id)

    # تفريغ الصوت
    text = transcribe_audio(audio_bytes)

    if not text:
        return bot.edit_message_text("❌ لم أستطع التفريغ.", wait_msg.chat.id, wait_msg.message_id)

    # تحديث الوقت
    users = load_users()
    users[uid]["used"] += duration
    save_users(users)

    bot.edit_message_text(
        f"✅ تم التفريغ بنجاح:\n\n"
        f"{text}\n\n"
        f"⏱ المدة: {duration} ثانية.\n"
        f"🔢 مجموع الاستخدام: {users[uid]['used']} ثانية.",
        wait_msg.chat.id,
        wait_msg.message_id,
    )


# ==========================
# تشغيل البوت
# ==========================
print("Bot is running...")
bot.infinity_polling(skip_pending=True, timeout=60)
