import os
import pytest

from DisplayCAL.setup import get_data


@pytest.mark.parametrize(
    "tgt_dir, key, pkgname, subkey, excludes",
    [["DisplayCAL", "doc", None, None, ["LICENSE.txt"]]],
)
def test_get_data_returns_relative_paths(tgt_dir, key, pkgname, subkey, excludes):
    """DisplayCAL.setup.get_data() returns relative paths."""
    result = get_data(tgt_dir, key, pkgname, subkey, excludes)
    all_paths = []
    for r in result:
        all_paths += r[1]
    assert all([not os.path.isabs(path) for path in all_paths])
