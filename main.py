import os
import math
import httpx

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Trading Janta Party API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

TWELVE_DATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY")


@app.get("/")
def home():
    return {
        "status": "online",
        "service": "Trading Janta Party API"
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "api_configured": bool(TWELVE_DATA_API_KEY)
    }


@app.get("/api/signal")
async def signal(
    pair: str = Query("EUR/USD")
):
    if not TWELVE_DATA_API_KEY:
        return {
            "success": False,
            "error": "TWELVE_DATA_API_KEY is not configured"
        }

    url = "https://api.twelvedata.com/time_series"

    params = {
        "symbol": pair,
        "interval": "1min",
        "outputsize": 50,
        "apikey": TWELVE_DATA_API_KEY,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url, params=params)

        data = response.json()

        if response.status_code != 200:
            return {
                "success": False,
                "error": "Market data request failed"
            }

        if data.get("status") == "error":
            return {
                "success": False,
                "error": data.get(
                    "message",
                    "Twelve Data error"
                )
            }

        values = data.get("values", [])

        if len(values) < 25:
            return {
                "success": False,
                "error": "Not enough market data"
            }

        values.reverse()

        closes = [
            float(c["close"])
            for c in values
        ]

        current_price = closes[-1]

        ema9 = calculate_ema(closes, 9)
        ema21 = calculate_ema(closes, 21)
        rsi = calculate_rsi(closes, 14)

        score = 0

        if ema9 > ema21:
            score += 2
        elif ema9 < ema21:
            score -= 2

        if rsi > 55:
            score += 1
        elif rsi < 45:
            score -= 1

        if score >= 2:
            direction = "CALL"
        elif score <= -2:
            direction = "PUT"
        else:
            direction = "WAIT"

        confidence = min(
            95,
            max(
                50,
                round(60 + abs(score) * 8)
            )
        )

        return {
            "success": True,
            "pair": pair,
            "signal": direction,
            "confidence": confidence,
            "price": round(current_price, 5),
            "indicators": {
                "ema9": round(ema9, 5),
                "ema21": round(ema21, 5),
                "rsi": round(rsi, 2)
            },
            "source": "Twelve Data"
        }

    except Exception as e:
        return {
            "success": False,
            "error": "Backend request failed"
        }


def calculate_ema(values, period):
    multiplier = 2 / (period + 1)

    ema = values[0]

    for price in values[1:]:
        ema = (
            (price - ema) * multiplier
        ) + ema

    return ema


def calculate_rsi(values, period):
    if len(values) <= period:
        return 50

    gains = []
    losses = []

    for i in range(1, len(values)):
        difference = (
            values[i] - values[i - 1]
        )

        gains.append(max(difference, 0))
        losses.append(max(-difference, 0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (
            (avg_gain * (period - 1))
            + gains[i]
        ) / period

        avg_loss = (
            (avg_loss * (period - 1))
            + losses[i]
        ) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss

    return 100 - (
        100 / (1 + rs)
)
