# Zeipo.ai Sandbox Whisper Integration

This repository contains the Whisper speech recognition integration for Zeipo.ai, an AI-driven telephony solution designed for businesses in Africa. The solution uses OpenAI's Whisper model to transcribe and understand multiple African languages.

## Getting Started

### Prerequisites

- Windows, macOS, or Linux
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Git](https://git-scm.com/downloads)
- PowerShell (for Windows) or Bash (for macOS/Linux)

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/zeipo-sandbox.git
   cd zeipo-sandbox
   ```

2. Download sample audio files:
   ```
   ./scripts/download-samples.ps1
   ```

3. Build the Docker image:
   ```
   ./scripts/run-whisper.ps1 build
   ```

### Basic Usage

Run a basic test to verify everything is working:
```
./scripts/run-whisper.ps1 test
```

Transcribe an audio file:
```
./scripts/run-whisper.ps1 transcribe data/samples/english_sample.mp3 --model small
```

Start the API server:
```
./scripts/run-whisper.ps1 api
```

Run benchmarks:
```
./scripts/run-whisper.ps1 benchmark
```

## Project Structure

- `src/`: Source code for the application
  - `api.py`: FastAPI server for speech recognition
  - `transcribe.py`: Command-line tool for transcription
  - `streaming.py`: Real-time streaming transcription
  - `languages.py`: Language information and utilities
  - `utils.py`: Shared utility functions
- `tests/`: Unit and integration tests
- `scripts/`: Utility scripts for development
- `docker/`: Docker configuration files
- `data/samples/`: Sample audio files for testing

## Development

### Running Tests

```
./scripts/run-whisper.ps1 python -m unittest discover tests
```

### API Documentation

When the API server is running, you can access the interactive documentation at:
```
http://localhost:8000/docs
```

### Google Cloud Deployment

The project includes GitHub Actions workflow for deploying to Google Cloud. To use it:

1. Create a Google Cloud service account with appropriate permissions
2. Add the service account key as a GitHub secret named `GCP_SA_KEY`
3. Add your Google Cloud project ID as a GitHub secret named `GCP_PROJECT_ID`
4. Push to the main branch or manually trigger the workflow

## Models

The project supports the following Whisper models:

| Model | Parameters | VRAM Required | Use Case |
|-------|------------|--------------|----------|
| tiny  | 39M        | ~1 GB        | Fast, lower accuracy, development |
| base  | 74M        | ~1 GB        | Better accuracy, still fast       |
| small | 244M       | ~2 GB        | Good balance for production       |
| medium| 769M       | ~5 GB        | High accuracy, slower             |
| large | 1550M      | ~10 GB       | Highest accuracy, slowest         |

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Setting Up Your Environment

Now that you have created all the necessary files, follow these steps to get your environment up and running:

1. Create all the directories and files as shown above. You can use PowerShell to create directories and files, or use your favorite code editor.

2. Open PowerShell in your project root directory and run:

   ```powershell
   # Allow execution of our scripts
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

   # Download sample audio files
   ./scripts/download-samples.ps1

   # Build the Docker environment
   ./scripts/run-whisper.ps1 build
   ```

3. Test your environment:

   ```powershell
   # Run basic tests
   ./scripts/run-whisper.ps1 test

   # Try transcribing a file
   ./scripts/run-whisper.ps1 transcribe data/samples/english_sample.mp3 --model tiny
   ```

4. Start the API server and explore the interactive documentation:

   ```powershell
   ./scripts/run-whisper.ps1 api
   ```

   Then open your browser to `http://localhost:8000/docs`

Here's a more generic version of your text:

---

### What Makes This Project Unique   

- **Multilingual support**: Addressing gaps in speech recognition for underrepresented languages.  
- **Low-latency processing**: Optimizing for real-time applications where quick response times are essential.  
- **Streaming audio handling**: Enabling continuous audio stream processing instead of working with pre-recorded files.  
- **Seamless integration**: Connecting transcription with business logic, intent recognition, and automated or human-assisted workflows.  

The Docker-based development environment ensures a consistent and reproducible setup, making it easier to refine and scale each component. By prioritizing these areas, this project is designed to meet the unique challenges of real-time voice processing and automation.