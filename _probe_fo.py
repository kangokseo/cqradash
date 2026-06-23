# -*- coding: utf-8 -*-
import requests
import kis_config as cfg
import collector as col

acct = [a for a in cfg.load_accounts() if a.idx == 7][0]
token = col.get_access_token(acct.app_key, acct.app_secret)

url = f"{cfg.BASE_URL}/uapi/domestic-futureoption/v1/trading/inquire-balance"
tr = "CTFO6118R"
attempts = [
    {"MGNA_DVSN": "01", "EXCC_STAT_CD": "2"},
    {"MGNA_DVSN": "01", "EXCC_STAT_CD": "1"},
    {"MGNA_DVSN": "02", "EXCC_STAT_CD": "2"},
]
for extra in attempts:
    params = {"CANO": acct.cano, "ACNT_PRDT_CD": acct.acnt,
              "CTX_AREA_FK200": "", "CTX_AREA_NK200": ""}
    params.update(extra)
    h = col._headers(token, tr, acct.app_key, acct.app_secret)
    r = requests.get(url, headers=h, params=params, timeout=15)
    js = r.json()
    print("=== params", extra, "http", r.status_code,
          "rt_cd", js.get("rt_cd"), "msg", js.get("msg1"))
    if js.get("rt_cd") == "0":
        o2 = js.get("output2")
        if isinstance(o2, list):
            o2 = o2[0] if o2 else {}
        print("output2 keys/vals:")
        for k, v in (o2 or {}).items():
            print(f"   {k} = {v}")
        break
