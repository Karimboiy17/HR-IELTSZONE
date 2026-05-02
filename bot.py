import logging
import os
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
)
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Config
BOT_TOKEN = os.environ.get("BOT_TOKEN")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "1054482233,7375517762").split(",")]

# Google Sheets setup
def get_sheets_client():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    creds_dict = json.loads(creds_json)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

def get_or_create_sheet(name):
    client = get_sheets_client()
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    try:
        return spreadsheet.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title=name, rows=1000, cols=20)
        return sheet

def get_departments():
    sheet = get_or_create_sheet("Departments")
    data = sheet.get_all_values()
    if not data or data == [[]]:
        return []
    return [row[0] for row in data if row and row[0]]

def add_department(name):
    sheet = get_or_create_sheet("Departments")
    sheet.append_row([name])

def remove_department(name):
    sheet = get_or_create_sheet("Departments")
    data = sheet.get_all_values()
    for i, row in enumerate(data):
        if row and row[0] == name:
            sheet.delete_rows(i + 1)
            return True
    return False

def save_resume(applicant_name, department, telegram_id, username, file_id, file_type):
    sheet = get_or_create_sheet("Resumes")
    # Add header if empty
    data = sheet.get_all_values()
    if not data or data == [[]]:
        sheet.append_row(["#", "Sana", "Ism", "Bo'lim", "Telegram ID", "Username", "File ID", "File Type", "Holat", "Admin izohi"])
    
    row_num = len(sheet.get_all_values())
    sheet.append_row([
        row_num,
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        applicant_name,
        department,
        str(telegram_id),
        username or "—",
        file_id,
        file_type,
        "Kutilmoqda",
        ""
    ])
    return row_num

def update_resume_status(row_num, status, comment):
    sheet = get_or_create_sheet("Resumes")
    data = sheet.get_all_values()
    for i, row in enumerate(data):
        if row and str(row[0]) == str(row_num):
            sheet.update_cell(i + 1, 9, status)
            sheet.update_cell(i + 1, 10, comment)
            return True
    return False

def get_resume_by_row(row_num):
    sheet = get_or_create_sheet("Resumes")
    data = sheet.get_all_values()
    for row in data:
        if row and str(row[0]) == str(row_num):
            return row
    return None

# States
(MAIN_MENU, SELECT_DEPARTMENT, ENTER_NAME, UPLOAD_RESUME,
 ADMIN_MENU, ADMIN_ADD_DEPT, ADMIN_REMOVE_DEPT, ADMIN_REPLY_SELECT, ADMIN_REPLY_TEXT) = range(9)

# IELTS Zone haqida ma'lumot
IELTS_ZONE_INFO = """
🎓 *IELTS ZONE* haqida

IELTS Zone — O'zbekistondagi eng yirik va ishonchli IELTS tayyorlov markazlaridan biri.

📌 *Bizning afzalliklarimiz:*
• Tajribali va sertifikatlangan o'qituvchilar
• Kichik guruhlar (max 8 kishi)
• Haqiqiy imtihon sharoitida mashqlar
• Shaxsiy progress kuzatuvi
• Moslashuvchan jadval

🏆 *Natijalarimiz:*
• 5000+ muvaffaqiyatli talabalar
• O'rtacha ball: 7.0+
• Top universitetlarga qabul

📍 Toshkent bo'ylab filiallarimiz mavjud

Biz bilan ishlash — karyerangizni rivojlantirish! 🚀
"""

# ---- USER HANDLERS ----

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in ADMIN_IDS:
        return await admin_start(update, context)
    
    keyboard = [[InlineKeyboardButton("📝 Ishga ariza topshirish", callback_data="apply")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👋 *IELTS Zone HR Botiga xush kelibsiz!*\n\nBizga qo'shilishni xohlaysizmi?",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return MAIN_MENU

async def apply_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.message.reply_text(
        IELTS_ZONE_INFO,
        parse_mode="Markdown"
    )
    
    departments = get_departments()
    if not departments:
        await query.message.reply_text(
            "⚠️ Hozircha bo'sh ish o'rinlari yo'q. Keyinroq qayta urinib ko'ring."
        )
        return MAIN_MENU
    
    keyboard = [[InlineKeyboardButton(dept, callback_data=f"dept_{dept}")] for dept in departments]
    keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        "📋 *Qaysi bo'lim uchun ariza topshirmoqchisiz?*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return SELECT_DEPARTMENT

async def select_department(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back":
        return await start_from_query(update, context)
    
    dept = query.data.replace("dept_", "")
    context.user_data["department"] = dept
    
    await query.message.reply_text(
        f"✅ Bo'lim tanlandi: *{dept}*\n\n👤 Iltimos, to'liq ismingizni yozing (Familiya Ism):",
        parse_mode="Markdown"
    )
    return ENTER_NAME

async def enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 3:
        await update.message.reply_text("⚠️ Iltimos, to'liq ismingizni kiriting.")
        return ENTER_NAME
    
    context.user_data["name"] = name
    
    await update.message.reply_text(
        f"👋 Salom, *{name}*!\n\n"
        f"📎 Endi rezyumengizni yuboring.\n"
        f"📄 Qabul qilinadigan formatlar: *PDF* yoki *Word (.docx)*",
        parse_mode="Markdown"
    )
    return UPLOAD_RESUME

async def upload_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    document = update.message.document
    
    if not document:
        await update.message.reply_text("⚠️ Iltimos, fayl yuboring (PDF yoki Word).")
        return UPLOAD_RESUME
    
    file_name = document.file_name.lower()
    if not (file_name.endswith(".pdf") or file_name.endswith(".docx") or file_name.endswith(".doc")):
        await update.message.reply_text(
            "❌ Faqat PDF yoki Word formatidagi fayllar qabul qilinadi.\nIltimos, qayta yuboring."
        )
        return UPLOAD_RESUME
    
    name = context.user_data["name"]
    department = context.user_data["department"]
    file_id = document.file_id
    file_type = "PDF" if file_name.endswith(".pdf") else "Word"
    
    # Save to sheets
    row_num = save_resume(name, department, user.id, user.username, file_id, file_type)
    
    # Notify admins
    for admin_id in ADMIN_IDS:
        try:
            caption = (
                f"📨 *Yangi ariza!*\n\n"
                f"👤 Ism: {name}\n"
                f"🏢 Bo'lim: {department}\n"
                f"📱 Telegram: @{user.username or '—'}\n"
                f"🆔 ID: `{user.id}`\n"
                f"📄 Format: {file_type}\n"
                f"🕐 Vaqt: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                f"Ariza #: `{row_num}`"
            )
            keyboard = [[
                InlineKeyboardButton("✅ Qabul qilish", callback_data=f"accept_{row_num}_{user.id}"),
                InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_{row_num}_{user.id}")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_document(
                chat_id=admin_id,
                document=file_id,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Admin {admin_id} ga xabar yuborishda xato: {e}")
    
    await update.message.reply_text(
        "✅ *Rezyumengiz muvaffaqiyatli yuborildi!*\n\n"
        "⏳ HR adminimiz ko'rib chiqib, tez orada siz bilan bog'lanadi.\n\n"
        "🙏 Vaqt ajratganingiz uchun rahmat!",
        parse_mode="Markdown"
    )
    
    context.user_data.clear()
    return ConversationHandler.END

# ---- ADMIN HANDLERS ----

async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ Bo'lim qo'shish", callback_data="admin_add_dept")],
        [InlineKeyboardButton("➖ Bo'lim o'chirish", callback_data="admin_remove_dept")],
        [InlineKeyboardButton("📋 Bo'limlar ro'yxati", callback_data="admin_list_depts")],
        [InlineKeyboardButton("📊 Arizalar", callback_data="admin_resumes")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    msg = update.message or update.callback_query.message
    await msg.reply_text(
        "👨‍💼 *Admin Panel*\n\nNimani qilmoqchisiz?",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return ADMIN_MENU

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "admin_add_dept":
        await query.message.reply_text("✏️ Yangi bo'lim nomini yozing:")
        return ADMIN_ADD_DEPT
    
    elif data == "admin_remove_dept":
        departments = get_departments()
        if not departments:
            await query.message.reply_text("❌ Hozircha bo'limlar yo'q.")
            return ADMIN_MENU
        keyboard = [[InlineKeyboardButton(f"🗑 {dept}", callback_data=f"del_{dept}")] for dept in departments]
        keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin_back")])
        await query.message.reply_text(
            "Qaysi bo'limni o'chirmoqchisiz?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ADMIN_REMOVE_DEPT
    
    elif data == "admin_list_depts":
        departments = get_departments()
        if not departments:
            text = "📋 Bo'limlar ro'yxati bo'sh."
        else:
            text = "📋 *Bo'limlar ro'yxati:*\n\n" + "\n".join([f"• {d}" for d in departments])
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="admin_back")]]
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return ADMIN_MENU
    
    elif data == "admin_resumes":
        sheet = get_or_create_sheet("Resumes")
        data_rows = sheet.get_all_values()
        if len(data_rows) <= 1:
            await query.message.reply_text("📊 Hozircha arizalar yo'q.")
        else:
            text = "📊 *Arizalar:*\n\n"
            for row in data_rows[1:]:
                if row:
                    text += f"#{row[0]} | {row[2]} | {row[3]} | {row[8]}\n"
            await query.message.reply_text(text, parse_mode="Markdown")
        return ADMIN_MENU
    
    elif data == "admin_back":
        return await admin_start(update, context)
    
    elif data.startswith("del_"):
        dept = data.replace("del_", "")
        remove_department(dept)
        await query.message.reply_text(f"✅ *{dept}* bo'limi o'chirildi.")
        return ADMIN_MENU
    
    elif data.startswith("accept_") or data.startswith("reject_"):
        parts = data.split("_")
        action = parts[0]
        row_num = parts[1]
        applicant_id = int(parts[2])
        
        status = "Qabul qilindi ✅" if action == "accept" else "Rad etildi ❌"
        context.user_data["reply_row"] = row_num
        context.user_data["reply_user"] = applicant_id
        context.user_data["reply_status"] = status
        
        await query.message.reply_text(
            f"📝 Ariza #{row_num} uchun izoh yozing\n(yoki /skip yozing izoхsiz yuborish uchun):"
        )
        return ADMIN_REPLY_TEXT
    
    return ADMIN_MENU

async def admin_add_dept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dept_name = update.message.text.strip()
    if not dept_name:
        await update.message.reply_text("⚠️ Bo'lim nomi bo'sh bo'lmasligi kerak.")
        return ADMIN_ADD_DEPT
    
    add_department(dept_name)
    await update.message.reply_text(f"✅ *{dept_name}* bo'limi qo'shildi!")
    return await admin_start(update, context)

async def admin_remove_dept_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    dept = query.data.replace("del_", "")
    remove_department(dept)
    await query.message.reply_text(f"✅ *{dept}* o'chirildi.", parse_mode="Markdown")
    return await admin_start(update, context)

async def admin_reply_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    comment = update.message.text
    row_num = context.user_data.get("reply_row")
    applicant_id = context.user_data.get("reply_user")
    status = context.user_data.get("reply_status")
    
    if comment == "/skip":
        comment = ""
    
    # Update sheets
    update_resume_status(row_num, status, comment)
    
    # Notify applicant
    try:
        msg = f"📬 *Arizangiz bo'yicha yangilik!*\n\n"
        msg += f"Holat: *{status}*\n"
        if comment:
            msg += f"💬 Izoh: {comment}"
        
        await context.bot.send_message(
            chat_id=applicant_id,
            text=msg,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Arizachiga xabar yuborishda xato: {e}")
    
    await update.message.reply_text(f"✅ Javob yuborildi! Ariza #{row_num} yangilandi.")
    context.user_data.clear()
    return await admin_start(update, context)

async def start_from_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    keyboard = [[InlineKeyboardButton("📝 Ishga ariza topshirish", callback_data="apply")]]
    await query.message.reply_text(
        "👋 *IELTS Zone HR Botiga xush kelibsiz!*\n\nBizga qo'shilishni xohlaysizmi?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return MAIN_MENU

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(apply_start, pattern="^apply$"),
            ],
            SELECT_DEPARTMENT: [
                CallbackQueryHandler(select_department, pattern="^dept_"),
                CallbackQueryHandler(start_from_query, pattern="^back$"),
            ],
            ENTER_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_name)
            ],
            UPLOAD_RESUME: [
                MessageHandler(filters.Document.ALL, upload_resume)
            ],
            ADMIN_MENU: [
                CallbackQueryHandler(admin_callback),
            ],
            ADMIN_ADD_DEPT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_dept)
            ],
            ADMIN_REMOVE_DEPT: [
                CallbackQueryHandler(admin_callback),
            ],
            ADMIN_REPLY_TEXT: [
                MessageHandler(filters.TEXT, admin_reply_text),
                CommandHandler("skip", admin_reply_text),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    app.add_handler(conv_handler)
    
    logger.info("Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
