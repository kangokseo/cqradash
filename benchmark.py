"""S&P500 등 벤치마크 일별 종가 수집 (Yahoo Finance).

stooq 가 봇 차단(JS 검증)을 도입해 CSV 다운로드가 막혀, Yahoo Finance
차트 API 로 일별 종가를 받아온다 (API 키 불필요).
  https://query1.finance.yahoo.com/v8/finance/chart/^GSPC?range=2y&interval=1d
수집한 종가는 nav_snapshot 과 동일한 SQLite 에 bench_price 로 저장.
저장 심볼은 cfg.BENCHMARK_SYMBOL(예: ^spx) 그대로 유지한다.
"""
from __future__ import annotations

import datetime as _dt
import sqlite3

import requests

import kis_config as cfg

# 저장용 심볼(stooq 표기) → Yahoo 차트 심볼 매핑
_YAHOO_SYMBOL = {
    "^spx": "^GSPC",
    "^SPX": "^GSPC",
}

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def init_db() -> sqlite3.Connection:
    con = sqlite3.connect(cfg.DB_PATH)
    con.execute(
        """CREATE TABLE IF NOT EXISTS bench_price (
               date TEXT, symbol TEXT, close REAL,
               PRIMARY KEY (date, symbol))"""
    )
    con.commit()
    return con


def fetch_yahoo(symbol: str) -> list[tuple[str, float]]:
    """Yahoo Finance 일별 종가. [(YYYY-MM-DD, close), ...]"""
    ysym = _YAHOO_SYMBOL.get(symbol, symbol)
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ysym}"
        "?range=2y&interval=1d"
    )
    r = requests.get(url, headers={"User-Agent": _UA}, timeout=30)
    r.raise_for_status()
    result = r.json()["chart"]["result"][0]
    ts = result["timestamp"]
    closes = result["indicators"]["quote"][0]["close"]
    rows: list[tuple[str, float]] = []
    for t, c in zip(ts, closes):
        if c is None:
            continue
        d = _dt.datetime.fromtimestamp(t, _dt.timezone.utc).strftime("%Y-%m-%d")
        rows.append((d, float(c)))
    return rows


def update_benchmark() -> None:
    symbol = cfg.BENCHMARK_SYMBOL
    rows = fetch_yahoo(symbol)
    if not rows:
        raise SystemExit(f"⚠️  벤치마크 데이터 수집 실패: {symbol}")
    con = init_db()
    con.executemany(
        "REPLACE INTO bench_price VALUES (?,?,?)",
        [(d, symbol, c) for d, c in rows],
    )
    con.commit()
    con.close()
    print(f"[benchmark] {symbol} {len(rows)}일 종가 저장 (최근 {rows[-1][0]})")


if __name__ == "__main__":
    update_benchmark()
