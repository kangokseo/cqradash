"""오케스트레이터.

사용법:
  python run.py            # 오늘 NAV 스냅샷 + 벤치마크 갱신 + data.json 생성 (실거래)
  python run.py 2026-06-18 # 지정일자로 잔고 스냅샷 (장중 보정 등)
  python run.py --demo     # 키 없이 합성 샘플 데이터로 대시보드 미리보기
  python run.py --compute  # 수집 생략, data.json 만 재생성
"""
from __future__ import annotations

import sys

import compute


def run_live(asof: str | None) -> None:
    import benchmark
    import collector

    print("== KIS 잔고 스냅샷 ==")
    collector.snapshot_today(asof)
    print("== 벤치마크(S&P500) 갱신 ==")
    benchmark.update_benchmark()
    print("== data.json 생성 ==")
    compute.write_json()


def run_demo() -> None:
    """합성 데이터로 DB 채우기 (키 불필요, 미리보기 전용)."""
    import math
    import random
    import sqlite3
    from datetime import date, timedelta

    import kis_config as cfg

    random.seed(7)
    con = sqlite3.connect(cfg.DB_PATH)
    con.execute("DROP TABLE IF EXISTS nav_snapshot")
    con.execute("DROP TABLE IF EXISTS bench_price")
    con.execute(
        "CREATE TABLE nav_snapshot (date TEXT, acct_idx INTEGER, name TEXT, "
        "nav REAL, stock_eval REAL, cash REAL, PRIMARY KEY (date, acct_idx))"
    )
    con.execute(
        "CREATE TABLE bench_price (date TEXT, symbol TEXT, close REAL, "
        "PRIMARY KEY (date, symbol))"
    )

    demo_starts = ["2024-09-02", "2024-11-01", "2025-01-02",
                   "2025-03-03", "2025-06-02", "2025-09-01"]
    accounts = cfg.load_accounts() or [
        cfg.Account(i, "0", "01", f"데모계좌{i}", demo_starts[i - 1]) for i in range(1, 7)
    ]
    con.execute("DROP TABLE IF EXISTS account_meta")
    con.execute("CREATE TABLE account_meta (idx INTEGER PRIMARY KEY, name TEXT, start TEXT)")
    for a in accounts:
        con.execute("REPLACE INTO account_meta VALUES (?,?,?)", (a.idx, a.name, a.start))

    start = date(2024, 9, 2)
    end = date(2026, 6, 19)
    days = [start + timedelta(d) for d in range((end - start).days + 1)]
    days = [d for d in days if d.weekday() < 5]  # 영업일만

    # 벤치마크: 연 9% 드리프트 + 변동성
    bench = 5000.0
    for d in days:
        bench *= math.exp(0.09 / 252 + random.gauss(0, 0.009))
        con.execute("REPLACE INTO bench_price VALUES (?,?,?)",
                    (d.isoformat(), cfg.BENCHMARK_SYMBOL, round(bench, 2)))

    profiles = [(0.14, 0.011), (0.07, 0.008), (0.18, 0.016),
                (0.05, 0.006), (0.11, 0.013), (-0.02, 0.010),
                (0.10, 0.012), (0.08, 0.009)]
    for acct in accounts:
        mu, sig = profiles[(acct.idx - 1) % len(profiles)]
        nav = 100_000_000.0
        for i, d in enumerate(days):
            nav *= math.exp(mu / 252 + random.gauss(0, sig))
            stock = round(nav * 0.95, 0)
            cash = round(nav * 0.05, 0)
            con.execute("REPLACE INTO nav_snapshot VALUES (?,?,?,?,?,?)",
                        (d.isoformat(), acct.idx, acct.name, round(nav, 0), stock, cash))
    con.commit()
    con.close()
    print("[demo] 합성 데이터 생성 완료.")
    compute.write_json()


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--demo" in args:
        run_demo()
    elif "--compute" in args:
        compute.write_json()
    else:
        asof = args[0] if args and not args[0].startswith("--") else None
        run_live(asof)
