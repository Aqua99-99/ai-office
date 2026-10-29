---
name: scorecard
description: 트레이딩 사무실 성적표. 지금까지 내린 판단을 실제 주가로 채점하고(분석일 다음 종가부터 5거래일, 시장지수 대비), 등급별 적중률·평균 초과수익과 교훈을 보여 준다. "성적표", "지난 판단 맞았어?", "적중률", "트레이딩 사무실 기록" 같은 요청에 쓴다.
---

# 트레이딩 사무실 — 성적표

1. `SCRIPTS` = 이 스킬 폴더 옆의 `../analyze/scripts/`. `BASE` = 현재 작업 폴더(`기억/decisions.json`이 있는 곳). `cd "$BASE"`.
2. `PY=$(bash "$SCRIPTS/setup.sh" | tail -n 1)`
3. `"$PY" -I "$SCRIPTS/memory.py" settle` — 새로 채점된 항목 중 `need_lesson`이 있으면, analyze 스킬 2단계와 같은 방식(2~4문장: 수치 인용 → 논리의 어느 부분이 맞고 틀렸는지 → 다음에 적용할 교훈 하나)으로 교훈을 쓰고 `memory.py lesson`으로 저장한다.
4. `"$PY" -I "$SCRIPTS/memory.py" scorecard [--ticker 종목]` 결과를 한국어로 정리해 보여 준다.
   - 등급별: 건수, 방향 적중률(Buy/Overweight는 초과수익 > 0, Underweight/Sell은 < 0 이면 적중. Hold는 방향을 주장하지 않으므로 적중률 없음), 평균 초과수익
   - 최근 판단 10개와 교훈
   - 채점 대기 중인 건수
5. 꼭 덧붙인다: 표본이 적으면(등급별 10건 미만) 우연일 가능성이 크고, 5거래일은 장기 논리를 판단하기에 짧으며, 같은 날짜로 다시 돌려도 AI 판단이 달라질 수 있다는 점.
