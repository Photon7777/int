from __future__ import annotations

import base64
import json
import mimetypes
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parseaddr
from typing import Callable, Iterable, List, Optional

from auth import get_user_gmail_connection, save_user_gmail_connection


class GmailSendError(Exception):
    pass


GMAIL_SEND_SCOPES = (
    "https://www.googleapis.com/auth/gmail.send",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
)

GMAIL_READ_SCOPES = (
    "https://www.googleapis.com/auth/gmail.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
)

GMAIL_CONNECT_SCOPES = (
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
)


@dataclass
class GmailSettings:
    sender_email: str
    client_secret_file: str = ""
    token_file: str = "gmail_token.json"
    token_json: Optional[str] = None
    persist_token: Optional[Callable[[str], None]] = None
    scopes: tuple[str, ...] = GMAIL_SEND_SCOPES


class GmailSender:
    def __init__(self, settings: GmailSettings):
        self.settings = settings

    @classmethod
    def oauth_redirect_uri(cls) -> str:
        return (
            os.getenv("GMAIL_OAUTH_REDIRECT_URI", "").strip()
            or os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "").strip()
            or "http://localhost:8501"
        )

    @classmethod
    def oauth_client_secret_file(cls) -> str:
        client_secret_file = (
            os.getenv("GMAIL_CLIENT_SECRET_FILE", "").strip()
            or os.getenv("GOOGLE_CLIENT_SECRET_FILE", "").strip()
        )
        if not client_secret_file:
            raise GmailSendError(
                "Missing Google OAuth config. Set GMAIL_CLIENT_SECRET_FILE or GOOGLE_CLIENT_SECRET_FILE."
            )
        if not os.path.exists(client_secret_file):
            raise GmailSendError(f"Could not find Google client secret file: {client_secret_file}")
        return client_secret_file

    @classmethod
    def from_env(cls) -> "GmailSender":
        sender_email = os.getenv("GMAIL_SENDER_EMAIL", "").strip()
        client_secret_file = os.getenv("GMAIL_CLIENT_SECRET_FILE", "").strip()
        token_file = os.getenv("GMAIL_TOKEN_FILE", "gmail_token.json").strip() or "gmail_token.json"
        if not sender_email or not client_secret_file:
            raise GmailSendError(
                "Missing Gmail config. Set GMAIL_SENDER_EMAIL and GMAIL_CLIENT_SECRET_FILE."
            )
        return cls(
            GmailSettings(
                sender_email=sender_email,
                client_secret_file=client_secret_file,
                token_file=token_file,
            )
        )

    @classmethod
    def from_user(cls, user_id: str) -> "GmailSender":
        connection = get_user_gmail_connection(user_id, include_token=True)
        if not connection.get("connected"):
            raise GmailSendError(
                "No Gmail account is connected for this user. Open Account settings and connect Gmail first."
            )
        sender_email = (connection.get("gmail_email") or "").strip()
        token_json = connection.get("token_json") or ""
        if not sender_email or not token_json:
            raise GmailSendError(
                "The connected Gmail account is incomplete. Reconnect Gmail from Account settings."
            )

        def persist(updated_token_json: str) -> None:
            save_user_gmail_connection(user_id, sender_email, updated_token_json)

        return cls(
            GmailSettings(
                sender_email=sender_email,
                token_json=token_json,
                persist_token=persist,
            )
        )

    @classmethod
    def begin_user_connect_flow(cls) -> tuple[str, str]:
        try:
            from google_auth_oauthlib.flow import Flow
        except ImportError as exc:
            raise GmailSendError(
                "Missing Gmail OAuth libraries. Install google-auth-oauthlib."
            ) from exc

        client_secret_file = cls.oauth_client_secret_file()
        flow = Flow.from_client_secrets_file(
            client_secret_file,
            scopes=list(GMAIL_CONNECT_SCOPES),
            redirect_uri=cls.oauth_redirect_uri(),
        )
        auth_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        return auth_url, state

    @classmethod
    def complete_user_connect_flow(cls, user_id: str, *, state: str, code: str) -> str:
        try:
            from google_auth_oauthlib.flow import Flow
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise GmailSendError(
                "Missing Gmail OAuth libraries. Install google-api-python-client and google-auth-oauthlib."
            ) from exc

        client_secret_file = cls.oauth_client_secret_file()
        flow = Flow.from_client_secrets_file(
            client_secret_file,
            scopes=list(GMAIL_CONNECT_SCOPES),
            state=state,
            redirect_uri=cls.oauth_redirect_uri(),
        )
        try:
            flow.fetch_token(code=code)
        except Exception as exc:
            raise GmailSendError(f"Could not complete Google OAuth: {exc}") from exc

        creds = flow.credentials
        userinfo_service = build("oauth2", "v2", credentials=creds, cache_discovery=False)
        try:
            profile = userinfo_service.userinfo().get().execute()
        except Exception as exc:
            raise GmailSendError("Google OAuth succeeded, but the Gmail account email could not be read.") from exc

        gmail_email = (profile.get("email") or "").strip()
        if not gmail_email:
            raise GmailSendError("Google OAuth succeeded, but no Gmail email address was returned.")

        save_user_gmail_connection(user_id, gmail_email, creds.to_json())
        return gmail_email

    def _get_service(self, scopes: Optional[Iterable[str]] = None):
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise GmailSendError(
                "Missing Gmail API libraries. Install google-api-python-client, "
                "google-auth-httplib2, google-auth-oauthlib."
            ) from exc

        creds = None
        original_token_json = self.settings.token_json or ""
        requested_scopes = list(scopes or self.settings.scopes)

        if original_token_json:
            creds = Credentials.from_authorized_user_info(
                json.loads(original_token_json),
                requested_scopes,
            )
        elif os.path.exists(self.settings.token_file):
            creds = Credentials.from_authorized_user_file(self.settings.token_file, requested_scopes)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                if self.settings.persist_token:
                    self.settings.persist_token(creds.to_json())
            else:
                if original_token_json:
                    raise GmailSendError(
                        "The connected Gmail account needs to be reconnected. Open Account settings and reconnect Gmail."
                    )
                if not os.path.exists(self.settings.client_secret_file):
                    raise GmailSendError(
                        f"Could not find client secret file: {self.settings.client_secret_file}"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.settings.client_secret_file,
                    requested_scopes,
                )
                creds = flow.run_local_server(port=0)
            if self.settings.persist_token:
                self.settings.persist_token(creds.to_json())
            elif self.settings.token_file:
                with open(self.settings.token_file, "w", encoding="utf-8") as token:
                    token.write(creds.to_json())

        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    @staticmethod
    def _normalized_email(value: str) -> str:
        return (value or "").strip().lower()

    @staticmethod
    def _email_from_header(value: str) -> str:
        _, addr = parseaddr(value or "")
        return GmailSender._normalized_email(addr or value)

    @staticmethod
    def _header_map(message: dict) -> dict[str, str]:
        payload = message.get("payload", {}) or {}
        headers = payload.get("headers", []) or []
        return {
            str(item.get("name", "")).strip().lower(): str(item.get("value", "")).strip()
            for item in headers
            if item.get("name")
        }

    @staticmethod
    def _internal_date_iso(value) -> str:
        try:
            return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).isoformat()
        except Exception:
            return ""

    @staticmethod
    def _read_error_message(exc: Exception) -> str:
        raw = str(exc)
        lower = raw.lower()
        if "insufficient authentication scopes" in lower or "insufficientpermissions" in lower:
            return (
                "This Gmail connection can send email but cannot sync replies yet. "
                "Reconnect Gmail from Account settings to grant inbox-read access."
            )
        return f"Could not sync Gmail replies: {raw}"

    @staticmethod
    def _is_bounce_message(headers: dict[str, str], snippet: str) -> bool:
        from_value = f"{headers.get('from', '')} {headers.get('subject', '')} {snippet}".lower()
        markers = (
            "mailer-daemon",
            "mail delivery subsystem",
            "delivery status notification",
            "undeliverable",
            "delivery has failed",
            "returned mail",
        )
        return any(marker in from_value for marker in markers)

    def get_thread(self, thread_id: str) -> dict:
        if not str(thread_id).strip():
            raise GmailSendError("A Gmail thread ID is required for inbox sync.")

        service = self._get_service(scopes=GMAIL_READ_SCOPES)
        try:
            return service.users().threads().get(
                userId="me",
                id=str(thread_id).strip(),
                format="metadata",
                metadataHeaders=["From", "To", "Subject", "Date"],
            ).execute()
        except Exception as exc:
            raise GmailSendError(self._read_error_message(exc)) from exc

    def get_thread_summary(self, thread_id: str) -> dict:
        thread = self.get_thread(thread_id)
        messages = sorted(
            list(thread.get("messages", []) or []),
            key=lambda item: int(item.get("internalDate") or 0),
        )
        sender_email = self._normalized_email(self.settings.sender_email)

        latest_message = messages[-1] if messages else {}
        latest_headers = self._header_map(latest_message)
        latest_snippet = str(latest_message.get("snippet", "") or "").strip()

        latest_inbound = {}
        latest_inbound_headers = {}
        for message in messages:
            headers = self._header_map(message)
            from_email = self._email_from_header(headers.get("from", ""))
            if from_email and from_email != sender_email:
                latest_inbound = message
                latest_inbound_headers = headers

        active_message = latest_inbound or latest_message
        active_headers = latest_inbound_headers or latest_headers
        active_snippet = str(active_message.get("snippet", "") or "").strip()

        return {
            "thread_id": str(thread.get("id", "") or thread_id),
            "message_count": str(len(messages)),
            "has_inbound_reply": bool(latest_inbound),
            "is_bounce": self._is_bounce_message(active_headers, active_snippet),
            "latest_message_id": str(active_message.get("id", "") or ""),
            "latest_message_at": self._internal_date_iso(active_message.get("internalDate")),
            "latest_message_from": active_headers.get("from", ""),
            "latest_snippet": active_snippet,
        }

    @staticmethod
    def _normalize_recipients(value: str | Iterable[str]) -> List[str]:
        if isinstance(value, str):
            return [x.strip() for x in value.split(",") if x.strip()]
        return [str(x).strip() for x in value if str(x).strip()]

    @staticmethod
    def _attachment_part(
        attachment_bytes: bytes,
        attachment_filename: str,
        attachment_mime_type: Optional[str] = None,
    ) -> MIMEBase:
        mime_type = attachment_mime_type or mimetypes.guess_type(attachment_filename)[0] or "application/octet-stream"
        maintype, subtype = mime_type.split("/", 1) if "/" in mime_type else ("application", "octet-stream")
        part = MIMEBase(maintype, subtype)
        part.set_payload(attachment_bytes)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=attachment_filename)
        return part

    def send_email(
        self,
        *,
        to: str | Iterable[str],
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        cc: Optional[str | Iterable[str]] = None,
        bcc: Optional[str | Iterable[str]] = None,
        reply_to: Optional[str] = None,
        attachment_bytes: Optional[bytes] = None,
        attachment_filename: Optional[str] = None,
        attachment_mime_type: Optional[str] = None,
    ) -> dict:
        service = self._get_service()
        recipients = self._normalize_recipients(to)
        if not recipients:
            raise GmailSendError("At least one recipient email address is required.")

        message = MIMEMultipart("mixed")
        message["To"] = ", ".join(recipients)
        message["From"] = self.settings.sender_email
        message["Subject"] = subject
        if cc:
            message["Cc"] = ", ".join(self._normalize_recipients(cc))
        if bcc:
            message["Bcc"] = ", ".join(self._normalize_recipients(bcc))
        if reply_to:
            message["Reply-To"] = reply_to

        alt_part = MIMEMultipart("alternative")
        alt_part.attach(MIMEText(body_text, "plain", "utf-8"))
        if body_html:
            alt_part.attach(MIMEText(body_html, "html", "utf-8"))
        message.attach(alt_part)

        if attachment_bytes and attachment_filename:
            message.attach(self._attachment_part(attachment_bytes, attachment_filename, attachment_mime_type))

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        return service.users().messages().send(userId="me", body={"raw": raw}).execute()
