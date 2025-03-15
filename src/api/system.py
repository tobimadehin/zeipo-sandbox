# app/api/system.py 
import torch
from static.constants import logger
from main import router

# Get available device - Enhanced with better diagnostic logging
def get_device():
    """Detect and configure the optimal device with detailed logging."""
    try:
        logger.info(f"CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            # Log GPU information
            device_count = torch.cuda.device_count()
            logger.info(f"Found {device_count} CUDA device(s)")
            
            for i in range(device_count):
                logger.info(f"Device {i}: {torch.cuda.get_device_name(i)}")
                
            # Test CUDA functionality
            test_tensor = torch.tensor([1.0, 2.0, 3.0]).cuda()
            logger.info(f"Test tensor created on GPU: {test_tensor.device}")
            
            return "cuda"
        else:
            logger.warning("CUDA is not available, falling back to CPU")
            return "cpu"
    except Exception as e:
        logger.error(f"Error detecting device: {str(e)}")
        logger.warning("Falling back to CPU due to error")
        return "cpu"


@router.get("/system/gpu")
async def gpu_info():
    """Detailed information about available GPU resources."""
    # Existing GPU info code from api.py
    if not torch.cuda.is_available():
        return {"status": "No GPU available", "device": "cpu"}
    
    try:
        info = {
            "cuda_available": True,
            "device_count": torch.cuda.device_count(),
            "current_device": torch.cuda.current_device(),
            "devices": []
        }
        
        for i in range(info["device_count"]):
            device_info = {
                "index": i,
                "name": torch.cuda.get_device_name(i),
                "capability": torch.cuda.get_device_capability(i),
                "total_memory": torch.cuda.get_device_properties(i).total_memory / (1024**3)
            }
            info["devices"].append(device_info)
        
        return info
    except Exception as e:
        return {"status": "Error getting GPU info", "error": str(e)}
    
DEVICE = get_device()    
