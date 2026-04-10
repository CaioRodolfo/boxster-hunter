"""Notifier dispatch tests."""

import responses

from boxster_hunter.notifier import Notifier, format_email, format_slack_message
from boxster_hunter.scoring import score_listing
from tests.conftest import make_listing


def _gold():
    return score_listing(
        make_listing(
            title="2004 Boxster S — Lagoon Green",
            description="6-speed manual, IMS Solution",
            mileage=47500,
        )
    )


def _strong():
    return score_listing(
        make_listing(
            title="2003 Boxster S — Guards Red",
            description="6-speed manual, IMS bearing replaced",
            year=2003,
        )
    )


def _review():
    return score_listing(
        make_listing(
            title="2004 Boxster S 3.2L",
            description="6-speed manual, IMS bearing replaced",
        )
    )


def _marginal():
    return score_listing(
        make_listing(
            title="2004 Boxster S",
            description="3.2L, runs and drives.",
        )
    )


def test_format_slack_includes_url_and_score():
    msg = format_slack_message(_gold())
    assert "🏆 GOLD" in msg
    assert "Score:" in msg
    assert "https://" in msg


def test_format_email_returns_subject_and_body():
    listing = _gold()
    subject, body = format_email(listing)
    assert "GOLD" in subject
    assert "score" in subject.lower()
    assert "Mileage:" in body
    assert listing.url_str in body


def test_dispatch_gold_hits_all_channels(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    n = Notifier()
    results = n.dispatch(_gold())
    assert results == {"slack": True, "email": True, "sms": True}


def test_dispatch_strong_no_sms(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
    n = Notifier()
    results = n.dispatch(_strong())
    assert results["slack"] is True
    assert results["email"] is True
    assert results["sms"] is False


def test_dispatch_review_silent(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    n = Notifier()
    results = n.dispatch(_review())
    assert results == {"slack": False, "email": False, "sms": False}


def test_dispatch_marginal_silent(monkeypatch):
    n = Notifier()
    results = n.dispatch(_marginal())
    assert results == {"slack": False, "email": False, "sms": False}


@responses.activate
def test_send_slack_posts_to_webhook():
    responses.add(responses.POST, "https://hooks.slack.com/services/x/y/z", status=200)
    n = Notifier(slack_webhook="https://hooks.slack.com/services/x/y/z")
    assert n.send_slack(_gold()) is True
    # JSON encoder escapes non-ASCII by default; just verify GOLD appears
    assert "GOLD" in responses.calls[0].request.body.decode()


@responses.activate
def test_send_email_posts_to_sendgrid():
    responses.add(
        responses.POST,
        "https://api.sendgrid.com/v3/mail/send",
        status=202,
    )
    n = Notifier(sendgrid_api_key="SG.test", alert_email="me@example.com")
    assert n.send_email(_gold()) is True
    body = responses.calls[0].request.body.decode()
    assert "me@example.com" in body
    assert "GOLD" in body
