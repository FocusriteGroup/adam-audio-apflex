import json
import numpy as np
from scipy.optimize import linear_sum_assignment
from app.database import get_unmatched_drivers, store_pairs, get_frequency_vector


def _calculate_rmse_matrix(left_levels, right_levels):
    """Calculate RMSE matrix between all left and right driver level arrays.

    Args:
        left_levels: list of (serial, levels_array) tuples for left drivers.
        right_levels: list of (serial, levels_array) tuples for right drivers.

    Returns:
        2D numpy array where element (i,j) is the RMSE between left[i] and right[j].
    """
    n_left = len(left_levels)
    n_right = len(right_levels)
    matrix = np.zeros((n_left, n_right))

    for i, (_, l_vals) in enumerate(left_levels):
        l_arr = np.array(l_vals)
        for j, (_, r_vals) in enumerate(right_levels):
            r_arr = np.array(r_vals)
            matrix[i, j] = np.sqrt(np.mean((l_arr - r_arr) ** 2))

    return matrix


def _filter_by_freq_range(levels_list, freq_vector, freq_min, freq_max):
    """Filter levels to only include indices within [freq_min, freq_max].

    Args:
        levels_list: list of (serial, [float, ...]) tuples.
        freq_vector: list of frequency values matching the levels length.
        freq_min: lower frequency bound (Hz).
        freq_max: upper frequency bound (Hz).

    Returns:
        list of (serial, filtered_levels_list) tuples.
    """
    indices = [i for i, f in enumerate(freq_vector) if freq_min <= f <= freq_max]
    if not indices:
        return levels_list
    return [(s, [lvl[i] for i in indices]) for s, lvl in levels_list]


def compute_pairs(rmse_threshold=1.0, freq_min=None, freq_max=None):
    """Run the Hungarian algorithm on all unmatched left/right drivers.

    Drivers are grouped by their number of frequency points so that only
    drivers with the same resolution are compared.

    Args:
        rmse_threshold: Maximum allowed RMSE (in dB) for a valid pair.
        freq_min: Lower frequency bound (Hz) for RMSE calculation. None = no limit.
        freq_max: Upper frequency bound (Hz) for RMSE calculation. None = no limit.

    Returns:
        Number of new pairs found.
    """
    left_drivers, right_drivers = get_unmatched_drivers()

    if not left_drivers or not right_drivers:
        return 0

    # Build levels lists: [(serial, [float, ...]), ...]
    left_levels = [(s, json.loads(lvl)) for s, lvl in left_drivers]
    right_levels = [(s, json.loads(lvl)) for s, lvl in right_drivers]

    # Get frequency vector for range filtering
    freq_vector = None
    if freq_min is not None or freq_max is not None:
        freq_vector = get_frequency_vector()

    # Group by number of data points
    from collections import defaultdict
    left_by_len = defaultdict(list)
    right_by_len = defaultdict(list)
    for item in left_levels:
        left_by_len[len(item[1])].append(item)
    for item in right_levels:
        right_by_len[len(item[1])].append(item)

    all_pairs = []
    for n_points in left_by_len:
        left_group = left_by_len[n_points]
        right_group = right_by_len.get(n_points, [])
        if not right_group:
            continue

        # Apply frequency range filter if configured
        if freq_vector and len(freq_vector) == n_points:
            fmin = freq_min if freq_min is not None else 0
            fmax = freq_max if freq_max is not None else float('inf')
            left_filtered = _filter_by_freq_range(left_group, freq_vector, fmin, fmax)
            right_filtered = _filter_by_freq_range(right_group, freq_vector, fmin, fmax)
        else:
            left_filtered = left_group
            right_filtered = right_group

        matrix = _calculate_rmse_matrix(left_filtered, right_filtered)
        row_indices, col_indices = linear_sum_assignment(matrix)

        for row, col in zip(row_indices, col_indices):
            rmse = matrix[row, col]
            if rmse <= rmse_threshold:
                all_pairs.append((
                    left_group[row][0],
                    right_group[col][0],
                    float(rmse),
                ))

    if all_pairs:
        store_pairs(all_pairs)

    return len(all_pairs)
