import os
import json
import requests
import telebot
from telebot import types

# ==========================
# المتغيرات من Koyeb
# ==========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # مثال: 604494923

if not BOT_TOKEN or not GROQ_API_KEY:
    raise RuntimeError("❌ يجب ضبط BOT_TOKEN و GROQ_API_KEY في إعدادات Koyeb")

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
    """
    يتأكد أن المستخدم موجود في users.json
    ويحدّث اليوزرنيم إذا تغيّر.
    """
    users = load_users()
    if uid not in users:
        users[uid] = {
            "used": 0,          # الثواني المستخدمة
            "paid": 0,          # الثواني المدفوعة
            "username": username or "",
            "pending_plan": ""  # الخطة المطلوبة قبل الدفع (دقائق كنص: "60" أو "120"...)
        }
        save_users(users)
    else:
        if username:
            users[uid]["username"] = username
            save_users(users)
    return users


# ==========================
# لوحة البداية (القائمة الرئيسية)
# ==========================
def main_menu(is_admin: bool = False):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🎧 تفريغ صوت", "📄 الاشتراكات")
    kb.row("⚙️ الإعدادات", "📞 تواصل معنا")
    if is_admin:
        kb.row("🛠 لوحة التحكم")
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
    "بعد الدفع يرجى إرسال لقطة شاشة هنا في المحادثة مع البوت."
)

PAYEER_MESSAGE = (
    "💰 Payeer:\n\n"
    f"{PAYEER_ADDR}\n\n"
    "بعد الدفع يرجى إرسال لقطة شاشة هنا في المحادثة مع البوت."
)


# ==========================
# /start
# ==========================
@bot.message_handler(commands=["start"])
def cmd_start(message: telebot.types.Message):
    uid = str(message.from_user.id)
    username = message.from_user.username or ""
    ensure_user(uid, username)

    is_admin = (message.from_user.id == ADMIN_ID)

    bot.send_message(
        message.chat.id,
        "👋 أهلاً بك في الأسطورة للتفريغ الصوتي!\n\n"
        "🎙 يعتمد على Groq – موديل *whisper-large-v3* مع دعم ممتاز للعربية.\n"
        "🎁 لديك 120 ثانية مجانية للتجربة.\n\n"
        "اختر من الأزرار بالأسفل أو أرسل مقطعًا صوتيًا مباشرة.",
        reply_markup=main_menu(is_admin=is_admin),
        parse_mode="Markdown",
    )


# ==========================
# 📞 تواصل معنا
# ==========================
CONTACT_USERNAME = "@moh1ali96"


@bot.message_handler(func=lambda m: m.text == "📞 تواصل معنا")
def contact_us(message: telebot.types.Message):
    bot.send_message(
        message.chat.id,
        f"📞 للتواصل مع المطوّر:\n{CONTACT_USERNAME}"
    )


# ==========================
# 📄 الاشتراكات
# ==========================
@bot.message_handler(func=lambda m: m.text == "📄 الاشتراكات")
def show_plans(message: telebot.types.Message):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🕐 60 دقيقة – 5$", callback_data="plan_60"))
    kb.add(types.InlineKeyboardButton("🕑 120 دقيقة – 9$", callback_data="plan_120"))
    kb.add(types.InlineKeyboardButton("🕔 300 دقيقة – 20$", callback_data="plan_300"))

    bot.send_message(message.chat.id, "💳 اختر الباقة:", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data in ["plan_60", "plan_120", "plan_300"])
def plan_selected(call: telebot.types.CallbackQuery):
    plans_text = {
        "plan_60": ("اخترت 60 دقيقة – 5$.\n\nاختر طريقة الدفع:", 60),
        "plan_120": ("اخترت 120 دقيقة – 9$.\n\nاختر طريقة الدفع:", 120),
        "plan_300": ("اخترت 300 دقيقة – 20$.\n\nاختر طريقة الدفع:", 300),
    }

    text, minutes = plans_text[call.data]

    uid = str(call.from_user.id)
    username = call.from_user.username or ""
    ensure_user(uid, username)

    users = load_users()
    if uid not in users:
        users[uid] = {
            "used": 0,
            "paid": 0,
            "username": username,
            "pending_plan": ""
        }

    users[uid]["pending_plan"] = str(minutes)
    save_users(users)

    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=payment_keyboard(),
    )


@bot.callback_query_handler(func=lambda c: c.data == "pay_usdt")
def pay_usdt(call: telebot.types.CallbackQuery):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, USDT_MESSAGE)


@bot.callback_query_handler(func=lambda c: c.data == "pay_payeer")
def pay_payeer(call: telebot.types.CallbackQuery):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, PAYEER_MESSAGE)


# ==========================
# ⚙️ الإعدادات (للجميع)
# ==========================
FREE_LIMIT = 120  # 120 ثانية مجانية


def seconds_to_minutes_str(seconds: int) -> str:
    minutes = seconds / 60.0
    return f"{seconds} ثانية ≈ {minutes:.2f} دقيقة"


@bot.message_handler(func=lambda m: m.text == "⚙️ الإعدادات")
def user_settings(message: telebot.types.Message):
    uid = str(message.from_user.id)
    username = message.from_user.username or ""
    ensure_user(uid, username)
    users = load_users()
    data = users.get(uid, {"used": 0, "paid": 0})
    used = data.get("used", 0)
    paid = data.get("paid", 0)

    remaining = max(0, FREE_LIMIT + paid - used)

    header = (
        f"⚙️ إعدادات حسابك:\n\n"
        f"🆔 ID: <code>{uid}</code>\n"
    )
    if username:
        header += f"👤 Username: @{username}\n"
    else:
        header += "👤 بدون Username\n"

    text = header
    text += "\n"
    text += f"⏱ الوقت المستخدم: {seconds_to_minutes_str(used)}\n"
    text += f"🎁 الوقت المدفوع المتاح: {seconds_to_minutes_str(paid)}\n"
    text += f"✅ المجموع المتاح الآن: {seconds_to_minutes_str(remaining)}"

    if message.from_user.id == ADMIN_ID:
        text += "\n\n👑 أنت مدير البوت، يمكنك فتح 🛠 لوحة التحكم من الزر الخاص بذلك."

    bot.send_message(message.chat.id, text, parse_mode="HTML")


# ==========================
# لوحة تحكم الأدمن (زر مستقل)
# ==========================
ADMIN_STATE = {}  # لحالة إضافة الوقت التفاعلي للأدمن


@bot.message_handler(func=lambda m: m.text == "🛠 لوحة التحكم")
def admin_menu(message: telebot.types.Message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ غير مسموح لك بالدخول هنا.")

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📊 الإحصائيات", "➕ إضافة وقت")
    kb.row("📃 عرض المستخدمين")
    kb.row("↩️ رجوع")

    bot.send_message(message.chat.id, "🔧 لوحة التحكم:", reply_markup=kb)


@bot.message_handler(func=lambda m: m.text == "↩️ رجوع")
def admin_back(message: telebot.types.Message):
    if message.from_user.id in ADMIN_STATE:
        ADMIN_STATE.pop(message.from_user.id)

    is_admin = (message.from_user.id == ADMIN_ID)
    bot.send_message(
        message.chat.id,
        "🔙 رجوع للقائمة الرئيسية",
        reply_markup=main_menu(is_admin=is_admin),
    )


@bot.message_handler(func=lambda m: m.text == "📊 الإحصائيات")
def admin_stats(message: telebot.types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    users = load_users()
    total_users = len(users)
    total_used = sum(u.get("used", 0) for u in users.values())
    total_paid = sum(u.get("paid", 0) for u in users.values())

    text = (
        "📊 إحصائيات البوت:\n\n"
        f"👥 عدد المستخدمين: {total_users}\n"
        f"⏱ مجموع الوقت المستخدم: {seconds_to_minutes_str(total_used)}\n"
        f"🎁 مجموع الوقت المدفوع المسجَّل: {seconds_to_minutes_str(total_paid)}"
    )

    bot.send_message(message.chat.id, text)


@bot.message_handler(func=lambda m: m.text == "📃 عرض المستخدمين")
def list_users(message: telebot.types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    users = load_users()
    if not users:
        return bot.send_message(message.chat.id, "📃 لا يوجد مستخدمون بعد.")

    lines = ["📃 قائمة المستخدمين:\n"]
    for uid, data in users.items():
        uname = data.get("username") or "بدون Username"
        paid = data.get("paid", 0)
        used = data.get("used", 0)
        lines.append(
            f"🆔 {uid} – @{uname} – مدفوع: {paid} ث – مستخدم: {used} ث"
        )

    txt = "\n".join(lines)
    bot.send_message(message.chat.id, txt)


@bot.message_handler(func=lambda m: m.text == "➕ إضافة وقت")
def ask_user_id(message: telebot.types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    ADMIN_STATE[message.from_user.id] = {"step": 1, "uid": ""}

    bot.reply_to(message, "🆔 أرسل الآن ID المستخدم المراد إضافة وقت له:")


@bot.message_handler(func=lambda m: m.from_user.id in ADMIN_STATE, content_types=["text"])
def process_add_time(message: telebot.types.Message):
    state = ADMIN_STATE[message.from_user.id]

    if state["step"] == 1:
        uid = message.text.strip()
        users = load_users()
        if uid not in users:
            ADMIN_STATE.pop(message.from_user.id)
            return bot.reply_to(message, "❌ هذا المستخدم غير موجود في قاعدة البيانات!")

        state["uid"] = uid
        state["step"] = 2
        return bot.reply_to(message, "⏱ أرسل عدد الدقائق التي تريد إضافتها:")

    if state["step"] == 2:
        try:
            minutes = int(message.text.strip())
        except ValueError:
            return bot.reply_to(message, "❌ أرسل رقمًا صحيحًا لعدد الدقائق.")

        uid = state["uid"]
        users = load_users()
        if uid not in users:
            ADMIN_STATE.pop(message.from_user.id)
            return bot.reply_to(message, "❌ المستخدم اختفى من قاعدة البيانات!")

        users[uid]["paid"] = users[uid].get("paid", 0) + minutes * 60
        save_users(users)

        bot.send_message(
            message.chat.id,
            f"✔ تم إضافة {minutes} دقيقة للمستخدم {uid}.\n"
            f"إجمالي الوقت المدفوع الآن: {seconds_to_minutes_str(users[uid]['paid'])}.",
        )

        ADMIN_STATE.pop(message.from_user.id)

        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row("📊 الإحصائيات", "➕ إضافة وقت")
        kb.row("📃 عرض المستخدمين")
        kb.row("↩️ رجوع")
        return bot.send_message(message.chat.id, "🔧 عدت إلى لوحة التحكم.", reply_markup=kb)


# ==========================
# استقبال لقطات الشاشة (الدفع)
# ==========================
@bot.message_handler(content_types=["photo", "document"])
def handle_payment_screenshot(message: telebot.types.Message):
    uid = str(message.from_user.id)
    username = message.from_user.username or ""
    ensure_user(uid, username)
    users = load_users()
    data = users.get(uid, {})
    pending_plan = data.get("pending_plan", "")

    plan_text = "غير محددة"
    if pending_plan == "60":
        plan_text = "باقة 60 دقيقة (5$) – 60 دقيقة"
    elif pending_plan == "120":
        plan_text = "باقة 120 دقيقة (9$) – 120 دقيقة"
    elif pending_plan == "300":
        plan_text = "باقة 300 دقيقة (20$) – 300 دقيقة"

    bot.reply_to(
        message,
        "📸 تم استلام لقطة الشاشة بنجاح.\n"
        "📩 سيتم مراجعة الدفع وتفعيل الباقة من قبل الإدارة."
    )

    if ADMIN_ID:
        caption = (
            "💳 إشعار دفع جديد:\n\n"
            f"🆔 ID: <code>{uid}</code>\n"
        )
        if username:
            caption += f"👤 Username: @{username}\n"
        else:
            caption += "👤 بدون Username\n"

        caption += f"📦 الخطة المطلوبة: {plan_text}"

        try:
            bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
            bot.send_message(ADMIN_ID, caption, parse_mode="HTML")
        except Exception as e:
            print("Forward error:", e)


# ==========================
# Groq – whisper-large-v3
# ==========================
def transcribe_groq(audio_bytes: bytes) -> str | None:
    """
    تفريغ الصوت عبر Groq – موديل whisper-large-v3
    مع التركيز على اللغة العربية.
    """

    url = "https://api.groq.com/openai/v1/audio/transcriptions"

    files = {
        "file": ("audio.wav", audio_bytes, "audio/wav"),
        "model": (None, "whisper-large-v3"),
        "response_format": (None, "text"),
        "language": (None, "ar"),  # تركيز على العربية
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}"
    }

    try:
        resp = requests.post(url, headers=headers, files=files, timeout=600)
        if resp.status_code != 200:
            print("Groq error status:", resp.status_code, resp.text)
            return None
        return resp.text
    except Exception as e:
        print("Groq error:", e)
        return None


# ==========================
# 🎧 تفريغ صوت
# ==========================
@bot.message_handler(func=lambda m: m.text == "🎧 تفريغ صوت")
def explain(message: telebot.types.Message):
    bot.reply_to(
        message,
        "🎙 أرسل الآن مقطعًا صوتيًا (voice) أو ملفًا صوتيًا.\n"
        f"🎁 لديك {FREE_LIMIT} ثانية مجانية، وبعدها تحتاج لاشتراك."
    )


@bot.message_handler(content_types=["voice", "audio"])
def handle_audio(message: telebot.types.Message):
    uid = str(message.from_user.id)
    username = message.from_user.username or ""
    ensure_user(uid, username)
    users = load_users()

    if message.content_type == "voice":
        duration = message.voice.duration or 0
        file_id = message.voice.file_id
    else:
        duration = message.audio.duration or 0
        file_id = message.audio.file_id

    used = users[uid].get("used", 0)
    paid = users[uid].get("paid", 0)
    available = FREE_LIMIT + paid - used

    if duration > available:
        return bot.reply_to(
            message,
            f"❌ وقتك غير كافٍ.\n"
            f"⏳ المتبقي: {max(0, available)} ثانية.\n"
            "📄 يمكنك شراء باقة من قسم الاشتراكات."
        )

    wait_msg = bot.reply_to(message, "⏳ جاري التفريغ…")

    try:
        file_info = bot.get_file(file_id)
        url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
        audio_bytes = requests.get(url, timeout=600).content
    except Exception as e:
        print("Download error:", e)
        return bot.edit_message_text(
            "❌ حدث خطأ أثناء تحميل الملف من تيليجرام.",
            wait_msg.chat.id,
            wait_msg.message_id,
        )

    text = transcribe_groq(audio_bytes)

    if not text:
        return bot.edit_message_text(
            "❌ لم أستطع تفريغ الصوت. لن يتم خصم أي وقت من رصيدك.\n"
            "🔁 حاول مرة أخرى أو أرسل ملفًا آخر.",
            wait_msg.chat.id,
            wait_msg.message_id,
        )

    users = load_users()
    users[uid]["used"] = users[uid].get("used", 0) + duration
    save_users(users)

    bot.edit_message_text(
        f"✅ تم التفريغ بنجاح:\n\n{text}\n\n"
        f"⏱ المدة: {duration} ثانية ≈ {duration / 60.0:.2f} دقيقة.\n"
        f"🔢 المجموع المستخدم حتى الآن: {seconds_to_minutes_str(users[uid]['used'])}.",
        wait_msg.chat.id,
        wait_msg.message_id,
    )


# ==========================
# تشغيل البوت
# ==========================
print("Bot is running...")
bot.infinity_polling(skip_pending=True, timeout=60)
