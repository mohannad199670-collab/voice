import os
import json
import requests
import io
import time # للإنتظار في التفريغ الطويل
import telebot
from telebot import types
from pydub import AudioSegment # مكتبة تحويل الصوت
import tempfile # لحفظ الملفات المؤقتة

# مكتبات جوجل
from google.oauth2 import service_account
from google.cloud import speech_v1p1beta1 as speech
from google.cloud import storage # مكتبة التخزين السحابي

# ==========================
# المتغيرات من Koyeb
# ==========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # مثال: 604494923
GCP_SERVICE_ACCOUNT_JSON = os.getenv("GCP_SERVICE_ACCOUNT_JSON")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME") # <<<<<< متغير جديد

if not all([BOT_TOKEN, GCP_SERVICE_ACCOUNT_JSON, GCS_BUCKET_NAME]):
    raise RuntimeError(
        "❌ يجب ضبط BOT_TOKEN و GCP_SERVICE_ACCOUNT_JSON و GCS_BUCKET_NAME في إعدادات Koyeb"
    )

bot = telebot.TeleBot(BOT_TOKEN)

# ==========================
# تهيئة عملاء Google Cloud
# ==========================
# 1. تهيئة الـ Credentials
credentials_info = json.loads(GCP_SERVICE_ACCOUNT_JSON)
credentials = service_account.Credentials.from_service_account_info(credentials_info)

# 2. تهيئة Speech-to-Text Client
speech_client = speech.SpeechClient(credentials=credentials)

# 3. تهيئة Cloud Storage Client
storage_client = storage.Client(credentials=credentials)
bucket = storage_client.bucket(GCS_BUCKET_NAME)

# ==========================
# ملف تخزين المستخدمين (باقي الكود كما هو)
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
    # ... (الدالة كاملة كما هي)
    users = load_users()
    if uid not in users:
        users[uid] = {
            "used": 0,
            "paid": 0,
            "username": username or "",
            "pending_plan": ""
        }
        save_users(users)
    else:
        if username:
            users[uid]["username"] = username
            save_users(users)
    return users


# ==========================
# الدوال المساعدة
# ==========================
FREE_LIMIT = 120  # 120 ثانية مجانية


def seconds_to_minutes_str(seconds: int) -> str:
    minutes = seconds / 60.0 if seconds else 0
    return f"{seconds} ثانية ≈ {minutes:.2f} دقيقة"


# ==========================
# Google STT – دالة التفريغ الرئيسية
# ==========================
def transcribe_google(
    audio_data: bytes | str, # يمكن أن تكون بايتس أو رابط GCS
    is_long: bool,
    file_extension: str, # لا نحتاجه إذا كنا حولنا لـ FLAC
) -> str | None:
    """
    تفريغ باستخدام Google Speech-to-Text.
    تستخدم:
    - محتوى الملف (bytes) للتفريغ القصير (< 60 ثانية).
    - رابط GCS (str) للتفريغ الطويل (> 60 ثانية).
    """

    # نحدد الإعدادات العامة (الـ FLAC هو الأفضل والمدعوم للملفات الطويلة)
    config_kwargs = {
        "encoding": speech.RecognitionConfig.AudioEncoding.FLAC,
        "language_code": "ar-EG",
        "enable_automatic_punctuation": True,
        "model": "default", # يمكن استخدام 'video' للملفات الطويلة بجودة عالية
    }

    config = speech.RecognitionConfig(**config_kwargs)

    try:
        if is_long:
            # حالة التفريغ الطويل (ملف مرفوع على GCS)
            audio = speech.RecognitionAudio(uri=audio_data)
            operation = speech_client.long_running_recognize(
                config=config,
                audio=audio,
            )
            # ننتظر حتى تخلص العملية (مع استخدام فترة انتظار معقولة)
            response = operation.result(timeout=600) # انتظار 10 دقائق كحد أقصى

        else:
            # حالة التفريغ القصير (محتوى الملف مباشرة)
            audio = speech.RecognitionAudio(content=audio_data)
            response = speech_client.recognize(
                config=config,
                audio=audio,
            )

        texts = []
        for result in response.results:
            if result.alternatives:
                texts.append(result.alternatives[0].transcript)

        full_text = "\n".join(texts).strip()
        return full_text if full_text else None

    except Exception as e:
        print(f"Google STT error (is_long={is_long}):", e)
        return None

# ==========================
# دالة تحميل وتحويل الصوت
# ==========================
def download_and_convert(file_id: str, file_path_tele: str) -> tuple[bytes | None, str | None]:
    """
    تحميل الملف من التليجرام وتحويله إلى FLAC.
    """
    url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path_tele}"
    try:
        # 1. تحميل ملف التليجرام الأصلي
        original_audio_bytes = requests.get(url, timeout=600).content

        # 2. تحميل pydub للملف الأصلي
        if file_path_tele.lower().endswith(('.ogg', '.oga')):
            audio = AudioSegment.from_ogg(io.BytesIO(original_audio_bytes))
        elif file_path_tele.lower().endswith(('.mp3', '.m4a', '.mp4')):
            audio = AudioSegment.from_file(io.BytesIO(original_audio_bytes))
        else:
            # محاولة أخرى للتعامل مع ملفات صوت التليجرام (Voice)
            audio = AudioSegment.from_file(io.BytesIO(original_audio_bytes), format="ogg")

        # 3. حفظه مؤقتاً كـ FLAC في الذاكرة (أو ملف مؤقت إذا كان حجمه كبير جداً)
        output_buffer = io.BytesIO()
        audio.export(output_buffer, format="flac")
        output_buffer.seek(0)

        # 4. إعادة المحتوى المحول
        return output_buffer.read(), "flac"

    except Exception as e:
        print("Audio conversion/download error:", e)
        return None, None


# ==========================
# 🎧 تفريغ صوت - المعالج الجديد
# ==========================
@bot.message_handler(content_types=["voice", "audio"])
def handle_audio(message: telebot.types.Message):
    uid = str(message.from_user.id)
    username = message.from_user.username or ""
    ensure_user(uid, username)
    users = load_users()

    # حساب المدة
    duration = message.voice.duration if message.content_type == "voice" else message.audio.duration
    duration = duration or 0
    file_id = message.voice.file_id if message.content_type == "voice" else message.audio.file_id

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

    wait_msg = bot.reply_to(message, "⏳ جاري تحميل وتحويل الصوت إلى FLAC...")

    # 1. تحميل الملف من تيليجرام وتحويله لـ FLAC
    try:
        file_info = bot.get_file(file_id)
        audio_flac_bytes, file_ext = download_and_convert(file_id, file_info.file_path)
    except Exception as e:
        print("Get file info error:", e)
        return bot.edit_message_text(
            "❌ حدث خطأ أثناء تحميل الملف من تيليجرام.",
            wait_msg.chat.id,
            wait_msg.message_id,
        )

    if not audio_flac_bytes:
        return bot.edit_message_text(
            "❌ فشل تحويل الملف الصوتي إلى صيغة FLAC المطلوبة.",
            wait_msg.chat.id,
            wait_msg.message_id,
        )

    # 2. تحديد طريقة التفريغ
    is_long = duration > 60

    gcs_uri = None # لحفظ رابط GCS

    if is_long:
        bot.edit_message_text("⬆️ جاري رفع الملف على Google Cloud Storage...", wait_msg.chat.id, wait_msg.message_id)

        # 3. الرفع على Google Cloud Storage (للملفات الطويلة فقط)
        gcs_filename = f"stt_files/{uid}_{int(time.time())}.flac"
        blob = bucket.blob(gcs_filename)
        
        try:
            # الرفع
            blob.upload_from_string(audio_flac_bytes, content_type='audio/flac')
            gcs_uri = f"gs://{GCS_BUCKET_NAME}/{gcs_filename}"
            # نمرر الرابط للدالة
            audio_for_transcribe = gcs_uri
        except Exception as e:
            print("GCS Upload error:", e)
            return bot.edit_message_text(
                "❌ فشل رفع الملف إلى Google Cloud Storage.",
                wait_msg.chat.id,
                wait_msg.message_id,
            )
    else:
        # التفريغ القصير - نمرر البايتس مباشرة
        audio_for_transcribe = audio_flac_bytes

    # 4. تفريغ عبر Google
    bot.edit_message_text("⏳ جاري التفريغ عبر Google Speech-to-Text...", wait_msg.chat.id, wait_msg.message_id)

    text = transcribe_google(
        audio_data=audio_for_transcribe,
        is_long=is_long,
        file_extension="flac", # ثابت بعد التحويل
    )
    
    # 5. تنظيف الملف من GCS إذا كان ملف طويل
    if is_long and gcs_uri:
        try:
            blob.delete()
        except Exception as e:
            print("GCS Delete error:", e)
            # نستمر حتى لو فشل الحذف

    if not text:
        # لا نخصم أي وقت هنا
        return bot.edit_message_text(
            "❌ لم أستطع تفريغ الصوت. لن يتم خصم أي وقت من رصيدك.\n"
            "🔁 حاول مرة أخرى أو أرسل ملفًا آخر.",
            wait_msg.chat.id,
            wait_msg.message_id,
        )

    # 6. خصم الوقت فقط عند النجاح
    users = load_users()
    users[uid]["used"] = users[uid].get("used", 0) + duration
    save_users(users)

    # 7. إرسال النتيجة
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
# ... (باقي المعالجات والدوال مثل main_menu, cmd_start, admin_menu, إلخ... تبقى كما هي بالضبط)

@bot.message_handler(commands=["start"])
def cmd_start(message: telebot.types.Message):
    # ... (كما هي)
    uid = str(message.from_user.id)
    username = message.from_user.username or ""
    ensure_user(uid, username)
    is_admin = (message.from_user.id == ADMIN_ID)
    bot.send_message(
        message.chat.id,
        "👋 أهلاً بك في الأسطورة للتفريغ الصوتي!\n\n"
        "🎙 يعتمد على Google Speech-to-Text ويدعم العربية 100%.\n"
        f"🎁 لديك {FREE_LIMIT} ثانية مجانية للتجربة.\n\n"
        "اختر من الأزرار بالأسفل أو أرسل مقطعًا صوتيًا مباشرة.",
        reply_markup=main_menu(is_admin=is_admin),
    )


# [تابع إضافة جميع الدوال والمعالجات المتبقية هنا... مثل: contact_us, show_plans, payment_keyboard, admin_menu, إلخ...]


# ==========================
# تشغيل البوت (النهاية)
# ==========================
print("Bot is running...")
bot.infinity_polling(skip_pending=True, timeout=60)
