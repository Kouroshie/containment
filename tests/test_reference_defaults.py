"""Blank inputs are filled with site-specific reference values, and say so."""

import pytest

from containment import reference_defaults as REF
from containment import units as U
from containment.config import Project


def _sparse(lon=-94.3, **zone):
    z = {"top_depth": 6000, "thickness": 200, "porosity": 0.25, "permeability": 300, **zone}
    return Project.from_dict({
        "formation": {"injection_zone": z, "usdw": {"base_depth": 1500}},
        "wells": [{"name": "I", "latitude": 29.9, "longitude": lon, "rate": 1.0,
                   "start_year": 0, "stop_year": 20}],
        "model": {"engine": "analytical"}})


def test_gulf_coast_pressure_is_a_brine_column_not_a_constant():
    p = _sparse(salinity_ppm=115000)
    grad = U.pressure_out(p.injection_zone.initial_pressure, "psi") / 6000
    assert 0.45 < grad < 0.47                       # AAPG 0.465; Texas applications
    usdw = (U.pressure_out(p.usdw.initial_pressure, "psi") - 14.7) / 1500
    assert 0.43 < usdw < 0.44                       # a near-fresh column


def test_region_follows_the_wells():
    gulf = _sparse()
    west = _sparse(lon=-102.4)
    tg = U.temperature_out(gulf.injection_zone.temperature, "F")
    tw = U.temperature_out(west.injection_zone.temperature, "F")
    assert tg == pytest.approx(70 + 1.33 * 61, abs=0.5)     # mid-zone 6,100 ft
    assert tw == pytest.approx(65 + 0.75 * 61, abs=0.5)
    assert any("depleted" in u["basis"] for u in west.defaults_used)


def test_every_default_is_recorded_and_given_values_are_kept():
    p = _sparse(temperature=160)
    names = {u["input"] for u in p.defaults_used}
    assert "injection zone temperature" not in names
    assert U.temperature_out(p.injection_zone.temperature, "F") == pytest.approx(160)
    for item in ("injection zone initial pressure", "rock compressibility",
                 "relative permeability sgr", "mud gel strength", "simulation end"):
        assert item in names
    assert all(u["basis"] for u in p.defaults_used)
    assert any("filled with reference values" in w for w in p.warnings)


def test_gel_strength_is_not_credited_and_the_run_ends_50_years_after_injection():
    p = _sparse()
    assert p.gel_strength == 0.0
    assert U.time_out(p.end_time, "yr") == pytest.approx(70.0)


def test_rock_compressibility_follows_porosity_and_lithology():
    sand, _ = REF.rock_compressibility(0.25)
    tight, _ = REF.rock_compressibility(0.10)
    carb, basis = REF.rock_compressibility(0.10, "carbonate")
    assert U.compressibility_out(sand, "1/psi") == pytest.approx(3.27e-6, rel=0.01)
    assert tight > sand                        # Hall: tighter rock, more compressible
    assert "Newman" in basis and carb != tight
