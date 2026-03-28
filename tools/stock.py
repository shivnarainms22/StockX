"""
StockX — Stock Analysis Tool (v2)
Full-spectrum investment analysis pipeline:
  Raw data  →  Technical indicators  →  Fundamentals  →  Sentiment/Macro
  →  Risk assessment  →  Trading setup  →  Scored recommendation
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import httpx

# ── Company name → ticker symbol lookup ──────────────────────────────────────
_NAME_TO_TICKER: dict[str, str] = {
    # Tech
    "apple": "AAPL", "microsoft": "MSFT", "nvidia": "NVDA", "google": "GOOGL",
    "alphabet": "GOOGL", "meta": "META", "facebook": "META", "amazon": "AMZN",
    "tesla": "TSLA", "amd": "AMD", "intel": "INTC", "qualcomm": "QCOM",
    "broadcom": "AVGO", "salesforce": "CRM", "oracle": "ORCL", "adobe": "ADBE",
    "palantir": "PLTR", "snowflake": "SNOW", "arm": "ARM", "micron": "MU",
    "crowdstrike": "CRWD", "datadog": "DDOG", "mongodb": "MDB", "servicenow": "NOW",
    "workday": "WDAY", "zscaler": "ZS", "super micro": "SMCI", "supermicro": "SMCI",
    "dell": "DELL", "ibm": "IBM", "hp": "HPE", "hewlett packard": "HPE",
    "netflix": "NFLX", "spotify": "SPOT", "uber": "UBER", "lyft": "LYFT",
    "airbnb": "ABNB", "coinbase": "COIN", "microstrategy": "MSTR",
    # Finance
    "jpmorgan": "JPM", "jp morgan": "JPM", "bank of america": "BAC",
    "wells fargo": "WFC", "goldman sachs": "GS", "morgan stanley": "MS",
    "blackrock": "BLK", "citigroup": "C", "citi": "C", "schwab": "SCHW",
    "american express": "AXP", "amex": "AXP", "visa": "V", "mastercard": "MA",
    "paypal": "PYPL", "square": "SQ", "block": "SQ",
    # Healthcare
    "johnson and johnson": "JNJ", "j&j": "JNJ", "unitedhealth": "UNH",
    "eli lilly": "LLY", "lilly": "LLY", "abbvie": "ABBV", "merck": "MRK",
    "thermo fisher": "TMO", "abbott": "ABT", "danaher": "DHR",
    "bristol myers": "BMY", "amgen": "AMGN", "gilead": "GILD",
    "vertex": "VRTX", "intuitive surgical": "ISRG", "regeneron": "REGN",
    "moderna": "MRNA", "pfizer": "PFE", "novo nordisk": "NVO", "astrazeneca": "AZN",
    # Energy
    "exxon": "XOM", "exxonmobil": "XOM", "chevron": "CVX", "conocophillips": "COP",
    "schlumberger": "SLB", "halliburton": "HAL", "occidental": "OXY",
    # Consumer
    "home depot": "HD", "mcdonalds": "MCD", "mcdonald's": "MCD",
    "nike": "NKE", "starbucks": "SBUX", "target": "TGT", "walmart": "WMT",
    "costco": "COST", "booking": "BKNG", "chipotle": "CMG",
    # Industrials
    "caterpillar": "CAT", "john deere": "DE", "deere": "DE",
    "honeywell": "HON", "lockheed": "LMT", "lockheed martin": "LMT",
    "raytheon": "RTX", "northrop": "NOC", "northrop grumman": "NOC",
    "general electric": "GE", "ge": "GE", "boeing": "BA", "ups": "UPS",
    "fedex": "FDX",
    # Commodities / ETFs
    "gold etf": "GLD", "gold fund": "GLD", "spdr gold": "GLD",
    "silver etf": "SLV", "ishares silver": "SLV",
    "s&p 500": "SPY", "sp500": "SPY", "s&p": "SPY",
    "nasdaq": "QQQ", "dow jones": "DIA", "dow": "DIA",
    "russell 2000": "IWM", "vix": "^VIX",
    "newmont": "NEM", "barrick": "GOLD", "barrick gold": "GOLD",
    "gold miners": "GDX", "junior gold miners": "GDXJ",
    "silver miners": "SIL", "pan american": "PAAS",
    # EV
    "rivian": "RIVN", "lucid": "LCID", "nio": "NIO",
    "general motors": "GM", "ford": "F",
    # Berkshire
    "berkshire": "BRK-B", "berkshire hathaway": "BRK-B",
    "brk": "BRK-B", "brk.b": "BRK-B", "brk.a": "BRK-A",
    # Crypto (Yahoo Finance uses SYMBOL-USD)
    "bitcoin": "BTC-USD", "btc": "BTC-USD",
    "ethereum": "ETH-USD", "eth": "ETH-USD",
    "solana": "SOL-USD", "sol": "SOL-USD",
    "ripple": "XRP-USD", "xrp": "XRP-USD",
    "dogecoin": "DOGE-USD", "doge": "DOGE-USD",
    "cardano": "ADA-USD", "ada": "ADA-USD",
    "avalanche": "AVAX-USD", "avax": "AVAX-USD",
    "chainlink": "LINK-USD", "link": "LINK-USD",
    "polkadot": "DOT-USD", "dot": "DOT-USD",
    "litecoin": "LTC-USD", "ltc": "LTC-USD",
}

def _resolve_ticker(raw: str) -> str:
    """
    Convert a company name or messy input to a valid ticker symbol.
    1. Strip whitespace, try exact ticker match.
    2. Look up in name dictionary.
    3. Fall back to yfinance search.
    """
    cleaned = raw.strip()
    upper   = cleaned.upper()

    # Already looks like a ticker (e.g. AAPL, BRK-B, BTC-USD, ^VIX)
    if re.fullmatch(r"[A-Z0-9\.\-\^]{1,10}", upper):
        return upper

    # Name dictionary lookup (case-insensitive)
    lower = cleaned.lower()
    if lower in _NAME_TO_TICKER:
        return _NAME_TO_TICKER[lower]

    # Partial match — check if any key is contained in the input
    for name, ticker in _NAME_TO_TICKER.items():
        if name in lower:
            return ticker

    # yfinance search fallback
    try:
        import yfinance as yf
        results = yf.Search(cleaned, max_results=1).quotes
        if results:
            return results[0].get("symbol", upper)
    except Exception:
        pass

    # Return uppercased input as last resort
    return upper

from tools.base import BaseTool

logger = logging.getLogger(__name__)

# ── Sector / industry / asset-class universe ──────────────────────────────────
_SECTOR_TICKERS: dict[str, list[str]] = {
    "technology":   ["AAPL","MSFT","NVDA","META","GOOGL","AMZN","AMD","TSLA","AVGO","CRM","ORCL","ADBE","QCOM","MU","PLTR","SNOW","ARM"],
    "healthcare":   ["JNJ","UNH","LLY","ABBV","MRK","TMO","ABT","DHR","BMY","AMGN","GILD","VRTX","ISRG","SYK","REGN"],
    "finance":      ["JPM","BAC","WFC","GS","MS","BLK","C","SCHW","AXP","V","MA","COF","USB","PNC","TFC"],
    "energy":       ["XOM","CVX","COP","EOG","SLB","MPC","PSX","VLO","OXY","HAL","DVN","HES","BKR","FANG"],
    "consumer":     ["HD","MCD","NKE","SBUX","TGT","WMT","COST","LOW","BKNG","CMG","YUM","DG","ROST","TJX"],
    "industrials":  ["CAT","DE","HON","UNP","RTX","LMT","GE","MMM","UPS","FDX","BA","NOC","GD","EMR","ETN"],
    "real_estate":  ["PLD","AMT","EQIX","CCI","PSA","O","WELL","DLR","SPG","AVB","EQR","VTR","BXP","ARE"],
    "utilities":    ["NEE","DUK","SO","D","EXC","AEP","XEL","WEC","ES","ETR","FE","PPL","CMS","NI","AES"],
    "materials":    ["LIN","APD","SHW","FCX","NEM","NUE","VMC","MLM","CF","MOS","ALB","ECL","DD","PPG"],
    "telecom":      ["T","VZ","TMUS","LUMN","DISH"],
    # Industries
    "semiconductors":["NVDA","AMD","INTC","QCOM","AVGO","MU","ARM","TSM","ASML","AMAT","LRCX","KLAC","MRVL","ON","MPWR"],
    "software":     ["MSFT","CRM","ORCL","ADBE","NOW","SNOW","PLTR","WDAY","TEAM","ZS","CRWD","DDOG","MDB","HUBS"],
    "ai":           ["NVDA","MSFT","GOOGL","META","AMD","PLTR","ARM","SMCI","DELL","IBM","SNOW","C3AI"],
    "biotech":      ["MRNA","BNTX","REGN","VRTX","BIIB","GILD","ALNY","BMRN","INCY","ROIV","RXRX","BEAM"],
    "banks":        ["JPM","BAC","WFC","C","USB","PNC","TFC","FITB","RF","HBAN","KEY","CFG","MTB","ZION"],
    "payments":     ["V","MA","PYPL","SQ","FIS","FISV","GPN","AXP","WEX","FOUR"],
    "defense":      ["LMT","RTX","NOC","GD","BA","HII","KTOS","AVAV","LDOS","BAH","SAIC"],
    "ev":           ["TSLA","RIVN","LCID","NIO","LI","XPEV","GM","F","STLA","CHPT","BLNK","EVGO"],
    "retail":       ["WMT","COST","TGT","HD","LOW","AMZN","TJX","ROST","DG","DLTR","KR","SFM","FIVE"],
    "pharma":       ["JNJ","PFE","MRK","ABBV","LLY","BMY","AZN","NVO","GSK","SNY","VTRS"],
    # Commodities
    "gold":         ["GLD","IAU","PHYS","NEM","GOLD","AEM","KGC","AU","GFI","GDX","GDXJ"],
    "silver":       ["SLV","PSLV","SIL","PAAS","AG","MAG","HL","CDE","FSM"],
    "commodities":  ["GLD","SLV","USO","UNG","PDBC","DJP","GSG","NEM","GOLD","FCX","AA"],
    # ETFs
    "etf": [
        "SPY","VOO","IVV","VTI","QQQ","DIA","IWM","VEA","VWO",
        "XLK","XLF","XLV","XLE","XLY","XLP","XLI","XLB","XLU","XLRE",
        "ARKK","ARKG","BOTZ","ICLN","SOXX","SMH","HACK","CIBR",
        "TLT","IEF","BND","HYG","LQD","TIP","VCIT",
        "GLD","SLV","IAU","USO","UNG","PDBC","GDX","GDXJ","SIL",
        "VYM","SCHD","DVY","HDV","DGRO",
        "EFA","EEM","VGK","FXI","EWJ","INDA",
        "IBIT","FBTC","GBTC",
    ],
}
_SECTOR_TICKERS["etfs"]           = _SECTOR_TICKERS["etf"]
_SECTOR_TICKERS["metals"]         = _SECTOR_TICKERS["gold"] + _SECTOR_TICKERS["silver"]
_SECTOR_TICKERS["precious_metals"]= _SECTOR_TICKERS["metals"]
_SECTOR_TICKERS["miners"]         = ["NEM","GOLD","AEM","KGC","AU","GFI","GDX","GDXJ","PAAS","AG","MAG","HL","CDE","FSM","FCX"]
_SECTOR_TICKERS["crypto_related"] = ["COIN","MSTR","RIOT","MARA","CLSK","HUT","IBIT","FBTC","GBTC"]
_equity_sectors = ["technology","healthcare","finance","energy","consumer","industrials","real_estate","utilities","materials","telecom"]
_SECTOR_TICKERS["all"] = list({t for k in _equity_sectors for t in _SECTOR_TICKERS[k]})

_ETF_TICKERS: set[str] = {
    "SPY","VOO","IVV","VTI","QQQ","DIA","IWM","VEA","VWO",
    "XLK","XLF","XLV","XLE","XLY","XLP","XLI","XLB","XLU","XLRE",
    "ARKK","ARKG","BOTZ","ICLN","SOXX","SMH","HACK","CIBR",
    "TLT","IEF","BND","HYG","LQD","TIP","VCIT",
    "GLD","SLV","IAU","PHYS","PSLV","USO","UNG","PDBC","DJP","GSG",
    "CORN","WEAT","SOYB","GDX","GDXJ","SIL",
    "VYM","SCHD","DVY","HDV","DGRO",
    "EFA","EEM","VGK","FXI","EWJ","INDA",
    "IBIT","FBTC","GBTC",
}

# ── Ticker result cache (item 2) ─────────────────────────────────────────────
_ticker_cache: dict[str, tuple[float, str]] = {}  # {ticker: (timestamp, result)}
_TICKER_TTL = 300  # 5 minutes


def clear_ticker_cache(ticker: str | None = None) -> None:
    """Invalidate cache for one ticker or all tickers."""
    if ticker is None:
        _ticker_cache.clear()
    else:
        _ticker_cache.pop(ticker.upper(), None)


# ── Rate-limit-safe yfinance fetch ────────────────────────────────────────────
_yf_lock = threading.Lock()

def _ticker_with_retry(symbol: str, max_tries: int = 4) -> tuple[Any, Any, Any]:
    import yfinance as yf
    last_exc: Exception | None = None
    for attempt in range(max_tries):
        with _yf_lock:
            try:
                stock = yf.Ticker(symbol)
                hist  = stock.history(period="2y")
                info  = stock.info or {}
                time.sleep(0.3)
                return stock, hist, info
            except Exception as exc:
                last_exc = exc
                err = str(exc).lower()
                if "rate limit" in err or "too many" in err or "429" in err:
                    wait = 2 ** attempt
                    logger.warning("Rate limited on %s — retrying in %ds", symbol, wait)
                    time.sleep(wait)
                else:
                    raise
    raise RuntimeError(f"Rate limited after {max_tries} attempts for {symbol}: {last_exc}")

# ── Currency context (thread-local so concurrent analyses don't clash) ─────────
_cur_ctx = threading.local()

_CURRENCY_SYMBOLS: dict[str, str] = {
    "USD": "$",   "CAD": "CA$", "AUD": "A$",  "NZD": "NZ$", "HKD": "HK$",
    "SGD": "S$",  "MXN": "MX$","BRL": "R$",  "GBP": "£",   "EUR": "€",
    "JPY": "¥",   "CNY": "¥",  "CNH": "¥",   "INR": "₹",   "KRW": "₩",
    "CHF": "Fr",  "SEK": "kr", "NOK": "kr",  "DKK": "kr",  "ZAR": "R",
    "TRY": "₺",   "ILS": "₪",  "TWD": "NT$", "THB": "฿",   "MYR": "RM",
    "IDR": "Rp",  "PHP": "₱",  "VND": "₫",
}
_ZERO_DECIMAL: frozenset[str] = frozenset({"JPY", "KRW", "VND", "IDR"})

# Ticker suffix → currency fallback (used when yfinance info["currency"] is missing)
_SUFFIX_CURRENCY: dict[str, str] = {
    # Asia-Pacific
    ".NS": "INR", ".BO": "INR",          # India NSE / BSE
    ".T":  "JPY", ".OS": "JPY",          # Japan TSE / OSE
    ".KS": "KRW", ".KQ": "KRW",          # Korea KOSPI / KOSDAQ
    ".SS": "CNY", ".SZ": "CNY",          # China Shanghai / Shenzhen
    ".HK": "HKD",                        # Hong Kong
    ".TW": "TWD", ".TWO": "TWD",         # Taiwan
    ".SI": "SGD",                        # Singapore
    ".AX": "AUD",                        # Australia ASX
    ".NZ": "NZD",                        # New Zealand
    ".BK": "THB",                        # Thailand
    ".KL": "MYR",                        # Malaysia
    ".JK": "IDR",                        # Indonesia
    ".PS": "PHP",                        # Philippines
    # Europe
    ".L":  "GBP", ".IL": "GBP",         # UK LSE
    ".PA": "EUR", ".DE": "EUR",          # France / Germany
    ".MI": "EUR", ".AS": "EUR",          # Italy / Netherlands
    ".BR": "EUR", ".MC": "EUR",          # Belgium / Spain
    ".LS": "EUR", ".IR": "EUR",          # Portugal / Ireland
    ".AT": "EUR", ".HE": "EUR",          # Greece / Finland
    ".SW": "CHF",                        # Switzerland
    ".ST": "SEK", ".OL": "NOK",         # Sweden / Norway
    ".CO": "DKK",                        # Denmark
    ".IS": "TRY",                        # Turkey
    ".TA": "ILS",                        # Israel
    # Americas
    ".TO": "CAD", ".V":  "CAD",         # Canada TSX / TSX-V
    ".SA": "BRL",                        # Brazil
    ".MX": "MXN",                        # Mexico
    # Africa / Middle East
    ".JO": "ZAR",                        # South Africa
}

def _currency_from_ticker(ticker: str) -> str:
    """Infer currency from the ticker suffix (e.g. INFY.NS → INR)."""
    upper = ticker.upper()
    # Try longest suffix match first
    for suffix in sorted(_SUFFIX_CURRENCY, key=len, reverse=True):
        if upper.endswith(suffix.upper()):
            return _SUFFIX_CURRENCY[suffix]
    return "USD"  # default for US markets (no suffix)

def _set_currency(code: str | None, ticker: str = "") -> None:
    """Set thread-local currency. Falls back to ticker-suffix inference if code is missing."""
    if code and code.upper() not in ("", "USD") or (code and not ticker):
        _cur_ctx.code = code.upper()
    elif code and code.upper() == "USD" and ticker:
        # yfinance sometimes reports USD for non-USD stocks — cross-check with suffix
        inferred = _currency_from_ticker(ticker)
        _cur_ctx.code = inferred if inferred != "USD" else "USD"
    else:
        _cur_ctx.code = _currency_from_ticker(ticker) if ticker else "USD"

def _cur() -> str:
    return getattr(_cur_ctx, "code", "USD")

def _sym() -> str:
    return _CURRENCY_SYMBOLS.get(_cur(), f"{_cur()} ")

# ── Formatting helpers ─────────────────────────────────────────────────────────
def _p(v: float | None, mult: bool = True) -> str:
    if v is None: return "N/A"
    val = v * 100 if mult else v
    return f"+{val:.1f}%" if val > 0 else f"{val:.1f}%"

def _pp(v: float | None) -> str:
    """Format already-percentage value."""
    return _p(v, mult=False)

def _price(v: float | None) -> str:
    if v is None: return "N/A"
    s = _sym()
    return f"{s}{v:,.0f}" if _cur() in _ZERO_DECIMAL else f"{s}{v:,.2f}"

def _mcap(v: float | None) -> str:
    if v is None: return "N/A"
    s = _sym()
    if v >= 1e12: return f"{s}{v/1e12:.2f}T"
    if v >= 1e9:  return f"{s}{v/1e9:.2f}B"
    return f"{s}{v/1e6:.2f}M"

def _n(v: float | None, dec: int = 2) -> str:
    return f"{v:.{dec}f}" if v is not None else "N/A"

# ── Technical indicator calculators ──────────────────────────────────────────

def _calc_atr(hist: Any, period: int = 14) -> float:
    high, low, close = hist["High"], hist["Low"], hist["Close"]
    prev_close = close.shift(1)
    tr = (high - low).combine(
        (high - prev_close).abs(), max
    ).combine((low - prev_close).abs(), max)
    return float(tr.rolling(period).mean().iloc[-1])

def _calc_adx(hist: Any, period: int = 14) -> tuple[float, float, float]:
    """Returns (ADX, +DI, -DI)."""
    high, low, close = hist["High"], hist["Low"], hist["Close"]
    prev_high = high.shift(1); prev_low = low.shift(1); prev_close = close.shift(1)
    up_move   = high - prev_high
    down_move = prev_low - low
    plus_dm  = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    tr = (high - low).combine((high - prev_close).abs(), max).combine((low - prev_close).abs(), max)
    atr      = tr.ewm(span=period, adjust=False).mean()
    plus_di  = 100 * plus_dm.ewm(span=period, adjust=False).mean() / atr
    minus_di = 100 * minus_dm.ewm(span=period, adjust=False).mean() / atr
    dx  = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.ewm(span=period, adjust=False).mean()
    return float(adx.iloc[-1]), float(plus_di.iloc[-1]), float(minus_di.iloc[-1])

def _calc_stochastic(hist: Any, k_period: int = 14, d_period: int = 3) -> tuple[float, float]:
    low_min  = hist["Low"].rolling(k_period).min()
    high_max = hist["High"].rolling(k_period).max()
    k = 100 * (hist["Close"] - low_min) / (high_max - low_min)
    d = k.rolling(d_period).mean()
    return float(k.iloc[-1]), float(d.iloc[-1])

def _calc_roc(hist: Any, period: int = 14) -> float:
    close = hist["Close"]
    return float((close.iloc[-1] - close.iloc[-period]) / close.iloc[-period] * 100) if len(hist) >= period else 0.0

def _calc_obv(hist: Any) -> tuple[float, float]:
    """Returns (latest OBV, OBV 20-day SMA). Positive divergence = bullish."""
    close  = hist["Close"]
    volume = hist["Volume"]
    direction = close.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    obv = (volume * direction).cumsum()
    return float(obv.iloc[-1]), float(obv.rolling(20).mean().iloc[-1])

def _calc_vwap(hist: Any) -> float:
    """VWAP over the full dataset (used as trend reference)."""
    typical = (hist["High"] + hist["Low"] + hist["Close"]) / 3
    return float((typical * hist["Volume"]).sum() / hist["Volume"].sum())

def _find_support_resistance(hist: Any, lookback: int = 60) -> tuple[float, float]:
    """Find nearest support (recent swing low) and resistance (recent swing high)."""
    recent = hist.tail(lookback)
    current = float(hist["Close"].iloc[-1])
    highs = recent["High"].values
    lows  = recent["Low"].values
    # Swing highs / lows: local peaks/troughs in a 5-bar window
    swing_highs = [highs[i] for i in range(2, len(highs)-2)
                   if highs[i] == max(highs[i-2:i+3])]
    swing_lows  = [lows[i]  for i in range(2, len(lows)-2)
                   if lows[i]  == min(lows[i-2:i+3])]
    resistance = min((h for h in swing_highs if h > current), default=float(recent["High"].max()))
    support    = max((l for l in swing_lows  if l < current), default=float(recent["Low"].min()))
    return support, resistance

def _calc_fibonacci(high: float, low: float) -> dict[str, float]:
    rng = high - low
    return {
        "23.6%": high - 0.236 * rng,
        "38.2%": high - 0.382 * rng,
        "50.0%": high - 0.500 * rng,
        "61.8%": high - 0.618 * rng,
        "78.6%": high - 0.786 * rng,
    }

# ── Macro context (TTL cache — refreshes every 5 minutes) ────────────────────
_macro_cache: dict | None = None
_macro_cache_ts: float    = 0.0
_macro_lock  = threading.Lock()
_MACRO_TTL   = 300  # seconds

def _fetch_macro() -> dict:
    global _macro_cache, _macro_cache_ts
    with _macro_lock:
        if _macro_cache is not None and (time.time() - _macro_cache_ts) < _MACRO_TTL:
            return _macro_cache
    try:
        import yfinance as yf
        result: dict[str, Any] = {}

        # VIX — fear gauge
        vix_hist = yf.Ticker("^VIX").history(period="5d")
        result["vix"] = float(vix_hist["Close"].iloc[-1]) if not vix_hist.empty else None

        # US Dollar Index
        dxy_hist = yf.Ticker("DX=F").history(period="5d")
        result["dxy"] = float(dxy_hist["Close"].iloc[-1]) if not dxy_hist.empty else None

        # Yield curve: 10Y minus 2Y spread
        t10 = yf.Ticker("^TNX").history(period="5d")
        t2  = yf.Ticker("^IRX").history(period="5d")
        y10 = float(t10["Close"].iloc[-1]) if not t10.empty else None
        y2  = float(t2["Close"].iloc[-1]) if not t2.empty else None   # both ^TNX and ^IRX quote in % points
        if y10 is not None and y2 is not None:
            result["yield_10y"] = y10
            result["yield_2y"]  = y2
            result["yield_spread"] = y10 - y2
        else:
            result["yield_10y"] = y10
            result["yield_2y"]  = None
            result["yield_spread"] = None

        # Fear & Greed Index (CNN)
        try:
            resp = httpx.get(
                "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=8,
            )
            fg_data = resp.json()
            fg = fg_data.get("fear_and_greed", {})
            result["fear_greed_score"]  = fg.get("score")
            result["fear_greed_rating"] = fg.get("rating", "")
        except Exception:
            result["fear_greed_score"]  = None
            result["fear_greed_rating"] = ""

        with _macro_lock:
            _macro_cache    = result
            _macro_cache_ts = time.time()
        return result
    except Exception as exc:
        logger.warning("Macro context fetch failed: %s", exc)
        return {}


# ── Main tool class ───────────────────────────────────────────────────────────

class StockTool(BaseTool):
    name = "stock"
    description = (
        "Full-spectrum stock/ETF/commodity analysis. "
        "Covers OHLC price data, ATR, ADX, Stochastic, ROC, OBV, VWAP, "
        "support/resistance, Fibonacci levels, RSI, MACD, Bollinger Bands, "
        "fundamentals (P/E, P/S, EV/EBITDA, P/B, PEG, ROE, FCF, cash runway), "
        "institutional/insider activity, macro context (VIX, DXY, yield curve, Fear & Greed), "
        "earnings dates, risk assessment, and a complete trading setup "
        "(entry zone, stop-loss based on ATR, price target, position sizing). "
        "Actions: "
        "'analyse' — deep analysis of specific ticker(s); "
        "'screen'  — scan a sector/industry/asset class for top candidates; "
        "'report'  — full investment report: screen + deep analysis. "
        "Sectors: technology, healthcare, finance, energy, consumer, industrials, "
        "real_estate, utilities, materials, telecom, semiconductors, software, ai, "
        "biotech, banks, payments, defense, ev, retail, pharma, "
        "gold, silver, commodities, metals, miners, etf/etfs, crypto_related, all."
    )
    parameters = {
        "action":   "string — one of: analyse | screen | report",
        "tickers":  "string or list — e.g. 'NVDA' or ['AAPL','GLD','SPY']",
        "sector":   "string (optional) — sector/industry/asset class to screen. Default: all",
        "top_n":    "integer (optional) — top stocks to return (default 5)",
    }

    # ── Entry point ───────────────────────────────────────────────────────────

    async def run(self, params: dict[str, Any]) -> str:
        action = params.get("action", "screen").lower()
        loop   = asyncio.get_event_loop()

        if action == "analyse":
            raw = params.get("tickers", "")
            raw_list = (
                [str(t).strip() for t in raw if str(t).strip()]
                if isinstance(raw, list)
                else [t.strip() for t in str(raw).split(",") if t.strip()]
            )
            tickers = [_resolve_ticker(t) for t in raw_list]
            if not tickers:
                return "Error: 'tickers' required. E.g. tickers='AAPL' or ['AAPL','NVDA']"
            return await loop.run_in_executor(None, self._analyse_multiple, tickers[:5])

        if action == "screen":
            sector = params.get("sector", "all").lower()
            top_n  = int(params.get("top_n", 5))
            return await loop.run_in_executor(None, self._screen, sector, top_n)

        if action == "report":
            sector = params.get("sector", "all").lower()
            top_n  = int(params.get("top_n", 5))
            return await loop.run_in_executor(None, self._full_report, sector, top_n)

        return f"Unknown action '{action}'. Use: analyse | screen | report"

    # ── Screening ─────────────────────────────────────────────────────────────

    def _screen(self, sector: str, top_n: int) -> str:
        universe = _SECTOR_TICKERS.get(sector, _SECTOR_TICKERS["all"])

        def _score_one(ticker: str) -> dict | None:
            try:
                stock, hist, info = _ticker_with_retry(ticker)
                if hist.empty or len(hist) < 50:
                    return None
                price = float(hist["Close"].iloc[-1])
                score = 0

                ma200 = float(hist["Close"].tail(200).mean()) if len(hist) >= 200 else float(hist["Close"].mean())
                if price > ma200: score += 2

                ret_1y = (price - float(hist["Close"].iloc[0])) / float(hist["Close"].iloc[0])
                score += 3 if ret_1y > 0.20 else (2 if ret_1y > 0.10 else (1 if ret_1y > 0 else 0))

                if len(hist) >= 66:
                    ret_3m = (price - float(hist["Close"].iloc[-66])) / float(hist["Close"].iloc[-66])
                    score += 2 if ret_3m > 0.10 else (1 if ret_3m > 0.05 else 0)
                else:
                    ret_3m = 0.0

                delta = hist["Close"].diff()
                rsi   = float((100 - 100 / (1 + delta.clip(lower=0).rolling(14).mean() /
                               (-delta.clip(upper=0)).rolling(14).mean())).iloc[-1])
                score += 2 if 40 <= rsi <= 65 else (1 if rsi < 38 else 0)

                try: adx, pdi, mdi = _calc_adx(hist)
                except Exception: adx, pdi, mdi = 0, 0, 0
                if adx > 25 and pdi > mdi: score += 2

                rec    = info.get("recommendationMean") or 3
                target = info.get("targetMeanPrice")
                upside = (target - price) / price if target and price else None
                score += 3 if rec <= 1.8 else (2 if rec <= 2.2 else (1 if rec <= 2.5 else 0))
                score += 2 if upside and upside > 0.20 else (1 if upside and upside > 0.10 else 0)

                rev_g  = info.get("revenueGrowth") or 0
                earn_g = info.get("earningsGrowth") or 0
                score += 2 if rev_g > 0.15 else (1 if rev_g > 0.05 else 0)
                score += 2 if earn_g > 0.15 else (1 if earn_g > 0.05 else 0)

                inst = info.get("heldPercentInstitutions") or 0
                if inst > 0.70: score += 1

                if ticker.upper() not in _ETF_TICKERS:
                    short_pct = info.get("shortPercentOfFloat") or 0
                    if short_pct > 0.15: score -= 2

                fcf = info.get("freeCashflow") or 0
                if fcf > 0: score += 1

                return {
                    "ticker": ticker, "name": info.get("longName", ticker),
                    "score": score, "price": price, "rsi": rsi, "adx": adx,
                    "ret_1y": ret_1y, "ret_3m": ret_3m, "rec": rec,
                    "rev_g": rev_g, "inst": inst, "upside": upside,
                    "sector_s": info.get("sector", "N/A"),
                }
            except Exception as exc:
                logger.debug("Screen failed for %s: %s", ticker, exc)
                return None

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(_score_one, t): t for t in universe}
            candidates = [f.result() for f in as_completed(futures) if f.result()]

        candidates.sort(key=lambda x: x["score"], reverse=True)
        top = candidates[:top_n]
        if not top:
            return "No stocks passed screening. Try a different sector or check your connection."

        from datetime import datetime
        lines = [
            f"TOP {top_n} PICKS — {sector.upper()}  |  Data fetched: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "=" * 80,
            f"{'#':<3} {'Ticker':<7} {'Name':<26} {'Score':<6} {'RSI':<6} {'ADX':<6} {'1Y':<8} {'3M':<8} {'Upside':<8}",
            "-" * 80,
        ]
        for i, s in enumerate(top, 1):
            upside_s = _p(s["upside"]) if s["upside"] else "N/A"
            lines.append(
                f"{i:<3} {s['ticker']:<7} {s['name'][:25]:<26} {s['score']:<6} "
                f"{s['rsi']:<6.1f} {s['adx']:<6.1f} {_p(s['ret_1y']):<8} "
                f"{_p(s['ret_3m']):<8} {upside_s:<8}"
            )
        lines.append(f"\nUse action='analyse' with tickers={[s['ticker'] for s in top]} for full analysis.")
        return "\n".join(lines)

    # ── Full report ───────────────────────────────────────────────────────────

    def _full_report(self, sector: str, top_n: int) -> str:
        screen = self._screen(sector, top_n)
        tickers = re.findall(r"\b([A-Z]{2,5})\b", screen)
        seen: set[str] = set()
        ordered: list[str] = []
        for t in tickers:
            if t not in seen and t not in _SECTOR_TICKERS and t not in ("N","A","TOP","USE"):
                seen.add(t); ordered.append(t)
        ordered = ordered[:top_n]
        if not ordered:
            return screen
        header = ["=" * 70, f"  AGENTX FULL INVESTMENT REPORT — {sector.upper()}", "=" * 70, "", screen, "", "=" * 70, "  DETAILED ANALYSIS", "=" * 70]
        deep = self._analyse_multiple(ordered)
        return "\n".join(header) + "\n\n" + deep

    # ── ETF analysis ──────────────────────────────────────────────────────────

    def _analyse_etf(self, ticker: str, stock: Any, hist: Any, info: dict, macro: dict) -> str:
        if hist.empty:
            return f"No data found for ETF {ticker}."

        _set_currency(info.get("currency"), ticker)
        price    = float(hist["Close"].iloc[-1])
        name     = info.get("longName") or info.get("shortName") or ticker
        category = info.get("category") or info.get("fundFamily") or "N/A"
        aum      = info.get("totalAssets")
        expense  = info.get("annualReportExpenseRatio") or info.get("expenseRatio")
        div_yield= info.get("yield") or info.get("dividendYield")
        beta     = info.get("beta") or info.get("beta3Year")

        def _ret(n: int) -> float | None:
            return (price - float(hist["Close"].iloc[-n])) / float(hist["Close"].iloc[-n]) if len(hist) >= n else None

        ret_1m = _ret(22); ret_3m = _ret(66); ret_6m = _ret(132)
        ret_1y = _ret(252); ret_2y = (price - float(hist["Close"].iloc[0])) / float(hist["Close"].iloc[0])
        high_52w = float(hist["High"].tail(252).max()); low_52w = float(hist["Low"].tail(252).min())
        pct_hi   = (price - high_52w) / high_52w;      pct_lo  = (price - low_52w) / low_52w

        ma20  = float(hist["Close"].rolling(20).mean().iloc[-1])
        ma50  = float(hist["Close"].rolling(50).mean().iloc[-1])
        ma200 = float(hist["Close"].rolling(200).mean().iloc[-1])
        delta = hist["Close"].diff()
        rsi   = float((100 - 100 / (1 + delta.clip(lower=0).rolling(14).mean() /
                       (-delta.clip(upper=0)).rolling(14).mean())).iloc[-1])
        ema12 = hist["Close"].ewm(span=12, adjust=False).mean()
        ema26 = hist["Close"].ewm(span=26, adjust=False).mean()
        macd_bull = float((ema12 - ema26).iloc[-1]) > float((ema12 - ema26).ewm(span=9).mean().iloc[-1])
        atr   = _calc_atr(hist)
        try: adx, pdi, mdi = _calc_adx(hist)
        except: adx, pdi, mdi = 0, 0, 0
        stoch_k, stoch_d = _calc_stochastic(hist)
        roc   = _calc_roc(hist)
        obv, obv_ma = _calc_obv(hist)
        vwap  = _calc_vwap(hist)
        ann_vol = float(hist["Close"].pct_change().dropna().std() * 252**0.5)
        avg_vol = float(hist["Volume"].tail(30).mean())
        vol_ratio = float(hist["Volume"].iloc[-1]) / avg_vol if avg_vol > 0 else 1.0
        support, resistance = _find_support_resistance(hist)
        fibs = _calc_fibonacci(high_52w, low_52w)

        score = 0; sigs: list[str] = []
        if price > ma200: score += 3; sigs.append("Above 200-day MA — long-term uptrend confirmed")
        else: sigs.append("Below 200-day MA — long-term trend broken")
        if price > ma50:  score += 2; sigs.append("Above 50-day MA — medium-term momentum positive")
        if price > ma20:  score += 1; sigs.append("Above 20-day MA — short-term uptrend")
        if price > vwap:  score += 1; sigs.append(f"Above VWAP ({_price(vwap)}) — bullish bias")
        if macd_bull:     score += 2; sigs.append("MACD bullish crossover")
        if adx > 25 and pdi > mdi: score += 2; sigs.append(f"ADX {adx:.1f} >25 with +DI>{_n(pdi,1)} > -DI{_n(mdi,1)} — strong uptrend")
        elif adx > 25:             sigs.append(f"ADX {adx:.1f} — strong trend but bearish direction")
        if 40 <= rsi <= 65:  score += 2; sigs.append(f"RSI {rsi:.1f} — healthy momentum zone")
        elif rsi < 35:       score += 1; sigs.append(f"RSI {rsi:.1f} — oversold, potential bounce")
        elif rsi > 72:       score -= 1; sigs.append(f"RSI {rsi:.1f} — overbought, caution")
        if stoch_k > stoch_d and stoch_k < 80: score += 1; sigs.append(f"Stochastic %K {stoch_k:.1f} > %D {stoch_d:.1f} — bullish crossover")
        if obv > obv_ma: score += 1; sigs.append("OBV above its MA — volume confirming price trend")
        else:            sigs.append("OBV below its MA — volume divergence, watch carefully")
        if vol_ratio > 1.5: score += 1; sigs.append(f"Volume {vol_ratio:.1f}x average — strong participation")
        if ret_1y and ret_1y > 0.20: score += 3; sigs.append(f"Strong 1-year return {_p(ret_1y)}")
        elif ret_1y and ret_1y > 0:  score += 1; sigs.append(f"Positive 1-year return {_p(ret_1y)}")
        elif ret_1y and ret_1y < -0.20: score -= 2; sigs.append(f"Poor 1-year return {_p(ret_1y)}")
        if ann_vol < 0.15: score += 1; sigs.append(f"Low volatility {_pp(ann_vol*100)} — stable")
        elif ann_vol > 0.40: sigs.append(f"High volatility {_pp(ann_vol*100)} — wide swings")

        if score >= 15: rating = "STRONG BUY"
        elif score >= 10: rating = "BUY"
        elif score >= 6:  rating = "WATCH / HOLD"
        elif score >= 2:  rating = "CAUTION"
        else:             rating = "AVOID"

        # Trading setup
        stop_loss = max(support, price - 2 * atr)
        risk_per_share = price - stop_loss
        port_1pct = 10000 * 0.01  # assume $10k portfolio for illustration
        pos_size  = int(port_1pct / risk_per_share) if risk_per_share > 0 else 0

        # News
        news_lines: list[str] = []
        try:
            for item in (stock.news or [])[:5]:
                c = item.get("content", {})
                title = c.get("title") or item.get("title","")
                src   = (c.get("provider",{}).get("displayName","") if isinstance(c.get("provider"),dict) else item.get("publisher",""))
                if title: news_lines.append(f"  • {title}" + (f" [{src}]" if src else ""))
        except Exception: pass

        fib_lines = "  " + "  |  ".join(f"{k}: {_price(v)}" for k, v in fibs.items())

        lines = [
            "=" * 70,
            f"  {name} ({ticker}) — ETF / FUND",
            f"  RATING: {rating}   (Score: {score})",
            "=" * 70,
            f"  Category: {category}  |  AUM: {_mcap(aum)}  |  Expense: {f'{expense*100:.3f}%' if expense else 'N/A'}",
            f"  Yield: {_p(div_yield)}  |  Beta: {_n(beta)}",
            "",
            "── PRICE & VOLUME " + "─"*52,
            f"  Current Price:    {_price(price)}  |  VWAP: {_price(vwap)}  ({'Above' if price > vwap else 'Below'})",
            f"  52W High: {_price(high_52w)} ({_pp(pct_hi*100)} from high)  |  52W Low: {_price(low_52w)} (+{_pp(pct_lo*100)} from low)",
            f"  ATR (14):  {_price(atr)}  ({_pp(atr/price*100)} of price — volatility measure)",
            f"  Volume vs 30d avg: {vol_ratio:.2f}x  |  Ann. Volatility: {_pp(ann_vol*100)}",
            "",
            "── RETURNS (MULTI-TIMEFRAME) " + "─"*42,
            f"  1-Month: {_p(ret_1m):<10}  3-Month: {_p(ret_3m):<10}  6-Month: {_p(ret_6m)}",
            f"  1-Year:  {_p(ret_1y):<10}  2-Year:  {_p(ret_2y)}",
            "",
            "── TECHNICAL INDICATORS " + "─"*46,
            f"  RSI (14):          {rsi:.1f}  {'(healthy)' if 40<=rsi<=65 else ('(overbought)' if rsi>70 else '(oversold)')}",
            f"  Stochastic %K/%D:  {stoch_k:.1f} / {stoch_d:.1f}  ({'Bullish' if stoch_k>stoch_d else 'Bearish'})",
            f"  MACD:              {'Bullish crossover' if macd_bull else 'Bearish — below signal line'}",
            f"  ADX:               {adx:.1f}  ({'Strong trend' if adx>25 else 'Weak/no trend'})  +DI: {pdi:.1f}  -DI: {mdi:.1f}",
            f"  ROC (14):          {roc:+.2f}%",
            f"  OBV vs OBV-MA:     {'Positive — buying pressure' if obv > obv_ma else 'Negative — selling pressure'}",
            f"  20-Day MA: {_price(ma20)} ({'ABOVE' if price>ma20 else 'BELOW'})  |  50-Day: {_price(ma50)} ({'ABOVE' if price>ma50 else 'BELOW'})  |  200-Day: {_price(ma200)} ({'ABOVE' if price>ma200 else 'BELOW'})",
            "",
            "── SUPPORT / RESISTANCE & FIBONACCI " + "─"*35,
            f"  Key Support:    {_price(support)}  |  Key Resistance: {_price(resistance)}",
            f"  Fibonacci Retracements (52W High→Low):",
            fib_lines,
        ]

        if macro:
            vix = macro.get("vix"); dxy = macro.get("dxy")
            fg_s = macro.get("fear_greed_score"); fg_r = macro.get("fear_greed_rating","")
            spread = macro.get("yield_spread")
            lines += [
                "",
                "── MACRO CONTEXT " + "─"*54,
                f"  VIX:            {_n(vix,1)} ({'Fear elevated' if vix and vix>25 else ('Complacency' if vix and vix<15 else 'Neutral')})",
                f"  Fear & Greed:   {_n(fg_s,0)} / 100  [{fg_r.upper()}]" if fg_s else "  Fear & Greed:   N/A",
                f"  DXY (Dollar):   {_n(dxy,2)}  ({'Strong USD — headwind for risk assets' if dxy and dxy>103 else 'USD neutral/weak'})",
                f"  Yield Curve:    {'INVERTED — recession risk elevated' if spread and spread < 0 else f'Normal (+{spread:.2f}% spread)' if spread else 'N/A'}",
            ]

        lines += [
            "",
            "── TRADING SETUP " + "─"*54,
            f"  Entry Zone:     {_price(support)} – {_price(price)}",
            f"  Stop Loss:      {_price(stop_loss)}  (2×ATR below or key support)",
            f"  Risk/Share:     {_price(risk_per_share)}",
            f"  Position Size:  ~{pos_size} shares for 1% portfolio risk on $10k",
            f"  Key Resistance: {_price(resistance)}  (first target)",
        ]

        lines += ["", "── SIGNALS SUMMARY " + "─"*51]
        lines += [f"  • {s}" for s in sigs]

        if news_lines:
            lines += ["", "── RECENT NEWS " + "─"*55] + news_lines

        lines += ["", f"  VERDICT: {rating}", "=" * 70]
        return "\n".join(lines)

    # ── Deep stock analysis ───────────────────────────────────────────────────

    def _analyse_multiple(self, tickers: list[str]) -> str:
        from datetime import datetime
        # Fetch macro once for all tickers
        macro = _fetch_macro()
        sep = "\n\n" + "=" * 70 + "\n\n"
        header = f"Data fetched: {datetime.now().strftime('%Y-%m-%d %H:%M')} (prices delayed up to 15 min)\n"

        if len(tickers) == 1:
            return header + self._analyse_ticker(tickers[0], macro)

        # Parallel execution for multiple tickers (item 4)
        # _ticker_with_retry uses _yf_lock to serialise yfinance calls;
        # post-fetch computation runs concurrently.
        from concurrent.futures import ThreadPoolExecutor, as_completed as _as_completed
        results: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(self._analyse_ticker, t, macro): t for t in tickers}
            for fut in _as_completed(futures):
                t = futures[fut]
                try:
                    results[t] = fut.result()
                except Exception as exc:
                    results[t] = f"Error analysing {t}: {exc}"
        return header + sep.join(results.get(t, "") for t in tickers)

    def _analyse_ticker(self, ticker: str, macro: dict | None = None) -> str:
        if macro is None:
            macro = _fetch_macro()

        # Cache check (item 2)
        now = time.time()
        if ticker in _ticker_cache:
            cache_ts, cached_result = _ticker_cache[ticker]
            if now - cache_ts < _TICKER_TTL:
                return cached_result

        try:
            stock, hist, info = _ticker_with_retry(ticker)
            if hist.empty:
                return f"No price data for {ticker}. Check the ticker symbol."

            # Set currency context for all _price() / _mcap() calls below
            _set_currency(info.get("currency"), ticker)

            # Route ETFs
            is_etf = (ticker.upper() in _ETF_TICKERS) or (info.get("quoteType","").upper() == "ETF")
            if is_etf:
                return self._analyse_etf(ticker, stock, hist, info, macro)

            # ── Price data ────────────────────────────────────────────────
            price = float(hist["Close"].iloc[-1])

            def _ret(n: int) -> float | None:
                return (price - float(hist["Close"].iloc[-n])) / float(hist["Close"].iloc[-n]) if len(hist) >= n else None

            ret_1m = _ret(22); ret_3m = _ret(66); ret_6m = _ret(132); ret_1y = _ret(252)
            ret_2y = (price - float(hist["Close"].iloc[0])) / float(hist["Close"].iloc[0])
            high_52w = float(hist["High"].tail(252).max()); low_52w = float(hist["Low"].tail(252).min())
            pct_hi   = (price - high_52w) / high_52w;      pct_lo  = (price - low_52w)  / low_52w

            # Weekly trend (zoom out)
            try:
                import yfinance as yf
                whist = yf.Ticker(ticker).history(period="2y", interval="1wk")
                wma20 = float(whist["Close"].rolling(20).mean().iloc[-1]) if len(whist) >= 20 else None
                weekly_trend = "Uptrend" if (wma20 and price > wma20) else "Downtrend"
            except Exception:
                wma20 = None; weekly_trend = "N/A"

            # ── Technical indicators ──────────────────────────────────────
            ma20  = float(hist["Close"].rolling(20).mean().iloc[-1])
            ma50  = float(hist["Close"].rolling(50).mean().iloc[-1])
            ma200 = float(hist["Close"].rolling(200).mean().iloc[-1])
            ema20 = float(hist["Close"].ewm(span=20, adjust=False).mean().iloc[-1])
            ema50 = float(hist["Close"].ewm(span=50, adjust=False).mean().iloc[-1])

            delta = hist["Close"].diff()
            gain  = delta.clip(lower=0).rolling(14).mean()
            loss  = (-delta.clip(upper=0)).rolling(14).mean()
            rsi   = float((100 - 100 / (1 + gain / loss)).iloc[-1])

            ema12 = hist["Close"].ewm(span=12, adjust=False).mean()
            ema26 = hist["Close"].ewm(span=26, adjust=False).mean()
            macd_line   = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            macd_val    = float(macd_line.iloc[-1])
            sig_val     = float(signal_line.iloc[-1])
            macd_bull   = macd_val > sig_val
            macd_hist   = macd_val - sig_val

            atr = _calc_atr(hist)
            try: adx, pdi, mdi = _calc_adx(hist)
            except: adx, pdi, mdi = 0.0, 0.0, 0.0
            stoch_k, stoch_d = _calc_stochastic(hist)
            roc  = _calc_roc(hist)
            obv, obv_ma = _calc_obv(hist)
            vwap = _calc_vwap(hist)

            bb_mid   = hist["Close"].rolling(20).mean()
            bb_std   = hist["Close"].rolling(20).std()
            bb_upper = float((bb_mid + 2*bb_std).iloc[-1])
            bb_lower = float((bb_mid - 2*bb_std).iloc[-1])
            bb_pct   = (price - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5

            avg_vol   = float(hist["Volume"].tail(30).mean())
            vol_ratio = float(hist["Volume"].iloc[-1]) / avg_vol if avg_vol > 0 else 1.0
            ann_vol   = float(hist["Close"].pct_change().dropna().std() * 252**0.5)

            support, resistance = _find_support_resistance(hist)
            fibs = _calc_fibonacci(high_52w, low_52w)

            # ── Fundamentals ──────────────────────────────────────────────
            pe_trail  = info.get("trailingPE")
            pe_fwd    = info.get("forwardPE")
            peg       = info.get("pegRatio")
            ps        = info.get("priceToSalesTrailing12Months")
            pb        = info.get("priceToBook")
            ev_ebitda = info.get("enterpriseToEbitda")
            mktcap    = info.get("marketCap")
            rev_growth= info.get("revenueGrowth")
            earn_growth=info.get("earningsGrowth")
            profit_mg = info.get("profitMargins")
            gross_mg  = info.get("grossMargins")
            roe       = info.get("returnOnEquity")
            roa       = info.get("returnOnAssets")
            debt_eq   = info.get("debtToEquity")
            cur_ratio = info.get("currentRatio")
            fcf       = info.get("freeCashflow")
            total_cash= info.get("totalCash")
            total_debt= info.get("totalDebt")
            op_cf     = info.get("operatingCashflow")
            eps_trail = info.get("trailingEps")
            eps_fwd   = info.get("forwardEps")
            div_yield = info.get("dividendYield")
            beta      = info.get("beta")
            shares    = info.get("sharesOutstanding")

            # Cash runway (quarters) — for unprofitable companies
            if op_cf and op_cf < 0 and total_cash:
                quarterly_burn = abs(op_cf) / 4
                cash_runway_q  = total_cash / quarterly_burn if quarterly_burn > 0 else None
            else:
                cash_runway_q = None

            # ── Analyst & ownership ───────────────────────────────────────
            tgt_price   = info.get("targetMeanPrice")
            tgt_high    = info.get("targetHighPrice")
            tgt_low     = info.get("targetLowPrice")
            rec_mean    = info.get("recommendationMean")
            rec_key     = info.get("recommendationKey", "")
            n_analysts  = info.get("numberOfAnalystOpinions")
            inst_own    = info.get("heldPercentInstitutions")
            insider_own = info.get("heldPercentInsiders")
            short_pct   = info.get("shortPercentOfFloat")
            short_ratio = info.get("shortRatio")
            upside      = (tgt_price - price) / price if tgt_price and price else None

            # Insider transactions
            try:
                ins_df = stock.insider_transactions
                if ins_df is not None and not ins_df.empty:
                    buys  = int((ins_df["Shares"] > 0).sum()) if "Shares" in ins_df else 0
                    sells = int((ins_df["Shares"] < 0).sum()) if "Shares" in ins_df else 0
                    insider_summary = f"{buys} buys / {sells} sells (recent)"
                else:
                    insider_summary = "N/A"
            except Exception:
                insider_summary = "N/A"

            # Institutional holders
            top_holders: list[str] = []
            try:
                hdf = stock.institutional_holders
                if hdf is not None and not hdf.empty:
                    for _, row in hdf.head(5).iterrows():
                        h = row.get("Holder") or row.get("Name","")
                        s = row.get("Shares") or row.get("Value","")
                        top_holders.append(f"  • {h}: {s:,.0f} sh" if isinstance(s, (int,float)) else f"  • {h}")
            except Exception:
                pass

            # Earnings date
            try:
                cal = stock.calendar
                if cal is not None and isinstance(cal, dict):
                    ed = cal.get("Earnings Date") or cal.get("earningsDate")
                    earnings_date = str(ed[0])[:10] if ed and hasattr(ed, '__getitem__') else str(ed)[:10] if ed else "N/A"
                elif cal is not None:
                    earnings_date = "See Yahoo Finance"
                else:
                    earnings_date = "N/A"
            except Exception:
                earnings_date = "N/A"

            # News
            news_lines: list[str] = []
            try:
                for item in (stock.news or [])[:6]:
                    c = item.get("content", {})
                    title = c.get("title") or item.get("title","")
                    src   = (c.get("provider",{}).get("displayName","") if isinstance(c.get("provider"),dict) else item.get("publisher",""))
                    if title: news_lines.append(f"  • {title}" + (f" [{src}]" if src else ""))
            except Exception:
                pass

            # ── Scoring ───────────────────────────────────────────────────
            tech_score = 0; fund_score = 0; risk_score = 0
            tech_sigs: list[str] = []; fund_sigs: list[str] = []; risk_items: list[str] = []

            # Technical scoring (max ~20)
            if price > ma200:  tech_score += 3; tech_sigs.append("Price above 200-day SMA — confirmed long-term uptrend")
            else:              tech_sigs.append("Price below 200-day SMA — long-term trend broken")
            if price > ma50:   tech_score += 2; tech_sigs.append("Price above 50-day SMA — medium-term momentum intact")
            if price > ma20:   tech_score += 1; tech_sigs.append("Price above 20-day SMA — short-term strength")
            if price > vwap:   tech_score += 1; tech_sigs.append(f"Price above VWAP ({_price(vwap)}) — institutional buy bias")
            if macd_bull:      tech_score += 2; tech_sigs.append(f"MACD ({macd_val:.3f}) above signal — bullish momentum")
            else:              tech_sigs.append(f"MACD ({macd_val:.3f}) below signal — bearish momentum")
            if adx > 25 and pdi > mdi: tech_score += 2; tech_sigs.append(f"ADX {adx:.1f} — strong trend, +DI ({pdi:.1f}) leads -DI ({mdi:.1f})")
            elif adx > 25:     tech_sigs.append(f"ADX {adx:.1f} — strong bearish trend (-DI dominates)")
            else:              tech_sigs.append(f"ADX {adx:.1f} — weak/ranging market, no clear trend")
            if 40 <= rsi <= 65:  tech_score += 2; tech_sigs.append(f"RSI {rsi:.1f} — healthy momentum, room to run")
            elif rsi < 35:       tech_score += 1; tech_sigs.append(f"RSI {rsi:.1f} — oversold, contrarian buy signal")
            elif rsi > 72:       tech_score -= 1; tech_sigs.append(f"RSI {rsi:.1f} — overbought, pullback risk")
            if stoch_k > stoch_d and stoch_k < 80: tech_score += 1; tech_sigs.append(f"Stochastic bullish: %K {stoch_k:.1f} > %D {stoch_d:.1f}")
            elif stoch_k > 80:   tech_sigs.append(f"Stochastic overbought: %K {stoch_k:.1f}")
            if obv > obv_ma:     tech_score += 1; tech_sigs.append("OBV above MA — volume confirms uptrend (accumulation)")
            else:                tech_sigs.append("OBV below MA — volume divergence (distribution)")
            if vol_ratio > 1.5:  tech_score += 1; tech_sigs.append(f"Volume {vol_ratio:.1f}x average — high conviction move")
            if bb_pct < 0.25:    tech_score += 1; tech_sigs.append("Near Bollinger lower band — oversold relative to range")
            elif bb_pct > 0.85:  tech_score -= 1; tech_sigs.append("Near Bollinger upper band — stretched, near-term caution")
            if ret_1m and ret_1m > 0.05: tech_score += 1; tech_sigs.append(f"Strong 1-month momentum {_p(ret_1m)}")
            elif ret_1m and ret_1m < -0.10: tech_score -= 1; tech_sigs.append(f"Weak 1-month performance {_p(ret_1m)}")
            if roc > 5:  tech_score += 1; tech_sigs.append(f"ROC +{roc:.1f}% — positive rate of change")
            elif roc < -10: tech_sigs.append(f"ROC {roc:.1f}% — negative momentum")
            tech_sigs.append(f"Weekly trend: {weekly_trend}")

            # Fundamental scoring (max ~25)
            if ret_1y and ret_1y > 0.30:  fund_score += 3; fund_sigs.append(f"Exceptional 1-year return {_p(ret_1y)}")
            elif ret_1y and ret_1y > 0.15: fund_score += 2; fund_sigs.append(f"Strong 1-year return {_p(ret_1y)}")
            elif ret_1y and ret_1y > 0:    fund_score += 1; fund_sigs.append(f"Positive 1-year return {_p(ret_1y)}")
            elif ret_1y and ret_1y < -0.25: fund_score -= 2; fund_sigs.append(f"Poor 1-year return {_p(ret_1y)}")
            if ret_2y > 0.30: fund_score += 2; fund_sigs.append(f"Strong 2-year return {_p(ret_2y)} — sustained momentum")
            elif ret_2y > 0:  fund_score += 1; fund_sigs.append(f"Positive 2-year return {_p(ret_2y)}")
            if rev_growth and rev_growth > 0.20: fund_score += 3; fund_sigs.append(f"Revenue growing {_p(rev_growth)} YoY — strong expansion")
            elif rev_growth and rev_growth > 0.08: fund_score += 2; fund_sigs.append(f"Revenue growing {_p(rev_growth)} YoY")
            elif rev_growth and rev_growth > 0:    fund_score += 1; fund_sigs.append(f"Revenue growing {_p(rev_growth)} YoY")
            elif rev_growth and rev_growth < 0:    fund_score -= 1; fund_sigs.append(f"Revenue declining {_p(rev_growth)} YoY")
            if earn_growth and earn_growth > 0.20: fund_score += 3; fund_sigs.append(f"Earnings growing {_p(earn_growth)} YoY — improving profitability")
            elif earn_growth and earn_growth > 0.08: fund_score += 2; fund_sigs.append(f"Earnings growing {_p(earn_growth)} YoY")
            elif earn_growth and earn_growth > 0:   fund_score += 1; fund_sigs.append(f"Earnings growing {_p(earn_growth)} YoY")
            if profit_mg and profit_mg > 0.20: fund_score += 2; fund_sigs.append(f"High profit margin {_p(profit_mg)} — strong pricing power")
            elif profit_mg and profit_mg > 0.10: fund_score += 1; fund_sigs.append(f"Healthy profit margin {_p(profit_mg)}")
            if roe and roe > 0.20: fund_score += 2; fund_sigs.append(f"Excellent ROE {_p(roe)} — efficient capital use")
            elif roe and roe > 0.12: fund_score += 1; fund_sigs.append(f"Good ROE {_p(roe)}")
            if fcf and fcf > 0:    fund_score += 2; fund_sigs.append(f"Positive free cash flow {_mcap(fcf)} — real profitability")
            elif fcf and fcf < 0:  fund_score -= 1; fund_sigs.append(f"Negative FCF {_mcap(fcf)} — burning cash")
            if inst_own and inst_own > 0.70: fund_score += 2; fund_sigs.append(f"Strong institutional backing {_p(inst_own)} — smart money conviction")
            elif inst_own and inst_own > 0.50: fund_score += 1; fund_sigs.append(f"Good institutional ownership {_p(inst_own)}")
            if rec_mean and rec_mean <= 1.8: fund_score += 3; fund_sigs.append(f"Analyst consensus STRONG BUY ({rec_mean:.1f}/5) — {n_analysts} analysts")
            elif rec_mean and rec_mean <= 2.2: fund_score += 2; fund_sigs.append(f"Analyst consensus BUY ({rec_mean:.1f}/5) — {n_analysts} analysts")
            elif rec_mean and rec_mean <= 2.5: fund_score += 1; fund_sigs.append(f"Analyst leaning BUY ({rec_mean:.1f}/5)")
            elif rec_mean and rec_mean > 3.5:  fund_score -= 1; fund_sigs.append(f"Analyst consensus SELL ({rec_mean:.1f}/5)")
            if upside and upside > 0.25: fund_score += 3; fund_sigs.append(f"Analyst target {_price(tgt_price)} implies {_p(upside)} upside")
            elif upside and upside > 0.12: fund_score += 2; fund_sigs.append(f"Analyst target {_price(tgt_price)} implies {_p(upside)} upside")
            elif upside and upside > 0.05: fund_score += 1; fund_sigs.append(f"Analyst target {_price(tgt_price)} implies {_p(upside)} upside")
            elif upside and upside < -0.05: fund_score -= 1; fund_sigs.append(f"Analyst target {_price(tgt_price)} BELOW current — downside risk")
            if peg and 0 < peg < 1.0: fund_score += 2; fund_sigs.append(f"PEG {peg:.2f} < 1 — undervalued vs growth")
            elif peg and 1.0 <= peg < 2.0: fund_score += 1; fund_sigs.append(f"PEG {peg:.2f} — fair value for growth rate")

            # Risk scoring (positive = good, negative = bad, max ±5)
            if short_pct and short_pct > 0.20: risk_score -= 2; risk_items.append(f"HIGH short interest {_p(short_pct)} — significant bearish bets")
            elif short_pct and short_pct < 0.03: risk_score += 1; risk_items.append(f"Very low short interest {_p(short_pct)} — minimal bearish pressure")
            if earnings_date != "N/A": risk_items.append(f"Next earnings: {earnings_date} — binary event risk, vol spikes beforehand")
            if debt_eq and debt_eq > 200: risk_score -= 1; risk_items.append(f"High debt/equity {_n(debt_eq)} — elevated financial leverage")
            elif debt_eq and debt_eq < 50:  risk_score += 1; risk_items.append(f"Low debt/equity {_n(debt_eq)} — clean balance sheet")
            if cur_ratio and cur_ratio < 1.0: risk_score -= 1; risk_items.append(f"Current ratio {_n(cur_ratio)} < 1 — potential liquidity concern")
            elif cur_ratio and cur_ratio > 2.0: risk_score += 1; risk_items.append(f"Current ratio {_n(cur_ratio)} — strong liquidity")
            if cash_runway_q: risk_items.append(f"Cash runway: ~{cash_runway_q:.0f} quarters — unprofitable, dilution risk")
            if ann_vol > 0.50: risk_score -= 1; risk_items.append(f"Very high volatility {_pp(ann_vol*100)} — needs wider stops")
            if beta and beta > 1.5: risk_items.append(f"High beta {_n(beta)} — amplifies market moves both ways")
            elif beta and beta < 0.8: risk_score += 1; risk_items.append(f"Low beta {_n(beta)} — defensive, lower market correlation")

            # Macro impact on risk
            vix = macro.get("vix")
            spread = macro.get("yield_spread")
            if vix and vix > 30: risk_score -= 1; risk_items.append(f"VIX {vix:.1f} — elevated fear, broad market stress")
            if spread is not None and spread < 0: risk_score -= 1; risk_items.append("Inverted yield curve — historical recession indicator")

            total_score = tech_score + fund_score + risk_score

            if total_score >= 30:   rating = "STRONG BUY"
            elif total_score >= 22: rating = "BUY"
            elif total_score >= 14: rating = "WATCH / HOLD"
            elif total_score >= 7:  rating = "CAUTION"
            else:                   rating = "AVOID"

            # ── Trading setup ─────────────────────────────────────────────
            stop_loss      = max(support, price - 2 * atr)
            conservative_stop = price - 1.5 * atr
            risk_per_share = price - stop_loss
            portfolio_10k  = 10_000
            pos_size_1pct  = int((portfolio_10k * 0.01) / risk_per_share) if risk_per_share > 0 else 0
            pos_size_2pct  = int((portfolio_10k * 0.02) / risk_per_share) if risk_per_share > 0 else 0
            rr_ratio       = (resistance - price) / risk_per_share if risk_per_share > 0 else 0
            entry_zone_lo  = max(support, price - atr)

            # ── Build report ──────────────────────────────────────────────
            name     = info.get("longName", ticker)
            sector_s = info.get("sector","N/A"); industry = info.get("industry","N/A")
            summary  = (info.get("longBusinessSummary") or "")[:500].rstrip()
            if len(info.get("longBusinessSummary","")) > 500: summary += "..."

            fib_str = "  " + "  |  ".join(f"{k}: {_price(v)}" for k,v in fibs.items())

            report = [
                "=" * 70,
                f"  {name} ({ticker})",
                f"  RATING: {rating}",
                f"  Technical: {tech_score}  |  Fundamental: {fund_score}  |  Risk: {risk_score:+d}  |  Total: {total_score}",
                "=" * 70,
                f"  Sector: {sector_s}  |  Industry: {industry}",
                f"  Market Cap: {_mcap(mktcap)}  |  Beta: {_n(beta)}  |  Shares Out: {_mcap(shares)}",
                "",
                "── RAW PRICE DATA " + "─"*52,
                f"  Current:      {_price(price)}  |  VWAP: {_price(vwap)}  ({'Above' if price>vwap else 'Below'} VWAP)",
                f"  52W High:     {_price(high_52w)} ({_pp(pct_hi*100)} from high)",
                f"  52W Low:      {_price(low_52w)} (+{_pp(pct_lo*100)} from low)",
                f"  ATR (14):     {_price(atr)} ({_pp(atr/price*100)} of price)",
                f"  Ann. Vol:     {_pp(ann_vol*100)}  |  Volume vs avg: {vol_ratio:.2f}x",
                "",
                "── RETURNS (MULTI-TIMEFRAME) " + "─"*42,
                f"  1M: {_p(ret_1m):<10}  3M: {_p(ret_3m):<10}  6M: {_p(ret_6m)}",
                f"  1Y: {_p(ret_1y):<10}  2Y: {_p(ret_2y):<10}  Weekly trend: {weekly_trend}",
                "",
                "── TREND INDICATORS " + "─"*51,
                f"  20-SMA: {_price(ma20)} ({'ABOVE' if price>ma20 else 'BELOW'})  |  50-SMA: {_price(ma50)} ({'ABOVE' if price>ma50 else 'BELOW'})  |  200-SMA: {_price(ma200)} ({'ABOVE' if price>ma200 else 'BELOW'})",
                f"  20-EMA: {_price(ema20)}  |  50-EMA: {_price(ema50)}",
                f"  MACD: {macd_val:.4f} | Signal: {sig_val:.4f} | Hist: {macd_hist:+.4f}  ({'Bullish' if macd_bull else 'Bearish'})",
                f"  ADX: {adx:.1f} ({'Strong' if adx>25 else 'Weak'} trend)  |  +DI: {pdi:.1f}  |  -DI: {mdi:.1f}",
                "",
                "── MOMENTUM INDICATORS " + "─"*47,
                f"  RSI (14):         {rsi:.1f}  ({'Healthy' if 40<=rsi<=65 else ('Overbought' if rsi>70 else 'Oversold')})",
                f"  Stochastic %K/%D: {stoch_k:.1f} / {stoch_d:.1f}  ({'Bullish' if stoch_k>stoch_d else 'Bearish'})",
                f"  ROC (14):         {roc:+.2f}%",
                f"  Bollinger %B:     {bb_pct:.0%}  (Lower: {_price(bb_lower)} | Upper: {_price(bb_upper)})",
                "",
                "── VOLUME INDICATORS " + "─"*49,
                f"  OBV vs 20-MA:  {'Positive — accumulation' if obv>obv_ma else 'Negative — distribution'}",
                f"  Volume/30d avg: {vol_ratio:.2f}x  ({'High conviction' if vol_ratio>1.5 else ('Low conviction' if vol_ratio<0.6 else 'Normal')})",
                "",
                "── SUPPORT, RESISTANCE & FIBONACCI " + "─"*35,
                f"  Key Support:      {_price(support)}  |  Key Resistance: {_price(resistance)}",
                f"  Fibonacci (52W High {_price(high_52w)} → Low {_price(low_52w)}):",
                fib_str,
                "",
                "── VALUATION " + "─"*57,
                f"  P/E (trail/fwd):  {_n(pe_trail)} / {_n(pe_fwd)}  |  PEG: {_n(peg)}",
                f"  P/S: {_n(ps)}  |  P/B: {_n(pb)}  |  EV/EBITDA: {_n(ev_ebitda)}",
                f"  EPS (trail/fwd):  {_price(eps_trail)} / {_price(eps_fwd)}",
                "",
                "── GROWTH & PROFITABILITY " + "─"*44,
                f"  Revenue Growth:   {_p(rev_growth)}  |  Earnings Growth: {_p(earn_growth)}",
                f"  Gross Margin:     {_p(gross_mg)}  |  Profit Margin: {_p(profit_mg)}",
                f"  ROE: {_p(roe)}  |  ROA: {_p(roa)}",
                f"  Free Cash Flow:   {_mcap(fcf)}  |  Op. Cash Flow: {_mcap(op_cf)}",
                f"  Dividend Yield:   {_p(div_yield)}",
                "",
                "── FINANCIAL HEALTH " + "─"*51,
                f"  Debt/Equity:  {_n(debt_eq)}  |  Current Ratio: {_n(cur_ratio)}",
                f"  Total Cash:   {_mcap(total_cash)}  |  Total Debt: {_mcap(total_debt)}",
            ] + ([f"  Cash Runway:  {cash_runway_q:.0f} quarters (burning cash)"] if cash_runway_q else []) + [
                "",
                "── OWNERSHIP & ANALYST DATA " + "─"*42,
                f"  Institutional: {_p(inst_own)}  |  Insider: {_p(insider_own)}",
                f"  Insider Transactions: {insider_summary}",
                f"  Short Interest: {_p(short_pct)} of float  |  Short Ratio: {_n(short_ratio)} days to cover",
                f"  Analyst Target: {_price(tgt_price)}  (Low: {_price(tgt_low)} / High: {_price(tgt_high)})",
                f"  Implied Upside: {_p(upside)}  |  Rating: {_n(rec_mean)}/5.0 — {rec_key.upper()}  ({n_analysts} analysts)",
                f"  Next Earnings:  {earnings_date}",
            ]

            if top_holders:
                report += ["", "── TOP INSTITUTIONAL HOLDERS " + "─"*41] + top_holders

            # Macro context
            vix = macro.get("vix"); dxy = macro.get("dxy")
            fg_s = macro.get("fear_greed_score"); fg_r = macro.get("fear_greed_rating","")
            y10  = macro.get("yield_10y"); y2 = macro.get("yield_2y"); spread = macro.get("yield_spread")
            report += [
                "",
                "── MACRO CONTEXT " + "─"*54,
                f"  VIX:             {_n(vix,1)}  ({'High fear — risk-off' if vix and vix>25 else ('Low fear — complacency' if vix and vix<15 else 'Neutral fear')})",
                f"  Fear & Greed:    {_n(fg_s,0)}/100  [{fg_r.upper()}]" if fg_s else "  Fear & Greed:    N/A",
                f"  DXY (Dollar):    {_n(dxy,2)}  ({'Strong USD — headwind for multinationals & commodities' if dxy and dxy>103 else 'Weak/neutral USD — tailwind'})",
                f"  10Y Yield:       {_n(y10,2)}%  |  2Y Yield: {_n(y2,2)}%",
                f"  Yield Curve:     {'INVERTED — recession risk elevated (historically reliable signal)' if spread and spread<0 else f'Normal spread +{spread:.2f}%' if spread else 'N/A'}",
            ]

            report += [
                "",
                "── RISK ASSESSMENT " + "─"*52,
            ] + [f"  {'[!]' if any(w in r for w in ['HIGH','Inverted','SELL','burn','concern','amplifies','elevated','stress']) else '[i]'} {r}" for r in risk_items]

            report += [
                "",
                "── TRADING SETUP " + "─"*54,
                f"  Entry Zone:        {_price(entry_zone_lo)} – {_price(price)}",
                f"  Stop Loss:         {_price(stop_loss)}  (2×ATR from entry, or key support)",
                f"  Conservative Stop: {_price(conservative_stop)}  (1.5×ATR)",
                f"  First Target:      {_price(resistance)}  (key resistance)",
                f"  Analyst Target:    {_price(tgt_price)}  ({_p(upside)} from here)",
                f"  Risk/Reward:       {rr_ratio:.2f}x  {'(Favourable)' if rr_ratio >= 2 else '(Marginal)' if rr_ratio >= 1 else '(Poor — avoid)'}",
                f"  Risk per Share:    {_price(risk_per_share)}",
                f"  Position Size:     ~{pos_size_1pct} shares (1% risk on $10k)  |  ~{pos_size_2pct} shares (2% risk)",
                "",
                "── TECHNICAL SIGNALS " + "─"*49,
            ] + [f"  • {s}" for s in tech_sigs] + [
                "",
                "── FUNDAMENTAL SIGNALS " + "─"*47,
            ] + [f"  • {s}" for s in fund_sigs]

            if news_lines:
                report += ["", "── RECENT NEWS " + "─"*55] + news_lines

            if summary:
                report += ["", "── BUSINESS OVERVIEW " + "─"*49, f"  {summary}"]

            report += [
                "",
                f"  VERDICT: {rating}  |  Score: {total_score}  (Tech {tech_score} + Fund {fund_score} + Risk {risk_score:+d})",
                "",
                "  DISCLAIMER: This is not financial advice. Past performance does not",
                "  guarantee future results. Always do your own research.",
                "=" * 70,
            ]

            # Score card sentinel for GUI rendering (item 3)
            import json as _json
            score_card_json = _json.dumps({
                "tech": tech_score, "fund": fund_score, "risk": risk_score,
                "total": total_score, "rating": rating,
            })
            report.append(f"SCORE_CARD:{score_card_json}")

            result = "\n".join(report)
            _ticker_cache[ticker] = (time.time(), result)
            return result

        except Exception as exc:
            logger.exception("Analysis failed for %s", ticker)
            return f"Error analysing {ticker}: {exc}"
