# Dev helper - is machine pe local Python nahi hai, sab kuch Docker me chalta hai.
# Code bind-mount hota hai, isliye edit ke baad rebuild ki zaroorat nahi.
#
#   .\dev.ps1 build              # image banao (requirements badle tab hi zaroori)
#   .\dev.ps1 ingest             # docs -> chroma (incremental)
#   .\dev.ps1 ingest -Reset      # wipe karke dobara build
#   .\dev.ps1 ask "why does chunk overlap matter?"
#   .\dev.ps1 test               # pytest suite (no API key needed)
#   .\dev.ps1 eval               # routing eval - ASLI Groq + DuckDuckGo calls
#   .\dev.ps1 eval --limit 5     # smoke run, rate limit bachane ke liye
#   .\dev.ps1 eval -Corpus scifact -Env USE_HYBRID=false,USE_RERANKER=false `
#       --out eval/results_scifact_baseline.json      # A/B ka baseline arm
#   .\dev.ps1 serve [-Port 8042] # FastAPI -> http://localhost:PORT/docs
#   .\dev.ps1 shell              # container ke andar bash
#
# Phase 7 me proper docker-compose.yml aayega; ye tab tak ka scaffolding hai.

param(
    [Parameter(Position = 0)][string]$Command = "ask",
    [Parameter(Position = 1, ValueFromRemainingArguments = $true)][string[]]$Rest,
    [switch]$Reset,
    [int]$Port = 8000,
    # "concepts" (default) ya "scifact" - dono alag Chroma collections me rehte
    # hain, isliye switch karne pe re-ingest nahi karna padta.
    [ValidateSet("", "concepts", "scifact")][string]$Corpus = "",
    # Extra env vars container ke liye: -Env USE_HYBRID=false,USE_RERANKER=false
    # Retrieval ka A/B isi ke bina raw `docker run` likhna padta tha, jisme mounts
    # dobara type karne padte the - aur wahi A/B is project ka core workflow hai.
    [string[]]$Env = @()
)

$ErrorActionPreference = "Stop"
$Root    = $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Image   = "adaptive-crag-backend:dev"

New-Item -ItemType Directory -Force -Path (Join-Path $Backend "vectorstore") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Backend "beir") | Out-Null

# Code + data + vectorstore mount - image sirf dependencies deti hai
$Mounts = @(
    "-v", "${Backend}\app:/app/app",
    "-v", "${Backend}\data:/app/data",
    "-v", "${Backend}\vectorstore:/app/vectorstore",
    "-v", "${Backend}\ingest.py:/app/ingest.py",
    "-v", "${Backend}\main.py:/app/main.py",
    "-v", "${Backend}\tests:/app/tests",
    "-v", "${Backend}\eval:/app/eval",
    # BEIR download host pe cache rehta hai - container har baar 5k abstracts
    # dobara download na kare.
    "-v", "${Backend}\beir:/app/beir"
)

# .env repo root se - secrets image me bake nahi hote
$EnvArgs = @()
$EnvFile = Join-Path $Root ".env"
if (Test-Path $EnvFile) { $EnvArgs += @("--env-file", $EnvFile) }
else { Write-Host "[dev] warning: .env nahi mila - LLM call fail hogi (.env.example copy karo)" -ForegroundColor Yellow }

# -e ke baad aata hai taaki --env-file ki value ko override kare, ulta nahi.
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
        # Baaki flags (jaise --limit) seedha pass ho jaate hain.
        if ($Rest) { $cmdArgs += $Rest }
        docker run --rm @Mounts @EnvArgs $Image @cmdArgs
    }
    "ask" {
        $question = ($Rest -join " ")
        docker run --rm @Mounts @EnvArgs $Image python -m app $question
    }
    "serve" {
        # Is machine pe 8000 aksar doosre projects ke containers le lete hain,
        # isliye port override kar sakte hain: .\dev.ps1 serve -Port 8042
        Write-Host "[dev] http://localhost:$Port/docs" -ForegroundColor Cyan
        docker run --rm -p "${Port}:8000" @Mounts @EnvArgs $Image uvicorn main:app --host 0.0.0.0 --port 8000 --reload
    }
    "test" {
        docker run --rm @Mounts @EnvArgs $Image python -m pytest tests/ -q
    }
    "eval" {
        # Asli Groq + asli DuckDuckGo hit karta hai - tests ke ulat. Rate limit
        # bachane ke liye smoke run: .\dev.ps1 eval --limit 5
        $evalArgs = @("python", "-m", "eval.run_eval") + $Rest
        docker run --rm @Mounts @EnvArgs $Image @evalArgs
    }
    "shell"  { docker run --rm -it @Mounts @EnvArgs $Image bash }
    default  { Write-Host "unknown command: $Command  (build | ingest | ask | test | eval | serve | shell)" }
}
