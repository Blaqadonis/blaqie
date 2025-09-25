# send email mcp server
import os
import smtplib
from typing import Union
from mcp.server.fastmcp import FastMCP
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

mcp = FastMCP("send_email")

@mcp.tool()
def send_email(recipient_email: str, subject: str, body: str, sender_email: Union[str, None] = None, sender_password: Union[str, None] = None) -> str:
    """Sends an email via Gmail's SMTP server to the specified recipient."""
    sender_email = sender_email or os.getenv("GMAIL_USER")
    sender_password = sender_password or os.getenv("GMAIL_PASSWORD")
    if not sender_email or not sender_password:
        return "Error: Gmail credentials not set in environment variables."
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = recipient_email
    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return f"Email sent successfully to {recipient_email}: '{subject}'"
    except Exception as e:
        return f"Failed to send email to {recipient_email}: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport="stdio")