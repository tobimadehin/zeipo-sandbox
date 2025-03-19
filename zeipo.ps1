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

# Add this after other function definitions
function Convert-ToContainerPath {
    param (
        [string]$Path
    )
    
    # Normalize path separators
    $Path = $Path.Replace('\', '/')
    
    # Remove ./ prefix if present
    if ($Path.StartsWith('./')) {
        $Path = $Path.Substring(2)
    } elseif ($Path.StartsWith('.')) {
        $Path = $Path.Substring(1)
    }
    
    # Check if it's already an absolute path in container format
    if ($Path.StartsWith('/app/') -or $Path.StartsWith('/')) {
        return $Path
    }
    
    # For relative paths, just prepend /app/
    return "/app/$Path"
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

# Function to check if Cloudflare CLI is installed
function Test-CloudflareCLI {
    try {
        $cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
        if ($null -eq $cloudflared) {
            Write-ZeipoMessage "Cloudflare Tunnel CLI (cloudflared) is not installed." -Color Red
            Write-ZeipoMessage "Please download it from: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/" -Color Yellow
            return $false
        }
        return $true
    }
    catch {
        Write-ZeipoMessage "Error checking Cloudflare CLI: $_" -Color Red
        return $false
    }
}

# Function to start a Cloudflare tunnel
function Start-CloudflareTunnel {
    param (
        [int]$Port = 8000
    )
    
    try {
        # Check if cloudflared is already running
        $process = Get-Process cloudflared -ErrorAction SilentlyContinue
        if ($process) {
            Write-ZeipoMessage "Cloudflare Tunnel is already running. Stopping it..." -Color Yellow
            Stop-Process -Name cloudflared -Force
            Start-Sleep -Seconds 2
        }
        
        # Start Cloudflare tunnel in a new PowerShell window
        Write-ZeipoMessage "Starting Cloudflare Tunnel..." -Color Cyan
        Start-Process powershell -ArgumentList "-Command", "cloudflared tunnel --url http://localhost:$Port --logfile cloudflared.log" -WindowStyle Minimized
        
        # Wait for tunnel to initialize
        Write-ZeipoMessage "Waiting for Cloudflare Tunnel to initialize..." -Color Yellow
        Start-Sleep -Seconds 5
        
        # Get the tunnel URL from logs
        $logPath = Join-Path $projectRoot "cloudflared.log"
        $maxAttempts = 10
        $attempt = 0
        $tunnelUrl = $null
        
        while ($attempt -lt $maxAttempts) {
            if (Test-Path $logPath) {
                $logContent = Get-Content $logPath -Raw
                if ($logContent -match "https://.*\.trycloudflare\.com") {
                    $tunnelUrl = $Matches[0]
                    break
                }
            }
            
            $attempt++
            Start-Sleep -Seconds 1
        }
        
        if ($null -eq $tunnelUrl) {
            Write-ZeipoMessage "Failed to get Cloudflare Tunnel URL from logs." -Color Red
            return $null
        }
        
        Write-ZeipoMessage "Cloudflare Tunnel URL: $tunnelUrl" -Color Green
        return $tunnelUrl
    }
    catch {
        Write-ZeipoMessage "Error starting Cloudflare Tunnel: $_" -Color Red
        return $null
    }
}

# Get project root in WSL format
$wslProjectRoot = $projectRoot.ToString().Replace("\", "/").Replace("C:", "/mnt/c").Replace("D:", "/mnt/d")
Write-Host "Using WSL path: $wslProjectRoot"

# Get Docker Compose file path
$composeFile = Join-Path $projectRoot "docker\docker-compose.yml"
$wslComposeFile = $composeFile.ToString().Replace("\", "/").Replace("C:", "/mnt/c").Replace("D:", "/mnt/d")
Write-Host "Using WSL compose path: $wslComposeFile"

# Check Docker and WSL before executing commands
if ($Command -ne "help" -and $Command -ne "version" -and $Command -ne "voice") {
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
        Write-Host "  voice       - Start voice channel"
        Write-Host "  build       - Build or rebuild the Docker image"
        Write-Host "  clean       - Clean up corrupted model files"
        Write-Host "  start       - Start the Docker container"
        Write-Host "  stop        - Stop the Docker container"
        Write-Host "  bash        - Open a bash shell in the container"
        Write-Host "  python      - Run a Python command in the container"
        Write-Host "  logs        - View services/api logs"
        Write-Host "  calls       - View recent call logs"
        Write-Host "  gpu         - Test GPU access"
        Write-Host "  version     - Show version information"
        Write-Host "  setup       - Setup the zeipo cli for easier access"
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
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' exec -e PYTHONUNBUFFERED=1 whisper fastapi dev main.py --host 0.0.0.0"
    }
    
    "test-all" {
        Write-ZeipoMessage "Running all tests..." -Color Yellow
        Write-ZeipoMessage "Starting container (if needed)..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' up -d"
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' exec whisper python -m unittest discover tests"
    }

    "test-at" {
        Write-ZeipoMessage "Running Africa's Talking tests..." -Color Yellow
        Write-ZeipoMessage "Starting container (if needed)..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' up -d"
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' exec whisper python -m tests.test_at"
    }

    "test-api" {
        Write-ZeipoMessage "Running API tests..." -Color Yellow
        Write-ZeipoMessage "Starting container (if needed)..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' up -d"
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' exec whisper python -m tests.test_api"
    }

    "test-whisper" {
        Write-ZeipoMessage "Running Whisper tests..." -Color Yellow
        Write-ZeipoMessage "Starting container (if needed)..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' up -d"
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' exec whisper python -m tests.test_whisper"
    }

    "test-streaming" {
        Write-ZeipoMessage "Running streaming tests..." -Color Yellow
        Write-ZeipoMessage "Starting container (if needed)..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' up -d"
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' exec whisper python -m tests.test_steaming"
    }

    "test-nlp" {
        Write-ZeipoMessage "Running NLP tests..." -Color Yellow
        Write-ZeipoMessage "Starting container (if needed)..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' up -d"
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' exec whisper python -m tests.test_nlp"
    }

    "test-nlu" {
        Write-ZeipoMessage "Running NLU tests..." -Color Yellow
        Write-ZeipoMessage "Starting container (if needed)..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' up -d"
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' exec whisper python -m tests.test_nlu"
    }

    "test" {
        Write-ZeipoMessage "Available test commands:" -Color Cyan
        Write-Host "  zeipo test-all       Run all tests" 
        Write-Host "  zeipo test-at        Test Africa's Talking integration"
        Write-Host "  zeipo test-api       Test API endpoints"
        Write-Host "  zeipo test-whisper   Test Whisper functionality"
        Write-Host "  zeipo test-streaming Test streaming transcription"
        Write-Host "  zeipo test-nlp       Test NLP components" 
        Write-Host "  zeipo test-nlu       Test NLU API"
    }
    
    "transcribe" {
        Write-ZeipoMessage "Transcribing audio..."
        
        # Process the first argument (file path) separately
        $filePath = $null
        $otherArgs = @()
        
        if ($RemainingArgs.Count -gt 0) {
            $filePath = Convert-ToContainerPath -Path $RemainingArgs[0]
            $otherArgs = $RemainingArgs[1..($RemainingArgs.Count-1)]
        }
        
        $argsStr = ($otherArgs -join " ")
        
        Write-ZeipoMessage "Starting container (if needed)..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' up -d"
        
        Write-ZeipoMessage "Executing transcription..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' exec whisper python -m src.transcribe $filePath $argsStr"
    }

    "clean" {
        Write-ZeipoMessage "Cleaning up cached Whisper models..." -Color Yellow
        
        # Start container if not running
        Write-ZeipoMessage "Starting container (if needed)..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' up -d"
        
        # Clean Whisper cache directory
        Write-ZeipoMessage "Removing cached Whisper models..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' exec whisper rm -rf ~/.cache/whisper/*"
        
        # Verify cleanup
        Write-ZeipoMessage "Verifying cleanup..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' exec whisper ls -la ~/.cache/whisper/ || mkdir -p ~/.cache/whisper/"
        
        Write-ZeipoMessage "Cleanup completed successfully." -Color Green
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
        
        # Also stop any running Cloudflare tunnels
        $process = Get-Process cloudflared -ErrorAction SilentlyContinue
        if ($process) {
            Write-ZeipoMessage "Stopping Cloudflare Tunnel..." -Color Yellow
            Stop-Process -Name cloudflared -Force
            Write-ZeipoMessage "Cloudflare Tunnel stopped." -Color Green
        }
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

    # Add this as a new case in the switch statement in zeipo.ps1
    "calls" {
        Write-ZeipoMessage "Viewing call logs..." -Color Cyan
        
        # Get arguments to pass to the call logs script
        $args = $RemainingArgs -join " "
        
        # Start container if not running
        Write-ZeipoMessage "Starting container (if needed)..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' up -d"
        
        # Run the call logs viewer script
        Write-ZeipoMessage "Fetching call logs..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' exec whisper python -m tools.call_logs $args"
    }
    
    "gpu" {
        Write-Host "Testing GPU access directly in WSL..." -ForegroundColor Cyan
        Invoke-WslCommand "nvidia-smi"
        
        Write-Host "`nTesting GPU in Docker container..." -ForegroundColor Cyan
        Invoke-WslCommand "cd '$wslProjectRoot' && docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi"
    }
    
    "version" {
        $version = "0.0.2" 
        Write-ZeipoMessage "Zeipo Tools version $version" -Color Green
        Write-ZeipoMessage "Whisper Sandbox Integration with Africa's Talking Support" -Color Green
    }
    
    "voice" {
        Write-ZeipoMessage "Starting Zeipo with Africa's Talking integration..." -Color Cyan
        
        # Check if Cloudflare CLI is installed
        $cloudflareOk = Test-CloudflareCLI
        if (-not $cloudflareOk) {
            Write-ZeipoMessage "Please install Cloudflare Tunnel CLI (cloudflared) to continue." -Color Red
            exit 1
        }
        
        # Start container first
        Write-ZeipoMessage "Starting Docker container..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' up -d"
        
        # Start Cloudflare tunnel
        $tunnelUrl = Start-CloudflareTunnel -Port 8000
        if ($null -eq $tunnelUrl) {
            Write-ZeipoMessage "Failed to start Cloudflare Tunnel. Cannot continue." -Color Red
            exit 1
        }
        
        # Update the .env file with the tunnel URL
        $envPath = Join-Path $projectRoot ".env"
        if (Test-Path $envPath) {
            $envContent = Get-Content $envPath
            
            if ($envContent -match "WEBHOOK_URL=") {
                $envContent = $envContent -replace "WEBHOOK_URL=.*", "WEBHOOK_URL=$tunnelUrl"
            } else {
                $envContent += "`nWEBHOOK_URL=$tunnelUrl"
            }
            
            Set-Content -Path $envPath -Value $envContent
            Write-ZeipoMessage "Updated .env file with Cloudflare Tunnel URL" -Color Green
        } else {
            Write-ZeipoMessage "Error: .env file not found in $envPath" -Color Red
            Write-ZeipoMessage "Please create an .env file with your configuration before running this command." -Color Yellow
        }
        
        # Get API prefix from env file
        $apiV1Str = "/api/v1"
        if (Test-Path $envPath) {
            $envContent = Get-Content $envPath
            if ($envContent -match "API_V1_STR=(.*)") {
                $apiV1Str = $matches[1]
            }
        }
        
        # Calculate Africa's Talking webhook URLs
        $voiceWebhookUrl = "$tunnelUrl$apiV1Str/at/voice"
        $eventsWebhookUrl = "$tunnelUrl$apiV1Str/at/events"
        $dtmfWebhookUrl = "$tunnelUrl$apiV1Str/at/dtmf"
        
        Write-Host "`nAfrica's Talking Webhook URLs:" -ForegroundColor Yellow
        Write-Host "Voice URL: $voiceWebhookUrl" -ForegroundColor Cyan
        Write-Host "Events URL: $eventsWebhookUrl" -ForegroundColor Cyan
        Write-Host "DTMF URL: $dtmfWebhookUrl" -ForegroundColor Cyan
        
        Write-Host "`nImportant: Update your Africa's Talking voice service with these webhook URLs" -ForegroundColor Yellow
        Write-Host "1. Log in to your Africa's Talking Console" -ForegroundColor White
        Write-Host "2. Go to Voice > Settings" -ForegroundColor White
        Write-Host "3. Configure the following URLs:" -ForegroundColor White
        Write-Host "   - Incoming Call URL: $voiceWebhookUrl" -ForegroundColor White
        Write-Host "   - Events Callback URL: $eventsWebhookUrl" -ForegroundColor White
        Write-Host "   - DTMF Callback URL: $dtmfWebhookUrl" -ForegroundColor White
        Write-Host "4. Save your changes" -ForegroundColor White
        
        # Start the API server with Africa's Talking integration
        Write-ZeipoMessage "Starting API server..." -Color Green
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' exec -e PYTHONUNBUFFERED=1 whisper fastapi dev main.py --host 0.0.0.0"
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
