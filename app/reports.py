import logging
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import aiosmtplib
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import Document, async_session
from app.google_drive import gdrive_service

logger = logging.getLogger(__name__)


async def get_documents_in_range(start: datetime, end: datetime) -> list[Document]:
    """Fetch documents created within a date range."""
    async with async_session() as session:
        result = await session.execute(
            select(Document)
            .where(and_(Document.created_at >= start, Document.created_at < end))
            .order_by(Document.created_at.desc())
        )
        return list(result.scalars().all())


async def get_category_stats(start: datetime, end: datetime) -> dict:
    """Get document count grouped by category."""
    async with async_session() as session:
        result = await session.execute(
            select(Document.category, func.count(Document.id))
            .where(and_(Document.created_at >= start, Document.created_at < end))
            .group_by(Document.category)
        )
        return dict(result.all())


async def generate_report_data(period: str = "daily") -> dict:
    """Generate report data for daily or weekly period."""
    now = datetime.utcnow()
    if period == "daily":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        period_label = f"รายงานประจำวัน {start.strftime('%d/%m/%Y')}"
    else:
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)
        period_label = f"รายงานประจำสัปดาห์ {start.strftime('%d/%m')} - {end.strftime('%d/%m/%Y')}"

    docs = await get_documents_in_range(start, end)
    stats = await get_category_stats(start, end)
    total = len(docs)

    return {
        "period": period,
        "period_label": period_label,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "total_documents": total,
        "category_stats": stats,
        "documents": [
            {
                "id": d.id,
                "filename": d.original_filename,
                "category": d.category or "ไม่ระบุ",
                "summary": d.ai_summary or "",
                "sender": d.sender_name or "ไม่ทราบ",
                "source": d.source,
                "gdrive_url": d.gdrive_url or "",
                "created_at": d.created_at.strftime("%d/%m/%Y %H:%M"),
            }
            for d in docs
        ],
    }


def format_telegram_report(data: dict) -> str:
    """Format report data as Telegram message."""
    lines = [
        f"📊 *{data['period_label']}*",
        f"📄 เอกสารทั้งหมด: *{data['total_documents']}* ฉบับ",
        "",
        "📁 *แยกตามหมวดหมู่:*",
    ]
    for cat, count in sorted(data["category_stats"].items(), key=lambda x: -x[1]):
        lines.append(f"  • {cat}: {count} ฉบับ")

    if data["documents"][:5]:
        lines.append("")
        lines.append("📋 *เอกสารล่าสุด:*")
        for doc in data["documents"][:5]:
            link = f"[ดูไฟล์]({doc['gdrive_url']})" if doc["gdrive_url"] else ""
            lines.append(f"  • {doc['filename']} ({doc['category']}) {link}")

    return "\n".join(lines)


async def send_telegram_report(bot, chat_id: int, period: str = "daily"):
    """Send report via Telegram bot."""
    data = await generate_report_data(period)
    message = format_telegram_report(data)
    await bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
    logger.info(f"Sent {period} report to Telegram chat {chat_id}")


async def send_email_report(period: str = "daily"):
    """Send report via email."""
    if not settings.SMTP_USER or not settings.REPORT_EMAIL_RECIPIENTS:
        logger.warning("Email not configured, skipping email report")
        return

    data = await generate_report_data(period)

    # Build HTML email
    rows_html = ""
    for doc in data["documents"]:
        link = f'<a href="{doc["gdrive_url"]}">ดูไฟล์</a>' if doc["gdrive_url"] else "-"
        rows_html += f"""
        <tr>
            <td style="padding:8px;border:1px solid #ddd">{doc['filename']}</td>
            <td style="padding:8px;border:1px solid #ddd">{doc['category']}</td>
            <td style="padding:8px;border:1px solid #ddd">{doc['sender']}</td>
            <td style="padding:8px;border:1px solid #ddd">{doc['created_at']}</td>
            <td style="padding:8px;border:1px solid #ddd">{link}</td>
        </tr>"""

    stats_html = "".join(
        f"<li><strong>{cat}</strong>: {count} ฉบับ</li>"
        for cat, count in sorted(data["category_stats"].items(), key=lambda x: -x[1])
    )

    html = f"""
    <html><body style="font-family:sans-serif;max-width:800px;margin:auto">
    <h2>{data['period_label']}</h2>
    <p>เอกสารทั้งหมด: <strong>{data['total_documents']}</strong> ฉบับ</p>
    <h3>แยกตามหมวดหมู่</h3>
    <ul>{stats_html}</ul>
    <h3>รายการเอกสาร</h3>
    <table style="border-collapse:collapse;width:100%">
        <tr style="background:#f2f2f2">
            <th style="padding:8px;border:1px solid #ddd">ชื่อไฟล์</th>
            <th style="padding:8px;border:1px solid #ddd">หมวดหมู่</th>
            <th style="padding:8px;border:1px solid #ddd">ผู้ส่ง</th>
            <th style="padding:8px;border:1px solid #ddd">วันที่</th>
            <th style="padding:8px;border:1px solid #ddd">ลิงก์</th>
        </tr>
        {rows_html}
    </table>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = data["period_label"]
    msg["From"] = settings.SMTP_USER
    msg["To"] = ", ".join(settings.REPORT_EMAIL_RECIPIENTS)
    msg.attach(MIMEText(html, "html"))

    await aiosmtplib.send(
        msg,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASSWORD,
        start_tls=True,
    )
    logger.info(f"Sent {period} report email to {settings.REPORT_EMAIL_RECIPIENTS}")


async def update_google_sheet(period: str = "daily"):
    """Update Google Sheet with report data."""
    if not settings.GOOGLE_SHEETS_ID:
        logger.warning("Google Sheets ID not configured, skipping")
        return

    data = await generate_report_data(period)

    rows = []
    for doc in data["documents"]:
        rows.append([
            doc["created_at"],
            doc["filename"],
            doc["category"],
            doc["summary"],
            doc["sender"],
            doc["source"],
            doc["gdrive_url"],
        ])

    if rows:
        await gdrive_service.append_to_sheet(settings.GOOGLE_SHEETS_ID, rows)
        logger.info(f"Updated Google Sheet with {len(rows)} rows")
