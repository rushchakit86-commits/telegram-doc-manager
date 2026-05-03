import logging
import aiohttp
from pathlib import Path

from app.config import settings
from app.database import Document, async_session
from app.classifier import classify_document
from app.google_drive import gdrive_service

logger = logging.getLogger(__name__)

TELEGRAM_API = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"
TELEGRAM_FILE_API = f"https://api.telegram.org/file/bot{settings.TELEGRAM_BOT_TOKEN}"

# Map Telegram MIME types to our file types
def detect_file_type(mime_type: str, filename: str) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    mime_map = {
        "application/pdf": "pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "application/msword": "doc",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
        "application/vnd.ms-excel": "xls",
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/gif": "gif",
        "image/webp": "webp",
    }
    return mime_map.get(mime_type, ext or "unknown")


async def download_telegram_file(file_id: str) -> tuple[bytes, str]:
    """Download a file from Telegram servers. Returns (bytes, file_path)."""
    async with aiohttp.ClientSession() as session:
        # Get file path
        async with session.get(f"{TELEGRAM_API}/getFile", params={"file_id": file_id}) as resp:
            data = await resp.json()
            file_path = data["result"]["file_path"]

        # Download file
        async with session.get(f"{TELEGRAM_FILE_API}/{file_path}") as resp:
            file_bytes = await resp.read()

    return file_bytes, file_path


async def send_message(chat_id: int, text: str, parse_mode: str = "Markdown"):
    """Send a text message via Telegram."""
    async with aiohttp.ClientSession() as session:
        await session.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
        )


async def handle_document(update: dict):
    """Process a document/photo received from Telegram."""
    message = update.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    sender = message.get("from", {})
    sender_name = f"{sender.get('first_name', '')} {sender.get('last_name', '')}".strip()
    sender_id = str(sender.get("id", ""))

    # Determine file info
    file_id = None
    filename = "unknown"
    mime_type = "application/octet-stream"
    file_size = 0

    if "document" in message:
        doc = message["document"]
        file_id = doc["file_id"]
        filename = doc.get("file_name", "document")
        mime_type = doc.get("mime_type", "application/octet-stream")
        file_size = doc.get("file_size", 0)
    elif "photo" in message:
        # Get highest resolution photo
        photo = message["photo"][-1]
        file_id = photo["file_id"]
        filename = f"photo_{photo['file_id'][:8]}.jpg"
        mime_type = "image/jpeg"
        file_size = photo.get("file_size", 0)

    if not file_id:
        await send_message(chat_id, "❌ ไม่พบไฟล์ในข้อความ")
        return

    # Acknowledge receipt
    file_type = detect_file_type(mime_type, filename)
    await send_message(chat_id, f"📥 ได้รับไฟล์ *{filename}* กำลังประมวลผล...")

    try:
        # 1. Download from Telegram
        file_bytes, _ = await download_telegram_file(file_id)

        # 2. Classify with AI
        classification = await classify_document(file_bytes, filename, file_type, mime_type)
        category = classification.get("category", "อื่นๆ")

        # 3. Upload to Google Drive
        drive_result = await gdrive_service.upload_file(
            file_bytes, filename, mime_type, category
        )

        # 4. Save to database
        import json
        async with async_session() as session:
            doc_record = Document(
                telegram_file_id=file_id,
                original_filename=filename,
                file_type=file_type,
                file_size=file_size,
                mime_type=mime_type,
                category=category,
                subcategory=classification.get("subcategory", ""),
                ai_summary=classification.get("summary", ""),
                ai_confidence=classification.get("confidence", 0),
                tags=json.dumps(classification.get("tags", []), ensure_ascii=False),
                gdrive_file_id=drive_result["file_id"],
                gdrive_folder_id=drive_result["folder_id"],
                gdrive_url=drive_result["url"],
                sender_name=sender_name,
                sender_id=sender_id,
                source="telegram",
            )
            session.add(doc_record)
            await session.commit()

        # 5. Send confirmation
        confidence_pct = int(classification.get("confidence", 0) * 100)
        tags_str = ", ".join(classification.get("tags", [])[:5])
        reply = (
            f"✅ *บันทึกเรียบร้อย!*\n\n"
            f"📄 ไฟล์: {filename}\n"
            f"📁 หมวดหมู่: *{category}*\n"
            f"📝 สรุป: {classification.get('summary', '-')}\n"
            f"🏷️ Tags: {tags_str}\n"
            f"🎯 ความมั่นใจ: {confidence_pct}%\n"
            f"☁️ [ดูไฟล์บน Drive]({drive_result['url']})"
        )
        await send_message(chat_id, reply)

    except Exception as e:
        logger.error(f"Error processing document: {e}", exc_info=True)
        await send_message(chat_id, f"❌ เกิดข้อผิดพลาด: {str(e)[:200]}")


async def handle_command(update: dict):
    """Handle bot commands like /start, /report, /status."""
    message = update.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")

    if text.startswith("/start"):
        welcome = (
            "👋 *สวัสดีครับ! ผมเป็น Document Manager Bot*\n\n"
            "📎 ส่งไฟล์มาได้เลย (ภาพ, PDF, Word, Excel)\n"
            "ผมจะ:\n"
            "1. จัดเก็บไฟล์บน Google Drive\n"
            "2. จำแนกหมวดหมู่ด้วย AI\n"
            "3. สร้าง Report อัตโนมัติ\n\n"
            "*คำสั่ง:*\n"
            "/report\\_daily - รายงานประจำวัน\n"
            "/report\\_weekly - รายงานประจำสัปดาห์\n"
            "/status - สถานะระบบ\n"
            "/categories - ดูหมวดหมู่ทั้งหมด"
        )
        await send_message(chat_id, welcome)

    elif text.startswith("/report_daily"):
        from app.reports import generate_report_data, format_telegram_report
        data = await generate_report_data("daily")
        report = format_telegram_report(data)
        await send_message(chat_id, report)

    elif text.startswith("/report_weekly"):
        from app.reports import generate_report_data, format_telegram_report
        data = await generate_report_data("weekly")
        report = format_telegram_report(data)
        await send_message(chat_id, report)

    elif text.startswith("/categories"):
        cats = "\n".join(f"  • {c}" for c in settings.CATEGORIES)
        await send_message(chat_id, f"📁 *หมวดหมู่เอกสาร:*\n{cats}")

    elif text.startswith("/status"):
        from app.database import async_session
        from sqlalchemy import select, func
        async with async_session() as session:
            result = await session.execute(select(func.count(Document.id)))
            total = result.scalar() or 0
        await send_message(chat_id, f"✅ ระบบทำงานปกติ\n📄 เอกสารทั้งหมด: *{total}* ฉบับ")

    else:
        await send_message(chat_id, "❓ ไม่รู้จักคำสั่งนี้ พิมพ์ /start เพื่อดูวิธีใช้")


async def process_update(update: dict):
    """Main entry point for processing Telegram updates."""
    message = update.get("message", {})

    if not message:
        return

    # Check if it's a command
    if "text" in message and message["text"].startswith("/"):
        await handle_command(update)
    elif "document" in message or "photo" in message:
        await handle_document(update)
    else:
        chat_id = message.get("chat", {}).get("id")
        if chat_id:
            await send_message(
                chat_id,
                "📎 ส่งไฟล์ (ภาพ/PDF/Word/Excel) มาให้ผมได้เลยครับ!\nหรือพิมพ์ /start เพื่อดูวิธีใช้",
            )
