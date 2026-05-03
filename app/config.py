import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_WEBHOOK_URL: str = os.getenv("TELEGRAM_WEBHOOK_URL", "")

    # Google OAuth 2.0
    GOOGLE_OAUTH_CLIENT_ID: str = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
    GOOGLE_OAUTH_CLIENT_SECRET: str = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
    GOOGLE_OAUTH_REFRESH_TOKEN: str = os.getenv("GOOGLE_OAUTH_REFRESH_TOKEN", "")
    GOOGLE_CREDENTIALS_FILE: str = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
    GOOGLE_DRIVE_ROOT_FOLDER_ID: str = os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_ID", "")
    GOOGLE_SHEETS_ID: str = os.getenv("GOOGLE_SHEETS_ID", "")

    # AI (Ollama Cloud)
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "https://api.ollama.com")
    OLLAMA_API_KEY: str = os.getenv("OLLAMA_API_KEY", "")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "gemma3")
    OLLAMA_VISION_MODEL: str = os.getenv("OLLAMA_VISION_MODEL", "gemma3")

    # Email
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    REPORT_EMAIL_RECIPIENTS: list[str] = [
        e.strip() for e in os.getenv("REPORT_EMAIL_RECIPIENTS", "").split(",") if e.strip()
    ]

    # App
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./documents.db")
    DAILY_REPORT_HOUR: int = int(os.getenv("DAILY_REPORT_HOUR", "8"))
    WEEKLY_REPORT_DAY: str = os.getenv("WEEKLY_REPORT_DAY", "monday")
    WEEKLY_REPORT_HOUR: int = int(os.getenv("WEEKLY_REPORT_HOUR", "9"))

    # Document categories
    CATEGORIES: list[str] = [
        "ใบเสร็จ/ใบแจ้งหนี้",
        "สัญญา/ข้อตกลง",
        "รายงาน/บันทึก",
        "ใบสั่งซื้อ/PO",
        "เอกสารภาษี",
        "จดหมาย/หนังสือ",
        "ข้อมูลตาราง/สถิติ",
        "รูปภาพ/หลักฐาน",
        "อื่นๆ",
    ]


settings = Settings()
