"""
ADAM Audio Helper Functions

Essential helper functions for file operations, timestamps, and path management.
Used across the ADAM Audio production system.
"""

import os
import datetime
import logging

HELPERS_LOGGER = logging.getLogger("AdamHelpers")

def generate_timestamp_extension():
    """Generate a file extension using the current time in the format 'year_month_day_hour_minute_second'."""
    now = datetime.datetime.now()
    extension = now.strftime("%Y_%m_%d_%H_%M_%S")
    HELPERS_LOGGER.info(f"Generated timestamp extension: {extension}")
    return extension

def construct_path(paths):
    """
    Construct a path by joining the list of paths.

    Args:
        paths (list): A list of strings representing path components.

    Returns:
        str: A normalized path string.

    Raises:
        ValueError: If 'paths' is not a non-empty list of strings.
    """
    if not paths or not isinstance(paths, list):
        HELPERS_LOGGER.error("construct_path: 'paths' must be a non-empty list of strings.")
        raise ValueError("'paths' must be a non-empty list of strings.")
    if not all(isinstance(p, str) for p in paths):
        HELPERS_LOGGER.error("construct_path: All elements in 'paths' must be strings.")
        raise ValueError("All elements in 'paths' must be strings.")
    result = os.path.normpath(os.path.join(*paths))
    HELPERS_LOGGER.info(f"Constructed path: {result}")
    return result

def generate_timestamp_subpath():
    """Generate a timestamp subpath formatted as 'YYYY/MM/DD/HH_MM_SS'."""
    now = datetime.datetime.now()
    subpath = now.strftime("%Y/%m_%d")
    subpath_norm = os.path.normpath(subpath)
    HELPERS_LOGGER.info(f"Generated timestamp subpath: {subpath_norm}")
    return subpath_norm

def generate_file_prefix(strings):
    """
    Generate a file prefix by concatenating a list of strings with an underscore.

    Args:
        strings (list): A list of strings to concatenate.

    Returns:
        str: A single string with the substrings joined by an underscore.

    Raises:
        ValueError: If 'strings' is not a non-empty list of strings.
    """
    if not strings or not isinstance(strings, list):
        HELPERS_LOGGER.error("generate_file_prefix: 'strings' must be a non-empty list of strings.")
        raise ValueError("'strings' must be a non-empty list of strings.")
    if not all(isinstance(s, str) for s in strings):
        HELPERS_LOGGER.error("generate_file_prefix: All elements in 'strings' must be strings.")
        raise ValueError("All elements in 'strings' must be strings.")
    result = "_".join(strings)
    HELPERS_LOGGER.info(f"Generated file prefix: {result}")
    return result