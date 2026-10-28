# coding=utf-8
"""Test del calcolo del lago di sbarramento su un DEM sintetico a V (solo numpy)."""

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lake_utils  # noqa: E402

PIXEL = 2.0
HALF_SIZE = 1000.0
VALLEY_SIDE_SLOPE = 0.3      # pendenza dei versanti (trasversale)
THALWEG_SLOPE = 0.05         # pendenza dell'alveo: a 1 km il talweg supera la sella
DAM_HEIGHT = 30.0
CREST_SLOPE_DEG = 5.0
SIDE_DIP_DEG = 25.0
MAX_RADIUS = 400.0


def build_case(direction_deg, upstream_sign, thalweg_slope=THALWEG_SLOPE, river_along_direction=False):
    """
    Valle a V con l'alveo lungo d_perpendicular (o lungo d_parallel se river_along_direction):
    il monte è dal lato upstream_sign.
    Il cuneo è costruito come in calculate_landslide_dam_wedge con altezza fissa.
    """
    coords = np.arange(-HALF_SIZE + PIXEL / 2.0, HALF_SIZE, PIXEL)
    X, Y = np.meshgrid(coords, coords[::-1])
    azimuth = np.radians(direction_deg)
    d_par = X * np.sin(azimuth) + Y * np.cos(azimuth)
    d_perp = X * np.cos(azimuth) - Y * np.sin(azimuth)

    z0 = 100.0
    across, along = (d_perp, d_par) if river_along_direction else (d_par, d_perp)
    dem = (z0 + VALLEY_SIDE_SLOPE * np.abs(across) + upstream_sign * thalweg_slope * along).astype(np.float32)

    dam_surface = (z0 + DAM_HEIGHT - np.abs(d_par) * np.tan(np.radians(CREST_SLOPE_DEG))
                   - np.abs(d_perp) * np.tan(np.radians(SIDE_DIP_DEG)))
    wedge = (np.sqrt(X ** 2 + Y ** 2) <= MAX_RADIUS) & (dam_surface > dem)
    thickness = np.where(wedge, dam_surface - dem, 0.0)
    final_dem = np.where(thickness > 0, dam_surface, dem).astype(np.float32)
    return dem, final_dem, thickness, d_par, d_perp


def expected_spill_level():
    """Intersezione tra la cresta (d_perp = 0) e il versante: z0 + H - x*tan(crest), con x*(0.3 + tan) = H."""
    tan_crest = np.tan(np.radians(CREST_SLOPE_DEG))
    x = DAM_HEIGHT / (VALLEY_SIDE_SLOPE + tan_crest)
    return 100.0 + DAM_HEIGHT - x * tan_crest


class LakeUtilsTest(unittest.TestCase):

    def run_case(self, direction_deg, upstream_sign):
        dem, final_dem, thickness, d_par, d_perp = build_case(direction_deg, upstream_sign)
        seed, outlet, _ = lake_utils.find_seed_and_outlet(dem, thickness)
        self.assertGreater(upstream_sign * d_perp[seed], 0)
        self.assertLess(upstream_sign * d_perp[outlet], 0)
        self.assertEqual(thickness[seed], 0)

        max_level = float(np.nanmax(final_dem[thickness > 0]))
        spill = lake_utils.compute_spill_level(final_dem, seed, outlet, max_level)
        self.assertEqual(spill['status'], 'ok')
        # La sella reale è poco sotto l'intersezione sulla cresta (il versante scende verso valle)
        self.assertAlmostEqual(spill['level'], expected_spill_level(), delta=1.5)
        self.assertLess(final_dem[seed], spill['level'])

        _, volume, area, max_depth = lake_utils.lake_statistics(
            final_dem, spill['lake_mask'], spill['level'], PIXEL * PIXEL)
        self.assertGreater(volume, 0)
        self.assertGreater(area, 0)
        # Il lago resta tutto a monte della cresta
        self.assertTrue(np.all(upstream_sign * d_perp[spill['lake_mask']] > -PIXEL * 2))
        return spill['level'], volume

    def test_directions_and_flow_sense(self):
        for direction in (0.0, 45.0, 90.0, 180.0, 300.0):
            for upstream_sign in (1, -1):
                with self.subTest(direction=direction, upstream_sign=upstream_sign):
                    self.run_case(direction, upstream_sign)

    def test_fallback_without_scipy(self):
        saved = lake_utils.ndimage
        lake_utils.ndimage = None
        try:
            level_fallback, volume_fallback = self.run_case(90.0, 1)
        finally:
            lake_utils.ndimage = saved
        level, volume = self.run_case(90.0, 1)
        self.assertAlmostEqual(level_fallback, level, places=6)
        self.assertAlmostEqual(volume_fallback, volume, delta=volume * 1e-9)

    def test_lake_truncated_by_dem_border(self):
        # Alveo poco pendente: a monte il DEM finisce sotto la quota di sella
        dem, final_dem, thickness, d_par, d_perp = build_case(90.0, 1, thalweg_slope=0.02)
        seed, outlet, _ = lake_utils.find_seed_and_outlet(dem, thickness)
        max_level = float(np.nanmax(final_dem[thickness > 0]))
        spill = lake_utils.compute_spill_level(final_dem, seed, outlet, max_level)
        self.assertEqual(spill['status'], 'border')
        self.assertLess(spill['level'], expected_spill_level())

    def test_river_along_dam_direction(self):
        # Convenzione opposta: il fiume scorre lungo 'Direction' (cresta parallela all'alveo)
        for upstream_sign in (1, -1):
            with self.subTest(upstream_sign=upstream_sign):
                dem, final_dem, thickness, d_par, _ = build_case(30.0, upstream_sign, river_along_direction=True)
                seed, outlet, _ = lake_utils.find_seed_and_outlet(dem, thickness)
                self.assertGreater(upstream_sign * d_par[seed], 0)
                self.assertLess(upstream_sign * d_par[outlet], 0)
                max_level = float(np.nanmax(final_dem[thickness > 0]))
                spill = lake_utils.compute_spill_level(final_dem, seed, outlet, max_level)
                self.assertEqual(spill['status'], 'ok')
                self.assertGreater(spill['level'], final_dem[seed])
                self.assertTrue(np.all(upstream_sign * d_par[spill['lake_mask']] > -PIXEL * 2))

    def test_internal_nodata_in_channel(self):
        # Alveo a monte mascherato come NoData (tipico dei DTM LiDAR): non deve causare tracimazione
        dem, final_dem, thickness, d_par, d_perp = build_case(90.0, 1)
        hole = (d_perp > 200) & (d_perp < 260) & (np.abs(d_par) < 8)
        dem[hole] = np.nan
        final_dem[hole] = np.nan
        seed, outlet, _ = lake_utils.find_seed_and_outlet(dem, thickness)
        max_level = float(np.nanmax(final_dem[thickness > 0]))
        spill = lake_utils.compute_spill_level(final_dem, seed, outlet, max_level)
        self.assertEqual(spill['status'], 'ok')
        self.assertGreater(spill['internal_nodata_cells'], 0)
        self.assertAlmostEqual(spill['level'], expected_spill_level(), delta=1.5)

    def test_dam_not_closing_valley(self):
        dem, _, thickness, d_par, d_perp = build_case(90.0, 1)
        seed, outlet, _ = lake_utils.find_seed_and_outlet(dem, thickness)
        # Senza cuneo il DEM non trattiene acqua: lo sbarramento non è efficace
        spill = lake_utils.compute_spill_level(dem, seed, outlet, float(dem[seed]) + 30.0)
        self.assertEqual(spill['status'], 'not_effective')
        self.assertEqual(spill['exit_rc'], tuple(outlet))


if __name__ == '__main__':
    unittest.main()
