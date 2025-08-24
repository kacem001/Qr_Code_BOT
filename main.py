

import logging
import io
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
import qrcode
import cv2
from pyzbar.pyzbar import decode
import numpy as np

# --- Configuration ---
# تم قراءة التوكن من متغير البيئة BOT_TOKEN
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# --- Setup Logging ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Conversation States ---
# تم تصحيح الخطأ هنا: تغيير range(14) إلى range(16)
(
    SELECTING_ACTION,
    AWAITING_SINGLE_INPUT,
    # WiFi States
    AWAITING_WIFI_SSID, AWAITING_WIFI_PASS, AWAITING_WIFI_ENCRYPTION,
    # Contact States
    AWAITING_CONTACT_NAME, AWAITING_CONTACT_PHONE, AWAITING_CONTACT_EMAIL,
    # Event States
    AWAITING_EVENT_SUMMARY, AWAITING_EVENT_START, AWAITING_EVENT_END,
    # SMS States
    AWAITING_SMS_NUMBER, AWAITING_SMS_MESSAGE,
    # Email States
    AWAITING_EMAIL_ADDRESS, AWAITING_EMAIL_SUBJECT, AWAITING_EMAIL_BODY,
) = range(16)


# --- Helper Functions for Menus ---

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str = None):
    """Displays the main menu."""
    keyboard = [
        [InlineKeyboardButton("🚀 إنشاء رمز QR", callback_data="create_qr_menu")],
        [InlineKeyboardButton("🔍 مسح رمز QR", callback_data="scan_qr_menu")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = message_text or "أهلاً بك! اختر مهمة من القائمة أدناه:"
    
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)
    return ConversationHandler.END

async def create_qr_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the QR type selection menu."""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🌐 رابط موقع", callback_data="website"), InlineKeyboardButton("📝 نص", callback_data="txt")],
        [InlineKeyboardButton("📧 بريد إلكتروني", callback_data="email"), InlineKeyboardButton("📞 رقم هاتف", callback_data="phone")],
        [InlineKeyboardButton("💬 رسالة SMS", callback_data="sms"), InlineKeyboardButton("👤 جهة اتصال", callback_data="contact")],
        [InlineKeyboardButton("📶 شبكة Wi-Fi", callback_data="wifi"), InlineKeyboardButton("📍 موقع جغرافي", callback_data="location")],
        [InlineKeyboardButton("📅 مناسبة", callback_data="event")],
        [InlineKeyboardButton("--- وسائل التواصل الاجتماعي ---", callback_data="no_op")],
        [InlineKeyboardButton("Instagram", callback_data="instagram"), InlineKeyboardButton("Facebook", callback_data="facebook")],
        [InlineKeyboardButton("WhatsApp", callback_data="whatsapp"), InlineKeyboardButton("X (Twitter)", callback_data="twitter")],
        [InlineKeyboardButton("YouTube", callback_data="youtube"), InlineKeyboardButton("Spotify", callback_data="spotify")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="اختر نوع رمز QR الذي تريد إنشاءه:", reply_markup=reply_markup)
    return SELECTING_ACTION

async def scan_qr_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the scanning instructions."""
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="لمسح رمز QR، أرسل صورته مباشرة إلى هذه المحادثة.", reply_markup=reply_markup)
    return ConversationHandler.END

# --- Main Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await main_menu(update, context, message_text="أهلاً بك في بوت إنشاء ومسح رموز QR الاحترافي!")

# --- Generic Prompt Function ---
async def prompt_with_cancel(query: Update.callback_query, text: str):
    """Edits a message to show a prompt with a cancel button."""
    keyboard = [[InlineKeyboardButton("🔙 إلغاء", callback_data="create_qr_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=text, reply_markup=reply_markup)

# --- Multi-Step Conversation Handlers ---

async def route_qr_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Routes the user to the correct input flow based on QR type."""
    query = update.callback_query
    qr_type = query.data
    context.user_data.clear()
    context.user_data['qr_type'] = qr_type

    # Simple types with single input
    simple_prompts = {
        "website": "الرجاء إرسال رابط الموقع كاملاً.", "txt": "الرجاء إرسال النص.",
        "phone": "الرجاء إرسال رقم الهاتف مع رمز الدولة.", "location": "أرسل خط الطول وخط العرض مفصولين بـ `,`.",
        "instagram": "أرسل اسم مستخدم انستغرام.", "facebook": "أرسل رابط صفحتك على فيسبوك.",
        "whatsapp": "أرسل رقم واتساب مع رمز الدولة.", "twitter": "أرسل اسم المستخدم على منصة X.",
        "youtube": "أرسل رابط قناتك أو الفيديو.", "spotify": "أرسل رابط الأغنية، الألبوم، أو الفنان."
    }
    if qr_type in simple_prompts:
        await prompt_with_cancel(query, simple_prompts[qr_type])
        return AWAITING_SINGLE_INPUT

    # Multi-step types
    if qr_type == 'wifi':
        await prompt_with_cancel(query, "1/3: الرجاء إرسال اسم شبكة Wi-Fi (SSID).")
        return AWAITING_WIFI_SSID
    if qr_type == 'contact':
        await prompt_with_cancel(query, "1/3: الرجاء إرسال اسم جهة الاتصال.")
        return AWAITING_CONTACT_NAME
    if qr_type == 'event':
        await prompt_with_cancel(query, "1/3: الرجاء إرسال عنوان المناسبة.")
        return AWAITING_EVENT_SUMMARY
    if qr_type == 'sms':
        await prompt_with_cancel(query, "1/2: الرجاء إرسال رقم الهاتف المستقبِل.")
        return AWAITING_SMS_NUMBER
    if qr_type == 'email':
        await prompt_with_cancel(query, "1/3: الرجاء إرسال البريد الإلكتروني للمستقبِل.")
        return AWAITING_EMAIL_ADDRESS
    
    return ConversationHandler.END

# WiFi Flow
async def get_wifi_ssid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['wifi_ssid'] = update.message.text
    await update.message.reply_text("2/3: الآن، أدخل كلمة المرور (أو أرسل 'لا يوجد' إذا كانت مفتوحة).")
    return AWAITING_WIFI_PASS

async def get_wifi_pass(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    password = update.message.text
    context.user_data['wifi_pass'] = "" if password.lower() == 'لا يوجد' else password
    keyboard = [
        [InlineKeyboardButton("WPA/WPA2", callback_data="WPA")],
        [InlineKeyboardButton("WEP", callback_data="WEP")],
        [InlineKeyboardButton("بدون تشفير", callback_data="nopass")]
    ]
    await update.message.reply_text("3/3: اختر نوع التشفير:", reply_markup=InlineKeyboardMarkup(keyboard))
    return AWAITING_WIFI_ENCRYPTION

# Contact Flow
async def get_contact_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['contact_name'] = update.message.text
    await update.message.reply_text("2/3: الآن، أدخل رقم الهاتف.")
    return AWAITING_CONTACT_PHONE

async def get_contact_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['contact_phone'] = update.message.text
    await update.message.reply_text("3/3: أخيراً، أدخل البريد الإلكتروني (أو أرسل 'لا يوجد').")
    return AWAITING_CONTACT_EMAIL

# Event Flow
async def get_event_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['event_summary'] = update.message.text
    await update.message.reply_text("2/3: أدخل تاريخ ووقت البدء بالصيغة: YYYYMMDDTHHMMSS")
    return AWAITING_EVENT_START

async def get_event_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['event_start'] = update.message.text
    await update.message.reply_text("3/3: أدخل تاريخ ووقت النهاية بنفس الصيغة.")
    return AWAITING_EVENT_END

# SMS Flow
async def get_sms_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['sms_number'] = update.message.text
    await update.message.reply_text("2/2: الآن، أدخل نص الرسالة.")
    return AWAITING_SMS_MESSAGE

# Email Flow
async def get_email_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['email_address'] = update.message.text
    await update.message.reply_text("2/3: أدخل موضوع الرسالة (أو أرسل 'لا يوجد').")
    return AWAITING_EMAIL_SUBJECT

async def get_email_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    subject = update.message.text
    context.user_data['email_subject'] = "" if subject.lower() == 'لا يوجد' else subject
    await update.message.reply_text("3/3: أدخل نص الرسالة (أو أرسل 'لا يوجد').")
    return AWAITING_EMAIL_BODY

# --- QR Code Generation ---
async def generate_qr_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Generates the QR code from user input (single or multi-step) and ends the conversation."""
    qr_type = context.user_data.get('qr_type')
    data_to_encode = ""
    
    # Determine if it's a final step from a button or a text message
    if update.callback_query:
        await update.callback_query.answer()
        # Final step for WiFi encryption
        if qr_type == 'wifi':
            context.user_data['wifi_encryption'] = update.callback_query.data
    else: # It's a text message
        # Final step for multi-input text flows
        if qr_type == 'contact': context.user_data['contact_email'] = update.message.text
        elif qr_type == 'event': context.user_data['event_end'] = update.message.text
        elif qr_type == 'sms': context.user_data['sms_message'] = update.message.text
        elif qr_type == 'email': context.user_data['email_body'] = update.message.text
        # Single input flows
        else: context.user_data['single_input'] = update.message.text

    # --- Assemble data string for encoding ---
    try:
        if qr_type in ["website", "txt", "phone", "location", "instagram", "facebook", "whatsapp", "twitter", "youtube", "spotify"]:
            user_input = context.user_data['single_input']
            if qr_type == "website": data_to_encode = user_input
            elif qr_type == "txt": data_to_encode = user_input
            elif qr_type == "phone": data_to_encode = f"tel:{user_input}"
            elif qr_type == "location": data_to_encode = f"geo:{user_input}"
            elif qr_type == "instagram": data_to_encode = f"https://instagram.com/{user_input}"
            elif qr_type == "facebook": data_to_encode = user_input
            elif qr_type == "whatsapp": data_to_encode = f"https://wa.me/{''.join(filter(str.isdigit, user_input))}"
            elif qr_type == "twitter": data_to_encode = f"https://x.com/{user_input}"
            elif qr_type == "youtube": data_to_encode = user_input
            elif qr_type == "spotify": data_to_encode = user_input
        elif qr_type == 'wifi':
            d = context.user_data
            data_to_encode = f"WIFI:T:{d['wifi_encryption']};S:{d['wifi_ssid']};P:{d['wifi_pass']};;"
        elif qr_type == 'contact':
            d = context.user_data
            email = "" if d['contact_email'].lower() == 'لا يوجد' else d['contact_email']
            data_to_encode = f"MECARD:N:{d['contact_name']};TEL:{d['contact_phone']};EMAIL:{email};;"
        elif qr_type == 'event':
            d = context.user_data
            data_to_encode = f"BEGIN:VEVENT\nSUMMARY:{d['event_summary']}\nDTSTART:{d['event_start']}\nDTEND:{d['event_end']}\nEND:VEVENT"
        elif qr_type == 'sms':
            d = context.user_data
            data_to_encode = f"smsto:{d['sms_number']}:{d['sms_message']}"
        elif qr_type == 'email':
            d = context.user_data
            body = "" if d['email_body'].lower() == 'لا يوجد' else d['email_body']
            data_to_encode = f"mailto:{d['email_address']}?subject={d['email_subject']}&body={body}"
    except Exception as e:
        logger.error(f"Error encoding QR data: {e}")
        await update.effective_message.reply_text("حدث خطأ أثناء تجميع البيانات. يرجى المحاولة مرة أخرى.")
        return await main_menu(update, context)

    # --- Image Generation ---
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(data_to_encode)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    bio = io.BytesIO()
    bio.name = 'qrcode.png'
    img.save(bio, 'PNG')
    bio.seek(0)

    await update.effective_message.reply_photo(photo=bio, caption="✅ تم إنشاء رمز QR بنجاح!")
    
    await main_menu(update, context, message_text="يمكنك الآن اختيار مهمة جديدة:")
    return ConversationHandler.END

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles photos, scans for QR codes, and returns to the main menu."""
    processing_message = await update.message.reply_text("🔍 جاري معالجة الصورة...")
    
    photo_file = await update.message.photo[-1].get_file()
    file_bytes = await photo_file.download_as_bytearray()
    nparr = np.frombuffer(file_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=processing_message.message_id)

    if img is None:
        await update.message.reply_text("لم أتمكن من قراءة الصورة. الرجاء محاولة إرسالها مرة أخرى.")
    else:
        decoded_objects = decode(img)
        if not decoded_objects:
            await update.message.reply_text("❌ عذراً، لم يتم العثور على رمز QR في هذه الصورة.")
        else:
            for obj in decoded_objects:
                data = obj.data.decode("utf-8")
                await update.message.reply_text(f"✅ تم العثور على رمز!\n\n**المحتوى:**\n`{data}`")
    
    await main_menu(update, context, message_text="يمكنك الآن اختيار مهمة جديدة:")

async def no_op(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles callback queries that do nothing, like titles."""
    await update.callback_query.answer()

# ===============================================================
# == 3. دالة التشغيل الرئيسية ==
# ===============================================================
def main() -> None:
    """Start the bot."""
    if BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        print("!!! خطأ: الرجاء استبدال 'YOUR_TELEGRAM_BOT_TOKEN' بالتوكن الصحيح الخاص بك !!!")
        return
        
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(create_qr_menu, pattern="^create_qr_menu$")],
        states={
            SELECTING_ACTION: [CallbackQueryHandler(route_qr_type)],
            AWAITING_SINGLE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, generate_qr_code)],
            # WiFi States
            AWAITING_WIFI_SSID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_wifi_ssid)],
            AWAITING_WIFI_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_wifi_pass)],
            AWAITING_WIFI_ENCRYPTION: [CallbackQueryHandler(generate_qr_code)],
            # Contact States
            AWAITING_CONTACT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_contact_name)],
            AWAITING_CONTACT_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_contact_phone)],
            AWAITING_CONTACT_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, generate_qr_code)],
            # Event States
            AWAITING_EVENT_SUMMARY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_event_summary)],
            AWAITING_EVENT_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_event_start)],
            AWAITING_EVENT_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, generate_qr_code)],
            # SMS States
            AWAITING_SMS_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_sms_number)],
            AWAITING_SMS_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, generate_qr_code)],
            # Email States
            AWAITING_EMAIL_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email_address)],
            AWAITING_EMAIL_SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email_subject)],
            AWAITING_EMAIL_BODY: [MessageHandler(filters.TEXT & ~filters.COMMAND, generate_qr_code)],
        },
        fallbacks=[
            CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            CallbackQueryHandler(create_qr_menu, pattern="^create_qr_menu$")
        ],
        allow_reentry=True
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(scan_qr_menu, pattern="^scan_qr_menu$"))
    application.add_handler(CallbackQueryHandler(main_menu, pattern="^main_menu$"))
    application.add_handler(CallbackQueryHandler(no_op, pattern="^no_op$"))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    logger.info("Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()