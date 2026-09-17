import os
import httpx

from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

# Load .env
load_dotenv()

app = FastAPI(
    title="Trading Janta Party API",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# API KEY
# =========================

def get_api_key():
    return os.getenv(
        "TWELVE_DATA_API_KEY",
        ""
    ).strip()


# =========================
# HOME
# =========================

@app.api_route(
    "/",
    methods=["GET", "HEAD"]
)
def home():
    return {
        "status": "online",
        "service": "Trading Janta Party API"
    }


# =========================
# HEALTH
# =========================

@app.api_route(
    "/health",
    methods=["GET", "HEAD"]
)
def health():
    api_key = get_api_key()

    return {
        "status": "ok",
        "api_configured": bool(api_key)
    }


# =========================
# SIGNAL
# =========================

@app.get("/api/signal")
async def signal(
    pair: str = Query("EUR/USD")
):

    api_key = get_api_key()

    if not api_key:
        return {
            "success": False,
            "error": "TWELVE_DATA_API_KEY is not configured"
        }

    pair = pair.strip().upper()

    if not pair:
        pair = "EUR/USD"

    url = (
        "https://api.twelvedata.com/"
        "time_series"
    )

    params = {
        "symbol": pair,
        "interval": "1min",
        "outputsize": 50,
        "apikey": api_key
    }

    try:

        async with httpx.AsyncClient(
            timeout=20
        ) as client:

            response = await client.get(
                url,
                params=params
            )

        data = response.json()

        # Twelve Data error
        if data.get("status") == "error":

            return {
                "success": False,
                "error": data.get(
                    "message",
                    "Twelve Data API error"
                )
            }

        values = data.get(
            "values",
            []
        )

        if not values:

            return {
                "success": False,
                "error": "No market data returned"
            }

        # Newest -> oldest
        # Convert to oldest -> newest
        values.reverse()

        closes = []

        for candle in values:

            try:

                close_price = float(
                    candle["close"]
                )

                closes.append(
                    close_price
                )

            except (
                KeyError,
                TypeError,
                ValueError
            ):
                continue

        if len(closes) < 25:

            return {
                "success": False,
                "error": "Not enough market data"
            }

        # =========================
        # INDICATORS
        # =========================

        current_price = closes[-1]

        ema9 = calculate_ema(
            closes,
            9
        )

        ema21 = calculate_ema(
            closes,
            21
        )

        rsi = calculate_rsi(
            closes,
            14
        )

        # =========================
        # SIGNAL SCORE
        # =========================

        score = 0

        if ema9 > ema21:
            score += 2

        elif ema9 < ema21:
            score -= 2

        if rsi > 55:
            score += 1

        elif rsi < 45:
            score -= 1

        # =========================
        # DIRECTION
        # =========================

        if score >= 2:

            direction = "CALL"

        elif score <= -2:

            direction = "PUT"

        else:

            direction = "WAIT"

        # =========================
        # CONFIDENCE
        # =========================

        confidence = min(
            95,
            max(
                50,
                round(
                    60 + (
                        abs(score) * 8
                    )
                )
            )
        )

        return {

            "success": True,

            "pair": pair,

            "signal": direction,

            "confidence": confidence,

            "price": round(
                current_price,
                5
            ),

            "indicators": {

                "ema9": round(
                    ema9,
                    5
                ),

                "ema21": round(
                    ema21,
                    5
                ),

                "rsi": round(
                    rsi,
                    2
                )
            },

            "source": "Twelve Data"
        }

    except httpx.TimeoutException:

        return {
            "success": False,
            "error": (
                "Twelve Data request timed out"
            )
        }

    except httpx.RequestError:

        return {
            "success": False,
            "error": (
                "Unable to connect to Twelve Data"
            )
        }

    except Exception:

        return {
            "success": False,
            "error": (
                "Backend request failed"
            )
        }


# =========================
# EMA
# =========================

def calculate_ema(
    values,
    period
):

    if not values:
        return 0.0

    if len(values) < period:

        return (
            sum(values)
            / len(values)
        )

    multiplier = 2 / (
        period + 1
    )

    ema = (
        sum(values[:period])
        / period
    )

    for price in values[period:]:

        ema = (
            (
                price - ema
            ) * multiplier
        ) + ema

    return ema


# =========================
# RSI
# =========================

def calculate_rsi(
    values,
    period=14
):

    if len(values) <= period:

        return 50.0

    gains = []
    losses = []

    for i in range(
        1,
        len(values)
    ):

        change = (
            values[i]
            - values[i - 1]
        )

        gains.append(
            max(change, 0)
        )

        losses.append(
            max(-change, 0)
        )

    avg_gain = (
        sum(gains[:period])
        / period
    )

    avg_loss = (
        sum(losses[:period])
        / period
    )

    for i in range(
        period,
        len(gains)
    ):

        avg_gain = (
            (
                avg_gain
                * (period - 1)
            )
            + gains[i]
        ) / period

        avg_loss = (
            (
                avg_loss
                * (period - 1)
            )
            + losses[i]
        ) / period

    if avg_loss == 0:

        return 100.0

    rs = (
        avg_gain
        / avg_loss
    )

    return 100 - (
        100 / (1 + rs)
    )
