param (
    [string]$Command = "help",
    [Parameter(ValueFromRemainingArguments=$true)]
    $RemainingArgs
)

# Ensure we're in the project root directory
$projectRoot = Split-Path -Parent $PSScriptRoot

# Convert Windows path to WSL path
function ConvertTo-WslPath {
    param (
        [string]$WindowsPath
    )
    $wslPath = wsl wslpath -u "'$WindowsPath'"
    return $wslPath.Trim()
}

# Set project paths
$wslProjectRoot = ConvertTo-WslPath -WindowsPath $projectRoot
$composeFile = Join-Path $projectRoot "docker\docker-compose.yml"
$wslComposeFile = ConvertTo-WslPath -WindowsPath $composeFile

# Verify WSL and Docker are running
try {
    $null = wsl -- docker ps
    Write-Host "Docker is working correctly in WSL." -ForegroundColor Green
} catch {
    Write-Host "Docker commands aren't working in WSL. Attempting to start Docker..." -ForegroundColor Yellow
    
    # Try starting Docker daemon in detached mode
    wsl -- sudo dockerd > /dev/null 2>&1 &
    Start-Sleep -Seconds 5
    
    # Check again if Docker works now
    try {
        $null = wsl -- docker ps
        Write-Host "Docker daemon started successfully." -ForegroundColor Green
    } catch {
        Write-Host "Failed to start Docker in WSL. Please start it manually with 'sudo dockerd &'" -ForegroundColor Red
        exit 1
    }
}

# Check if the container is already running
function Get-ContainerRunning {
    $result = wsl docker ps --format "{{.Names}}" | Select-String -Pattern "docker-whisper-1"
    return [bool]$result
}

# Execute WSL command with direct output
function Invoke-WslCommand {
    param (
        [string]$Command
    )
    
    # Run with direct output streaming to console
    wsl -- bash -c "$Command"
    return $LASTEXITCODE
}

# Main command handling
switch ($Command) {
    "help" {
        Write-Host "Zeipo Whisper Development Tool (WSL Mode)" -ForegroundColor Cyan
        Write-Host "--------------------------------------" -ForegroundColor Cyan
        Write-Host "Available commands:" -ForegroundColor Cyan
        Write-Host "  test           - Run basic Whisper tests"
        Write-Host "  transcribe     - Transcribe an audio file (transcribe sample.mp3 [--model small])"
        Write-Host "  api            - Start the Whisper API server"
        Write-Host "  benchmark      - Run performance benchmarks on different models"
        Write-Host "  bash           - Open a bash shell in the container"
        Write-Host "  python         - Run a Python command/script in the container"
        Write-Host "  down           - Stop the running container"
        Write-Host "  build          - Rebuild the Docker image"
        Write-Host "  gpu            - Test GPU access in container"
        Write-Host "  build          - Build with detailed progress output"
        Write-Host "  silent-build   - Build without progress output"
        Write-Host "  start          - Just start the container"
        Write-Host "  logs           - View container logs"
    }
    
    "gpu" {
        Write-Host "Testing GPU access directly in WSL..." -ForegroundColor Cyan
        Invoke-WslCommand "nvidia-smi"
        
        Write-Host "`nTesting GPU in Docker container..." -ForegroundColor Cyan
        Invoke-WslCommand "cd $wslProjectRoot && docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi"
    }
    
    "test" {
        Write-Host "Running Whisper tests..." -ForegroundColor Cyan
        $args = $RemainingArgs -join " "
        
        Write-Host "Starting container (if needed)..." -ForegroundColor Yellow
        Invoke-WslCommand "cd $wslProjectRoot && docker-compose -f $wslComposeFile up -d"
        
        Write-Host "Executing tests..." -ForegroundColor Yellow
        Invoke-WslCommand "cd $wslProjectRoot && docker-compose -f $wslComposeFile exec whisper python -m tests.test_whisper $args"
    }
    
    "transcribe" {
        Write-Host "Transcribing audio..." -ForegroundColor Cyan
        $args = $RemainingArgs -join " "
        
        Write-Host "Starting container (if needed)..." -ForegroundColor Yellow
        Invoke-WslCommand "cd $wslProjectRoot && docker-compose -f $wslComposeFile up -d"
        
        Write-Host "Executing transcription..." -ForegroundColor Yellow
        Invoke-WslCommand "cd $wslProjectRoot && docker-compose -f $wslComposeFile exec whisper python -m src.transcribe $args"
    }
    
    "api" {
        Write-Host "Starting Whisper API..." -ForegroundColor Cyan
        
        Write-Host "Starting container (if needed)..." -ForegroundColor Yellow
        Invoke-WslCommand "cd $wslProjectRoot && docker-compose -f $wslComposeFile up -d"
        
        Write-Host "Starting API server..." -ForegroundColor Yellow
        Invoke-WslCommand "cd $wslProjectRoot && docker-compose -f $wslComposeFile exec whisper python -m src.api"
    }
    
    "bash" {
        Write-Host "Opening bash shell in container..." -ForegroundColor Cyan
  
        Write-Host "Starting container (if needed)..." -ForegroundColor Yellow
        Invoke-WslCommand "cd $wslProjectRoot && docker-compose -f $wslComposeFile up -d"

        wsl -e bash -c "cd $wslProjectRoot && docker-compose -f $wslComposeFile exec whisper bash"
    }
    
    "python" {
        Write-Host "Running Python in container..." -ForegroundColor Cyan
        $args = $RemainingArgs -join " "
        
        Write-Host "Starting container (if needed)..." -ForegroundColor Yellow
        Invoke-WslCommand "cd $wslProjectRoot && docker-compose -f $wslComposeFile up -d"

        Write-Host "Executing Python command..." -ForegroundColor Yellow
        Invoke-WslCommand "cd $wslProjectRoot && docker-compose -f $wslComposeFile exec whisper python $args"
    }
    
    "down" {
        Write-Host "Stopping container..." -ForegroundColor Yellow
        Invoke-WslCommand "cd $wslProjectRoot && docker-compose -f $wslComposeFile down"
        Write-Host "Container stopped." -ForegroundColor Green
    }
    
    "silent-build" {
        Write-Host "Building Docker image..." -ForegroundColor Yellow
        Invoke-WslCommand "cd $wslProjectRoot && docker-compose -f $wslComposeFile build"
        Write-Host "Build complete." -ForegroundColor Green
    }
    
    "build" {
        Write-Host "Building Docker image with detailed output..." -ForegroundColor Yellow
        Invoke-WslCommand "cd $wslProjectRoot && DOCKER_BUILDKIT=1 docker-compose -f $wslComposeFile build --progress=plain"
        Write-Host "Build complete." -ForegroundColor Green
    }
    
    "start" {
        Write-Host "Starting container..." -ForegroundColor Yellow
        Invoke-WslCommand "cd $wslProjectRoot && docker-compose -f $wslComposeFile up -d"
        Write-Host "Container started." -ForegroundColor Green
    }
    
    "logs" {
        Write-Host "Viewing container logs..." -ForegroundColor Cyan
        $follow = $RemainingArgs -contains "-f" -or $RemainingArgs -contains "--follow"
        
        if ($follow) {
            Write-Host "Showing logs in follow mode (Ctrl+C to exit)..." -ForegroundColor Yellow
            Invoke-WslCommand "cd $wslProjectRoot && docker-compose -f $wslComposeFile logs -f"
        } else {
            Invoke-WslCommand "cd $wslProjectRoot && docker-compose -f $wslComposeFile logs"
        }
    }
    
    default {
        Write-Host "Unknown command: $Command" -ForegroundColor Red
        Write-Host "Run './scripts/run-whisper.ps1 help' for available commands." -ForegroundColor Yellow
    }
}
