"""작업 폴더의 보고서들을 한국어 웹페이지 한 장(report.html)으로 묶는다.

사용법: python render_report.py WORKDIR

WORKDIR 안에서 읽는 파일 (없는 것은 건너뜀):
  instrument.json, decision.json {"rating", "summary"}
  7_final.md, 6_trader.md, 5_research_plan.md
  risk/*.md (aggressive_1, conservative_1, neutral_1, ...), debate/*.md (bull_1, bear_1, ...)
  reports/market.md, reports/sentiment.md, reports/news.md, reports/fundamentals.md
"""

from __future__ import annotations

import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from markdown_it import MarkdownIt

MD = MarkdownIt("commonmark", {"html": False, "linkify": False}).enable("table").enable("strikethrough")

RATING_KO = {"Buy": "매수", "Overweight": "비중 확대", "Hold": "보유", "Underweight": "비중 축소",
             "Sell": "매도", "REVIEW": "확인 필요"}
RATING_TONE = {"Buy": "up", "Overweight": "up", "Hold": "flat", "Underweight": "down", "Sell": "down",
               "REVIEW": "flat"}
SPEAKER = {"bull": "강세 연구원", "bear": "약세 연구원", "aggressive": "공격형 리스크 담당",
           "conservative": "보수형 리스크 담당", "neutral": "중립형 리스크 담당"}


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8").strip() if p.exists() else ""


def _order(p: Path) -> tuple[int, int]:
    m = re.match(r"([a-z]+)_(\d+)", p.stem)
    if not m:
        return (99, 0)
    keys = list(SPEAKER)
    return (int(m.group(2)), keys.index(m.group(1)) if m.group(1) in keys else 9)


def _turns(folder: Path) -> str:
    parts = []
    for p in sorted(folder.glob("*.md"), key=_order):
        m = re.match(r"([a-z]+)_(\d+)", p.stem)
        who = SPEAKER.get(m.group(1), p.stem) if m else p.stem
        rnd = f" · {m.group(2)}라운드" if m else ""
        tone = {"bull": "up", "aggressive": "up", "bear": "down", "conservative": "down"}.get(
            m.group(1) if m else "", "flat")
        parts.append(f'<div class="turn {tone}"><div class="who">{html.escape(who + rnd)}</div>'
                     f'{MD.render(_read(p))}</div>')
    return "".join(parts)


CSS = """
:root{--bg:#f7f7f5;--card:#fff;--ink:#1c1c1a;--sub:#5f5e5a;--line:#e3e2dd;--accent:#2f5d8a;
--up:#1f7a4d;--up-bg:#e6f4ec;--down:#b3392f;--down-bg:#fbeae8;--flat:#6b6a63;--flat-bg:#efeee9}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--card:#1f1f1d;--ink:#ecebe6;--sub:#a5a49d;
--line:#33332f;--accent:#8db7e0;--up:#6fcf9b;--up-bg:#1b2f24;--down:#f08a80;--down-bg:#3a201d;
--flat:#b5b4ad;--flat-bg:#2a2a27}}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.7 "Pretendard","Apple SD Gothic Neo",
"Malgun Gothic",system-ui,sans-serif;word-break:keep-all;overflow-wrap:anywhere}
.wrap{max-width:1080px;margin:0 auto;padding:24px 16px 64px;display:grid;grid-template-columns:220px 1fr;gap:28px}
nav{position:sticky;top:16px;align-self:start;font-size:14px}
nav a{display:block;color:var(--sub);text-decoration:none;padding:5px 10px;border-left:2px solid var(--line)}
nav a:hover{color:var(--accent);border-color:var(--accent)}
header{grid-column:1/-1;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px}
header .meta{color:var(--sub);font-size:14px}
header h1{margin:4px 0 12px;font-size:26px;line-height:1.3}
.badge{display:inline-block;font-weight:700;font-size:20px;padding:6px 16px;border-radius:999px}
.badge.up{color:var(--up);background:var(--up-bg)}.badge.down{color:var(--down);background:var(--down-bg)}
.badge.flat{color:var(--flat);background:var(--flat-bg)}
.summary{margin-top:14px;font-size:17px}
section{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:6px 22px 18px;margin-bottom:18px}
section>h2{font-size:20px;border-bottom:1px solid var(--line);padding-bottom:10px}
main h1{font-size:19px}main h2{font-size:18px}main h3{font-size:16px}
table{border-collapse:collapse;display:block;overflow-x:auto;font-size:14px;margin:10px 0}
th,td{border:1px solid var(--line);padding:6px 10px;text-align:left;white-space:nowrap}
th{background:var(--flat-bg)}code{background:var(--flat-bg);padding:1px 5px;border-radius:4px}
pre{overflow-x:auto;background:var(--flat-bg);padding:10px;border-radius:8px}
blockquote{margin:0;padding-left:12px;border-left:3px solid var(--line);color:var(--sub)}
.turn{border-left:4px solid var(--line);padding:2px 0 2px 14px;margin:16px 0}
.turn.up{border-color:var(--up)}.turn.down{border-color:var(--down)}
.who{font-weight:700;font-size:14px;color:var(--sub)}
details summary{cursor:pointer;font-weight:600;padding:8px 0}
footer{grid-column:1/-1;color:var(--sub);font-size:13px;text-align:center}
@media (max-width:760px){.wrap{grid-template-columns:1fr}nav{position:static;display:flex;flex-wrap:wrap;gap:6px}
nav a{border:1px solid var(--line);border-radius:999px;padding:3px 10px}header h1{font-size:22px}}
@media print{nav{display:none}.wrap{display:block}section{break-inside:avoid-page}}
"""


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    w = Path(sys.argv[1])
    info = json.loads(_read(w / "instrument.json") or "{}")
    decision = json.loads(_read(w / "decision.json") or "{}")
    rating = decision.get("rating", "REVIEW")
    ticker = info.get("ticker", w.name)
    name = (info.get("identity") or {}).get("company_name") or ticker
    date = info.get("date", "")

    sections: list[tuple[str, str, str]] = []

    def add(sid: str, title: str, body_html: str, open_: bool = True) -> None:
        if body_html.strip():
            sections.append((sid, title, body_html if open_ else
                             f"<details><summary>펼쳐 보기</summary>{body_html}</details>"))

    add("final", "최종 결정 — 포트폴리오 매니저", MD.render(_read(w / "7_final.md")))
    add("trader", "트레이더 거래 제안", MD.render(_read(w / "6_trader.md")))
    add("plan", "리서치 매니저 투자 계획", MD.render(_read(w / "5_research_plan.md")))
    add("risk", "리스크 토론", _turns(w / "risk"), open_=False)
    add("debate", "강세 vs 약세 토론", _turns(w / "debate"), open_=False)
    for key, title in (("market", "차트·기술적 분석"), ("sentiment", "투자심리 분석"),
                       ("news", "뉴스·거시 분석"), ("fundamentals", "재무 분석")):
        add(key, f"분석가 보고서 · {title}", MD.render(_read(w / "reports" / f"{key}.md")), open_=False)

    nav = "".join(f'<a href="#{sid}">{html.escape(t.split(" — ")[0])}</a>' for sid, t, _ in sections)
    body = "".join(f'<section id="{sid}"><h2>{html.escape(t)}</h2>{b}</section>' for sid, t, b in sections)
    tone = RATING_TONE.get(rating, "flat")
    page = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(name)} 분석 보고서 {html.escape(date)}</title><style>{CSS}</style></head><body>
<div class="wrap">
<header><div class="meta">{html.escape(ticker)} · 분석 기준일 {html.escape(date)} · 트레이딩 사무실</div>
<h1>{html.escape(name)}</h1>
<span class="badge {tone}">{html.escape(RATING_KO.get(rating, rating))} · {html.escape(rating)}</span>
<div class="summary">{html.escape(decision.get("summary", ""))}</div></header>
<nav>{nav}</nav>
<main>{body}</main>
<footer>AI 직원 12명이 공개 데이터로 작성한 연구용 분석이에요. 투자 권유가 아니며, 같은 날짜로 다시 돌려도 결과가 달라질 수 있어요.
<br>데이터: Yahoo Finance · SEC EDGAR · StockTwits · Reddit · Polymarket (TradingAgents 데이터 계층) · 만든 시각 {datetime.now():%Y-%m-%d %H:%M}</footer>
</div></body></html>"""
    out = w / "report.html"
    out.write_text(page, encoding="utf-8")
    print(json.dumps({"ok": True, "report": str(out), "sections": [s[0] for s in sections]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
