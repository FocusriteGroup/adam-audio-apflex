import os
import datetime


class Utilities:
    """Utility class for various helper functions."""

    @staticmethod
    def generate_timestamp_extension():
        """Generate a file extension using the current time in the format 'year_month_day_hour_minute_second'."""
        now = datetime.datetime.now()
        extension = now.strftime("%Y_%m_%d_%H_%M_%S")
        return extension

    @staticmethod
    def construct_path(paths):
        """
        Construct a path by joining the list of paths.

        Args:
            paths (list): A list of strings representing path components.

        Returns:
            str: A normalized path string.
        """
        if not paths or not isinstance(paths, list):
            raise ValueError("'paths' must be a non-empty list of strings.")
        if not all(isinstance(p, str) for p in paths):
            raise ValueError("All elements in 'paths' must be strings.")
        return os.path.normpath(os.path.join(*paths))

    @staticmethod
    def generate_timestamp_subpath():
        """Generate a timestamp subpath formatted as 'YYYY/MM/DD/HH_MM_SS'."""
        now = datetime.datetime.now()
        subpath = now.strftime("%Y/%m_%d")
        return os.path.normpath(subpath)

    @staticmethod
    def generate_file_prefix(strings):
        """
        Generate a file prefix by concatenating a list of strings with an underscore.

        Args:
            strings (list): A list of strings to concatenate.

        Returns:
            str: A single string with the substrings joined by an underscore.
        """
        if not strings or not isinstance(strings, list):
            raise ValueError("'strings' must be a non-empty list of strings.")
        if not all(isinstance(s, str) for s in strings):
            raise ValueError("All elements in 'strings' must be strings.")
        return "_".join(strings)
    
