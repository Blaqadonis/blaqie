# send whatsapp message mcp server
from mcp.server.fastmcp import FastMCP
import pywhatkit

mcp = FastMCP("send_whatsapp_message")

@mcp.tool()
def send_whatsapp_message(phone_number: str, message: str) -> str:
    """Sends a WhatsApp message to the specified phone number using WhatsApp Web automation."""
    try:
        pywhatkit.sendwhatmsg_instantly(phone_number, message)
        return f"WhatsApp message sent successfully to {phone_number}: '{message}'"
    except Exception as e:
        return f"Failed to send WhatsApp message to {phone_number}: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
