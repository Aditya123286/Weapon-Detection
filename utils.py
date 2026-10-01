import cv2
import os
import logging

logger = logging.getLogger(__name__)

def save_detection_image(image, output_path):
    """
    Save the detection image with bounding boxes
    
    Args:
        image: The image with detection bounding boxes
        output_path (str): Path where to save the result
    
    Returns:
        bool: Success status
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Save the image
        cv2.imwrite(output_path, image)
        logger.info(f"Detection image saved to {output_path}")
        return True
    except Exception as e:
        logger.error(f"Error saving detection image: {str(e)}")
        return False
