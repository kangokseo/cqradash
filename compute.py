"""수익률 계산 엔진 → data.json / data.js 생성.

설계 핵심: Python 은 '입출금 보정 TWR 지수(rebased 100)' 와 '벤치마크 종가' 의
전체 시계열만 만들어 담는다. 1M/3M/6M/1Y·누적·CAGR·초과수익(α)·임의 기준일
(과거일 포함) 계산은 대시보드(HTML)에서 이 시계열로 직접 수행한다.
→ 기준일 셀렉터가 Python 재실행 없이 즉시 동작.

TWR(시간가중수익률): 입출금 효과 제거. 운용성과 ↔ 벤치마크 비교에 표준.
  구간수익률 HPR_t = (NAV_t − 구간내입출금) / NAV_{t-1}
  지수_t = 지수_{t-1} × HPR_t   (시작 100)
입출금은 cashflows.csv 로 입력 (입금 +, 출금 −). 비어 있으면 0 으로 처리.
"""
from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timedelta, timezone

import kis_config as cfg

KST = timezone(timedelta(hours=9))  # 생성시간 표기는 KST 고정


def load_cashflows() -> dict[int, list[tuple[str, float]]]:
    """cashflows.csv → {acct_idx: [(date, amount), ...]}  (입금 +, 출금 −)"""
    path = cfg.BASE_DIR / "cashflows.csv"
    flows: dict[int, list[tuple[str, float]]] = {}
    if not path.exists():
        return flows
    with path.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            try:
                idx = int(row["acct_idx"])
                d = row["date"].strip()
                amt = float(row["amount"])
            except (KeyError, ValueError, TypeError):
                continue
            flows.setdefault(idx, []).append((d, amt))
    for idx in flows:
        flows[idx].sort()
    return flows


def twr_index(snaps: list[tuple[str, float]], flows: list[tuple[str, float]]) -> list[list]:
    """입출금 보정 TWR 지수 시계열. [[date, index, nav], ...] (index 시작 100)"""
    if not snaps:
        return []
    out = [[snaps[0][0], 100.0, round(snaps[0][1], 2)]]
    idx_val = 100.0
    for i in range(1, len(snaps)):
        d_prev, nav_prev = snaps[i - 1]
        d_cur, nav_cur = snaps[i]
        flow = sum(a for (d, a) in flows if d_prev < d <= d_cur)
        if nav_prev > 0:
            hpr = (nav_cur - flow) / nav_prev
            if hpr > 0:
                idx_val *= hpr
        out.append([d_cur, round(idx_val, 4), round(nav_cur, 2)])
    return out


def _accounts_from_db(con) -> list[cfg.Account]:
    """config(.env)에 계좌가 없을 때 DB(nav_snapshot)에서 계좌 목록 복원."""
    try:
        rows = con.execute(
            "SELECT acct_idx, name, MIN(date) AS d FROM nav_snapshot "
            "GROUP BY acct_idx ORDER BY acct_idx"
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    meta = {}
    try:
        for m in con.execute("SELECT idx, name, start FROM account_meta"):
            meta[m["idx"]] = (m["name"], m["start"])
    except sqlite3.OperationalError:
        pass
    out = []
    for r in rows:
        name, start = meta.get(r["acct_idx"], (r["name"], r["d"]))
        out.append(cfg.Account(r["acct_idx"], "", "01", name, start))
    return out


def build() -> dict:
    con = sqlite3.connect(cfg.DB_PATH)
    con.row_factory = sqlite3.Row

    accounts = cfg.load_accounts() or _accounts_from_db(con)
    cf = load_cashflows()

    series: dict[str, list] = {}
    acct_meta = []
    for acct in accounts:
        rows = con.execute(
            "SELECT date, nav FROM nav_snapshot WHERE acct_idx=? ORDER BY date",
            (acct.idx,),
        ).fetchall()
        snaps = [(r["date"], float(r["nav"])) for r in rows if r["nav"]]
        series[str(acct.idx)] = twr_index(snaps, cf.get(acct.idx, []))
        acct_meta.append(
            {
                "idx": acct.idx,
                "name": acct.name,
                "start": acct.start,
                "setamt": acct.setamt,
                "cashflows": [[d, a] for (d, a) in cf.get(acct.idx, [])],
            }
        )

    bench_rows = con.execute(
        "SELECT date, close FROM bench_price WHERE symbol=? ORDER BY date",
        (cfg.BENCHMARK_SYMBOL,),
    ).fetchall()
    bench = [[r["date"], float(r["close"])] for r in bench_rows]
    con.close()

    return {
        "generated_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST"),
        "benchmark_name": cfg.BENCHMARK_NAME,
        "benchmark_symbol": cfg.BENCHMARK_SYMBOL,
        "benchmark_start": cfg.BENCHMARK_START,
        "accounts": acct_meta,
        "series": series,
        "bench": bench,
    }


def write_json() -> None:
    data = build()
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    cfg.DATA_JSON.write_text(payload, encoding="utf-8")
    # data.js: 로컬 더블클릭(file://)에서도 동작하도록 script 태그용 변수로 저장
    (cfg.BASE_DIR / "data.js").write_text(
        "window.DASH_DATA=" + payload + ";", encoding="utf-8"
    )
    n = sum(len(v) for v in data["series"].values())
    print(f"[compute] data.json / data.js 생성 — 계좌 {len(data['accounts'])}개, "
          f"NAV포인트 {n}개, 벤치 {len(data['bench'])}일")


if __name__ == "__main__":
    write_json()
