import os
import asyncio
import aiosqlite
import hashlib
import secrets
import re
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Optional
from io import BytesIO
from telegram import Update, InputFile
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from telegram.ext import CallbackQueryHandler
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)

# =======================
# Config desde ENV
# =======================
DB_PATH = os.environ.get("DB_PATH", "AdalikM.db")
BOT_TOKEN = os.environ.get("BOT_TOKEN")  # requerido
STORAGE_DIR = os.environ.get("STORAGE_DIR", "storage")
EXPIRY_HOURS = int(os.environ.get("EXPIRY_HOURS", "24"))
MAX_BYTES = int(os.environ.get("MAX_BYTES", 2_000_000))  # 2 MB por defecto
MIN_INTERVAL = float(
    os.environ.get("MIN_INTERVAL", 1.0)
)  # seg entre requests por usuario
AUTO_PURGE_INTERVAL = int(os.environ.get("AUTO_PURGE_INTERVAL", 3600))  # cada 1h

os.makedirs(STORAGE_DIR, exist_ok=True)

# Reenvío autorizado (IDs de remitente original)
AUTH_FORWARDERS = {
    int(x)
    for x in os.environ.get("AUTH_FORWARDERS", "").split(",")
    if x.strip().isdigit()
}

# Lista blanca de uploaders (quiénes pueden SUBIR). Vacío = cualquiera.
ALLOWED_UPLOADERS = {
    int(x)
    for x in os.environ.get("ALLOWED_UPLOADERS", "").split(",")
    if x.strip().isdigit()
}

# Rate limiting en memoria (por proceso)
LAST_HIT = defaultdict(float)


# =======================
# Utilidades
# =======================
def is_txt(filename: str, mime: Optional[str]) -> bool:
    return filename.lower().endswith(".txt") or (mime or "").startswith("text/")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def gen_single_use_key() -> str:
    """
    Clave tipo: 6 dígitos - variante _ 64 hex
    Ej: 547146-1_d1ba88be95ad625f...(64 hex)
    """
    prefix = f"{secrets.randbelow(900000)+100000}"  # 6 dígitos
    variant = str(secrets.randbelow(3) + 1)  # 1..3
    suffix = secrets.token_hex(32)  # 64 hex
    return f"{prefix}-{variant}_{suffix}"


def key_to_hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def normalize_key(text: str) -> Optional[str]:
    """
    Extrae la clave aunque venga con '@Bot /get ...', saltos de línea, etc.
    """
    text = text.replace("\n", " ").strip()
    m = re.search(r"(\d{6}-[0-9]+_[A-Za-z0-9]{20,})", text)
    if m:
        return m.group(1)
    m = re.search(r"([A-Za-z0-9_-]{20,})", text)
    return m.group(1) if m else None


def extract_forwarder_id(update: Update) -> Optional[int]:
    """
    Intenta obtener el remitente de un mensaje reenviado (ptb v20).
    """
    m = update.effective_user.id
    try:
        if m is not None:
            return m
    except Exception:
        pass
    return None


def rate_limit_ok(user_id: int) -> bool:
    now = time.time()
    if now - LAST_HIT[user_id] < MIN_INTERVAL:
        return False
    LAST_HIT[user_id] = now
    return True


# =======================
# Base de datos
# =======================
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
        CREATE TABLE IF NOT EXISTS files(
          id           INTEGER PRIMARY KEY AUTOINCREMENT,
          key_hash     TEXT UNIQUE,
          filename     TEXT,
          content      BLOB,
          uploader_id  INTEGER,
          used         INTEGER DEFAULT 0,
          created_at   TEXT,
          file_sha     TEXT,
          expires_at   TEXT,
          used_by      INTEGER,
          used_at      TEXT
        )
        """
        )
        await db.commit()


async def purge_expired_and_used():
    """
    Borra de la DB las filas usadas o expiradas y elimina del filesystem
    el archivo físico si existe.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    to_delete = []
    async with aiosqlite.connect(DB_PATH) as db:
        # Traer candidatos para limpiar
        cur = await db.execute(
            """
            SELECT id, filename, used, expires_at
            FROM files
            WHERE used = 1
               OR (expires_at IS NOT NULL AND expires_at < ?)
        """,
            (now_iso,),
        )
        rows = await cur.fetchall()

        for fid, fname, used, expires_at in rows:
            # Intentar borrar archivo físico
            fpath = os.path.join(STORAGE_DIR, os.path.basename(fname))
            try:
                if os.path.exists(fpath):
                    os.remove(fpath)
            except Exception:
                pass
            to_delete.append(fid)

        # Borrar de DB
        if to_delete:
            q = f"DELETE FROM files WHERE id IN ({','.join('?'*len(to_delete))})"
            await db.execute(q, to_delete)
            await db.commit()


# =======================
# Handlers
# =======================


async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not rate_limit_ok(update.effective_user.id):
            return await update.message.reply_text(
                "Demasiadas peticiones; intenta de nuevo en un momento."
            )
        try:
            user = update.effective_user
            uid = user.id
            username = f"@{user.username}" if user.username else "(sin username)"
            await update.message.reply_text(f"🆔 Tu ID: {uid}\n👤 Usuario: {username}")
        except Exception:
            await update.message.reply_text("Error al obtener tu ID.")
    except Exception:
        return


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not rate_limit_ok(update.effective_user.id):
            return await update.message.reply_text(
                "Demasiadas peticiones; intenta de nuevo en un momento."
            )
        await update.message.reply_text(
            f"🔥💳 *BOT OFICIAL ADALIK CORP* 💳🔥\n\n\n"
            + "*_¿Que puede hacer este bot?_*\n\n"
            + "💎_/get \<clave\>_  ✦✧✦✧✦  _descargar lote/unidad CC_\n"
            + "💎_/status \<clave\>_  ✦✧✦✧✦  _vigencia y tiempo rest\. de clave_\n"
            + "💎_/help_  ✦✧✦✧✦  _comandos de utilidad_\n\n\n\n"
            + "_Adalik Corp®_",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    except Exception:
        # Error silencioso para no filtrar trazas a usuarios
        return


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not rate_limit_ok(update.effective_user.id):
            return await update.message.reply_text(
                "Demasiadas peticiones; intenta de nuevo en un momento."
            )
        msg = (
            "📦 *ADALIK CORP HELPER* 📦\n\n"
            "✨ *Comandos disponibles:*\n"
            "> • _/start_ → mensaje de bienvenida\n"
            "> • _/help_ → muestra esta ayuda\n"
            "> • _/id_ → devuelve tu identificador de usuario\n"
            "> • _/ping_ → comprobación de estado del bot\n\n"
            "🕒 *Las claves expiran automáticamente tras 24 horas y son de un solo uso*\n"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception:
        return


async def ping_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not rate_limit_ok(update.effective_user.id):
            return await update.message.reply_text(
                "Demasiadas peticiones; intenta de nuevo en un momento."
            )
        await update.message.reply_text("pong")
    except Exception:
        return


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not rate_limit_ok(update.effective_user.id):
            return await update.message.reply_text(
                "Demasiadas peticiones; intenta de nuevo en un momento."
            )
        if not context.args:
            return await update.message.reply_text("Uso: /status <clave>")
        key = normalize_key(" ".join(context.args))
        if not key:
            return await update.message.reply_text("No pude reconocer la clave.")
        k_hash = key_to_hash(key)
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                """
                SELECT used, expires_at, filename FROM files WHERE key_hash = ?
            """,
                (k_hash,),
            )
            row = await cur.fetchone()
            if not row:
                return await update.message.reply_text("No existe esa clave.")
            used, expires_at, filename = row
            if used:
                return await update.message.reply_text("Esa clave ya fue utilizada.")
            if expires_at:
                exp_dt = datetime.fromisoformat(expires_at)
                remaining = exp_dt - datetime.now(timezone.utc)
                if remaining.total_seconds() <= 0:
                    return await update.message.reply_text("Clave expirada.")
                hrs = int(remaining.total_seconds() // 3600)
                mins = int((remaining.total_seconds() % 3600) // 60)
                return await update.message.reply_text(
                    f"Vigencia del archivo *{os.path.basename(filename)}*. "
                    f"Tiempo restante: {hrs}h {mins}m.",
                    parse_mode="Markdown",
                )
            else:
                return await update.message.reply_text(
                    "Sigue vigente (sin expiración configurada)."
                )
    except Exception:
        return


async def handle_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    try:
        if not rate_limit_ok(update.effective_user.id):
            return await msg.reply_text(
                "Demasiadas peticiones; intenta de nuevo en un momento."
            )

        doc = msg.document
        if not doc:
            return

        # Validar extensión/mime
        if not is_txt(doc.file_name, doc.mime_type):
            return await msg.reply_text("Solo acepto archivos .txt")

        # Lista blanca de uploaders (si configurada)
        if ALLOWED_UPLOADERS and update.effective_user.id not in ALLOWED_UPLOADERS:
            return await msg.reply_text("No tienes permiso para subir archivos.")

        # Reenvío autorizado (si configurado)
        if AUTH_FORWARDERS:
            fid = extract_forwarder_id(update)
            if fid not in AUTH_FORWARDERS:
                return await msg.reply_text("❌ Solo reenviados desde autorizados.")

        # Límite de tamaño
        if doc.file_size and doc.file_size > MAX_BYTES:
            return await msg.reply_text(
                f"Archivo demasiado grande (máx {MAX_BYTES} bytes)."
            )

        # Descargar datos
        f = await context.bot.get_file(doc.file_id)
        data = await f.download_as_bytearray()
        if len(data) > MAX_BYTES:
            return await msg.reply_text(
                f"Archivo demasiado grande (máx {MAX_BYTES} bytes)."
            )

        file_hash = sha256(data)

        # Duplicados por hash
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT id FROM files WHERE file_sha = ?", (file_hash,)
            )
            if await cur.fetchone():
                return await msg.reply_text(
                    "❗ Este archivo ya fue subido anteriormente."
                )

        # Generar clave y guardar
        key = gen_single_use_key()

        k_hash = key_to_hash(key)

        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=EXPIRY_HOURS)

        stored_name = f"{now.strftime('%Y%m%d_%H%M%S')}_{doc.file_name}"

        path = os.path.join(STORAGE_DIR, stored_name)
        with open(path, "wb") as fp:
            fp.write(data)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                INSERT INTO files(key_hash, filename, content, uploader_id, used,
                                  created_at, file_sha, expires_at)
                VALUES (?, ?, ?, ?, 0, ?, ?, ?)
            """,
                (
                    k_hash,
                    stored_name,
                    data,
                    msg.from_user.id,
                    now.isoformat(),
                    file_hash,
                    expires.isoformat(),
                ),
            )
            await db.commit()

        await msg.reply_text(
            f"Clave de descarga:\n"
            f"Usa /get {key}\n Clave de un solo uso, expira en {EXPIRY_HOURS}h.",
        )
    except Exception:
        try:
            await msg.reply_text(
                "Ocurrió un error al procesar el archivo. Intenta de nuevo."
            )
        except Exception:
            pass


async def get_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Rate limit
        if not rate_limit_ok(update.effective_user.id):
            return await update.message.reply_text(
                "Demasiadas peticiones; intenta de nuevo en un momento."
            )

        # Argumento requerido
        if not context.args:
            return await update.message.reply_text("Uso: /get <clave>")

        # Normalizar/validar clave
        key_raw = " ".join(context.args)
        key = normalize_key(key_raw)
        if not key:
            return await update.message.reply_text("No pude reconocer la clave.")

        k_hash = key_to_hash(key)

        # Buscar registro
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT id, filename, content, used, expires_at, uploader_id
                FROM files
                WHERE key_hash = ?
                """,
                (k_hash,),
            )
            row = await cur.fetchone()

            if not row:
                return await update.message.reply_text("Clave inválida o ya utilizada.")

            # Campos
            fid = row["id"]
            fname = row["filename"]
            content = row["content"]
            used = row["used"]
            expires_at = row["expires_at"]
            uploader_id = row["uploader_id"]

            # Ya utilizada
            if used:
                return await update.message.reply_text("Clave inválida o ya utilizada.")

            # Expiración
            if expires_at:
                try:
                    exp_dt = datetime.fromisoformat(expires_at)
                except Exception:
                    exp_dt = None
                if exp_dt and datetime.now(timezone.utc) > exp_dt:
                    # Marca como usada por expiración
                    await db.execute(
                        "UPDATE files SET used = 1, used_at = ? WHERE id = ?",
                        (datetime.now(timezone.utc).isoformat(), fid),
                    )
                    await db.commit()
                    return await update.message.reply_text(
                        f"Clave expirada ({EXPIRY_HOURS}h). Pide una nueva."
                    )

        # Enviar archivo (prioriza desde disco; si no existe, usa BLOB)
        original_name = os.path.basename(fname)
        if "_" in original_name:
            original_name = original_name.split("_", 1)[-1]

        full_path = os.path.join(STORAGE_DIR, fname)

        try:
            if os.path.exists(full_path):
                with open(full_path, "rb") as f:
                    file_data = f.read()
                bio = BytesIO(file_data)
                bio.name = original_name
                bio.seek(0)
                await update.message.reply_document(document=bio)
            else:
                # Fallback: enviar desde DB (BLOB)
                if content is None:
                    return await update.message.reply_text(
                        "No se encontró el contenido del archivo."
                    )
                bio = BytesIO(content)
                bio.name = original_name
                bio.seek(0)
                await update.message.reply_document(document=bio)

            # ✅ Si llegamos aquí, el envío fue exitoso → marcar como usada
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    """
                    UPDATE files
                    SET used = 1, used_by = ?, used_at = ?
                    WHERE id = ? AND used = 0
                    """,
                    (
                        update.effective_user.id,
                        datetime.now(timezone.utc).isoformat(),
                        fid,
                    ),
                )
                await db.commit()

        except Exception as e:
            # No marcar usada si falló el envío
            print(f"[get_cmd] Error al enviar archivo: {e!r}")
            return await update.message.reply_text(
                "No se pudo enviar el archivo. Intenta de nuevo."
            )

    except Exception as e:
        try:
            await update.message.reply_text(
                "Ocurrió un error al entregar el archivo. Intenta de nuevo."
            )
        except Exception:
            pass
        # Log útil en contenedor
        print(f"[get_cmd] error general: {e!r}")


# =======================
# Main
# =======================
def main():
    if not BOT_TOKEN:
        raise SystemExit("Falta BOT_TOKEN (exporta BOT_TOKEN=...)")

    # Ejecuta la inicialización de DB (async) ANTES de arrancar el bot
    asyncio.run(init_db())

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("get", get_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("ping", ping_cmd))
    app.add_handler(CommandHandler("id", id_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_doc))

    # Purga periódica (puedes agendar una corrutina en JobQueue)
    if app.job_queue:
        app.job_queue.run_repeating(
            lambda ctx: asyncio.create_task(purge_expired_and_used()),
            interval=AUTO_PURGE_INTERVAL,
            first=0,
        )

    print("Bot corriendo…")
    # IMPORTANTE: NO usar await aquí ni envolver en asyncio.run(...)
    app.run_polling()


if __name__ == "__main__":
    main()
