# 📄 Telegram Document Manager

ระบบรับเอกสารผ่าน Telegram → จัดเก็บ Google Drive → จำแนกหมวดหมู่ด้วย AI → สร้าง Report อัตโนมัติ

## สถาปัตยกรรม

```
Telegram Bot ──► FastAPI Server ──► Google Drive (จัดเก็บตามหมวดหมู่)
Web Upload  ──►       │          ──► Claude AI (จำแนกเอกสาร)
                      │          ──► SQLite (Metadata)
                      ▼
              Report Generator
              ├── Google Sheets
              ├── Web Dashboard
              ├── Telegram Message
              └── Email
```

## ขั้นตอนการติดตั้ง

### 1. สร้าง Telegram Bot

1. คุยกับ [@BotFather](https://t.me/BotFather) บน Telegram
2. ส่ง `/newbot` → ตั้งชื่อ → ได้ **Bot Token**
3. ใส่ Token ใน `.env` → `TELEGRAM_BOT_TOKEN`

### 2. ตั้งค่า Google Cloud

1. ไปที่ [Google Cloud Console](https://console.cloud.google.com/)
2. สร้าง Project ใหม่
3. เปิด **Google Drive API** และ **Google Sheets API**
4. สร้าง **Service Account** → ดาวน์โหลด JSON Key → ตั้งชื่อเป็น `credentials.json`
5. สร้างโฟลเดอร์บน Google Drive → แชร์ให้ Service Account Email
6. คัดลอก Folder ID ใส่ `.env` → `GOOGLE_DRIVE_ROOT_FOLDER_ID`

### 3. ตั้งค่า Anthropic API

1. ไปที่ [Anthropic Console](https://console.anthropic.com/)
2. สร้าง API Key
3. ใส่ใน `.env` → `ANTHROPIC_API_KEY`

### 4. ตั้งค่า Email (ถ้าต้องการ)

1. ใช้ Gmail → เปิด App Password
2. ใส่ข้อมูลใน `.env` → `SMTP_*`

### 5. ติดตั้งและรัน

```bash
# Clone & setup
cd telegram-doc-manager
cp .env.example .env
# แก้ไข .env ใส่ค่าต่างๆ

# ติดตั้ง dependencies
pip install -r requirements.txt

# รัน server
python main.py

# ตั้งค่า Webhook (รันครั้งเดียว)
python setup_webhook.py
```

### 6. Deploy (แนะนำ)

```bash
# Docker
docker build -t doc-manager .
docker run -d -p 8000:8000 --env-file .env doc-manager

# หรือใช้ Railway / Render / VPS
```

## การใช้งาน

### Telegram Bot Commands

| คำสั่ง | คำอธิบาย |
|--------|----------|
| `/start` | เริ่มต้นใช้งาน |
| `/report_daily` | ดูรายงานประจำวัน |
| `/report_weekly` | ดูรายงานประจำสัปดาห์ |
| `/categories` | ดูหมวดหมู่ทั้งหมด |
| `/status` | ดูสถานะระบบ |

### Web Dashboard

เข้า `http://your-domain:8000` เพื่อ:
- ดู Dashboard สถิติ
- อัพโหลดไฟล์ผ่านเว็บ
- ดูรายการเอกสารทั้งหมด
- กรองตามหมวดหมู่/แหล่งที่มา
- ดาวน์โหลด Report

### API Endpoints

| Method | Path | คำอธิบาย |
|--------|------|----------|
| POST | `/webhook/telegram` | Telegram Webhook |
| POST | `/api/upload` | อัพโหลดไฟล์ |
| GET | `/api/documents` | รายการเอกสาร |
| GET | `/api/stats` | สถิติรวม |
| GET | `/api/report/{daily\|weekly}` | ข้อมูล Report |

## โครงสร้างโปรเจกต์

```
telegram-doc-manager/
├── main.py              # FastAPI app หลัก + scheduler
├── setup_webhook.py     # ตั้งค่า Telegram webhook
├── requirements.txt     # Python dependencies
├── Dockerfile           # Docker containerization
├── .env.example         # ตัวอย่างค่า config
├── app/
│   ├── config.py        # ค่า settings ทั้งหมด
│   ├── database.py      # SQLAlchemy models + DB
│   ├── telegram_bot.py  # Telegram bot handler
│   ├── google_drive.py  # Google Drive upload/manage
│   ├── classifier.py    # AI document classification
│   └── reports.py       # Report generation
└── templates/
    └── dashboard.html   # Web dashboard UI
```

## หมวดหมู่เอกสาร (ปรับแก้ได้ใน config.py)

- ใบเสร็จ/ใบแจ้งหนี้
- สัญญา/ข้อตกลง
- รายงาน/บันทึก
- ใบสั่งซื้อ/PO
- เอกสารภาษี
- จดหมาย/หนังสือ
- ข้อมูลตาราง/สถิติ
- รูปภาพ/หลักฐาน
- อื่นๆ
