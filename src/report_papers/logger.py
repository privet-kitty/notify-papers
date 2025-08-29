"""Centralized logging configuration for AWS Lambda environment."""

import logging
import sys
from typing import Optional


def setup_root_logger() -> None:
    """Setup root logger for Lambda environment."""
    root_logger = logging.getLogger()
    
    # Clear any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Setup basic configuration for Lambda
    logging.basicConfig(
        level=logging.INFO,
        format='[%(levelname)s] %(asctime)s %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        stream=sys.stdout
    )
    
    root_logger.setLevel(logging.INFO)


# Setup root logger when module is imported
setup_root_logger()


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a properly configured logger for AWS Lambda environment.
    
    Args:
        name: Logger name. If None, returns root logger.
        
    Returns:
        Configured logger instance
    """
    # Get logger
    if name:
        logger = logging.getLogger(name)
    else:
        logger = logging.getLogger()
    
    # Only configure if handlers haven't been set up yet
    if not logger.handlers:
        # Remove any existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # Create handler that writes to stdout (Lambda captures this)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        
        # Create formatter optimized for CloudWatch
        formatter = logging.Formatter(
            fmt='[%(levelname)s] %(asctime)s %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        
        # Add handler to logger
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        # Prevent propagation to avoid duplicate logs
        logger.propagate = False
    
    return logger