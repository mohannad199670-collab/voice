import os
import json
import time
import requests
import telebot
from telebot import types

# ==========================
# المتغيرات من Koyeb
# ==========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # مثال: 604494923

if not BOT_TOKEN or not ASSEMBLYAI_API_KEY:
    raise RuntimeError("❌ يجب ضبط BOT_TOKEN و ASSEMBLYAI_API_KEY في إعدادات Koyeb")

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
            "pending_plan": ""  # الخطة المختارة قبل الدفع (60 أو 120 أو 300)
        }
        save_users(users)
    else:
        if username:  # تحديث اليوزرنيم عند تغيّره
            if users[uid].get("username") != username:
                users[uid]["username"] = username
                save_users(users)
    return users


# ==========================
# دوال مساعدة للتنسيق
# ==========================
def format_sec_min(seconds: int) -> str:
    """عرض الثواني + تقريب بالدقائق."""
    minutes = seconds // 60
    return f"{seconds} ثانية (~{minutes} دقيقة)"


# ==========================
# لوحة البداية
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
    "بعد الدفع يرجى إرسال لقطة شاشة هنا في محادثة البوت."
)

PAYEER_MESSAGE = (
    "💰 Payeer:\n\n"
    f"{PAYEER_ADDR}\n\n"
    "بعد الدفع يرجى إرسال لقطة شاشة هنا في محادثة البوت."
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
        "👋 أهلاً بك في <b>الأسطورة للتفريغ الصوتي</b>!\n\n"
        "🎙 يدعم العربية واكتشاف اللغة تلقائيًا عبر AssemblyAI.\n"
        "🎁 لديك <b>120 ثانية</b> مجانية للتجربة.\n\n"
        "اختر من الأزرار بالأسفل أو أرسل مقطعًا صوتيًا مباشرة.",
        reply_markup=main_menu(is_admin=is_admin),
        parse_mode="HTML"
    )


# ==========================
# زر تواصل معنا
# ==========================
@bot.message_handler(func=lambda m: m.text == "📞 تواصل معنا")
def contact_us(message: telebot.types.Message):
    bot.send_message(
        message.chat.id,
        "📨 للتواصل مع الإدارة:\n"
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
    mapping = {
        "plan_60": ("اخترت 60 دقيقة – 5$.\n\nاختر طريقة الدفع:", "60"),
        "plan_120": ("اخترت 120 دقيقة – 9$.\n\nاختر طريقة الدفع:", "120"),
        "plan_300": ("اخترت 300 دقيقة – 20$.\n\nاختر طريقة الدفع:", "300"),
    }

    text, minutes_str = mapping[call.data]

    uid = str(call.from_user.id)
    username = call.from_user.username or ""
    ensure_user(uid, username)

    users = load_users()
    if uid not in users:
        users[uid] = {"used": 0, "paid": 0, "username": username, "pending_plan": ""}
    users[uid]["pending_plan"] = minutes_str
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

    uname_part = f"👤 Username: @{username}" if username else "👤 بدون Username"

    text = (
        "⚙️ <b>إعدادات حسابك</b>:\n\n"
        f"🆔 ID: <code>{uid}</code>\n"
        f"{uname_part}\n\n"
        f"⏱ الوقت المستخدم: {format_sec_min(used)}\n"
        f"🎁 الوقت المدفوع المتاح: {format_sec_min(paid)}\n"
        f"✅ المجموع المتاح الآن: {format_sec_min(remaining)}"
    )

    if message.from_user.id == ADMIN_ID:
        text += "\n\n👑 أنت مدير البوت، يمكنك فتح <b>🛠 لوحة التحكم</b> من الزر الخاص."

    bot.send_message(message.chat.id, text, parse_mode="HTML")


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
    # لو الأدمن داخل عملية إضافة وقت → نحذف حالته
    if message.from_user.id in ADMIN_STATE:
        ADMIN_STATE.pop(message.from_user.id, None)

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
    total_used = sum(u.get("used", 0) for u in users.values())
    total_paid = sum(u.get("paid", 0) for u in users.values())
    total_remaining = sum(max(0, FREE_LIMIT + u.get("paid", 0) - u.get("used", 0)) for u in users.values())

    text = (
        "📊 <b>إحصائيات البوت</b>:\n\n"
        f"👥 عدد المستخدمين: {total_users}\n"
        f"⏱ مجموع الوقت المستخدم: {format_sec_min(total_used)}\n"
        f"🎁 مجموع الوقت المدفوع المسجَّل: {format_sec_min(total_paid)}\n"
        f"✅ مجموع الوقت المتاح للمستخدمين: {format_sec_min(total_remaining)}"
    )

    bot.send_message(message.chat.id, text, parse_mode="HTML")


# 📃 عرض المستخدمين
@bot.message_handler(func=lambda m: m.text == "📃 عرض المستخدمين")
def list_users(message: telebot.types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    users = load_users()
    if not users:
        return bot.send_message(message.chat.id, "📃 لا يوجد مستخدمون بعد.")

    lines = ["📃 <b>قائمة المستخدمين</b>:\n"]
    for uid, data in users.items():
        uname = data.get("username") or "بدون Username"
        paid = data.get("paid", 0)
        used = data.get("used", 0)
        lines.append(
            f"🆔 <code>{uid}</code> – @{uname}\n"
            f"   مدفوع: {format_sec_min(paid)} – مستخدم: {format_sec_min(used)}\n"
        )

    txt = "\n".join(lines)
    bot.send_message(message.chat.id, txt, parse_mode="HTML")


# ➕ إضافة وقت – الخطوة الأولى
@bot.message_handler(func=lambda m: m.text == "➕ إضافة وقت")
def ask_user_id(message: telebot.types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    ADMIN_STATE[message.from_user.id] = {"step": 1, "uid": ""}

    bot.reply_to(message, "🆔 أرسل الآن <b>ID المستخدم</b> المراد إضافة وقت له:", parse_mode="HTML")


# نظام إضافة الوقت التفاعلي
@bot.message_handler(func=lambda m: m.from_user.id in ADMIN_STATE)
def process_add_time(message: telebot.types.Message):
    state = ADMIN_STATE[message.from_user.id]

    # STEP 1 → استلام ID
    if state["step"] == 1:
        uid = message.text.strip()
        users = load_users()
        if uid not in users:
            ADMIN_STATE.pop(message.from_user.id, None)
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
            ADMIN_STATE.pop(message.from_user.id, None)
            return bot.reply_to(message, "❌ المستخدم اختفى من قاعدة البيانات!")

        users[uid]["paid"] = users[uid].get("paid", 0) + minutes * 60
        save_users(users)

        bot.send_message(
            message.chat.id,
            f"✔ تم إضافة {minutes} دقيقة للمستخدم {uid}.\n"
            f"إجمالي الوقت المدفوع الآن: {format_sec_min(users[uid]['paid'])}.",
        )

        # إزالة الحالة والعودة للوحة التحكم
        ADMIN_STATE.pop(message.from_user.id, None)

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
    minutes_int = 0
    if pending_plan == "60":
        plan_text = "باقة 60 دقيقة (5$)"
        minutes_int = 60
    elif pending_plan == "120":
        plan_text = "باقة 120 دقيقة (9$)"
        minutes_int = 120
    elif pending_plan == "300":
        plan_text = "باقة 300 دقيقة (20$)"
        minutes_int = 300

    # تنبيه المستخدم
    bot.reply_to(
        message,
        "📸 تم استلام لقطة الشاشة بنجاح.\n"
        "📩 سيتم مراجعة الدفع وتفعيل الباقة من قبل الإدارة في أقرب وقت."
    )

    # إرسال للأدمن
    if ADMIN_ID:
        uname_part = f"@{username}" if username else "بدون Username"
        caption = (
            "💳 <b>إشعار دفع جديد</b>:\n\n"
            f"🆔 ID: <code>{uid}</code>\n"
            f"👤 Username: {uname_part}\n"
            f"📦 الخطة المطلوبة: {plan_text}\n"
            f"⏱ عدد الدقائق في هذه الباقة: {minutes_int} دقيقة"
        )

        try:
            # إعادة توجيه لقطة الشاشة للأدمن
            bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
            # إرسال تفاصيل
            bot.send_message(ADMIN_ID, caption, parse_mode="HTML")
        except Exception as e:
            print("Forward error:", e)


# ==========================
# تفريغ الصوت – AssemblyAI
# ==========================
ASSEMBLYAI_TRANSCRIPT_URL = "https://api.assemblyai.com/v2/transcript"
ASSEMBLYAI_UPLOAD_URL = "https://api.assemblyai.com/v2/upload"

def assemblyai_transcribe_from_url(audio_url: str) -> str | None:
    """
    المحاولة الأولى: التفريغ عبر URL مباشرة (الخيار B).
    """
    headers = {
        "authorization": ASSEMBLYAI_API_KEY,
        "content-type": "application/json",
    }
    payload = {
        "audio_url": audio_url,
        "language_detection": True,
        "speaker_labels": False,
        "punctuate": True,
        "format_text": True,
    }

    try:
        resp = requests.post(ASSEMBLYAI_TRANSCRIPT_URL, json=payload, headers=headers, timeout=30)
        data = resp.json()
        if resp.status_code != 200 or "id" not in data:
            print("AssemblyAI URL start error:", resp.status_code, data)
            return None

        transcript_id = data["id"]

        # الاستعلام المتكرر حتى يكتمل
        while True:
            time.sleep(3)
            check = requests.get(f"{ASSEMBLYAI_TRANSCRIPT_URL}/{transcript_id}", headers=headers, timeout=30)
            result = check.json()
            status = result.get("status")
            if status == "completed":
                return result.get("text", "")
            if status == "error":
                print("AssemblyAI URL error:", result)
                return None
    except Exception as e:
        print("AssemblyAI URL exception:", e)
        return None


def assemblyai_transcribe_from_bytes(audio_bytes: bytes) -> str | None:
    """
    المحاولة الثانية: رفع الملف إلى AssemblyAI (الخيار A).
    """
    try:
        # 1) رفع الملف
        headers_upload = {
            "authorization": ASSEMBLYAI_API_KEY,
        }
        up_resp = requests.post(
            ASSEMBLYAI_UPLOAD_URL,
            headers=headers_upload,
            data=audio_bytes,
            timeout=600
        )
        if up_resp.status_code != 200:
            print("AssemblyAI upload error:", up_resp.status_code, up_resp.text)
            return None

        upload_url = up_resp.json().get("upload_url")
        if not upload_url:
            print("No upload_url from AssemblyAI upload")
            return None

        # 2) طلب التفريغ
        headers = {
            "authorization": ASSEMBLYAI_API_KEY,
            "content-type": "application/json",
        }
        payload = {
            "audio_url": upload_url,
            "language_detection": True,
            "speaker_labels": False,
            "punctuate": True,
            "format_text": True,
        }
        resp = requests.post(ASSEMBLYAI_TRANSCRIPT_URL, json=payload, headers=headers, timeout=30)
        data = resp.json()
        if resp.status_code != 200 or "id" not in data:
            print("AssemblyAI upload-start error:", resp.status_code, data)
            return None

        transcript_id = data["id"]

        while True:
            time.sleep(3)
            check = requests.get(f"{ASSEMBLYAI_TRANSCRIPT_URL}/{transcript_id}", headers=headers, timeout=30)
            result = check.json()
            status = result.get("status")
            if status == "completed":
                return result.get("text", "")
            if status == "error":
                print("AssemblyAI upload-run error:", result)
                return None

    except Exception as e:
        print("AssemblyAI upload exception:", e)
        return None


def transcribe_audio_assemblyai(file_url: str, audio_bytes: bytes) -> str | None:
    """
    دالة موحّدة:
    1) تحاول التفريغ عبر URL مباشرة (B).
    2) لو فشل، تحاول رفع الملف (A).
    """
    # أولاً: عبر الـ URL
    text = assemblyai_transcribe_from_url(file_url)
    if text:
        return text

    # ثانياً: رفع الملف
    text = assemblyai_transcribe_from_bytes(audio_bytes)
    return text


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

    # حساب المدة
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
            f"⏳ المتبقي: {format_sec_min(max(0, available))}.\n"
            "📄 يمكنك شراء باقة من قسم الاشتراكات."
        )

    wait_msg = bot.reply_to(message, "⏳ جاري التفريغ عبر AssemblyAI…")

    # 1) الحصول على رابط الملف من تيليجرام + تحميل البايتات
    try:
        file_info = bot.get_file(file_id)
        tg_file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
        audio_bytes = requests.get(tg_file_url, timeout=600).content
    except Exception as e:
        print("Download error:", e)
        return bot.edit_message_text(
            "❌ حدث خطأ أثناء تحميل الملف من تيليجرام.",
            wait_msg.chat.id,
            wait_msg.message_id,
        )

    # 2) تفريغ عبر AssemblyAI (URL أولًا ثم Upload)
    text = transcribe_audio_assemblyai(tg_file_url, audio_bytes)

    if not text:
        return bot.edit_message_text(
            "❌ فشل التفريغ من AssemblyAI. تأكد من الإعدادات أو جرّب لاحقًا.",
            wait_msg.chat.id,
            wait_msg.message_id,
        )

    # 3) خصم الوقت
    users = load_users()
    users[uid]["used"] = users[uid].get("used", 0) + duration
    save_users(users)

    bot.edit_message_text(
        f"✅ تم التفريغ بنجاح:\n\n{text}\n\n"
        f"⏱ مدة التسجيل: {format_sec_min(duration)}.\n"
        f"🔢 المجموع المستخدم حتى الآن: {format_sec_min(users[uid]['used'])}.",
        wait_msg.chat.id,
        wait_msg.message_id,
    )


# ==========================
# تشغيل البوت
# ==========================
print("Bot is running with AssemblyAI (URL + Upload fallback)...")
bot.infinity_polling(skip_pending=True)
