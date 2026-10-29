"""분석에 쓸 데이터를 미리 모아 파일로 저장한다 (AI 호출 없음).

TradingAgents(https://github.com/TauricResearch/TradingAgents)의 데이터 계층을
그대로 쓴다. 모든 함수는 분석 날짜(trade_date) 이후의 데이터를 내주지 않으므로
과거 날짜로 돌려도 '미래 엿보기'가 생기지 않는다.

사용법:
    python fetch_data.py TICKER YYYY-MM-DD OUTDIR [--analysts market,social,news,fundamentals]

OUTDIR 안에 instrument.json, market.md, sentiment.md, news.md, fundamentals.md 를 만든다.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

try:
    from tradingagents.agents import tools as T
    from tradingagents.agents.context import build_instrument_context, resolve_instrument_identity
    from tradingagents.dataflows.symbols import normalize_symbol, safe_ticker_component
    from tradingagents.dataflows.vendors.reddit import fetch_reddit_posts, subreddits_for
    from tradingagents.dataflows.vendors.stocktwits import fetch_stocktwits_messages
except ImportError:  # pragma: no cover - 설치 안내
    sys.exit(
        "TradingAgents 데이터 모듈이 없어요. 먼저 설치하세요:\n"
        "  pip install -r requirements.txt\n"
        "(또는) pip install \"tradingagents @ git+https://github.com/TauricResearch/TradingAgents@v0.7.1\""
    )

INDICATORS = ["close_10_ema", "close_50_sma", "close_200_sma", "macd", "macds", "macdh",
              "rsi", "boll", "boll_ub", "boll_lb", "atr", "vwma", "mfi"]
MACRO = ["fed_funds_rate", "10y_treasury", "cpi", "unemployment", "vix"]
ALL_ANALYSTS = ("market", "social", "news", "fundamentals")


def _days_back(date: str, days: int) -> str:
    return (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=days)).strftime("%Y-%m-%d")


def _safe(label: str, fn, *args) -> str:
    """도구 하나를 부르고, 실패해도 전체를 멈추지 않는다."""
    try:
        out = fn(*args)
        text = out if isinstance(out, str) else str(out)
    except Exception as exc:  # noqa: BLE001
        text = f"DATA_UNAVAILABLE: {label} 를 가져오지 못했어요 ({type(exc).__name__}: {exc}). 값을 추측하지 마세요."
    return f"## {label}\n\n{text.strip()}\n"


def _write(path: Path, title: str, sections: list[str]) -> None:
    path.write_text(f"# {title}\n\n" + "\n".join(sections), encoding="utf-8")


def market(t: str, d: str) -> list[str]:
    out = [_safe("검증된 시장 스냅샷 (정확한 가격·지표는 여기를 기준으로)",
                 T.get_verified_market_snapshot.func, t, d, 30, d),
           _safe("최근 6개월 일봉 (OHLCV)", T.get_stock_data.func, t, _days_back(d, 180), d, d)]
    for ind in INDICATORS:
        out.append(_safe(f"지표 {ind} (최근 60일)", T.get_indicators.func, t, ind, d, 60, d))
    return out


def social(t: str, d: str) -> list[str]:
    start = _days_back(d, 7)
    return [
        _safe("최근 7일 뉴스 헤드라인", T.get_news.func, t, start, d, d),
        _safe("StockTwits 게시글", fetch_stocktwits_messages, t, 30, 10.0, start, d),
        _safe("Reddit 게시글", lambda: fetch_reddit_posts(t, subreddits_for(t), start_date=start, end_date=d)),
    ]


def news(t: str, d: str) -> list[str]:
    out = [_safe("종목 뉴스 (최근 14일)", T.get_news.func, t, _days_back(d, 14), d, d),
           _safe("세계·거시 뉴스 (최근 7일)", T.get_global_news.func, d, 7, 10, d),
           _safe("내부자 거래", T.get_insider_transactions.func, t, d)]
    if os.environ.get("FRED_API_KEY"):
        for m in MACRO:
            out.append(_safe(f"미국 거시지표 {m}", T.get_macro_indicators.func, m, d, 365, d))
    else:
        out.append("## 미국 거시지표\n\nFRED_API_KEY가 없어 건너뜀. 필요하면 웹 검색으로 보충하세요.\n")
    for topic in ("Fed rate", "recession"):
        out.append(_safe(f"예측시장 확률: {topic}", T.get_prediction_markets.func, topic, 5, d))
    return out


def fundamentals(t: str, d: str) -> list[str]:
    return [
        _safe("기업 개요·밸류에이션", T.get_fundamentals.func, t, d, d),
        _safe("재무상태표 (분기)", T.get_balance_sheet.func, t, "quarterly", d, d),
        _safe("현금흐름표 (분기)", T.get_cashflow.func, t, "quarterly", d, d),
        _safe("손익계산서 (분기)", T.get_income_statement.func, t, "quarterly", d, d),
    ]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ticker")
    ap.add_argument("date", help="분석 날짜 YYYY-MM-DD (오늘 또는 과거)")
    ap.add_argument("outdir")
    ap.add_argument("--analysts", default=",".join(ALL_ANALYSTS))
    ap.add_argument("--asset-type", default=None, choices=["stock", "crypto"])
    a = ap.parse_args()

    try:
        datetime.strptime(a.date, "%Y-%m-%d")
    except ValueError:
        sys.exit(f"날짜 형식이 잘못됐어요: {a.date} (예: 2026-10-29)")
    if a.date > datetime.now().strftime("%Y-%m-%d"):
        sys.exit("미래 날짜는 분석할 수 없어요.")

    ticker = normalize_symbol(a.ticker)
    safe_ticker_component(ticker)  # 경로에 쓸 수 없는 값이면 여기서 멈춘다
    asset_type = a.asset_type or ("crypto" if "-USD" in ticker or ticker.endswith("USDT") else "stock")
    picked = [x.strip() for x in a.analysts.split(",") if x.strip()]
    unknown = set(picked) - set(ALL_ANALYSTS)
    if unknown:
        sys.exit(f"모르는 분석가: {', '.join(sorted(unknown))} (가능: {', '.join(ALL_ANALYSTS)})")

    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)

    identity = resolve_instrument_identity(ticker)
    info = {
        "ticker": ticker,
        "input": a.ticker,
        "date": a.date,
        "asset_type": asset_type,
        "identity": identity,
        "instrument_context": build_instrument_context(ticker, asset_type, identity, a.date),
        "analysts": picked,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }
    (out / "instrument.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")

    jobs = {"market": ("market.md", "시장·기술적 데이터", market),
            "social": ("sentiment.md", "투자심리 데이터", social),
            "news": ("news.md", "뉴스·거시 데이터", news),
            "fundamentals": ("fundamentals.md", "재무 데이터", fundamentals)}
    for key in picked:
        fname, title, fn = jobs[key]
        if key == "fundamentals" and asset_type == "crypto":
            _write(out / fname, title, ["코인은 재무제표가 없어요. 이 분석가는 건너뛰세요.\n"])
            continue
        _write(out / fname, f"{title} — {ticker} ({a.date} 기준)", fn(ticker, a.date))

    name = identity.get("company_name", "이름 확인 안 됨")
    print(json.dumps({"ok": True, "ticker": ticker, "name": name, "outdir": str(out),
                      "files": sorted(p.name for p in out.iterdir())}, ensure_ascii=False))


if __name__ == "__main__":
    main()
