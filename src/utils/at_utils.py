# app/src/utils/at_utils.py
import json
import os
from datetime import datetime
from static.constants import logger, LOG_DIR

def ensure_log_directory():
    """Ensure that the log directory exists."""
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR, exist_ok=True)

def log_call_to_file(call_sid, phone_number, direction, status, additional_data=None) -> None:
    """
    Log call information to a JSON file.
    
    Args:
        call_sid: Africa's Talking Session ID
        phone_number: Caller's phone number
        direction: 'inbound' or 'outbound'
        status: Call status
        additional_data: Any additional data to log
    """
    ensure_log_directory()
    
    # Create log entry
    log_entry = {
        "call_sid": call_sid,
        "phone_number": phone_number,
        "direction": direction,
        "status": status,
        "timestamp": datetime.now().isoformat(),
    }
    
    # Add additional data if provided
    if additional_data:
        log_entry.update(additional_data)
    
    # Create filename based on call SID
    filename = f"{LOG_DIR}/{call_sid}.json"
    
    try:
        # If file exists, read existing data
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                existing_data = json.load(f)
                
            # If existing data is a dict, convert to list
            if isinstance(existing_data, dict):
                existing_data = [existing_data]
                
            existing_data.append(log_entry)
            log_data = existing_data
        else:
            log_data = log_entry
        
        # Write log data to file
        with open(filename, 'w') as f:
            json.dump(log_data, f, indent=2)
            
        logger.info(f"Call logged to file: {filename}")
        
    except Exception as e:
        logger.error(f"Error logging call to file: {str(e)}")

def parse_at_error(error_obj) -> str:
    """
    Parse an Africa's Talking API error object.
    
    Args:
        error_obj: Error object from Africa's Talking API
        
    Returns:
        Formatted error message
    """
    try:
        # If it's not a response-type error, just return the string representation
        if not hasattr(error_obj, 'response'):
            return str(error_obj)
            
        response = error_obj.response
        
        # If there's no text attribute, return just the status code
        if not hasattr(response, 'text'):
            return f"Africa's Talking API Error - Status Code: {response.status_code}"
            
        # Try to parse as JSON
        try:
            error_data = json.loads(response.text)
            status = error_data.get('status', 'error')
            message = error_data.get('message', 'Unknown error')
            code = error_data.get('code', 'unknown')
            return f"Africa's Talking API Error - Status: {status}, Code: {code}, Message: {message}"
        except json.JSONDecodeError:
            # Not valid JSON, return raw response
            return f"Africa's Talking API Error - Status Code: {response.status_code}, Response: {response.text}"
            
    except Exception as e:
        return f"Error parsing Africa's Talking error: {str(e)} - Original error: {str(error_obj)}"

def format_phone_number(phone_number: str) -> str:
    """
    Format a phone number for Africa's Talking API.
    
    Args:
        phone_number: Phone number to format
        
    Returns:
        Formatted phone number
    """
    # Remove any non-digit characters
    digits_only = ''.join(filter(str.isdigit, phone_number))
    
    # Add + prefix if not present
    if not phone_number.startswith('+'):
        # For Nigerian numbers, add country code if not present
        if len(digits_only) == 10 and digits_only.startswith('0'):
            # Convert 0XXXXXXXXX to +234XXXXXXXXX
            return f"+234{digits_only[1:]}"
        elif len(digits_only) > 10:
            # If already has country code without +, add +
            return f"+{digits_only}"
        else:
            # Default to Nigerian country code if unsure
            return f"+234{digits_only}"
    else:
        return phone_number
    