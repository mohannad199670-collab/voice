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
    raise RuntimeError("❌ BOT_TOKEN و OPENAI_API_KEY مطلوبان!")

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
# القائمة الرئيسية
# ==========================
def main_menu(is_admin=False):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🎧 تفريغ صوت", "📄 الاشتراكات")

    if is_admin:
        kb.row("🛠 لوحة التحكم")

    return kb

# ==========================
# /start
# ==========================
@bot.message_handler(commands=["start"])
def start(message):
    uid = str(message.from_user.id)
    ensure_user(uid, message.from_user.username or "")

    bot.send_message(
        message.chat.id,
        "👋 أهلاً بك في الأسطورة للتفريغ الصوتي!\n\n"
        "🎙 يدعم العربية 100% باستخدام Whisper.\n"
        "🎁 لديك 120 ثانية مجانية للتجربة.\n",
        reply_markup=main_menu(is_admin=(message.from_user.id == ADMIN_ID))
    )

# ==========================
# الاشتراكات
# ==========================
USDT_ADDR = "TRWu3vC1GRDwbEymaiPNjXbpUw4wmwSRYa"
PAYEER_ADDR = "P1058635648"

def payment_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("USDT (TRC20)", callback_data="pay_usdt"))
    kb.add(types.InlineKeyboardButton("بايير", callback_data="pay_payeer"))
    return kb

@bot.message_handler(func=lambda m: m.text == "📄 الاشتراكات")
def show_plans(message):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🕐 60 دقيقة – 5$", callback_data="plan_60"))
    kb.add(types.InlineKeyboardButton("🕑 120 دقيقة – 9$", callback_data="plan_120"))
    kb.add(types.InlineKeyboardButton("🕔 300 دقيقة – 20$", callback_data="plan_300"))

    bot.send_message(message.chat.id, "💳 اختر الباقة:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("plan_"))
def choose_plan(call):
    msg = {
        "plan_60": "اخترت 60 دقيقة – 5$.\nاختر طريقة الدفع:",
        "plan_120": "اخترت 120 دقيقة – 9$.\nاختر طريقة الدفع:",
        "plan_300": "اخترت 300 دقيقة – 20$.\nاختر طريقة الدفع:",
    }[call.data]

    bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=payment_keyboard())


@bot.callback_query_handler(func=lambda c: c.data == "pay_usdt")
def pay_usdt(call):
    bot.send_message(call.message.chat.id, f"USDT (TRC20):\n{USDT_ADDR}\n\n📸 أرسل لقطة شاشة بعد الدفع.")

@bot.callback_query_handler(func=lambda c: c.data == "pay_payeer")
def pay_payeer(call):
    bot.send_message(call.message.chat.id, f"💰 Payeer:\n{PAYEER_ADDR}\n\n📸 أرسل لقطة شاشة بعد الدفع.")

# ==========================
# نظام حالات الأدمن (STATE)
# ==========================
ADMIN_STATE = {}   # {admin_id: {step:1/2, uid:""}}

# ==========================
# لوحة التحكم
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
# زر رجوع
# ==========================
@bot.message_handler(func=lambda m: m.text == "↩️ رجوع")
def admin_back(message):
    if message.from_user.id in ADMIN_STATE:
        ADMIN_STATE.pop(message.from_user.id)

    bot.send_message(
        message.chat.id,
        "🔙 رجوع للقائمة الرئيسية",
        reply_markup=main_menu(is_admin=(message.from_user.id == ADMIN_ID)),
    )

# ==========================
# عرض المستخدمين
# ==========================
@bot.message_handler(func=lambda m: m.text == "📃 عرض المستخدمين")
def list_users(message):
    if message.from_user.id != ADMIN_ID:
        return

    users = load_users()
    txt = "📃 قائمة المستخدمين:\n\n"
    for uid, data in users.items():
        txt += f"🆔 {uid} – @{data['username']} – مدفوع: {data['paid']} ثانية\n"

    bot.send_message(message.chat.id, txt)

# ==========================
# إضافة وقت — الخطوة الأولى
# ==========================
@bot.message_handler(func=lambda m: m.text == "➕ إضافة وقت")
def ask_user_id(message):
    if message.from_user.id != ADMIN_ID:
        return

    ADMIN_STATE[message.from_user.id] = {"step": 1}

    bot.reply_to(message, "🆔 أرسل ID المستخدم الآن:")

# ==========================
# نظام إضافة الوقت – كامل
# ==========================
@bot.message_handler(func=lambda m: m.from_user.id in ADMIN_STATE)
def process_add_time(message):
    state = ADMIN_STATE[message.from_user.id]

    # STEP 1 → ID
    if state["step"] == 1:
        state["uid"] = message.text.strip()
        state["step"] = 2
        return bot.reply_to(message, "⏱ أرسل عدد الدقائق لإضافتها:")

    # STEP 2 → دقائق
    if state["step"] == 2:
        try:
            minutes = int(message.text)
        except:
            return bot.reply_to(message, "❌ أرسل رقمًا فقط.")

        uid = state["uid"]
        users = load_users()

        if uid not in users:
            ADMIN_STATE.pop(message.from_user.id)
            return bot.reply_to(message, "❌ المستخدم غير موجود.")

        users[uid]["paid"] += minutes * 60
        save_users(users)

        bot.send_message(
            message.chat.id,
            f"✔ تمت إضافة {minutes} دقيقة للمستخدم {uid}."
        )

        # إنهاء الحالة
        ADMIN_STATE.pop(message.from_user.id)

        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row("📊 الإحصائيات", "➕ إضافة وقت")
        kb.row("📃 عرض المستخدمين")
        kb.row("↩️ رجوع")

        return bot.send_message(message.chat.id, "🔧 عدت إلى لوحة التحكم.", reply_markup=kb)

# ==========================
# Whisper – تفريغ الصوت
# ==========================
FREE_LIMIT = 120

def transcribe_openai(audio_bytes):
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
    except:
        return None

# ==========================
# تفريغ صوت
# ==========================
@bot.message_handler(func=lambda m: m.text == "🎧 تفريغ صوت")
def explain(message):
    bot.reply_to(message, "🎙 أرسل مقطع صوتي الآن…")

@bot.message_handler(content_types=["voice", "audio"])
def handle_audio(message):
    uid = str(message.from_user.id)
    users = ensure_user(uid, message.from_user.username or "")

    duration = message.voice.duration if message.content_type == "voice" else message.audio.duration

    available = FREE_LIMIT + users[uid]["paid"] - users[uid]["used"]

    if duration > available:
        return bot.reply_to(message, f"❌ وقت غير كافٍ. المتبقي: {available} ثانية.")

    wait = bot.reply_to(message, "⏳ جاري التفريغ…")

    file_id = message.voice.file_id if message.content_type == "voice" else message.audio.file_id
    file_info = bot.get_file(file_id)
    url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
    audio_bytes = requests.get(url).content

    text = transcribe_openai(audio_bytes)

    if not text:
        return bot.edit_message_text("❌ لم أستطع تفريغ الصوت.", wait.chat.id, wait.message_id)

    users = load_users()
    users[uid]["used"] += duration
    save_users(users)

    bot.edit_message_text(
        f"✅ تم التفريغ:\n\n{text}\n\n⏱ المدة: {duration} ثانية.",
        wait.chat.id,
        wait.message_id,
    )

# ==========================
# تشغيل البوت
# ==========================
print("Bot is running…")
bot.infinity_polling(skip_pending=True)
