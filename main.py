"""
TEMPLATE: Roz shaam 6 baje auto-run hokar Gmail par report bhejne wala script
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from datetime import datetime

# ===== STEP 1: TUMHARA REPORT KA CODE YAHAN =====
def apna_report_banao():
    # --- EXAMPLE (isko hata kar apna code likhna hai) ---
    aaj = datetime.now().strftime("%d-%m-%Y")
    report = f"""
    Namaste! Ye aaj ki report hai ({aaj})

    - Kaam 1: Ho gaya
    - Kaam 2: Ho gaya
    - Total: 100

    Ye email GitHub se automatic aaya hai.
    """
    return report


# ===== STEP 2: EMAIL BHEJNE KA CODE (isko mat chhedo) =====
def email_bhejo(report_text):
    email_from = os.environ.get("MY_EMAIL")
    app_password = os.environ.get("MY_APP_PASSWORD")
    email_to = os.environ.get("MY_EMAIL")

    if not email_from or not app_password:
        print("ERROR: GitHub Secrets me MY_EMAIL / MY_APP_PASSWORD nahi mile!")
        return

    msg = MIMEMultipart()
    msg["From"] = email_from
    msg["To"] = email_to
    msg["Subject"] = f"Daily Report - {datetime.now().strftime('%d-%m-%Y')}"

    msg.attach(MIMEText(report_text, "plain", "utf-8"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(email_from, app_password)
        server.send_message(msg)

    print("Email safal ta se bhej diya!")


if __name__ == "__main__":
    print("Report ban rahi hai...")
    report = apna_report_banao()
    print(report)
    email_bhejo(report)
