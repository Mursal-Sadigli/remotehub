import asyncio
import html
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
)

ALLOWED_TARGETS = {
    "smartai-shop": "https://smartai-shop.vercel.app/",
}

K6_PATH = r"C:\Program Files\k6\k6.exe"
MAX_DURATION = 60
MAX_RATE = 10
MAX_REQUESTS = MAX_DURATION * MAX_RATE

SITE, DURATION, RATE, CONFIRM = range(4)

stress_process = None


def authorized(update: Update) -> bool:
    return (
        update.effective_user is not None
        and update.effective_user.id == 6426820534
    )


async def stress_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        await update.message.reply_text("⛔ İcazə yoxdur.")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("🛒 smartai-shop.vercel.app",
                              callback_data="stress_site:smartai-shop")],
        [InlineKeyboardButton("❌ CANCEL", callback_data="stress_cancel")],
    ]

    await update.message.reply_text(
        "🧪 <b>REMOTEHUB LOAD TEST</b>\n\n🌐 Test etmək istədiyin saytı seç:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return SITE


async def choose_site(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "stress_cancel":
        await query.edit_message_text("❌ Test ləğv edildi.")
        return ConversationHandler.END

    key = query.data.split(":", 1)[1]
    target = ALLOWED_TARGETS.get(key)

    if not target:
        await query.edit_message_text("⛔ Bu sayt allowlist-də deyil.")
        return ConversationHandler.END

    context.user_data["stress_target"] = target

    keyboard = [
        [InlineKeyboardButton("10 saniyə", callback_data="stress_duration:10"),
         InlineKeyboardButton("30 saniyə", callback_data="stress_duration:30")],
        [InlineKeyboardButton("60 saniyə", callback_data="stress_duration:60")],
        [InlineKeyboardButton("❌ CANCEL", callback_data="stress_cancel")],
    ]

    await query.edit_message_text(
        "⏱️ <b>Müddəti seç:</b>\n\nMaksimum: 60 saniyə",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return DURATION


async def choose_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "stress_cancel":
        await query.edit_message_text("❌ Test ləğv edildi.")
        return ConversationHandler.END

    duration = int(query.data.split(":", 1)[1])
    context.user_data["stress_duration"] = duration

    keyboard = [
        [InlineKeyboardButton("1 req/s", callback_data="stress_rate:1"),
         InlineKeyboardButton("5 req/s", callback_data="stress_rate:5")],
        [InlineKeyboardButton("10 req/s", callback_data="stress_rate:10")],
        [InlineKeyboardButton("❌ CANCEL", callback_data="stress_cancel")],
    ]

    await query.edit_message_text(
        "📨 <b>Request rate seç:</b>\n\nMaksimum: 10 request/s",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return RATE


async def choose_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "stress_cancel":
        await query.edit_message_text("❌ Test ləğv edildi.")
        return ConversationHandler.END

    rate = int(query.data.split(":", 1)[1])
    duration = context.user_data["stress_duration"]
    total = duration * rate

    if rate > MAX_RATE or total > MAX_REQUESTS:
        await query.edit_message_text("⛔ Test limiti aşılır.")
        return ConversationHandler.END

    context.user_data["stress_rate"] = rate
    target = context.user_data["stress_target"]

    keyboard = [[
        InlineKeyboardButton("▶️ START", callback_data="stress_confirm"),
        InlineKeyboardButton("❌ CANCEL", callback_data="stress_cancel"),
    ]]

    await query.edit_message_text(
        "🧪 <b>LOAD TEST HAZIRDIR</b>\n\n"
        f"🌐 Target: <code>{html.escape(target)}</code>\n"
        f"⏱ Müddət: <b>{duration} saniyə</b>\n"
        f"📨 Rate: <b>{rate} req/s</b>\n"
        f"📊 Maksimum: <b>{total} request</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CONFIRM


async def cancel_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ Test ləğv edildi.")
    return ConversationHandler.END


async def run_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global stress_process

    query = update.callback_query
    await query.answer()

    if stress_process is not None:
        await query.edit_message_text("⚠️ Hazırda başqa load test işləyir.")
        return ConversationHandler.END

    target = context.user_data["stress_target"]
    duration = context.user_data["stress_duration"]
    rate = context.user_data["stress_rate"]

    script_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "remotehub_stress_test.js",
    )

    script = f'''import http from "k6/http";

export const options = {{
    scenarios: {{
        remotehub_load: {{
            executor: "constant-arrival-rate",
            rate: {rate},
            timeUnit: "1s",
            duration: "{duration}s",
            preAllocatedVUs: 5,
            maxVUs: 10,
        }},
    }},
}};

export default function () {{
    http.get("{target}", {{
        headers: {{
            "X-RemoteHub-Test": "true"
        }}
    }});
}}
'''

    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)

    await query.edit_message_text(
        "🚀 <b>LOAD TEST BAŞLADI</b>\n\n"
        f"🎯 {html.escape(target)}\n"
        f"⏱ {duration} saniyə\n"
        f"📨 {rate} req/s\n"
        f"📊 Maksimum: {duration * rate} request",
        parse_mode="HTML",
    )

    try:
        stress_process = await asyncio.create_subprocess_exec(
            K6_PATH, "run", script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        stdout, _ = await stress_process.communicate()
        process = stress_process
        stress_process = None
        output = stdout.decode("utf-8", errors="replace")

        lines = [
            line.strip() for line in output.splitlines()
            if any(x in line for x in (
                "http_req_duration",
                "http_req_failed",
                "http_reqs",
                "iterations",
            ))
        ]

        result = (
            "📊 <b>LOAD TEST NƏTİCƏSİ</b>\n\n"
            f"🎯 Target: <code>{html.escape(target)}</code>\n"
            f"⏱ Müddət: {duration}s\n"
            f"📨 Rate: {rate} req/s\n\n"
        )

        result += "\n".join(
            f"<code>{html.escape(line)}</code>" for line in lines
        ) if lines else "✅ Test tamamlandı."

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=result,
            parse_mode="HTML",
        )

    except Exception as e:
        stress_process = None
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ Stress test xətası:\n<code>{html.escape(str(e))}</code>",
            parse_mode="HTML",
        )

    return ConversationHandler.END


async def stop_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global stress_process

    if not authorized(update):
        await update.message.reply_text("⛔ İcazə yoxdur.")
        return

    if stress_process is None:
        await update.message.reply_text("ℹ️ Aktiv load test yoxdur.")
        return

    stress_process.kill()
    await stress_process.wait()
    stress_process = None
    await update.message.reply_text("🛑 <b>Load test dayandırıldı.</b>",
                                     parse_mode="HTML")


def get_stress_handlers():
    conversation = ConversationHandler(
        entry_points=[CommandHandler("stress", stress_start)],
        states={
            SITE: [CallbackQueryHandler(
                choose_site, pattern=r"^stress_(site:|cancel$)"
            )],
            DURATION: [CallbackQueryHandler(
                choose_duration, pattern=r"^stress_(duration:|cancel$)"
            )],
            RATE: [CallbackQueryHandler(
                choose_rate, pattern=r"^stress_(rate:|cancel$)"
            )],
            CONFIRM: [
                CallbackQueryHandler(run_test, pattern=r"^stress_confirm$"),
                CallbackQueryHandler(cancel_test, pattern=r"^stress_cancel$"),
            ],
        },
        fallbacks=[CommandHandler("stress_stop", stop_test)],
        allow_reentry=True,
    )
    return [conversation, CommandHandler("stress_stop", stop_test)]
