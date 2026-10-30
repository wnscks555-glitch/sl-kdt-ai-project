# Claude 역할: 구현 담당

- 작업 기준은 `handoff/tasks.md` 맨 위 「현행 작업」의 명세와 기대표, 그리고 그 아래 완료 단계들의 보존 조건이다. `docs/`의 기존 문서(재검사 범위)는 이전 기록이다.
- 처음 시작할 때 `handoff/setup-notes.md`를 읽고 배경을 파악한다.
- 작업 전에 `handoff/tasks.md`, `handoff/decisions.md`, `handoff/reviews/`의 최신 파일을 읽는다.
- 리뷰 항목마다 반영/보류/반박과 그 이유를 `handoff/gpt-log.md`에 기록한다. 이 파일은 이력을 잇기 위해 이름을 유지하며, 5단계부터 구현 담당인 Claude가 쓴다.
- 작업 단위마다 커밋한다. 커밋 메시지에 관련 T ID를 넣는다. 자동 검토 루프 안에서는 커밋하지 않는다. 커밋은 루프 스크립트가 한다.
- 실행은 `py -m src.main`, 테스트는 `py -m unittest discover -s tests`로 한다. 이 PC의 `python`은 Store 안내로 연결되므로 쓰지 않는다.
- `handoff/reviews/`, `AGENTS.md`, `.claude/`는 읽기만 한다. `handoff/decisions.md`와 `handoff/tasks.md`는 사용자가 쓰는 파일이라 수정하지 않는다.
- 기대표나 기존 테스트를 구현 결과에 맞춰 고치지 않는다. 맞지 않으면 "명세 이견"으로 기록한다.
- push, 원격 설정 변경, 패키지 설치는 사용자에게 먼저 묻는다.
