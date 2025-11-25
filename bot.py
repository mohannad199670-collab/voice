import os
import json
import math
from io import BytesIO

import requests
import telebot
from telebot import types
from pydub import AudioSegment

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
        users[uid] = {
            "used": 0,          # الثواني المستخدمة
            "paid": 0,          # الثواني المدفوعة
            "username": username or "",
            "pending_plan": ""  # الخطة المختارة قبل الدفع
        }
        save_users(users)
    else:
        # تحديث اليوزرنيم إذا تغيّر
        if username:
            users[uid]["username"] = username
            save_users(users)
    return users


# ==========================
# لوحة البداية
# ==========================
def main_menu(is_admin: bool = False):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🎧 تفريغ صوت", "📄 الاشتراكات")
    kb.row("⚙️ الإعدادات", "📞 اتصل بنا")
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
        "🎙 يدعم العربية 100% (Whisper OpenAI).\n"
        "🎁 لديك 120 ثانية مجانية للتجربة.\n\n"
        "اختر من الأزرار بالأسفل أو أرسل مقطعًا صوتيًا مباشرة.",
        reply_markup=main_menu(is_admin=is_admin),
    )


# ==========================
# زر اتصل بنا
# ==========================
@bot.message_handler(func=lambda m: m.text == "📞 اتصل بنا")
def contact_us(message: telebot.types.Message):
    bot.send_message(
        message.chat.id,
        "للتواصل معنا عبر تيليجرام:\n\n@moh1ali96"
    )


# ==========================
# الاشتراكات
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
    # حفظ الخطة المختارة
    users[uid]["pending_plan"] = f"{minutes}"
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
# ⚙️ الإعدادات (للجميع) – ثواني + دقائق
# ==========================
FREE_LIMIT = 120  # 120 ثانية مجانية

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

    used_min = round(used / 60, 2)
    paid_min = round(paid / 60, 2)
    rem_min = round(remaining / 60, 2)

    base = (
        "⚙️ إعدادات حسابك:\n\n"
        f"🆔 ID: <code>{uid}</code>\n"
    )
    if username:
        base += f"👤 Username: @{username}"
    else:
        base += "👤 بدون Username"

    base += (
        f"\n\n⏱ الوقت المستخدم: {used} ثانية (≈ {used_min} دقيقة)"
        f"\n🎁 الوقت المدفوع المتاح: {paid} ثانية (≈ {paid_min} دقيقة)"
        f"\n✅ المجموع المتاح الآن: {remaining} ثانية (≈ {rem_min} دقيقة)"
    )

    if message.from_user.id == ADMIN_ID:
        base += "\n\n👑 أنت مدير البوت، يمكنك فتح 🛠 لوحة التحكم من الزر الخاص بذلك."

    bot.send_message(message.chat.id, base, parse_mode="HTML")


# ==========================
# لوحة تحكم الأدمن (زر مستقل)
# ==========================
ADMIN_STATE = {}  # لتخزين حالة إضافة الوقت


@bot.message_handler(func=lambda m: m.text == "🛠 لوحة التحكم")
def admin_menu(message: telebot.types.Message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ غير مسموح لك بالدخول هنا.")

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📊 الإحصائيات", "➕ إضافة وقت")
    kb.row("📃 عرض المستخدمين")
    kb.row("↩️ رجوع")

    bot.send_message(message.chat.id, "🔧 لوحة التحكم:", reply_markup=kb)


# زر رجوع
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


# 📊 الإحصائيات (ثواني + دقائق)
@bot.message_handler(func=lambda m: m.text == "📊 الإحصائيات")
def admin_stats(message: telebot.types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    users = load_users()
    total_users = len(users)
    total_used = sum(u.get("used", 0) for u in users.values())
    total_paid = sum(u.get("paid", 0) for u in users.values())

    total_used_min = round(total_used / 60, 2)
    total_paid_min = round(total_paid / 60, 2)

    text = (
        "📊 إحصائيات البوت:\n\n"
        f"👥 عدد المستخدمين: {total_users}\n"
        f"⏱ مجموع الوقت المستخدم: {total_used} ثانية (≈ {total_used_min} دقيقة)\n"
        f"🎁 مجموع الوقت المدفوع المسجَّل: {total_paid} ثانية (≈ {total_paid_min} دقيقة)"
    )

    bot.send_message(message.chat.id, text)


# 📃 عرض المستخدمين
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
        paid_min = round(paid / 60, 2)
        used_min = round(used / 60, 2)
        lines.append(
            f"🆔 {uid} – @{uname} – مدفوع: {paid}ث (≈ {paid_min}د) – مستخدم: {used}ث (≈ {used_min}د)"
        )

    txt = "\n".join(lines)
    bot.send_message(message.chat.id, txt)


# ➕ إضافة وقت – الخطوة الأولى
@bot.message_handler(func=lambda m: m.text == "➕ إضافة وقت")
def ask_user_id(message: telebot.types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    ADMIN_STATE[message.from_user.id] = {"step": 1, "uid": ""}

    bot.reply_to(message, "🆔 أرسل الآن ID المستخدم المراد إضافة وقت له:")


# نظام إضافة الوقت التفاعلي
@bot.message_handler(func=lambda m: m.from_user.id in ADMIN_STATE)
def process_add_time(message: telebot.types.Message):
    state = ADMIN_STATE[message.from_user.id]

    # STEP 1 → استلام ID
    if state["step"] == 1:
        uid = message.text.strip()
        users = load_users()
        if uid not in users:
            ADMIN_STATE.pop(message.from_user.id)
            return bot.reply_to(message, "❌ هذا المستخدم غير موجود في قاعدة البيانات.")

        state["uid"] = uid
        state["step"] = 2
        return bot.reply_to(message, "⏱ أرسل عدد الدقائق التي تريد إضافتها:")

    # STEP 2 → استلام الدقائق
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
            f"إجمالي الوقت المدفوع الآن: {users[uid]['paid']} ثانية.",
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
        plan_text = "باقة 60 دقيقة (5$)"
    elif pending_plan == "120":
        plan_text = "باقة 120 دقيقة (9$)"
    elif pending_plan == "300":
        plan_text = "باقة 300 دقيقة (20$)"

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
# 🔥 تفريغ الصوت باستخدام OpenAI Whisper
# + تقسيم الملف الكبير بـ pydub
# ==========================
MAX_PART_BYTES = 20 * 1024 * 1024   # الحد الأقصى لكل جزء ~20MB
MAX_PART_MINUTES = 10               # الحد الأقصى لمدة كل جزء (دقائق)


def split_audio_bytes(audio_bytes: bytes):
    """
    تقسيم الصوت إلى أجزاء إذا كان كبيرًا (حسب الحجم + المدة)
    يرجع: list[bytes], len_in_seconds
    """
    audio = AudioSegment.from_file(BytesIO(audio_bytes))
    duration_ms = len(audio)
    duration_sec = duration_ms / 1000.0
    duration_min = duration_ms / 60000.0

    n_by_size = max(1, math.ceil(len(audio_bytes) / MAX_PART_BYTES))
    n_by_time = max(1, math.ceil(duration_min / MAX_PART_MINUTES))
    parts_count = max(n_by_size, n_by_time)

    if parts_count <= 1:
        buf = BytesIO()
        audio.export(buf, format="mp3")
        buf.seek(0)
        return [buf.read()], duration_sec

    chunk_ms = math.ceil(duration_ms / parts_count)
    parts = []

    for i in range(parts_count):
        start = i * chunk_ms
        end = min((i + 1) * chunk_ms, duration_ms)
        if start >= end:
            continue
        chunk = audio[start:end]
        buf = BytesIO()
        chunk.export(buf, format="mp3")
        buf.seek(0)
        parts.append(buf.read())

    return parts, duration_sec


def transcribe_openai(audio_bytes: bytes) -> str | None:
    url = "https://api.openai.com/v1/audio/transcriptions"

    files = {
        "file": ("audio.mp3", audio_bytes, "audio/mpeg"),
        "model": (None, "whisper-1"),
        "response_format": (None, "text"),
        "language": (None, "ar"),  # تركيز على العربية
    }

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }

    try:
        r = requests.post(url, headers=headers, files=files, timeout=120)
        if r.status_code != 200:
            print("OpenAI error status:", r.status_code, r.text)
            return None
        return r.text
    except Exception as e:
        print("OpenAI error:", e)
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

    # حساب المدة من تيليجرام
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

    wait_msg = bot.reply_to(message, "⏳ جاري تحميل الملف من تيليجرام…")

    # تحميل الملف الأصلي
    try:
        file_info = bot.get_file(file_id)
        url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
        original_bytes = requests.get(url, timeout=300).content
    except Exception as e:
        print("Download error:", e)
        return bot.edit_message_text(
            "❌ حدث خطأ أثناء تحميل الملف من تيليجرام.",
            wait_msg.chat.id,
            wait_msg.message_id,
        )

    # تقسيم الصوت إذا لزم
    try:
        parts, real_duration_sec = split_audio_bytes(original_bytes)
    except Exception as e:
        print("Split error (fallback to single part):", e)
        parts = [original_bytes]
        real_duration_sec = duration

    parts_count = len(parts)

    if parts_count > 1:
        bot.edit_message_text(
            f"⏳ ملف كبير – تم تقسيمه إلى {parts_count} أجزاء.\n"
            "جاري التفريغ، يرجى الانتظار…",
            wait_msg.chat.id,
            wait_msg.message_id,
        )
    else:
        bot.edit_message_text(
            "⏳ جاري التفريغ عبر OpenAI Whisper…",
            wait_msg.chat.id,
            wait_msg.message_id,
        )

    full_text_parts = []
    for idx, part_bytes in enumerate(parts, start=1):
        part_text = transcribe_openai(part_bytes)
        if not part_text:
            full_text_parts.append(f"[الجزء {idx}] ❌ فشل التفريغ لهذا الجزء.")
        else:
            if parts_count > 1:
                full_text_parts.append(f"[الجزء {idx}]\n{part_text}")
            else:
                full_text_parts.append(part_text)

    final_text = "\n\n".join(full_text_parts).strip()

    if not final_text:
        return bot.edit_message_text(
            "❌ فشل التفريغ من OpenAI. تأكد من الرصيد أو الإعدادات.",
            wait_msg.chat.id,
            wait_msg.message_id,
        )

    # خصم الوقت (حسب مدة تيليجرام)
    users = load_users()
    users[uid]["used"] = users[uid].get("used", 0) + duration
    save_users(users)

    used_total = users[uid]["used"]
    used_min = round(used_total / 60, 2)

    bot.edit_message_text(
        f"✅ تم التفريغ بنجاح:\n\n{final_text}\n\n"
        f"⏱ المدة (من تيليجرام): {duration} ثانية.\n"
        f"🔢 المجموع المستخدم حتى الآن: {used_total} ثانية (≈ {used_min} دقيقة).",
        wait_msg.chat.id,
        wait_msg.message_id,
    )


# ==========================
# تشغيل البوت
# ==========================
print("Bot is running...")
bot.infinity_polling(skip_pending=True)
