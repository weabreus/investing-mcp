
from mcp.server.fastmcp import FastMCP
from tools.polygon import register_stock_tools

mcp = FastMCP(
    name="Investing MCP Server", 
    instructions="""
    This server includes tools to aid in day to day trading tasks.
    """)

# Register all tools
register_stock_tools(mcp)

if __name__ == "__main__":
    mcp.run(transport="stdio")