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
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # مثال: 604494923

if not BOT_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("❌ يجب ضبط BOT_TOKEN و OPENAI_API_KEY في إعدادات Koyeb")

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
        users[uid] = {"used": 0, "paid": 0, "username": username or ""}
        save_users(users)
    return users


# ==========================
# تخزين آخر باقة اختارها المستخدم
# ==========================
LAST_PLAN = {}  # مثال: LAST_PLAN[user_id] = 60


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
# /start
# ==========================
@bot.message_handler(commands=["start"])
def cmd_start(message):
    uid = str(message.from_user.id)
    username = message.from_user.username or ""
    ensure_user(uid, username)

    # إشعار الأدمن
    if ADMIN_ID:
        bot.send_message(
            ADMIN_ID,
            f"📩 مستخدم جديد استخدم /start\n"
            f"🆔 ID: <code>{uid}</code>\n"
            f"👤 Username: @{username}" if username else "👤 بدون Username",
            parse_mode="HTML"
        )

    bot.send_message(
        message.chat.id,
        "👋 أهلاً بك في الأسطورة للتفريغ الصوتي!\n\n"
        "🎙 يدعم اللغة العربية 100% باستخدام Whisper.\n"
        "🎁 لديك 120 ثانية مجانية للتجربة.\n\n"
        "اختر من الأزرار بالأسفل أو أرسل مقطعًا صوتيًا الآن.",
        reply_markup=main_menu(),
    )


# ==========================
# الاشتراكات
# ==========================
@bot.message_handler(func=lambda m: m.text == "📄 الاشتراكات")
def show_plans(message):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🕐 60 دقيقة – 5$", callback_data="plan_60"))
    kb.add(types.InlineKeyboardButton("🕑 120 دقيقة – 9$", callback_data="plan_120"))
    kb.add(types.InlineKeyboardButton("🕔 300 دقيقة – 20$", callback_data="plan_300"))
    bot.send_message(message.chat.id, "💳 اختر الباقة:", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data in ("plan_60", "plan_120", "plan_300"))
def on_plan_selected(call):
    plans_text = {
        "plan_60": ("اخترت باقة 60 دقيقة مقابل 5$.\n\nاختر طريقة الدفع:", 60),
        "plan_120": ("اخترت باقة 120 دقيقة مقابل 9$.\n\nاختر طريقة الدفع:", 120),
        "plan_300": ("اخترت باقة 300 دقيقة مقابل 20$.\n\nاختر طريقة الدفع:", 300),
    }

    text, minutes = plans_text[call.data]

    # 🔥 حفظ آخر باقة اختارها المستخدم
    LAST_PLAN[str(call.from_user.id)] = minutes

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=text,
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
# لوحة التحكم
# ==========================
@bot.message_handler(func=lambda m: m.text == "⚙️ الإعدادات")
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ هذا القسم للأدمن فقط.")

    users = load_users()
    total_users = len(users)
    total_used = sum(u["used"] for u in users.values())
    total_paid = sum(u["paid"] for u in users.values())

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📋 عرض المستخدمين")
    kb.row("🔄 تحديث")
    kb.row("⬅️ رجوع")

    bot.send_message(
        message.chat.id,
        "🛠 لوحة تحكم الأسطورة\n\n"
        f"👥 عدد المستخدمين: {total_users}\n"
        f"⏱ إجمالي الوقت المستخدم: {total_used} ثانية\n"
        f"🎁 الوقت المدفوع المتبقي (المجموع): {total_paid} ثانية\n\n"
        "اختر من الخيارات بالأسفل:",
        reply_markup=kb
    )


# ==========================
# عرض المستخدمين
# ==========================
@bot.message_handler(func=lambda m: m.text == "📋 عرض المستخدمين")
def show_users(message):
    if message.from_user.id != ADMIN_ID:
        return

    users = load_users()
    text = "📋 قائمة المستخدمين:\n\n"

    for uid, info in users.items():
        text += (
            f"🆔 {uid}\n"
            f"👤 @{info['username']}\n"
            f"⏱ المستخدم: {info['used']} ثانية\n"
            f"🎁 المدفوع: {info['paid']} ثانية\n\n"
        )

    bot.send_message(message.chat.id, text)


# ==========================
# أمر إضافة الوقت المبسط
# ==========================
@bot.message_handler(commands=["add_time"])
def add_time(message):
    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split()
    if len(parts) != 3:
        return bot.reply_to(message, "❌ الصيغة:\n/add_time user_id دقائق")

    uid = parts[1]
    minutes = int(parts[2])

    users = load_users()
    if uid not in users:
        return bot.reply_to(message, "❌ المستخدم غير موجود.")

    users[uid]["paid"] += minutes * 60
    save_users(users)

    bot.reply_to(message, f"✔ تمت إضافة {minutes} دقيقة للمستخدم.")


# ==========================
# 📸 إشعار الأدمن عند إرسال لقطة شاشة
# ==========================
@bot.message_handler(content_types=["photo"])
def handle_screenshot(message):
    uid = str(message.from_user.id)
    username = message.from_user.username or "بدون Username"

    minutes = LAST_PLAN.get(uid, "غير معروف")

    admin_msg = (
        "📸 استلمت لقطة شاشة لإثبات الدفع:\n\n"
        f"🆔 ID: <code>{uid}</code>\n"
        f"👤 Username: @{username}\n"
        f"⏱ الباقة المختارة: {minutes} دقيقة\n"
        "📥 الصورة بالأسفل:"
    )

    if ADMIN_ID:
        bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML")
        bot.send_photo(ADMIN_ID, message.photo[-1].file_id)

    bot.reply_to(message, "👌 تم استلام لقطة الشاشة، سيتم التفعيل قريبًا.")


# ==========================
# 🔥 تفريغ الصوت باستخدام Whisper
# ==========================
def transcribe_openai(audio_bytes: bytes):
    url = "https://api.openai.com/v1/audio/transcriptions"

    files = {
        "file": ("audio.mp3", audio_bytes, "audio/mpeg"),
        "model": (None, "whisper-1"),
        "response_format": (None, "text"),
    }

    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}

    try:
        r = requests.post(url, headers=headers, files=files)
        return r.text
    except Exception as e:
        print("OpenAI error:", e)
        return None


# ==========================
# 🎧 تفريغ صوت
# ==========================
FREE_LIMIT = 120

@bot.message_handler(func=lambda m: m.text == "🎧 تفريغ صوت")
def explain(message):
    bot.reply_to(message, "🎙 أرسل صوت الآن… لديك 120 ثانية مجانية.")

@bot.message_handler(content_types=["voice", "audio"])
def handle_audio(message):
    uid = str(message.from_user.id)
    users = ensure_user(uid, message.from_user.username or "")

    # المدة
    duration = (
        message.voice.duration if message.content_type == "voice"
        else message.audio.duration
    )

    # رصيد
    available = FREE_LIMIT + users[uid]["paid"] - users[uid]["used"]

    if duration > available:
        return bot.reply_to(message, f"❌ وقتك غير كافٍ. المتبقي: {available} ثانية.")

    wait_msg = bot.reply_to(message, "⏳ جاري التفريغ…")

    # تحميل الملف
    file_id = message.voice.file_id if message.content_type == "voice" else message.audio.file_id
    file_info = bot.get_file(file_id)
    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
    audio_bytes = requests.get(file_url).content

    # تفريغ
    text = transcribe_openai(audio_bytes)

    if not text:
        return bot.edit_message_text("❌ فشل التفريغ.", wait_msg.chat.id, wait_msg.message_id)

    users = load_users()
    users[uid]["used"] += duration
    save_users(users)

    bot.edit_message_text(
        f"✅ تم التفريغ بنجاح:\n\n{text}\n\n⏱ المدة: {duration} ثانية.",
        wait_msg.chat.id,
        wait_msg.message_id,
    )


# ==========================
# تشغيل البوت
# ==========================
print("Bot is running...")
bot.infinity_polling(skip_pending=True)
