import os
import json
import time
import telebot
import requests
from pydub import AudioSegment
from telebot.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton

# -----------------------------
#  الإعدادات
# -----------------------------
ADMIN_ID = 604494923
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DEEPGRAM_KEY = os.getenv("DEEPGRAM_KEY")

if not TELEGRAM_TOKEN or not DEEPGRAM_KEY:
    raise RuntimeError("❌ يجب ضبط TELEGRAM_TOKEN و DEEPGRAM_KEY داخل Koyeb")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# -----------------------------
#  قاعدة البيانات
# -----------------------------
DB_FILE = "users.json"

def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    return json.load(open(DB_FILE, "r"))

def save_db(db):
    json.dump(db, open(DB_FILE, "w"), indent=2)

db = load_db()

# -----------------------------
#  مساعدات
# -----------------------------
def get_user(uid):
    if str(uid) not in db:
        db[str(uid)] = {
            "free_used": False,
            "minutes_left": 0,
            "total_used": 0
        }
        save_db(db)
    return db[str(uid)]

def notify_admin(text):
    try:
        bot.send_message(ADMIN_ID, text)
    except:
        pass

def format_user(user):
    name = user.first_name or "مجهول"
    uname = f"@{user.username}" if user.username else "بدون يوزر"
    return f"👤 الاسم: {name}\n🔗 اليوزر: {uname}\n🆔 الايدي: {user.id}"

# -----------------------------
#  رسالة الترحيب
# -----------------------------
def main_menu():
    mk = ReplyKeyboardMarkup(resize_keyboard=True)
    mk.row("🎧 تفريغ صوت")
    mk.row("💳 اشتراك", "⚙️ الإعدادات")
    return mk

WELCOME = (
    "🎉 أهلاً بك في *الأسطورة للتفريغ الصوتي*!\n\n"
    "🎧 المميزات:\n"
    "• دقيقتان مجاناً\n"
    "• دفع USDT TRC20 أو Payeer\n"
    "• اشتراكات حسب مدة الصوت (تفريغ حقيقي)\n"
    "• نظام احترافي للمشتركين\n\n"
    "اختر من القائمة بالأسفل 👇"
)

# -----------------------------
#  بدء التشغيل
# -----------------------------
@bot.message_handler(commands=["start"])
def start_cmd(msg):
    bot.send_message(msg.chat.id, WELCOME, reply_markup=main_menu(), parse_mode="Markdown")

    # إرسال بيانات المستخدم للأدمن
    notify_admin("🔥 مستخدم جديد:\n" + format_user(msg.from_user))

# -----------------------------
#  لوحة الإعدادات
# -----------------------------
@bot.message_handler(func=lambda m: m.text == "⚙️ الإعدادات")
def settings(msg):
    user = get_user(msg.from_user.id)
    txt = (
        f"⚙️ *إعدادات حسابك*\n\n"
        f"🆔 ID: `{msg.from_user.id}`\n"
        f"⏳ الدقائق المتبقية: {user['minutes_left']} دقيقة\n"
        f"🎧 تم تفريغ: {user['total_used']} دقيقة\n"
    )
    bot.send_message(msg.chat.id, txt, parse_mode="Markdown")

# -----------------------------
#  قائمة الاشتراكات
# -----------------------------
@bot.message_handler(func=lambda m: m.text == "💳 اشتراك")
def sub_menu(msg):
    mk = InlineKeyboardMarkup()
    mk.add(
        InlineKeyboardButton("⏱ 1 ساعة — 5$", callback_data="p1"),
        InlineKeyboardButton("⏱ 2 ساعة — 9$", callback_data="p2")
    )
    mk.add(
        InlineKeyboardButton("⏱ 5 ساعات — 20$", callback_data="p5")
    )
    mk.add(
        InlineKeyboardButton("طرق الدفع", callback_data="pay")
    )
    bot.send_message(msg.chat.id, "💳 اختر خطة الاشتراك:", reply_markup=mk)

# -----------------------------
#  طرق الدفع
# -----------------------------
@bot.callback_query_handler(func=lambda c: c.data == "pay")
def show_payment(c):
    txt = (
        "💰 *طرق الدفع المقبولة:*\n\n"
        "💎 USDT TRC20:\n"
        "`TRWu3vC1GRDwbEymaiPNjXbpUw4wmwSRYa`\n\n"
        "💳 Payeer:\n"
        "`P1058635648`\n\n"
        "📤 بعد الدفع: قم بإرسال لقطة الشاشة وسيتم تفعيل اشتراكك."
    )
    bot.send_message(c.message.chat.id, txt, parse_mode="Markdown")

# -----------------------------
#  تفعيل الخطة بعد الدفع (يدوياً من الأدمن)
# -----------------------------
@bot.message_handler(commands=["add"])
def add_time(msg):
    if msg.from_user.id != ADMIN_ID:
        return bot.send_message(msg.chat.id, "❌ هذا الأمر للمدير فقط")

    try:
        uid, minutes = msg.text.split()[1:]
        minutes = int(minutes)
    except:
        return bot.send_message(msg.chat.id, "❗ مثال:\n/add 123456789 60")

    user = get_user(uid)
    user["minutes_left"] += minutes
    save_db(db)

    bot.send_message(msg.chat.id, "✔ تم إضافة الوقت.")
    bot.send_message(int(uid), f"🎉 تم تفعيل اشتراكك!\n⏳ الرصيد المتبقي: {user['minutes_left']} دقيقة")

# -----------------------------
#  معالجة الصوت
# -----------------------------
@bot.message_handler(func=lambda m: m.text == "🎧 تفريغ صوت")
def ask_voice(msg):
    bot.send_message(msg.chat.id, "🎤 أرسل الآن المقطع الصوتي…")

@bot.message_handler(content_types=['voice', 'audio'])
def handle_audio(msg):
    uid = msg.from_user.id
    user = get_user(uid)

    notify_admin("🎧 صوت جديد من:\n" + format_user(msg.from_user))

    # تنزيل الصوت
    fid = msg.voice.file_id if msg.voice else msg.audio.file_id
    finfo = bot.get_file(fid)
    url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{finfo.file_path}"
    data = requests.get(url).content

    # حساب مدة الصوت
    temp = "temp.ogg"
    open(temp, "wb").write(data)
    audio = AudioSegment.from_file(temp)
    duration_sec = len(audio) // 1000
    duration_min = duration_sec / 60

    # نظام الدقيقتين المجانية
    if not user["free_used"]:
        user["free_used"] = True
        save_db(db)

        if duration_sec > 120:
            audio = audio[:120000]

        bot.send_message(msg.chat.id, "⏳ جاري التفريغ المجاني…")
    else:
        # يحتاج اشتراك
        needed = duration_sec // 60 + 1
        if user["minutes_left"] < needed:
            return bot.send_message(msg.chat.id, "❌ انتهى رصيدك.\n💳 اشترك لإكمال التفريغ.", reply_markup=main_menu())

        user["minutes_left"] -= needed
        user["total_used"] += needed
        save_db(db)
        bot.send_message(msg.chat.id, f"⏳ تم خصم {needed} دقيقة…")

    # إرسال الصوت إلى Deepgram
    headers = {
        "Authorization": f"Token {DEEPGRAM_KEY}",
        "Content-Type": "audio/ogg"
    }
    res = requests.post("https://api.deepgram.com/v1/listen", headers=headers, data=audio.export(format="ogg"))
    text = res.json().get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])[0].get("transcript")

    bot.send_message(msg.chat.id, f"📝 النص المستخرج:\n{text}")

# -----------------------------
#  تشغيل البوت
# -----------------------------
bot.infinity_polling()
