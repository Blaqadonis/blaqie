# send Slack message mcp server
import os
from typing import Union
from mcp.server.fastmcp import FastMCP
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv

load_dotenv()

mcp = FastMCP("send_slack_message")

@mcp.tool()
def send_slack_message(recipient: str, message: str, token: Union[str, None] = None) -> str:
    """Sends a message to a Slack channel or direct message (DM) using the Slack API."""
    token = token or os.getenv("SLACK_BOT_TOKEN")
    if not token:
        return "Error: Slack Bot Token not set in environment variables."
    client = WebClient(token=token)
    try:
        if recipient.startswith(('U', 'W')):
            response = client.conversations_open(users=recipient)
            channel_id = response['channel']['id']
        else:
            channel_id = recipient
        response = client.chat_postMessage(channel=channel_id, text=message)
        return f"Slack message sent successfully to {recipient} (TS: {response['ts']}): '{message}'"
    except SlackApiError as e:
        return f"Failed to send Slack message to {recipient}: {e.response['error']}"
    except Exception as e:
        return f"Unexpected error sending Slack message to {recipient}: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport="stdio")