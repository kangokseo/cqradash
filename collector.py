"""KIS REST API 수집기 (계좌별 APP_KEY/SECRET 지원).

- OAuth 접근토큰: APP_KEY 별로 발급·캐시 (KIS 토큰 유효 약 24h)
- 주식잔고조회(TTTC8434R): 일별 순자산(NAV) 스냅샷 저장 → 정본 시계열
- 기간별매매손익현황조회(TTTC8715R): 실현손익 (참고/근사용)

KIS는 과거 일별 평가금액(MTM NAV) 시계열을 제공하지 않으므로,
정확한 시계열은 이 수집기를 매일 실행해 정방향으로 누적해 만듭니다.
"""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime

import requests

import kis_config as cfg

REAL_TR_BALANCE = "TTTC8434R"
REAL_TR_PROFIT = "TTTC8715R"
VTS_TR_BALANCE = "VTTC8434R"  # 모의투자
REAL_TR_FO_BALANCE = "CTFO6118R"  # 국내선물옵션 잔고현황
VTS_TR_FO_BALANCE = "VTFO6118R"   # 모의 선물옵션

_FUTURES_KINDS = {"futures", "future", "fo", "선물", "선물옵션", "deriv", "derivatives"}


def _is_vts() -> bool:
    return "vts" in cfg.BASE_URL.lower()


# ----------------------------------------------------------------------
# 접근 토큰 (APP_KEY 별 캐시)
# ----------------------------------------------------------------------
def _load_token_cache() -> dict:
    if cfg.TOKEN_CACHE.exists():
        try:
            return json.loads(cfg.TOKEN_CACHE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_token_cache(cache: dict) -> None:
    cfg.TOKEN_CACHE.write_text(json.dumps(cache), encoding="utf-8")


def get_access_token(app_key: str, app_secret: str) -> str:
    """APP_KEY 단위로 토큰을 발급/재사용. 캐시는 키별로 저장."""
    cache = _load_token_cache()
    entry = cache.get(app_key)
    if entry and entry.get("expires_at", 0) > time.time() + 300:
        return entry["access_token"]

    url = f"{cfg.BASE_URL}/oauth2/tokenP"
    body = {"grant_type": "client_credentials", "appkey": app_key, "appsecret": app_secret}
    r = requests.post(url, json=body, timeout=15)
    r.raise_for_status()
    data = r.json()
    token = data["access_token"]
    expires_in = int(data.get("expires_in", 86400))
    cache[app_key] = {"access_token": token, "expires_at": time.time() + expires_in}
    _save_token_cache(cache)
    return token


def _headers(token: str, tr_id: str, app_key: str, app_secret: str) -> dict:
    return {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": tr_id,
        "custtype": "P",
    }


# ----------------------------------------------------------------------
# 잔고 조회 → 순자산(NAV)
# ----------------------------------------------------------------------
def fetch_balance(acct: cfg.Account, token: str) -> dict:
    """주식잔고조회. 순자산금액(nass_amt)을 NAV 로 사용."""
    tr = VTS_TR_BALANCE if _is_vts() else REAL_TR_BALANCE
    url = f"{cfg.BASE_URL}/uapi/domestic-stock/v1/trading/inquire-balance"
    params = {
        "CANO": acct.cano,
        "ACNT_PRDT_CD": acct.acnt,
        "AFHR_FLPR_YN": "N",
        "OFL_YN": "",
        "INQR_DVSN": "02",
        "UNPR_DVSN": "01",
        "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N",
        "PRCS_DVSN": "00",
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": "",
    }
    r = requests.get(url, headers=_headers(token, tr, acct.app_key, acct.app_secret),
                     params=params, timeout=15)
    r.raise_for_status()
    js = r.json()
    if js.get("rt_cd") != "0":
        raise RuntimeError(f"[{acct.name}] 잔고조회 실패: {js.get('msg1')}")
    out2 = (js.get("output2") or [{}])[0]

    def f(key: str) -> float:
        try:
            return float(out2.get(key, 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    nass = f("nass_amt")          # 순자산금액
    tot_eval = f("tot_evlu_amt")  # 총평가금액
    cash = f("dnca_tot_amt")      # 예수금총금액
    stock_eval = f("scts_evlu_amt")  # 유가증권평가금액
    nav = nass or tot_eval or (stock_eval + cash)
    return {"nav": nav, "stock_eval": stock_eval, "cash": cash, "tot_eval": tot_eval}


def fetch_balance_futures(acct: cfg.Account, token: str) -> dict:
    """국내선물옵션 잔고현황. 추정예탁자산(prsm_dpast_amt)을 NAV 로 사용."""
    tr = VTS_TR_FO_BALANCE if _is_vts() else REAL_TR_FO_BALANCE
    url = f"{cfg.BASE_URL}/uapi/domestic-futureoption/v1/trading/inquire-balance"
    params = {
        "CANO": acct.cano,
        "ACNT_PRDT_CD": acct.acnt,
        "MGNA_DVSN": "01",       # 증거금구분 01:위탁
        "EXCC_STAT_CD": "1",     # 정산상태코드
        "CTX_AREA_FK200": "",
        "CTX_AREA_NK200": "",
    }
    r = requests.get(url, headers=_headers(token, tr, acct.app_key, acct.app_secret),
                     params=params, timeout=15)
    r.raise_for_status()
    js = r.json()
    if js.get("rt_cd") != "0":
        raise RuntimeError(f"[{acct.name}] 선물옵션 잔고조회 실패: {js.get('msg1')}")
    out2 = js.get("output2") or {}
    if isinstance(out2, list):
        out2 = out2[0] if out2 else {}

    def f(key: str) -> float:
        try:
            return float(out2.get(key, 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    cash = f("dnca_cash") or f("dnca_tot_amt")            # 예수금현금
    # NAV(예탁자산) 후보 키 우선순위
    nav = (f("prsm_dpast_amt") or f("dpast_amt")
           or f("tot_asst_amt") or f("prsm_tot_asst"))
    if not nav:  # 후보 키가 없으면 합산 추정 + 디버그용 키 출력
        nav = cash + f("dnca_sbst") + f("evlu_pfls_smtl_amt")
        if not nav:
            print(f"  · {acct.name} 선물옵션 응답 키: {list(out2.keys())}")
    return {"nav": nav, "stock_eval": nav - cash, "cash": cash, "tot_eval": nav}


def fetch_account_balance(acct: cfg.Account, token: str) -> dict:
    """계좌유형(kind)에 따라 주식/선물옵션 잔고 API 분기.
    kind 미지정 시 주식 우선, '위탁계좌' 오류면 선물옵션으로 자동 재시도."""
    if acct.kind in _FUTURES_KINDS:
        return fetch_balance_futures(acct, token)
    try:
        return fetch_balance(acct, token)
    except RuntimeError as e:
        if "위탁계좌" in str(e) or "선물" in str(e):
            print(f"  · {acct.name}: 주식잔고 불가 → 선물옵션 잔고로 자동 재시도")
            return fetch_balance_futures(acct, token)
        raise


def fetch_period_realized(acct: cfg.Account, token: str, start: str, end: str) -> float:
    """기간별매매손익현황조회 → 기간 실현손익 합계 (참고용)."""
    if _is_vts():
        return 0.0  # 모의투자 미지원
    url = f"{cfg.BASE_URL}/uapi/domestic-stock/v1/trading/inquire-period-trade-profit"
    params = {
        "CANO": acct.cano,
        "ACNT_PRDT_CD": acct.acnt,
        "SORT_DVSN": "00",
        "PDNO": "",
        "INQR_STRT_DT": start.replace("-", ""),
        "INQR_END_DT": end.replace("-", ""),
        "CBLC_DVSN": "00",
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": "",
    }
    try:
        r = requests.get(url, headers=_headers(token, REAL_TR_PROFIT, acct.app_key, acct.app_secret),
                         params=params, timeout=15)
        r.raise_for_status()
        js = r.json()
        if js.get("rt_cd") != "0":
            return 0.0
        out2 = js.get("output2") or [{}]
        out2 = out2[0] if isinstance(out2, list) else out2
        for k in ("rlzt_pfls", "tot_rlzt_pfls", "smtl_rlzt_pfls"):
            v = out2.get(k)
            if v not in (None, ""):
                return float(v)
    except Exception as e:
        print(f"  · 기간별손익 조회 생략({acct.name}): {e}")
    return 0.0


# ----------------------------------------------------------------------
# 저장소
# ----------------------------------------------------------------------
def init_db() -> sqlite3.Connection:
    con = sqlite3.connect(cfg.DB_PATH)
    con.execute(
        """CREATE TABLE IF NOT EXISTS nav_snapshot (
               date TEXT, acct_idx INTEGER, name TEXT,
               nav REAL, stock_eval REAL, cash REAL,
               PRIMARY KEY (date, acct_idx))"""
    )
    con.execute(
        """CREATE TABLE IF NOT EXISTS realized_pl (
               date TEXT, acct_idx INTEGER, realized REAL,
               PRIMARY KEY (date, acct_idx))"""
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS account_meta (idx INTEGER PRIMARY KEY, name TEXT, start TEXT)"
    )
    con.commit()
    return con


def snapshot_today(asof: str | None = None) -> None:
    """오늘(또는 지정일)의 모든 계좌 NAV 스냅샷 저장. 계좌별 키로 인증."""
    asof = asof or datetime.now().strftime("%Y-%m-%d")
    accounts = cfg.load_accounts()
    if not accounts:
        raise SystemExit("⚠️  .env 에 계좌(ACCOUNTS__1__...)가 없습니다.")

    missing = [a.name for a in accounts if not a.app_key or a.app_key.startswith("계좌")]
    if missing:
        raise SystemExit(f"⚠️  다음 계좌의 APP_KEY/SECRET 를 .env 에 입력하세요: {', '.join(missing)}")

    con = init_db()
    token_by_key: dict[str, str] = {}
    for acct in accounts:
        con.execute("REPLACE INTO account_meta VALUES (?,?,?)", (acct.idx, acct.name, acct.start))
        try:
            # 같은 APP_KEY 는 토큰 재사용
            token = token_by_key.get(acct.app_key)
            if not token:
                token = get_access_token(acct.app_key, acct.app_secret)
                token_by_key[acct.app_key] = token
            bal = fetch_account_balance(acct, token)
        except Exception as e:
            print(f"  ✗ {acct.name}: {e}")
            continue
        con.execute(
            "REPLACE INTO nav_snapshot VALUES (?,?,?,?,?,?)",
            (asof, acct.idx, acct.name, bal["nav"], bal["stock_eval"], bal["cash"]),
        )
        if acct.start:
            rp = fetch_period_realized(acct, token, acct.start, asof)
            con.execute("REPLACE INTO realized_pl VALUES (?,?,?)", (asof, acct.idx, rp))
        print(f"  ✓ {acct.name}: NAV {bal['nav']:,.0f}")
        time.sleep(0.3)  # KIS 호출 간격 (유량제한 방지)
    con.commit()
    con.close()
    print(f"[collector] {asof} 스냅샷 저장 완료 ({len(accounts)}개 계좌)")


if __name__ == "__main__":
    import sys

    asof = sys.argv[1] if len(sys.argv) > 1 else None
    snapshot_today(asof)
