# Dev helper - there is no local Python on this machine, everything runs in
# Docker. The code is bind-mounted, so an edit needs no rebuild.
#
#   .\dev.ps1 build              # build the image (only needed when requirements change)
#   .\dev.ps1 ingest             # docs -> chroma (incremental)
#   .\dev.ps1 ingest -Reset      # wipe and rebuild
#   .\dev.ps1 ask "why does chunk overlap matter?"
#   .\dev.ps1 test               # pytest suite (no API key needed)
#   .\dev.ps1 eval               # routing eval - REAL Groq + DuckDuckGo calls
#   .\dev.ps1 eval --limit 5     # smoke run, saves rate limit
#   .\dev.ps1 eval -Corpus scifact -Env USE_HYBRID=false,USE_RERANKER=false `
#       --out eval/results_scifact_baseline.json      # A/B ka baseline arm
#   .\dev.ps1 serve [-Port 8042] # FastAPI -> http://localhost:PORT/docs
#   .\dev.ps1 shell              # bash inside the container

param(
    [Parameter(Position = 0)][string]$Command = "ask",
    [Parameter(Position = 1, ValueFromRemainingArguments = $true)][string[]]$Rest,
    [switch]$Reset,
    [int]$Port = 8000,
    # "concepts" (default) or "scifact" - they live in separate Chroma
    # collections, so switching needs no re-ingest.
    [ValidateSet("", "concepts", "scifact")][string]$Corpus = "",
    # Extra env vars for the container: -Env USE_HYBRID=false,USE_RERANKER=false
    # Without this the retrieval A/B meant hand-writing a raw `docker run` with
    # all its mounts - and that A/B is this project's core workflow.
    [string[]]$Env = @()
)

$ErrorActionPreference = "Stop"
$Root    = $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Image   = "adaptive-crag-backend:dev"

New-Item -ItemType Directory -Force -Path (Join-Path $Backend "vectorstore") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Backend "beir") | Out-Null

# Mount code, data and the vector store - the image provides dependencies only
$Mounts = @(
    "-v", "${Backend}\app:/app/app",
    "-v", "${Backend}\data:/app/data",
    "-v", "${Backend}\vectorstore:/app/vectorstore",
    "-v", "${Backend}\ingest.py:/app/ingest.py",
    "-v", "${Backend}\main.py:/app/main.py",
    "-v", "${Backend}\tests:/app/tests",
    "-v", "${Backend}\eval:/app/eval",
    # The BEIR download is cached on the host so the container does not re-fetch
    # 5k abstracts every run.
    "-v", "${Backend}\beir:/app/beir"
)

# .env from the repo root - secrets are never baked into the image
$EnvArgs = @()
$EnvFile = Join-Path $Root ".env"
if (Test-Path $EnvFile) { $EnvArgs += @("--env-file", $EnvFile) }
else { Write-Host "[dev] warning: no .env found - LLM calls will fail (copy .env.example)" -ForegroundColor Yellow }

# Comes after -e so it overrides --env-file, not the other way round.
if ($Corpus) { $EnvArgs += @("-e", "CORPUS=$Corpus") }
foreach ($pair in $Env) {
    foreach ($kv in ($pair -split ",")) {
        if ($kv.Trim()) { $EnvArgs += @("-e", $kv.Trim()) }
    }
}

switch ($Command) {
    "build"  { docker build -t $Image $Backend }
    "ingest" {
        $cmdArgs = @("python", "ingest.py")
        if ($Reset) { $cmdArgs += "--reset" }
        if ($Corpus) { $cmdArgs += @("--corpus", $Corpus) }
        # Other flags (--limit and so on) pass straight through.
        if ($Rest) { $cmdArgs += $Rest }
        docker run --rm @Mounts @EnvArgs $Image @cmdArgs
    }
    "ask" {
        $question = ($Rest -join " ")
        docker run --rm @Mounts @EnvArgs $Image python -m app $question
    }
    "serve" {
        # Other projects' containers often hold 8000 on this machine, so the
        # port can be overridden: .\dev.ps1 serve -Port 8042
        Write-Host "[dev] http://localhost:$Port/docs" -ForegroundColor Cyan
        docker run --rm -p "${Port}:8000" @Mounts @EnvArgs $Image uvicorn main:app --host 0.0.0.0 --port 8000 --reload
    }
    "test" {
        docker run --rm @Mounts @EnvArgs $Image python -m pytest tests/ -q
    }
    "eval" {
        # Hits real Groq and real DuckDuckGo, unlike the tests. For a smoke run
        # that saves rate limit: .\dev.ps1 eval --limit 5
        $evalArgs = @("python", "-m", "eval.run_eval") + $Rest
        docker run --rm @Mounts @EnvArgs $Image @evalArgs
    }
    "shell"  { docker run --rm -it @Mounts @EnvArgs $Image bash }
    default  { Write-Host "unknown command: $Command  (build | ingest | ask | test | eval | serve | shell)" }
}
