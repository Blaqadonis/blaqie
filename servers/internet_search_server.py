# internet search mcp server
import os
from typing import Literal
from tavily import TavilyClient
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

mcp = FastMCP("internet_search")
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

@mcp.tool()
def internet_search(query: str, max_results: int = 5, topic: Literal["general", "news", "finance"] = "general", include_raw_content: bool = False) -> dict:
    """Performs a web search using the Tavily API to retrieve relevant results."""
    return tavily_client.search(query, max_results=max_results, include_raw_content=include_raw_content, topic=topic)

if __name__ == "__main__":
    mcp.run(transport="stdio")