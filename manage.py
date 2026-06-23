"""계좌 추가/삭제 운영 유틸.

  python manage.py list          # 현재 .env 계좌 + DB 보유 데이터 현황
  python manage.py purge <idx>   # 삭제한 계좌의 DB 데이터 정리(스냅샷/메타)

계좌 추가:
  .env 에 ACCOUNTS__<새 인덱스>__... 블록을 추가한 뒤  python run.py 실행.
계좌 삭제:
  .env 에서 해당 계좌 블록을 지우면 대시보드에서 자동으로 사라집니다.
  과거 데이터까지 DB에서 지우려면  python manage.py purge <idx>.

⚠️ 삭제한 인덱스를 다른 계좌에 재사용하지 마세요(과거 데이터가 섞입니다).
"""
from __future__ import annotations

import sqlite3
import sys

import kis_config as cfg


def _db_indices() -> dict[int, tuple[int, str, str]]:
    """DB에 데이터가 있는 계좌: {idx: (스냅샷수, 최초일, 최종일)}"""
    if not cfg.DB_PATH.exists():
        return {}
    con = sqlite3.connect(cfg.DB_PATH)
    try:
        rows = con.execute(
            "SELECT acct_idx, COUNT(*), MIN(date), MAX(date) "
            "FROM nav_snapshot GROUP BY acct_idx"
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    con.close()
    return {r[0]: (r[1], r[2], r[3]) for r in rows}


def cmd_list() -> None:
    accts = cfg.load_accounts()
    db = _db_indices()
    print(f"\n.env 계좌 {len(accts)}개:")
    print(f"  {'idx':>3}  {'계좌명':<28} {'운용시작일':<12} {'NAV스냅샷':<10} {'키':<8}")
    print("  " + "-" * 70)
    env_idx = set()
    for a in accts:
        env_idx.add(a.idx)
        n, d0, d1 = db.get(a.idx, (0, "-", "-"))
        keyflag = "OK" if a.app_key and not a.app_key.startswith("계좌") else "미입력"
        span = f"{n}개({d0}~{d1})" if n else "없음"
        print(f"  {a.idx:>3}  {a.name:<28} {a.start or '-':<12} {span:<18} {keyflag}")
    orphan = sorted(set(db) - env_idx)
    if orphan:
        print("\n⚠️ .env 에 없지만 DB에 데이터가 남은 인덱스(삭제된 계좌):", orphan)
        print("   정리하려면:  python manage.py purge <idx>")
    print()


def cmd_purge(idx: int) -> None:
    if not cfg.DB_PATH.exists():
        print("DB 없음.")
        return
    con = sqlite3.connect(cfg.DB_PATH)
    n = con.execute("SELECT COUNT(*) FROM nav_snapshot WHERE acct_idx=?", (idx,)).fetchone()[0]
    for tbl, col in [("nav_snapshot", "acct_idx"), ("realized_pl", "acct_idx"),
                     ("account_meta", "idx")]:
        try:
            con.execute(f"DELETE FROM {tbl} WHERE {col}=?", (idx,))
        except sqlite3.OperationalError:
            pass
    con.commit()
    con.close()
    print(f"인덱스 {idx} 데이터 삭제 완료 (NAV 스냅샷 {n}건). "
          f"대시보드 갱신:  python run.py --compute")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "list":
        cmd_list()
    elif args[0] == "purge" and len(args) == 2 and args[1].isdigit():
        cmd_purge(int(args[1]))
    else:
        print(__doc__)
