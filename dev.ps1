# Dev helper - is machine pe local Python nahi hai, sab kuch Docker me chalta hai.
# Code bind-mount hota hai, isliye edit ke baad rebuild ki zaroorat nahi.
#
#   .\dev.ps1 build              # image banao (requirements badle tab hi zaroori)
#   .\dev.ps1 ingest             # docs -> chroma (incremental)
#   .\dev.ps1 ingest -Reset      # wipe karke dobara build
#   .\dev.ps1 ask "why does chunk overlap matter?"
#   .\dev.ps1 test               # pytest suite
#   .\dev.ps1 serve [-Port 8042] # FastAPI -> http://localhost:PORT/docs
#   .\dev.ps1 shell              # container ke andar bash
#
# Phase 7 me proper docker-compose.yml aayega; ye tab tak ka scaffolding hai.

param(
    [Parameter(Position = 0)][string]$Command = "ask",
    [Parameter(Position = 1, ValueFromRemainingArguments = $true)][string[]]$Rest,
    [switch]$Reset,
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$Root    = $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Image   = "adaptive-crag-backend:dev"

New-Item -ItemType Directory -Force -Path (Join-Path $Backend "vectorstore") | Out-Null

# Code + data + vectorstore mount - image sirf dependencies deti hai
$Mounts = @(
    "-v", "${Backend}\app:/app/app",
    "-v", "${Backend}\data:/app/data",
    "-v", "${Backend}\vectorstore:/app/vectorstore",
    "-v", "${Backend}\ingest.py:/app/ingest.py",
    "-v", "${Backend}\main.py:/app/main.py",
    "-v", "${Backend}\tests:/app/tests"
)

# .env repo root se - secrets image me bake nahi hote
$EnvArgs = @()
$EnvFile = Join-Path $Root ".env"
if (Test-Path $EnvFile) { $EnvArgs = @("--env-file", $EnvFile) }
else { Write-Host "[dev] warning: .env nahi mila - LLM call fail hogi (.env.example copy karo)" -ForegroundColor Yellow }

switch ($Command) {
    "build"  { docker build -t $Image $Backend }
    "ingest" {
        $cmdArgs = @("python", "ingest.py")
        if ($Reset) { $cmdArgs += "--reset" }
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
    "shell"  { docker run --rm -it @Mounts @EnvArgs $Image bash }
    default  { Write-Host "unknown command: $Command  (build | ingest | ask | test | serve | shell)" }
}
