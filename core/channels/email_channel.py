"""Email integration for JARVIS (SMTP send + IMAP polling)."""

from __future__ import annotations

import email
import imaplib
import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, Optional

# Direct script execution breaks package-relative imports.
if __name__ == "__main__" and (not __package__):
    raise SystemExit("Run this module as: python -m core.channels.email_channel")

from ..channel_manager import BaseChannel


class EmailChannel(BaseChannel):
    """Email channel using IMAP for receive and SMTP for send."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__("email", config)
        self.imap_server = config.get("imap_server")
        self.smtp_server = config.get("smtp_server")
        self.email_address = config.get("email")
        self.password = config.get("password")
        self.imap_port = int(config.get("imap_port", 993))
        self.smtp_port = int(config.get("smtp_port", 587))
        self.check_interval = int(config.get("check_interval", 60))
        self._stop_event = threading.Event()
        self._checker_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        super().start()
        self._stop_event.clear()
        self._checker_thread = threading.Thread(target=self._check_emails, daemon=True)
        self._checker_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        super().stop()
        if self._checker_thread and self._checker_thread.is_alive():
            self._checker_thread.join(timeout=2)

    def send(self, message: str, recipient: Optional[str] = None, subject: str = "Message from JARVIS") -> bool:
        if not recipient:
            self.logger.error("No recipient specified")
            return False
        if not self.smtp_server or not self.email_address or not self.password:
            self.logger.error("SMTP credentials/config are missing")
            return False

        try:
            msg = MIMEMultipart()
            msg["From"] = self.email_address
            msg["To"] = recipient
            msg["Subject"] = subject
            msg.attach(MIMEText(message, "plain"))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_address, self.password)
                server.send_message(msg)

            self.logger.info("Email sent to %s", recipient)
            return True
        except Exception as exc:
            self.logger.error("Email send failed: %s", exc)
            return False

    def check_inbox_once(self) -> Dict[str, Any]:
        """Run one IMAP poll and return a summary for interactive commands."""
        processed = 0
        errors = []

        try:
            processed = self._poll_imap_once()
        except Exception as exc:
            errors.append(str(exc))

        return {
            "processed": processed,
            "errors": errors,
        }

    def _check_emails(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._poll_imap_once()
            except Exception as exc:
                self.logger.error("Email check failed: %s", exc)
            self._stop_event.wait(self.check_interval)

    def _poll_imap_once(self) -> int:
        if not self.imap_server or not self.email_address or not self.password:
            self.logger.error("IMAP credentials/config are missing")
            return 0

        processed = 0
        with imaplib.IMAP4_SSL(self.imap_server, self.imap_port) as mail:
            mail.login(self.email_address, self.password)
            mail.select("inbox")
            status, message_ids = mail.search(None, "UNSEEN")
            if status != "OK":
                return 0

            for msg_id in message_ids[0].split():
                status, msg_data = mail.fetch(msg_id, "(RFC822)")
                if status != "OK" or not msg_data or msg_data[0] is None:
                    continue

                email_body = msg_data[0][1]
                email_message = email.message_from_bytes(email_body)

                subject = str(email_message.get("subject", "(no subject)"))
                sender = email.utils.parseaddr(str(email_message.get("from", "")))[1]
                body = self._extract_body(email_message)

                self.receive(
                    {
                        "text": f"Subject: {subject}\n\n{body}",
                        "sender": sender,
                        "recipient": self.email_address,
                        "subject": subject,
                        "message_id": msg_id.decode(errors="ignore"),
                    }
                )
                processed += 1

        return processed

    def _extract_body(self, email_message: email.message.Message) -> str:
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() != "text/plain":
                    continue
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                charset = part.get_content_charset() or "utf-8"
                try:
                    return payload.decode(charset, errors="replace")
                except Exception:
                    return payload.decode(errors="replace")
            return ""

        payload = email_message.get_payload(decode=True)
        if payload is None:
            return str(email_message.get_payload() or "")

        charset = email_message.get_content_charset() or "utf-8"
        try:
            return payload.decode(charset, errors="replace")
        except Exception:
            return payload.decode(errors="replace")
