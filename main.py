"""
relay_bot.py — Bot relais anonyme
Les messages envoyés en DM au bot sont transférés dans un groupe.
Les réponses dans le groupe (en reply) sont renvoyées à l'utilisateur.
"""
import logging
import os
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

RELAY_BOT_TOKEN = os.getenv("RELAY_BOT_TOKEN", "")
GROUP_CHAT_ID   = int(os.getenv("RELAY_GROUP_ID", "0"))  # ID du groupe (négatif ex: -1001234567890)

# Stocke la correspondance : message_id dans le groupe → user_id
# (en mémoire, se remet à zéro au redémarrage)
msg_map: dict[int, int] = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Bienvenue sur le support *Alpha Convert* !\n\n"
        "Envoie-moi ton message et notre équipe te répondra rapidement.\n\n"
        "_Ton identité reste anonyme._",
        parse_mode="Markdown",
    )


async def forward_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """DM utilisateur → groupe"""
    user    = update.effective_user
    message = update.message

    # Ne pas traiter les messages venant du groupe
    if update.effective_chat.id == GROUP_CHAT_ID:
        return

    header = (
        f"👤 *Utilisateur :* {user.first_name}"
        + (f" (@{user.username})" if user.username else "")
        + f"\n🆔 ID : `{user.id}`\n\n"
    )

    try:
        if message.text:
            sent = await context.bot.send_message(
                chat_id    = GROUP_CHAT_ID,
                text       = header + message.text,
                parse_mode = "Markdown",
            )
        elif message.photo:
            sent = await context.bot.send_photo(
                chat_id   = GROUP_CHAT_ID,
                photo     = message.photo[-1].file_id,
                caption   = header + (message.caption or ""),
                parse_mode= "Markdown",
            )
        elif message.video:
            sent = await context.bot.send_video(
                chat_id   = GROUP_CHAT_ID,
                video     = message.video.file_id,
                caption   = header + (message.caption or ""),
                parse_mode= "Markdown",
            )
        elif message.document:
            sent = await context.bot.send_document(
                chat_id   = GROUP_CHAT_ID,
                document  = message.document.file_id,
                caption   = header + (message.caption or ""),
                parse_mode= "Markdown",
            )
        else:
            await message.reply_text("⚠️ Type de message non supporté. Envoie du texte ou une image.")
            return

        # Mémoriser la correspondance
        msg_map[sent.message_id] = user.id
        await message.reply_text("✅ Message envoyé ! Notre équipe te répondra bientôt.")

    except Exception as e:
        logger.error(f"Erreur forward_to_group : {e}")
        await message.reply_text("❌ Erreur lors de l'envoi. Réessaie.")


async def reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Réponse dans le groupe → DM utilisateur"""
    message = update.message

    # Uniquement les messages du groupe qui sont des réponses
    if update.effective_chat.id != GROUP_CHAT_ID:
        return
    if not message.reply_to_message:
        return
    # Ignorer les messages du bot lui-même
    if message.from_user.is_bot:
        return

    original_id = message.reply_to_message.message_id
    user_id     = msg_map.get(original_id)

    if not user_id:
        await message.reply_text("⚠️ Impossible de retrouver l'utilisateur (bot redémarré ?).")
        return

    try:
        if message.text:
            await context.bot.send_message(
                chat_id    = user_id,
                text       = f"💬 *Réponse du support :*\n\n{message.text}",
                parse_mode = "Markdown",
            )
        elif message.photo:
            await context.bot.send_photo(
                chat_id  = user_id,
                photo    = message.photo[-1].file_id,
                caption  = f"💬 *Réponse du support :*\n\n{message.caption or ''}",
                parse_mode="Markdown",
            )
        else:
            await context.bot.send_message(
                chat_id = user_id,
                text    = "💬 Le support t'a envoyé un message (type non supporté).",
            )

        await message.reply_text("✅ Réponse envoyée à l'utilisateur.")

    except Exception as e:
        logger.error(f"Erreur reply_to_user : {e}")
        await message.reply_text(f"❌ Impossible d'envoyer à l'utilisateur : {e}")


def main():
    app = Application.builder().token(RELAY_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    # Messages DM → groupe
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & ~filters.COMMAND,
        forward_to_group
    ))

    # Réponses groupe → utilisateur
    app.add_handler(MessageHandler(
        filters.Chat(GROUP_CHAT_ID) & filters.REPLY & ~filters.COMMAND,
        reply_to_user
    ))

    logger.info("✅ Bot relais démarré")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
