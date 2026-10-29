---
name: analyze
description: 트레이딩 사무실 팀장. 종목 이름이나 코드(삼성전자, 005930.KS, NVDA, BTC-USD)를 받아 AI 직원 12명(분석가 4·강세/약세 연구원·리서치 매니저·트레이더·리스크 3·포트폴리오 매니저)을 TradingAgents 방식으로 돌리고 한국어 보고서 웹페이지와 최종 등급을 낸다. "종목 분석해줘", "삼성전자 어때", "NVDA 사도 돼?", "트레이딩 사무실", "관심종목 분석" 같은 요청에 쓴다.
---

# 트레이딩 사무실 — 팀장 업무 순서

TradingAgents(Tauric Research)의 회사 구조를 그대로 따른다: 분석가 4명이 동시에 조사 → 강세/약세 토론 → 리서치 매니저 → 트레이더 → 리스크 3명 토론 → 포트폴리오 매니저 최종 결정. 데이터 수집만 TradingAgents 코드를 쓰고, 생각은 모두 Claude 직원들이 한다.

## 0. 입력 정리

요청에서 다음을 뽑는다. 빠진 것은 기본값을 쓰고, **사람이 없는 자동 실행(GitHub Actions)에서는 절대 질문하지 않는다.**

| 항목 | 기본값 |
|---|---|
| 종목 (여러 개 가능) | 없으면 저장소의 `관심종목.txt` |
| 분석 날짜 | 오늘 (Asia/Seoul) — 미래 날짜는 거절 |
| 분석가 | market, social, news, fundamentals 전부 |
| 강세/약세 토론 라운드 | 1 |
| 리스크 토론 라운드 | 1 |
| 보유 현황 | 없음 (사용자가 "100주 갖고 있어" 등 말하면 반영) |

종목 이름은 Yahoo Finance 코드로 바꾼다: 코스피 `6자리.KS`, 코스닥 `6자리.KQ`, 미국은 그대로(`NVDA`), 코인은 `BTC-USD`. 확실하지 않으면 웹 검색으로 종목코드를 확인한다.

## 1. 준비

- `SCRIPTS` = 이 스킬 폴더의 `scripts/` (스킬을 불러올 때 표시되는 "Base directory" 기준)
- `BASE` = 현재 작업 폴더. 그 안에 `보고서/`와 `기억/`을 쓴다. (데스크톱에서 연결된 폴더가 있으면 그 폴더를 BASE로 쓴다.)
- 파이썬 준비: `PY=$(bash "$SCRIPTS/setup.sh" | tail -n 1)`. 처음에는 1~3분 걸린다. 실패하면 오류를 사용자에게 그대로 알리고 멈춘다.
- 모든 스크립트는 `cd "$BASE"` 한 상태에서 `"$PY" -I "$SCRIPTS/..."`로 실행한다.

**직원 이름**: 에이전트 목록에 `trading-office:market-analyst`처럼 앞에 `trading-office:`가 붙은 이름이 있으면 그것을, 없으면 `market-analyst`처럼 붙지 않은 이름을 쓴다.

## 2. 지난 판단 채점 (기억)

1. `"$PY" -I "$SCRIPTS/memory.py" settle` 실행.
2. 출력의 `need_lesson` 항목마다 팀장이 직접 교훈을 쓴다. 해당 `report` 폴더의 `7_final.md`가 있으면 읽고, 다음을 **2~4문장 평문**으로 쓴다:
   (1) N거래일 초과수익(alpha)이 방향 판단에 대해 말해 주는 것 — 수치 인용, 기간이 너무 짧아 논리를 판단할 수 없으면 그렇다고 말하기
   (2) 이 기간이 투자 논리의 어느 부분을 지지하거나 약화시키는지
   (3) 다음 비슷한 분석에 적용할 구체적 교훈 하나
3. `"$PY" -I "$SCRIPTS/memory.py" lesson --id <id> --text "<교훈>"`으로 저장.

## 3. 종목마다 반복

`WORKDIR = 보고서/<날짜>_<종목코드>` (예: `보고서/2026-10-29_005930.KS`). 같은 폴더가 있으면 안의 이전 결과를 지우고 새로 만든다.

### 3-1. 데이터 수집 (AI 호출 없음)
```
"$PY" -I "$SCRIPTS/fetch_data.py" <종목> <날짜> "$WORKDIR" --analysts <분석가 목록>
"$PY" -I "$SCRIPTS/memory.py" context --ticker <종목> --date <날짜> > "$WORKDIR/lessons.md"
```
보유 현황이 있으면 `$WORKDIR/portfolio.md`에 적는다. 출력의 `name`으로 회사 이름을 확인하고, 사용자가 말한 회사와 다르면 멈추고 알린다.
`mkdir -p "$WORKDIR/reports" "$WORKDIR/debate" "$WORKDIR/risk"`

### 3-2. 분석가 (동시에)
고른 분석가들을 **한 번의 응답에서 동시에** Agent로 부른다. 각자에게 작업 폴더의 절대 경로를 준다.

| 키 | 직원 | 결과 파일 |
|---|---|---|
| market | market-analyst | reports/market.md |
| social | sentiment-analyst | reports/sentiment.md |
| news | news-analyst | reports/news.md |
| fundamentals | fundamentals-analyst | reports/fundamentals.md |

모두 끝나면 결과 파일이 있는지 확인한다. 없는 것은 한 번만 다시 시키고, 그래도 없으면 "보고서 없음"으로 두고 진행한다.

### 3-3. 강세/약세 토론 (순서대로)
라운드 n = 1..R 마다: `bull-researcher`(라운드 n) → 끝나면 `bear-researcher`(라운드 n). 동시에 부르지 않는다(상대 주장을 읽어야 한다).

### 3-4. 리서치 매니저 → 트레이더
`research-manager` → `5_research_plan.md`. 그다음 `trader` → `6_trader.md`.

### 3-5. 리스크 토론 (순서대로)
라운드 n = 1..R 마다: `aggressive-risk` → `conservative-risk` → `neutral-risk`.

### 3-6. 최종 결정
`portfolio-manager` → `7_final.md`, `decision.json`.
`decision.json`의 rating이 Buy/Overweight/Hold/Underweight/Sell 중 하나가 아니면, `7_final.md` 첫 줄의 `**Rating**:` 값을 확인한다. 그래도 알 수 없으면 rating을 `REVIEW`로 고친다(Hold로 바꾸지 않는다).

### 3-7. 보고서·기록
```
"$PY" -I "$SCRIPTS/render_report.py" "$WORKDIR"
"$PY" -I "$SCRIPTS/memory.py" record --ticker <종목> --date <날짜> --rating <등급> --name "<회사명>" --summary "<요약>" --report "$WORKDIR"
```
그리고 `$WORKDIR/summary.md`를 쓴다 (GitHub 이슈 댓글로도 쓰인다):
```
## <회사명> (<종목코드>) · <날짜>
**최종 등급: <한국어 등급> (<영어 등급>)**

<요약 1~2문장>

- 트레이더 제안: <Action>, 진입 <가격>, 손절 <가격>, 비중 <...>
- 리서치 매니저: <Recommendation>
- 전체 보고서: `<WORKDIR>/report.html`

> 연구용 AI 분석이며 투자 권유가 아니에요.
```

## 4. 마무리

- 사용자에게: 종목별 최종 등급과 한 줄 요약을 표로 보여 주고, 보고서 웹페이지(`report.html`)를 파일로 전달한다(데스크톱이면 파일을 보여 주고, 자동 실행이면 경로만).
- 데이터가 막혀 빠진 부분(예: 한국 종목의 StockTwits)이 있었으면 한 줄로 알린다.
- 분석가 보고서 내용을 채팅에 길게 다시 쓰지 않는다.

## 지켜야 할 것

- 분석 날짜 이후의 정보는 어떤 직원도 쓰지 않는다. 데이터 스크립트가 이미 막아 주지만, 웹 검색도 날짜를 지킨다.
- 직원이 실패하거나 엉뚱한 결과를 내면 한 번 다시 시킨다. 팀장이 직원 대신 보고서를 지어내지 않는다.
- 등급 라벨 줄(`**Rating**:`, `**Recommendation**:`, `**Action**:`)은 영어 값 그대로 둔다.
- 투자 조언이 아니라 연구용 분석이라는 점을 결과에 항상 밝힌다.
