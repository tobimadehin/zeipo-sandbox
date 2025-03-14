# zeipo.ps1 - Main command interface for Zeipo project
param (
    [string]$Command = "help",
    [Parameter(ValueFromRemainingArguments=$true)]
    $RemainingArgs
)

# Project root is the directory where this script is located
$projectRoot = $PSScriptRoot

# Function to format output
function Write-ZeipoMessage {
    param (
        [string]$Message,
        [string]$Color = "Cyan"
    )
    
    Write-Host "Zeipo: " -NoNewline -ForegroundColor Magenta
    Write-Host $Message -ForegroundColor $Color
}

# Verify Docker and WSL are running
function Test-DockerWsl {
    try {
        $wsl = wsl -- echo "WSL is working"
        if ($wsl -ne "WSL is working") {
            Write-ZeipoMessage "WSL is not responding correctly" -Color Red
            return $false
        }
        
        $docker = wsl -- docker ps 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-ZeipoMessage "Docker is not running in WSL. Attempting to start..." -Color Yellow
            try {
                wsl -- sudo dockerd > /dev/null 2>&1 &
                Start-Sleep -Seconds 3
                $docker = wsl -- docker ps 2>&1
                if ($LASTEXITCODE -ne 0) {
                    Write-ZeipoMessage "Failed to start Docker in WSL" -Color Red
                    return $false
                }
            }
            catch {
                Write-ZeipoMessage "Error starting Docker: $_" -Color Red
                return $false
            }
        }
        return $true
    }
    catch {
        Write-ZeipoMessage "Error checking Docker/WSL: $_" -Color Red
        return $false
    }
}

# Execute WSL command
function Invoke-WslCommand {
    param (
        [string]$Command
    )
    
    # Run with direct output streaming to console
    wsl -- bash -c "$Command"
    return $LASTEXITCODE
}

# Get project root in WSL format
$wslProjectRoot = $projectRoot.ToString().Replace("\", "/").Replace("C:", "/mnt/c").Replace("D:", "/mnt/d")
Write-Host "Using WSL path: $wslProjectRoot"

# Get Docker Compose file path
$composeFile = Join-Path $projectRoot "docker\docker-compose.yml"
$wslComposeFile = $composeFile.ToString().Replace("\", "/").Replace("C:", "/mnt/c").Replace("D:", "/mnt/d")
Write-Host "Using WSL compose path: $wslComposeFile"

# Check Docker and WSL before executing commands
if ($Command -ne "help" -and $Command -ne "version") {
    $dockerWslOk = Test-DockerWsl
    if (-not $dockerWslOk) {
        Write-ZeipoMessage "Cannot continue without Docker and WSL working properly." -Color Red
        exit 1
    }
}

# Main command processing
switch ($Command) {
    "help" {
        Write-Host "Zeipo - AI-driven Telephony Solution Tools" -ForegroundColor Magenta
        Write-Host "----------------------------------------" -ForegroundColor Magenta
        Write-Host "Commands:" -ForegroundColor Cyan
        Write-Host "  api         - Start the Whisper API server"
        Write-Host "  test        - Run Whisper tests"
        Write-Host "  transcribe  - Transcribe an audio file (zeipo transcribe sample.mp3 [--model small])"
        Write-Host "  build       - Build or rebuild the Docker image"
        Write-Host "  start       - Start the Docker container"
        Write-Host "  stop        - Stop the Docker container"
        Write-Host "  bash        - Open a bash shell in the container"
        Write-Host "  python      - Run a Python command in the container"
        Write-Host "  logs        - View Docker container logs"
        Write-Host "  gpu         - Test GPU access"
        Write-Host "  version     - Show version information"
        Write-Host "  setup       - Setup the zeipo command for easier access"
    }
    
    "api" {
        Write-ZeipoMessage "Starting the Whisper API server..." 
        
        # First, stop any existing container that might be using the port
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' down"
        
        # Start container
        Write-ZeipoMessage "Starting container..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' up -d"
        
        # Get the container IP address
        $containerIP = wsl -- docker inspect -f "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}" docker-whisper-1
        Write-ZeipoMessage "Container IP address: $containerIP" -Color Green
        
        Write-ZeipoMessage "Starting API server..." -Color Yellow
        Write-ZeipoMessage "API will be available at: http://localhost:8000" -Color Green
        
        # Start the API with explicit 0.0.0.0 binding to allow external connections
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' exec -e PYTHONUNBUFFERED=1 whisper fastapi dev src/api.py"
    }
    
    "test" {
        Write-ZeipoMessage "Running Whisper tests..."
        $args = $RemainingArgs -join " "
        
        Write-ZeipoMessage "Starting container (if needed)..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' up -d"
        
        Write-ZeipoMessage "Executing tests..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' exec whisper python -m tests.test_whisper $args"
    }
    
    "transcribe" {
        Write-ZeipoMessage "Transcribing audio..."
        $args = $RemainingArgs -join " "
        
        Write-ZeipoMessage "Starting container (if needed)..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' up -d"
        
        Write-ZeipoMessage "Executing transcription..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' exec whisper python -m src.transcribe $args"
    }
    
    "build" {
        Write-ZeipoMessage "Building Docker image..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && DOCKER_BUILDKIT=1 docker-compose -f '$wslComposeFile' build --progress=plain"
        Write-ZeipoMessage "Build complete." -Color Green
    }
    
    "start" {
        Write-ZeipoMessage "Starting container..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' up -d"
        Write-ZeipoMessage "Container started." -Color Green
    }
    
    "stop" {
        Write-ZeipoMessage "Stopping container..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' down"
        Write-ZeipoMessage "Container stopped." -Color Green
    }
    
    "bash" {
        Write-ZeipoMessage "Opening bash shell in container..." -Color Cyan
        
        Write-ZeipoMessage "Starting container (if needed)..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' up -d"
        
        wsl -e bash -c "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' exec whisper bash"
    }
    
    "python" {
        Write-ZeipoMessage "Running Python command in container..." -Color Cyan
        $args = $RemainingArgs -join " "
        
        Write-ZeipoMessage "Starting container (if needed)..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' up -d"
        
        Write-ZeipoMessage "Executing Python command..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' exec whisper python $args"
    }
    
    "logs" {
        Write-ZeipoMessage "Viewing container logs..." -Color Cyan
        $follow = $RemainingArgs -contains "-f" -or $RemainingArgs -contains "--follow"
        
        if ($follow) {
            Write-ZeipoMessage "Showing logs in follow mode (Ctrl+C to exit)..." -Color Yellow
            Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' logs -f"
        } else {
            Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' logs"
        }
    }
    
    "gpu" {
        Write-Host "Testing GPU access directly in WSL..." -ForegroundColor Cyan
        Invoke-WslCommand "nvidia-smi"
        
        Write-Host "`nTesting GPU in Docker container..." -ForegroundColor Cyan
        Invoke-WslCommand "cd '$wslProjectRoot' && docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi"
    }
    
    "version" {
        $version = "0.0.1" # You can read this from a version file if available
        Write-ZeipoMessage "Zeipo Tools version $version" -Color Green
        Write-ZeipoMessage "Whisper Sandbox Integration" -Color Green
    }
    
    "setup" {
        Write-ZeipoMessage "Setting up zeipo command for easier access..." -Color Yellow
        
        # Create the command alias
        $setupScript = @"
# Check if PowerShell profile exists
if (!(Test-Path -Path `$PROFILE)) {
    New-Item -ItemType File -Path `$PROFILE -Force
}

# Create zeipo function in profile
`$zeipoFunction = @'
function zeipo {
    param(
        [Parameter(Position=0, ValueFromRemainingArguments=`$true)]
        `$Arguments
    )
    
    # Call the zeipo.ps1 script with all arguments
    & "$projectRoot\zeipo.ps1" `$Arguments
}
'@

# Add function to profile if it doesn't exist
if (!(Select-String -Path `$PROFILE -Pattern "function zeipo" -Quiet)) {
    Add-Content -Path `$PROFILE -Value `$zeipoFunction
    Write-Host "Zeipo command has been added to your PowerShell profile." -ForegroundColor Green
    Write-Host "Reload your profile with: . `$PROFILE" -ForegroundColor Cyan
} else {
    Write-Host "Zeipo command already exists in your PowerShell profile." -ForegroundColor Yellow
}
"@
        
        # Create and run the setup script
        $setupScriptPath = Join-Path $env:TEMP "zeipo-setup.ps1"
        $setupScript | Out-File -FilePath $setupScriptPath -Encoding utf8
        
        # Run the setup script
        & $setupScriptPath
        
        # Clean up
        Remove-Item -Path $setupScriptPath -Force
    }
    
    default {
        Write-ZeipoMessage "Unknown command: $Command" -Color Red
        Write-ZeipoMessage "Run 'zeipo help' for available commands." -Color Yellow
        exit 1
    }
}
