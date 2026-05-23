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
        conn.execute("INSERT OR IGNORE INTO sozlamalar VALUES ('qollanma', 'Botdan foydalanish qollanmasi')")
        conn.execute("INSERT OR IGNORE INTO sozlamalar VALUES ('reklama', 'Reklama uchun: @admin')")
        conn.execute("INSERT OR IGNORE INTO sozlamalar VALUES ('vip_narx', '10000')")
        conn.execute("INSERT OR IGNORE INTO sozlamalar VALUES ('vip_mud', '30')")
        conn.execute("INSERT OR IGNORE INTO sozlamalar VALUES ('xush_kelibsiz', 'Anime Botga xush kelibsiz!')")
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

def asosiy_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🔍 Anime izlash")],
        [KeyboardButton("🔴 Shorts"), KeyboardButton("📚 Qollanma")],
        [KeyboardButton("💎 VIP"), KeyboardButton("👥 Referral")],
        [KeyboardButton("💰 Reklama")]
    ], resize_keyboard=True)

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
        kb = [[InlineKeyboardButton(f"Obuna: {k['nomi']}", url=f"https://t.me/{k['kanal_id'].replace('@','')}")] for k in kanallar]
        kb.append([InlineKeyboardButton("Tekshirish ✅", callback_data="obuna_tekshir")])
        await update.message.reply_text("Botdan foydalanish uchun obuna boling:", reply_markup=InlineKeyboardMarkup(kb))
        return

    vip = is_vip(user.id)
    xush = get_sozlama("xush_kelibsiz")
    kb = [
        [InlineKeyboardButton("🔍 Nom boyicha", callback_data="izlash_nom"), InlineKeyboardButton("🔑 Kod boyicha", callback_data="izlash_kod")],
        [InlineKeyboardButton("📋 Barcha animelar", callback_data="barcha_anime")],
        [InlineKeyboardButton("🔥 Top animelar", callback_data="top_anime"), InlineKeyboardButton("🆕 Yangi qoshilgan", callback_data="yangi_anime")],
    ]
    await update.message.reply_text(
        f"{xush}\n\n👤 {user.first_name}\n{'💎 VIP' if vip else '👤 Oddiy foydalanuvchi'}\n\nAnime izlash:",
        reply_markup=InlineKeyboardMarkup(kb))
    await update.message.reply_text("Pastki menyu:", reply_markup=asosiy_menu())

async def obuna_tekshir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    if await majburiy_tekshir(user.id, context):
        vip = is_vip(user.id)
        kb = [
            [InlineKeyboardButton("🔍 Nom boyicha", callback_data="izlash_nom"), InlineKeyboardButton("🔑 Kod boyicha", callback_data="izlash_kod")],
            [InlineKeyboardButton("📋 Barcha animelar", callback_data="barcha_anime")],
            [InlineKeyboardButton("🔥 Top animelar", callback_data="top_anime")],
        ]
        await query.edit_message_text(
            f"Xush kelibsiz, {user.first_name}!\n{'💎 VIP' if vip else '👤 Oddiy'}",
            reply_markup=InlineKeyboardMarkup(kb))
    else:
        await query.answer("Hali obuna bolmadingiz!", show_alert=True)

async def start_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    vip = is_vip(user.id)
    kb = [
        [InlineKeyboardButton("🔍 Nom boyicha", callback_data="izlash_nom"), InlineKeyboardButton("🔑 Kod boyicha", callback_data="izlash_kod")],
        [InlineKeyboardButton("📋 Barcha animelar", callback_data="barcha_anime")],
        [InlineKeyboardButton("🔥 Top animelar", callback_data="top_anime"), InlineKeyboardButton("🆕 Yangi", callback_data="yangi_anime")],
    ]
    await query.edit_message_text(
        f"Bosh sahifa\n\n👤 {user.first_name} | {'💎 VIP' if vip else 'Oddiy'}",
        reply_markup=InlineKeyboardMarkup(kb))

# ===== IZLASH =====
async def izlash_nom_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["izlash_turi"] = "nom"
    await query.edit_message_text("🔍 Anime nomini yozing:")
    return IZLASH_HOLAT

async def izlash_kod_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["izlash_turi"] = "kod"
    await query.edit_message_text("🔑 Anime kodini yozing:")
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
        await update.message.reply_text("😕 Natija topilmadi!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Orqaga", callback_data="start")]]))
        return ConversationHandler.END
    kb = []
    for r in rows:
        kb.append([InlineKeyboardButton(f"{'[VIP] ' if r['vip'] else ''}{r['nomi']} | {r['janr'] or '-'}", callback_data=f"anime_{r['id']}")])
    kb.append([InlineKeyboardButton("Orqaga", callback_data="start")])
    await update.message.reply_text(f"Natijalar: {len(rows)} ta", reply_markup=InlineKeyboardMarkup(kb))
    return ConversationHandler.END

# ===== KLAVIATURA =====
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = update.message.text
    if t == "🔍 Anime izlash":
        kb = [
            [InlineKeyboardButton("Nom boyicha", callback_data="izlash_nom")],
            [InlineKeyboardButton("Kod boyicha", callback_data="izlash_kod")],
            [InlineKeyboardButton("Barcha animelar", callback_data="barcha_anime")],
            [InlineKeyboardButton("Top animelar", callback_data="top_anime")],
        ]
        await update.message.reply_text("Quyidagilardan birini tanlang:", reply_markup=InlineKeyboardMarkup(kb))
    elif t == "🔴 Shorts":
        uid = update.effective_user.id
        vip = is_vip(uid)
        with db() as conn:
            rows = conn.execute("SELECT * FROM animelar WHERE turi='shorts'" + ("" if vip or is_admin(uid) else " AND vip=0") + " ORDER BY id DESC").fetchall()
        if not rows:
            await update.message.reply_text("Hozircha shorts yoq.")
            return
        kb = [[InlineKeyboardButton(r['nomi'], callback_data=f"anime_{r['id']}")] for r in rows]
        await update.message.reply_text("🔴 Shorts:", reply_markup=InlineKeyboardMarkup(kb))
    elif t == "📚 Qollanma":
        await update.message.reply_text(f"📚 Qollanma:\n\n{get_sozlama('qollanma')}")
    elif t == "💎 VIP":
        uid = update.effective_user.id
        if is_vip(uid):
            await update.message.reply_text("💎 Siz allaqachon VIP foydalanuvchisiz!")
            return
        narx = get_sozlama("vip_narx")
        mud = get_sozlama("vip_mud")
        kb = [
            [InlineKeyboardButton("💳 Tolov qilish", callback_data="vip_tolov")],
            [InlineKeyboardButton("📸 Chek yuborish", callback_data="chek_yuborish")],
        ]
        await update.message.reply_text(
            f"💎 VIP obuna\n\nNarxi: {narx} som\nMuddati: {mud} kun\n\nImkoniyatlar:\n- Barcha VIP animelarga kirish\n- Seriyalarga kirish\n- Tezkor yangilanishlar\n\nTolov usulini tanlang:",
            reply_markup=InlineKeyboardMarkup(kb))
    elif t == "👥 Referral":
        uid = update.effective_user.id
        with db() as conn:
            r = conn.execute("SELECT referrallar FROM foydalanuvchilar WHERE user_id=?", (uid,)).fetchone()
        ref_soni = r["referrallar"] if r else 0
        link = f"https://t.me/bot?start={uid}"
        await update.message.reply_text(
            f"👥 Referral tizimi\n\nSizning havolangiz:\n{link}\n\nJalb qilganlar: {ref_soni} ta\n\nHar 5 ta referral uchun 1 kun VIP!")
    elif t == "💰 Reklama":
        await update.message.reply_text(f"💰 Reklama va Homiylik:\n\n{get_sozlama('reklama')}")

# ===== ANIMELAR =====
async def barcha_anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    vip = is_vip(uid)
    with db() as conn:
        rows = conn.execute("SELECT * FROM animelar WHERE turi='anime'" + ("" if vip or is_admin(uid) else " AND vip=0") + " ORDER BY id DESC").fetchall()
    if not rows:
        await query.edit_message_text("Hozircha anime yoq.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Orqaga", callback_data="start")]]))
        return
    kb = [[InlineKeyboardButton(f"{'[VIP] ' if r['vip'] else ''}{r['nomi']} | {r['janr'] or '-'}", callback_data=f"anime_{r['id']}")] for r in rows]
    kb.append([InlineKeyboardButton("Orqaga", callback_data="start")])
    await query.edit_message_text("📋 Barcha animelar:", reply_markup=InlineKeyboardMarkup(kb))

async def top_anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    vip = is_vip(uid)
    with db() as conn:
        rows = conn.execute("SELECT * FROM animelar WHERE turi='anime'" + ("" if vip or is_admin(uid) else " AND vip=0") + " ORDER BY korishlar DESC LIMIT 10").fetchall()
    if not rows:
        await query.edit_message_text("Hozircha anime yoq.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Orqaga", callback_data="start")]]))
        return
    kb = [[InlineKeyboardButton(f"{i+1}. {r['nomi']} | {r['korishlar']} ta", callback_data=f"anime_{r['id']}")] for i, r in enumerate(rows)]
    kb.append([InlineKeyboardButton("Orqaga", callback_data="start")])
    await query.edit_message_text("🔥 Top 10 animelar:", reply_markup=InlineKeyboardMarkup(kb))

async def yangi_anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    vip = is_vip(uid)
    with db() as conn:
        rows = conn.execute("SELECT * FROM animelar WHERE turi='anime'" + ("" if vip or is_admin(uid) else " AND vip=0") + " ORDER BY id DESC LIMIT 10").fetchall()
    if not rows:
        await query.edit_message_text("Hozircha anime yoq.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Orqaga", callback_data="start")]]))
        return
    kb = [[InlineKeyboardButton(f"🆕 {r['nomi']}", callback_data=f"anime_{r['id']}")] for r in rows]
    kb.append([InlineKeyboardButton("Orqaga", callback_data="start")])
    await query.edit_message_text("🆕 Yangi qoshilgan animelar:", reply_markup=InlineKeyboardMarkup(kb))

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
        await query.edit_message_text("Anime topilmadi.")
        return
    if anime["vip"] and not is_vip(uid) and not is_admin(uid):
        kb = [
            [InlineKeyboardButton("💎 VIP olish", callback_data="vip_olish_cb")],
            [InlineKeyboardButton("Orqaga", callback_data="barcha_anime")]
        ]
        await query.edit_message_text("Bu anime faqat VIP uchun!\n\nVIP oling va barcha animelarga kiring!", reply_markup=InlineKeyboardMarkup(kb))
        return

    vb = "[VIP] " if anime["vip"] else ""
    matn = f"{vb}{anime['nomi']}\n\nJanr: {anime['janr'] or '-'}\nKod: {anime['kod'] or '-'}\nKorishlar: {anime['korishlar']}"
    if anime["tavsif"]:
        matn += f"\n\nTavsif: {anime['tavsif']}"

    kb = []
    if seriyalar:
        matn += f"\n\nSeriyalar: {len(seriyalar)} ta"
        for s in seriyalar:
            kb.append([InlineKeyboardButton(s['nomi'], callback_data=f"seriya_{s['id']}")])
    if is_staff(uid):
        kb.append([InlineKeyboardButton("Ochirish", callback_data=f"del_{anime_id}")])
    kb.append([InlineKeyboardButton("Orqaga", callback_data="barcha_anime")])

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
        await query.edit_message_text("Seriya topilmadi.")
        return
    kb = [[InlineKeyboardButton("Orqaga", callback_data=f"anime_{s['anime_id']}")]]
    if s["video"]:
        await query.message.reply_video(video=s["video"], caption=s["nomi"], reply_markup=InlineKeyboardMarkup(kb))
        await query.delete_message()
    else:
        await query.edit_message_text(s["nomi"], reply_markup=InlineKeyboardMarkup(kb))

# ===== VIP =====
async def vip_olish_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    if is_vip(uid):
        await query.edit_message_text("💎 Siz allaqachon VIP!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Orqaga", callback_data="start")]]))
        return
    narx = get_sozlama("vip_narx")
    mud = get_sozlama("vip_mud")
    kb = [
        [InlineKeyboardButton("💳 Tolov qilish", callback_data="vip_tolov")],
        [InlineKeyboardButton("📸 Chek yuborish", callback_data="chek_yuborish")],
        [InlineKeyboardButton("Orqaga", callback_data="start")]
    ]
    await query.edit_message_text(
        f"💎 VIP obuna\n\nNarxi: {narx} som\nMuddati: {mud} kun\n\nTolov usulini tanlang:",
        reply_markup=InlineKeyboardMarkup(kb))

async def vip_tolov(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    narx = get_sozlama("vip_narx")
    kb = [
        [InlineKeyboardButton("📸 Chek yuborish", callback_data="chek_yuborish")],
        [InlineKeyboardButton("Orqaga", callback_data="start")]
    ]
    await query.edit_message_text(
        f"💳 Tolov\n\nNarxi: {narx} som\n\nTolov rekvizitlari:\n- Payme: 8600XXXXXXXXXXXXXXXX\n- Click: 8600XXXXXXXXXXXXXXXX\n\nTolov qilib chek rasmini yuboring:",
        reply_markup=InlineKeyboardMarkup(kb))

async def chek_yuborish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📸 Tolov cheki rasmini yuboring:")
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
        await update.message.reply_text("Rasm yuboring!")
        return TOLOV_CHECK

    with db() as conn:
        conn.execute("INSERT INTO tolovlar (user_id, chek, sana) VALUES (?,?,?)",
            (uid, chek_id, datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.commit()
        tolov_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]

    for admin_id in ADMIN_IDS:
        try:
            kb = [[
                InlineKeyboardButton("Tasdiqlash", callback_data=f"vip_tasdiq_{uid}"),
                InlineKeyboardButton("Rad etish", callback_data=f"vip_rad_{uid}")
            ]]
            await context.bot.send_photo(
                chat_id=admin_id, photo=chek_id,
                caption=f"💳 VIP Tolov #{tolov_id}\n\nFoydalanuvchi: {user.first_name}\nID: {uid}\n@{user.username or 'yoq'}",
                reply_markup=InlineKeyboardMarkup(kb))
        except: pass

    await update.message.reply_text("Chek qabul qilindi! Admin tekshirgandan keyin VIP beriladi.")
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
        await context.bot.send_message(tid, "Tabriklaymiz! Siz endi VIP foydalanuvchisiz! 💎\n\n/start bosing!")
    except: pass
    await query.edit_message_caption(caption=query.message.caption + "\n\n TASDIQLANDI")

async def vip_rad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    tid = int(query.data.split("_")[2])
    try:
        await context.bot.send_message(tid, "Tolovingiz rad etildi. Admin bilan boglanin.")
    except: pass
    await query.edit_message_caption(caption=query.message.caption + "\n\n RAD ETILDI")

# ===== ADMIN PANEL =====
async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_staff(update.effective_user.id):
        await update.message.reply_text("Ruxsat yoq!")
        return
    await _admin_panel_msg(update.message)

async def _admin_panel_msg(msg):
    with db() as conn:
        a = conn.execute("SELECT COUNT(*) as c FROM animelar").fetchone()["c"]
        u = conn.execute("SELECT COUNT(*) as c FROM foydalanuvchilar").fetchone()["c"]
        v = conn.execute("SELECT COUNT(*) as c FROM foydalanuvchilar WHERE vip=1").fetchone()["c"]
        s = conn.execute("SELECT COUNT(*) as c FROM foydalanuvchilar WHERE vip_so_rov=1").fetchone()["c"]
        t = conn.execute("SELECT COUNT(*) as c FROM tolovlar WHERE holat='kutilmoqda'").fetchone()["c"]
    kb = [
        [InlineKeyboardButton("NEW Anime qoshish", callback_data="anime_qosh"), InlineKeyboardButton("Animelar", callback_data="admin_anime_list")],
        [InlineKeyboardButton("Seriya qoshish", callback_data="seriya_qosh")],
        [InlineKeyboardButton("Anime tahrirlash", callback_data="anime_tahrir_list"), InlineKeyboardButton("Seriya tahrirlash", callback_data="seriya_tahrir_list")],
        [InlineKeyboardButton("Post yuborish", callback_data="post_tayyorla"), InlineKeyboardButton("Alohida xabar", callback_data="alohida_xabar")],
        [InlineKeyboardButton("Statistika", callback_data="statistika"), InlineKeyboardButton("Foydalanuvchilar", callback_data="userlar")],
        [InlineKeyboardButton("Majburiy azo", callback_data="majburiy_azo"), InlineKeyboardButton("Staff qoshish", callback_data="staff_qosh")],
        [InlineKeyboardButton("Qollanma", callback_data="qollanma_edit"), InlineKeyboardButton("Reklama", callback_data="reklama_edit")],
        [InlineKeyboardButton("VIP narxi", callback_data="vip_narx_edit"), InlineKeyboardButton("Xush kelibsiz", callback_data="xush_edit")],
        [InlineKeyboardButton("Tolovlar", callback_data="tolovlar_list")],
    ]
    await msg.reply_text(
        f"Admin Panel\n\nAnimelar: {a}\nFoydalanuvchilar: {u}\nVIP: {v}\nVIP sorovlar: {s}\nKutilayotgan tolovlar: {t}",
        reply_markup=InlineKeyboardMarkup(kb))

async def admin_panel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_staff(query.from_user.id): return
    with db() as conn:
        a = conn.execute("SELECT COUNT(*) as c FROM animelar").fetchone()["c"]
        u = conn.execute("SELECT COUNT(*) as c FROM foydalanuvchilar").fetchone()["c"]
        v = conn.execute("SELECT COUNT(*) as c FROM foydalanuvchilar WHERE vip=1").fetchone()["c"]
        s = conn.execute("SELECT COUNT(*) as c FROM foydalanuvchilar WHERE vip_so_rov=1").fetchone()["c"]
        t = conn.execute("SELECT COUNT(*) as c FROM tolovlar WHERE holat='kutilmoqda'").fetchone()["c"]
    kb = [
        [InlineKeyboardButton("NEW Anime qoshish", callback_data="anime_qosh"), InlineKeyboardButton("Animelar", callback_data="admin_anime_list")],
        [InlineKeyboardButton("Seriya qoshish", callback_data="seriya_qosh")],
        [InlineKeyboardButton("Anime tahrirlash", callback_data="anime_tahrir_list"), InlineKeyboardButton("Seriya tahrirlash", callback_data="seriya_tahrir_list")],
        [InlineKeyboardButton("Post yuborish", callback_data="post_tayyorla"), InlineKeyboardButton("Alohida xabar", callback_data="alohida_xabar")],
        [InlineKeyboardButton("Statistika", callback_data="statistika"), InlineKeyboardButton("Foydalanuvchilar", callback_data="userlar")],
        [InlineKeyboardButton("Majburiy azo", callback_data="majburiy_azo"), InlineKeyboardButton("Staff qoshish", callback_data="staff_qosh")],
        [InlineKeyboardButton("Qollanma", callback_data="qollanma_edit"), InlineKeyboardButton("Reklama", callback_data="reklama_edit")],
        [InlineKeyboardButton("VIP narxi", callback_data="vip_narx_edit"), InlineKeyboardButton("Xush kelibsiz", callback_data="xush_edit")],
        [InlineKeyboardButton("Tolovlar", callback_data="tolovlar_list")],
    ]
    await query.edit_message_text(
        f"Admin Panel\n\nAnimelar: {a}\nFoydalanuvchilar: {u}\nVIP: {v}\nVIP sorovlar: {s}\nKutilayotgan tolovlar: {t}",
        reply_markup=InlineKeyboardMarkup(kb))

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
    top_t = "\n".join([f"{i+1}. {r['nomi']} - {r['korishlar']} ta" for i, r in enumerate(top)])
    await query.edit_message_text(
        f"Statistika\n\nAnimelar: {a}\nShorts: {sh}\nSeriyalar: {se}\nFoydalanuvchilar: {u}\nBugun qoshildi: {bugun}\nVIP: {v}\nStaff: {st}\n\nTop 5:\n{top_t}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Orqaga", callback_data="admin_panel")]]))

async def tolovlar_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    with db() as conn:
        rows = conn.execute("SELECT * FROM tolovlar ORDER BY id DESC LIMIT 20").fetchall()
    if not rows:
        await query.edit_message_text("Tolovlar yoq.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Orqaga", callback_data="admin_panel")]]))
        return
    matn = "Tolovlar:\n\n"
    for r in rows:
        matn += f"#{r['id']} | User: {r['user_id']} | {r['holat']} | {r['sana']}\n"
    await query.edit_message_text(matn, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Orqaga", callback_data="admin_panel")]]))

async def admin_anime_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    with db() as conn:
        rows = conn.execute("SELECT * FROM animelar ORDER BY id DESC").fetchall()
    if not rows:
        await query.edit_message_text("Anime yoq.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Orqaga", callback_data="admin_panel")]]))
        return
    kb = [[InlineKeyboardButton(f"{r['nomi']} | {r['turi']}", callback_data=f"del_{r['id']}")] for r in rows]
    kb.append([InlineKeyboardButton("Orqaga", callback_data="admin_panel")])
    await query.edit_message_text("Animelar (ochirish uchun bosing):", reply_markup=InlineKeyboardMarkup(kb))

# ===== ANIME QO'SHISH =====
async def anime_qosh_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_staff(query.from_user.id): return
    context.user_data["ya"] = {"turi": "anime"}
    await query.edit_message_text("1. Anime nomini yozing:")
    return ANIME_NOMI

async def shorts_qosh_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_staff(query.from_user.id): return
    context.user_data["ya"] = {"turi": "shorts"}
    await query.edit_message_text("1. Shorts nomini yozing:")
    return ANIME_NOMI

async def a_nomi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ya"]["nomi"] = update.message.text
    await update.message.reply_text("2. Janrini yozing:")
    return ANIME_JANR

async def a_janr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ya"]["janr"] = update.message.text
    await update.message.reply_text("3. Kod (masalan: 887):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Otkazib yuborish", callback_data="skip_kod")]]))
    return ANIME_KOD

async def a_kod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ya"]["kod"] = update.message.text
    await update.message.reply_text("4. Rasm yuboring:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Otkazib yuborish", callback_data="skip_rasm")]]))
    return ANIME_RASM

async def skip_kod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("4. Rasm yuboring:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Otkazib yuborish", callback_data="skip_rasm")]]))
    return ANIME_RASM

async def a_rasm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data["ya"]["rasm"] = update.message.photo[-1].file_id
    await update.message.reply_text("5. Video yuboring:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Otkazib yuborish", callback_data="skip_video")]]))
    return ANIME_VIDEO_FILE

async def skip_rasm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("5. Video yuboring:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Otkazib yuborish", callback_data="skip_video")]]))
    return ANIME_VIDEO_FILE

async def a_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.video:
        context.user_data["ya"]["video"] = update.message.video.file_id
    await update.message.reply_text("6. VIP yoki Bepul?", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("VIP", callback_data="av_vip"), InlineKeyboardButton("Bepul", callback_data="av_bepul")]]))
    return ANIME_TURI

async def skip_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("6. VIP yoki Bepul?", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("VIP", callback_data="av_vip"), InlineKeyboardButton("Bepul", callback_data="av_bepul")]]))
    return ANIME_TURI

async def a_saqlash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    vip = 1 if query.data == "av_vip" else 0
    ya = context.user_data.get("ya", {})
    with db() as conn:
        conn.execute("INSERT INTO animelar (nomi, janr, kod, rasm, video, vip, turi) VALUES (?,?,?,?,?,?,?)",
            (ya.get("nomi"), ya.get("janr"), ya.get("kod"), ya.get("rasm"), ya.get("video"), vip, ya.get("turi","anime")))
        conn.commit()
    await query.edit_message_text(f"{ya.get('nomi')} qoshildi!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Admin Panel", callback_data="admin_panel")]]))
    return ConversationHandler.END

# ===== SERIYA =====
async def seriya_qosh_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_staff(query.from_user.id): return
    with db() as conn:
        rows = conn.execute("SELECT id, nomi FROM animelar WHERE turi='anime' ORDER BY id DESC").fetchall()
    if not rows:
        await query.edit_message_text("Avval anime qoshing.")
        return
    kb = [[InlineKeyboardButton(r['nomi'], callback_data=f"sa_{r['id']}")] for r in rows]
    kb.append([InlineKeyboardButton("Orqaga", callback_data="admin_panel")])
    await query.edit_message_text("Qaysi animega seriya?", reply_markup=InlineKeyboardMarkup(kb))

async def seriya_anime_sel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    aid = int(query.data.split("_")[1])
    context.user_data["seriya"] = {"anime_id": aid}
    await query.edit_message_text("Seriya nomini yozing (1-qism):")
    return SERIYA_NOMI

async def seriya_nomi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["seriya"]["nomi"] = update.message.text
    await update.message.reply_text("Seriya videosini yuboring:")
    return SERIYA_VIDEO

async def seriya_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = context.user_data.get("seriya", {})
    vid = update.message.video.file_id if update.message.video else None
    with db() as conn:
        conn.execute("INSERT INTO seriyalar (anime_id, nomi, video) VALUES (?,?,?)", (s.get("anime_id"), s.get("nomi"), vid))
        conn.commit()
    await update.message.reply_text(f"{s.get('nomi')} qoshildi!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Admin Panel", callback_data="admin_panel")]]))
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
    await query.edit_message_text(f"{anime['nomi']} ochirildi!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Admin Panel", callback_data="admin_panel")]]))

async def seriya_tahrir_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    with db() as conn:
        rows = conn.execute("SELECT s.id, s.nomi, a.nomi as an FROM seriyalar s JOIN animelar a ON s.anime_id=a.id ORDER BY s.id DESC").fetchall()
    if not rows:
        await query.edit_message_text("Seriya yoq.")
        return
    kb = [[InlineKeyboardButton(f"{r['an']} - {r['nomi']}", callback_data=f"sdel_{r['id']}")] for r in rows]
    kb.append([InlineKeyboardButton("Orqaga", callback_data="admin_panel")])
    await query.edit_message_text("Seriyalar:", reply_markup=InlineKeyboardMarkup(kb))

async def seriya_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.split("_")[1])
    with db() as conn:
        s = conn.execute("SELECT nomi FROM seriyalar WHERE id=?", (sid,)).fetchone()
        conn.execute("DELETE FROM seriyalar WHERE id=?", (sid,))
        conn.commit()
    await query.edit_message_text(f"{s['nomi']} ochirildi!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Admin Panel", callback_data="admin_panel")]]))

async def anime_tahrir_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    with db() as conn:
        rows = conn.execute("SELECT id, nomi FROM animelar ORDER BY id DESC").fetchall()
    if not rows:
        await query.edit_message_text("Anime yoq.")
        return
    kb = [[InlineKeyboardButton(r['nomi'], callback_data=f"aedit_{r['id']}")] for r in rows]
    kb.append([InlineKeyboardButton("Orqaga", callback_data="admin_panel")])
    await query.edit_message_text("Tanlang:", reply_markup=InlineKeyboardMarkup(kb))

async def anime_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    aid = int(query.data.split("_")[1])
    with db() as conn:
        a = conn.execute("SELECT * FROM animelar WHERE id=?", (aid,)).fetchone()
    kb = [
        [InlineKeyboardButton("Ochirish", callback_data=f"del_{aid}")],
        [InlineKeyboardButton("Orqaga", callback_data="anime_tahrir_list")]
    ]
    await query.edit_message_text(f"Anime: {a['nomi']}\nJanr: {a['janr']}\nKod: {a['kod']}\nKorishlar: {a['korishlar']}", reply_markup=InlineKeyboardMarkup(kb))

# ===== POST =====
async def post_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_staff(query.from_user.id): return
    await query.edit_message_text("Post matnini yozing (rasm ham yuborishingiz mumkin):")
    return POST_MATN

async def post_yuborish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db() as conn:
        users = conn.execute("SELECT user_id FROM foydalanuvchilar").fetchall()
    yuborildi = 0
    for u in users:
        try:
            await update.message.copy_to(chat_id=u["user_id"])
            yuborildi += 1
        except: pass
    await update.message.reply_text(f"Post yuborildi! {yuborildi}/{len(users)} ta", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Admin Panel", callback_data="admin_panel")]]))
    return ConversationHandler.END

# ===== ALOHIDA =====
async def alohida_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    await query.edit_message_text("User ID yozing:")
    return ALOHIDA_ID

async def alohida_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["alohida_id"] = int(update.message.text)
        await update.message.reply_text("Xabar yozing:")
        return ALOHIDA_MATN
    except:
        await update.message.reply_text("Notogri ID!")
        return ConversationHandler.END

async def alohida_matn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = context.user_data.get("alohida_id")
    try:
        await update.message.copy_to(chat_id=tid)
        await update.message.reply_text("Xabar yuborildi!")
    except:
        await update.message.reply_text("Yuborib bolmadi.")
    return ConversationHandler.END

# ===== MAJBURIY =====
async def majburiy_azo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    with db() as conn:
        kanallar = conn.execute("SELECT * FROM kanallar").fetchall()
    matn = "Majburiy kanallar:\n\n"
    for k in kanallar:
        matn += f"- {k['nomi']} ({k['kanal_id']})\n"
    matn += "\n@kanal_username yozing qoshish uchun"
    await query.edit_message_text(matn, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Orqaga", callback_data="admin_panel")]]))
    return MAJBURIY_KANAL

async def majburiy_qosh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kanal = update.message.text.strip()
    if not kanal.startswith("@"):
        await update.message.reply_text("@ bilan boshlang!")
        return MAJBURIY_KANAL
    with db() as conn:
        conn.execute("INSERT OR IGNORE INTO kanallar (kanal_id, nomi) VALUES (?,?)", (kanal, kanal))
        conn.commit()
    await update.message.reply_text(f"{kanal} qoshildi!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Admin Panel", callback_data="admin_panel")]]))
    return ConversationHandler.END

# ===== STAFF =====
async def staff_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    with db() as conn:
        stafflar = conn.execute("SELECT * FROM foydalanuvchilar WHERE staff=1").fetchall()
    matn = "Stafflar:\n" + "\n".join([f"- {s['ism']} ({s['user_id']})" for s in stafflar]) if stafflar else "Staff yoq"
    matn += "\n\nYangi staff ID yozing:"
    await query.edit_message_text(matn, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Orqaga", callback_data="admin_panel")]]))
    return STAFF_ID

async def staff_qosh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sid = int(update.message.text)
        with db() as conn:
            conn.execute("INSERT OR IGNORE INTO foydalanuvchilar (user_id, ism) VALUES (?,'Staff')", (sid,))
            conn.execute("UPDATE foydalanuvchilar SET staff=1 WHERE user_id=?", (sid,))
            conn.commit()
        await update.message.reply_text(f"{sid} staff qilindi!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Admin Panel", callback_data="admin_panel")]]))
    except:
        await update.message.reply_text("Notogri ID!")
    return ConversationHandler.END

# ===== SOZLAMALAR =====
async def qollanma_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(f"Hozirgi: {get_sozlama('qollanma')}\n\nYangi matnni yozing:")
    return QOLLANMA_EDIT

async def qollanma_saqlash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db() as conn:
        conn.execute("UPDATE sozlamalar SET qiymat=? WHERE kalit='qollanma'", (update.message.text,))
        conn.commit()
    await update.message.reply_text("Qollanma yangilandi!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Admin Panel", callback_data="admin_panel")]]))
    return ConversationHandler.END

async def reklama_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(f"Hozirgi: {get_sozlama('reklama')}\n\nYangi matnni yozing:")
    return REKLAMA_EDIT

async def reklama_saqlash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db() as conn:
        conn.execute("UPDATE sozlamalar SET qiymat=? WHERE kalit='reklama'", (update.message.text,))
        conn.commit()
    await update.message.reply_text("Reklama yangilandi!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Admin Panel", callback_data="admin_panel")]]))
    return ConversationHandler.END

async def vip_narx_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(f"Hozirgi narx: {get_sozlama('vip_narx')} som\n\nYangi narxni yozing (faqat son):")
    return VIP_NARX_EDIT

async def vip_narx_saqlash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        narx = int(update.message.text)
        with db() as conn:
            conn.execute("UPDATE sozlamalar SET qiymat=? WHERE kalit='vip_narx'", (str(narx),))
            conn.commit()
        await update.message.reply_text(f"VIP narxi {narx} som qilindi!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Admin Panel", callback_data="admin_panel")]]))
    except:
        await update.message.reply_text("Faqat son kiriting!")
    return ConversationHandler.END

async def xush_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Yangi xush kelibsiz matnini yozing:")
    context.user_data["sozlama_kalit"] = "xush_kelibsiz"
    return QOLLANMA_EDIT + 100

async def xush_saqlash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db() as conn:
        conn.execute("UPDATE sozlamalar SET qiymat=? WHERE kalit='xush_kelibsiz'", (update.message.text,))
        conn.commit()
    await update.message.reply_text("Yangilandi!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Admin Panel", callback_data="admin_panel")]]))
    return ConversationHandler.END

async def userlar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    with db() as conn:
        rows = conn.execute("SELECT * FROM foydalanuvchilar ORDER BY vip DESC LIMIT 30").fetchall()
    matn = "Foydalanuvchilar:\n\n"
    for r in rows:
        matn += f"{'[VIP]' if r['vip'] else '[Oddiy]'} {r['ism']} | {r['user_id']}\n"
    await query.edit_message_text(matn, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Orqaga", callback_data="admin_panel")]]))

def main():
    db_setup()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    izlash_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(izlash_nom_start, "^izlash_nom$"), CallbackQueryHandler(izlash_kod_start, "^izlash_kod$")],
        states={IZLASH_HOLAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, izlash_natija)]},
        fallbacks=[CommandHandler("start", start)])

    anime_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(anime_qosh_start, "^anime_qosh$"), CallbackQueryHandler(shorts_qosh_start, "^shorts_qosh$")],
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
        states={ALOHIDA_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, alohida_id)], ALOHIDA_MATN: [MessageHandler(filters.ALL & ~filters.COMMAND, alohida_matn)]},
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

    for conv in [izlash_conv, anime_conv, seriya_conv, tolov_conv, post_conv, alohida_conv, majburiy_conv, staff_conv, qollanma_conv, reklama_conv, vip_narx_conv, xush_conv]:
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

    print("Bot ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()
