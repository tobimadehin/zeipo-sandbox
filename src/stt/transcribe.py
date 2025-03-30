import argparse
import time
import whisper
import torch
import os

def format_time(seconds):
    """Format seconds into a readable time string."""
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{int(hours):02d}:{int(minutes):02d}:{seconds:05.2f}"

def main():
    parser = argparse.ArgumentParser(description="Transcribe audio with Whisper")
    parser.add_argument("audio", nargs="?", help="Audio file to transcribe")
    parser.add_argument("--model", default="tiny", help="Model to use (tiny, base, small, medium, large)")
    parser.add_argument("--language", help="Language code (if known)")
    parser.add_argument("--output", help="Output file for transcription")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed information")
    args = parser.parse_args()
    
    # Check if an audio file was provided
    if not args.audio:
        parser.print_help()
        return
    
    # Check if the audio file exists
    if not os.path.exists(args.audio):
        print(f"Error: Audio file not found: {args.audio}")
        return
    
    # Print device information
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if args.verbose:
        print(f"Using device: {device}")
        if device == "cuda":
            print(f"GPU: {torch.cuda.get_device_name(0)}")
    
    # Load model
    print(f"Loading model: {args.model}")
    start_time = time.time()
    model = whisper.load_model(args.model, device=device)
    load_time = time.time() - start_time
    print(f"Model loaded in {load_time:.2f} seconds")
    
    # Prepare transcription options
    options = {}
    if args.language:
        options["language"] = args.language
    
    # Transcribe audio
    print(f"Transcribing: {args.audio}")
    start_time = time.time()
    result = model.transcribe(args.audio, **options)
    transcribe_time = time.time() - start_time
    
    # Calculate audio duration and real-time factor
    audio = whisper.load_audio(args.audio)
    audio_duration = len(audio) / whisper.audio.SAMPLE_RATE
    rtf = transcribe_time / audio_duration
    
    # Print results
    print("\nTranscription:")
    print(result["text"])
    
    # Print statistics
    print("\nStatistics:")
    print(f"Audio duration: {format_time(audio_duration)}")
    print(f"Processing time: {format_time(transcribe_time)}")
    print(f"Real-time factor: {rtf:.2f}x")
    
    if "language" in result:
        print(f"Detected language: {result['language']}")
    
    # Save to file if requested
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(result["text"])
            
            if args.verbose:
                f.write("\n\n--- Segments ---\n\n")
                for segment in result["segments"]:
                    start = format_time(segment["start"])
                    end = format_time(segment["end"])
                    f.write(f"[{start} --> {end}] {segment['text']}\n")
        
        print(f"\nTranscription saved to: {args.output}")
    
    # Print detailed segments in verbose mode
    if args.verbose:
        print("\nSegments:")
        for segment in result["segments"]:
            start = format_time(segment["start"])
            end = format_time(segment["end"])
            print(f"[{start} --> {end}] {segment['text']}")

if __name__ == "__main__":
    main()