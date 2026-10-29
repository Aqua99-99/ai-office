"""트레이딩 사무실의 기억: 판단을 기록하고, 나중에 결과로 채점하고, 교훈을 남긴다.

저장 위치: 기본 ./기억/decisions.json (환경변수 TRADING_OFFICE_HOME 으로 바꿀 수 있음)

명령:
  record    --ticker T --date D --rating R [--name N] [--summary S] [--report PATH]
  settle    [--holding 5]          채점할 때가 된 판단을 채점하고, 교훈이 필요한 항목을 출력
  lesson    --id ID --text "..."   채점된 판단에 교훈(2~4문장)을 붙임
  context   --ticker T --date D    포트폴리오 매니저가 읽을 지난 교훈 (D 이전 것만)
  scorecard [--ticker T]           등급별 적중률·평균 초과수익
  list      [--ticker T]           기록 목록
채점 방식(TradingAgents와 같음): 분석일 다음 첫 종가에 들어가서, holding 거래일 뒤 종가까지의
수익률과, 같은 기간 시장지수 대비 초과수익(alpha)을 잰다. 아직 장이 끝나지 않은 날은 쓰지 않는다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

DIRECTION = {"Buy": 1, "Overweight": 1, "Hold": 0, "Underweight": -1, "Sell": -1}
RATINGS = tuple(DIRECTION)
BENCHMARKS = {
    ".KS": "^KS11", ".KQ": "^KQ11", ".T": "^N225", ".HK": "^HSI", ".SS": "000001.SS",
    ".SZ": "399001.SZ", ".NS": "^NSEI", ".BO": "^BSESN", ".TW": "^TWII", ".L": "^FTSE",
    ".DE": "^GDAXI", ".PA": "^FCHI", ".TO": "^GSPTSE", ".AX": "^AXJO",
}


def home() -> Path:
    return Path(os.environ.get("TRADING_OFFICE_HOME", "기억"))


def db_path() -> Path:
    return home() / "decisions.json"


def load() -> list[dict]:
    p = db_path()
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def save(entries: list[dict]) -> None:
    p = db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def benchmark_for(ticker: str) -> str:
    if "." in ticker:
        suffix = "." + ticker.rsplit(".", 1)[1].upper()
        if suffix in BENCHMARKS:
            return BENCHMARKS[suffix]
    return "SPY"


def _closes(symbol: str, start: str, end: str):
    import yfinance as yf

    df = yf.download(symbol, start=start, end=end, progress=False, auto_adjust=True)
    if df is None or df.empty:
        return []
    close = df["Close"]
    if hasattr(close, "columns"):  # 여러 단계 열 이름
        close = close.iloc[:, 0]
    return [(idx.strftime("%Y-%m-%d"), float(v)) for idx, v in close.dropna().items()]


def _window_return(symbol: str, date: str, holding: int):
    """(entry_date, exit_date, return) 또는 아직 채점 불가면 None."""
    start = date
    end = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=holding * 3 + 20)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")
    bars = [(d, c) for d, c in _closes(symbol, start, end) if d > date and d < today]
    if len(bars) <= holding:
        return None
    (d0, c0), (d1, c1) = bars[0], bars[holding]
    return d0, d1, c1 / c0 - 1


def cmd_record(a) -> None:
    rating = a.rating.strip().capitalize()
    if rating not in RATINGS and rating.upper() != "REVIEW":
        sys.exit(f"등급은 {', '.join(RATINGS)} 또는 REVIEW 중 하나여야 해요: {a.rating}")
    entries = load()
    entries = [e for e in entries if not (e["ticker"] == a.ticker and e["date"] == a.date)]
    entries.append({
        "id": f"{a.date}_{a.ticker}", "ticker": a.ticker, "name": a.name or "", "date": a.date,
        "rating": rating if rating in RATINGS else "REVIEW", "summary": a.summary or "",
        "report": a.report or "", "status": "pending", "recorded_at": datetime.now().isoformat(timespec="seconds"),
    })
    entries.sort(key=lambda e: (e["date"], e["ticker"]))
    save(entries)
    print(json.dumps({"ok": True, "id": f"{a.date}_{a.ticker}", "rating": rating}, ensure_ascii=False))


def cmd_settle(a) -> None:
    entries = load()
    settled, failed = [], []
    for e in entries:
        if e["status"] != "pending" or e["rating"] == "REVIEW":
            continue
        bench = benchmark_for(e["ticker"])
        try:
            r = _window_return(e["ticker"], e["date"], a.holding)
            b = _window_return(bench, e["date"], a.holding)
        except Exception as exc:  # noqa: BLE001
            failed.append({"id": e["id"], "reason": str(exc)})
            continue
        if r is None or b is None:
            continue
        e.update(status="settled", benchmark=bench, holding_days=a.holding, entry_date=r[0],
                 exit_date=r[1], raw_return=round(r[2], 4), alpha=round(r[2] - b[2], 4))
        settled.append(e)
    save(entries)
    need = [e for e in entries if e["status"] == "settled" and not e.get("lesson")]
    print(json.dumps({"newly_settled": [e["id"] for e in settled], "failed": failed,
                      "need_lesson": [{k: e.get(k) for k in ("id", "ticker", "name", "date", "rating",
                                                              "raw_return", "alpha", "benchmark",
                                                              "holding_days", "summary", "report")}
                                      for e in need]}, ensure_ascii=False, indent=2))


def cmd_lesson(a) -> None:
    entries = load()
    for e in entries:
        if e["id"] == a.id:
            e["lesson"] = a.text.strip()
            e["status"] = "learned"
            save(entries)
            print(json.dumps({"ok": True, "id": a.id}, ensure_ascii=False))
            return
    sys.exit(f"그런 기록이 없어요: {a.id}")


def _line(e: dict) -> str:
    res = (f"{e['holding_days']}거래일 수익 {e['raw_return']:+.1%}, {e['benchmark']} 대비 {e['alpha']:+.1%}"
           if "alpha" in e else "아직 채점 전")
    return f"- [{e['date']} {e['ticker']} {e['rating']}] {res}. 교훈: {e.get('lesson', '-')}"


def cmd_context(a) -> None:
    past = [e for e in load() if e["date"] < a.date and e.get("lesson")]
    past.sort(key=lambda e: e["date"], reverse=True)
    same = [e for e in past if e["ticker"] == a.ticker][:3]
    other = [e for e in past if e["ticker"] != a.ticker][:2]
    if not same and not other:
        print("(지난 교훈 없음 — 첫 분석이거나 아직 채점된 판단이 없어요)")
        return
    if same:
        print(f"같은 종목({a.ticker})의 지난 판단:")
        print("\n".join(_line(e) for e in same))
    if other:
        print("다른 종목에서 얻은 교훈:")
        print("\n".join(_line(e) for e in other))


def cmd_scorecard(a) -> None:
    entries = [e for e in load() if not a.ticker or e["ticker"] == a.ticker]
    done = [e for e in entries if "alpha" in e]
    out = {"total": len(entries), "scored": len(done),
           "pending": sum(1 for e in entries if e["status"] == "pending"), "by_rating": {}}
    for r in RATINGS:
        grp = [e for e in done if e["rating"] == r]
        if not grp:
            continue
        d = DIRECTION[r]
        hits = [e for e in grp if (e["alpha"] > 0) == (d > 0)] if d else []
        out["by_rating"][r] = {"count": len(grp),
                               "hit_rate": round(len(hits) / len(grp), 3) if d else None,
                               "mean_alpha": round(sum(e["alpha"] for e in grp) / len(grp), 4)}
    out["recent"] = [_line(e) for e in sorted(entries, key=lambda e: e["date"], reverse=True)[:10]]
    print(json.dumps(out, ensure_ascii=False, indent=2))


def cmd_list(a) -> None:
    for e in load():
        if not a.ticker or e["ticker"] == a.ticker:
            print(_line(e) + f"  ({e['status']})")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("record")
    p.add_argument("--ticker", required=True)
    p.add_argument("--date", required=True)
    p.add_argument("--rating", required=True)
    p.add_argument("--name")
    p.add_argument("--summary")
    p.add_argument("--report")
    p = sub.add_parser("settle")
    p.add_argument("--holding", type=int, default=5)
    p = sub.add_parser("lesson")
    p.add_argument("--id", required=True)
    p.add_argument("--text", required=True)
    p = sub.add_parser("context")
    p.add_argument("--ticker", required=True)
    p.add_argument("--date", required=True)
    p = sub.add_parser("scorecard")
    p.add_argument("--ticker")
    p = sub.add_parser("list")
    p.add_argument("--ticker")
    a = ap.parse_args()
    {"record": cmd_record, "settle": cmd_settle, "lesson": cmd_lesson, "context": cmd_context,
     "scorecard": cmd_scorecard, "list": cmd_list}[a.cmd](a)


if __name__ == "__main__":
    main()
