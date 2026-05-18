import os
import resend
import base64
from dotenv import load_dotenv
import time

load_dotenv()

resend.api_key = os.getenv(
    "RESEND_API_KEY"
)


def send_report_email(
    to_email,
    company,
    pdf_path
):

    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                print(f"📧 Email Service: Retry attempt {attempt} (waiting {retry_delay}s)")
                time.sleep(retry_delay)
                retry_delay *= 2
            
            print(f"📧 Email Service: Sending email (attempt {attempt + 1}/{max_retries})")
            print(f"📧 Email Service: Reading PDF from {pdf_path}")
            with open(pdf_path, "rb") as f:
                pdf_data = f.read()

            print(f"📧 Email Service: PDF size {len(pdf_data)} bytes")

            pdf_base64 = base64.b64encode(
                pdf_data
            ).decode("utf-8")

            params = {
                "from": os.getenv(
                    "SENDER_EMAIL"
                ),
                "to": [to_email],
                "subject": f"{company} - AI Growth Audit Report",
                "html": f"""
            <h2>Your AI Growth Audit is Ready</h2>

            <p>
            We analyzed your company website and generated
            a personalized business growth report.
            </p>

            <p>
            The report is attached as a PDF.
            </p>

            <p>
            Thanks for trying the platform.
            </p>
            """,
                "attachments": [
                    {
                        "filename": f"{company}.pdf",
                        "content": pdf_base64
                    }
                ]
            }

            print(f"📧 Email Service: Sending to {to_email}")
            
            email = resend.Emails.send(
                params
            )

            print(f"📧 Email Service: ✓ Email sent successfully")
            return email
            
        except Exception as e:
            print(f"📧 Email Service: ⚠ Error on attempt {attempt + 1}: {type(e).__name__}: {str(e)}")
            if attempt == max_retries - 1:
                print(f"📧 Email Service: ✗ Failed after {max_retries} attempts")
                return {
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "failed_attempts": max_retries
                }
            continue
