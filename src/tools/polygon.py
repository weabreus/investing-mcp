import os
import aiohttp
import asyncio
import ssl
import certifi
from typing import Dict, Any, Optional
from mcp.server.fastmcp import FastMCP
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Get your free API key from https://polygon.io/
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY", "")
BASE_URL = "https://api.polygon.io"

if not POLYGON_API_KEY:
    raise ValueError("POLYGON_API_KEY not found in environment variables. Please check your .env file.")

async def make_polygon_request(endpoint: str, params: Dict[str, str] = None) -> Dict[str, Any]:
    """Make an async API request to Polygon"""
    if not params:
        params = {}
    params["apikey"] = POLYGON_API_KEY
    
    url = f"{BASE_URL}{endpoint}"
    
    # Create SSL context with proper certificates
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.get(url, params=params) as response:
            if response.status == 200:
                return await response.json()
            else:
                raise Exception(f"API request failed with status {response.status}: {await response.text()}")

def register_stock_tools(mcp: FastMCP):
    """Register Polygon stock data tools with the MCP server"""
    

    @mcp.tool("GetStockPrice")
    async def get_stock_price(symbol: str) -> str:
        """
        Get the current stock price and daily stats for a given symbol.
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL', 'GOOGL', 'TSLA')
            
        Returns:
            Current stock price and daily trading stats
        """
        try:
            # Get the most recent trading day data
            # Go back a few days to ensure we get data (handles weekends/holidays)
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
            
            # Using multiplier=1, timespan=day for daily bars
            endpoint = f"/v2/aggs/ticker/{symbol.upper()}/range/1/day/{start_date}/{end_date}"
            
            data = await make_polygon_request(endpoint)
            
            if (data.get("status") == "OK" or data.get("status") == "DELAYED") and data.get("results"):
                # Get the most recent trading day (last item in results)
                result_data = data["results"][-1]
                
                open_price = result_data.get("o", "N/A")
                high_price = result_data.get("h", "N/A")
                low_price = result_data.get("l", "N/A")
                close_price = result_data.get("c", "N/A")
                volume = result_data.get("v", "N/A")
                timestamp = result_data.get("t", "N/A")
                
                # Convert timestamp to readable date
                if timestamp != "N/A":
                    trade_date = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d')
                else:
                    trade_date = "N/A"
                
                # Calculate change if we have open and close
                change_info = ""
                if open_price != "N/A" and close_price != "N/A":
                    change_val = close_price - open_price
                    change_pct = (change_val / open_price) * 100
                    change_direction = "📈" if change_val > 0 else "📉" if change_val < 0 else "➡️"
                    change_info = f"Change: ${change_val:.2f} ({change_pct:.2f}%) {change_direction}"
                
                # Format volume with commas
                volume_formatted = f"{volume:,}" if volume != "N/A" else "N/A"
                
                return f"""
    📊 **{symbol.upper()}** - {trade_date}

    💰 **Price Data:**
    • Open: ${open_price:.2f}
    • High: ${high_price:.2f}
    • Low: ${low_price:.2f}
    • Close: ${close_price:.2f}

    📈 **Performance:**
    {change_info}

    📊 **Volume:** {volume_formatted} shares

    ℹ️  *Data from most recent trading day*
    """
            else:
                return f"❌ Error: Could not retrieve data for {symbol.upper()}.\nStatus: {data.get('status', 'Unknown')}\nMessage: {data.get('error', 'No additional info')}"
                
        except Exception as e:
            return f"❌ Error fetching stock price for {symbol.upper()}: {str(e)}"
    @mcp.tool("GetStockDetails")
    async def get_stock_details(symbol: str) -> str:
        """
        Get detailed company information and ticker details.
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL', 'GOOGL', 'TSLA')
            
        Returns:
            Company details and ticker information
        """
        try:
            endpoint = f"/v3/reference/tickers/{symbol.upper()}"
            
            data = await make_polygon_request(endpoint)
            
            if data.get("status") == "OK" and data.get("results"):
                ticker = data["results"]
                
                return f"""
Company: {ticker.get('name', 'N/A')}
Symbol: {ticker.get('ticker', 'N/A')}
Market: {ticker.get('market', 'N/A')}
Primary Exchange: {ticker.get('primary_exchange', 'N/A')}
Type: {ticker.get('type', 'N/A')}
Currency: {ticker.get('currency_name', 'N/A')}
Active: {ticker.get('active', 'N/A')}
Homepage: {ticker.get('homepage_url', 'N/A')}
Description: {ticker.get('description', 'N/A')[:200]}...
Market Cap: ${ticker.get('market_cap', 'N/A'):,} (if available)
"""
            else:
                return f"Error: Could not retrieve details for {symbol}"
                
        except Exception as e:
            return f"Error fetching stock details: {str(e)}"
    
    @mcp.tool("GetStockNews")
    async def get_stock_news(symbol: str, limit: int = 10) -> str:
        """
        Get recent news for a stock symbol.
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL', 'GOOGL', 'TSLA')
            limit: Number of news articles to return (default: 10)
            
        Returns:
            Recent news articles related to the stock
        """
        try:
            endpoint = "/v2/reference/news"
            params = {
                "ticker": symbol.upper(),
                "limit": str(limit),
                "sort": "published_utc",
                "order": "desc"
            }
            
            data = await make_polygon_request(endpoint, params)
            
            if data.get("status") == "OK" and data.get("results"):
                news_items = data["results"]
                result = f"Recent news for {symbol.upper()}:\n\n"
                
                for i, item in enumerate(news_items, 1):
                    title = item.get("title", "N/A")
                    description = item.get("description", "N/A")[:150]
                    author = item.get("author", "N/A")
                    published = item.get("published_utc", "N/A")
                    url = item.get("article_url", "N/A")
                    
                    result += f"{i}. {title}\n"
                    result += f"   Author: {author} | Published: {published}\n"
                    result += f"   Description: {description}...\n"
                    result += f"   URL: {url}\n\n"
                
                return result
            else:
                return f"Error: Could not retrieve news for {symbol}"
                
        except Exception as e:
            return f"Error fetching stock news: {str(e)}"
    
    @mcp.tool("SearchStocks")
    async def search_stocks(query: str, limit: int = 10) -> str:
        """
        Search for stocks by company name or symbol.
        
        Args:
            query: Company name or symbol to search for
            limit: Number of results to return (default: 10)
            
        Returns:
            List of matching stocks with symbols and details
        """
        try:
            endpoint = "/v3/reference/tickers"
            params = {
                "search": query,
                "limit": str(limit),
                "active": "true"
            }
            
            data = await make_polygon_request(endpoint, params)
            
            if data.get("status") == "OK" and data.get("results"):
                matches = data["results"]
                result = f"Search results for '{query}':\n\n"
                
                for i, match in enumerate(matches, 1):
                    symbol = match.get("ticker", "N/A")
                    name = match.get("name", "N/A")
                    market = match.get("market", "N/A")
                    exchange = match.get("primary_exchange", "N/A")
                    
                    result += f"{i}. {symbol} - {name}\n"
                    result += f"   Market: {market} | Exchange: {exchange}\n\n"
                
                return result
            else:
                return f"No results found for '{query}'"
                
        except Exception as e:
            return f"Error searching stocks: {str(e)}"
    
    @mcp.tool("GetMarketStatus")
    async def get_market_status() -> str:
        """
        Get current market status and trading hours.
        
        Returns:
            Market status information
        """
        try:
            endpoint = "/v1/marketstatus/now"
            
            data = await make_polygon_request(endpoint)
            
            if data.get("market") == "open":
                return "🟢 Market is currently OPEN"
            elif data.get("market") == "closed":
                return "🔴 Market is currently CLOSED"
            else:
                return f"Market status: {data.get('market', 'Unknown')}"
                
        except Exception as e:
            return f"Error fetching market status: {str(e)}"
    
    @mcp.tool("GetStockBars")
    async def get_stock_bars(symbol: str, timespan: str = "day", limit: int = 10) -> str:
        """
        Get historical price bars for a stock.
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL', 'GOOGL', 'TSLA')
            timespan: Timespan for bars (minute, hour, day, week, month, quarter, year)
            limit: Number of bars to return (default: 10)
            
        Returns:
            Historical price data
        """
        try:
            # Get date range
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            
            endpoint = f"/v2/aggs/ticker/{symbol.upper()}/range/1/{timespan}/{start_date}/{end_date}"
            params = {"limit": str(limit)}
            
            data = await make_polygon_request(endpoint, params)

            if (data.get("status") == "OK" or data.get("status") == "DELAYED") and data.get("results"):
                bars = data["results"][-limit:]  # Get most recent bars
                result = f"Recent {timespan} bars for {symbol.upper()}:\n\n"
                
                for bar in bars:
                    timestamp = datetime.fromtimestamp(bar["t"] / 1000).strftime('%Y-%m-%d %H:%M')
                    result += f"Date: {timestamp}\n"
                    result += f"Open: ${bar['o']:.2f} | High: ${bar['h']:.2f} | Low: ${bar['l']:.2f} | Close: ${bar['c']:.2f}\n"
                    result += f"Volume: {bar['v']:,} shares\n\n"
                
                return result
            else:
                return f"Error: Could not retrieve bars for {symbol}"
                
        except Exception as e:
            return f"Error fetching stock bars: {str(e)}"