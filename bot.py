import os
import json
import requests
import telebot
from telebot import types

# ==========================
# المتغيرات من Koyeb
# ==========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GLADIA_API_KEY = os.getenv("GLADIA_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # مثال: 604494923

if not BOT_TOKEN or not GLADIA_API_KEY:
    raise RuntimeError("❌ يجب ضبط BOT_TOKEN و GLADIA_API_KEY في إعدادات Koyeb")

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
    " USDT (TRC20)\n\n"
    f"{USDT_ADDR}\n\n"
    "بعد الدفع يرجى إرسال لقطة شاشة."
)

PAYEER_MESSAGE = (
    "💰 Payeer:\n\n"
    f"{PAYEER_ADDR}\n\n"
    "بعد الدفع يرجى إرسال لقطة شاشة."
)

# ==========================
# رسالة ترحيب /start
# ==========================
@bot.message_handler(commands=["start"])
def cmd_start(message: telebot.types.Message):
    uid = str(message.from_user.id)
    username = message.from_user.username or ""
    users = ensure_user(uid, username)

    # تحديث اسم المستخدم
    users = load_users()
    users[uid]["username"] = username
    save_users(users)

    # إشعار الأدمن
    if ADMIN_ID:
        try:
            bot.send_message(
                ADMIN_ID,
                f"📥 مستخدم جديد /start\n"
                f"🆔 ID: <code>{uid}</code>\n"
                f"👤 Username: @{username}" if username else "👤 لا يوجد Username",
                parse_mode="HTML",
            )
        except:
            pass

    bot.send_message(
        message.chat.id,
        "👋 أهلاً بك في الأسطورة للتفريغ الصوتي!\n\n"
        "🎙 يدعم العربية واكتشاف اللغة تلقائيًا.\n"
        "🎁 لديك دقيقتان مجانًا للتجربة.\n\n"
        "اختر من الأزرار بالأسفل أو أرسل مقطعًا صوتيًا مباشرة.",
        reply_markup=main_menu(),
    )


# ==========================
# الاشتراكات
# ==========================
@bot.message_handler(func=lambda m: m.text == "📄 الاشتراكات")
def show_plans(message):
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("🕐 باقة 60 دقيقة – 5$", callback_data="plan_60"),
    )
    kb.add(
        types.InlineKeyboardButton("🕑 باقة 120 دقيقة – 9$", callback_data="plan_120"),
    )
    kb.add(
        types.InlineKeyboardButton("🕔 باقة 300 دقيقة – 20$", callback_data="plan_300"),
    )

    bot.send_message(message.chat.id, "💳 اختر الباقة المناسبة لك:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data in ("plan_60", "plan_120", "plan_300"))
def on_plan_selected(call):
    plans = {
        "plan_60": "اخترت باقة 60 دقيقة مقابل 5$.\n\nاختر طريقة الدفع:",
        "plan_120": "اخترت باقة 120 دقيقة مقابل 9$.\n\nاختر طريقة الدفع:",
        "plan_300": "اخترت باقة 300 دقيقة مقابل 20$.\n\nاختر طريقة الدفع:",
    }

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=plans[call.data],
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
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return bot.send_message(message.chat.id, "❌ غير مسموح لك بالدخول هنا.")

    users = load_users()
    total_users = len(users)
    total_used = sum(u.get("used", 0) for u in users.values())
    total_paid = sum(u.get("paid", 0) for u in users.values())

    bot.send_message(
        message.chat.id,
        f"🛠 لوحة تحكم الأدمن\n\n"
        f"👥 عدد المستخدمين: {total_users}\n"
        f"⏱ إجمالي الوقت المستخدم: {total_used} ثانية\n"
        f"🎁 إجمالي الوقت المدفوع المتبقي: {total_paid} ثانية\n\n"
        "لإضافة وقت:\n"
        "<code>/add_time user_id دقائق</code>",
        parse_mode="HTML",
    )


@bot.message_handler(commands=["add_time"])
def cmd_add_time(message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        _, uid, minutes = message.text.split()
        uid = str(uid)
        minutes = int(minutes)
    except:
        return bot.reply_to(
            message,
            "❌ صيغة خاطئة.\n"
            "<code>/add_time user_id دقائق</code>",
            parse_mode="HTML",
        )

    users = load_users()
    if uid not in users:
        return bot.reply_to(message, "❌ المستخدم غير موجود.")

    users[uid]["paid"] += minutes * 60
    save_users(users)

    bot.reply_to(
        message,
        f"✔ تمت إضافة {minutes} دقيقة.\n"
        f"الوقت الجديد: {users[uid]['paid']} ثانية.",
    )

# ==========================
# تفريغ الصوت – Gladia
# ==========================
def transcribe_audio(audio_bytes: bytes):
    """
    Gladia – يدعم العربية + اكتشاف اللغة
    """

    url = "https://api.gladia.io/audio/text/audio-transcription/"

    headers = {
        "x-gladia-key": GLADIA_API_KEY
    }

    files = {
        "audio": ("audio.ogg", audio_bytes, "audio/ogg")
    }

    data = {
        "language_behaviour": "auto",   # اكتشاف اللغة تلقائياً
        "toggle_diarization": "false",
        "toggle_noise_reduction": "true",
    }

    try:
        r = requests.post(url, headers=headers, data=data, files=files)
        result = r.json()
        return result["result"]["transcription"]
    except Exception as e:
        print("Gladia error:", e)
        return None


# ==========================
# 🎧 تفريغ صوت
# ==========================
FREE_LIMIT = 120  # 120 ثانية مجانا

@bot.message_handler(func=lambda m: m.text == "🎧 تفريغ صوت")
def explain_voice(message):
    bot.reply_to(
        message,
        "🎙 أرسل الآن مقطعًا صوتيًا أو ملفًا صوتيًا.\n"
        "🎁 لديك 120 ثانية مجانية."
    )


@bot.message_handler(content_types=["voice", "audio"])
def handle_audio(message):
    uid = str(message.from_user.id)
    username = message.from_user.username or ""
    users = ensure_user(uid, username)

    # تحديد المدة والملف
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
            f"❌ الوقت غير كافٍ.\n"
            f"⏳ المتبقي: {max(0, available)} ثانية.\n"
            "📄 اشترِ باقة لزيادة رصيدك."
        )

    wait_msg = bot.reply_to(message, "⏳ جاري التفريغ…")

    # تحميل الصوت
    try:
        file_info = bot.get_file(file_id)
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
        audio_bytes = requests.get(file_url).content
    except:
        return bot.edit_message_text(
            "❌ خطأ أثناء تحميل الصوت.",
            wait_msg.chat.id,
            wait_msg.message_id,
        )

    # Gladia – التفريغ
    text = transcribe_audio(audio_bytes)

    if not text:
        return bot.edit_message_text(
            "❌ لم أستطع تفريغ الصوت.",
            wait_msg.chat.id,
            wait_msg.message_id,
        )

    # خصم الوقت
    users = load_users()
    users[uid]["used"] += duration
    save_users(users)

    bot.edit_message_text(
        f"✅ تم التفريغ بنجاح!\n\n"
        f"📄 النص:\n{text}\n\n"
        f"⏱ مدة التسجيل: {duration} ثانية.\n"
        f"🔢 المجموع حتى الآن: {users[uid]['used']} ثانية.",
        wait_msg.chat.id,
        wait_msg.message_id,
    )


# ==========================
# تشغيل البوت
# ==========================
print("Bot is running...")
bot.infinity_polling(skip_pending=True)
