from __future__ import annotations

import unittest

from keiba_next.course_key import course_key_from_race
from keiba_next.win_match import build_profiles, match_win_fit


def _run(finish: int) -> dict:
    return {
        "JyoCD": "09",
        "TrackCD": "1",
        "Kyori": 2400,
        "SibaBabaCD": "1",
        "KakuteiJyuni": str(finish),
        "Umaban": 1,
    }


class WinMatchTests(unittest.TestCase):
    def test_rentai_outranks_third_only(self) -> None:
        profiles = build_profiles(
            {
                "W": [_run(1) for _ in range(4)],
                "R": [_run(2) for _ in range(4)],
                "P": [_run(3) for _ in range(4)],
            }
        )
        course = course_key_from_race(_run(1))
        winner = match_win_fit(profiles["W"], course, 1)
        rentai = match_win_fit(profiles["R"], course, 1)
        third = match_win_fit(profiles["P"], course, 1)
        self.assertGreater(winner, rentai)
        self.assertGreater(rentai, third)
        self.assertAlmostEqual(profiles["R"].rentai_rate, 1.0)
        self.assertAlmostEqual(profiles["P"].rentai_rate, 0.0)
        self.assertAlmostEqual(profiles["P"].place_rate, 1.0)


if __name__ == "__main__":
    unittest.main()
