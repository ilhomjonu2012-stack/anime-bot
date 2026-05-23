import logging
import sqlite3
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

BOT_TOKEN = "8979966075:AAHOlUPn7g6q49Om-D2ogufEYQvzG07l5jM"
ADMIN_IDS = [7882729721]
PAYME_NARX = 10000  # so'm

# States
(ANIME_NOMI, ANIME_JANR, ANIME_KOD, ANIME_RASM, ANIME_VIDEO_FILE, ANIME_TURI) = range(6)
(SERIYA_ANIME_ID, SERIYA_NOMI, SERIYA_VIDEO) = range(10, 13)
IZLASH_HOLAT = 20
QOLLANMA_EDIT, REKLAMA_EDIT = 30, 31
POST_MATN = 40
ALOHIDA_ID, ALOHIDA_MATN = 50, 51
MAJBURIY_KANAL = 60
STAFF_ID = 70
TOLOV_CHECK = 80
VIP_NARX_EDIT = 90
TAVSIF_EDIT = 100

logging.basicConfig(level=logging.INFO)

# ===== DATABASE =====
def db():
    conn = sqlite3.connect("anime.db")
    conn.row_factory = sqlite3.Row
    return conn

def db_setup():
    with db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS animelar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nomi TEXT NOT NULL, janr TEXT, kod TEXT,
            rasm TEXT, video TEXT, turi TEXT DEFAULT 'anime',
            vip INTEGER DEFAULT 0, korishlar INTEGER DEFAULT 0,
            tavsif TEXT
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS seriyalar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anime_id INTEGER, nomi TEXT, video TEXT,
            FOREIGN KEY(anime_id) REFERENCES animelar(id)
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS foydalanuvchilar (
            user_id INTEGER PRIMARY KEY, ism TEXT, username TEXT,
            vip INTEGER DEFAULT 0, vip_so_rov INTEGER DEFAULT 0,
            staff INTEGER DEFAULT 0, referral_id INTEGER DEFAULT 0,
            referrallar INTEGER DEFAULT 0, joined TEXT
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS sozlamalar (
            kalit TEXT PRIMARY KEY, qiymat TEXT
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS kanallar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kanal_id TEXT, nomi TEXT
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS tolovlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, chek TEXT, holat TEXT DEFAULT 'kutilmoqda',
            sana TEXT
        )""")
        conn.execute("INSERT OR IGNORE INTO sozlamalar VALUES ('qollanma', '📖 Botdan foydalanish qollanmasi:\n\n🔍 Anime izlash - nom yoki kod orqali anime toping\n🔴 Shorts - qisqa anime kliplar\n💎 VIP - barcha premium animelarga kirish\n👥 Referral - do\'stlarni taklif qilib bonus oling')")
        conn.execute("INSERT OR IGNORE INTO sozlamalar VALUES ('reklama', '📢 Reklama va Homiylik uchun:\n\n👤 Admin: @admin\n💰 Narxlar kelishiladi')")
        conn.execute("INSERT OR IGNORE INTO sozlamalar VALUES ('vip_narx', '10000')")
        conn.execute("INSERT OR IGNORE INTO sozlamalar VALUES ('vip_mud', '30')")
        conn.execute("INSERT OR IGNORE INTO sozlamalar VALUES ('xush_kelibsiz', '🎌 Anime Botga xush kelibsiz!\n\nBarcha sevimli animeleringizni shu yerda toping 🔥')")
        conn.execute("INSERT OR IGNORE INTO sozlamalar VALUES ('payme_karta', '8600 XXXX XXXX XXXX')")
        conn.execute("INSERT OR IGNORE INTO sozlamalar VALUES ('click_karta', '8600 XXXX XXXX XXXX')")
        conn.commit()

def is_admin(uid): return uid in ADMIN_IDS
def is_staff(uid):
    if is_admin(uid): return True
    with db() as conn:
        r = conn.execute("SELECT staff FROM foydalanuvchilar WHERE user_id=?", (uid,)).fetchone()
        return r and r["staff"] == 1
def is_vip(uid):
    with db() as conn:
        r = conn.execute("SELECT vip FROM foydalanuvchilar WHERE user_id=?", (uid,)).fetchone()
        return r and r["vip"] == 1

def register_user(uid, ism, username=None, ref=None):
    from datetime import datetime
    with db() as conn:
        exists = conn.execute("SELECT user_id FROM foydalanuvchilar WHERE user_id=?", (uid,)).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO foydalanuvchilar (user_id, ism, username, referral_id, joined) VALUES (?,?,?,?,?)",
                (uid, ism, username or '', ref or 0, datetime.now().strftime("%Y-%m-%d"))
            )
            if ref and ref != uid:
                conn.execute("UPDATE foydalanuvchilar SET referrallar=referrallar+1 WHERE user_id=?", (ref,))
            conn.commit()

async def majburiy_tekshir(uid, context):
    with db() as conn:
        kanallar = conn.execute("SELECT * FROM kanallar").fetchall()
    if not kanallar: return True
    for k in kanallar:
        try:
            m = await context.bot.get_chat_member(k["kanal_id"], uid)
            if m.status in ["left", "kicked"]: return False
        except: pass
    return True

def asosiy_menu(uid=None):
    buttons = [
        [KeyboardButton("🔍 Anime izlash"), KeyboardButton("🔴 Shorts")],
        [KeyboardButton("💎 VIP"), KeyboardButton("👥 Referral")],
        [KeyboardButton("📚 Qollanma"), KeyboardButton("💰 Reklama")],
    ]
    if uid and is_staff(uid):
        buttons.append([KeyboardButton("⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_sozlama(kalit):
    with db() as conn:
        r = conn.execute("SELECT qiymat FROM sozlamalar WHERE kalit=?", (kalit,)).fetchone()
        return r["qiymat"] if r else ""

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ref = None
    if context.args:
        try: ref = int(context.args[0])
        except: pass
    register_user(user.id, user.first_name, user.username, ref)

    if not await majburiy_tekshir(user.id, context):
        with db() as conn:
            kanallar = conn.execute("SELECT * FROM kanallar").fetchall()
        kb = [[InlineKeyboardButton(f"📢 {k['nomi']}", url=f"https://t.me/{k['kanal_id'].replace('@','')}")] for k in kanallar]
        kb.append([InlineKeyboardButton("✅ Tekshirish", callback_data="obuna_tekshir")])
        await update.message.reply_text(
            "⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
            reply_markup=InlineKeyboardMarkup(kb))
        return

    vip = is_vip(user.id)
    xush = get_sozlama("xush_kelibsiz")

    badge = "💎 VIP" if vip else ("🛡️ Staff" if is_staff(user.id) else "👤 Oddiy")

    kb = [
        [InlineKeyboardButton("🔍 Nom bo'yicha", callback_data="izlash_nom"),
         InlineKeyboardButton("🔑 Kod bo'yicha", callback_data="izlash_kod")],
        [InlineKeyboardButton("📋 Barcha animelar", callback_data="barcha_anime")],
        [InlineKeyboardButton("🔥 Top animelar", callback_data="top_anime"),
         InlineKeyboardButton("🆕 Yangi qo'shilgan", callback_data="yangi_anime")],
    ]
    await update.message.reply_text(
        f"{xush}\n\n👤 {user.first_name} | {badge}",
        reply_markup=InlineKeyboardMarkup(kb))
    await update.message.reply_text("📌 Pastki menyu:", reply_markup=asosiy_menu(user.id))

async def obuna_tekshir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    if await majburiy_tekshir(user.id, context):
        vip = is_vip(user.id)
        badge = "💎 VIP" if vip else "👤 Oddiy"
        kb = [
            [InlineKeyboardButton("🔍 Nom bo'yicha", callback_data="izlash_nom"),
             InlineKeyboardButton("🔑 Kod bo'yicha", callback_data="izlash_kod")],
            [InlineKeyboardButton("📋 Barcha animelar", callback_data="barcha_anime")],
            [InlineKeyboardButton("🔥 Top animelar", callback_data="top_anime")],
        ]
        await query.edit_message_text(
            f"✅ Muvaffaqiyatli!\n\n👤 {user.first_name} | {badge}",
            reply_markup=InlineKeyboardMarkup(kb))
    else:
        await query.answer("❌ Hali obuna bo'lmadingiz!", show_alert=True)

async def start_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    vip = is_vip(user.id)
    badge = "💎 VIP" if vip else ("🛡️ Staff" if is_staff(user.id) else "👤 Oddiy")
    kb = [
        [InlineKeyboardButton("🔍 Nom bo'yicha", callback_data="izlash_nom"),
         InlineKeyboardButton("🔑 Kod bo'yicha", callback_data="izlash_kod")],
        [InlineKeyboardButton("📋 Barcha animelar", callback_data="barcha_anime")],
        [InlineKeyboardButton("🔥 Top animelar", callback_data="top_anime"),
         InlineKeyboardButton("🆕 Yangi", callback_data="yangi_anime")],
    ]
    await query.edit_message_text(
        f"🏠 Bosh sahifa\n\n👤 {user.first_name} | {badge}",
        reply_markup=InlineKeyboardMarkup(kb))

# ===== IZLASH =====
async def izlash_nom_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["izlash_turi"] = "nom"
    await query.edit_message_text("🔍 Anime nomini yozing:\n\n(masalan: Naruto, One Piece...)")
    return IZLASH_HOLAT

async def izlash_kod_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["izlash_turi"] = "kod"
    await query.edit_message_text("🔑 Anime kodini yozing:\n\n(masalan: 001, 123...)")
    return IZLASH_HOLAT

async def izlash_natija(update: Update, context: ContextTypes.DEFAULT_TYPE):
    matn = update.message.text
    turi = context.user_data.get("izlash_turi", "nom")
    uid = update.effective_user.id
    vip = is_vip(uid)
    with db() as conn:
        if turi == "kod":
            rows = conn.execute(
                "SELECT * FROM animelar WHERE kod=? AND turi='anime'" + ("" if vip or is_admin(uid) else " AND vip=0"),
                (matn,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM animelar WHERE nomi LIKE ? AND turi='anime'" + ("" if vip or is_admin(uid) else " AND vip=0"),
                (f"%{matn}%",)).fetchall()
    if not rows:
        await update.message.reply_text(
            "😕 Hech narsa topilmadi!\n\nBoshqa nom yoki kod bilan urinib ko'ring.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Bosh sahifa", callback_data="start")]]))
        return ConversationHandler.END
    kb = []
    for r in rows:
        label = f"{'🔒 ' if r['vip'] else '▶️ '}{r['nomi']}"
        if r['janr']: label += f" | {r['janr']}"
        kb.append([InlineKeyboardButton(label, callback_data=f"anime_{r['id']}")])
    kb.append([InlineKeyboardButton("🏠 Bosh sahifa", callback_data="start")])
    await update.message.reply_text(
        f"🔍 Natijalar: {len(rows)} ta topildi",
        reply_markup=InlineKeyboardMarkup(kb))
    return ConversationHandler.END

# ===== KLAVIATURA =====
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = update.message.text
    uid = update.effective_user.id

    if t == "🔍 Anime izlash":
        kb = [
            [InlineKeyboardButton("🔍 Nom bo'yicha", callback_data="izlash_nom"),
             InlineKeyboardButton("🔑 Kod bo'yicha", callback_data="izlash_kod")],
            [InlineKeyboardButton("📋 Barcha animelar", callback_data="barcha_anime")],
            [InlineKeyboardButton("🔥 Top 10", callback_data="top_anime"),
             InlineKeyboardButton("🆕 Yangi", callback_data="yangi_anime")],
        ]
        await update.message.reply_text("🔍 Quyidagilardan birini tanlang:", reply_markup=InlineKeyboardMarkup(kb))

    elif t == "🔴 Shorts":
        vip = is_vip(uid)
        with db() as conn:
            rows = conn.execute(
                "SELECT * FROM animelar WHERE turi='shorts'" + ("" if vip or is_admin(uid) else " AND vip=0") + " ORDER BY id DESC"
            ).fetchall()
        if not rows:
            await update.message.reply_text("😕 Hozircha shorts yo'q.")
            return
        kb = [[InlineKeyboardButton(f"▶️ {r['nomi']}", callback_data=f"anime_{r['id']}")] for r in rows]
        await update.message.reply_text("🔴 Shorts:", reply_markup=InlineKeyboardMarkup(kb))

    elif t == "📚 Qollanma":
        await update.message.reply_text(f"📚 Qo'llanma:\n\n{get_sozlama('qollanma')}")

    elif t == "💎 VIP":
        if is_vip(uid):
            await update.message.reply_text("💎 Siz allaqachon VIP foydalanuvchisiz!\n\nBarcha premium imkoniyatlar sizda bor ✅")
            return
        narx = get_sozlama("vip_narx")
        mud = get_sozlama("vip_mud")
        payme = get_sozlama("payme_karta")
        click = get_sozlama("click_karta")
        kb = [
            [InlineKeyboardButton("💳 To'lov qilish", callback_data="vip_tolov")],
            [InlineKeyboardButton("📸 Chek yuborish", callback_data="chek_yuborish")],
        ]
        await update.message.reply_text(
            f"💎 VIP Obuna\n\n"
            f"💰 Narxi: {narx} so'm\n"
            f"⏳ Muddati: {mud} kun\n\n"
            f"✅ VIP imkoniyatlar:\n"
            f"• Barcha VIP animelarga kirish\n"
            f"• Seriyalarga to'liq kirish\n"
            f"• Tezkor yangilanishlar\n"
            f"• Reklama ko'rsatilmaydi\n\n"
            f"💳 To'lov rekvizitlari:\n"
            f"• Payme: {payme}\n"
            f"• Click: {click}",
            reply_markup=InlineKeyboardMarkup(kb))

    elif t == "👥 Referral":
        with db() as conn:
            r = conn.execute("SELECT referrallar FROM foydalanuvchilar WHERE user_id=?", (uid,)).fetchone()
        ref_soni = r["referrallar"] if r else 0
        bot_info = await context.bot.get_me()
        link = f"https://t.me/{bot_info.username}?start={uid}"
        progress = ref_soni % 5
        bar = "🟩" * progress + "⬜" * (5 - progress)
        await update.message.reply_text(
            f"👥 Referral Tizimi\n\n"
            f"🔗 Sizning havolangiz:\n{link}\n\n"
            f"👫 Jalb qilganlar: {ref_soni} ta\n"
            f"🎁 Keyingi bonusgacha: {5 - progress} ta\n"
            f"{bar}\n\n"
            f"ℹ️ Har 5 ta referral uchun 1 kun VIP beriladi!")

    elif t == "💰 Reklama":
        await update.message.reply_text(f"💰 Reklama va Homiylik:\n\n{get_sozlama('reklama')}")

    elif t == "⚙️ Admin Panel":
        if not is_staff(uid):
            await update.message.reply_text("❌ Ruxsat yo'q!")
            return
        await _admin_panel_msg(update.message, uid)

# ===== ANIMELAR =====
async def barcha_anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    vip = is_vip(uid)
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM animelar WHERE turi='anime'" + ("" if vip or is_admin(uid) else " AND vip=0") + " ORDER BY id DESC"
        ).fetchall()
    if not rows:
        await query.edit_message_text(
            "😕 Hozircha anime yo'q.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Bosh sahifa", callback_data="start")]]))
        return
    kb = []
    for r in rows:
        label = f"{'🔒 ' if r['vip'] else '▶️ '}{r['nomi']}"
        if r['janr']: label += f" | {r['janr']}"
        kb.append([InlineKeyboardButton(label, callback_data=f"anime_{r['id']}")])
    kb.append([InlineKeyboardButton("🏠 Bosh sahifa", callback_data="start")])
    await query.edit_message_text(f"📋 Barcha animelar ({len(rows)} ta):", reply_markup=InlineKeyboardMarkup(kb))

async def top_anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    vip = is_vip(uid)
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM animelar WHERE turi='anime'" + ("" if vip or is_admin(uid) else " AND vip=0") + " ORDER BY korishlar DESC LIMIT 10"
        ).fetchall()
    if not rows:
        await query.edit_message_text(
            "😕 Hozircha anime yo'q.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Bosh sahifa", callback_data="start")]]))
        return
    medals = ["🥇", "🥈", "🥉"] + ["🔥"] * 7
    kb = [[InlineKeyboardButton(f"{medals[i]} {r['nomi']} | 👁 {r['korishlar']}", callback_data=f"anime_{r['id']}")] for i, r in enumerate(rows)]
    kb.append([InlineKeyboardButton("🏠 Bosh sahifa", callback_data="start")])
    await query.edit_message_text("🔥 Top 10 animelar:", reply_markup=InlineKeyboardMarkup(kb))

async def yangi_anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    vip = is_vip(uid)
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM animelar WHERE turi='anime'" + ("" if vip or is_admin(uid) else " AND vip=0") + " ORDER BY id DESC LIMIT 10"
        ).fetchall()
    if not rows:
        await query.edit_message_text(
            "😕 Hozircha anime yo'q.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Bosh sahifa", callback_data="start")]]))
        return
    kb = [[InlineKeyboardButton(f"🆕 {r['nomi']}", callback_data=f"anime_{r['id']}")] for r in rows]
    kb.append([InlineKeyboardButton("🏠 Bosh sahifa", callback_data="start")])
    await query.edit_message_text("🆕 Yangi qo'shilgan animelar:", reply_markup=InlineKeyboardMarkup(kb))

async def anime_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_id = int(query.data.split("_")[1])
    uid = query.from_user.id
    with db() as conn:
        anime = conn.execute("SELECT * FROM animelar WHERE id=?", (anime_id,)).fetchone()
        conn.execute("UPDATE animelar SET korishlar=korishlar+1 WHERE id=?", (anime_id,))
        seriyalar = conn.execute("SELECT * FROM seriyalar WHERE anime_id=? ORDER BY id", (anime_id,)).fetchall()
        conn.commit()
    if not anime:
        await query.edit_message_text("❌ Anime topilmadi.")
        return
    if anime["vip"] and not is_vip(uid) and not is_admin(uid):
        kb = [
            [InlineKeyboardButton("💎 VIP olish", callback_data="vip_olish_cb")],
            [InlineKeyboardButton("🏠 Orqaga", callback_data="barcha_anime")]
        ]
        await query.edit_message_text(
            "🔒 Bu anime faqat VIP foydalanuvchilar uchun!\n\n"
            "💎 VIP oling va barcha premium animelarga kiring!\n\n"
            "✅ 30 kun | Arzon narx | To'liq kirish",
            reply_markup=InlineKeyboardMarkup(kb))
        return

    badge = "🔒 VIP" if anime["vip"] else "✅ Bepul"
    matn = (
        f"🎌 {anime['nomi']}\n\n"
        f"🏷️ Janr: {anime['janr'] or '—'}\n"
        f"🔑 Kod: {anime['kod'] or '—'}\n"
        f"👁️ Ko'rishlar: {anime['korishlar']}\n"
        f"💎 Turi: {badge}"
    )
    if anime["tavsif"]:
        matn += f"\n\n📝 Tavsif:\n{anime['tavsif']}"

    kb = []
    if seriyalar:
        matn += f"\n\n📺 Seriyalar: {len(seriyalar)} ta"
        for s in seriyalar:
            kb.append([InlineKeyboardButton(f"▶️ {s['nomi']}", callback_data=f"seriya_{s['id']}")])

    if is_staff(uid):
        kb.append([
            InlineKeyboardButton("🗑️ O'chirish", callback_data=f"del_{anime_id}"),
            InlineKeyboardButton("✏️ Tahrirlash", callback_data=f"aedit_{anime_id}")
        ])
    kb.append([InlineKeyboardButton("🔙 Orqaga", callback_data="barcha_anime")])

    if anime["video"] and not seriyalar:
        await query.message.reply_video(video=anime["video"], caption=matn, reply_markup=InlineKeyboardMarkup(kb))
        await query.delete_message()
    elif anime["rasm"]:
        await query.message.reply_photo(photo=anime["rasm"], caption=matn, reply_markup=InlineKeyboardMarkup(kb))
        await query.delete_message()
    else:
        await query.edit_message_text(matn, reply_markup=InlineKeyboardMarkup(kb))

async def seriya_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.split("_")[1])
    with db() as conn:
        s = conn.execute("SELECT * FROM seriyalar WHERE id=?", (sid,)).fetchone()
    if not s:
        await query.edit_message_text("❌ Seriya topilmadi.")
        return
    kb = [[InlineKeyboardButton("🔙 Orqaga", callback_data=f"anime_{s['anime_id']}")]]
    if s["video"]:
        await query.message.reply_video(video=s["video"], caption=f"▶️ {s['nomi']}", reply_markup=InlineKeyboardMarkup(kb))
        await query.delete_message()
    else:
        await query.edit_message_text(s["nomi"], reply_markup=InlineKeyboardMarkup(kb))

# ===== VIP =====
async def vip_olish_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    if is_vip(uid):
        await query.edit_message_text(
            "💎 Siz allaqachon VIP foydalanuvchisiz!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Bosh sahifa", callback_data="start")]]))
        return
    narx = get_sozlama("vip_narx")
    mud = get_sozlama("vip_mud")
    payme = get_sozlama("payme_karta")
    click = get_sozlama("click_karta")
    kb = [
        [InlineKeyboardButton("💳 To'lov qilish", callback_data="vip_tolov")],
        [InlineKeyboardButton("📸 Chek yuborish", callback_data="chek_yuborish")],
        [InlineKeyboardButton("🏠 Orqaga", callback_data="start")]
    ]
    await query.edit_message_text(
        f"💎 VIP Obuna\n\n"
        f"💰 Narxi: {narx} so'm\n"
        f"⏳ Muddati: {mud} kun\n\n"
        f"✅ VIP imkoniyatlar:\n"
        f"• Barcha VIP animelarga kirish\n"
        f"• Seriyalarga to'liq kirish\n"
        f"• Tezkor yangilanishlar\n\n"
        f"💳 To'lov rekvizitlari:\n"
        f"• Payme: {payme}\n"
        f"• Click: {click}",
        reply_markup=InlineKeyboardMarkup(kb))

async def vip_tolov(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    narx = get_sozlama("vip_narx")
    payme = get_sozlama("payme_karta")
    click = get_sozlama("click_karta")
    kb = [
        [InlineKeyboardButton("📸 Chek yuborish", callback_data="chek_yuborish")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="start")]
    ]
    await query.edit_message_text(
        f"💳 To'lov\n\n"
        f"💰 Narxi: {narx} so'm\n\n"
        f"📋 Rekvizitlar:\n"
        f"• Payme: {payme}\n"
        f"• Click: {click}\n\n"
        f"⚠️ To'lov qilib chek rasmini yuboring!",
        reply_markup=InlineKeyboardMarkup(kb))

async def chek_yuborish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📸 To'lov cheki rasmini yuboring:\n\n"
        "⚠️ Faqat rasm formatida yuboring!")
    return TOLOV_CHECK

async def chek_qabul(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = update.effective_user
    from datetime import datetime
    chek_id = None
    if update.message.photo:
        chek_id = update.message.photo[-1].file_id
    elif update.message.document:
        chek_id = update.message.document.file_id

    if not chek_id:
        await update.message.reply_text("❌ Rasm yuboring!")
        return TOLOV_CHECK

    with db() as conn:
        conn.execute("INSERT INTO tolovlar (user_id, chek, sana) VALUES (?,?,?)",
            (uid, chek_id, datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.commit()
        tolov_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]

    for admin_id in ADMIN_IDS:
        try:
            kb = [[
                InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"vip_tasdiq_{uid}"),
                InlineKeyboardButton("❌ Rad etish", callback_data=f"vip_rad_{uid}")
            ]]
            await context.bot.send_photo(
                chat_id=admin_id, photo=chek_id,
                caption=f"💳 VIP To'lov #{tolov_id}\n\n"
                        f"👤 Foydalanuvchi: {user.first_name}\n"
                        f"🆔 ID: {uid}\n"
                        f"📱 Username: @{user.username or 'yo\'q'}\n"
                        f"📅 Sana: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                reply_markup=InlineKeyboardMarkup(kb))
        except: pass

    await update.message.reply_text(
        "✅ Chek qabul qilindi!\n\n"
        "⏳ Admin tekshirgandan so'ng VIP beriladi.\n"
        "Odatda 1-24 soat ichida!")
    return ConversationHandler.END

async def vip_tasdiq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    tid = int(query.data.split("_")[2])
    with db() as conn:
        conn.execute("UPDATE foydalanuvchilar SET vip=1, vip_so_rov=0 WHERE user_id=?", (tid,))
        conn.commit()
    try:
        await context.bot.send_message(
            tid,
            "🎉 Tabriklaymiz!\n\n"
            "💎 Siz endi VIP foydalanuvchisiz!\n\n"
            "✅ Barcha premium animelarga kirish huquqiga egasiz!\n\n"
            "/start bosing!")
    except: pass
    await query.edit_message_caption(caption=query.message.caption + "\n\n✅ TASDIQLANDI")

async def vip_rad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    tid = int(query.data.split("_")[2])
    try:
        await context.bot.send_message(
            tid,
            "❌ To'lovingiz rad etildi.\n\n"
            "Sabab: To'lov tasdiqlanmadi.\n"
            "Admin bilan bog'laning!")
    except: pass
    await query.edit_message_caption(caption=query.message.caption + "\n\n❌ RAD ETILDI")

# ===== ADMIN PANEL =====
async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_staff(update.effective_user.id):
        await update.message.reply_text("❌ Ruxsat yo'q!")
        return
    await _admin_panel_msg(update.message, update.effective_user.id)

async def _admin_panel_msg(msg, uid):
    with db() as conn:
        a = conn.execute("SELECT COUNT(*) as c FROM animelar WHERE turi='anime'").fetchone()["c"]
        sh = conn.execute("SELECT COUNT(*) as c FROM animelar WHERE turi='shorts'").fetchone()["c"]
        u = conn.execute("SELECT COUNT(*) as c FROM foydalanuvchilar").fetchone()["c"]
        v = conn.execute("SELECT COUNT(*) as c FROM foydalanuvchilar WHERE vip=1").fetchone()["c"]
        t = conn.execute("SELECT COUNT(*) as c FROM tolovlar WHERE holat='kutilmoqda'").fetchone()["c"]
        bugun = conn.execute("SELECT COUNT(*) as c FROM foydalanuvchilar WHERE joined=date('now')").fetchone()["c"]

    panel_text = (
        f"⚙️ Admin Panel\n"
        f"{'━' * 25}\n\n"
        f"📊 Statistika:\n"
        f"🎌 Animelar: {a} ta | 🔴 Shorts: {sh} ta\n"
        f"👥 Foydalanuvchilar: {u} ta\n"
        f"🆕 Bugun qo'shildi: {bugun} ta\n"
        f"💎 VIP: {v} ta\n"
        f"💳 Kutilayotgan to'lovlar: {t} ta\n\n"
        f"{'━' * 25}"
    )

    kb = []

    # Anime boshqaruv
    kb.append([
        InlineKeyboardButton("➕ Anime qo'shish", callback_data="anime_qosh"),
        InlineKeyboardButton("➕ Shorts qo'shish", callback_data="shorts_qosh")
    ])
    kb.append([
        InlineKeyboardButton("📋 Animelar ro'yxati", callback_data="admin_anime_list"),
        InlineKeyboardButton("🎬 Seriya qo'shish", callback_data="seriya_qosh")
    ])
    kb.append([
        InlineKeyboardButton("✏️ Anime tahrirlash", callback_data="anime_tahrir_list"),
        InlineKeyboardButton("✏️ Seriya tahrirlash", callback_data="seriya_tahrir_list")
    ])

    # Xabar yuborish
    kb.append([
        InlineKeyboardButton("📢 Post yuborish", callback_data="post_tayyorla"),
        InlineKeyboardButton("✉️ Alohida xabar", callback_data="alohida_xabar")
    ])

    # Foydalanuvchilar
    kb.append([
        InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="userlar"),
        InlineKeyboardButton("💳 To'lovlar", callback_data="tolovlar_list")
    ])

    if is_admin(uid):
        kb.append([
            InlineKeyboardButton("📢 Majburiy a'zo", callback_data="majburiy_azo"),
            InlineKeyboardButton("🛡️ Staff qo'shish", callback_data="staff_qosh")
        ])

    # Sozlamalar
    kb.append([
        InlineKeyboardButton("📖 Qo'llanma", callback_data="qollanma_edit"),
        InlineKeyboardButton("💰 Reklama", callback_data="reklama_edit")
    ])
    kb.append([
        InlineKeyboardButton("💎 VIP narxi", callback_data="vip_narx_edit"),
        InlineKeyboardButton("👋 Xush kelibsiz", callback_data="xush_edit")
    ])
    kb.append([
        InlineKeyboardButton("💳 Karta raqamlar", callback_data="karta_edit"),
        InlineKeyboardButton("📊 Batafsil stat", callback_data="statistika")
    ])

    await msg.reply_text(panel_text, reply_markup=InlineKeyboardMarkup(kb))

async def admin_panel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    if not is_staff(uid): return
    with db() as conn:
        a = conn.execute("SELECT COUNT(*) as c FROM animelar WHERE turi='anime'").fetchone()["c"]
        sh = conn.execute("SELECT COUNT(*) as c FROM animelar WHERE turi='shorts'").fetchone()["c"]
        u = conn.execute("SELECT COUNT(*) as c FROM foydalanuvchilar").fetchone()["c"]
        v = conn.execute("SELECT COUNT(*) as c FROM foydalanuvchilar WHERE vip=1").fetchone()["c"]
        t = conn.execute("SELECT COUNT(*) as c FROM tolovlar WHERE holat='kutilmoqda'").fetchone()["c"]
        bugun = conn.execute("SELECT COUNT(*) as c FROM foydalanuvchilar WHERE joined=date('now')").fetchone()["c"]

    panel_text = (
        f"⚙️ Admin Panel\n"
        f"{'━' * 25}\n\n"
        f"📊 Statistika:\n"
        f"🎌 Animelar: {a} ta | 🔴 Shorts: {sh} ta\n"
        f"👥 Foydalanuvchilar: {u} ta\n"
        f"🆕 Bugun qo'shildi: {bugun} ta\n"
        f"💎 VIP: {v} ta\n"
        f"💳 Kutilayotgan to'lovlar: {t} ta\n\n"
        f"{'━' * 25}"
    )

    kb = []
    kb.append([
        InlineKeyboardButton("➕ Anime qo'shish", callback_data="anime_qosh"),
        InlineKeyboardButton("➕ Shorts qo'shish", callback_data="shorts_qosh")
    ])
    kb.append([
        InlineKeyboardButton("📋 Animelar ro'yxati", callback_data="admin_anime_list"),
        InlineKeyboardButton("🎬 Seriya qo'shish", callback_data="seriya_qosh")
    ])
    kb.append([
        InlineKeyboardButton("✏️ Anime tahrirlash", callback_data="anime_tahrir_list"),
        InlineKeyboardButton("✏️ Seriya tahrirlash", callback_data="seriya_tahrir_list")
    ])
    kb.append([
        InlineKeyboardButton("📢 Post yuborish", callback_data="post_tayyorla"),
        InlineKeyboardButton("✉️ Alohida xabar", callback_data="alohida_xabar")
    ])
    kb.append([
        InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="userlar"),
        InlineKeyboardButton("💳 To'lovlar", callback_data="tolovlar_list")
    ])
    if is_admin(uid):
        kb.append([
            InlineKeyboardButton("📢 Majburiy a'zo", callback_data="majburiy_azo"),
            InlineKeyboardButton("🛡️ Staff qo'shish", callback_data="staff_qosh")
        ])
    kb.append([
        InlineKeyboardButton("📖 Qo'llanma", callback_data="qollanma_edit"),
        InlineKeyboardButton("💰 Reklama", callback_data="reklama_edit")
    ])
    kb.append([
        InlineKeyboardButton("💎 VIP narxi", callback_data="vip_narx_edit"),
        InlineKeyboardButton("👋 Xush kelibsiz", callback_data="xush_edit")
    ])
    kb.append([
        InlineKeyboardButton("💳 Karta raqamlar", callback_data="karta_edit"),
        InlineKeyboardButton("📊 Batafsil stat", callback_data="statistika")
    ])

    await query.edit_message_text(panel_text, reply_markup=InlineKeyboardMarkup(kb))

async def statistika(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    with db() as conn:
        a = conn.execute("SELECT COUNT(*) as c FROM animelar WHERE turi='anime'").fetchone()["c"]
        sh = conn.execute("SELECT COUNT(*) as c FROM animelar WHERE turi='shorts'").fetchone()["c"]
        se = conn.execute("SELECT COUNT(*) as c FROM seriyalar").fetchone()["c"]
        u = conn.execute("SELECT COUNT(*) as c FROM foydalanuvchilar").fetchone()["c"]
        v = conn.execute("SELECT COUNT(*) as c FROM foydalanuvchilar WHERE vip=1").fetchone()["c"]
        st = conn.execute("SELECT COUNT(*) as c FROM foydalanuvchilar WHERE staff=1").fetchone()["c"]
        top = conn.execute("SELECT nomi, korishlar FROM animelar ORDER BY korishlar DESC LIMIT 5").fetchall()
        bugun = conn.execute("SELECT COUNT(*) as c FROM foydalanuvchilar WHERE joined=date('now')").fetchone()["c"]
        hafta = conn.execute("SELECT COUNT(*) as c FROM foydalanuvchilar WHERE joined >= date('now', '-7 days')").fetchone()["c"]
        jami_kor = conn.execute("SELECT SUM(korishlar) as s FROM animelar").fetchone()["s"] or 0

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    top_t = "\n".join([f"{medals[i]} {r['nomi']} — {r['korishlar']} ta" for i, r in enumerate(top)])

    await query.edit_message_text(
        f"📊 Batafsil Statistika\n"
        f"{'━' * 25}\n\n"
        f"🎌 Animelar: {a} ta\n"
        f"🔴 Shorts: {sh} ta\n"
        f"🎬 Seriyalar: {se} ta\n"
        f"👁️ Jami ko'rishlar: {jami_kor} ta\n\n"
        f"👥 Foydalanuvchilar: {u} ta\n"
        f"🆕 Bugun: +{bugun} ta\n"
        f"📅 Hafta: +{hafta} ta\n"
        f"💎 VIP: {v} ta\n"
        f"🛡️ Staff: {st} ta\n\n"
        f"🏆 Top 5 anime:\n{top_t}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")]]))

async def tolovlar_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    with db() as conn:
        rows = conn.execute("SELECT * FROM tolovlar ORDER BY id DESC LIMIT 20").fetchall()
    if not rows:
        await query.edit_message_text(
            "💳 Hozircha to'lovlar yo'q.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")]]))
        return
    matn = "💳 So'nggi to'lovlar:\n\n"
    for r in rows:
        emoji = "✅" if r['holat'] == 'tasdiqlangan' else ("❌" if r['holat'] == 'rad' else "⏳")
        matn += f"{emoji} #{r['id']} | {r['user_id']} | {r['sana']}\n"
    await query.edit_message_text(matn, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")]]))

async def admin_anime_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    with db() as conn:
        rows = conn.execute("SELECT * FROM animelar ORDER BY id DESC").fetchall()
    if not rows:
        await query.edit_message_text(
            "😕 Anime yo'q.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")]]))
        return
    kb = []
    for r in rows:
        label = f"{'🔒' if r['vip'] else '✅'} {r['nomi']} ({r['turi']})"
        kb.append([InlineKeyboardButton(label, callback_data=f"del_{r['id']}")])
    kb.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")])
    await query.edit_message_text(
        f"📋 Animelar ({len(rows)} ta)\n⚠️ O'chirish uchun bosing:",
        reply_markup=InlineKeyboardMarkup(kb))

# ===== ANIME QO'SHISH =====
async def anime_qosh_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_staff(query.from_user.id): return
    context.user_data["ya"] = {"turi": "anime"}
    await query.edit_message_text("1️⃣ Anime nomini yozing:")
    return ANIME_NOMI

async def shorts_qosh_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_staff(query.from_user.id): return
    context.user_data["ya"] = {"turi": "shorts"}
    await query.edit_message_text("1️⃣ Shorts nomini yozing:")
    return ANIME_NOMI

async def a_nomi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ya"]["nomi"] = update.message.text
    await update.message.reply_text("2️⃣ Janrini yozing:\n(masalan: Action, Romance, Comedy...)")
    return ANIME_JANR

async def a_janr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ya"]["janr"] = update.message.text
    await update.message.reply_text(
        "3️⃣ Kodni yozing (masalan: 001):",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏭️ O'tkazib yuborish", callback_data="skip_kod")]]))
    return ANIME_KOD

async def a_kod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ya"]["kod"] = update.message.text
    await update.message.reply_text(
        "4️⃣ Rasm yuboring:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏭️ O'tkazib yuborish", callback_data="skip_rasm")]]))
    return ANIME_RASM

async def skip_kod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "4️⃣ Rasm yuboring:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏭️ O'tkazib yuborish", callback_data="skip_rasm")]]))
    return ANIME_RASM

async def a_rasm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data["ya"]["rasm"] = update.message.photo[-1].file_id
    await update.message.reply_text(
        "5️⃣ Video yuboring:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏭️ O'tkazib yuborish", callback_data="skip_video")]]))
    return ANIME_VIDEO_FILE

async def skip_rasm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "5️⃣ Video yuboring:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏭️ O'tkazib yuborish", callback_data="skip_video")]]))
    return ANIME_VIDEO_FILE

async def a_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.video:
        context.user_data["ya"]["video"] = update.message.video.file_id
    await update.message.reply_text(
        "6️⃣ VIP yoki Bepul?",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔒 VIP", callback_data="av_vip"),
            InlineKeyboardButton("✅ Bepul", callback_data="av_bepul")
        ]]))
    return ANIME_TURI

async def skip_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "6️⃣ VIP yoki Bepul?",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔒 VIP", callback_data="av_vip"),
            InlineKeyboardButton("✅ Bepul", callback_data="av_bepul")
        ]]))
    return ANIME_TURI

async def a_saqlash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    vip = 1 if query.data == "av_vip" else 0
    ya = context.user_data.get("ya", {})
    with db() as conn:
        conn.execute(
            "INSERT INTO animelar (nomi, janr, kod, rasm, video, vip, turi) VALUES (?,?,?,?,?,?,?)",
            (ya.get("nomi"), ya.get("janr"), ya.get("kod"), ya.get("rasm"), ya.get("video"), vip, ya.get("turi", "anime")))
        conn.commit()
    await query.edit_message_text(
        f"✅ '{ya.get('nomi')}' muvaffaqiyatli qo'shildi!\n\n"
        f"{'🔒 VIP' if vip else '✅ Bepul'} | {ya.get('turi', 'anime').capitalize()}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")]]))
    return ConversationHandler.END

# ===== SERIYA =====
async def seriya_qosh_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_staff(query.from_user.id): return
    with db() as conn:
        rows = conn.execute("SELECT id, nomi FROM animelar WHERE turi='anime' ORDER BY id DESC").fetchall()
    if not rows:
        await query.edit_message_text("⚠️ Avval anime qo'shing.")
        return
    kb = [[InlineKeyboardButton(r['nomi'], callback_data=f"sa_{r['id']}")] for r in rows]
    kb.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")])
    await query.edit_message_text("🎬 Qaysi animega seriya qo'shmoqchisiz?", reply_markup=InlineKeyboardMarkup(kb))

async def seriya_anime_sel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    aid = int(query.data.split("_")[1])
    context.user_data["seriya"] = {"anime_id": aid}
    await query.edit_message_text("1️⃣ Seriya nomini yozing (masalan: 1-qism):")
    return SERIYA_NOMI

async def seriya_nomi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["seriya"]["nomi"] = update.message.text
    await update.message.reply_text("2️⃣ Seriya videosini yuboring:")
    return SERIYA_VIDEO

async def seriya_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = context.user_data.get("seriya", {})
    vid = update.message.video.file_id if update.message.video else None
    with db() as conn:
        conn.execute("INSERT INTO seriyalar (anime_id, nomi, video) VALUES (?,?,?)",
                     (s.get("anime_id"), s.get("nomi"), vid))
        conn.commit()
    await update.message.reply_text(
        f"✅ '{s.get('nomi')}' seriyasi qo'shildi!",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")]]))
    return ConversationHandler.END

async def anime_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_staff(query.from_user.id): return
    aid = int(query.data.split("_")[1])
    with db() as conn:
        anime = conn.execute("SELECT nomi FROM animelar WHERE id=?", (aid,)).fetchone()
        conn.execute("DELETE FROM seriyalar WHERE anime_id=?", (aid,))
        conn.execute("DELETE FROM animelar WHERE id=?", (aid,))
        conn.commit()
    await query.edit_message_text(
        f"🗑️ '{anime['nomi']}' o'chirildi!",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")]]))

async def seriya_tahrir_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    with db() as conn:
        rows = conn.execute(
            "SELECT s.id, s.nomi, a.nomi as an FROM seriyalar s JOIN animelar a ON s.anime_id=a.id ORDER BY s.id DESC"
        ).fetchall()
    if not rows:
        await query.edit_message_text("😕 Seriya yo'q.")
        return
    kb = [[InlineKeyboardButton(f"🗑️ {r['an']} — {r['nomi']}", callback_data=f"sdel_{r['id']}")] for r in rows]
    kb.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")])
    await query.edit_message_text(
        "🎬 Seriyalar (o'chirish uchun bosing):",
        reply_markup=InlineKeyboardMarkup(kb))

async def seriya_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.split("_")[1])
    with db() as conn:
        s = conn.execute("SELECT nomi FROM seriyalar WHERE id=?", (sid,)).fetchone()
        conn.execute("DELETE FROM seriyalar WHERE id=?", (sid,))
        conn.commit()
    await query.edit_message_text(
        f"🗑️ '{s['nomi']}' seriyasi o'chirildi!",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")]]))

async def anime_tahrir_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    with db() as conn:
        rows = conn.execute("SELECT id, nomi, vip, turi FROM animelar ORDER BY id DESC").fetchall()
    if not rows:
        await query.edit_message_text("😕 Anime yo'q.")
        return
    kb = [[InlineKeyboardButton(f"✏️ {r['nomi']}", callback_data=f"aedit_{r['id']}")] for r in rows]
    kb.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")])
    await query.edit_message_text("✏️ Anime tanlang:", reply_markup=InlineKeyboardMarkup(kb))

async def anime_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    aid = int(query.data.split("_")[1])
    with db() as conn:
        a = conn.execute("SELECT * FROM animelar WHERE id=?", (aid,)).fetchone()
        se = conn.execute("SELECT COUNT(*) as c FROM seriyalar WHERE anime_id=?", (aid,)).fetchone()["c"]
    badge = "🔒 VIP" if a['vip'] else "✅ Bepul"
    kb = [
        [InlineKeyboardButton("🗑️ O'chirish", callback_data=f"del_{aid}")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="anime_tahrir_list")]
    ]
    await query.edit_message_text(
        f"🎌 {a['nomi']}\n\n"
        f"🏷️ Janr: {a['janr'] or '—'}\n"
        f"🔑 Kod: {a['kod'] or '—'}\n"
        f"👁️ Ko'rishlar: {a['korishlar']}\n"
        f"💎 Turi: {badge}\n"
        f"🎬 Seriyalar: {se} ta",
        reply_markup=InlineKeyboardMarkup(kb))

# ===== POST =====
async def post_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_staff(query.from_user.id): return
    await query.edit_message_text(
        "📢 Post matni yozing yoki rasm/video bilan yuboring:\n\n"
        "⚠️ Bu barcha foydalanuvchilarga yuboriladi!")
    return POST_MATN

async def post_yuborish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db() as conn:
        users = conn.execute("SELECT user_id FROM foydalanuvchilar").fetchall()
    yuborildi = 0
    xato = 0
    for u in users:
        try:
            await update.message.copy_to(chat_id=u["user_id"])
            yuborildi += 1
        except:
            xato += 1
    await update.message.reply_text(
        f"📢 Post yuborildi!\n\n"
        f"✅ Muvaffaqiyatli: {yuborildi} ta\n"
        f"❌ Xato: {xato} ta\n"
        f"📊 Jami: {len(users)} ta",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")]]))
    return ConversationHandler.END

# ===== ALOHIDA =====
async def alohida_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    await query.edit_message_text("✉️ Foydalanuvchi ID sini yozing:")
    return ALOHIDA_ID

async def alohida_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["alohida_id"] = int(update.message.text)
        await update.message.reply_text("✉️ Xabar yozing:")
        return ALOHIDA_MATN
    except:
        await update.message.reply_text("❌ Noto'g'ri ID!")
        return ConversationHandler.END

async def alohida_matn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = context.user_data.get("alohida_id")
    try:
        await update.message.copy_to(chat_id=tid)
        await update.message.reply_text(f"✅ Xabar {tid} ga yuborildi!")
    except:
        await update.message.reply_text("❌ Yuborib bo'lmadi. ID noto'g'ri bo'lishi mumkin.")
    return ConversationHandler.END

# ===== MAJBURIY =====
async def majburiy_azo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    with db() as conn:
        kanallar = conn.execute("SELECT * FROM kanallar").fetchall()
    matn = "📢 Majburiy kanallar:\n\n"
    if kanallar:
        for k in kanallar:
            matn += f"• {k['nomi']} ({k['kanal_id']})\n"
    else:
        matn += "Hozircha kanal yo'q.\n"
    matn += "\n@kanal_username yozing qo'shish uchun:"
    await query.edit_message_text(
        matn,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")]]))
    return MAJBURIY_KANAL

async def majburiy_qosh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kanal = update.message.text.strip()
    if not kanal.startswith("@"):
        await update.message.reply_text("⚠️ @ bilan boshlang! (masalan: @kanal_nomi)")
        return MAJBURIY_KANAL
    with db() as conn:
        conn.execute("INSERT OR IGNORE INTO kanallar (kanal_id, nomi) VALUES (?,?)", (kanal, kanal))
        conn.commit()
    await update.message.reply_text(
        f"✅ {kanal} qo'shildi!",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")]]))
    return ConversationHandler.END

# ===== STAFF =====
async def staff_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    with db() as conn:
        stafflar = conn.execute("SELECT * FROM foydalanuvchilar WHERE staff=1").fetchall()
    if stafflar:
        matn = "🛡️ Stafflar:\n\n"
        for s in stafflar:
            matn += f"• {s['ism']} | {s['user_id']}\n"
    else:
        matn = "🛡️ Hozircha staff yo'q.\n"
    matn += "\nYangi staff ID sini yozing:"
    await query.edit_message_text(
        matn,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")]]))
    return STAFF_ID

async def staff_qosh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sid = int(update.message.text)
        with db() as conn:
            conn.execute("INSERT OR IGNORE INTO foydalanuvchilar (user_id, ism) VALUES (?,'Staff')", (sid,))
            conn.execute("UPDATE foydalanuvchilar SET staff=1 WHERE user_id=?", (sid,))
            conn.commit()
        await update.message.reply_text(
            f"✅ {sid} ID li foydalanuvchi staff qilindi!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")]]))
    except:
        await update.message.reply_text("❌ Noto'g'ri ID!")
    return ConversationHandler.END

# ===== SOZLAMALAR =====
async def qollanma_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"📖 Hozirgi qo'llanma:\n\n{get_sozlama('qollanma')}\n\n"
        f"{'━' * 20}\n\nYangi matnni yozing:")
    return QOLLANMA_EDIT

async def qollanma_saqlash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db() as conn:
        conn.execute("UPDATE sozlamalar SET qiymat=? WHERE kalit='qollanma'", (update.message.text,))
        conn.commit()
    await update.message.reply_text(
        "✅ Qo'llanma yangilandi!",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")]]))
    return ConversationHandler.END

async def reklama_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"💰 Hozirgi reklama matni:\n\n{get_sozlama('reklama')}\n\n"
        f"{'━' * 20}\n\nYangi matnni yozing:")
    return REKLAMA_EDIT

async def reklama_saqlash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db() as conn:
        conn.execute("UPDATE sozlamalar SET qiymat=? WHERE kalit='reklama'", (update.message.text,))
        conn.commit()
    await update.message.reply_text(
        "✅ Reklama matni yangilandi!",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")]]))
    return ConversationHandler.END

async def vip_narx_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"💎 Hozirgi VIP narxi: {get_sozlama('vip_narx')} so'm\n"
        f"⏳ Muddati: {get_sozlama('vip_mud')} kun\n\n"
        f"Yangi narxni yozing (faqat son, so'mda):")
    return VIP_NARX_EDIT

async def vip_narx_saqlash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        narx = int(update.message.text)
        with db() as conn:
            conn.execute("UPDATE sozlamalar SET qiymat=? WHERE kalit='vip_narx'", (str(narx),))
            conn.commit()
        await update.message.reply_text(
            f"✅ VIP narxi {narx:,} so'm ga o'zgartirildi!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")]]))
    except:
        await update.message.reply_text("❌ Faqat son kiriting!")
    return ConversationHandler.END

async def xush_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"👋 Hozirgi xush kelibsiz matni:\n\n{get_sozlama('xush_kelibsiz')}\n\n"
        f"{'━' * 20}\n\nYangi matnni yozing:")
    return QOLLANMA_EDIT + 100

async def xush_saqlash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db() as conn:
        conn.execute("UPDATE sozlamalar SET qiymat=? WHERE kalit='xush_kelibsiz'", (update.message.text,))
        conn.commit()
    await update.message.reply_text(
        "✅ Xush kelibsiz matni yangilandi!",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")]]))
    return ConversationHandler.END

# ===== KARTA EDIT =====
KARTA_EDIT = 110

async def karta_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    payme = get_sozlama("payme_karta")
    click = get_sozlama("click_karta")
    await query.edit_message_text(
        f"💳 Hozirgi karta raqamlar:\n\n"
        f"• Payme: {payme}\n"
        f"• Click: {click}\n\n"
        f"Yangi Payme karta raqamini yozing:")
    context.user_data["karta_bosqich"] = "payme"
    return KARTA_EDIT

async def karta_saqlash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bosqich = context.user_data.get("karta_bosqich")
    if bosqich == "payme":
        with db() as conn:
            conn.execute("UPDATE sozlamalar SET qiymat=? WHERE kalit='payme_karta'", (update.message.text,))
            conn.commit()
        context.user_data["karta_bosqich"] = "click"
        await update.message.reply_text("✅ Payme saqlandi!\n\nEndi Click karta raqamini yozing:")
        return KARTA_EDIT
    elif bosqich == "click":
        with db() as conn:
            conn.execute("UPDATE sozlamalar SET qiymat=? WHERE kalit='click_karta'", (update.message.text,))
            conn.commit()
        await update.message.reply_text(
            "✅ Barcha karta raqamlar yangilandi!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")]]))
        return ConversationHandler.END

async def userlar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    with db() as conn:
        rows = conn.execute("SELECT * FROM foydalanuvchilar ORDER BY vip DESC, id DESC LIMIT 30").fetchall()
        jami = conn.execute("SELECT COUNT(*) as c FROM foydalanuvchilar").fetchone()["c"]
    matn = f"👥 Foydalanuvchilar (jami: {jami} ta)\n\n"
    for r in rows:
        badge = "💎" if r['vip'] else ("🛡️" if r['staff'] else "👤")
        matn += f"{badge} {r['ism']} | {r['user_id']}\n"
    await query.edit_message_text(
        matn,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")]]))

def main():
    db_setup()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    izlash_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(izlash_nom_start, "^izlash_nom$"),
            CallbackQueryHandler(izlash_kod_start, "^izlash_kod$")
        ],
        states={IZLASH_HOLAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, izlash_natija)]},
        fallbacks=[CommandHandler("start", start)])

    anime_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(anime_qosh_start, "^anime_qosh$"),
            CallbackQueryHandler(shorts_qosh_start, "^shorts_qosh$")
        ],
        states={
            ANIME_NOMI: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_nomi)],
            ANIME_JANR: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_janr)],
            ANIME_KOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_kod), CallbackQueryHandler(skip_kod, "^skip_kod$")],
            ANIME_RASM: [MessageHandler(filters.PHOTO, a_rasm), CallbackQueryHandler(skip_rasm, "^skip_rasm$")],
            ANIME_VIDEO_FILE: [MessageHandler(filters.VIDEO, a_video), CallbackQueryHandler(skip_video, "^skip_video$")],
            ANIME_TURI: [CallbackQueryHandler(a_saqlash, "^av_(vip|bepul)$")],
        },
        fallbacks=[CommandHandler("start", start)])

    seriya_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(seriya_qosh_start, "^seriya_qosh$")],
        states={
            SERIYA_ANIME_ID: [CallbackQueryHandler(seriya_anime_sel, "^sa_\\d+$")],
            SERIYA_NOMI: [MessageHandler(filters.TEXT & ~filters.COMMAND, seriya_nomi)],
            SERIYA_VIDEO: [MessageHandler(filters.VIDEO, seriya_video)],
        },
        fallbacks=[CommandHandler("start", start)])

    tolov_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(chek_yuborish, "^chek_yuborish$")],
        states={TOLOV_CHECK: [MessageHandler(filters.PHOTO | filters.Document.ALL, chek_qabul)]},
        fallbacks=[CommandHandler("start", start)])

    post_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(post_start, "^post_tayyorla$")],
        states={POST_MATN: [MessageHandler(filters.ALL & ~filters.COMMAND, post_yuborish)]},
        fallbacks=[CommandHandler("start", start)])

    alohida_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(alohida_start, "^alohida_xabar$")],
        states={
            ALOHIDA_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, alohida_id)],
            ALOHIDA_MATN: [MessageHandler(filters.ALL & ~filters.COMMAND, alohida_matn)]
        },
        fallbacks=[CommandHandler("start", start)])

    majburiy_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(majburiy_azo, "^majburiy_azo$")],
        states={MAJBURIY_KANAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, majburiy_qosh)]},
        fallbacks=[CommandHandler("start", start)])

    staff_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(staff_start, "^staff_qosh$")],
        states={STAFF_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, staff_qosh)]},
        fallbacks=[CommandHandler("start", start)])

    qollanma_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(qollanma_edit_start, "^qollanma_edit$")],
        states={QOLLANMA_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, qollanma_saqlash)]},
        fallbacks=[CommandHandler("start", start)])

    reklama_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(reklama_edit_start, "^reklama_edit$")],
        states={REKLAMA_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, reklama_saqlash)]},
        fallbacks=[CommandHandler("start", start)])

    vip_narx_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(vip_narx_edit_start, "^vip_narx_edit$")],
        states={VIP_NARX_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, vip_narx_saqlash)]},
        fallbacks=[CommandHandler("start", start)])

    xush_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(xush_edit_start, "^xush_edit$")],
        states={QOLLANMA_EDIT + 100: [MessageHandler(filters.TEXT & ~filters.COMMAND, xush_saqlash)]},
        fallbacks=[CommandHandler("start", start)])

    karta_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(karta_edit_start, "^karta_edit$")],
        states={KARTA_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, karta_saqlash)]},
        fallbacks=[CommandHandler("start", start)])

    for conv in [
        izlash_conv, anime_conv, seriya_conv, tolov_conv, post_conv,
        alohida_conv, majburiy_conv, staff_conv, qollanma_conv,
        reklama_conv, vip_narx_conv, xush_conv, karta_conv
    ]:
        app.add_handler(conv)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CallbackQueryHandler(start_cb, "^start$"))
    app.add_handler(CallbackQueryHandler(obuna_tekshir, "^obuna_tekshir$"))
    app.add_handler(CallbackQueryHandler(barcha_anime, "^barcha_anime$"))
    app.add_handler(CallbackQueryHandler(top_anime, "^top_anime$"))
    app.add_handler(CallbackQueryHandler(yangi_anime, "^yangi_anime$"))
    app.add_handler(CallbackQueryHandler(anime_detail, "^anime_\\d+$"))
    app.add_handler(CallbackQueryHandler(seriya_detail, "^seriya_\\d+$"))
    app.add_handler(CallbackQueryHandler(seriya_delete, "^sdel_\\d+$"))
    app.add_handler(CallbackQueryHandler(vip_olish_cb, "^vip_olish_cb$"))
    app.add_handler(CallbackQueryHandler(vip_tolov, "^vip_tolov$"))
    app.add_handler(CallbackQueryHandler(vip_tasdiq, "^vip_tasdiq_\\d+$"))
    app.add_handler(CallbackQueryHandler(vip_rad, "^vip_rad_\\d+$"))
    app.add_handler(CallbackQueryHandler(admin_panel_cb, "^admin_panel$"))
    app.add_handler(CallbackQueryHandler(admin_anime_list, "^admin_anime_list$"))
    app.add_handler(CallbackQueryHandler(anime_delete, "^del_\\d+$"))
    app.add_handler(CallbackQueryHandler(anime_tahrir_list, "^anime_tahrir_list$"))
    app.add_handler(CallbackQueryHandler(anime_edit, "^aedit_\\d+$"))
    app.add_handler(CallbackQueryHandler(seriya_tahrir_list, "^seriya_tahrir_list$"))
    app.add_handler(CallbackQueryHandler(statistika, "^statistika$"))
    app.add_handler(CallbackQueryHandler(userlar, "^userlar$"))
    app.add_handler(CallbackQueryHandler(tolovlar_list, "^tolovlar_list$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("🚀 Bot ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()
