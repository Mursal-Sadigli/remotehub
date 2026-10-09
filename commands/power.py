"""
Power əmrləri: /shutdown, /restart, /cancel_shutdown
"""

import os
from telegram import Update
from telegram.ext import ContextTypes

# ─── Konfiqurasiya ────────────────────────────────────────
# İcazəli istifadəçi ID-si. bot.py-dən import etmək üçün
# aşağıdaki funksiya istifadə olunur.
ALLOWED_USER_ID = 6426820534

# Söndürmə/restart gecikməsi (saniyə)
DELAY_SECONDS = 10


# ─── Köməkçi funksiyalar ──────────────────────────────────
def authorized(update: Update) -> bool:
    """İstifadəçinin icazəli olub-olmadığını yoxlayır."""
    return (
        update.effective_user is not None
        and update.effective_user.id == ALLOWED_USER_ID
    )


# ─── Əmrlər ───────────────────────────────────────────────
async def shutdown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kompüteri söndürür (gecikmə ilə)."""
    if not authorized(update):
        await update.message.reply_text("⛔ İcazə yoxdur.")
        return

    await update.message.reply_text(
        f"⏻ <b>Kompüter söndürüləcək</b>\n\n"
        f"⏱️ Gecikmə: {DELAY_SECONDS} saniyə\n"
        f"❌ Ləğv etmək üçün: /cancel_shutdown",
        parse_mode="HTML"
    )

    os.system(f"shutdown /s /t {DELAY_SECONDS}")


async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kompüteri yenidən başladır (gecikmə ilə)."""
    if not authorized(update):
        await update.message.reply_text("⛔ İcazə yoxdur.")
        return

    await update.message.reply_text(
        f"🔄 <b>Kompüter yenidən başladılacaq</b>\n\n"
        f"⏱️ Gecikmə: {DELAY_SECONDS} saniyə\n"
        f"❌ Ləğv etmək üçün: /cancel_shutdown",
        parse_mode="HTML"
    )

    os.system(f"shutdown /r /t {DELAY_SECONDS}")


async def cancel_shutdown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Planlaşdırılmış söndürmə/restart əməliyyatını ləğv edir."""
    if not authorized(update):
        await update.message.reply_text("⛔ İcazə yoxdur.")
        return

    return_code = os.system("shutdown /a")

    if return_code == 0:
        await update.message.reply_text(
            "✅ <b>Planlaşdırılmış əməliyyat ləğv edildi.</b>",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            "ℹ️ Ləğv ediləcək planlaşdırılmış əməliyyat yoxdur."
        )