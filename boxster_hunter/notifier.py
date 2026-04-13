"""Notification dispatch. Generic, target-aware.

Maps a scored Listing to the right channels:

  GOLD (90+):    Email + Slack + Notion + SMS
  STRONG (70+):  Email + Slack + Notion + SMS
  REVIEW (50+):  Notion only
  MARGINAL (<50): nothing (still recorded in SQLite)

A single ``Notifier`` instance is bound to one ``TargetConfig`` and reads the
target's ``slack_webhook_env`` to find its destination webhook. Email + SMS
share globally-named env vars across targets (one mailbox, one phone number)
since users typically don't want a different inbox per car. If you do want
that, swap ``ALERT_EMAIL`` / ``TWILIO_*`` for per-target env var names on the
target's TargetConfig.

All channels are env-var gated; missing creds → log-only no-op so the rest of
the pipeline still works.
"""

from __future__ import annotations

import logging
import os

import requests

from boxster_hunter.models import Listing
from boxster_hunter.targets.base import TargetConfig

log = logging.getLogger("boxster.notify")

GOLD_TIER = "🏆 GOLD"
STRONG_TIER = "🥇 STRONG"
REVIEW_TIER = "🥈 REVIEW"


class Notifier:
    def __init__(
        self,
        target: TargetConfig,
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
        self.target = target
        self.slack_webhook = slack_webhook or os.environ.get(target.slack_webhook_env)
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
        """Send notifications appropriate to the listing's tier."""
        tier = listing.tier
        results = {"slack": False, "email": False, "sms": False}

        if tier in (GOLD_TIER, STRONG_TIER):
            results["slack"] = self.send_slack(listing)
            results["email"] = self.send_email(listing)
            results["sms"] = self.send_sms(listing)

        return results

    # ---------- Slack ----------

    def send_slack(self, listing: Listing) -> bool:
        text = format_slack_message(listing, self.target)
        if not self.slack_webhook:
            log.info("[dry-run] %s Slack: %s", self.target.target_id, text)
            return True
        resp = self.session.post(self.slack_webhook, json={"text": text}, timeout=10)
        if not resp.ok:
            log.error("Slack webhook failed %s: %s", resp.status_code, resp.text)
            return False
        return True

    # ---------- Email (SendGrid) ----------

    def send_email(self, listing: Listing) -> bool:
        subject, body = format_email(listing, self.target)
        if not (self.sendgrid_api_key and self.alert_email):
            log.info("[dry-run] %s Email to %s: %s", self.target.target_id, self.alert_email, subject)
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
        body = (
            f"{listing.tier} {self.target.emoji} {listing.title} "
            f"(score {listing.score}) {listing.url_str}"
        )
        if not (self.twilio_sid and self.twilio_token and self.twilio_from and self.twilio_to):
            log.info("[dry-run] %s SMS to %s: %s", self.target.target_id, self.twilio_to, body)
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


def format_slack_message(listing: Listing, target: TargetConfig | None = None) -> str:
    prefix = f"{target.emoji} " if target else ""
    parts = [
        f"*{listing.tier}* — {prefix}{listing.title}",
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


def format_email(listing: Listing, target: TargetConfig | None = None) -> tuple[str, str]:
    subject_prefix = f"{target.emoji} " if target else ""
    subject = f"[{listing.tier}] {subject_prefix}{listing.title} — score {listing.score}"
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
