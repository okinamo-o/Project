import os
import uuid
import asyncio
import datetime
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, List, Optional, Tuple
from backend.app.core.config import settings
from backend.app.core.events import event_manager

logger = logging.getLogger("nexus.email_service")

ROOM_DISPLAY_NAMES: Dict[str, str] = {
    "classroom_01": "Classroom 01",
    "classroom_02": "Classroom 02",
    "lab_01": "Computer Lab 01",
    "lab_02": "Chemistry & Physics Lab 02",
    "server_room": "Server Room",
    "storage_room": "Chemical Storage Room",
    "main_hall": "Main Hall",
    "entrance": "Main Entrance",
    "emergency_exit": "Emergency Exit",
}


class EmailNotificationService:
    """
    Generates and dispatches per-room Warning & Alert reports via Email.
    Defaults to 'louayhamdi438@gmail.com' and allows dynamic recipient updates from the UI.
    Automatically triggers when any room enters a WARNING or CRITICAL ALERT state,
    and also supports on-demand room report dispatch.
    """

    def __init__(self):
        self.recipient_email: str = settings.ALERT_RECIPIENT_EMAIL or "louayhamdi438@gmail.com"
        self.auto_send: bool = bool(settings.AUTO_EMAIL_ON_ALERT)
        self.smtp_host: str = settings.SMTP_HOST or "smtp.gmail.com"
        self.smtp_port: int = int(settings.SMTP_PORT or 587)
        self.smtp_user: str = settings.SMTP_USER or self.recipient_email
        self.smtp_password: Optional[str] = settings.SMTP_PASSWORD or os.environ.get("SMTP_PASSWORD")
        self.reports_dir: str = os.path.join("logs", "email_reports")
        os.makedirs(self.reports_dir, exist_ok=True)
        self.sent_reports: List[Dict[str, Any]] = []

    def update_config(
        self,
        recipient_email: Optional[str] = None,
        auto_send: Optional[bool] = None,
        smtp_password: Optional[str] = None,
    ) -> Dict[str, Any]:
        if recipient_email and "@" in recipient_email:
            self.recipient_email = recipient_email.strip()
        if auto_send is not None:
            self.auto_send = bool(auto_send)
        if smtp_password is not None and smtp_password.strip():
            self.smtp_password = smtp_password.strip()
        return self.get_config()

    def get_config(self) -> Dict[str, Any]:
        return {
            "recipient_email": self.recipient_email,
            "auto_send": self.auto_send,
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port,
            "smtp_user": self.smtp_user,
            "smtp_configured": bool(self.smtp_password),
            "recent_reports": self.sent_reports[:15],
        }

    def build_room_report_email(
        self,
        room_id: str,
        room_name: str,
        severity: str,
        incident: Optional[Dict[str, Any]],
        telemetry: Dict[str, Any],
        recipient_email: str,
    ) -> Tuple[str, str, str]:
        """
        Builds (subject, plain_text_body, html_body) for a room Warning/Alert/Status report.
        """
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        sev_upper = (severity or "WARNING").upper()

        if sev_upper == "CRITICAL":
            badge_label = "CRITICAL ALERT"
            badge_bg = "#dc2626"
            badge_border = "#ef4444"
            accent_color = "#ef4444"
            bg_tint = "#241217"
            border_color = "#dc2626"
            subject = f"🚨 [NEXUS CRITICAL ALERT] {room_name} — {incident.get('type', 'EMERGENCY').replace('_', ' ') if incident else 'Critical Hazard'}"
        elif sev_upper == "WARNING":
            badge_label = "WARNING"
            badge_bg = "#d97706"
            badge_border = "#f59e0b"
            accent_color = "#f59e0b"
            bg_tint = "#261d12"
            border_color = "#d97706"
            subject = f"⚠️ [NEXUS WARNING REPORT] {room_name} — {incident.get('type', 'ANOMALY').replace('_', ' ') if incident else 'Environmental Warning'}"
        else:
            badge_label = "NORMAL"
            badge_bg = "#059669"
            badge_border = "#10b981"
            accent_color = "#10b981"
            bg_tint = "#12231c"
            border_color = "#059669"
            subject = f"✅ [NEXUS ROOM REPORT] {room_name} — Operational Telemetry & Safety Summary"

        inc_id = incident.get("id", f"REP-{uuid.uuid4().hex[:6].upper()}") if incident else f"REP-{uuid.uuid4().hex[:6].upper()}"
        inc_type = incident.get("type", "ENVIRONMENTAL_STATUS_REPORT").replace("_", " ") if incident else "NOMINAL_INSPECTION"
        inc_conf = f"{int(float(incident.get('confidence', 0.95)) * 100)}%" if incident else "99%"
        inc_summary = (
            incident.get("summary")
            if incident and incident.get("summary")
            else f"{room_name} ({room_id}) is currently operating within safe environmental parameters."
        )

        temp_val = telemetry.get("temperature", 22.0)
        hum_val = telemetry.get("humidity", 45.0)
        gas_val = telemetry.get("gas", 80.0)
        smoke_val = telemetry.get("smoke", 0.3)
        occ_val = telemetry.get("occupancy", 0)

        evidence_list = incident.get("evidence", []) if incident else []
        evidence_rows_html = ""
        evidence_lines_txt = []
        if evidence_list:
            for ev in evidence_list:
                s_type = ev.get("source_type", "SENSOR")
                s_id = ev.get("source_id", "device")
                contrib = int(float(ev.get("contribution", 0)) * 100)
                expl = ev.get("explanation", "")
                evidence_rows_html += (
                    f"<tr>"
                    f"<td style='padding:10px 12px;border-bottom:1px solid #1e293b;font-weight:600;color:#e2e8f0;'>{s_type}: {s_id}</td>"
                    f"<td style='padding:10px 12px;border-bottom:1px solid #1e293b;color:#cbd5e1;'>{expl}</td>"
                    f"<td style='padding:10px 12px;border-bottom:1px solid #1e293b;color:{accent_color};font-weight:700;text-align:right;'>{contrib}%</td>"
                    f"</tr>"
                )
                evidence_lines_txt.append(f"  * [{s_type}: {s_id}] ({contrib}% impact) — {expl}")
        else:
            evidence_rows_html = (
                "<tr><td colspan='3' style='padding:12px;color:#94a3b8;'>"
                "All multi-sensor channels evaluated within normal baseline thresholds."
                "</td></tr>"
            )
            evidence_lines_txt.append("  * All multi-sensor channels within normal baseline thresholds.")

        timeline_list = (incident.get("timeline", []) if incident else [])[-6:]
        timeline_html = ""
        for t in timeline_list:
            t_str = str(t.get("time", ""))[:19]
            t_src = t.get("source", "SYSTEM")
            t_desc = t.get("description", "")
            timeline_html += (
                f"<li style='margin-bottom:8px;padding-left:10px;border-left:2px solid {accent_color};color:#cbd5e1;font-size:13px;'>"
                f"<span style='color:#64748b;font-family:monospace;'>[{t_str}]</span> "
                f"<strong>[{t_src}]</strong> {t_desc}</li>"
            )
        if not timeline_html:
            timeline_html = f"<li style='color:#94a3b8;font-size:13px;'>[{now_str}] Snapshot generated for {room_name}.</li>"

        plain_text = (
            f"NEXUS SMART BUILDING — {badge_label}\n"
            f"============================================================\n"
            f"Recipient:      {recipient_email}\n"
            f"Room:           {room_name} ({room_id})\n"
            f"Severity:       {badge_label}\n"
            f"Incident ID:    {inc_id}\n"
            f"Classification: {inc_type} (Confidence: {inc_conf})\n"
            f"Timestamp:      {now_str}\n\n"
            f"SUMMARY:\n"
            f"{inc_summary}\n\n"
            f"LIVE ROOM TELEMETRY ({room_name}):\n"
            f"  - Temperature: {temp_val:.1f} °C\n"
            f"  - Humidity:    {hum_val:.0f} %\n"
            f"  - Gas (MQ-2):  {gas_val:.0f} ppm\n"
            f"  - Smoke:       {smoke_val:.1f} %\n"
            f"  - Occupancy:   {occ_val} person(s)\n\n"
            f"CONTRIBUTING SENSOR EVIDENCE:\n"
            + "\n".join(evidence_lines_txt)
            + "\n\nOPEN LIVE DASHBOARD TO INSPECT:\n"
            f"  https://nexus-7ba7a.web.app\n"
            f"============================================================\n"
            f"Generated automatically by NEXUS Smart Building Monitor."
        )

        html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{subject}</title>
</head>
<body style="margin:0;padding:28px;background-color:#0b0f19;color:#e2e8f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;line-height:1.6;">
  <div style="max-width:760px;margin:0 auto;background-color:#131b2e;border:1px solid #1e293b;border-radius:14px;overflow:hidden;box-shadow:0 12px 32px rgba(0,0,0,0.45);">
    <!-- HEADER -->
    <div style="padding:22px 26px;background-color:{bg_tint};border-bottom:2px solid {border_color};">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="width:100%;border-collapse:collapse;margin:0;padding:0;">
        <tr>
          <td align="left" valign="middle" style="vertical-align:middle;padding:0;text-align:left;">
            <div style="font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:{accent_color};margin:0 0 4px 0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
              NEXUS SMART BUILDING &bull; AUTOMATED ALERT
            </div>
            <h1 style="margin:0;padding:0;font-size:22px;font-weight:800;color:#ffffff;line-height:28px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
              {room_name} <span style="font-size:14px;font-weight:500;color:#94a3b8;">({room_id.upper()})</span>
            </h1>
            <div style="font-size:12px;color:#94a3b8;margin:5px 0 0 0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
              Dispatched to: <span style="color:#cbd5e1;font-weight:600;">{recipient_email}</span> &bull; {now_str}
            </div>
          </td>
          <td align="right" valign="middle" style="vertical-align:middle;text-align:right;padding:0 0 0 16px;white-space:nowrap;width:1%;">
            <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;display:inline-table;vertical-align:middle;margin-left:auto;">
              <tr>
                <td style="background-color:{badge_bg};border:1px solid {badge_border};border-radius:6px;padding:6px 14px;text-align:center;vertical-align:middle;white-space:nowrap;">
                  <span style="color:#ffffff;font-weight:800;font-size:12px;letter-spacing:0.8px;text-transform:uppercase;display:block;line-height:16px;white-space:nowrap;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
                    {badge_label}
                  </span>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </div>

    <div style="padding:26px;">
      <!-- INCIDENT HIGHLIGHT BOX -->
      <div style="padding:18px 20px;border-radius:12px;background:#0f172a;border:1px solid {border_color};margin-bottom:24px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:8px;border-collapse:collapse;">
          <tr>
            <td align="left" valign="middle" style="padding:0;">
              <strong style="color:{accent_color};font-size:15px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">{inc_type}</strong>
            </td>
            <td align="right" valign="middle" style="padding:0;text-align:right;font-size:12px;color:#94a3b8;font-family:monospace;white-space:nowrap;">
              ID: {inc_id} &bull; Confidence: {inc_conf}
            </td>
          </tr>
        </table>
        <p style="margin:0 0 14px 0;font-size:14px;color:#f1f5f9;line-height:1.5;">{inc_summary}</p>
        <a href="https://nexus-7ba7a.web.app" style="display:inline-block;padding:10px 18px;border-radius:8px;background:{badge_bg};color:#ffffff;font-weight:700;font-size:13px;text-decoration:none;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
          Open NEXUS Live Website Dashboard &rarr;
        </a>
      </div>

      <h3 style="margin:0 0 12px 0;font-size:13px;text-transform:uppercase;letter-spacing:0.8px;color:#94a3b8;">
        Live Room Sensor Readings — {room_name}
      </h3>
      <table style="width:100%;border-collapse:separate;border-spacing:8px;margin-bottom:24px;">
        <tr>
          <td style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:12px;text-align:center;">
            <div style="font-size:11px;color:#94a3b8;">Temperature</div>
            <div style="font-size:18px;font-weight:700;color:#f8fafc;margin-top:2px;">{temp_val:.1f}°C</div>
          </td>
          <td style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:12px;text-align:center;">
            <div style="font-size:11px;color:#94a3b8;">Gas (MQ-2)</div>
            <div style="font-size:18px;font-weight:700;color:#f8fafc;margin-top:2px;">{gas_val:.0f} ppm</div>
          </td>
          <td style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:12px;text-align:center;">
            <div style="font-size:11px;color:#94a3b8;">Smoke Density</div>
            <div style="font-size:18px;font-weight:700;color:#f8fafc;margin-top:2px;">{smoke_val:.1f}%</div>
          </td>
          <td style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:12px;text-align:center;">
            <div style="font-size:11px;color:#94a3b8;">Humidity</div>
            <div style="font-size:18px;font-weight:700;color:#f8fafc;margin-top:2px;">{hum_val:.0f}%</div>
          </td>
          <td style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:12px;text-align:center;">
            <div style="font-size:11px;color:#94a3b8;">Occupancy</div>
            <div style="font-size:18px;font-weight:700;color:#f8fafc;margin-top:2px;">{occ_val}</div>
          </td>
        </tr>
      </table>

      <h3 style="margin:0 0 10px 0;font-size:13px;text-transform:uppercase;letter-spacing:0.8px;color:#94a3b8;">
        Why This {badge_label.title()} Triggered (Sensor Attribution)
      </h3>
      <table style="width:100%;border-collapse:collapse;background:#0f172a;border-radius:10px;overflow:hidden;margin-bottom:24px;font-size:13px;">
        <thead>
          <tr style="background:#1e293b;color:#94a3b8;text-align:left;font-size:11px;text-transform:uppercase;">
            <th style="padding:10px 12px;">Sensor / Modality</th>
            <th style="padding:10px 12px;">Evidence Explanation</th>
            <th style="padding:10px 12px;text-align:right;">Impact</th>
          </tr>
        </thead>
        <tbody>
          {evidence_rows_html}
        </tbody>
      </table>

      <h3 style="margin:0 0 10px 0;font-size:13px;text-transform:uppercase;letter-spacing:0.8px;color:#94a3b8;">
        Recent Room Event Timeline
      </h3>
      <ul style="list-style:none;padding:0;margin:0 0 20px 0;">
        {timeline_html}
      </ul>

      <div style="padding-top:16px;border-top:1px solid #1e293b;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;font-size:11px;color:#64748b;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
          <tr>
            <td align="left" valign="middle" style="padding:0;">NEXUS Multimodal Safety Engine v1.0</td>
            <td align="right" valign="middle" style="padding:0;text-align:right;">Recipient: {recipient_email}</td>
          </tr>
        </table>
      </div>
    </div>
  </div>
</body>
</html>"""
        return subject, plain_text, html_body

    def _read_env_smtp_password(self) -> Optional[str]:
        if self.smtp_password:
            return self.smtp_password.replace(" ", "")
        try:
            if os.path.exists(".env"):
                with open(".env", "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("SMTP_PASSWORD="):
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if val:
                                return val.replace(" ", "")
        except Exception:
            pass
        raw = settings.SMTP_PASSWORD or os.environ.get("SMTP_PASSWORD")
        return raw.replace(" ", "") if raw else None

    def _send_smtp_sync(self, recipient: str, subject: str, plain_text: str, html_body: str) -> Tuple[bool, str]:
        """Sends multipart HTML email via SMTP if SMTP_PASSWORD is provided."""
        smtp_pass = self._read_env_smtp_password()
        if not smtp_pass:
            return False, "SMTP_PASSWORD not set in .env"

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"NEXUS Building Monitor <{self.smtp_user}>"
            msg["To"] = recipient
            msg.attach(MIMEText(plain_text, "plain", "utf-8"))
            msg.attach(MIMEText(html_body, "html", "utf-8"))

            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.smtp_user, smtp_pass)
                server.sendmail(self.smtp_user, [recipient], msg.as_string())
            return True, f"Delivered via SMTP ({self.smtp_host}) to {recipient}"
        except Exception as e:
            logger.warning(f"[EMAIL] SMTP delivery failed: {e}")
            return False, f"SMTP error: {str(e)}"

    async def send_room_report(
        self,
        room_id: str,
        severity: str,
        incident: Optional[Dict[str, Any]],
        telemetry: Dict[str, Any],
        recipient_email: Optional[str] = None,
        trigger_source: str = "AUTO",
    ) -> Dict[str, Any]:
        """
        Generates the room Warning/Alert report, saves the HTML report,
        attempts SMTP delivery to `recipient_email` (defaults to `louayhamdi438@gmail.com`),
        and broadcasts the dispatch event to the UI.
        """
        target_email = (recipient_email or self.recipient_email or "louayhamdi438@gmail.com").strip()
        if "@" in target_email:
            self.recipient_email = target_email

        room_name = ROOM_DISPLAY_NAMES.get(room_id, room_id.replace("_", " ").title())
        subject, plain_text, html_body = self.build_room_report_email(
            room_id=room_id,
            room_name=room_name,
            severity=severity,
            incident=incident,
            telemetry=telemetry,
            recipient_email=target_email,
        )

        report_id = f"MAIL-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')}-{room_id[:4].upper()}-{uuid.uuid4().hex[:4].upper()}"
        file_path = os.path.join(self.reports_dir, f"{report_id}.html")
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html_body)
        except Exception as e:
            logger.error(f"[EMAIL] Failed to write local HTML report {file_path}: {e}")

        smtp_sent, status_note = await asyncio.to_thread(
            self._send_smtp_sync, target_email, subject, plain_text, html_body
        )

        record = {
            "report_id": report_id,
            "room_id": room_id,
            "room_name": room_name,
            "severity": (severity or "WARNING").upper(),
            "incident_id": incident.get("id") if incident else None,
            "incident_type": incident.get("type") if incident else "ROOM_STATUS_REPORT",
            "recipient_email": target_email,
            "subject": subject,
            "plain_text": plain_text,
            "smtp_delivered": smtp_sent,
            "delivery_note": status_note,
            "trigger_source": trigger_source,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "preview_url": f"http://127.0.0.1:8000/api/incidents/email-preview/{report_id}",
        }
        self.sent_reports.insert(0, record)
        self.sent_reports = self.sent_reports[:50]

        logger.info(
            f"[EMAIL] Room Report {report_id} ({severity}) for {room_id} -> {target_email} [{status_note}]"
        )

        try:
            await event_manager.broadcast({
                "type": "EMAIL_REPORT_DISPATCHED",
                "report": {
                    k: v for k, v in record.items() if k != "plain_text"
                }
            })
        except Exception:
            pass

        return record

    def get_report_html(self, report_id: str) -> Optional[str]:
        safe_id = os.path.basename(report_id)
        path = os.path.join(self.reports_dir, f"{safe_id}.html")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return None


email_service = EmailNotificationService()
