import os
import asyncio
import time
from io import BytesIO
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from typing import Optional

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)

from config import (
    DB_PATH,
    BOT_TOKEN,
    STORAGE_DIR,
    EXPIRY_HOURS,
    MAX_BYTES,
    MIN_INTERVAL,
    AUTO_PURGE_INTERVAL,
    AUTH_FORWARDERS,
    ALLOWED_UPLOADERS,
)
from keys import gen_single_use_key, key_to_hash, normalize_key
from db import (
    init_db,
    file_exists_by_hash,
    insert_file,
    get_file_by_keyhash,
    mark_used,
    purge_expired_and_used,
    sha256,
    path_for,
)

LAST_HIT = defaultdict(float)


def rate_limit_ok(user_id: int) -> bool:
    now = time.time()
    if now - LAST_HIT[user_id] < MIN_INTERVAL:
        return False
    LAST_HIT[user_id] = now
    return True


def is_txt(filename: str, mime: Optional[str]) -> bool:
    return filename.lower().endswith(".txt") or (mime or "").startswith("text/")


def extract_forwarder_id(update: Update) -> Optional[int]:
    try:
        uid = update.effective_user.id
        return uid if uid is not None else None
    except Exception:
        return None


async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
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


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not rate_limit_ok(update.effective_user.id):
        return await update.message.reply_text(
            "Demasiadas peticiones; intenta de nuevo en un momento."
        )
    await update.message.reply_text(
        "🔥💳 *BOT OFICIAL ADALIK CORP* 💳🔥\n\n\n"
        + "*_¿Que puede hacer este bot?_*\n\n"
        + "💎_/get \\<clave\\>_  ✦✧✦✧✦  _descargar lote/unidad CC_\n"
        + "💎_/status \\<clave\\>_  ✦✧✦✧✦  _vigencia y tiempo rest\\. de clave_\n"
        + "💎_/help_  ✦✧✦✧✦  _comandos de utilidad_\n\n\n\n"
        + "_Adalik Corp®_",
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
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


async def ping_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not rate_limit_ok(update.effective_user.id):
        return await update.message.reply_text(
            "Demasiadas peticiones; intenta de nuevo en un momento."
        )
    await update.message.reply_text("pong")


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not rate_limit_ok(update.effective_user.id):
        return await update.message.reply_text(
            "Demasiadas peticiones; intenta de nuevo en un momento."
        )
    if not context.args:
        return await update.message.reply_text("Uso: /status <clave>")
    key = normalize_key(" ".join(context.args))
    if not key:
        return await update.message.reply_text("No pude reconocer la clave.")
    row = await get_file_by_keyhash(key_to_hash(key))
    if not row:
        return await update.message.reply_text("No existe esa clave.")
    used = row["used"]
    expires_at = row["expires_at"]
    filename = row["filename"]
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
            f"Vigencia del archivo *{os.path.basename(filename)}*. Tiempo restante: {hrs}h {mins}m.",
            parse_mode="Markdown",
        )
    else:
        return await update.message.reply_text(
            "Sigue vigente (sin expiración configurada)."
        )


async def handle_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not rate_limit_ok(update.effective_user.id):
        return await msg.reply_text(
            "Demasiadas peticiones; intenta de nuevo en un momento."
        )

    doc = msg.document
    if not doc:
        return

    if not is_txt(doc.file_name, doc.mime_type):
        return await msg.reply_text("Solo acepto archivos .txt")

    if ALLOWED_UPLOADERS and update.effective_user.id not in ALLOWED_UPLOADERS:
        return await msg.reply_text("No tienes permiso para subir archivos.")

    if AUTH_FORWARDERS:
        fid = extract_forwarder_id(update)
        if fid not in AUTH_FORWARDERS:
            return await msg.reply_text("❌ Solo reenviados desde autorizados.")

    if doc.file_size and doc.file_size > MAX_BYTES:
        return await msg.reply_text(
            f"Archivo demasiado grande (máx {MAX_BYTES} bytes)."
        )

    f = await context.bot.get_file(doc.file_id)
    data = await f.download_as_bytearray()
    if len(data) > MAX_BYTES:
        return await msg.reply_text(
            f"Archivo demasiado grande (máx {MAX_BYTES} bytes)."
        )

    file_hash = sha256(data)

    if await file_exists_by_hash(file_hash):
        return await msg.reply_text("❗ Este archivo ya fue subido anteriormente.")

    key = gen_single_use_key()
    k_hash = key_to_hash(key)

    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=EXPIRY_HOURS)

    stored_name = f"{now.strftime('%Y%m%d_%H%M%S')}_{doc.file_name}"

    with open(path_for(stored_name), "wb") as fp:
        fp.write(data)

    await insert_file(
        key_hash=k_hash,
        stored_name=stored_name,
        data=data,
        uploader_id=msg.from_user.id,
        created_at_iso=now.isoformat(),
        file_sha=file_hash,
        expires_at_iso=expires.isoformat(),
    )

    await msg.reply_text(
        f"Clave de descarga:\nUsa /get {key}\nClave de un solo uso, expira en {EXPIRY_HOURS}h.",
    )


async def get_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not rate_limit_ok(update.effective_user.id):
        return await update.message.reply_text(
            "Demasiadas peticiones; intenta de nuevo en un momento."
        )
    if not context.args:
        return await update.message.reply_text("Uso: /get <clave>")

    key = normalize_key(" ".join(context.args))
    if not key:
        return await update.message.reply_text("No pude reconocer la clave.")

    row = await get_file_by_keyhash(key_to_hash(key))
    if not row:
        return await update.message.reply_text("Clave inválida o ya utilizada.")
    if row["used"]:
        return await update.message.reply_text("Clave inválida o ya utilizada.")

    exp = row["expires_at"]
    if exp:
        try:
            exp_dt = datetime.fromisoformat(exp)
        except Exception:
            exp_dt = None
        if exp_dt and datetime.now(timezone.utc) > exp_dt:
            await mark_used(row["id"], update.effective_user.id)
            return await update.message.reply_text(
                f"Clave expirada ({EXPIRY_HOURS}h). Pide una nueva."
            )

    fname = row["filename"]
    original_name = os.path.basename(fname)
    if "_" in original_name:
        original_name = original_name.split("_", 1)[-1]

    full_path = os.path.join(STORAGE_DIR, fname)
    try:
        if os.path.exists(full_path):
            with open(full_path, "rb") as f:
                await update.message.reply_document(document=f, filename=original_name)
        else:
            content = row["content"]
            if content is None:
                return await update.message.reply_text(
                    "No se encontró el contenido del archivo."
                )
            bio = BytesIO(content)
            bio.name = original_name
            bio.seek(0)
            await update.message.reply_document(document=bio)

        await mark_used(row["id"], update.effective_user.id)
    except Exception:
        return await update.message.reply_text(
            "No se pudo enviar el archivo. Intenta de nuevo."
        )


def main():
    if not BOT_TOKEN:
        raise SystemExit("Falta BOT_TOKEN (exporta BOT_TOKEN=...)")
    asyncio.run(init_db())
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("get", get_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("ping", ping_cmd))
    app.add_handler(CommandHandler("id", id_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_doc))

    if app.job_queue:
        app.job_queue.run_repeating(
            lambda ctx: asyncio.create_task(purge_expired_and_used()),
            interval=AUTO_PURGE_INTERVAL,
            first=0,
        )

    print("Bot corriendo…")
    app.run_polling()


if __name__ == "__main__":
    main()
