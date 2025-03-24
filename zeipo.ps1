# zeipo.ps1 - Main command interface for Zeipo project
param (
    [string]$Command = "help",
    [Parameter(ValueFromRemainingArguments=$true)]
    $RemainingArgs
)

# Extract just the main command if there are spaces or hyphens (for subcommands with args)
if ($Command -match "^(\w+)(\s|-)") {
    # Get the base command and move the rest to RemainingArgs
    $baseCommand = $matches[1]
    $extraArgs = $Command.Substring($baseCommand.Length).Trim()
    if ($extraArgs) {
        # Add the extra arguments to the beginning of RemainingArgs
        $RemainingArgs = @($extraArgs.Split(" ", [StringSplitOptions]::RemoveEmptyEntries)) + $RemainingArgs
    }
    $Command = $baseCommand
}

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
    param (
        [switch]$ForceRestart
    )
    
    try {
        # First check if WSL is working
        $wsl = wsl -- echo "WSL is working" 2>&1
        if ($wsl -ne "WSL is working") {
            Write-ZeipoMessage "WSL is not responding correctly" -Color Red
            return $false
        }
        
        # If force restart is requested, kill Docker processes first
        if ($ForceRestart) {
            Write-ZeipoMessage "Force restart requested. Stopping Docker in WSL..." -Color Yellow
            wsl -- bash -c "sudo killall -9 dockerd containerd docker-proxy 2>/dev/null || true"
            Start-Sleep -Seconds 2
        }
        
        # Check if Docker is running and responsive
        $docker = wsl -- docker ps 2>&1
        $dockerRunning = $LASTEXITCODE -eq 0
        
        # Additional deeper check in case Docker appears running but isn't working
        if ($dockerRunning) {
            $deepCheck = wsl -- bash -c "docker info >/dev/null 2>&1 || echo 'docker_not_responsive'"
            if ($deepCheck -eq "docker_not_responsive") {
                Write-ZeipoMessage "Docker appears to be running but is not responsive. Attempting restart..." -Color Yellow
                $dockerRunning = $false
            }
        }
        
        if (-not $dockerRunning) {
            Write-ZeipoMessage "Docker is not running in WSL. Attempting to start..." -Color Yellow
            
            # Kill any existing Docker processes that might be stuck
            wsl -- bash -c "sudo killall -9 dockerd containerd docker-proxy 2>/dev/null || true"
            Start-Sleep -Seconds 2
            
            # Start Docker daemon in WSL with proper detachment
            try {
                # Use nohup to ensure the process continues after the WSL session ends
                wsl -- bash -c "sudo nohup dockerd > /dev/null 2>&1 &"
                Write-ZeipoMessage "Waiting for Docker to initialize..." -Color Yellow
                Start-Sleep -Seconds 5
                
                # Verify Docker is now running
                $docker = wsl -- docker ps 2>&1
                if ($LASTEXITCODE -ne 0) {
                    # Try one more time with direct command
                    Write-ZeipoMessage "First attempt failed. Trying alternative method..." -Color Yellow
                    wsl -- sudo dockerd > /dev/null 2>&1 &
                    Start-Sleep -Seconds 5
                    $docker = wsl -- docker ps 2>&1
                    
                    if ($LASTEXITCODE -ne 0) {
                        Write-ZeipoMessage "Failed to start Docker in WSL" -Color Red
                        return $false
                    }
                }
                
                Write-ZeipoMessage "Docker started successfully" -Color Green
            }
            catch {
                Write-ZeipoMessage "Error starting Docker: $_" -Color Red
                return $false
            }
        }
        
        Write-ZeipoMessage "Docker is running properly in WSL" -Color Green
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
        Start-Sleep -Seconds 15
        
        # Get the tunnel URL from logs
        $logPath = Join-Path $projectRoot "cloudflared.log"
        $maxAttempts = 10
        $attempt = 0
        $tunnelUrl = $null
        
        while ($attempt -lt $maxAttempts) {
            if (Test-Path $logPath) {
                $logContent = Get-Content $logPath -Tail 20 | Out-String
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

# Function to clear port conflicts in both Windows and WSL
function Clear-PortConflicts {
    param (
        [int]$Port = 8000,
        [int]$WaitSeconds = 3
    )
    
    Write-ZeipoMessage "Checking for processes using port $Port in Windows..." -Color Yellow
    
    # Find and kill Windows processes using the port
    $processInfo = netstat -ano | findstr ":${Port}" | findstr "LISTENING"
    
    if ($processInfo) {
        # Extract process IDs
        $processIds = @()
        
        foreach ($line in $processInfo) {
            if ($line -match "LISTENING\s+(\d+)") {
                $_pid = $matches[1]
                if (-not ($processIds -contains $_pid)) {
                    $processIds += $_pid
                    
                    # Get process name for better logging
                    $processName = (Get-Process -Id $_pid -ErrorAction SilentlyContinue).ProcessName
                    if ($processName) {
                        Write-ZeipoMessage "Found Windows process using port ${Port}: $processName (PID: $_pid)" -Color Yellow
                    } else {
                        Write-ZeipoMessage "Found Windows process using port ${Port}: PID $_pid" -Color Yellow
                    }
                }
            }
        }
        
        # Kill Windows processes
        foreach ($_pid in $processIds) {
            Write-ZeipoMessage "Terminating Windows process with PID $_pid..." -Color Yellow
            taskkill /PID $_pid /F
        }
    } else {
        Write-ZeipoMessage "No Windows processes found using port ${Port}." -Color Green
    }
    
    # Now check and kill processes in WSL
    Write-ZeipoMessage "Checking for processes using port $Port in WSL..." -Color Yellow
    
    # Find WSL processes using the port - run the entire command in WSL
    $wslProcessInfo = wsl -- bash -c "netstat -tulpn 2>/dev/null | grep ':${Port} ' || true"
    
    if ($wslProcessInfo) {
        Write-ZeipoMessage "Found WSL processes using port ${Port}. Terminating..." -Color Yellow
        
        # Kill processes in WSL using port - run everything inside a single bash command
        wsl -- bash -c "pids=\$(ss -tulpn | grep ':$Port' | awk '{print \$7}' | cut -d'=' -f2 | cut -d',' -f1 | xargs); [ -n \"\$_pids\" ] && sudo kill -9 \$_pids || true"
        
        # Also try these common web server processes
        wsl -- bash -c "sudo pkill -f 'uvicorn' || true"
        wsl -- bash -c "sudo pkill -f 'fastapi' || true"
        wsl -- bash -c "sudo pkill -f 'python.*:${Port}' || true"
    } else {
        Write-ZeipoMessage "No WSL processes found using port ${Port}." -Color Green
    }
    
    # For Docker containers, stop any that might be using the port
    Write-ZeipoMessage "Stopping any Docker containers that might be using port ${Port}..." -Color Yellow
    wsl -- docker ps --quiet --filter "publish=${Port}" | ForEach-Object { wsl -- docker stop $_ }
    
    # Wait for ports to be fully released
    Write-ZeipoMessage "Waiting $WaitSeconds seconds for port to be fully released..." -Color Yellow
    Start-Sleep -Seconds $WaitSeconds
    
    # Verify port is clear in Windows
    $checkAgainWindows = netstat -ano | findstr ":${Port}" | findstr "LISTENING"
    if ($checkAgainWindows) {
        Write-ZeipoMessage "Warning: Port $Port is still in use in Windows after termination attempts." -Color Red
    } else {
        Write-ZeipoMessage "Port $Port is now available in Windows." -Color Green
    }
    
    # Verify port is clear in WSL
    $checkAgainWSL = wsl -- bash -c "ss -tulpn | grep ':${Port}' || true"
    if ($checkAgainWSL) {
        Write-ZeipoMessage "Warning: Port $Port is still in use in WSL after termination attempts." -Color Red
    } else {
        Write-ZeipoMessage "Port $Port is now available in WSL." -Color Green
    }

    # Final cleanup - forcefully kill anything using the port
    wsl -- bash -c "sudo fuser -k ${Port}/tcp 2>/dev/null || true"
}

# Generate a QR code for the URL
function Show-QRCode {
    param (
        [Parameter(Mandatory = $true)]
        [string]$Url
    )
    
    # Create a temporary file to store the QR code
    $tempFile = [System.IO.Path]::GetTempFileName()
    
    # Use curl (pre-installed on Windows 10+) to download QR code as text
    $curl = @"
curl -s https://qrenco.de/$Url
"@
    
    # Execute curl and display result directly
    Write-ZeipoMessage "Scan this QR code to access the Voice client:" -Color Cyan
    Invoke-Expression $curl
    Write-ZeipoMessage "URL: $Url" -Color Green
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
        Write-Host "Zeipo AI CLI tools" -ForegroundColor Magenta
        Write-Host "----------------------------------------------------------------------------------------------------------------" -ForegroundColor Magenta
        Write-Host "Commands:" -ForegroundColor Cyan
        Write-Host "  api                                           - Start the Whisper API server"
        Write-Host "  test                                          - Run Whisper tests"
        Write-Host "  stt                                           - Transcribe an audio file (zeipo stt sample.mp3 [--model small])"
        Write-Host "  tts                                           - Generate speech from text"
        Write-Host "  zeipo voice                                   - Start with Africa's Talking + Cloudflare tunnel"
        Write-Host "  zeipo voice -local                            - Start with Africa's Talking on local network"
        Write-Host "  zeipo voice -provider voip_simulator -local   - Start with VoIP simulator"
        Write-Host "  build                                         - Build or rebuild the Docker image"
        Write-Host "  clean                                         - Clean up corrupted model files"
        Write-Host "  start                                         - Start the Docker container"
        Write-Host "  stop                                          - Stop the Docker container"
        Write-Host "  bash                                          - Open a bash shell in the container"
        Write-Host "  python                                        - Run a Python command in the container"
        Write-Host "  logs                                          - View services/api logs"
        Write-Host "  calls                                         - View recent call logs"
        Write-Host "  gpu                                           - Test GPU access"
        Write-Host "  version                                       - Show version information"
        Write-Host "  setup                                         - Setup the zeipo cli for easier access"
    }
    
    "api" {
        Write-ZeipoMessage "Starting the Whisper API server..." 

        Clear-PortConflicts
        
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

    "test-stt" {
        Write-ZeipoMessage "Running Whisper tests..." -Color Yellow
        Write-ZeipoMessage "Starting container (if needed)..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' up -d"
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' exec whisper python -m tests.test_stt"
    }

    "test-tts" {
        Write-ZeipoMessage "Running Google TTS tests..." -Color Yellow
        Write-ZeipoMessage "Starting container (if needed)..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' up -d"
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' exec whisper python -m tests.test_tts"
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
        Write-Host "  zeipo test-stt       Test Whisper functionality"
        Write-Host "  zeipo test-tts       Test Google TTS functionality"
        Write-Host "  zeipo test-streaming Test streaming transcription"
        Write-Host "  zeipo test-nlp       Test NLP components" 
        Write-Host "  zeipo test-nlu       Test NLU API"
    }
    
    "stt" {
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
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' exec whisper python -m src.stt.transcribe $filePath $argsStr"
    }

    "tts" {
        Write-ZeipoMessage "Available tts commands:" -Color Cyan
        Write-Host "  zeipo tts-voices     List available TTS voices" 
        Write-Host "  zeipo tts-speak      Generate speech from text (zeipo tts-speak 'Hello world' [--voice en-US-Neural2-F])"
        Write-Host "  zeipo test-api       Test API endpoints"
    }

    "tts-voices" {
        Write-ZeipoMessage "Listing available TTS voices..." -Color Cyan
        
        # Get language filter if provided
        $language = $null
        if ($RemainingArgs.Count -gt 0) {
            $language = $RemainingArgs[0]
        }
        
        # Start container if needed
        Write-ZeipoMessage "Starting container (if needed)..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' up -d"
        
        # Make API request to list voices
        $languageParam = if ($language) { "?language_code=$language" } else { "" }
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' exec whisper curl -s 'http://localhost:8000/api/v1/tts/voices$languageParam' | python -m json.tool"
    }

    "tts-speak" {
        Write-ZeipoMessage "Generating speech from text..." -Color Cyan
        
        # Get text and optional parameters
        if ($RemainingArgs.Count -lt 1) {
            Write-ZeipoMessage "Error: Text to speak is required." -Color Red
            Write-ZeipoMessage "Usage: zeipo tts-speak 'Hello world' [--voice en-US-Neural2-F] [--language en-US]" -Color Yellow
            exit 1
        }
        
        $text = $RemainingArgs[0]
        $voice = $null
        $language = $null
        
        # Parse remaining args for voice and language
        for ($i = 1; $i -lt $RemainingArgs.Count; $i++) {
            if ($RemainingArgs[$i] -eq "--voice" -and $i+1 -lt $RemainingArgs.Count) {
                $voice = $RemainingArgs[$i+1]
                $i++
            }
            elseif ($RemainingArgs[$i] -eq "--language" -and $i+1 -lt $RemainingArgs.Count) {
                $language = $RemainingArgs[$i+1]
                $i++
            }
        }
        
        # Start container if needed
        Write-ZeipoMessage "Starting container (if needed)..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' up -d"
        
        # Build API request
        $curlCmd = "curl -s -X POST 'http://localhost:8000/api/v1/tts/synthesize"
        $curlCmd += "?text=" + [uri]::EscapeDataString($text)
        if ($voice) {
            $curlCmd += "&voice_id=" + [uri]::EscapeDataString($voice)
        }
        if ($language) {
            $curlCmd += "&language_code=" + [uri]::EscapeDataString($language)
        }
        $curlCmd += "' | python -m json.tool"
        
        # Make API request to synthesize speech
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' exec whisper bash -c '$curlCmd'"
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

        Clear-PortConflicts
        
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
        # Parse parameters from $RemainingArgs
        $provider = "at"  # Default value
        $local = $false
        
        # Loop through arguments
        $i = 0
        while ($i -lt $RemainingArgs.Count) {
            $arg = $RemainingArgs[$i]
            
            if ($arg -eq "-provider" -or $arg -eq "--provider") {
                if ($i + 1 -lt $RemainingArgs.Count) {
                    $provider = $RemainingArgs[$i + 1]
                    $i += 2  # Skip both the flag and its value
                    continue
                }
            }
            elseif ($arg -eq "-local" -or $arg -eq "--local") {
                $local = $true
            }
            
            $i++  # Move to next argument
        }
        
        Write-ZeipoMessage "Starting Zeipo with $provider telephony provider, local: $local" -Color Cyan
        
        Clear-PortConflicts

        # Start container if not running
        Write-ZeipoMessage "Starting Docker container..." -Color Yellow
        Invoke-WslCommand "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' up -d"
        
        # Set default configuration
        $webhookUrl = ""
        $wsUrl = ""
        $serverPort = 8000
        
        if ($local) {
            # For local testing, get the computer's network IP
            $localIP = (Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias Wi-*).IPAddress
            if (-not $localIP) {
                $localIP = (Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias Ethernet*).IPAddress
            }
            if (-not $localIP) {
                Write-ZeipoMessage "Could not detect local IP, using localhost as fallback." -Color Yellow
                $localIP = "localhost"
            }
            
            $webhookUrl = "http://$localIP`:$serverPort"
            $wsUrl = "ws://$localIP`:$serverPort/api/v1/ws"
            
            Write-Host "`nMobile Connection Information:" -ForegroundColor Yellow
            Write-Host "WebSocket URL: $wsUrl/audio/test_session" -ForegroundColor Cyan
            Write-Host "Web API: $webhookUrl/api/v1" -ForegroundColor Cyan
            
            Write-Host "`nImportant: Enter this URL in your Zeipo VoIP Tester app:" -ForegroundColor Yellow
            Write-Host "$wsUrl/audio/test_session" -ForegroundColor Green
        }
        else {
            # For public testing, use Cloudflare tunnel
            $cloudflareOk = Test-CloudflareCLI
            if (-not $cloudflareOk) {
                Write-ZeipoMessage "Please install Cloudflare Tunnel CLI (cloudflared) to continue." -Color Red
                exit 1
            }
            
            # Start Cloudflare tunnel
            $tunnelUrl = Start-CloudflareTunnel -Port $serverPort
            if ($null -eq $tunnelUrl) {
                Write-ZeipoMessage "Failed to start Cloudflare Tunnel. Cannot continue." -Color Red
                exit 1
            }
            
            $webhookUrl = $tunnelUrl
            $wsUrl = $tunnelUrl.Replace("https:", "wss:")
            
            # Update the .env file with the tunnel URL
            $envPath = Join-Path $projectRoot ".env"
            if (Test-Path $envPath) {
                $envContent = Get-Content $envPath
                
                if ($envContent -match "WEBHOOK_URL=") {
                    $envContent = $envContent -replace "WEBHOOK_URL=.*", "WEBHOOK_URL=$webhookUrl"
                } else {
                    $envContent += "`nWEBHOOK_URL=$webhookUrl"
                }
                
                Set-Content -Path $envPath -Value $envContent
                Write-ZeipoMessage "Updated .env file with Cloudflare Tunnel URL" -Color Green
            }
            
            # Display voice webhook URLs
            $apiV1Str = "/api/v1"
            if (Test-Path $envPath) {
                $envContent = Get-Content $envPath
                if ($envContent -match "API_V1_STR=(.*)") {
                    $apiV1Str = $matches[1]
                }
            }
            
            $voiceWebhookUrl = "$webhookUrl$apiV1Str/at/voice"
            $eventsWebhookUrl = "$webhookUrl$apiV1Str/at/events"
            $dtmfWebhookUrl = "$webhookUrl$apiV1Str/at/dtmf"
            
            Write-Host "`nVoice Webhook URLs:" -ForegroundColor Yellow
            Write-Host "Voice URL: $voiceWebhookUrl" -ForegroundColor Cyan
            Write-Host "Events URL: $eventsWebhookUrl" -ForegroundColor Cyan
            Write-Host "DTMF URL: $dtmfWebhookUrl" -ForegroundColor Cyan

            # Display VoIP client URL
            $voipClientUrl = "$webhookUrl/client"
            Write-Host "`nVoIP Client:" -ForegroundColor Yellow
            Show-QRCode -Url $voipClientUrl
        }
        
        # Start the API server with the specified telephony provider
        Write-ZeipoMessage "Starting API server with $provider provider..." -Color Green
        
        # Build the command with the appropriate environment variables
        $cmd = "cd '$wslProjectRoot' && docker-compose -f '$wslComposeFile' exec"
        $cmd += " -e PYTHONUNBUFFERED=1"
        $cmd += " -e TELEPHONY_PROVIDER=$provider"
        $cmd += " -e DEFAULT_TELEPHONY_PROVIDER=$provider"
        
        if ($webhookUrl) {
            $cmd += " -e WEBHOOK_URL=$webhookUrl"
            $cmd += " -e WS_URL=$wsUrl"
        }
        
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
