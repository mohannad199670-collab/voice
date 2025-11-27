import os
import json
import requests
import telebot
from telebot import types

# ==========================
# المتغيرات من Koyeb
# ==========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # مثال: 604494923

if not BOT_TOKEN or not DEEPGRAM_API_KEY:
    raise RuntimeError("❌ يجب ضبط BOT_TOKEN و DEEPGRAM_API_KEY في إعدادات Koyeb")

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
    إنشاء أو تحديث مستخدم في قاعدة البيانات.
    """
    users = load_users()
    if uid not in users:
        users[uid] = {
            "used": 0,          # الثواني المستخدمة
            "paid": 0,          # الثواني المدفوعة
            "username": username or "",
            "pending_plan": ""  # الخطة التي اختارها قبل إرسال لقطة الدفع
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

    # إشعار للأدمن عند دخول مستخدم جديد
    if ADMIN_ID and message.from_user.id != ADMIN_ID:
        try:
            uname_text = f"@{username}" if username else "بدون Username"
            bot.send_message(
                ADMIN_ID,
                f"📥 مستخدم جديد /start\n"
                f"🆔 ID: <code>{uid}</code>\n"
                f"👤 Username: {uname_text}",
                parse_mode="HTML",
            )
        except Exception:
            pass

    bot.send_message(
        message.chat.id,
        "👋 أهلاً بك في الأسطورة للتفريغ الصوتي!\n\n"
        "🎙 يعتمد على Deepgram (يدعم العربية والدقة العالية).\n"
        "🎁 لديك 120 ثانية مجانية للتجربة.\n\n"
        "اختر من الأزرار بالأسفل أو أرسل مقطعًا صوتيًا مباشرة.",
        reply_markup=main_menu(is_admin=is_admin),
    )


# ==========================
# 📞 اتصل بنا (للجميع + للأدمن)
# ==========================
@bot.message_handler(func=lambda m: m.text == "📞 اتصل بنا")
def contact_us(message: telebot.types.Message):
    bot.reply_to(
        message,
        "📩 للتواصل المباشر:\n"
        "@moh1ali96"
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

    # حفظ الخطة المختارة داخل pending_plan
    users = load_users()
    if uid not in users:
        users[uid] = {
            "used": 0,
            "paid": 0,
            "username": username,
            "pending_plan": ""
        }

    users[uid]["pending_plan"] = str(minutes)  # حفظ عدد الدقائق كـ نص
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
    """
    تحويل ثواني إلى نص بالدقائق (تقريب بسيط مع رقمين بعد الفاصلة).
    """
    minutes = seconds / 60.0
    return f"{minutes:.2f} دقيقة"


@bot.message_handler(func=lambda m: m.text == "⚙️ الإعدادات")
def user_settings(message: telebot.types.Message):
    uid = str(message.from_user.id)
    username = message.from_user.username or ""
    ensure_user(uid, username)

    users = load_users()
    data = users.get(uid, {"used": 0, "paid": 0})
    used = int(data.get("used", 0))
    paid = int(data.get("paid", 0))

    remaining = max(0, FREE_LIMIT + paid - used)

    uname_text = f"@{username}" if username else "بدون Username"

    text = (
        "⚙️ إعدادات حسابك:\n\n"
        f"🆔 ID: <code>{uid}</code>\n"
        f"👤 Username: {uname_text}\n\n"
        f"⏱ الوقت المستخدم: {used} ثانية = {seconds_to_minutes_str(used)}\n"
        f"🎁 الوقت المدفوع المتاح: {paid} ثانية = {seconds_to_minutes_str(paid)}\n"
        f"✅ المجموع المتاح الآن: {remaining} ثانية = {seconds_to_minutes_str(remaining)}"
    )

    if message.from_user.id == ADMIN_ID:
        text += "\n\n👑 أنت مدير البوت، يمكنك فتح 🛠 لوحة التحكم من الزر المخصص."

    bot.send_message(message.chat.id, text, parse_mode="HTML")


# ==========================
# لوحة تحكم الأدمن (زر مستقل)
# ==========================
ADMIN_STATE = {}  # لتخزين حالة إضافة الوقت التفاعلية


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
    # لو الأدمن داخل عملية إضافة وقت → نحذف حالته
    if message.from_user.id in ADMIN_STATE:
        ADMIN_STATE.pop(message.from_user.id)

    is_admin = (message.from_user.id == ADMIN_ID)
    bot.send_message(
        message.chat.id,
        "🔙 رجوع للقائمة الرئيسية",
        reply_markup=main_menu(is_admin=is_admin),
    )


# 📊 الإحصائيات
@bot.message_handler(func=lambda m: m.text == "📊 الإحصائيات")
def admin_stats(message: telebot.types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    users = load_users()
    total_users = len(users)
    total_used = sum(int(u.get("used", 0)) for u in users.values())
    total_paid = sum(int(u.get("paid", 0)) for u in users.values())
    total_available = FREE_LIMIT * total_users + total_paid - total_used
    if total_available < 0:
        total_available = 0

    text = (
        "📊 إحصائيات البوت:\n\n"
        f"👥 عدد المستخدمين: {total_users}\n\n"
        f"⏱ مجموع الوقت المستخدم: {total_used} ثانية = {seconds_to_minutes_str(total_used)}\n"
        f"🎁 مجموع الوقت المدفوع المسجَّل: {total_paid} ثانية = {seconds_to_minutes_str(total_paid)}\n"
        f"✅ المجموع المتاح (لجميع المستخدمين): {total_available} ثانية = {seconds_to_minutes_str(total_available)}"
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
        paid = int(data.get("paid", 0))
        used = int(data.get("used", 0))
        lines.append(
            f"🆔 {uid} – @{uname} – مدفوع: {paid} ث ({seconds_to_minutes_str(paid)}) – مستخدم: {used} ث ({seconds_to_minutes_str(used)})"
        )

    txt = "\n".join(lines)
    bot.send_message(message.chat.id, txt)


# ➕ إضافة وقت – فتح الخطوة من زر
@bot.message_handler(func=lambda m: m.text == "➕ إضافة وقت")
def ask_user_id(message: telebot.types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    ADMIN_STATE[message.from_user.id] = {"step": 1, "uid": ""}

    bot.reply_to(message, "🆔 أرسل الآن ID المستخدم المراد إضافة وقت له:")


# إضافة وقت من خلال /add_time أيضاً (يفتح نفس النظام التفاعلي)
@bot.message_handler(commands=["add_time"])
def add_time_cmd(message: telebot.types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    ADMIN_STATE[message.from_user.id] = {"step": 1, "uid": ""}
    bot.reply_to(message, "🆔 أرسل الآن ID المستخدم المراد إضافة وقت له:")


# نظام إضافة الوقت التفاعلي الكامل
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

        add_seconds = minutes * 60
        users[uid]["paid"] = users[uid].get("paid", 0) + add_seconds
        save_users(users)

        bot.send_message(
            message.chat.id,
            f"✔ تم إضافة {minutes} دقيقة ({add_seconds} ثانية) للمستخدم {uid}.\n"
            f"إجمالي الوقت المدفوع الآن: {users[uid]['paid']} ثانية = {seconds_to_minutes_str(users[uid]['paid'])}.",
        )

        # إزالة الحالة والعودة للوحة التحكم
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
    minutes_num = 0
    if pending_plan == "60":
        plan_text = "باقة 60 دقيقة (5$)"
        minutes_num = 60
    elif pending_plan == "120":
        plan_text = "باقة 120 دقيقة (9$)"
        minutes_num = 120
    elif pending_plan == "300":
        plan_text = "باقة 300 دقيقة (20$)"
        minutes_num = 300

    # تنبيه المستخدم
    bot.reply_to(
        message,
        "📸 تم استلام لقطة الشاشة بنجاح.\n"
        "📩 سيتم مراجعة الدفع وتفعيل الباقة من قبل الإدارة."
    )

    # إرسال للأدمن
    if ADMIN_ID:
        uname_text = f"@{username}" if username else "بدون Username"
        caption = (
            "💳 إشعار دفع جديد:\n\n"
            f"🆔 ID: <code>{uid}</code>\n"
            f"👤 Username: {uname_text}\n"
            f"📦 الخطة المطلوبة: {plan_text}\n"
            f"⏱ الدقائق المطلوبة: {minutes_num} دقيقة"
        )

        try:
            # إعادة توجيه لقطة الشاشة للأدمن
            bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
            # إرسال تفاصيل جانبية
            bot.send_message(ADMIN_ID, caption, parse_mode="HTML")
        except Exception as e:
            print("Forward error:", e)


# ==========================
# Deepgram REST API – التفريغ
# ==========================
def transcribe_deepgram(audio_bytes: bytes, mimetype: str = "audio/ogg") -> str | None:
    """
    تفريغ الصوت باستخدام Deepgram REST API
    يدعم العربية والملفات الكبيرة.
    """

    url = "https://api.deepgram.com/v1/listen"

    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": mimetype,
    }

    params = {
        "punctuate": "true",
        "model": "nova-2",          # نموذج قوي ودقيق
        "smart_format": "true",
        "language": "ar",           # تركيز على العربية
        "detect_language": "true",  # مع ذلك يسمح بالكشف
        "multilingual": "true",
    }

    try:
        resp = requests.post(url, headers=headers, params=params, data=audio_bytes, timeout=300)
        if resp.status_code != 200:
            print("Deepgram error:", resp.status_code, resp.text)
            return None

        data = resp.json()
        # استخراج النص
        return data["results"]["channels"][0]["alternatives"][0]["transcript"]
    except Exception as e:
        print("Deepgram exception:", e)
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

    # حساب المدة واختيار file_id
    if message.content_type == "voice":
        duration = message.voice.duration or 0
        file_id = message.voice.file_id
        # ملفات voice في تيليجرام غالباً تكون ogg/opus
        mimetype = "audio/ogg"
    else:
        duration = message.audio.duration or 0
        file_id = message.audio.file_id
        # نفترض mp3 إن لم نعرف
        mimetype = "audio/mpeg"

    used = int(users[uid].get("used", 0))
    paid = int(users[uid].get("paid", 0))
    available = FREE_LIMIT + paid - used

    if duration > available:
        return bot.reply_to(
            message,
            f"❌ وقتك غير كافٍ.\n"
            f"⏳ المتبقي: {max(0, available)} ثانية = {seconds_to_minutes_str(max(0, available))}.\n"
            "📄 يمكنك شراء باقة من قسم الاشتراكات."
        )

    wait_msg = bot.reply_to(message, "⏳ جاري التفريغ بواسطة Deepgram…")

    # تحميل الملف من تيليجرام
    try:
        file_info = bot.get_file(file_id)
        url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
        audio_bytes = requests.get(url, timeout=300).content
    except Exception as e:
        print("Download error:", e)
        return bot.edit_message_text(
            "❌ حدث خطأ أثناء تحميل الملف من تيليجرام.",
            wait_msg.chat.id,
            wait_msg.message_id,
        )

    # تفريغ بواسطة Deepgram
    text = transcribe_deepgram(audio_bytes, mimetype=mimetype)

    # ❗ مهم: لا نخصم الوقت إذا فشل التفريغ
    if not text:
        return bot.edit_message_text(
            "❌ لم أستطع تفريغ الصوت. لن يتم خصم أي وقت من رصيدك.\n"
            "🔁 حاول مرة أخرى أو أرسل ملفًا آخر.",
            wait_msg.chat.id,
            wait_msg.message_id,
        )

    # ✅ هنا فقط نخصم الوقت لأنه تم التفريغ بنجاح
    users = load_users()
    users[uid]["used"] = users[uid].get("used", 0) + duration
    save_users(users)

    bot.edit_message_text(
        f"✅ تم التفريغ بنجاح:\n\n"
        f"{text}\n\n"
        f"⏱ المدة: {duration} ثانية = {seconds_to_minutes_str(duration)}.\n"
        f"🔢 المجموع المستخدم حتى الآن: {users[uid]['used']} ثانية = {seconds_to_minutes_str(users[uid]['used'])}.",
        wait_msg.chat.id,
        wait_msg.message_id,
    )


# ==========================
# تشغيل البوت
# ==========================
print("Bot is running with Deepgram...")
bot.infinity_polling(skip_pending=True, timeout=60)
