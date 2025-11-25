import os
import sqlite3
import time
from datetime import datetime
import requests
import telebot

# =========================
# المتغيرات من Koyeb
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN or not DEEPGRAM_API_KEY:
    raise RuntimeError("❌ يجب ضبط BOT_TOKEN و DEEPGRAM_API_KEY في إعدادات Koyeb")

bot = telebot.TeleBot(BOT_TOKEN)

# =========================
# إعداد قاعدة البيانات
# =========================
DB_PATH = "voice_bot.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # جدول المستخدمين
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            total_used_seconds INTEGER DEFAULT 0,
            free_seconds_used INTEGER DEFAULT 0,
            paid_seconds_left INTEGER DEFAULT 0,
            created_at TEXT
        )
        """
    )

    # سجل الاستخدام
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS usage_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            duration_sec INTEGER,
            created_at TEXT
        )
        """
    )

    conn.commit()
    conn.close()


def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


init_db()

# إعدادات البوت
FREE_SECONDS = 120  # دقيقتان مجاناً
PLANS = {
    "60": {"minutes": 60, "price": 5},
    "120": {"minutes": 120, "price": 9},
    "300": {"minutes": 300, "price": 20},
}

USDT_ADDRESS = "TRWu3vC1GRDwbEymaiPNjXbpUw4wmwSRYa"
PAYEER_ACCOUNT = "P1058635648"


# =========================
# دوال مساعدة لقاعدة البيانات
# =========================
def ensure_user(user_id: int, username: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if not row:
        c.execute(
            """
            INSERT INTO users (user_id, username, created_at)
            VALUES (?, ?, ?)
            """,
            (user_id, username or "", datetime.utcnow().isoformat()),
        )
        conn.commit()
    else:
        # تحديث اسم المستخدم في حال تغيّر
        c.execute(
            "UPDATE users SET username = ? WHERE user_id = ?",
            (username or "", user_id),
        )
        conn.commit()
    conn.close()


def get_user_stats(user_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """
        SELECT total_used_seconds, free_seconds_used, paid_seconds_left
        FROM users WHERE user_id = ?
        """,
        (user_id,),
    )
    row = c.fetchone()
    conn.close()
    if not row:
        return {"total_used": 0, "free_used": 0, "paid_left": 0}
    return {"total_used": row[0], "free_used": row[1], "paid_left": row[2]}


def update_usage(user_id: int, duration_sec: int):
    """تحديث استخدام الوقت (مجاني + مدفوع)"""
    stats = get_user_stats(user_id)
    free_used = stats["free_used"]
    paid_left = stats["paid_left"]

    free_left = max(0, FREE_SECONDS - free_used)
    total_available = free_left + paid_left

    if total_available <= 0:
        return False, 0, 0  # لا يوجد وقت

    if duration_sec > total_available:
        return False, free_left, paid_left  # المقطع أطول من المتبقي

    use_from_free = min(duration_sec, free_left)
    use_from_paid = duration_sec - use_from_free

    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """
        UPDATE users
        SET
            total_used_seconds = total_used_seconds + ?,
            free_seconds_used = free_seconds_used + ?,
            paid_seconds_left = paid_seconds_left - ?
        WHERE user_id = ?
        """,
        (duration_sec, use_from_free, use_from_paid, user_id),
    )

    c.execute(
        """
        INSERT INTO usage_log (user_id, duration_sec, created_at)
        VALUES (?, ?, ?)
        """,
        (user_id, duration_sec, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()

    return True, use_from_free, use_from_paid


def add_paid_minutes(user_id: int, minutes: int):
    """يستخدمها الأدمن لإضافة باقة للمستخدم بالدقائق"""
    seconds = minutes * 60
    ensure_user(user_id, None)
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """
        UPDATE users
        SET paid_seconds_left = paid_seconds_left + ?
        WHERE user_id = ?
        """,
        (seconds, user_id),
    )
    conn.commit()
    conn.close()
    return seconds


def get_global_stats():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    users_count = c.fetchone()[0]

    c.execute("SELECT SUM(total_used_seconds) FROM users")
    total_used = c.fetchone()[0] or 0

    c.execute("SELECT SUM(paid_seconds_left) FROM users")
    total_paid_left = c.fetchone()[0] or 0

    conn.close()
    return users_count, total_used, total_paid_left


# =========================
# تفريغ الصوت عبر Deepgram
# =========================
def transcribe_with_deepgram(audio_bytes: bytes) -> str | None:
    url = "https://api.deepgram.com/v1/listen?detect_language=true&punctuate=true"
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "application/octet-stream",
    }

    try:
        resp = requests.post(url, headers=headers, data=audio_bytes, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        text = (
            data.get("results", {})
            .get("channels", [{}])[0]
            .get("alternatives", [{}])[0]
            .get("transcript", "")
        )
        return text.strip() or None
    except Exception as e:
        print("Deepgram error:", e)
        return None


# =========================
# لوحة المفاتيح الرئيسية
# =========================
def main_menu(is_admin=False):
    kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("تفريغ صوت 🎧")
    kb.row("الاشتراكات 🧾", "الإعدادات ⚙️")
    if is_admin:
        kb.row("لوحة التحكم 🛠")
    return kb


# =========================
# /start
# =========================
@bot.message_handler(commands=["start"])
def cmd_start(message: telebot.types.Message):
    user = message.from_user
    ensure_user(user.id, user.username)

    is_admin = user.id == ADMIN_ID
    uname = f"@{user.username}" if user.username else "لا يوجد"

    text = (
        "👋 أهلاً بك في *الأسطورة للتفريغ الصوتي* 🎙\n\n"
        "• يدعم العربية تلقائيًّا 🌍\n"
        f"• لديك دقيقتان مجاناً للتجربة 🎁\n\n"
        f"🪪 *ID:* `{user.id}`\n"
        f"👤 *Username:* {uname}\n\n"
        "اختر من القائمة بالأسفل أو أرسل مقطعاً صوتياً مباشرة."
    )

    bot.send_message(
        message.chat.id,
        text,
        parse_mode="Markdown",
        reply_markup=main_menu(is_admin),
    )


# =========================
# زر تفريغ صوت
# =========================
@bot.message_handler(func=lambda m: m.text == "تفريغ صوت 🎧")
def btn_voice(message: telebot.types.Message):
    bot.reply_to(message, "🎤 أرسل الآن المقطع الصوتي الذي تريد تفريغه.")


# =========================
# زر الاشتراكات
# =========================
@bot.message_handler(func=lambda m: m.text == "الاشتراكات 🧾")
def btn_subscriptions(message: telebot.types.Message):
    text_lines = ["💳 *خطط الاشتراك المتاحة:*"]
    for key, plan in PLANS.items():
        text_lines.append(
            f"- باقة مدة *{plan['minutes']} دقيقة* ⏱ — السعر: *{plan['price']}$*"
        )
    text_lines.append("\nاختر الباقة المناسبة لك من الأزرار بالأسفل:")

    markup = telebot.types.InlineKeyboardMarkup()
    for key, plan in PLANS.items():
        btn = telebot.types.InlineKeyboardButton(
            text=f"{plan['minutes']} دقيقة — {plan['price']}$",
            callback_data=f"plan_{key}",
        )
        markup.add(btn)

    bot.send_message(
        message.chat.id, "\n".join(text_lines), parse_mode="Markdown", reply_markup=markup
    )


# معالجة اختيار الباقة
@bot.callback_query_handler(func=lambda call: call.data.startswith("plan_"))
def cb_plan(call: telebot.types.CallbackQuery):
    plan_key = call.data.split("_", 1)[1]
    plan = PLANS.get(plan_key)
    if not plan:
        bot.answer_callback_query(call.id, "خطة غير معروفة.")
        return

    minutes = plan["minutes"]
    price = plan["price"]

    text = (
        f"✅ اخترت باقة مدة *{minutes} دقيقة*.\n"
        f"💵 السعر: *{price}$*\n\n"
        "اختر طريقة الدفع من الأزرار بالأسفل:"
    )

    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton(
            "👈🏻 بايير", callback_data=f"pay_payeer_{minutes}"
        ),
        telebot.types.InlineKeyboardButton(
            "USDT (TRC20)", callback_data=f"pay_usdt_{minutes}"
        ),
    )

    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown", reply_markup=markup)
    bot.answer_callback_query(call.id)


# طرق الدفع
@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
def cb_payment(call: telebot.types.CallbackQuery):
    parts = call.data.split("_")
    method = parts[1]  # payeer / usdt
    minutes = int(parts[2])

    if method == "payeer":
        pay_text = (
            "💳 *الدفع عبر Payeer*\n\n"
            f"الرجاء إرسال المبلغ الخاص بباقة *{minutes} دقيقة* إلى الحساب:\n"
            f"`{PAYEER_ACCOUNT}`\n\n"
            "بعد إتمام الدفع، أرسل لقطة شاشة لعملية الدفع هنا ليتم تفعيل باقتك بأسرع وقت ✅."
        )
    else:
        pay_text = (
            "🔥 *الدفع عبر USDT (TRC20)*\n\n"
            f"الرجاء إرسال المبلغ الخاص بباقة *{minutes} دقيقة* إلى العنوان:\n"
            f"`{USDT_ADDRESS}`\n\n"
            "بعد إتمام التحويل، أرسل لقطة شاشة لعملية الدفع هنا ليتم تفعيل الباقة ✅."
        )

    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, pay_text, parse_mode="Markdown")


# =========================
# زر الإعدادات
# =========================
@bot.message_handler(func=lambda m: m.text == "الإعدادات ⚙️")
def btn_settings(message: telebot.types.Message):
    user = message.from_user
    ensure_user(user.id, user.username)
    stats = get_user_stats(user.id)

    total_used = stats["total_used"]
    free_used = stats["free_used"]
    paid_left = stats["paid_left"]

    free_left = max(0, FREE_SECONDS - free_used)

    text = (
        "⚙️ *إعدادات الاشتراك:*\n\n"
        f"⏱ الوقت المستخدم الكلي: *{total_used} ثانية*\n"
        f"🎁 المجاني المتبقي: *{free_left} ثانية* من أصل *{FREE_SECONDS}*\n"
        f"💳 الوقت المدفوع المتبقي: *{paid_left} ثانية*"
    )

    bot.reply_to(message, text, parse_mode="Markdown")


# =========================
# لوحة التحكم للأدمن
# =========================
@bot.message_handler(func=lambda m: m.text == "لوحة التحكم 🛠" or m.text == "/admin")
def cmd_admin(message: telebot.types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    users_count, total_used, total_paid_left = get_global_stats()

    text = (
        "🛠 *لوحة تحكم الأدمن*\n\n"
        f"👥 عدد المستخدمين المسجلين: *{users_count}*\n"
        f"⏱ مجموع الوقت المستخدم: *{total_used} ثانية*\n"
        f"💳 مجموع الوقت المدفوع المتبقي: *{total_paid_left} ثانية*\n\n"
        "لإضافة وقت لمستخدم استخدم الأمر:\n"
        "`/add_time user_id دقائق`\n"
        "مثال:\n"
        "`/add_time 123456789 60`  ➜ يضيف 60 دقيقة."
    )

    bot.reply_to(message, text, parse_mode="Markdown")


@bot.message_handler(commands=["add_time"])
def cmd_add_time(message: telebot.types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        parts = message.text.split()
        if len(parts) != 3:
            bot.reply_to(
                message,
                "❌ الصيغة غير صحيحة.\nاستعمل:\n`/add_time user_id دقائق`",
                parse_mode="Markdown",
            )
            return

        user_id = int(parts[1])
        minutes = int(parts[2])

        seconds_added = add_paid_minutes(user_id, minutes)
        bot.reply_to(
            message,
            f"✅ تمت إضافة *{minutes} دقيقة* (أي {seconds_added} ثانية) للمستخدم `{user_id}`.",
            parse_mode="Markdown",
        )

        # إعلام المستخدم لو كان في الخاص
        try:
            bot.send_message(
                user_id,
                f"✅ تم تفعيل/تجديد باقتك بإضافة *{minutes} دقيقة*.\n"
                "يمكنك الآن إرسال المقاطع الصوتية للتفريغ.",
                parse_mode="Markdown",
            )
        except Exception:
            pass

    except Exception as e:
        print("add_time error:", e)
        bot.reply_to(message, "حدث خطأ أثناء تنفيذ الأمر.")


# =========================
# معالجة الصوت (تفريغ مباشر)
# =========================
@bot.message_handler(content_types=["voice", "audio"])
def handle_voice(message: telebot.types.Message):
    user = message.from_user
    ensure_user(user.id, user.username)

    # مدة المقطع
    duration = 0
    if message.voice:
        duration = message.voice.duration
        file_id = message.voice.file_id
    else:
        duration = getattr(message.audio, "duration", 0) or 0
        file_id = message.audio.file_id

    if duration <= 0:
        bot.reply_to(message, "⚠️ لم أستطع قراءة مدة المقطع الصوتي.")
        return

    stats = get_user_stats(user.id)
    free_left = max(0, FREE_SECONDS - stats["free_used"])
    paid_left = stats["paid_left"]
    total_available = free_left + paid_left

    if total_available <= 0:
        bot.reply_to(
            message,
            "⛔ انتهى وقتك المتاح للتفريغ.\n"
            "الرجاء الاشتراك في إحدى الباقات من زر *الاشتراكات 🧾*.",
            parse_mode="Markdown",
        )
        return

    if duration > total_available:
        bot.reply_to(
            message,
            f"⛔ مدة المقطع (*{duration} ثانية*) أكبر من الوقت المتبقي لديك (*{total_available} ثانية*).\n"
            "الرجاء الاشتراك في باقة إضافية أو إرسال مقطع أقصر.",
            parse_mode="Markdown",
        )
        return

    bot.reply_to(message, "⏳ جاري تفريغ المقطع الصوتي…")

    # تحميل الملف من تيليجرام
    try:
        file_info = bot.get_file(file_id)
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
        audio_bytes = requests.get(file_url).content
    except Exception as e:
        print("Download error:", e)
        bot.reply_to(message, "❌ حدث خطأ أثناء تحميل الصوت من تيليجرام.")
        return

    # طلب التفريغ من Deepgram
    text = transcribe_with_deepgram(audio_bytes)
    if not text:
        bot.reply_to(message, "❌ لم أستطع تفريغ هذا المقطع، حاول مرة أخرى لاحقاً.")
        return

    # تحديث الاستخدام
    ok, used_free, used_paid = update_usage(user.id, duration)
    if not ok:
        # لو صار تعارض بعد التحقق (نادر جداً)
        bot.reply_to(
            message,
            "❌ حدث خطأ أثناء حساب الوقت. حاول مرة أخرى أو راجع الاشتراك.",
        )
        return

    # إرسال النتيجة
    response = (
        "🎙 *مقطع صوتي*\n\n"
        "📄 *النص المستخرج:*\n"
        f"{text}\n\n"
        "⏱ تم احتساب:\n"
        f"• من المجاني: *{used_free} ثانية*\n"
        f"• من المدفوع: *{used_paid} ثانية*"
    )

    bot.reply_to(message, response, parse_mode="Markdown")


# =========================
# أي رسائل أخرى
# =========================
@bot.message_handler(func=lambda m: True, content_types=["text"])
def fallback(message: telebot.types.Message):
    # للمستخدم العادي
    if message.text.startswith("/"):
        return
    cmd_start(message)


# =========================
# تشغيل البوت
# =========================
print("Bot is running...")
bot.infinity_polling(skip_pending=True, timeout=60)
