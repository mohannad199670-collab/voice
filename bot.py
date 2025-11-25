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
        users[uid] = {
            "used": 0,      # الثواني المستخدمة
            "paid": 0,      # الثواني المدفوعة المتبقية
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
# /start
# ==========================
@bot.message_handler(commands=["start"])
def cmd_start(message: telebot.types.Message):
    uid = str(message.from_user.id)
    username = message.from_user.username or ""
    ensure_user(uid, username)

    # إشعار للأدمن بدخول مستخدم جديد
    if ADMIN_ID:
        try:
            if username:
                admin_text = (
                    "📥 مستخدم جديد استخدم /start\n"
                    f"🆔 ID: <code>{uid}</code>\n"
                    f"👤 Username: @{username}"
                )
            else:
                admin_text = (
                    "📥 مستخدم جديد استخدم /start\n"
                    f"🆔 ID: <code>{uid}</code>\n"
                    "👤 لا يوجد Username"
                )
            bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_text,
                parse_mode="HTML"
            )
        except Exception:
            pass

    bot.send_message(
        chat_id=message.chat.id,
        text=(
            "👋 أهلاً بك في الأسطورة للتفريغ الصوتي!\n\n"
            "🎙 يدعم العربية 100% باستخدام Whisper من OpenAI.\n"
            "🎁 لديك 120 ثانية مجانية للتجربة.\n\n"
            "اختر من الأزرار بالأسفل أو أرسل مقطعًا صوتيًا مباشرة."
        ),
        reply_markup=main_menu(),
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

    bot.send_message(
        chat_id=message.chat.id,
        text="💳 اختر الباقة:",
        reply_markup=kb
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("plan_"))
def plan_selected(call: telebot.types.CallbackQuery):
    if call.data == "plan_60":
        msg = "اخترت 60 دقيقة – 5$.\n\nاختر طريقة الدفع:"
    elif call.data == "plan_120":
        msg = "اخترت 120 دقيقة – 9$.\n\nاختر طريقة الدفع:"
    else:
        msg = "اخترت 300 دقيقة – 20$.\n\nاختر طريقة الدفع:"

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=msg,
        reply_markup=payment_keyboard(),
    )


@bot.callback_query_handler(func=lambda c: c.data == "pay_usdt")
def pay_usdt(call: telebot.types.CallbackQuery):
    bot.answer_callback_query(call.id)
    bot.send_message(
        chat_id=call.message.chat.id,
        text=USDT_MESSAGE
    )


@bot.callback_query_handler(func=lambda c: c.data == "pay_payeer")
def pay_payeer(call: telebot.types.CallbackQuery):
    bot.answer_callback_query(call.id)
    bot.send_message(
        chat_id=call.message.chat.id,
        text=PAYEER_MESSAGE
    )


# ==========================
# لوحة تحكم الأدمن (رئيسية)
# ==========================
@bot.message_handler(func=lambda m: m.text == "⚙️ الإعدادات")
def admin_panel(message: telebot.types.Message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ ليس لديك صلاحية الدخول إلى لوحة التحكم.")

    users = load_users()
    total_users = len(users)
    total_used = sum(u.get("used", 0) for u in users.values())
    total_paid = sum(u.get("paid", 0) for u in users.values())

    text = (
        "🛠 لوحة تحكم الأسطورة\n\n"
        f"👥 عدد المستخدمين: {total_users}\n"
        f"⏱ إجمالي الوقت المستخدم: {total_used} ثانية\n"
        f"🎁 الوقت المدفوع المتبقي (مجموع الجميع): {total_paid} ثانية\n\n"
        "اختر من الخيارات بالأسفل:"
    )

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📋 عرض المستخدمين", callback_data="show_users"))
    kb.add(types.InlineKeyboardButton("🔄 تحديث", callback_data="refresh_admin"))

    bot.send_message(
        chat_id=message.chat.id,
        text=text,
        reply_markup=kb
    )


# ==========================
# عرض جميع المستخدمين
# ==========================
@bot.callback_query_handler(func=lambda c: c.data == "show_users")
def admin_show_users(call: telebot.types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية.")

    users = load_users()

    if not users:
        return bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="❌ لا يوجد مستخدمين حتى الآن."
        )

    kb = types.InlineKeyboardMarkup()
    for uid, u in users.items():
        username = f"@{u['username']}" if u.get("username") else "بدون يوزر"
        kb.add(
            types.InlineKeyboardButton(
                f"{username} — {uid}",
                callback_data=f"user_{uid}"
            )
        )

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="📋 اختر مستخدم لعرض تفاصيله:",
        reply_markup=kb
    )


# ==========================
# تفاصيل مستخدم واحد
# ==========================
@bot.callback_query_handler(func=lambda c: c.data.startswith("user_"))
def admin_user_details(call: telebot.types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية.")

    uid = call.data.split("_")[1]
    users = load_users()

    if uid not in users:
        return bot.answer_callback_query(call.id, "❌ المستخدم غير موجود.")

    u = users[uid]
    username = f"@{u['username']}" if u.get("username") else "بدون يوزر"

    text = (
        f"👤 المستخدم: {username}\n"
        f"🆔 ID: `{uid}`\n\n"
        f"⏱ الوقت المستخدم: {u.get('used', 0)} ثانية\n"
        f"🎁 الوقت المدفوع المتبقي: {u.get('paid', 0)} ثانية\n\n"
        "🔧 خيارات التحكم:"
    )

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("➕ إضافة وقت", callback_data=f"addtime_{uid}"))
    kb.add(types.InlineKeyboardButton("🗑 حذف المستخدم", callback_data=f"deluser_{uid}"))
    kb.add(types.InlineKeyboardButton("⬅️ رجوع", callback_data="show_users"))

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=text,
        reply_markup=kb,
        parse_mode="Markdown"
    )


# ==========================
# اختيار مدة الإضافة
# ==========================
@bot.callback_query_handler(func=lambda c: c.data.startswith("addtime_"))
def admin_add_time_menu(call: telebot.types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية.")

    uid = call.data.split("_")[1]

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("30 دقيقة", callback_data=f"add_30_{uid}"))
    kb.add(types.InlineKeyboardButton("60 دقيقة", callback_data=f"add_60_{uid}"))
    kb.add(types.InlineKeyboardButton("120 دقيقة", callback_data=f"add_120_{uid}"))
    kb.add(types.InlineKeyboardButton("300 دقيقة", callback_data=f"add_300_{uid}"))
    kb.add(types.InlineKeyboardButton("⬅️ رجوع", callback_data=f"user_{uid}"))

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="⏱ اختر عدد الدقائق لإضافتها:",
        reply_markup=kb
    )


# ==========================
# تنفيذ الإضافة
# ==========================
@bot.callback_query_handler(func=lambda c: c.data.startswith("add_"))
def admin_add_time(call: telebot.types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية.")

    _, mins, uid = call.data.split("_")
    mins = int(mins)

    users = load_users()
    if uid not in users:
        return bot.answer_callback_query(call.id, "❌ المستخدم غير موجود.")

    users[uid]["paid"] = users[uid].get("paid", 0) + mins * 60
    save_users(users)

    bot.answer_callback_query(call.id, f"✔ تمت إضافة {mins} دقيقة.")
    # إعادة عرض تفاصيل المستخدم بعد التحديث
    admin_user_details(call)


# ==========================
# حذف مستخدم
# ==========================
@bot.callback_query_handler(func=lambda c: c.data.startswith("deluser_"))
def admin_delete_user(call: telebot.types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية.")

    uid = call.data.split("_")[1]
    users = load_users()

    if uid not in users:
        return bot.answer_callback_query(call.id, "❌ المستخدم غير موجود.")

    del users[uid]
    save_users(users)

    bot.answer_callback_query(call.id, "🗑 تم حذف المستخدم.")
    admin_show_users(call)


# ==========================
# تحديث لوحة التحكم
# ==========================
@bot.callback_query_handler(func=lambda c: c.data == "refresh_admin")
def admin_refresh(call: telebot.types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية.")
    # نستدعي لوحة التحكم من جديد
    admin_panel(call.message)


# ==========================
# /add_time (بسيط – يوجّه للأزرار)
# ==========================
@bot.message_handler(commands=["add_time"])
def add_time_cmd(message: telebot.types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    bot.reply_to(
        message,
        "ℹ️ لإضافة وقت لمستخدم استخدم:\n"
        "زر ⚙️ الإعدادات → 📋 عرض المستخدمين → اختر المستخدم → ➕ إضافة وقت."
    )


# ==========================
# تفريغ الصوت – OpenAI Whisper
# ==========================
def transcribe_openai(audio_bytes: bytes) -> str | None:
    """
    تفريغ الصوت باستخدام OpenAI Whisper عبر /audio/transcriptions
    مع تركيز على العربية.
    """
    url = "https://api.openai.com/v1/audio/transcriptions"

    files = {
        "file": ("audio.mp3", audio_bytes),
    }
    data = {
        "model": "whisper-1",      # نموذج Whisper
        "response_format": "text", # نريد نصاً مباشراً
        "language": "ar",          # تركيز على العربية
    }

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }

    try:
        resp = requests.post(url, headers=headers, files=files, data=data)
        if resp.status_code != 200:
            # طباعة الخطأ في اللوج فقط
            print("OpenAI error:", resp.text)
            return None
        return resp.text
    except Exception as e:
        print("OpenAI exception:", e)
        return None


# ==========================
# 🎧 تفريغ صوت
# ==========================
FREE_LIMIT = 120  # 120 ثانية مجانية

@bot.message_handler(func=lambda m: m.text == "🎧 تفريغ صوت")
def explain(message: telebot.types.Message):
    bot.reply_to(
        message,
        "🎙 أرسل الآن مقطعًا صوتيًا أو ملفًا صوتيًا.\n"
        f"🎁 لديك {FREE_LIMIT} ثانية مجانية.\n"
        "بعدها تحتاج للاشتراك من خلال قسم الاشتراكات."
    )


@bot.message_handler(content_types=["voice", "audio"])
def handle_audio(message: telebot.types.Message):
    uid = str(message.from_user.id)
    username = message.from_user.username or ""
    users = ensure_user(uid, username)

    # المدة
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
            f"❌ وقتك غير كافٍ.\n"
            f"⏱ المتبقي لك: {max(0, available)} ثانية.\n"
            "📄 اشترِ باقة من قسم الاشتراكات لزيادة رصيدك."
        )

    wait_msg = bot.reply_to(message, "⏳ جاري التفريغ باستخدام Whisper…")

    # تحميل الملف من تيليجرام
    try:
        file_info = bot.get_file(file_id)
        url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
        audio_bytes = requests.get(url).content
    except Exception as e:
        print("Download error:", e)
        bot.edit_message_text(
            chat_id=wait_msg.chat.id,
            message_id=wait_msg.message_id,
            text="❌ حدث خطأ أثناء تحميل الملف من تيليجرام."
        )
        return

    # تفريغ OpenAI
    text = transcribe_openai(audio_bytes)

    if not text:
        bot.edit_message_text(
            chat_id=wait_msg.chat.id,
            message_id=wait_msg.message_id,
            text="❌ فشل التفريغ من OpenAI. تأكد من رصيد الـ API أو حاول لاحقًا."
        )
        return

    # خصم الوقت
    users = load_users()
    users[uid]["used"] = users[uid].get("used", 0) + duration
    save_users(users)

    bot.edit_message_text(
        chat_id=wait_msg.chat.id,
        message_id=wait_msg.message_id,
        text=(
            f"✅ تم التفريغ بنجاح:\n\n"
            f"{text}\n\n"
            f"⏱ مدة التسجيل: {duration} ثانية.\n"
            f"🔢 المجموع المستخدم حتى الآن: {users[uid]['used']} ثانية."
        )
    )


# ==========================
# تشغيل البوت
# ==========================
print("Bot is running...")
bot.infinity_polling(skip_pending=True, timeout=60)
