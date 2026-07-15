"""News feed router - real-time market news relevant to traded instruments."""
from fastapi import APIRouter
from datetime import datetime
from typing import List, Dict

from app.services.news_service import news_service

router = APIRouter(prefix="/news", tags=["News"])


# Curated market news - updated periodically
MARKET_NEWS: List[Dict] = [
    {
        "headline": "Gold reclaims $4,000 as geopolitical risk premium persists",
        "source": "FXStreet",
        "category": "Commodities",
        "symbols": ["XAUUSD"],
        "timestamp": "2026-07-01T10:00:00Z",
        "summary": "Gold manages to regain composure and advance past the key $4,000 per troy ounce, reversing two daily drops in a row. US-Iran tensions and Fed hawkish expectations keep safe-haven demand elevated.",
    },
    {
        "headline": "US JOLTS job openings hit two-year high at 7.594 million",
        "source": "Bureau of Labor Statistics",
        "category": "Macro",
        "symbols": ["EURUSD", "USDJPY", "NQ1!", "ES1!"],
        "timestamp": "2026-07-01T08:00:00Z",
        "summary": "The US Job Openings and Labor Turnover Survey showed job openings edged up to 7.594 million in May. Consumer Confidence Index rose to 91.2 in June, reinforcing hawkish Fed expectations.",
    },
    {
        "headline": "CME FedWatch: 80% chance of rate hike by year-end",
        "source": "CME Group",
        "category": "Macro",
        "symbols": ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"],
        "timestamp": "2026-07-01T09:00:00Z",
        "summary": "Traders are assigning over an 80% chance of a Fed rate hike move by the end of this year. Cleveland Fed President Beth Hammack said she may advocate for higher rates if inflation pressures don't moderate.",
    },
    {
        "headline": "NFP report on Thursday to drive market direction",
        "source": "Market Watch",
        "category": "Macro",
        "symbols": ["EURUSD", "USDJPY", "NQ1!", "ES1!", "XAUUSD"],
        "timestamp": "2026-07-01T07:00:00Z",
        "summary": "Market focus shifts to the US monthly Nonfarm Payrolls report on Thursday. ADP private-sector employment and ISM Manufacturing PMI due Wednesday will provide early clues.",
    },
    {
        "headline": "Gold expected to trade at $4,269 by end of quarter",
        "source": "Trading Economics",
        "category": "Commodities",
        "symbols": ["XAUUSD"],
        "timestamp": "2026-07-01T06:00:00Z",
        "summary": "Gold is expected to trade at 4,269.70 USD/t oz by the end of this quarter, according to global macro models. 12-month target is 4,460.56. Gold has fallen 9.10% over the past month but remains 21.56% higher YoY.",
    },
    {
        "headline": "OPEC+ production quotas and inventory reports in focus for oil traders",
        "source": "Energy News",
        "category": "Commodities",
        "symbols": ["CL1!"],
        "timestamp": "2026-06-30T14:00:00Z",
        "summary": "Key news events for oil include OPEC+ meetings where production quotas are set, weekly crude oil inventory reports from the EIA and API, and geopolitical events in oil-producing regions.",
    },
    {
        "headline": "ECB Forum in Sintra: Fed Chair Warsh speech awaited",
        "source": "Reuters",
        "category": "Macro",
        "symbols": ["EURUSD", "GBPUSD"],
        "timestamp": "2026-07-01T09:30:00Z",
        "summary": "Traders are waiting for Fed Chair Kevin Warsh's appearance at the European Central Bank Forum in Sintra. Any hawkish rhetoric could strengthen the USD further against European currencies.",
    },
]


@router.get("/latest")
def get_latest_news(limit: int = 25, relevant_only: bool = False):
    """Real-time market news, tagged with the supported symbols each item can move."""
    news = news_service.get_news(limit=limit)
    if relevant_only:
        news = [n for n in news if n.get("relevant")]
    return {
        "news": news,
        "count": len(news),
        "updated_at": datetime.utcnow().isoformat(),
    }


@router.get("/symbol/{symbol}")
def get_news_for_symbol(symbol: str, limit: int = 25):
    """Return news that can move a specific instrument."""
    symbol = symbol.upper()
    filtered = news_service.get_news(limit=limit, symbol=symbol)
    return {
        "symbol": symbol,
        "news": filtered,
        "count": len(filtered),
        "updated_at": datetime.utcnow().isoformat(),
    }
