import copy
import sys
from pathlib import Path

import pytest

from main import (  # type: ignore  # noqa: E402
    _clear_pentomino_cluster,
    _is_selection_valid,
    _transformations,
)


def _make_board(rows: int = 6, cols: int = 6, fill: str = "-") -> list[list[str]]:
    return [[fill for _ in range(cols)] for _ in range(rows)]


def test_is_selection_valid_true():
    board = _make_board()
    coords = [(1, 1), (1, 2), (2, 1), (2, 2), (2, 3)]
    for r, c in coords:
        board[r][c] = "*"

    assert _is_selection_valid(board, coords) is True


def test_is_selection_valid_false_when_not_connected():
    board = _make_board()
    coords = [(0, 0), (0, 1), (0, 2), (0, 3), (2, 2)]
    for r, c in coords:
        board[r][c] = "*"

    assert _is_selection_valid(board, coords) is False


def test_is_selection_valid_false_when_not_all_marked():
    board = _make_board()
    coords = [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4)]
    for r, c in coords[:-1]:
        board[r][c] = "*"
    board[0][4] = "-"

    assert _is_selection_valid(board, coords) is False


def test_is_selection_valid_false_when_duplicate_coords():
    board = _make_board()
    coords = [(1, 1), (1, 2), (1, 3), (1, 3), (1, 4)]
    for r, c in set(coords):
        board[r][c] = "*"

    assert _is_selection_valid(board, coords) is False


def test_transformations_contains_rotations_and_reflections():
    coords = [(0, 0), (1, 0), (2, 0), (2, 1), (2, 2)]  # an L shape
    forms = _transformations(coords)

    # Rotated to lie flat horizontally after normalization
    expected_variant = tuple(sorted([(0, 0), (0, 1), (0, 2), (1, 0), (2, 0)]))
    assert expected_variant in forms
    assert len(forms) <= 8


def test_transformations_includes_reflection_variant():
    coords = [(0, 0), (0, 1), (1, 1), (2, 1), (2, 2)]  # asymmetrical shape
    forms = _transformations(coords)

    reflected = tuple(sorted([(0, 0), (0, 1), (1, 0), (2, 0), (2, -1)]))
    min_r = min(r for r, _ in reflected)
    min_c = min(c for _, c in reflected)
    normalized_reflection = tuple(sorted((r - min_r, c - min_c) for r, c in reflected))

    assert normalized_reflection in forms


def test_clear_pentomino_cluster_success():
    board = _make_board()
    letter = "L"
    coords = [(2, 2), (3, 2), (4, 2), (4, 1), (4, 0)]
    for r, c in coords:
        board[r][c] = letter

    cleared = _clear_pentomino_cluster(board, 2, 2)

    assert cleared is True
    assert all(board[r][c] == "-" for r, c in coords)


def test_clear_pentomino_cluster_fails_if_not_exactly_five():
    board = _make_board()
    letter = "T"
    coords = [(1, 1), (1, 2), (1, 3), (2, 2)]  # only four tiles
    for r, c in coords:
        board[r][c] = letter

    snapshot = copy.deepcopy(board)

    cleared = _clear_pentomino_cluster(board, 1, 1)

    assert cleared is False
    assert board == snapshot


def test_clear_pentomino_cluster_fails_if_start_not_letter():
    board = _make_board()
    board[0][0] = "-"

    snapshot = copy.deepcopy(board)

    cleared = _clear_pentomino_cluster(board, 0, 0)

    assert cleared is False
    assert board == snapshot


def test_clear_pentomino_cluster_fails_if_cluster_too_large():
    board = _make_board()
    letter = "P"
    coords = [(1, 1), (1, 2), (2, 1), (2, 2), (3, 1), (3, 2)]  # six tiles
    for r, c in coords:
        board[r][c] = letter

    snapshot = copy.deepcopy(board)

    cleared = _clear_pentomino_cluster(board, 1, 1)

    assert cleared is False
    assert board == snapshot

