import logging
import os
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "1054482233,7375517762").split(",")]

# ---- GOOGLE SHEETS ----

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
        return spreadsheet.add_worksheet(title=name, rows=1000, cols=20)

def get_departments():
    sheet = get_or_create_sheet("Departments")
    data = sheet.get_all_values()
    return [row[0] for row in data if row and row[0].strip()]

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
    data = sheet.get_all_values()
    if not data or data == [[]]:
        sheet.append_row(["#", "Sana", "Ism", "Bo'lim", "Telegram ID", "Username", "File ID", "File Type", "Holat", "Izoh"])
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

# ---- STATE MANAGEMENT ----
# user_data keys:
# "step": current step
# "department": selected department
# "name": entered name
# "reply_row": admin reply row num
# "reply_user": admin reply user id
# "reply_status": accept/reject

# ---- HANDLERS ----

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.clear()

    if user_id in ADMIN_IDS:
        await show_admin_menu(update, context)
    else:
        await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("📝 Ishga ariza topshirish", callback_data="apply")]]
    text = "👋 *IELTS Zone HR Botiga xush kelibsiz!*\n\nBizga qo'shilishni xohlaysizmi?"
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.callback_query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ Bo'lim qo'shish", callback_data="admin_add")],
        [InlineKeyboardButton("🗑 Bo'lim o'chirish", callback_data="admin_remove")],
        [InlineKeyboardButton("📋 Bo'limlar ro'yxati", callback_data="admin_list")],
        [InlineKeyboardButton("📊 Arizalar", callback_data="admin_resumes")],
    ]
    text = "👨‍💼 *Admin Panel*\n\nNimani qilmoqchisiz?"
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.callback_query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    # ---- USER FLOW ----
    if data == "apply":
        IELTS_INFO = (
            "🎓 *IELTS ZONE* haqida\n\n"
            "IELTS Zone — O'zbekistondagi eng yirik IELTS tayyorlov markazlaridan biri.\n\n"
            "📌 *Afzalliklarimiz:*\n"
            "• Tajribali va sertifikatlangan o'qituvchilar\n"
            "• Kichik guruhlar (max 8 kishi)\n"
            "• Haqiqiy imtihon sharoitida mashqlar\n"
            "• O'rtacha natija: 7.0+\n\n"
            "Biz bilan ishlash — karyerangizni rivojlantirish! 🚀"
        )
        await query.message.reply_text(IELTS_INFO, parse_mode="Markdown")

        departments = get_departments()
        if not departments:
            await query.message.reply_text("⚠️ Hozircha bo'sh ish o'rinlari yo'q.")
            return

        keyboard = [[InlineKeyboardButton(dept, callback_data=f"dept_{dept}")] for dept in departments]
        keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")])
        await query.message.reply_text(
            "📋 *Qaysi bo'lim uchun ariza topshirmoqchisiz?*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        context.user_data["step"] = "select_dept"

    elif data.startswith("dept_") and context.user_data.get("step") == "select_dept":
        dept = data[5:]
        context.user_data["department"] = dept
        context.user_data["step"] = "enter_name"
        await query.message.reply_text(
            f"✅ Bo'lim: *{dept}*\n\n👤 To'liq ismingizni yozing (Familiya Ism):",
            parse_mode="Markdown"
        )

    elif data == "back_main":
        context.user_data.clear()
        await show_main_menu(update, context)

    # ---- ADMIN FLOW ----
    elif data == "admin_add" and user_id in ADMIN_IDS:
        context.user_data["step"] = "admin_adding_dept"
        keyboard = [[InlineKeyboardButton("🔙 Bekor qilish", callback_data="admin_back")]]
        await query.message.reply_text(
            "✏️ Yangi bo'lim nomini yozing:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "admin_remove" and user_id in ADMIN_IDS:
        departments = get_departments()
        if not departments:
            await query.message.reply_text("❌ Hozircha bo'limlar yo'q.")
            return
        keyboard = [[InlineKeyboardButton(f"🗑 {dept}", callback_data=f"del_{dept}")] for dept in departments]
        keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin_back")])
        await query.message.reply_text(
            "Qaysi bo'limni o'chirmoqchisiz?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("del_") and user_id in ADMIN_IDS:
        dept = data[4:]
        remove_department(dept)
        await query.message.reply_text(f"✅ *{dept}* o'chirildi.", parse_mode="Markdown")
        await show_admin_menu(update, context)

    elif data == "admin_list" and user_id in ADMIN_IDS:
        departments = get_departments()
        if not departments:
            text = "📋 Bo'limlar ro'yxati bo'sh."
        else:
            text = "📋 *Bo'limlar:*\n\n" + "\n".join([f"• {d}" for d in departments])
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="admin_back")]]
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "admin_resumes" and user_id in ADMIN_IDS:
        sheet = get_or_create_sheet("Resumes")
        rows = sheet.get_all_values()
        if len(rows) <= 1:
            await query.message.reply_text("📊 Hozircha arizalar yo'q.")
        else:
            text = "📊 *Arizalar:*\n\n"
            for row in rows[1:]:
                if len(row) >= 9:
                    text += f"#{row[0]} | {row[2]} | {row[3]} | {row[8]}\n"
            await query.message.reply_text(text, parse_mode="Markdown")
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="admin_back")]]
        await query.message.reply_text(".", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "admin_back" and user_id in ADMIN_IDS:
        context.user_data.clear()
        await show_admin_menu(update, context)

    elif (data.startswith("accept_") or data.startswith("reject_")) and user_id in ADMIN_IDS:
        parts = data.split("_")
        action = parts[0]
        row_num = parts[1]
        applicant_id = int(parts[2])
        status = "Qabul qilindi ✅" if action == "accept" else "Rad etildi ❌"
        context.user_data["step"] = "admin_replying"
        context.user_data["reply_row"] = row_num
        context.user_data["reply_user"] = applicant_id
        context.user_data["reply_status"] = status
        keyboard = [[InlineKeyboardButton("⏭ Izoхsiz yuborish", callback_data="skip_reply")]]
        await query.message.reply_text(
            f"📝 Ariza #{row_num} — *{status}*\n\nIzoh yozing yoki o'tkazib yuboring:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data == "skip_reply" and user_id in ADMIN_IDS:
        await send_reply_to_applicant(update, context, comment="")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    step = context.user_data.get("step")
    text = update.message.text

    # Admin: adding department
    if step == "admin_adding_dept" and user_id in ADMIN_IDS:
        name = text.strip()
        if not name:
            await update.message.reply_text("⚠️ Bo'lim nomi bo'sh bo'lmasligi kerak.")
            return
        add_department(name)
        await update.message.reply_text(f"✅ *{name}* bo'limi qo'shildi!", parse_mode="Markdown")
        context.user_data.clear()
        await show_admin_menu(update, context)

    # Admin: replying to applicant
    elif step == "admin_replying" and user_id in ADMIN_IDS:
        await send_reply_to_applicant(update, context, comment=text)

    # User: entering name
    elif step == "enter_name":
        name = text.strip()
        if len(name) < 3:
            await update.message.reply_text("⚠️ Iltimos, to'liq ismingizni kiriting (kamida 3 harf).")
            return
        context.user_data["name"] = name
        context.user_data["step"] = "upload_resume"
        await update.message.reply_text(
            f"👋 Salom, *{name}*!\n\n"
            "📎 Rezyumengizni yuboring.\n"
            "📄 Formatlar: *PDF* yoki *Word (.docx)*",
            parse_mode="Markdown"
        )

    else:
        if user_id in ADMIN_IDS:
            await show_admin_menu(update, context)
        else:
            await show_main_menu(update, context)

async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    step = context.user_data.get("step")

    if step != "upload_resume":
        await update.message.reply_text("Iltimos avval /start bosing.")
        return

    document = update.message.document
    file_name = document.file_name.lower()

    if not (file_name.endswith(".pdf") or file_name.endswith(".docx") or file_name.endswith(".doc")):
        await update.message.reply_text("❌ Faqat PDF yoki Word formatida yuboring.")
        return

    name = context.user_data["name"]
    department = context.user_data["department"]
    file_id = document.file_id
    file_type = "PDF" if file_name.endswith(".pdf") else "Word"

    row_num = save_resume(name, department, user.id, user.username, file_id, file_type)

    for admin_id in ADMIN_IDS:
        try:
            caption = (
                f"📨 *Yangi ariza!*\n\n"
                f"👤 Ism: {name}\n"
                f"🏢 Bo'lim: {department}\n"
                f"📱 Telegram: @{user.username or '—'}\n"
                f"🆔 ID: `{user.id}`\n"
                f"📄 Format: {file_type}\n"
                f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"Ariza #: `{row_num}`"
            )
            keyboard = [[
                InlineKeyboardButton("✅ Qabul", callback_data=f"accept_{row_num}_{user.id}"),
                InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_{row_num}_{user.id}")
            ]]
            await context.bot.send_document(
                chat_id=admin_id,
                document=file_id,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Admin {admin_id} ga yuborishda xato: {e}")

    await update.message.reply_text(
        "✅ *Rezyumengiz yuborildi!*\n\n"
        "⏳ HR adminimiz ko'rib chiqib, tez orada bog'lanadi.\n"
        "🙏 Rahmat!",
        parse_mode="Markdown"
    )
    context.user_data.clear()

async def send_reply_to_applicant(update: Update, context: ContextTypes.DEFAULT_TYPE, comment: str):
    row_num = context.user_data.get("reply_row")
    applicant_id = context.user_data.get("reply_user")
    status = context.user_data.get("reply_status")

    update_resume_status(row_num, status, comment)

    try:
        msg = f"📬 *Arizangiz bo'yicha yangilik!*\n\nHolat: *{status}*"
        if comment:
            msg += f"\n💬 Izoh: {comment}"
        await context.bot.send_message(chat_id=applicant_id, text=msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Arizachiga xabar yuborishda xato: {e}")

    if update.message:
        await update.message.reply_text(f"✅ Javob yuborildi! Ariza #{row_num} yangilandi.")
    else:
        await update.callback_query.message.reply_text(f"✅ Javob yuborildi! Ariza #{row_num} yangilandi.")

    context.user_data.clear()
    await show_admin_menu(update, context)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    logger.info("Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
