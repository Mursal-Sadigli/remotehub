import asyncio
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, urlparse

import requests
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

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


def load_infra_targets() -> list[dict]:
    """Load the operator's server/service menu from INFRA_SERVICES_JSON."""
    raw = os.environ.get("INFRA_SERVICES_JSON", "").strip()
    if not raw:
        return []
    try:
        entries = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("INFRA_SERVICES_JSON must contain valid JSON.") from exc
    if not isinstance(entries, list):
        raise ValueError("INFRA_SERVICES_JSON must be a JSON array.")

    clean = []
    seen_servers = set()
    for server in entries:
        if not isinstance(server, dict) or not isinstance(server.get("id"), str) or not isinstance(server.get("name"), str):
            raise ValueError("Each infrastructure server needs string id and name fields.")
        server_id = server["id"]
        if not server_id or server_id in seen_servers:
            raise ValueError("Infrastructure server IDs must be non-empty and unique.")
        seen_servers.add(server_id)
        services = server.get("services", [])
        if not isinstance(services, list):
            raise ValueError(f"services for server {server_id!r} must be an array.")
        clean_services = []
        seen_services = set()
        for service in services:
            if not isinstance(service, dict) or not isinstance(service.get("id"), str) or not isinstance(service.get("name"), str):
                raise ValueError("Each service needs string id and name fields.")
            service_id = service["id"]
            if not service_id or service_id in seen_services:
                raise ValueError(f"Service IDs for server {server_id!r} must be non-empty and unique.")
            seen_services.add(service_id)
            provider = service.get("provider")
            if provider not in {"render", "vercel"}:
                raise ValueError(f"Service {service_id!r} provider must be 'render' or 'vercel'.")

            clean_service = {"id": service_id, "name": service["name"], "provider": provider}
            if provider == "render":
                render_id = service.get("service_id")
                if not isinstance(render_id, str) or not render_id:
                    raise ValueError(f"Render service {service_id!r} needs a service_id.")
                clean_service["service_id"] = render_id
            else:
                project_id = service.get("project_id")
                if not isinstance(project_id, str) or not project_id:
                    raise ValueError(f"Vercel service {service_id!r} needs a project_id.")
                clean_service["project_id"] = project_id

                team_id = service.get("team_id")
                if team_id is not None:
                    if not isinstance(team_id, str) or not team_id:
                        raise ValueError(f"Vercel service {service_id!r} has an invalid team_id.")
                    clean_service["team_id"] = team_id

                deploy_hook_url = service.get("deploy_hook_url")
                if deploy_hook_url is not None:
                    if not isinstance(deploy_hook_url, str):
                        raise ValueError(f"Vercel service {service_id!r} has an invalid deploy_hook_url.")
                    parsed_url = urlparse(deploy_hook_url)
                    if (
                        parsed_url.scheme != "https"
                        or parsed_url.hostname != "api.vercel.com"
                        or not parsed_url.path.startswith("/v1/integrations/deploy/")
                    ):
                        raise ValueError(
                            f"Vercel service {service_id!r} deploy_hook_url must be a Vercel Deploy Hook URL."
                        )
                    clean_service["deploy_hook_url"] = deploy_hook_url
            clean_services.append(clean_service)
        clean.append({"id": server_id, "name": server["name"], "services": clean_services})
    return clean


INFRA_TARGETS = load_infra_targets()


def authorized(update: Update) -> bool:
    return update.effective_user is not None and update.effective_user.id == ALLOWED_USER_ID


def infra_keyboard(servers: list[dict]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(server["name"], callback_data=f"infra:server:{index}")]
        for index, server in enumerate(servers)
    ])


def infra_services_keyboard(server_index: int, server: dict) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(service["name"], callback_data=f"infra:service:{server_index}:{index}")]
        for index, service in enumerate(server["services"])
    ]
    buttons.append([InlineKeyboardButton("⬅️ Serverlər", callback_data="infra:servers:back")])
    return InlineKeyboardMarkup(buttons)


def infra_service_keyboard(service: dict, server_index: int, service_index: int) -> InlineKeyboardMarkup:
    callback_prefix = f"infra:action:{server_index}:{service_index}"
    buttons = [[InlineKeyboardButton("📊 Status", callback_data=f"{callback_prefix}:status")]]
    if service["provider"] == "render":
        buttons.append([InlineKeyboardButton("🔄 Restart", callback_data=f"{callback_prefix}:restart")])
    elif service.get("deploy_hook_url"):
        buttons.append([InlineKeyboardButton("🚀 Yeni deployment", callback_data=f"{callback_prefix}:deploy")])
    buttons.extend([
        [InlineKeyboardButton("🔁 Xidmət dəyiş", callback_data="infra:services:back")],
        [InlineKeyboardButton("🖥 Server dəyiş", callback_data="infra:servers:back")],
    ])
    return InlineKeyboardMarkup(buttons)


async def infra_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    if not INFRA_TARGETS:
        await update.message.reply_text(
            "Server/xidmət siyahısı hələ qurulmayıb. Render-də INFRA_SERVICES_JSON dəyişənini əlavə edin."
        )
        return
    await update.message.reply_text(
        "Server seç:", reply_markup=infra_keyboard(INFRA_TARGETS)
    )


async def infra_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not authorized(update):
        await query.answer("İcazə yoxdur.", show_alert=True)
        return
    await query.answer()
    parts = query.data.split(":")
    if len(parts) < 3 or parts[0] != "infra":
        return

    action = parts[1]
    if action == "server" and len(parts) == 3:
        try:
            server_index = int(parts[2])
            if server_index < 0:
                raise IndexError
            server = INFRA_TARGETS[server_index]
        except (ValueError, IndexError):
            await query.edit_message_text("Server tapılmadı. /infra ilə siyahını yenilə.")
            return
        context.user_data["infra_server_index"] = server_index
        context.user_data.pop("infra_service_index", None)
        if not server["services"]:
            await query.edit_message_text(f"{server['name']} seçildi. Bu server üçün xidmət əlavə edilməyib.")
            return
        await query.edit_message_text(
            f"{server['name']} seçildi. Xidmət seç:",
            reply_markup=infra_services_keyboard(server_index, server),
        )
    elif action == "service" and len(parts) == 4:
        try:
            server_index = int(parts[2])
            service_index = int(parts[3])
            if server_index < 0 or service_index < 0:
                raise IndexError
            server = INFRA_TARGETS[server_index]
            service = server["services"][service_index]
        except (KeyError, TypeError, ValueError, IndexError):
            await query.edit_message_text("Xidmət tapılmadı. /infra ilə yenidən başla.")
            return
        context.user_data["infra_server_index"] = server_index
        await query.edit_message_text(
            f"Seçildi: {server['name']} → {service['name']} ({service['provider'].title()})",
            reply_markup=infra_service_keyboard(service, server_index, service_index),
        )
    elif action == "services" and len(parts) == 3 and parts[2] == "back":
        try:
            server = INFRA_TARGETS[context.user_data["infra_server_index"]]
        except (KeyError, TypeError, IndexError):
            await query.edit_message_text("Server seçimi bitib. /infra ilə yenidən başla.")
            return
        server_index = context.user_data["infra_server_index"]
        await query.edit_message_text(
            f"{server['name']} üçün xidmət seç:",
            reply_markup=infra_services_keyboard(server_index, server),
        )
    elif action == "action" and len(parts) == 5:
        try:
            server_index = int(parts[2])
            service_index = int(parts[3])
            if server_index < 0 or service_index < 0:
                raise IndexError
            server = INFRA_TARGETS[server_index]
            service = server["services"][service_index]
        except (ValueError, TypeError, IndexError):
            await query.edit_message_text("Xidmət seçimi bitib. /infra ilə yenidən başla.")
            return

        operation = parts[4]
        if operation not in {"status", "restart", "deploy"}:
            return
        if operation == "restart" and service["provider"] != "render":
            return
        if operation == "deploy" and not service.get("deploy_hook_url"):
            return

        try:
            result = await asyncio.to_thread(run_infra_operation, service, operation)
        except RuntimeError as exc:
            await query.edit_message_text(
                f"Əməliyyat alınmadı: {exc}",
                reply_markup=infra_service_keyboard(service, server_index, service_index),
            )
            return
        await query.edit_message_text(
            f"{server['name']} → {service['name']}\n{result}",
            reply_markup=infra_service_keyboard(service, server_index, service_index),
        )
    elif action == "servers" and len(parts) == 3 and parts[2] == "back":
        await query.edit_message_text("Server seç:", reply_markup=infra_keyboard(INFRA_TARGETS))


def _platform_request(method: str, url: str, token: str | None = None, params: dict | None = None):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = requests.request(
            method, url, headers=headers, params=params, timeout=20, allow_redirects=False
        )
    except requests.Timeout as exc:
        raise RuntimeError("sorğu vaxtı bitdi.") from exc
    except requests.RequestException as exc:
        raise RuntimeError("platformaya qoşulmaq mümkün olmadı.") from exc

    if not response.ok:
        raise RuntimeError(f"platforma HTTP {response.status_code} xətası qaytardı.")
    return response


def _platform_json(response) -> dict | list:
    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError("platformadan düzgün JSON cavabı alınmadı.") from exc
    if not isinstance(data, (dict, list)):
        raise RuntimeError("platformadan gözlənilməyən cavab alındı.")
    return data


def run_infra_operation(service: dict, operation: str) -> str:
    provider = service["provider"]
    if provider == "render":
        api_key = os.environ.get("RENDER_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("Render əməliyyatları üçün RENDER_API_KEY təyin edilməyib.")
        service_id = quote(service["service_id"], safe="")
        base_url = f"https://api.render.com/v1/services/{service_id}"

        if operation == "restart":
            _platform_request("POST", f"{base_url}/restart", token=api_key)
            return "Render restart sorğusu qəbul etdi."
        if operation != "status":
            raise RuntimeError("Bu əməliyyat Render üçün dəstəklənmir.")

        service_data = _platform_json(_platform_request("GET", base_url, token=api_key))
        if not isinstance(service_data, dict):
            raise RuntimeError("Render xidmət məlumatı gözlənilməyən formatdadır.")
        suspended = service_data.get("suspended")
        if suspended == "suspended":
            status_text = "Dayandırılıb"
        elif suspended == "not_suspended":
            status_text = "Dayandırılmayıb"
        else:
            status_text = "Naməlum"

        deploys = _platform_json(_platform_request(
            "GET", f"{base_url}/deploys", token=api_key, params={"limit": 1}
        ))
        deploy_status = "məlumat yoxdur"
        if isinstance(deploys, list) and deploys:
            latest_deploy = deploys[0].get("deploy", {}) if isinstance(deploys[0], dict) else {}
            if not isinstance(latest_deploy, dict):
                raise RuntimeError("Render deploy məlumatı gözlənilməyən formatdadır.")
            deploy_status = latest_deploy.get("status", "naməlum")
        return f"Render xidməti: {status_text}\nSon deploy: {deploy_status}"

    if provider == "vercel":
        if operation == "deploy":
            response = _platform_request("POST", service["deploy_hook_url"])
            return "Vercel Deploy Hook sorğusu qəbul etdi."
        if operation != "status":
            raise RuntimeError("Bu əməliyyat Vercel üçün dəstəklənmir.")

        token = os.environ.get("VERCEL_TOKEN", "").strip()
        if not token:
            raise RuntimeError("Vercel statusu üçün VERCEL_TOKEN təyin edilməyib.")
        params = {"projectId": service["project_id"], "limit": 1}
        if service.get("team_id"):
            params["teamId"] = service["team_id"]
        deployments = _platform_json(_platform_request(
            "GET", "https://api.vercel.com/v7/deployments", token=token, params=params
        ))
        if not isinstance(deployments, dict) or not isinstance(deployments.get("deployments"), list):
            raise RuntimeError("Vercel deployment məlumatı gözlənilməyən formatdadır.")
        items = deployments["deployments"]
        if not items:
            return "Vercel-də deployment tapılmadı."
        latest = items[0]
        if not isinstance(latest, dict):
            raise RuntimeError("Vercel deployment məlumatı gözlənilməyən formatdadır.")
        state = latest.get("readyState") or latest.get("state") or "naməlum"
        deployment_url = latest.get("url")
        result = f"Son deployment: {state}"
        if deployment_url:
            result += f"\nURL: https://{deployment_url}"
        return result

    raise RuntimeError("Dəstəklənməyən platforma.")


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
        "/drive — Google Drive faylları və qovluqlar\n"
        "/infra — Server və xidmət seçimi\n\n"
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
    app.add_handler(CommandHandler("infra", infra_menu))
    app.add_handler(CallbackQueryHandler(infra_callback, pattern=r"^infra:"))
    
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
        BotCommand("infra",           "Server və xidmət seçimi"),
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
