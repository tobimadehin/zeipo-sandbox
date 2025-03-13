param (
    [string]$Command = "help",
    [Parameter(ValueFromRemainingArguments=$true)]
    $RemainingArgs
)

# Ensure we're in the project root directory
$projectRoot = Split-Path -Parent $PSScriptRoot

# Verify Docker is running
$dockerRunning = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue
if (-not $dockerRunning) {
    Write-Host "Docker Desktop is not running. Please start it first." -ForegroundColor Red
    exit 1
}

# Set Docker Compose file location
$composeFile = Join-Path $projectRoot "docker\docker-compose.yml"

# Check if the container is already running
function Get-ContainerRunning {
    $result = docker ps --format "{{.Names}}" | Select-String -Pattern "zeipo-whisper-whisper"
    return [bool]$result
}

# Start the container if it's not running
function Start-ContainerIfNeeded {
    if (-not (Get-ContainerRunning)) {
        Write-Host "Starting Whisper container..." -ForegroundColor Yellow
        docker-compose -f $composeFile up -d
        Write-Host "Container started successfully." -ForegroundColor Green
    }
}

# Execute a command in the running container
function Invoke-ContainerCommand {
    param (
        [string]$Cmd
    )
    
    Start-ContainerIfNeeded
    docker-compose -f $composeFile exec whisper $Cmd
}

# Main command handling
switch ($Command) {
    "help" {
        Write-Host "Zeipo Whisper Development Tool" -ForegroundColor Cyan
        Write-Host "--------------------------------" -ForegroundColor Cyan
        Write-Host "Available commands:" -ForegroundColor Cyan
        Write-Host "  test        - Run basic Whisper tests"
        Write-Host "  transcribe  - Transcribe an audio file (transcribe sample.mp3 [--model small])"
        Write-Host "  api         - Start the Whisper API server"
        Write-Host "  benchmark   - Run performance benchmarks on different models"
        Write-Host "  bash        - Open a bash shell in the container"
        Write-Host "  python      - Run a Python command/script in the container"
        Write-Host "  down        - Stop the running container"
        Write-Host "  build       - Rebuild the Docker image"
    }
    
    "test" {
        Write-Host "Running Whisper tests..." -ForegroundColor Cyan
        Invoke-ContainerCommand "python -m tests.test_whisper $RemainingArgs"
    }
    
    "transcribe" {
        Write-Host "Transcribing audio..." -ForegroundColor Cyan
        Invoke-ContainerCommand "python -m src.transcribe $RemainingArgs"
    }
    
    "api" {
        Write-Host "Starting Whisper API..." -ForegroundColor Cyan
        Invoke-ContainerCommand "python -m src.api"
    }
    
    "benchmark" {
        Write-Host "Running benchmarks..." -ForegroundColor Cyan
        Invoke-ContainerCommand "python -m scripts.benchmark $RemainingArgs"
    }
    
    "bash" {
        Write-Host "Opening bash shell in container..." -ForegroundColor Cyan
        Invoke-ContainerCommand "bash"
    }
    
    "python" {
        Write-Host "Running Python in container..." -ForegroundColor Cyan
        Invoke-ContainerCommand "python $RemainingArgs"
    }
    
    "down" {
        Write-Host "Stopping container..." -ForegroundColor Yellow
        docker-compose -f $composeFile down
        Write-Host "Container stopped." -ForegroundColor Green
    }
    
    "build" {
        Write-Host "Building Docker image..." -ForegroundColor Yellow
        docker-compose -f $composeFile build
        Write-Host "Build complete." -ForegroundColor Green
    }
    
    default {
        Write-Host "Unknown command: $Command" -ForegroundColor Red
        Write-Host "Run './scripts/run-whisper.ps1 help' for available commands." -ForegroundColor Yellow
    }
}