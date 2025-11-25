import os
import json
import requests
import telebot
from telebot import types

# ==========================
# المتغيرات من Koyeb
# ==========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("❌ BOT_TOKEN و OPENAI_API_KEY مفقودان من المتغيرات.")

bot = telebot.TeleBot(BOT_TOKEN)

# ==========================
# ملف المستخدمين
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


def ensure_user(uid, username=""):
    users = load_users()
    if uid not in users:
        users[uid] = {"used": 0, "paid": 0, "username": username}
        save_users(users)
    return users


# ==========================
# لوحة البداية
# ==========================
def main_menu(is_admin=False):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)

    kb.row("🎧 تفريغ صوت", "📄 الاشتراكات")

    if is_admin:
        kb.row("🛠 لوحة التحكم")

    return kb


# ==========================
# بيانات الدفع
# ==========================
USDT_ADDR = "TRWu3vC1GRDwbEymaiPNjXbpUw4wmwSRYa"
PAYEER_ADDR = "P1058635648"

USDT_MESSAGE = f"USDT (TRC20)\n\n{USDT_ADDR}\n\nبعد الدفع أرسل لقطة شاشة."
PAYEER_MESSAGE = f"💰 Payeer:\n\n{PAYEER_ADDR}\n\nبعد الدفع أرسل لقطة شاشة."


def payment_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("USDT (TRC20)", callback_data="pay_usdt"))
    kb.add(types.InlineKeyboardButton("بايير", callback_data="pay_payeer"))
    return kb


# ==========================
# /start
# ==========================
@bot.message_handler(commands=["start"])
def start(message):
    uid = str(message.from_user.id)
    username = message.from_user.username or ""
    ensure_user(uid, username)

    # إشعار الأدمن
    if ADMIN_ID:
        txt = (
            "📥 مستخدم جديد استخدم /start\n"
            f"🆔 ID: {uid}\n"
            f"👤 Username: @{username}"
        )
        bot.send_message(ADMIN_ID, txt)

    bot.send_message(
        message.chat.id,
        "👋 أهلاً بك في الأسطورة للتفريغ الصوتي!\n\n"
        "🎙 Whisper يدعم العربية 100%.\n"
        "🎁 لديك 120 ثانية مجانية.\n\n"
        "اختر من الأزرار أو أرسل صوت مباشرة.",
        reply_markup=main_menu(is_admin=(message.from_user.id == ADMIN_ID)),
    )


# ==========================
# الاشتراكات
# ==========================
@bot.message_handler(func=lambda m: m.text == "📄 الاشتراكات")
def show_plans(message):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("60 دقيقة – 5$", callback_data="plan_60"))
    kb.add(types.InlineKeyboardButton("120 دقيقة – 9$", callback_data="plan_120"))
    kb.add(types.InlineKeyboardButton("300 دقيقة – 20$", callback_data="plan_300"))
    bot.send_message(message.chat.id, "💳 اختر الباقة:", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data.startswith("plan_"))
def plan_selected(call):
    plans = {
        "plan_60": ("60", 5),
        "plan_120": ("120", 9),
        "plan_300": ("300", 20),
    }

    minutes, price = plans[call.data]

    bot.edit_message_text(
        f"اخترت باقة {minutes} دقيقة مقابل {price}$.\n\nاختر طريقة الدفع:",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
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
# إرسال لقطة شاشة للشراء → يصل للأدمن
# ==========================
@bot.message_handler(content_types=["photo"])
def handle_payment_screenshot(message):
    uid = str(message.from_user.id)
    username = message.from_user.username or "بدون يوذنيم"

    caption = (
        "🧾 تم إرسال إثبات دفع جديد!\n\n"
        f"🆔 ID: {uid}\n"
        f"👤 Username: @{username}\n"
        "⚠️ لم يتم تحديد الباقة بعد – تحقق يدويًا."
    )

    bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=caption)
    bot.reply_to(message, "📨 تم إرسال لقطة الشاشة، سيتم التفعيل قريبًا.")


# ==========================
# لوحة تحكم الأدمن
# ==========================
@bot.message_handler(func=lambda m: m.text == "🛠 لوحة التحكم")
def admin_menu(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ غير مسموح.")

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📊 الإحصائيات", "➕ إضافة وقت")
    kb.row("📃 عرض المستخدمين")
    kb.row("↩️ رجوع")

    bot.send_message(message.chat.id, "🔧 لوحة التحكم:", reply_markup=kb)


# ==========================
# الإحصائيات
# ==========================
@bot.message_handler(func=lambda m: m.text == "📊 الإحصائيات")
def stats(message):
    if message.from_user.id != ADMIN_ID:
        return

    users = load_users()
    total_users = len(users)
    used = sum(u["used"] for u in users.values())
    paid = sum(u["paid"] for u in users.values())

    bot.send_message(
        message.chat.id,
        f"📊 إحصائيات البوت:\n\n"
        f"👥 عدد المستخدمين: {total_users}\n"
        f"⏱ الوقت المستخدم: {used} ثانية\n"
        f"🎁 الوقت المدفوع المتبقي: {paid} ثانية"
    )


# ==========================
# قائمة المستخدمين
# ==========================
@bot.message_handler(func=lambda m: m.text == "📃 عرض المستخدمين")
def list_users(message):
    if message.from_user.id != ADMIN_ID:
        return

    users = load_users()
    if not users:
        return bot.send_message(message.chat.id, "لا يوجد مستخدمون.")

    txt = "📃 قائمة المستخدمين:\n\n"
    for uid, data in users.items():
        txt += f"🆔 {uid} – @{data['username']} – مدفوع: {data['paid']} ثانية\n"

    bot.send_message(message.chat.id, txt)


# ==========================
# إضافة وقت (تفاعلي)
# ==========================
ADDING_TIME = {}


@bot.message_handler(func=lambda m: m.text == "➕ إضافة وقت")
def ask_user_id(message):
    if message.from_user.id != ADMIN_ID:
        return

    bot.reply_to(message, "🆔 أرسل ID المستخدم:")
    ADDING_TIME[message.from_user.id] = {"step": 1}


@bot.message_handler(func=lambda m: message.from_user.id in ADDING_TIME)
def add_time_process(message):
    data = ADDING_TIME[message.from_user.id]

    # الخطوة 1: استلام ID
    if data["step"] == 1:
        data["uid"] = message.text.strip()
        data["step"] = 2
        return bot.reply_to(message, "⏱ أرسل عدد الدقائق:")

    # الخطوة 2: استلام الدقائق
    elif data["step"] == 2:
        try:
            minutes = int(message.text.strip())
        except:
            return bot.reply_to(message, "❌ يجب أن يكون رقمًا.")

        uid = data["uid"]

        users = load_users()
        if uid not in users:
            ADDING_TIME.pop(message.from_user.id)
            return bot.reply_to(message, "❌ المستخدم غير موجود.")

        users[uid]["paid"] += minutes * 60
        save_users(users)

        bot.reply_to(
            message,
            f"✔️ تم إضافة {minutes} دقيقة للمستخدم {uid}."
        )

        ADDING_TIME.pop(message.from_user.id)


# ==========================
# رجوع
# ==========================
@bot.message_handler(func=lambda m: m.text == "↩️ رجوع")
def back(message):
    bot.send_message(
        message.chat.id,
        "🔙 رجوع للقائمة الرئيسية",
        reply_markup=main_menu(is_admin=(message.from_user.id == ADMIN_ID)),
    )


# ==========================
# Whisper تفريغ
# ==========================
def transcribe(audio_bytes):
    url = "https://api.openai.com/v1/audio/transcriptions"

    files = {
        "file": ("audio.mp3", audio_bytes, "audio/mpeg"),
        "model": (None, "whisper-1"),
        "response_format": (None, "text"),
    }

    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}

    r = requests.post(url, headers=headers, files=files)
    return r.text


# ==========================
# تفريغ صوت
# ==========================
FREE_LIMIT = 120


@bot.message_handler(func=lambda m: m.text == "🎧 تفريغ صوت")
def explain(message):
    bot.reply_to(message, "🎙 أرسل مقطع صوت الآن…")


@bot.message_handler(content_types=["voice", "audio"])
def handle_audio(message):
    uid = str(message.from_user.id)
    users = ensure_user(uid, message.from_user.username or "")

    # المدة
    duration = message.voice.duration if message.content_type == "voice" else message.audio.duration

    # تحقق من الرصيد
    available = FREE_LIMIT + users[uid]["paid"] - users[uid]["used"]

    if duration > available:
        return bot.reply_to(message, f"❌ وقتك غير كافٍ. المتبقي: {available} ثانية.")

    wait = bot.reply_to(message, "⏳ جارٍ التفريغ…")

    # تحميل الملف
    file_id = message.voice.file_id if message.content_type == "voice" else message.audio.file_id
    info = bot.get_file(file_id)
    audio_bytes = requests.get(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{info.file_path}").content

    # تفريغ
    text = transcribe(audio_bytes)

    # خصم الوقت
    users = load_users()
    users[uid]["used"] += duration
    save_users(users)

    bot.edit_message_text(
        f"✅ تم التفريغ:\n\n{text}\n\n⏱ المدة: {duration} ثانية",
        wait.chat.id,
        wait.message_id,
    )


# ==========================
# تشغيل البوت
# ==========================
print("Bot is running…")
bot.infinity_polling(skip_pending=True)
