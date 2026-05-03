import io
import logging
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from app.config import settings

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

MIME_MAP = {
    "image": "image/jpeg",
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "png": "image/png",
    "jpg": "image/jpeg",
}


class GoogleDriveService:
    def __init__(self):
        self._drive = None
        self._sheets = None
        self._folder_cache: dict[str, str] = {}

    def _get_credentials(self) -> Credentials:
        """Get OAuth 2.0 user credentials using refresh token."""
        creds = Credentials(
            token=None,
            refresh_token=settings.GOOGLE_OAUTH_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
            client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
            scopes=SCOPES,
        )
        # Refresh to get a valid access token
        creds.refresh(Request())
        logger.info("OAuth 2.0 credentials refreshed successfully")
        return creds

    @property
    def drive(self):
        if self._drive is None:
            creds = self._get_credentials()
            self._drive = build("drive", "v3", credentials=creds)
        return self._drive

    @property
    def sheets(self):
        if self._sheets is None:
            creds = self._get_credentials()
            self._sheets = build("sheets", "v4", credentials=creds)
        return self._sheets

    async def get_or_create_folder(self, folder_name: str, parent_id: str = None) -> str:
        """Get existing folder or create a new one. Returns folder ID."""
        cache_key = f"{parent_id}:{folder_name}"
        if cache_key in self._folder_cache:
            return self._folder_cache[cache_key]

        parent = parent_id or settings.GOOGLE_DRIVE_ROOT_FOLDER_ID
        query = (
            f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' "
            f"and '{parent}' in parents and trashed=false"
        )
        results = self.drive.files().list(q=query, fields="files(id,name)").execute()
        files = results.get("files", [])

        if files:
            folder_id = files[0]["id"]
        else:
            metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent],
            }
            folder = self.drive.files().create(body=metadata, fields="id").execute()
            folder_id = folder["id"]

        self._folder_cache[cache_key] = folder_id
        return folder_id

    async def upload_file(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: str,
        category: str = "อื่นๆ",
    ) -> dict:
        """Upload file to Google Drive organized by category folder."""
        # Create category folder structure: Root > Category > YYYY-MM
        from datetime import datetime
        date_folder = datetime.now().strftime("%Y-%m")

        category_folder_id = await self.get_or_create_folder(
            category, settings.GOOGLE_DRIVE_ROOT_FOLDER_ID
        )
        date_folder_id = await self.get_or_create_folder(date_folder, category_folder_id)

        # Upload file
        file_metadata = {
            "name": filename,
            "parents": [date_folder_id],
        }
        media = MediaIoBaseUpload(
            io.BytesIO(file_bytes), mimetype=mime_type, resumable=True
        )
        uploaded = (
            self.drive.files()
            .create(body=file_metadata, media_body=media, fields="id,webViewLink")
            .execute()
        )

        logger.info(f"Uploaded {filename} to Drive folder: {category}/{date_folder}")
        return {
            "file_id": uploaded["id"],
            "folder_id": date_folder_id,
            "url": uploaded.get("webViewLink", ""),
        }

    async def append_to_sheet(self, sheet_id: str, values: list[list]) -> None:
        """Append rows to a Google Sheet for reporting."""
        body = {"values": values}
        self.sheets.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range="Sheet1!A1",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body,
        ).execute()
        logger.info(f"Appended {len(values)} rows to Google Sheet")


gdrive_service = GoogleDriveService()
