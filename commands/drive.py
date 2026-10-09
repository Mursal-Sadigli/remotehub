"""
Google Drive əmrləri: /drive, fayl açma, endirmə
Fayllar diskə yazılmır — birbaşa yaddaşda emal olunur.
"""

import io

from html import escape

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

# ─── Konfiqurasiya ────────────────────────────────────────
ALLOWED_USER_ID = 6426820534


def authorized(update: Update) -> bool:
    return (
        update.effective_user is not None
        and update.effective_user.id == ALLOWED_USER_ID
    )


def get_drive_service():
    creds = Credentials.from_authorized_user_file(
        "token.json",
        ["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds)


# ─── Fayl göstərmə ────────────────────────────────────────
async def show_drive(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    folder_id: str = "root"
):
    if not authorized(update):
        return

    try:
        service = get_drive_service()

        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            pageSize=50,
            fields="files(id, name, mimeType, size)"
        ).execute()

        files = results.get("files", [])
        display_files = files

        if folder_id == "root":
            root_folder_ids = [
                f["id"] for f in files
                if f["mimeType"] == "application/vnd.google-apps.folder"
            ]
            if root_folder_ids:
                child_query = " or ".join(
                    f"'{rid}' in parents" for rid in root_folder_ids
                )
                child_results = service.files().list(
                    q=f"({child_query}) and trashed = false",
                    pageSize=50,
                    fields="files(id, name, mimeType, size)"
                ).execute()
                display_files = files + child_results.get("files", [])

        keyboard = []
        if folder_id != "root":
            keyboard.append([
                InlineKeyboardButton("⬅️ Geri", callback_data="drive_back")
            ])

        for file in display_files:
            if file["mimeType"] == "application/vnd.google-apps.folder":
                keyboard.append([
                    InlineKeyboardButton(
                        f"📁 {file['name']}",
                        callback_data=f"folder:{file['id']}"
                    )
                ])
            else:
                keyboard.append([
                    InlineKeyboardButton(
                        f"📄 {file['name']}",
                        callback_data=f"file:{file['id']}"
                    )
                ])

        if not display_files:
            text = "☁️ <b>Google Drive</b>\n\n📭 Bu qovluq boşdur."
        else:
            text = "☁️ <b>Google Drive</b>\n\n"
            for file in display_files:
                icon = "📁" if file["mimeType"] == "application/vnd.google-apps.folder" else "📄"
                text += f"{icon} {escape(file['name'])}\n"

        markup = InlineKeyboardMarkup(keyboard)

        if update.callback_query:
            await update.callback_query.edit_message_text(
                text, parse_mode="HTML", reply_markup=markup
            )
        else:
            await update.message.reply_text(
                text, parse_mode="HTML", reply_markup=markup
            )

    except Exception as e:
        msg = f"❌ Google Drive xətası:\n{escape(str(e))}"
        if update.callback_query:
            await update.callback_query.edit_message_text(msg, parse_mode="HTML")
        else:
            await update.message.reply_text(msg, parse_mode="HTML")


# ─── Əmrlər ───────────────────────────────────────────────
async def drive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_drive(update, context, "root")


# ─── Fayl endirmə və göndərmə (yaddaşda) ──────────────────
async def send_file_from_drive(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    file_id: str
):
    query = update.callback_query
    await query.edit_message_text("⏳ Fayl endirilir...")

    try:
        service = get_drive_service()

        meta = service.files().get(
            fileId=file_id,
            fields="name, mimeType, size"
        ).execute()

        file_name = meta["name"]
        mime_type = meta["mimeType"]

        # ─── Hansı növü necə ixrac edək ────────────────────
        # (request, göndəriləcək_ad, mime)
        if mime_type == "application/vnd.google-apps.document":
            request = service.files().export_media(
                fileId=file_id, mimeType="application/pdf"
            )
            send_name = file_name + ".pdf"
            send_mime = "application/pdf"

        elif mime_type == "application/vnd.google-apps.spreadsheet":
            request = service.files().export_media(
                fileId=file_id,
                mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            send_name = file_name + ".xlsx"
            send_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        elif mime_type == "application/vnd.google-apps.presentation":
            request = service.files().export_media(
                fileId=file_id, mimeType="application/pdf"
            )
            send_name = file_name + ".pdf"
            send_mime = "application/pdf"

        elif mime_type == "application/vnd.google-apps.drawing":
            request = service.files().export_media(
                fileId=file_id, mimeType="image/png"
            )
            send_name = file_name + ".png"
            send_mime = "image/png"

        else:
            request = service.files().get_media(fileId=file_id)
            send_name = file_name
            send_mime = mime_type

        # ─── Yaddaşa endir ─────────────────────────────────
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)

        done = False
        while not done:
            status, done = downloader.next_chunk()

        buffer.seek(0)

        # ─── Telegram-a göndər ─────────────────────────────
        if send_mime.startswith("image/"):
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=buffer,
                filename=send_name,
                caption=f"🖼️ {escape(file_name)}",
                parse_mode="HTML"
            )
        else:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=buffer,
                filename=send_name,
                caption=f"📄 {escape(file_name)}",
                parse_mode="HTML"
            )

        await query.delete_message()

    except Exception as e:
        await query.edit_message_text(
            f"❌ Fayl açıla bilmədi:\n<code>{escape(str(e))}</code>",
            parse_mode="HTML"
        )


# ─── Callback ─────────────────────────────────────────────
async def drive_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if not authorized(update):
        await query.answer("⛔ İcazə yoxdur.")
        return

    await query.answer()
    data = query.data

    if data.startswith("folder:"):
        folder_id = data.split(":", 1)[1]
        context.user_data["current_folder"] = folder_id
        await show_drive(update, context, folder_id)

    elif data.startswith("file:"):
        file_id = data.split(":", 1)[1]
        await send_file_from_drive(update, context, file_id)

    elif data == "drive_back":
        await show_drive(update, context, "root")


# ─── Handler-ləri qaytar ──────────────────────────────────
def get_drive_handlers():
    from telegram.ext import CommandHandler, CallbackQueryHandler

    return [
        CommandHandler("drive", drive),
        CallbackQueryHandler(
            drive_callback,
            pattern=r"^(folder:|file:|drive_back)"
        ),
    ]