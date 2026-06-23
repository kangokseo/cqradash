# KIS 계좌 수익률 대시보드

한국투자증권 주식계좌(현재 7개, 추가·삭제 가능)의 일별 수익률을 KIS REST API 로 자동 수집하여
**1M / 3M / 6M / 1Y · 누적 · CAGR**, 그리고 **S&P500 대비 초과수익(α)** 을 보여주는 로컬 대시보드.

- **1M / 3M / 6M / 1Y** · 차트 = **TWR(시간가중수익률)**, 입출금 효과 제거
- **누적 · CAGR** = **설정금액(원금) 대비** (누적 = 현재 NAV ÷ 설정금액 − 1)

기준일을 바꾸면(과거일 포함) 해당일 기준으로 즉시 재계산됩니다.

---

## 1. 빠른 시작 (미리보기)

키 입력 없이 합성 데이터로 화면을 먼저 확인:

```bash
pip install requests
python run.py --demo
```

그 다음 **`dashboard.html` 더블클릭** → 계좌별 데모 데이터가 표시됩니다.
(이미 `data.js` 미리보기가 포함되어 있어 바로 열어봐도 됩니다.)

## 2. 실거래 데이터 연결

1) **KIS Developers 앱키 발급** — https://apiportal.koreainvestment.com 에서 발급.
   **계좌마다 APP_KEY / APP_SECRET 가 다른 구조**를 지원합니다(계좌 7개 = 키 7쌍).

2) **환경설정 파일 작성** — `config.example.env` 를 복사해 `.env` 로 저장 후 값 입력:
   ```
   Copy-Item config.example.env .env     # PowerShell
   ```
   계좌 블록마다 다음을 입력:
   - `ACCOUNTS__1__appkey`, `ACCOUNTS__1__appsecret` — **해당 계좌의 키/시크릿**
   - `ACCOUNTS__1__cano`(앞 8자리), `__acnt`(상품코드 2자리, 보통 01)
   - `__name`(별칭), `__start`(**운용시작일** YYYY-MM-DD, CAGR 연환산 기준일)
   - `__setamt`(**설정금액 = 원금**, 원 단위 정수) — 누적·CAGR 계산 기준.
     비우면 해당 계좌의 누적·CAGR 은 `—` 로 표시됩니다.

   여러 계좌가 같은 키를 공유하면 토큰을 자동 재사용합니다. 계좌 블록에 키를 비워두고
   전역 `KIS_APP_KEY`/`KIS_APP_SECRET` 만 채우면 그 값을 fallback 으로 씁니다.
   - **계좌 추가**: 다음 인덱스(8...) 블록을 복사 → 코드 수정 없이 자동 인식.
   - **벤치마크**: `BENCHMARK_SYMBOL`(기본 `^spx`), `BENCHMARK_NAME`,
     `BENCHMARK_START`(누적·CAGR 기준 시작일; 비우면 보유 데이터 최초일).

3) **수집 + 대시보드 갱신**:
   ```bash
   python run.py            # 오늘자 잔고 스냅샷 + S&P500 갱신 + 화면 데이터 생성
   python run.py 2026-06-18 # 특정일자로 스냅샷(필요 시)
   ```
   실행 후 `dashboard.html` 새로고침.

## 3. 계좌 추가·삭제 (운영 중)

계좌는 `.env` 의 `ACCOUNTS__<인덱스>__...` 블록 단위로 관리됩니다. 코드 수정은 필요 없습니다.

**현황 확인**
```bash
python manage.py list      # .env 계좌 + DB 보유 데이터 + 키 입력 여부
```

**추가**
1. `.env` 에 **사용하지 않은 새 인덱스**(예: 8) 블록을 추가 — appkey/appsecret/cano/acnt/name/start/setamt
2. `python run.py` 실행 → 다음 수집부터 대시보드에 표시. (수집 시점부터 NAV 누적)

**삭제**
1. `.env` 에서 해당 계좌 블록을 제거 → 대시보드에서 **자동으로 사라짐**
2. (선택) DB의 과거 데이터까지 정리: `python manage.py purge <인덱스>` → `python run.py --compute`

> ⚠️ **삭제한 인덱스를 다른 계좌에 재사용하지 마세요.** 과거 NAV 데이터가 섞입니다.
> 항상 새 인덱스를 부여하세요. 인덱스는 연속일 필요 없습니다(예: 1,2,4,5 가능).

## 4. 매일 16:00 자동 실행 (Windows 작업 스케줄러)

**한 번만** `register_schedule.bat` 더블클릭 → 매일 **16:00(PC 로컬시간)** 자동 수집이 등록됩니다.
(등록 실패 시 우클릭 → "관리자 권한으로 실행")

- 시간대 전제: PC 표준 시간대가 **(UTC+09:00) 서울(KST)** 이어야 16:00 = KST 입니다.
- 자동 수집은 `run_silent.bat`(무인 실행)을 호출하며 결과는 `data\run.log` 에 기록됩니다.
- 관련 명령:
  - 지금 한 번 실행: `schtasks /Run /TN "CQRA_Dashboard_Daily"`
  - 등록 확인: `schtasks /Query /TN "CQRA_Dashboard_Daily"`
  - 해제: `schtasks /Delete /TN "CQRA_Dashboard_Daily" /F`

> 자동 수집은 **PC가 켜져 있고 로그인된 상태**에서 동작합니다. (절전/종료 시 미실행 → 다음 실행일에 이어서 누적)
> 클라우드(에이전트) 예약으로는 KIS 접속이 불가하여 실수집이 되지 않습니다.

---

## 5. 수익률 계산 방식

- **1M / 3M / 6M / 1Y · 차트** = **TWR(시간가중수익률)** — 입출금 효과를 제거한 순수 운용성과.
  입출금은 `cashflows.csv` 에 기록합니다(입금 +, 출금 −):

  ```csv
  date,acct_idx,amount
  2025-03-10,1,50000000     # 1번 계좌 5천만원 입금
  2025-08-22,3,-20000000    # 3번 계좌 2천만원 출금
  ```

  기록하지 않으면 입출금이 TWR 수익률로 잡혀 **왜곡**됩니다. (KIS API 는 외부 입출금을
  단일 호출로 깔끔히 제공하지 않아 이 파일로 관리합니다.)

- **누적 · CAGR** = **설정금액(원금) 대비**. 누적 = 현재 NAV ÷ 설정금액 − 1,
  CAGR 은 운용시작일~기준일 연환산. 설정금액은 `.env` 의 `ACCOUNTS__<n>__setamt`.
  운용기간 1년 미만 계좌는 연환산 과장 방지를 위해 CAGR 을 `—` 로 둡니다.

## 6. 데이터 제약 (반드시 인지)

- KIS 는 **과거 일별 평가금액(MTM NAV) 시계열을 제공하지 않습니다.** 따라서 **TWR 기반
  1M/3M/6M/1Y** 는 수집기를 **매일 실행해 정방향으로 누적**해야 채워집니다(데이터가 쌓일
  때까지 해당 구간은 `—`).
- **누적·CAGR 은 설정금액(원금) 기준**이라 설정금액만 입력돼 있으면 **첫 수집일부터 즉시 표시**됩니다.
- 벤치마크(S&P500)는 **Yahoo Finance**(`^GSPC`, 최근 2년) 일별 종가 기준이며 **가격수익률**
  (배당 재투자·환헤지 미반영). 벤치마크 누적·CAGR 시작일은 `.env` 의 `BENCHMARK_START`.

## 7. 구성 파일

| 파일 | 역할 |
|---|---|
| `.env` | 앱키·계좌·운용시작일·설정금액 (앱이 읽는 실파일, 외부 공유 금지) |
| `config.example.env` | `.env` 작성용 템플릿 |
| `collector.py` | KIS 잔고(NAV)·기간별손익 수집 → SQLite (계좌별 키) |
| `benchmark.py` | S&P500 일별 종가 수집(Yahoo Finance `^GSPC`) |
| `compute.py` | TWR 지수·설정금액·벤치 시계열 → `data.json` / `data.js` |
| `run.py` | 수집→계산 오케스트레이터 (`--demo`, `--compute`) |
| `manage.py` | 계좌 현황 확인/삭제 정리 (`list`, `purge`) |
| `dashboard.html` | 표·차트·기준일 셀렉터 (더블클릭 실행) |
| `cashflows.csv` | 입출금 기록 (TWR 보정) |
| `data/portfolio.db` | 일별 시계열 저장소 |

---

작업시계 구분: 본 대시보드는 성과 모니터링용이며, 매매 판단은 별도 리스크 점검과 병행하십시오.
