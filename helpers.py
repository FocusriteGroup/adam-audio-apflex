"""
helpers.py

ADAM Audio Helper Functions
--------------------------

Author: Thilo Rode
Company: ADAM Audio GmbH
Version: 0.1
Date: 2025-10-20

Essential helper functions for file operations, timestamps, and path management.
Used across the ADAM Audio production system.
"""

import os
import datetime
import logging

HELPERS_LOGGER = logging.getLogger("AdamHelpers")

def generate_timestamp_extension():
    """
    Generate a file extension string using the current date and time.
    Format: 'year_month_day_hour_minute_second' (e.g., 2025_10_20_14_30_45)
    Returns:
        str: Timestamp string suitable for use as a file extension.
    """
    # Get the current local date and time
    now = datetime.datetime.now()
    # Format the timestamp as a string
    extension = now.strftime("%Y_%m_%d_%H_%M_%S")
    # Log the generated extension for traceability
    HELPERS_LOGGER.info("Generated timestamp extension: %s", extension)
    return extension

def construct_path(paths):
    """
    Construct a normalized file system path from a list of path components.

    Args:
        paths (list): A list of strings representing path components.

    Returns:
        str: A normalized path string.

    Raises:
        ValueError: If 'paths' is not a non-empty list of strings.
    """
    # Validate input: must be a non-empty list of strings
    if not paths or not isinstance(paths, list):
        HELPERS_LOGGER.error("construct_path: 'paths' must be a non-empty list of strings.")
        raise ValueError("'paths' must be a non-empty list of strings.")
    if not all(isinstance(p, str) for p in paths):
        HELPERS_LOGGER.error("construct_path: All elements in 'paths' must be strings.")
        raise ValueError("All elements in 'paths' must be strings.")
    # Join the path components and normalize the result
    result = os.path.normpath(os.path.join(*paths))
    # Log the constructed path for traceability
    HELPERS_LOGGER.info("Constructed path: %s", result)
    return result

def generate_timestamp_subpath():
    """
    Generate a timestamp-based subdirectory path for organizing files.
    Format: 'YYYY/MM_DD' (e.g., 2025/10_20)
    Returns:
        str: Normalized subpath string for use in file storage.
    """
    # Get the current local date and time
    now = datetime.datetime.now()
    # Format the subpath as year/month_day
    subpath = now.strftime("%Y/%m_%d")
    # Normalize the subpath for the current OS
    subpath_norm = os.path.normpath(subpath)
    # Log the generated subpath for traceability
    HELPERS_LOGGER.info("Generated timestamp subpath: %s", subpath_norm)
    return subpath_norm

def generate_file_prefix(strings):
    """
    Generate a file prefix by joining a list of strings with underscores.

    Args:
        strings (list): A list of strings to concatenate.

    Returns:
        str: A single string with the substrings joined by an underscore.

    Raises:
        ValueError: If 'strings' is not a non-empty list of strings.
    """
    # Validate input: must be a non-empty list of strings
    if not strings or not isinstance(strings, list):
        HELPERS_LOGGER.error("generate_file_prefix: 'strings' must be a non-empty list of strings.")
        raise ValueError("'strings' must be a non-empty list of strings.")
    if not all(isinstance(s, str) for s in strings):
        HELPERS_LOGGER.error("generate_file_prefix: All elements in 'strings' must be strings.")
        raise ValueError("All elements in 'strings' must be strings.")
    # Join the strings with underscores
    result = "_".join(strings)
    # Log the generated prefix for traceability
    HELPERS_LOGGER.info("Generated file prefix: %s", result)
    return result