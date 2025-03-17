# app/tools/call_logs.py
import os
import json
from datetime import datetime
import argparse

def get_log_files(log_dir="logs/calls", count=10):
    """Get the most recent log files."""
    if not os.path.exists(log_dir):
        print(f"Log directory {log_dir} does not exist.")
        return []
    
    # Get all log files
    log_files = []
    for filename in os.listdir(log_dir):
        if filename.endswith(".json"):
            file_path = os.path.join(log_dir, filename)
            modified_time = os.path.getmtime(file_path)
            log_files.append((file_path, modified_time))
    
    # Sort by modification time (newest first)
    log_files.sort(key=lambda x: x[1], reverse=True)
    
    # Return the requested number of files
    return [f[0] for f in log_files[:count]]

def display_call_log(log_file):
    """Display the contents of a call log file."""
    print("\n" + "=" * 50)
    print(f"Log File: {os.path.basename(log_file)}")
    print("-" * 50)
    
    try:
        with open(log_file, 'r') as f:
            log_data = json.load(f)
        
        if isinstance(log_data, list):
            # Multiple entries in the log
            for i, entry in enumerate(log_data):
                display_log_entry(entry, i+1)
        else:
            # Single entry
            display_log_entry(log_data)
            
    except Exception as e:
        print(f"Error reading log file: {str(e)}")

def display_log_entry(entry, index=None):
    """Display a single log entry."""
    if index is not None:
        print(f"\nEntry {index}:")
    
    print(f"Call SID: {entry.get('call_sid', 'N/A')}")
    print(f"Phone: {entry.get('phone_number', 'N/A')}")
    print(f"Direction: {entry.get('direction', 'N/A')}")
    print(f"Status: {entry.get('status', 'N/A')}")
    
    # Format timestamp if present
    timestamp = entry.get('timestamp')
    if timestamp:
        try:
            dt = datetime.fromisoformat(timestamp)
            formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
            print(f"Time: {formatted_time}")
        except:
            print(f"Time: {timestamp}")
    
    # Display duration if present
    duration = entry.get('duration')
    if duration:
        print(f"Duration: {duration} seconds")
    elif entry.get('durationInSeconds'):
        print(f"Duration: {entry.get('durationInSeconds')} seconds")
    
    # Display DTMF digits if present
    dtmf_digits = entry.get('dtmf_digits')
    if dtmf_digits:
        print(f"DTMF Input: {dtmf_digits}")
    
    # Display additional data if present, excluding headers which are too verbose
    additional_data = {}
    for key, value in entry.items():
        if key not in ['call_sid', 'phone_number', 'direction', 'status', 'timestamp', 
                       'duration', 'durationInSeconds', 'dtmf_digits', 'headers']:
            additional_data[key] = value
    
    if additional_data:
        print("Additional Data:")
        for key, value in additional_data.items():
            print(f"  {key}: {value}")

def main():
    parser = argparse.ArgumentParser(description="View recent call logs")
    parser.add_argument("--count", "-n", type=int, default=5, help="Number of recent logs to show")
    parser.add_argument("--all", "-a", action="store_true", help="Show all logs")
    parser.add_argument("--call-sid", "-c", help="Show logs for a specific Call SID/Session ID")
    args = parser.parse_args()
    
    # Directory for call logs
    log_dir = "logs/calls"
    
    if args.call_sid:
        # Show logs for a specific Call SID
        log_file = os.path.join(log_dir, f"{args.call_sid}.json")
        if os.path.exists(log_file):
            display_call_log(log_file)
        else:
            print(f"No log file found for Call SID/Session ID: {args.call_sid}")
    else:
        # Show the most recent logs
        count = 999999 if args.all else args.count
        log_files = get_log_files(log_dir, count)
        
        if not log_files:
            print("No call logs found.")
            return
        
        print(f"Displaying {len(log_files)} recent call logs:")
        for log_file in log_files:
            display_call_log(log_file)

if __name__ == "__main__":
    main()
    