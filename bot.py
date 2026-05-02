import logging
import os
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
ADMIN_IDS = [1054482233, 7375517762]

IELTS_INFO = (
    "🎓 *IELTS ZONE* haqida\n\n"
    "IELTS Zone — O'zbekistondagi eng yirik IELTS tayyorlov markazlaridan biri.\n\n"
    "📌 *Afzalliklarimiz:*\n"
    "• Tajribali va sertifikatlangan o'qituvchilar\n"
    "• Kichik guruhlar (max 8 kishi)\n"
    "• O'rtacha natija: 7.0+\n\n"
    "Biz bilan ishlash — karyerangizni rivojlantirish! 🚀"
)

# ========== SHEETS ==========

def sheets():
    creds_dict = json.loads(os.environ.get("GOOGLE_CREDENTIALS"))
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

def get_sheet(name):
    sp = sheets().open_by_key(SPREADSHEET_ID)
    try:
        return sp.worksheet(name)
    except:
        return sp.add_worksheet(title=name, rows=1000, cols=20)

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

def save_resume(name, dept, uid, username, file_id, ftype):
    ws = get_sheet("Resumes")
    rows = ws.get_all_values()
    if not rows or rows == [[]]:
        ws.append_row(["#", "Sana", "Ism", "Bolim", "TG ID", "Username", "File ID", "Turi", "Holat", "Izoh"])
    num = len(ws.get_all_values())
    ws.append_row([num, datetime.now().strftime("%Y-%m-%d %H:%M"), name, dept, str(uid), username or "-", file_id, ftype, "Kutilmoqda", ""])
    return num

def update_status(num, status, comment):
    ws = get_sheet("Resumes")
    for i, r in enumerate(ws.get_all_values()):
        if r and str(r[0]) == str(num):
            ws.update_cell(i+1, 9, status)
            ws.update_cell(i+1, 10, comment)
            return

# ========== KEYBOARDS ==========

def kb_main():
    return InlineKeyboardMarkup([[InlineKeyboardButton("📝 Ariza topshirish", callback_data="apply")]])

def kb_admin():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Bo'lim qo'shish", callback_data="a_add")],
        [InlineKeyboardButton("🗑 Bo'lim o'chirish", callback_data="a_del")],
        [InlineKeyboardButton("📋 Bo'limlar", callback_data="a_list")],
        [InlineKeyboardButton("📊 Arizalar", callback_data="a_resumes")],
    ])

def kb_depts():
    depts = get_departments()
    kb = [[InlineKeyboardButton(d, callback_data=f"d|{d}")] for d in depts]
    kb.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back")])
    return InlineKeyboardMarkup(kb), depts

def kb_back_admin():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin menu", callback_data="a_back")]])

# ========== COMMAND /start ==========

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    uid = update.effective_user.id
    if uid in ADMIN_IDS:
        await update.message.reply_text("👨‍💼 *Admin Panel*", reply_markup=kb_admin(), parse_mode="Markdown")
    else:
        await update.message.reply_text("👋 *IELTS Zone HR Botiga xush kelibsiz!*", reply_markup=kb_main(), parse_mode="Markdown")

# ========== CALLBACK HANDLER ==========

async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    uid = q.from_user.id

    # --- USER ---
    if d == "apply":
        await q.message.reply_text(IELTS_INFO, parse_mode="Markdown")
        kb, depts = kb_depts()
        if not depts:
            await q.message.reply_text("⚠️ Hozircha bo'sh o'rinlar yo'q.")
            return
        await q.message.reply_text("📋 *Qaysi bo'lim uchun?*", reply_markup=kb, parse_mode="Markdown")
        ctx.user_data["step"] = "dept"

    elif d.startswith("d|"):
        dept = d[2:]
        ctx.user_data["dept"] = dept
        ctx.user_data["step"] = "name"
        await q.message.reply_text(f"✅ Bo'lim: *{dept}*\n\n👤 To'liq ismingizni yozing:", parse_mode="Markdown")

    elif d == "back":
        ctx.user_data.clear()
        await q.message.reply_text("👋 *IELTS Zone HR Botiga xush kelibsiz!*", reply_markup=kb_main(), parse_mode="Markdown")

    # --- ADMIN ---
    elif d == "a_add" and uid in ADMIN_IDS:
        ctx.user_data["step"] = "adding_dept"
        await q.message.reply_text("✏️ Yangi bo'lim nomini yozing:", reply_markup=kb_back_admin())

    elif d == "a_del" and uid in ADMIN_IDS:
        depts = get_departments()
        if not depts:
            await q.message.reply_text("❌ Bo'limlar yo'q.", reply_markup=kb_back_admin())
            return
        kb = [[InlineKeyboardButton(f"🗑 {d}", callback_data=f"del|{d}")] for d in depts]
        kb.append([InlineKeyboardButton("🔙 Orqaga", callback_data="a_back")])
        await q.message.reply_text("Qaysi bo'limni o'chirish?", reply_markup=InlineKeyboardMarkup(kb))

    elif d.startswith("del|") and uid in ADMIN_IDS:
        dept = d[4:]
        del_dept(dept)
        await q.message.reply_text(f"✅ *{dept}* o'chirildi.", parse_mode="Markdown", reply_markup=kb_back_admin())

    elif d == "a_list" and uid in ADMIN_IDS:
        depts = get_departments()
        text = "📋 *Bo'limlar:*\n\n" + "\n".join(f"• {x}" for x in depts) if depts else "📋 Bo'limlar yo'q."
        await q.message.reply_text(text, parse_mode="Markdown", reply_markup=kb_back_admin())

    elif d == "a_resumes" and uid in ADMIN_IDS:
        ws = get_sheet("Resumes")
        rows = ws.get_all_values()
        if len(rows) <= 1:
            text = "📊 Hozircha arizalar yo'q."
        else:
            text = "📊 *Arizalar:*\n\n"
            for r in rows[1:]:
                if len(r) >= 9:
                    text += f"#{r[0]} | {r[2]} | {r[3]} | {r[8]}\n"
        await q.message.reply_text(text, parse_mode="Markdown", reply_markup=kb_back_admin())

    elif d == "a_back" and uid in ADMIN_IDS:
        ctx.user_data.clear()
        await q.message.reply_text("👨‍💼 *Admin Panel*", reply_markup=kb_admin(), parse_mode="Markdown")

    elif (d.startswith("acc|") or d.startswith("rej|")) and uid in ADMIN_IDS:
        parts = d.split("|")
        action, row_num, applicant_id = parts[0], parts[1], int(parts[2])
        status = "✅ Qabul qilindi" if action == "acc" else "❌ Rad etildi"
        ctx.user_data["step"] = "replying"
        ctx.user_data["r_row"] = row_num
        ctx.user_data["r_uid"] = applicant_id
        ctx.user_data["r_status"] = status
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Izoхsiz yuborish", callback_data="skip_reply")]])
        await q.message.reply_text(f"Ariza #{row_num} — *{status}*\n\nIzoh yozing:", reply_markup=kb, parse_mode="Markdown")

    elif d == "skip_reply" and uid in ADMIN_IDS:
        await do_reply(ctx, update, "")

# ========== MESSAGE HANDLER ==========

async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    step = ctx.user_data.get("step")
    text = update.message.text.strip()

    if step == "name":
        if len(text) < 3:
            await update.message.reply_text("⚠️ Kamida 3 harf kiriting.")
            return
        ctx.user_data["name"] = text
        ctx.user_data["step"] = "resume"
        await update.message.reply_text(
            f"👋 Salom, *{text}*!\n\n📎 Rezyumeni yuboring (PDF yoki Word):",
            parse_mode="Markdown"
        )

    elif step == "adding_dept" and uid in ADMIN_IDS:
        if not text:
            await update.message.reply_text("⚠️ Nom bo'sh bo'lmasin.")
            return
        add_dept(text)
        await update.message.reply_text(f"✅ *{text}* qo'shildi!", parse_mode="Markdown")
        ctx.user_data.clear()
        await update.message.reply_text("👨‍💼 *Admin Panel*", reply_markup=kb_admin(), parse_mode="Markdown")

    elif step == "replying" and uid in ADMIN_IDS:
        await do_reply(ctx, update, text)

    else:
        if uid in ADMIN_IDS:
            await update.message.reply_text("👨‍💼 *Admin Panel*", reply_markup=kb_admin(), parse_mode="Markdown")
        else:
            await update.message.reply_text("👋 *IELTS Zone HR Botiga xush kelibsiz!*", reply_markup=kb_main(), parse_mode="Markdown")

# ========== DOCUMENT HANDLER ==========

async def on_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data.get("step") != "resume":
        await update.message.reply_text("Iltimos /start bosing.")
        return

    doc = update.message.document
    fname = doc.file_name.lower()
    if not (fname.endswith(".pdf") or fname.endswith(".docx") or fname.endswith(".doc")):
        await update.message.reply_text("❌ Faqat PDF yoki Word (docx) yuboring.")
        return

    user = update.effective_user
    name = ctx.user_data["name"]
    dept = ctx.user_data["dept"]
    ftype = "PDF" if fname.endswith(".pdf") else "Word"
    row_num = save_resume(name, dept, user.id, user.username, doc.file_id, ftype)

    for admin_id in ADMIN_IDS:
        try:
            caption = (
                f"📨 *Yangi ariza #{row_num}*\n\n"
                f"👤 {name}\n🏢 {dept}\n"
                f"📱 @{user.username or '—'} | ID: `{user.id}`\n"
                f"📄 {ftype} | 🕐 {datetime.now().strftime('%H:%M %d.%m.%Y')}"
            )
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Qabul", callback_data=f"acc|{row_num}|{user.id}"),
                InlineKeyboardButton("❌ Rad", callback_data=f"rej|{row_num}|{user.id}")
            ]])
            await ctx.bot.send_document(chat_id=admin_id, document=doc.file_id, caption=caption, parse_mode="Markdown", reply_markup=kb)
        except Exception as e:
            logger.error(f"Admin {admin_id}: {e}")

    await update.message.reply_text("✅ *Rezyumengiz yuborildi!*\n\n⏳ Tez orada bog'lanamiz. Rahmat! 🙏", parse_mode="Markdown")
    ctx.user_data.clear()

# ========== REPLY HELPER ==========

async def do_reply(ctx, update, comment):
    row_num = ctx.user_data.get("r_row")
    applicant_id = ctx.user_data.get("r_uid")
    status = ctx.user_data.get("r_status")
    update_status(row_num, status, comment)
    try:
        msg = f"📬 *Arizangiz natijasi*\n\nHolat: *{status}*"
        if comment:
            msg += f"\n💬 {comment}"
        await ctx.bot.send_message(chat_id=applicant_id, text=msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Applicant reply error: {e}")

    reply_msg = f"✅ Yuborildi! Ariza #{row_num} yangilandi."
    if update.message:
        await update.message.reply_text(reply_msg)
    else:
        await update.callback_query.message.reply_text(reply_msg)

    ctx.user_data.clear()
    if update.message:
        await update.message.reply_text("👨‍💼 *Admin Panel*", reply_markup=kb_admin(), parse_mode="Markdown")
    else:
        await update.callback_query.message.reply_text("👨‍💼 *Admin Panel*", reply_markup=kb_admin(), parse_mode="Markdown")

# ========== MAIN ==========

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    logger.info("✅ Bot started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
