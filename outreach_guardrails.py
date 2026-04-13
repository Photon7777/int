from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


EMAIL_IN_NOTES_RE = re.compile(r"Email:\s*([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", re.I)


def normalize_outreach_email(value: str) -> str:
    return (value or "").strip().lower()


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def extract_outreach_email_from_notes(notes: str) -> str:
    match = EMAIL_IN_NOTES_RE.search(notes or "")
    if not match:
        return ""
    return normalize_outreach_email(match.group(1))


def contact_identity_keys(company: str, contact_name: str, email: str) -> Set[str]:
    keys: Set[str] = set()
    normalized_email = normalize_outreach_email(email)
    normalized_company = _normalize_text(company)
    normalized_name = _normalize_text(contact_name)

    if normalized_email:
        keys.add(f"email:{normalized_email}")
    if normalized_company and normalized_name:
        keys.add(f"company_name:{normalized_company}|{normalized_name}")
    if normalized_company and normalized_email:
        keys.add(f"company_email:{normalized_company}|{normalized_email}")
    return keys


def _row_records(rows: Any) -> List[Mapping[str, Any]]:
    if hasattr(rows, "to_dict"):
        return rows.to_dict("records")
    return list(rows or [])


def tracker_outreach_history(rows: Any) -> dict[str, Set[str]]:
    emails: Set[str] = set()
    identities: Set[str] = set()

    for row in _row_records(rows):
        company = str(row.get("Company", "") or "")
        contact_name = str(row.get("Contact Name", "") or "")
        notes = str(row.get("Notes", "") or "")
        email = normalize_outreach_email(str(row.get("Email", "") or "")) or extract_outreach_email_from_notes(notes)

        if email:
            emails.add(email)
        identities.update(contact_identity_keys(company, contact_name, email))

    return {"emails": emails, "identities": identities}


def is_duplicate_contact(
    company: str,
    contact_name: str,
    email: str,
    *,
    blocked_emails: Optional[Iterable[str]] = None,
    blocked_identity_keys: Optional[Iterable[str]] = None,
) -> bool:
    normalized_email = normalize_outreach_email(email)
    blocked_email_set = {normalize_outreach_email(item) for item in (blocked_emails or []) if normalize_outreach_email(item)}
    if normalized_email and normalized_email in blocked_email_set:
        return True

    identity_keys = contact_identity_keys(company, contact_name, email)
    blocked_identity_set = {str(item) for item in (blocked_identity_keys or []) if str(item)}
    return bool(identity_keys & blocked_identity_set)


def filter_new_contacts(
    company: str,
    contacts: Sequence[Mapping[str, Any]],
    *,
    blocked_emails: Optional[Iterable[str]] = None,
    blocked_identity_keys: Optional[Iterable[str]] = None,
) -> Tuple[List[Mapping[str, Any]], int]:
    seen_emails = {normalize_outreach_email(item) for item in (blocked_emails or []) if normalize_outreach_email(item)}
    seen_identity_keys = {str(item) for item in (blocked_identity_keys or []) if str(item)}

    filtered: List[Mapping[str, Any]] = []
    skipped = 0

    for contact in contacts:
        email = normalize_outreach_email(str(contact.get("email", "") or ""))
        identity_keys = contact_identity_keys(
            company,
            str(contact.get("name", "") or ""),
            email,
        )

        if email and email in seen_emails:
            skipped += 1
            continue
        if identity_keys and identity_keys & seen_identity_keys:
            skipped += 1
            continue

        filtered.append(contact)
        if email:
            seen_emails.add(email)
        seen_identity_keys.update(identity_keys)

    return filtered, skipped


def unique_send_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    already_contacted_emails: Optional[Iterable[str]] = None,
) -> Tuple[List[Mapping[str, Any]], List[dict[str, str]]]:
    existing = {normalize_outreach_email(item) for item in (already_contacted_emails or []) if normalize_outreach_email(item)}
    seen = set(existing)
    unique_rows: List[Mapping[str, Any]] = []
    skipped: List[dict[str, str]] = []

    for row in rows:
        email = normalize_outreach_email(str(row.get("Email", "") or ""))
        if not email:
            skipped.append({"email": "", "reason": "missing_email"})
            continue
        if email in seen:
            reason = "already_contacted" if email in existing else "duplicate_in_batch"
            skipped.append({"email": email, "reason": reason})
            continue
        seen.add(email)
        unique_rows.append(row)

    return unique_rows, skipped


def build_outreach_tracker_row(
    *,
    company: str,
    preferred_role: str,
    target_location: str,
    contact_name: str,
    contact_link: str,
    email: str,
    subject: str,
    personalization: str,
    sponsorship_signal: str,
    resume_name: str,
    send_source: str,
    role_source_url: str = "",
    gmail_message_id: str = "",
    gmail_thread_id: str = "",
    reply_status: str = "No reply",
    sequence_step: str = "Initial",
    sent_on: Optional[date] = None,
) -> dict[str, str]:
    today = sent_on or date.today()
    follow_up = today + timedelta(days=5)
    notes_lines = [
        "Outreach State: sent",
        f"Send Source: {send_source}",
        f"Sent On: {today.isoformat()}",
    ]
    if role_source_url:
        notes_lines.append(f"Role Source URL: {role_source_url}")

    return {
        "Date": today.isoformat(),
        "Company": company,
        "Role": preferred_role or "Cold outreach",
        "Location": target_location,
        "Status": "Sent",
        "Reply Status": reply_status or "No reply",
        "Resume Used": resume_name,
        "Follow-up Date": follow_up.isoformat(),
        "Next Follow-up At": follow_up.isoformat(),
        "Contact Name": contact_name,
        "Contact Link": contact_link,
        "Email": email,
        "Subject": subject,
        "Personalization": personalization,
        "Sponsorship Signal": sponsorship_signal or "Unknown / verify",
        "Send Source": send_source,
        "Role Source URL": role_source_url,
        "Gmail Message ID": gmail_message_id,
        "Gmail Thread ID": gmail_thread_id,
        "Last Reply At": "",
        "Last Reply From": "",
        "Last Reply Snippet": "",
        "Last Synced At": "",
        "Sequence Step": sequence_step or "Initial",
        "Paused Reason": "",
        "Notes": "\n".join(notes_lines),
    }


def _parse_date_maybe(value: str) -> Optional[date]:
    raw = (value or "").strip()
    if not raw:
        return None
    for candidate in (raw, raw.split("T", 1)[0]):
        try:
            return date.fromisoformat(candidate)
        except Exception:
            continue
    return None


def _first_sentence(text: str, limit: int = 220) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    sentence = parts[0].strip()
    if len(sentence) > limit:
        sentence = sentence[:limit].rstrip() + "..."
    return sentence


def fallback_outreach_next_step(
    *,
    reply_status: str,
    company: str,
    role: str,
    contact_name: str,
    sender_name: str,
    latest_reply_snippet: str = "",
    candidate_summary: str = "",
    personalization: str = "",
    linkedin_url: str = "",
    portfolio_url: str = "",
) -> dict[str, str]:
    first_name = (contact_name or "there").split()[0] if contact_name else "there"
    company_ref = (company or "the team").strip()
    role_ref = (role or "this role").strip()
    sender_display = (sender_name or "").strip() or "Sai Praneeth"
    summary_line = _first_sentence(candidate_summary, limit=180)
    if summary_line and summary_line[-1] not in ".!?":
        summary_line += "."
    personalization_line = (personalization or "").strip()
    if personalization_line and personalization_line[-1] not in ".!?":
        personalization_line += "."
    link_lines = []
    if (linkedin_url or "").strip():
        link_lines.append(f"LinkedIn: {linkedin_url.strip()}")
    if (portfolio_url or "").strip():
        link_lines.append(f"Portfolio: {portfolio_url.strip()}")
    link_block = "\n".join(link_lines)
    if link_block:
        link_block = "\n" + link_block

    snippet = re.sub(r"\s+", " ", (latest_reply_snippet or "").strip())
    snippet_lower = snippet.lower()
    normalized_status = (reply_status or "").strip()

    if normalized_status == "Bounced":
        return {
            "suggested_action": "Find a new contact before resending",
            "suggested_followup": (
                f"The last message to {company_ref} appears to have bounced. "
                "Do not resend to the same address yet. Verify the company domain, find an alternate recruiter or hiring manager, "
                f"and reuse the strongest angle from the prior outreach: {personalization_line or 'role fit and candidate background.'}"
            ),
        }

    if normalized_status == "Replied":
        if any(token in snippet_lower for token in ("schedule", "availability", "time", "calendar", "chat", "call", "meeting", "interview")):
            body = (
                f"Hi {first_name},\n\n"
                "Thank you for getting back to me. I would be happy to connect and can make time this week or next week. "
                "If there is a preferred time window that works best for you, I can adjust to it."
                f"{link_block}\n\nBest,\n{sender_display}\n"
            )
            return {
                "suggested_action": "Reply with availability and confirm interest",
                "suggested_followup": body,
            }
        if any(token in snippet_lower for token in ("resume", "cv", "send over", "share")):
            body = (
                f"Hi {first_name},\n\n"
                "Thank you for the reply. I have attached my resume here for convenience. "
                f"{summary_line or f'I remain very interested in {role_ref} opportunities at {company_ref}.'} "
                "Please let me know if there is any additional context that would be helpful."
                f"{link_block}\n\nBest,\n{sender_display}\n"
            )
            return {
                "suggested_action": "Reply with resume and a concise fit recap",
                "suggested_followup": body,
            }
        if any(token in snippet_lower for token in ("not hiring", "no opening", "no openings", "not currently", "future", "later")):
            body = (
                f"Hi {first_name},\n\n"
                "Thank you for the quick reply and for the transparency. I understand the timing may not be right right now. "
                f"If relevant roles open up later at {company_ref}, I would be grateful to stay on your radar."
                f"{link_block}\n\nBest,\n{sender_display}\n"
            )
            return {
                "suggested_action": "Thank them and ask to stay in touch",
                "suggested_followup": body,
            }
        body = (
            f"Hi {first_name},\n\n"
            "Thank you for getting back to me. I appreciate the response. "
            f"{summary_line or f'I am especially interested in {role_ref} work at {company_ref}.'} "
            "If there is a best next step, team, or opening I should focus on, I would really appreciate the guidance."
            f"{link_block}\n\nBest,\n{sender_display}\n"
        )
        return {
            "suggested_action": "Reply, acknowledge the note, and ask for the best next step",
            "suggested_followup": body,
        }

    if normalized_status == "Needs follow-up":
        body = (
            f"Hi {first_name},\n\n"
            f"Following up on my earlier note about {role_ref} opportunities at {company_ref}. "
            f"{personalization_line or f'I reached out because the work at {company_ref} looked closely aligned with my background.'} "
            f"{summary_line or ''} "
            "If there is a better next step or person to connect with, I would appreciate the guidance."
            f"{link_block}\n\nBest,\n{sender_display}\n"
        )
        return {
            "suggested_action": "Send a gentle follow-up",
            "suggested_followup": re.sub(r"\n{3,}", "\n\n", body).strip() + "\n",
        }

    if normalized_status == "Drafted":
        return {
            "suggested_action": "Review the draft and send the first email",
            "suggested_followup": "This outreach row is still a draft. Review the subject and body, confirm the contact, and send the initial message when ready.",
        }

    return {
        "suggested_action": "Wait for a reply or follow up on the due date",
        "suggested_followup": (
            f"No reply has been detected yet for {company_ref}. If the follow-up date has arrived, send a short check-in. "
            "Otherwise, wait until the next follow-up window so the outreach stays thoughtful instead of repetitive."
        ),
    }


def classify_outreach_thread(
    summary: Mapping[str, Any],
    *,
    follow_up_date: str,
    today: Optional[date] = None,
) -> dict[str, str]:
    current_day = today or date.today()
    latest_at = str(summary.get("latest_message_at") or "")
    latest_from = str(summary.get("latest_message_from") or "")
    latest_snippet = str(summary.get("latest_snippet") or "")
    is_bounce = bool(summary.get("is_bounce"))
    has_inbound_reply = bool(summary.get("has_inbound_reply"))

    if is_bounce:
        return {
            "Status": "Closed",
            "Reply Status": "Bounced",
            "Paused Reason": "bounce_detected",
            "Last Reply At": latest_at,
            "Last Reply From": latest_from,
            "Last Reply Snippet": latest_snippet,
            "Next Follow-up At": "",
        }

    if has_inbound_reply:
        return {
            "Status": "Replied",
            "Reply Status": "Replied",
            "Paused Reason": "reply_received",
            "Last Reply At": latest_at,
            "Last Reply From": latest_from,
            "Last Reply Snippet": latest_snippet,
            "Next Follow-up At": "",
        }

    due_date = _parse_date_maybe(follow_up_date)
    if due_date and due_date < current_day:
        return {
            "Status": "Sent",
            "Reply Status": "Needs follow-up",
            "Paused Reason": "",
            "Last Reply At": "",
            "Last Reply From": "",
            "Last Reply Snippet": "",
            "Next Follow-up At": due_date.isoformat(),
        }

    next_follow_up_at = due_date.isoformat() if due_date else ""
    return {
        "Status": "Sent",
        "Reply Status": "No reply",
        "Paused Reason": "",
        "Last Reply At": "",
        "Last Reply From": "",
        "Last Reply Snippet": "",
        "Next Follow-up At": next_follow_up_at,
    }
