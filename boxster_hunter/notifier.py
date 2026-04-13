"""Notification dispatch.

Maps a scored Listing to the right channels:

  GOLD (90+):    Email + Slack + Notion + SMS
  STRONG (70+):  Email + Slack + Notion + SMS
  REVIEW (50+):  Notion only
  MARGINAL (<50): nothing (still recorded in SQLite)

The SMS threshold was lowered from GOLD-only to STRONG+ so real candidates
flagged by the search-index scrapers actually generate alerts. The original
spec scoped SMS to GOLD on the assumption that listings would routinely score
90+; in practice search-index scoring caps out lower without a detail-fetch
pass, so STRONG-tier alerts are the right grain.

All channels are env-var gated; missing creds → log-only no-op so the rest of
the pipeline still works.
"""

from __future__ import annotations

import logging
import os

import requests

from boxster_hunter.models import Listing

log = logging.getLogger("boxster.notify")

GOLD_TIER = "🏆 GOLD"
STRONG_TIER = "🥇 STRONG"
REVIEW_TIER = "🥈 REVIEW"


class Notifier:
    def __init__(
        self,
        slack_webhook: str | None = None,
        sendgrid_api_key: str | None = None,
        alert_email: str | None = None,
        alert_from_email: str | None = None,
        twilio_sid: str | None = None,
        twilio_token: str | None = None,
        twilio_from: str | None = None,
        twilio_to: str | None = None,
        session: requests.Session | None = None,
    ):
        self.slack_webhook = slack_webhook or os.environ.get("SLACK_WEBHOOK_URL")
        self.sendgrid_api_key = sendgrid_api_key or os.environ.get("SENDGRID_API_KEY")
        self.alert_email = alert_email or os.environ.get("ALERT_EMAIL")
        self.alert_from_email = (
            alert_from_email or os.environ.get("ALERT_FROM_EMAIL") or "hunter@boxster-hunter.local"
        )
        self.twilio_sid = twilio_sid or os.environ.get("TWILIO_ACCOUNT_SID")
        self.twilio_token = twilio_token or os.environ.get("TWILIO_AUTH_TOKEN")
        self.twilio_from = twilio_from or os.environ.get("TWILIO_FROM_NUMBER")
        self.twilio_to = twilio_to or os.environ.get("TWILIO_TO_NUMBER")
        self.session = session or requests.Session()

    def dispatch(self, listing: Listing) -> dict[str, bool]:
        """Send notifications appropriate to the listing's tier.

        Returns a dict of {channel: sent_or_dryrun} for testability.
        """
        tier = listing.tier
        results = {"slack": False, "email": False, "sms": False}

        if tier in (GOLD_TIER, STRONG_TIER):
            results["slack"] = self.send_slack(listing)
            results["email"] = self.send_email(listing)
            results["sms"] = self.send_sms(listing)

        return results

    # ---------- Slack ----------

    def send_slack(self, listing: Listing) -> bool:
        text = format_slack_message(listing)
        if not self.slack_webhook:
            log.info("[dry-run] Slack: %s", text)
            return True
        resp = self.session.post(self.slack_webhook, json={"text": text}, timeout=10)
        if not resp.ok:
            log.error("Slack webhook failed %s: %s", resp.status_code, resp.text)
            return False
        return True

    # ---------- Email (SendGrid) ----------

    def send_email(self, listing: Listing) -> bool:
        subject, body = format_email(listing)
        if not (self.sendgrid_api_key and self.alert_email):
            log.info("[dry-run] Email to %s: %s", self.alert_email, subject)
            return True
        payload = {
            "personalizations": [{"to": [{"email": self.alert_email}], "subject": subject}],
            "from": {"email": self.alert_from_email},
            "content": [{"type": "text/plain", "value": body}],
        }
        resp = self.session.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {self.sendgrid_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )
        if not resp.ok:
            log.error("SendGrid failed %s: %s", resp.status_code, resp.text)
            return False
        return True

    # ---------- SMS (Twilio) ----------

    def send_sms(self, listing: Listing) -> bool:
        body = f"🏆 GOLD Boxster: {listing.title} (score {listing.score}) {listing.url_str}"
        if not (self.twilio_sid and self.twilio_token and self.twilio_from and self.twilio_to):
            log.info("[dry-run] SMS to %s: %s", self.twilio_to, body)
            return True
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.twilio_sid}/Messages.json"
        resp = self.session.post(
            url,
            auth=(self.twilio_sid, self.twilio_token),
            data={"From": self.twilio_from, "To": self.twilio_to, "Body": body},
            timeout=15,
        )
        if not resp.ok:
            log.error("Twilio failed %s: %s", resp.status_code, resp.text)
            return False
        return True


def format_slack_message(listing: Listing) -> str:
    parts = [
        f"*{listing.tier}* — {listing.title}",
        f"Score: *{listing.score}*  |  Source: {listing.source}",
    ]
    if listing.price:
        parts.append(f"Price: ${listing.price:,}")
    if listing.mileage:
        parts.append(f"Mileage: {listing.mileage:,}")
    if listing.location:
        parts.append(f"Location: {listing.location}")
    parts.append(listing.url_str)
    if listing.flags:
        parts.append("\n".join(f"  • {f}" for f in listing.flags))
    return "\n".join(parts)


def format_email(listing: Listing) -> tuple[str, str]:
    subject = f"[{listing.tier}] {listing.title} — score {listing.score}"
    body_lines = [
        f"{listing.tier} match — score {listing.score}/100",
        "",
        f"Title:    {listing.title}",
        f"URL:      {listing.url_str}",
        f"Source:   {listing.source}",
    ]
    if listing.year:
        body_lines.append(f"Year:     {listing.year}")
    if listing.mileage:
        body_lines.append(f"Mileage:  {listing.mileage:,}")
    if listing.price:
        body_lines.append(f"Price:    ${listing.price:,}")
    if listing.location:
        body_lines.append(f"Location: {listing.location}")
    body_lines.append("")
    body_lines.append("Flags:")
    for f in listing.flags:
        body_lines.append(f"  - {f}")
    body_lines.append("")
    body_lines.append(listing.description)
    return subject, "\n".join(body_lines)
