# Script to download sample audio files for testing
$sampleDir = Join-Path (Split-Path -Parent $PSScriptRoot) "data\samples"

# Create directory if it doesn't exist
if (-not (Test-Path $sampleDir)) {
    New-Item -ItemType Directory -Path $sampleDir -Force | Out-Null
}

# Sample audio files to download
$samples = @(
    @{
        name = "english_sample.mp3"
        url = "https://github.com/openai/whisper/raw/main/tests/jfk.flac"
        description = "JFK speech sample (English)"
    },
    @{
        name = "multilingual_sample.mp3"
        url = "https://github.com/ggerganov/whisper.cpp/raw/master/samples/jfk.wav"
        description = "Another JFK speech sample (English)"
    }
)

# Download each sample
foreach ($sample in $samples) {
    $outputPath = Join-Path $sampleDir $sample.name
    
    if (Test-Path $outputPath) {
        Write-Host "Sample already exists: $($sample.name)" -ForegroundColor Yellow
    } else {
        Write-Host "Downloading $($sample.description) to $($sample.name)..." -ForegroundColor Cyan
        
        try {
            Invoke-WebRequest -Uri $sample.url -OutFile $outputPath
            Write-Host "Downloaded successfully." -ForegroundColor Green
        } catch {
            Write-Host "Failed to download $($sample.name): $_" -ForegroundColor Red
        }
    }
}

Write-Host "Sample downloads complete. Files saved to $sampleDir" -ForegroundColor Cyan