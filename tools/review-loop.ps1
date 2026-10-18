#Requires -Version 7
<#
Claude 검토 → Codex 수정 자동 반복 루프.

  pwsh -File tools/review-loop.ps1            # 수정 최대 3회
  pwsh -File tools/review-loop.ps1 -MaxFixes 1

한 회차 = Claude 검토 → (VERDICT: FIX이면) Codex 수정 → 스크립트가 커밋.
마지막 수정 뒤에는 확인용 검토를 한 번 더 한다. 그래서 검토는 최대 MaxFixes+1회다.

멈추는 조건
  - Claude 판정이 VERDICT: PASS (미해결 높음/중간 없음)
  - 수정 횟수가 MaxFixes에 도달
  - Codex가 아무 파일도 바꾸지 않음 (진전 없음)
  - 판정 줄이 없거나 CLI가 실패함

Claude와 Codex는 커밋하지 않는다. 커밋은 이 스크립트가 한다.
사용자 승인(handoff/decisions.md)은 루프가 끝난 뒤 사람이 기록한다.
#>
param(
    [ValidateRange(0, 10)]
    [int]$MaxFixes = 3
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$OutputEncoding = [Text.Encoding]::UTF8

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$reviewDir = Join-Path $root 'handoff/reviews'
$logDir = Join-Path $root 'handoff/loop-logs'
New-Item -ItemType Directory -Force $reviewDir, $logDir | Out-Null

function Stop-Loop([string]$message) {
    Write-Host "`n[루프 종료] $message" -ForegroundColor Yellow
    exit 0
}

function Assert-Command([string]$name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "$name 명령을 찾을 수 없습니다. npm 전역 설치와 PATH를 확인하세요."
    }
}

function Get-NextReviewNumber {
    $nums = Get-ChildItem $reviewDir -Filter '*-review.md' -ErrorAction SilentlyContinue |
        ForEach-Object { if ($_.Name -match '^(\d{3})-review\.md$') { [int]$Matches[1] } }
    $max = ($nums | Measure-Object -Maximum).Maximum
    return [int]$max + 1
}

function Get-Verdict([string]$path) {
    if (-not (Test-Path $path)) { return $null }
    $line = Select-String -Path $path -Pattern '^\s*VERDICT:\s*(PASS|FIX)\s*$' | Select-Object -Last 1
    if ($line) { return $line.Matches[0].Groups[1].Value }
    return $null
}

function Save-Commit([string]$message, [string[]]$paths) {
    git add -- @paths
    git diff --cached --quiet
    if ($LASTEXITCODE -ne 0) {
        git commit -q -m $message
        if ($LASTEXITCODE -ne 0) { throw "커밋 실패: $message" }
    }
}

function Test-Dirty {
    # 루프 자신의 로그(실패한 실행이 남긴 것 포함)는 변경으로 치지 않는다.
    [bool](git status --porcelain -- . ':(exclude)handoff/loop-logs')
}

Assert-Command 'claude'
Assert-Command 'codex'
Assert-Command 'git'

if (Test-Dirty) {
    Stop-Loop '작업 트리에 커밋하지 않은 변경이 있습니다. Codex 작업을 먼저 커밋한 뒤 다시 실행하세요.'
}

# 첫 검토 범위: 마지막 "review:" 커밋 이후 전체. 없으면 저장소 처음부터.
$baseCommit = (git log --grep '^review:' -n 1 --format=%H | Out-String).Trim()
if (-not $baseCommit) { $baseCommit = (git rev-list --max-parents=0 HEAD | Select-Object -First 1).Trim() }
$prevReviewCommit = $null
$prevReviewFile = $null
$fixes = 0

while ($true) {
    $num = '{0:D3}' -f (Get-NextReviewNumber)
    $reviewFile = "handoff/reviews/$num-review.md"
    $round = $fixes + 1
    Write-Host "`n=== 검토 $num (회차 $round, 수정 $fixes/$MaxFixes) ===" -ForegroundColor Cyan

    if ($prevReviewCommit) {
        $scope = @"
이번은 재검토다. 이전 검토 파일은 $prevReviewFile 이다.
변경 범위는 git diff $prevReviewCommit..HEAD 로 확인한다.
- 이전 높음/중간 항목이 해결됐는지 항목별로 판정한다.
- handoff/gpt-log.md의 반박이 근거 있으면 받아들이고 해결로 처리한다.
- 이번 diff와 무관한 새 지적은 높음일 때만 올린다.
"@
    } else {
        $scope = "첫 검토다. 변경 범위는 git diff $baseCommit..HEAD 와 git log $baseCommit..HEAD 로 확인한다(직전 검토 이후 커밋 전체)."
    }

    $claudePrompt = @"
CLAUDE.md의 검수자 규칙을 따른다. 자동 검토 루프의 검토 단계다.
handoff/tasks.md 맨 위 「현행 작업」의 명세와 기대표를 기준으로 코드를 검수하라.
v1 보존 조건(T1-T10 무수정 통과, v1 보고서 바이트 동일)도 반드시 확인한다.
$scope
- 테스트는 py -m unittest discover -s tests 로 직접 실행하고 명령과 결과를 붙인다.
- 결과는 $reviewFile 하나에만 쓴다. 다른 파일은 만들거나 고치지 않는다.
- 심각도는 높음/중간/낮음이다. 낮음은 기록만 하고 수정 요구로 세지 않는다.
- 파일의 마지막 줄에는 반드시 아래 둘 중 하나만 단독으로 쓴다.
  VERDICT: PASS   (미해결 높음/중간이 없을 때)
  VERDICT: FIX    (미해결 높음/중간이 하나라도 있을 때)
"@

    $claudeLog = Join-Path $logDir "$num-claude.txt"
    $claudePrompt | claude -p --permission-mode dontAsk 2>&1 | Tee-Object -FilePath $claudeLog
    if ($LASTEXITCODE -ne 0) { Stop-Loop "Claude 실행 실패 (종료 코드 $LASTEXITCODE). 로그: $claudeLog" }

    $verdict = Get-Verdict (Join-Path $root $reviewFile)
    if (-not $verdict) {
        Save-Commit "review: $num (verdict missing)" @('handoff')
        Stop-Loop "$reviewFile 에 VERDICT 줄이 없습니다. 파일을 직접 확인하세요."
    }
    Save-Commit "review: $num ($verdict)" @('handoff')
    $prevReviewCommit = (git rev-parse HEAD).Trim()
    $prevReviewFile = $reviewFile
    Write-Host "판정: $verdict" -ForegroundColor Green

    if ($verdict -eq 'PASS') { Stop-Loop "검토 $num 통과. handoff/decisions.md에 승인 여부를 기록하세요." }
    if ($fixes -ge $MaxFixes) { Stop-Loop "수정 상한($MaxFixes회)에 도달했습니다. 남은 항목은 $reviewFile 을 보고 직접 결정하세요." }

    Write-Host "`n=== Codex 수정 (리뷰 $num 반영, $($fixes + 1)/$MaxFixes) ===" -ForegroundColor Cyan
    $codexPrompt = @"
AGENTS.md의 구현 담당 규칙을 따른다. 자동 검토 루프의 수정 단계다.
$reviewFile 의 높음/중간 항목만 처리하라. 낮음 항목과 새 기능은 건드리지 않는다.
- 항목마다 반영/보류/반박과 이유를 handoff/gpt-log.md에 기록한다. 리뷰가 틀렸다면 근거를 들어 반박해도 된다.
- handoff/tasks.md의 기대표와 기존 테스트의 기대값을 결과에 맞춰 바꾸지 않는다.
- handoff/reviews/, handoff/decisions.md, CLAUDE.md, .claude/ 는 수정하지 않는다.
- 수정 후 py -m unittest discover -s tests 를 실행하고 결과를 gpt-log.md에 붙인다.
- git commit 은 하지 않는다. 커밋은 루프 스크립트가 한다.
"@

    $codexLast = Join-Path $logDir "$num-codex.txt"
    $codexPrompt | codex exec -C $root -s workspace-write -o $codexLast - 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) { Stop-Loop "Codex 실행 실패 (종료 코드 $LASTEXITCODE)." }

    if (-not (Test-Dirty)) { Stop-Loop 'Codex가 아무 파일도 바꾸지 않았습니다. 진전이 없어 멈춥니다.' }
    $fixes++
    Save-Commit "fix: apply review $num (loop $fixes/$MaxFixes)" @('.')
}
