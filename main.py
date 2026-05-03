import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request, Depends, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import init_db, async_session, Document
from app.telegram_bot import process_update
from app.reports import (
    generate_report_data,
    send_email_report,
    update_google_sheet,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def scheduled_daily_report():
    """Run daily report tasks."""
    logger.info("Running scheduled daily report...")
    try:
        await update_google_sheet("daily")
        await send_email_report("daily")
    except Exception as e:
        logger.error(f"Daily report error: {e}", exc_info=True)


async def scheduled_weekly_report():
    """Run weekly report tasks."""
    logger.info("Running scheduled weekly report...")
    try:
        await update_google_sheet("weekly")
        await send_email_report("weekly")
    except Exception as e:
        logger.error(f"Weekly report error: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    logger.info("Database initialized")

    # Schedule reports
    scheduler.add_job(
        scheduled_daily_report,
        "cron",
        hour=settings.DAILY_REPORT_HOUR,
        minute=0,
        id="daily_report",
    )
    scheduler.add_job(
        scheduled_weekly_report,
        "cron",
        day_of_week=settings.WEEKLY_REPORT_DAY[:3].lower(),
        hour=settings.WEEKLY_REPORT_HOUR,
        minute=0,
        id="weekly_report",
    )
    scheduler.start()
    logger.info("Scheduler started")

    yield

    # Shutdown
    scheduler.shutdown()


app = FastAPI(
    title="Telegram Document Manager",
    description="รับเอกสารจาก Telegram → จัดเก็บ Google Drive → จำแนก AI → สร้าง Report",
    version="1.0.0",
    lifespan=lifespan,
)

templates = Jinja2Templates(directory="templates")


# ======== Telegram Webhook ========

@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """Receive updates from Telegram Bot."""
    update = await request.json()
    logger.info(f"Telegram update received: {update.get('update_id')}")
    try:
        await process_update(update)
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
    return JSONResponse({"ok": True})


# ======== Web Upload ========

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    sender_name: str = Form(default="Web Upload"),
    notes: str = Form(default=""),
):
    """Upload a file via the web dashboard."""
    from app.classifier import classify_document
    from app.google_drive import gdrive_service
    import json

    file_bytes = await file.read()
    filename = file.filename or "unknown"
    mime_type = file.content_type or "application/octet-stream"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "unknown"

    # Classify
    classification = await classify_document(file_bytes, filename, ext, mime_type)
    category = classification.get("category", "อื่นๆ")

    # Upload to Drive
    drive_result = await gdrive_service.upload_file(file_bytes, filename, mime_type, category)

    # Save to DB
    async with async_session() as session:
        doc = Document(
            original_filename=filename,
            file_type=ext,
            file_size=len(file_bytes),
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
            source="web",
            notes=notes,
        )
        session.add(doc)
        await session.commit()

    return JSONResponse({
        "success": True,
        "filename": filename,
        "category": category,
        "summary": classification.get("summary", ""),
        "gdrive_url": drive_result["url"],
    })


# ======== API Endpoints ========

@app.get("/api/documents")
async def list_documents(
    category: str = None,
    source: str = None,
    limit: int = 50,
    offset: int = 0,
):
    """List documents with optional filtering."""
    async with async_session() as session:
        query = select(Document).order_by(Document.created_at.desc())
        if category:
            query = query.where(Document.category == category)
        if source:
            query = query.where(Document.source == source)
        query = query.limit(limit).offset(offset)
        result = await session.execute(query)
        docs = result.scalars().all()

    return [
        {
            "id": d.id,
            "filename": d.original_filename,
            "file_type": d.file_type,
            "category": d.category,
            "subcategory": d.subcategory,
            "summary": d.ai_summary,
            "confidence": d.ai_confidence,
            "tags": d.tags,
            "sender": d.sender_name,
            "source": d.source,
            "gdrive_url": d.gdrive_url,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in docs
    ]


@app.get("/api/stats")
async def get_stats():
    """Get overall statistics for the dashboard."""
    async with async_session() as session:
        # Total docs
        total = (await session.execute(select(func.count(Document.id)))).scalar() or 0

        # Today's docs
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_count = (
            await session.execute(
                select(func.count(Document.id)).where(Document.created_at >= today)
            )
        ).scalar() or 0

        # By category
        cat_result = await session.execute(
            select(Document.category, func.count(Document.id)).group_by(Document.category)
        )
        by_category = dict(cat_result.all())

        # By source
        src_result = await session.execute(
            select(Document.source, func.count(Document.id)).group_by(Document.source)
        )
        by_source = dict(src_result.all())

        # Recent 10
        recent = await session.execute(
            select(Document).order_by(Document.created_at.desc()).limit(10)
        )
        recent_docs = [
            {
                "id": d.id,
                "filename": d.original_filename,
                "category": d.category,
                "source": d.source,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in recent.scalars().all()
        ]

    return {
        "total_documents": total,
        "today_documents": today_count,
        "by_category": by_category,
        "by_source": by_source,
        "recent_documents": recent_docs,
    }


@app.get("/api/report/{period}")
async def api_report(period: str):
    """Get report data as JSON."""
    if period not in ("daily", "weekly"):
        return JSONResponse({"error": "Period must be 'daily' or 'weekly'"}, 400)
    return await generate_report_data(period)


# ======== Dashboard ========

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Serve the web dashboard."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


# ======== Run ========

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=True)
