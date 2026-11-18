# SPDX-License-Identifier: MIT
import release_pipeline_dummy


def test_version() -> None:
    assert release_pipeline_dummy.__version__
