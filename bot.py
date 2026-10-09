import os
from html import escape

import asyncio

import psutil
from PIL import ImageGrab



from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from stress_module import get_stress_handlers
from commands import power, drive


# ============================================================
# CONFIG
# ============================================================

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

ALLOWED_USER_ID = 6426820534


# ============================================================
# AUTHORIZATION
# ============================================================

def authorized(update: Update) -> bool:
    return (
        update.effective_user is not None
        and update.effective_user.id == ALLOWED_USER_ID
    )


# ============================================================
# /start
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        await update.message.reply_text(
            "⛔ Bu botdan istifadə etməyə icazən yoxdur."
        )
        return

    message = (
        "🤖 <b>RemoteHub</b>\n\n"
        "💻 Laptop idarəetmə paneli\n\n"

        "<b>📊 Sistem</b>\n"
        "/status — CPU, RAM, Disk və batareya\n"
        "/battery — Batareya məlumatı\n\n"

        "<b>🔒 İdarə</b>\n"
        "/lock — Windows-u kilidlə\n"
        "/shutdown — Kompüteri söndür\n"
        "/restart — Yenidən başlat\n"
        "/cancel_shutdown — Ləğv et\n\n"

        "<b>📸 Media və fayl</b>\n"
        "/screenshot — Ekran görüntüsü\n"
        "/drive — Google Drive faylları\n\n"

        "<b>🧪 Test</b>\n"
        "/stress — Controlled load test\n"
        "/stress_stop — Load testi dayandır"
    )

    await update.message.reply_text(
        message,
        parse_mode="HTML"
    )


# ============================================================
# /status
# ============================================================

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not authorized(update):
        await update.message.reply_text(
            "⛔ İcazə yoxdur."
        )
        return

    cpu = psutil.cpu_percent(interval=1)

    memory = psutil.virtual_memory()

    disk = psutil.disk_usage("/")

    battery = psutil.sensors_battery()

    if battery:

        battery_percent = battery.percent

        if battery.power_plugged:
            battery_status = f"🔌 {battery_percent}% — Şarj olur"
        else:
            battery_status = f"🔋 {battery_percent}% — Batareyada"

    else:
        battery_status = "🔋 Batareya məlumatı yoxdur"

    message = (
        "🟢 <b>Laptop ONLINE</b>\n\n"
        f"🧠 CPU: {cpu}%\n"
        f"💾 RAM: {memory.percent}% istifadə olunur\n"
        f"💿 Disk: {disk.percent}% istifadə olunur\n"
        f"{battery_status}"
    )

    await update.message.reply_text(
        message,
        parse_mode="HTML"
    )


# ============================================================
# /battery
# ============================================================

async def battery(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not authorized(update):
        await update.message.reply_text(
            "⛔ İcazə yoxdur."
        )
        return

    battery_info = psutil.sensors_battery()

    if battery_info is None:
        await update.message.reply_text(
            "🔋 Batareya haqqında məlumat əldə etmək mümkün olmadı."
        )
        return

    percent = battery_info.percent

    if battery_info.power_plugged:
        status_text = "🔌 Şarj olunur"
    else:
        status_text = "🔋 Batareyada işləyir"

    message = (
        "🔋 <b>Batareya</b>\n\n"
        f"Faiz: <b>{percent}%</b>\n"
        f"Vəziyyət: {status_text}"
    )

    await update.message.reply_text(
        message,
        parse_mode="HTML"
    )


# ============================================================
# /lock
# ============================================================

async def lock(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not authorized(update):
        await update.message.reply_text(
            "⛔ İcazə yoxdur."
        )
        return

    os.system(
        "rundll32.exe user32.dll,LockWorkStation"
    )

    await update.message.reply_text(
        "🔒 Laptop kilidləndi."
    )


# ============================================================
# /screenshot
# ============================================================

async def screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not authorized(update):
        await update.message.reply_text(
            "⛔ İcazə yoxdur."
        )
        return

    await update.message.reply_text(
        "📸 Screenshot hazırlanır..."
    )

    image = ImageGrab.grab()

    screenshot_path = "screenshot.png"

    image.save(screenshot_path)

    with open(screenshot_path, "rb") as photo:

        await update.message.reply_photo(
            photo=photo,
            caption="🖥️ Laptop ekran görüntüsü"
        )

    os.remove(screenshot_path)


# ============================================================
# APPLICATION
# ============================================================

app = (
    Application
    .builder()
    .concurrent_updates(2)
    .token(TOKEN)
    .build()
)


# ============================================================
# BASIC COMMANDS
# ============================================================
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("status", status))
app.add_handler(CommandHandler("battery", battery))
app.add_handler(CommandHandler("lock", lock))
app.add_handler(CommandHandler("screenshot", screenshot))

# ─── YENİ: Power əmrləri ──────────────────────────────────
app.add_handler(CommandHandler("shutdown", power.shutdown))
app.add_handler(CommandHandler("restart", power.restart))
app.add_handler(CommandHandler("cancel_shutdown", power.cancel_shutdown))


# ============================================================
# REMOTEHUB LOAD TEST MODULE
# ============================================================

for handler in get_stress_handlers():
    app.add_handler(handler)

# ─── Drive ────────────────────────────────────────────────
for handler in drive.get_drive_handlers():
    app.add_handler(handler)



# ============================================================
# RUN
# ============================================================

print("🤖 RemoteHub işləyir...")

app.run_polling()