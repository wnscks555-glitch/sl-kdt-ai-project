# 인수인계: GPT–Claude 교차검수 환경 설정 (claude.ai 채팅 → Claude Code)

작성일: 2026-10-17 (같은 날 주제·위치 변경 반영)

## 배경
- 에스엘(SL) KDT AI 부트캠프 지원용 프로젝트이며 마감은 2026-10-18이다.
- 프로젝트 주제: 「교육용 가상 조립·검사 공정의 진행 조건 판정기」(Python CLI). 확정 명세와 기대표 T1–T10은 `handoff/tasks.md`에 있다.
  - 주제 변경 이력: 램프 조립·검사 진행·보류·재검토(v6) → 명령–응답 로그 검증(검토만 하고 폐기) → 현재 판정기. 재검사 범위는 이번 버전에서 제외한다.
- 역할 분담:
  - GPT(Codex): 구현과 수정을 맡는다.
  - Claude(Claude Code): 읽기 전용 교차검토와 피드백만 맡는다.
  - 사용자: 요구사항 제시, 최종 승인·반려, 결과 설명과 시연을 맡는다.
- 목표: 작성 AI와 읽기 전용 검수 AI를 분리하고 승인 기록과 증거를 남기는 멀티 에이전트 워크플로우를 보여준다.
- 환경: Windows 11, ChatGPT Plus, Claude Pro. 유료 API는 사용하지 않는다. Python은 `py`(3.9)로 실행한다. `python`은 Store 안내로 연결된다.

## 확정한 구조
- 코드 저장소: `C:\Users\PC\Documents\ChatGPT\에스엘 KDT AI 교육 부트캠프\project` (git, GitHub 원격 연결됨). Codex와 Claude Code 모두 이 폴더를 기본으로 연다.
- 상위 폴더의 `outputs\` 등 문서는 저장소 밖이며 검수 대상이 아니다.
- `docs/`의 기존 문서(v6, 재검사 R1–R8 등)는 이전 범위 기록이다. 현행 기준은 `handoff/tasks.md`와 README다.

```
project/
├─ AGENTS.md            Codex 규칙
├─ CLAUDE.md            Claude Code 규칙
├─ .claude/settings.json
├─ src/, tests/, data/  Codex만 수정
├─ docs/                이전 범위 기록 (requirements.md 맨 위 한 줄만 Codex가 추가)
└─ handoff/
   ├─ tasks.md          확정 명세와 기대표
   ├─ gpt-log.md        Codex 변경 내역과 이유, 리뷰 반영 여부
   ├─ reviews/          Claude 검수 결과 (NNN-review.md)
   └─ decisions.md      사용자 승인·반려
```

## 작업 순서
1. 사용자가 `tasks.md`를 작성한다. (완료)
2. Codex가 구현하고 커밋한 뒤 `gpt-log.md`에 기록한다.
3. Claude가 검수하고 결과를 `reviews/`에 남긴다.
4. 사용자가 `decisions.md`에 승인 여부를 기록한다.
5. Codex가 리뷰를 반영한다. 이 과정을 반복한다.

## Claude 권한 원칙
- 허용: 전체 읽기, `git diff`·`git log`·`git status`, 테스트 실행(`py -m unittest`), `handoff/reviews/`에 쓰기
- 금지: `src/`·`tests/`·`AGENTS.md` 수정, commit·push, pip 설치, 파일 삭제
- 목록에 없는 명령은 실행 전에 승인을 묻는 상태로 유지한다. deny 규칙만으로는 셸을 통한 쓰기를 완전히 막을 수 없기 때문이다.

## Claude Code에서 이어서 할 일
- [x] 폴더 구조 확인과 검수 설정 배치 (2026-10-17, `project\`로 통합)
- [x] `handoff/` 폴더와 파일 생성, `tasks.md`에 확정 명세 기록 (2026-10-17)
- [ ] Codex가 `AGENTS.md`를 만들고 설정 파일을 커밋한다.
- [ ] 첫 검수: Codex 완료 보고 뒤 `tasks.md` 기대표 T1–T10, `gpt-log.md`, 최근 git diff를 기준으로 진행하고 테스트를 직접 실행한다.
