"""공통 설정 로더 — .env 파싱, 계좌 목록, DB 경로."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "portfolio.db"
TOKEN_CACHE = DATA_DIR / ".token_cache.json"
DATA_JSON = BASE_DIR / "data.json"


def _load_dotenv(path: Path) -> None:
    """간단한 .env 파서 (외부 의존성 없음)."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        # 인라인 주석 제거 (값에 # 가 없다는 가정)
        if " #" in val:
            val = val.split(" #", 1)[0].strip()
        os.environ.setdefault(key, val)


_load_dotenv(BASE_DIR / ".env")


@dataclass
class Account:
    idx: int
    cano: str
    acnt: str
    name: str
    start: str  # YYYY-MM-DD
    app_key: str = ""     # 계좌별 APP_KEY (미지정 시 전역 KIS_APP_KEY)
    app_secret: str = ""  # 계좌별 APP_SECRET (미지정 시 전역 KIS_APP_SECRET)
    setamt: float = 0.0   # 설정금액(원금, 원). 누적·CAGR 계산 기준. 0 이면 미설정
    kind: str = ""        # 계좌유형: ""/stock=주식위탁, futures=선물옵션. 미지정 시 자동판별


def _to_amt(s: str) -> float:
    """'12,000,000' / '12000000' → float. 빈 값·파싱 실패 시 0.0."""
    s = (s or "").replace(",", "").replace("_", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def load_accounts() -> list[Account]:
    """ACCOUNTS__<idx>__<field> 형식 환경변수를 계좌 리스트로.

    계좌마다 appkey/appsecret 를 가질 수 있다. 미지정 시 전역 KIS_APP_KEY/SECRET 사용.
    """
    pat = re.compile(r"^ACCOUNTS__(\d+)__(\w+)$")
    buckets: dict[int, dict[str, str]] = {}
    for key, val in os.environ.items():
        m = pat.match(key)
        if not m:
            continue
        idx = int(m.group(1))
        buckets.setdefault(idx, {})[m.group(2).lower()] = val.strip()

    g_key = os.environ.get("KIS_APP_KEY", "").strip()
    g_secret = os.environ.get("KIS_APP_SECRET", "").strip()

    accounts: list[Account] = []
    for idx in sorted(buckets):
        b = buckets[idx]
        if not b.get("cano"):
            continue
        accounts.append(
            Account(
                idx=idx,
                cano=b.get("cano", ""),
                acnt=b.get("acnt", "01"),
                name=b.get("name", f"계좌{idx}"),
                start=b.get("start", ""),
                app_key=b.get("appkey", "") or g_key,
                app_secret=b.get("appsecret", "") or g_secret,
                setamt=_to_amt(b.get("setamt", "")),
                kind=b.get("kind", "").lower(),
            )
        )
    return accounts


def get(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


# 자주 쓰는 값
APP_KEY = get("KIS_APP_KEY")
APP_SECRET = get("KIS_APP_SECRET")
BASE_URL = get("KIS_BASE_URL", "https://openapi.koreainvestment.com:9443")
BENCHMARK_SYMBOL = get("BENCHMARK_SYMBOL", "^spx")
BENCHMARK_NAME = get("BENCHMARK_NAME", "S&P 500")
# 벤치마크 누적·CAGR 기준 시작일(YYYY-MM-DD). 비우면 보유 데이터의 가장 이른 날짜.
BENCHMARK_START = get("BENCHMARK_START", "")
