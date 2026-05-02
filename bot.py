import logging
import os
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
ADMIN_IDS = [1054482233, 7375517762]

WELCOME_TEXT = (
    "👋 Assalomu alaykum!\n"
    "IELTS Zone jamoasiga xush kelibsiz.\n"
    "Bu bot orqali siz:\n"
    "📌 Ishga ariza topshirishingiz\n"
    "📌 Bo'sh ish o'rinlari bilan tanishishingiz\n"
    "📌 Suhbat jarayoni haqida ma'lumot olishingiz mumkin\n"
    "Davom etish uchun quyidagi bo'limlardan birini tanlang 👇"
)

# ========== GOOGLE SHEETS ==========

def sheets_client():
    creds_dict = json.loads(os.environ.get("GOOGLE_CREDENTIALS"))
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

def get_sheet(name):
    sp = sheets_client().open_by_key(SPREADSHEET_ID)
    try:
        return sp.worksheet(name)
    except:
        return sp.add_worksheet(title=name, rows=1000, cols=20)

# --- Departments ---
def get_departments():
    ws = get_sheet("Departments")
    return [r[0] for r in ws.get_all_values() if r and r[0].strip()]

def add_dept(name):
    get_sheet("Departments").append_row([name.strip()])

def del_dept(name):
    ws = get_sheet("Departments")
    for i, r in enumerate(ws.get_all_values()):
        if r and r[0] == name:
            ws.delete_rows(i + 1)
            return

# --- Vacancies ---
def get_vacancies(dept):
    ws = get_sheet("Vacancies")
    rows = ws.get_all_values()
    return [r for r in rows if r and r[0] == dept]

def add_vacancy(dept, title, description):
    ws = get_sheet("Vacancies")
    rows = ws.get_all_values()
    if not rows or rows == [[]]:
        ws.append_row(["Bo'lim", "Vakansiya nomi", "Tavsif"])
    ws.append_row([dept, title.strip(), description.strip()])

def del_vacancy(dept, title):
    ws = get_sheet("Vacancies")
    for i, r in enumerate(ws.get_all_values()):
        if r and r[0] == dept and r[1] == title:
            ws.delete_rows(i + 1)
            return

# --- Resumes ---
def save_application(data: dict):
    ws = get_sheet("Resumes")
    rows = ws.get_all_values()
    if not rows or rows == [[]]:
        ws.append_row(["#", "Sana", "Ism", "Telefon", "Bo'lim", "Vakansiya", "TG ID", "Username", "File ID", "Fayl turi", "Holat", "Izoh"])
    num = len(ws.get_all_values())
    ws.append_row([
        num,
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        data.get("name", ""),
        data.get("phone", ""),
        data.get("dept", ""),
        data.get("vacancy", ""),
        str(data.get("uid", "")),
        data.get("username", "-"),
        data.get("file_id", ""),
        data.get("file_type", ""),
        "Kutilmoqda",
        ""
    ])
    return num

def update_status(num, status, comment):
    ws = get_sheet("Resumes")
    for i, r in enumerate(ws.get_all_values()):
        if r and str(r[0]) == str(num):
            ws.update_cell(i+1, 11, status)
            ws.update_cell(i+1, 12, comment)
            return

# ========== KEYBOARDS ==========

def kb_admin():
    return ReplyKeyboardMarkup([
        ["➕ Bo'lim qo'shish", "🗑 Bo'lim o'chirish"],
        ["📋 Bo'limlar", "💼 Vakansiyalar"],
        ["📊 Arizalar"],
    ], resize_keyboard=True)

def kb_user():
    return ReplyKeyboardMarkup([["📝 Ariza topshirish"]], resize_keyboard=True)

def kb_yes_no():
    return ReplyKeyboardMarkup([["✅ Ha, albatta!", "❌ Yo'q"]], resize_keyboard=True)

def kb_cancel():
    return ReplyKeyboardMarkup([["❌ Bekor qilish"]], resize_keyboard=True)

def kb_phone():
    return ReplyKeyboardMarkup([
        [{"text": "📱 Raqamni yuborish", "request_contact": True}],
        ["❌ Bekor qilish"]
    ], resize_keyboard=True)

# ========== START ==========

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    uid = update.effective_user.id
    if uid in ADMIN_IDS:
        await update.message.reply_text("👨‍💼 *Admin Panel*", reply_markup=kb_admin(), parse_mode="Markdown")
    else:
        kb = ReplyKeyboardMarkup([["✅ Ha, albatta!", "❌ Yo'q"]], resize_keyboard=True)
        await update.message.reply_text(WELCOME_TEXT, reply_markup=kb, parse_mode="Markdown")
        ctx.user_data["step"] = "welcome"

# ========== MESSAGE HANDLER ==========

async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip() if update.message.text else ""
    step = ctx.user_data.get("step")

    # ===== ADMIN =====
    if uid in ADMIN_IDS:

        if text == "❌ Bekor qilish":
            ctx.user_data.clear()
            await update.message.reply_text("✅ Bekor qilindi.", reply_markup=kb_admin())
            return

        if text == "➕ Bo'lim qo'shish":
            ctx.user_data["step"] = "adding_dept"
            await update.message.reply_text("✏️ Yangi bo'lim nomini yozing:", reply_markup=kb_cancel())
            return

        if text == "🗑 Bo'lim o'chirish":
            depts = get_departments()
            if not depts:
                await update.message.reply_text("❌ Bo'limlar yo'q.", reply_markup=kb_admin())
                return
            kb = [[InlineKeyboardButton(f"🗑 {d}", callback_data=f"del_dept|{d}")] for d in depts]
            await update.message.reply_text("Qaysi bo'limni o'chirish?", reply_markup=InlineKeyboardMarkup(kb))
            return

        if text == "📋 Bo'limlar":
            depts = get_departments()
            if not depts:
                t = "📋 Bo'limlar ro'yxati bo'sh."
            else:
                t = "📋 *Bo'limlar:*\n\n" + "\n".join(f"• {d}" for d in depts)
            await update.message.reply_text(t, parse_mode="Markdown", reply_markup=kb_admin())
            return

        if text == "💼 Vakansiyalar":
            depts = get_departments()
            if not depts:
                await update.message.reply_text("❌ Avval bo'lim qo'shing.", reply_markup=kb_admin())
                return
            kb = [[InlineKeyboardButton(d, callback_data=f"vac_dept|{d}")] for d in depts]
            await update.message.reply_text("Qaysi bo'lim vakansiyalari?", reply_markup=InlineKeyboardMarkup(kb))
            return

        if text == "📊 Arizalar":
            ws = get_sheet("Resumes")
            rows = ws.get_all_values()
            if len(rows) <= 1:
                t = "📊 Hozircha arizalar yo'q."
            else:
                t = "📊 *Arizalar:*\n\n"
                for r in rows[1:]:
                    if len(r) >= 11:
                        t += f"#{r[0]} | {r[2]} | {r[4]} → {r[5]} | {r[10]}\n"
            await update.message.reply_text(t, parse_mode="Markdown", reply_markup=kb_admin())
            return

        # Steps
        if step == "adding_dept":
            add_dept(text)
            ctx.user_data.clear()
            await update.message.reply_text(f"✅ *{text}* bo'limi qo'shildi!", parse_mode="Markdown", reply_markup=kb_admin())
            return

        if step == "adding_vac_title":
            ctx.user_data["vac_title"] = text
            ctx.user_data["step"] = "adding_vac_desc"
            await update.message.reply_text("📝 Vakansiya tavsifini yozing (maosh, tajriba, talablar):", reply_markup=kb_cancel())
            return

        if step == "adding_vac_desc":
            dept = ctx.user_data.get("vac_dept")
            title = ctx.user_data.get("vac_title")
            add_vacancy(dept, title, text)
            ctx.user_data.clear()
            await update.message.reply_text(f"✅ *{title}* vakansiyasi qo'shildi!", parse_mode="Markdown", reply_markup=kb_admin())
            return

        if step == "admin_replying":
            await do_reply(ctx, update, text)
            return

        await update.message.reply_text("👨‍💼 Menyudan tanlang:", reply_markup=kb_admin())

    # ===== USER =====
    else:

        if text == "❌ Bekor qilish":
            ctx.user_data.clear()
            await update.message.reply_text("✅ Bekor qilindi.", reply_markup=kb_user())
            return

        # Welcome screen
        if step == "welcome":
            if text == "✅ Ha, albatta!":
                depts = get_departments()
                if not depts:
                    await update.message.reply_text("⚠️ Hozircha bo'sh ish o'rinlari yo'q. Keyinroq qayta urinib ko'ring.", reply_markup=ReplyKeyboardRemove())
                    return
                kb = [[InlineKeyboardButton(d, callback_data=f"user_dept|{d}")] for d in depts]
                await update.message.reply_text(
                    "🎉 Ajoyib! Qaysi bo'lim uchun ariza topshirmoqchisiz?",
                    reply_markup=InlineKeyboardMarkup(kb)
                )
                ctx.user_data["step"] = "select_dept"
            else:
                await update.message.reply_text(
                    "🙂 Tushunarli! Qaror o'zgarsa, /start bosing.\n\nOmad! 👋",
                    reply_markup=ReplyKeyboardRemove()
                )
                ctx.user_data.clear()
            return

        if text == "📝 Ariza topshirish":
            depts = get_departments()
            if not depts:
                await update.message.reply_text("⚠️ Hozircha bo'sh ish o'rinlari yo'q.")
                return
            kb = [[InlineKeyboardButton(d, callback_data=f"user_dept|{d}")] for d in depts]
            await update.message.reply_text("📋 Qaysi bo'lim uchun ariza?", reply_markup=InlineKeyboardMarkup(kb))
            ctx.user_data["step"] = "select_dept"
            return

        if step == "enter_name":
            if len(text) < 3:
                await update.message.reply_text("⚠️ Kamida 3 harf kiriting.")
                return
            ctx.user_data["name"] = text
            ctx.user_data["step"] = "enter_phone"
            kb = ReplyKeyboardMarkup(
                [[{"text": "📱 Raqamni yuborish", "request_contact": True}], ["❌ Bekor qilish"]],
                resize_keyboard=True
            )
            await update.message.reply_text(
                f"👋 Salom, *{text}*!\n\n📱 Telefon raqamingizni yuboring:",
                parse_mode="Markdown",
                reply_markup=kb
            )
            return

        if step == "enter_phone":
            # Manual phone input
            if text and (text.startswith("+") or text.isdigit()):
                ctx.user_data["phone"] = text
                ctx.user_data["step"] = "upload_resume"
                await update.message.reply_text(
                    "📎 Rezyume yuboring (PDF, Word yoki Rasm):",
                    reply_markup=kb_cancel()
                )
            else:
                await update.message.reply_text("⚠️ Telefon raqam noto'g'ri. Qayta yuboring (masalan: +998901234567)")
            return

        if step == "admin_replying":
            await do_reply(ctx, update, text)
            return

        await update.message.reply_text("Boshlash uchun /start bosing.")

# ========== CONTACT HANDLER ==========

async def on_contact(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    step = ctx.user_data.get("step")
    if step == "enter_phone":
        phone = update.message.contact.phone_number
        ctx.user_data["phone"] = phone
        ctx.user_data["step"] = "upload_resume"
        await update.message.reply_text(
            f"✅ Raqam saqlandi: {phone}\n\n📎 Rezyume yuboring (PDF, Word yoki Rasm):",
            reply_markup=kb_cancel()
        )

# ========== CALLBACK ==========

async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    uid = q.from_user.id

    # --- Admin ---
    if d.startswith("del_dept|") and uid in ADMIN_IDS:
        dept = d.split("|")[1]
        del_dept(dept)
        await q.message.reply_text(f"✅ *{dept}* o'chirildi.", parse_mode="Markdown", reply_markup=kb_admin())

    elif d.startswith("vac_dept|") and uid in ADMIN_IDS:
        dept = d.split("|")[1]
        ctx.user_data["vac_dept"] = dept
        vacs = get_vacancies(dept)
        text = f"💼 *{dept}* vakansiyalari:\n\n"
        if vacs:
            for v in vacs:
                text += f"• *{v[1]}*\n  {v[2]}\n\n"
        else:
            text += "Hozircha vakansiyalar yo'q.\n"
        kb = [
            [InlineKeyboardButton("➕ Vakansiya qo'shish", callback_data=f"add_vac|{dept}")],
            [InlineKeyboardButton("🗑 Vakansiya o'chirish", callback_data=f"del_vac_list|{dept}")]
        ]
        await q.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

    elif d.startswith("add_vac|") and uid in ADMIN_IDS:
        dept = d.split("|")[1]
        ctx.user_data["vac_dept"] = dept
        ctx.user_data["step"] = "adding_vac_title"
        await q.message.reply_text(f"✏️ *{dept}* uchun vakansiya nomini yozing:", parse_mode="Markdown", reply_markup=kb_cancel())

    elif d.startswith("del_vac_list|") and uid in ADMIN_IDS:
        dept = d.split("|")[1]
        vacs = get_vacancies(dept)
        if not vacs:
            await q.message.reply_text("❌ Vakansiyalar yo'q.")
            return
        kb = [[InlineKeyboardButton(f"🗑 {v[1]}", callback_data=f"del_vac|{dept}|{v[1]}")] for v in vacs]
        await q.message.reply_text("Qaysi vakansiyani o'chirish?", reply_markup=InlineKeyboardMarkup(kb))

    elif d.startswith("del_vac|") and uid in ADMIN_IDS:
        parts = d.split("|")
        dept, title = parts[1], parts[2]
        del_vacancy(dept, title)
        await q.message.reply_text(f"✅ *{title}* o'chirildi.", parse_mode="Markdown", reply_markup=kb_admin())

    elif (d.startswith("acc|") or d.startswith("rej|")) and uid in ADMIN_IDS:
        parts = d.split("|")
        action, row_num, applicant_id = parts[0], parts[1], int(parts[2])
        status = "✅ Qabul qilindi" if action == "acc" else "❌ Rad etildi"
        ctx.user_data["step"] = "admin_replying"
        ctx.user_data["r_row"] = row_num
        ctx.user_data["r_uid"] = applicant_id
        ctx.user_data["r_status"] = status
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Izoхsiz yuborish", callback_data="skip_reply")]])
        await q.message.reply_text(
            f"Ariza #{row_num} — *{status}*\n\nIzoh yozing yoki o'tkazib yuboring:",
            reply_markup=kb,
            parse_mode="Markdown"
        )

    elif d == "skip_reply" and uid in ADMIN_IDS:
        await do_reply(ctx, update, "")

    # --- User ---
    elif d.startswith("user_dept|"):
        dept = d.split("|")[1]
        ctx.user_data["dept"] = dept
        vacs = get_vacancies(dept)
        if not vacs:
            await q.message.reply_text(f"⚠️ *{dept}* bo'limida hozircha vakansiyalar yo'q.", parse_mode="Markdown")
            return
        kb = [[InlineKeyboardButton(v[1], callback_data=f"user_vac|{v[1]}")] for v in vacs]
        await q.message.reply_text(
            f"💼 *{dept}* bo'limidagi vakansiyalar:",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
        ctx.user_data["step"] = "select_vac"

    elif d.startswith("user_vac|"):
        vac_title = d.split("|")[1]
        dept = ctx.user_data.get("dept")
        # Show vacancy details
        vacs = get_vacancies(dept)
        desc = ""
        for v in vacs:
            if v[1] == vac_title:
                desc = v[2]
                break
        ctx.user_data["vacancy"] = vac_title
        ctx.user_data["step"] = "enter_name"
        text = (
            f"💼 *{vac_title}*\n\n"
            f"📋 {desc}\n\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"Ariza topshirish uchun ma'lumotlaringizni to'ldiring.\n\n"
            f"👤 To'liq ismingizni yozing (Familiya Ism):"
        )
        await q.message.reply_text(text, parse_mode="Markdown", reply_markup=kb_cancel())

# ========== DOCUMENT & PHOTO HANDLER ==========

async def on_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data.get("step") != "upload_resume":
        await update.message.reply_text("Iltimos /start bosing.")
        return

    user = update.effective_user
    file_id = None
    file_type = None

    if update.message.document:
        doc = update.message.document
        fname = doc.file_name.lower()
        if not (fname.endswith(".pdf") or fname.endswith(".docx") or fname.endswith(".doc")):
            await update.message.reply_text("❌ Faqat PDF yoki Word (docx) yuboring.")
            return
        file_id = doc.file_id
        file_type = "PDF" if fname.endswith(".pdf") else "Word"

    elif update.message.photo:
        file_id = update.message.photo[-1].file_id
        file_type = "Rasm"

    if not file_id:
        await update.message.reply_text("❌ Fayl yuboring (PDF, Word yoki Rasm).")
        return

    app_data = {
        "name": ctx.user_data.get("name"),
        "phone": ctx.user_data.get("phone"),
        "dept": ctx.user_data.get("dept"),
        "vacancy": ctx.user_data.get("vacancy"),
        "uid": user.id,
        "username": user.username,
        "file_id": file_id,
        "file_type": file_type,
    }

    row_num = save_application(app_data)

    for admin_id in ADMIN_IDS:
        try:
            caption = (
                f"📨 *Yangi ariza #{row_num}*\n\n"
                f"👤 {app_data['name']}\n"
                f"📱 {app_data['phone']}\n"
                f"🏢 {app_data['dept']} → {app_data['vacancy']}\n"
                f"📱 @{user.username or '—'} | ID: `{user.id}`\n"
                f"📄 {file_type} | 🕐 {datetime.now().strftime('%H:%M %d.%m.%Y')}"
            )
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Qabul", callback_data=f"acc|{row_num}|{user.id}"),
                InlineKeyboardButton("❌ Rad", callback_data=f"rej|{row_num}|{user.id}")
            ]])
            if file_type == "Rasm":
                await ctx.bot.send_photo(chat_id=admin_id, photo=file_id, caption=caption, parse_mode="Markdown", reply_markup=kb)
            else:
                await ctx.bot.send_document(chat_id=admin_id, document=file_id, caption=caption, parse_mode="Markdown", reply_markup=kb)
        except Exception as e:
            logger.error(f"Admin {admin_id}: {e}")

    await update.message.reply_text(
        "✅ *Arizangiz muvaffaqiyatli yuborildi!*\n\n"
        "⏳ HR adminimiz ko'rib chiqib, tez orada siz bilan bog'lanadi.\n\n"
        "🙏 Vaqt ajratganingiz uchun rahmat!",
        parse_mode="Markdown",
        reply_markup=kb_user()
    )
    ctx.user_data.clear()

# ========== REPLY HELPER ==========

async def do_reply(ctx, update, comment):
    row_num = ctx.user_data.get("r_row")
    applicant_id = ctx.user_data.get("r_uid")
    status = ctx.user_data.get("r_status")
    update_status(row_num, status, comment)

    try:
        if "Qabul" in status:
            msg = (
                f"🎉 *Tabriklaymiz!*\n\n"
                f"Arizangiz ko'rib chiqildi va *qabul qilindi!*\n\n"
                f"📞 Tez orada HR menejerimiz siz bilan bog'lanadi.\n"
                f"Telegram: @ieltszone_hr\n\n"
            )
        else:
            msg = (
                f"📬 *Arizangiz natijasi*\n\n"
                f"Afsuski, arizangiz bu safar *rad etildi.*\n\n"
                f"💪 Umid uzmasdan, kelajakda yana ariza topshirishingiz mumkin!\n\n"
            )
        if comment:
            msg += f"💬 *Izoh:* {comment}"
        await ctx.bot.send_message(chat_id=applicant_id, text=msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Applicant reply error: {e}")

    ctx.user_data.clear()
    reply_text = f"✅ Javob yuborildi! Ariza #{row_num} yangilandi."
    if update.message:
        await update.message.reply_text(reply_text, reply_markup=kb_admin())
    else:
        await update.callback_query.message.reply_text(reply_text, reply_markup=kb_admin())

# ========== MAIN ==========

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.CONTACT, on_contact))
    app.add_handler(MessageHandler(filters.Document.ALL, on_file))
    app.add_handler(MessageHandler(filters.PHOTO, on_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    logger.info("✅ Bot started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
