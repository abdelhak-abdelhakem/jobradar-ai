"""
The designed HTML version of the digest email. The plain-text version in notify.py stays in the same email,
for mail apps that don't show HTML.

Email HTML isn't web HTML: Gmail drops <style> sheets, flexbox, and scripts, so the layout is tables with
inline styles, 600 pixels wide, like the emails companies send. Everything that comes from a job site or the
LLM is escaped, so a job title such as "<script>" is shown as text and never run.
"""
from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING

from src.config import MATCH_SCORE_THRESHOLD

if TYPE_CHECKING:   # imported only for type hints, since notify.py imports this module
    from src.agents.nodes.notify import Digest, DigestJob

BLUE = "#2a78d6"
INK = "#1e293b"
MUTED = "#64748b"
LINE = "#e2e8f0"
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"


def _paragraphs(text: str, style: str) -> str:
    """Plain text to HTML paragraphs: a blank line starts a paragraph, a single newline becomes <br>."""
    blocks = [block.strip() for block in text.strip().split("\n\n") if block.strip()]
    return "".join(f'<p style="margin:0 0 12px;{style}">{escape(block).replace(chr(10), "<br>")}</p>'
                   for block in blocks)


def _score_badge(score: int) -> str:
    strong = score >= MATCH_SCORE_THRESHOLD
    colors = f"background:{BLUE};color:#ffffff;" if strong else f"background:#f1f5f9;color:{MUTED};"
    return (f'<span style="{colors}display:inline-block;padding:4px 10px;border-radius:999px;'
            f'font-size:13px;font-weight:700;">{score}/100</span>')


def _stat(value: int, label: str) -> str:
    return (f'<td align="center" style="padding:16px 8px;">'
            f'<div style="font-size:28px;font-weight:700;color:{INK};">{value}</div>'
            f'<div style="font-size:12px;color:{MUTED};text-transform:uppercase;letter-spacing:.5px;">{label}</div>'
            f'</td>')


def _issues(job: DigestJob) -> str:
    if not job.issues:
        return ""
    items = "".join(
        f'<li style="margin:0 0 4px;">{"<i>“" + escape(issue["quote"]) + "”</i> " if issue["quote"] else ""}'
        f'{escape(issue["reason"])}</li>'
        for issue in job.issues
    )
    return (f'<div style="margin:0 0 16px;padding:12px 14px;background:#fffbeb;border:1px solid #fcd34d;'
            f'border-radius:8px;color:#78350f;font-size:14px;">'
            f'<b>⚠ Unverified letter.</b> Check these points before using it:'
            f'<ul style="margin:8px 0 0;padding-left:20px;">{items}</ul></div>')


def _job_card(job: DigestJob) -> str:
    url = escape(job.url, quote=True)
    return f"""
<tr><td style="padding:0 24px 20px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="border:1px solid {LINE};border-radius:12px;border-collapse:separate;">
    <tr><td style="padding:20px 20px 4px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
        <td style="font-size:13px;font-weight:700;color:{BLUE};">#{job.rank}</td>
        <td align="right">{_score_badge(job.score)}</td>
      </tr></table>
      <a href="{url}" style="display:block;margin:8px 0 12px;font-size:18px;font-weight:700;line-height:1.35;
         color:{INK};text-decoration:none;">{escape(job.title)}</a>
      <div style="margin:0 0 4px;font-size:12px;font-weight:700;color:{MUTED};text-transform:uppercase;
           letter-spacing:.5px;">Why this score</div>
      {_paragraphs(job.rationale, f"font-size:14px;line-height:1.55;color:{INK};")}
      {_issues(job)}
      <div style="margin:0 0 6px;font-size:12px;font-weight:700;color:{MUTED};text-transform:uppercase;
           letter-spacing:.5px;">Cover letter draft</div>
      <div style="padding:16px 16px 4px;background:#f8fafc;border-radius:8px;">
        {_paragraphs(job.letter, f"font-size:14px;line-height:1.6;color:{INK};")}
      </div>
    </td></tr>
    <tr><td style="padding:16px 20px 20px;">
      <a href="{url}" style="display:inline-block;padding:10px 18px;background:{BLUE};color:#ffffff;
         border-radius:8px;font-size:14px;font-weight:600;text-decoration:none;">View job posting →</a>
    </td></tr>
  </table>
</td></tr>"""


def render_email_html(digest: Digest, summary: list[str]) -> str:
    """The whole email. summary is the same sentences as the plain-text version, so both say the same."""
    notes = "".join(f'<p style="margin:0 0 6px;font-size:14px;color:{MUTED};">{escape(s)}</p>' for s in summary[1:])
    if digest.jobs:
        body = "".join(_job_card(job) for job in digest.jobs)
    else:
        body = (f'<tr><td align="center" style="padding:8px 24px 32px;font-size:15px;color:{MUTED};">'
                f'No new strong matches this time. JobRadar will keep looking.</td></tr>')

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<title>JobRadar digest</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;">
<!-- The preview text mail apps show next to the subject. -->
<div style="display:none;max-height:0;overflow:hidden;">{escape(summary[0])}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;">
<tr><td align="center" style="padding:24px 12px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="max-width:600px;background:#ffffff;border-radius:16px;font-family:{FONT};color:{INK};">
    <tr><td style="padding:22px 24px;background:{BLUE};border-radius:16px 16px 0 0;">
      <span style="font-size:20px;font-weight:700;color:#ffffff;">◉ JobRadar</span>
      <span style="float:right;padding-top:4px;font-size:13px;color:#dbeafe;">Your job digest</span>
    </td></tr>
    <tr><td style="padding:8px 16px 0;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-bottom:1px solid {LINE};">
        <tr>{_stat(digest.scored_count, "New jobs scored")}{_stat(len(digest.jobs), "Strong matches")}</tr>
      </table>
    </td></tr>
    <tr><td style="padding:16px 24px 12px;">{notes}</td></tr>
    {body}
    <tr><td style="padding:16px 24px 24px;border-top:1px solid {LINE};font-size:12px;line-height:1.5;color:{MUTED};">
      The cover letters are drafts for you to review: nothing was sent to employers.<br>
      Sent by JobRadar, running on your computer.
    </td></tr>
  </table>
</td></tr>
</table>
</body>
</html>"""
