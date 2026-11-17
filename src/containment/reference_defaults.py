"""Reference values for inputs an application leaves blank, and their sources.

EASiTool asks the user for every number and falls back on fixed constants
(rock compressibility 5e-10 1/Pa, Corey exponents 3, a 2 MPa critical
pressure). Containment fills a blank with the most site-specific estimate a
reference supports instead, and says so:

* initial pressure: a hydrostatic column of the site's own brine, integrated
  with depth from its salinity and the temperature profile, not a fixed
  psi/ft. Gulf Coast normally pressured zones measure 0.45 to 0.465 psi/ft
  (AAPG; 27 Texas Class VI zones), which this reproduces;
* temperature: a regional surface temperature and gradient calibrated on the
  15 Texas Class VI applications rebuilt for validation (Gulf Coast about
  1.3 degF per 100 ft over 70 degF; Permian and Panhandle about 0.75 over
  65 degF), consistent with the SMU and BEG temperature-at-depth maps;
* rock compressibility: Hall (1953) from porosity for sands, Newman (1973)
  for carbonates, rather than one constant;
* relative permeability: the medians of the Texas applications, each inside
  the published laboratory ranges (Bennion and Bachu 2008; Krevor et al.
  2012);
* gel strength 0 psi in the mud-column threshold (EPA, 2019 letter to PEC:
  gel strength is not credited unless documented), mud weight 9.0 ppg (Texas
  Class I convention);
* the model runs to the end of the last injection plus the 50-year default
  PISC period (40 CFR 146.93).

The threshold pressure is never defaulted: it is computed for every site.
Every value filled here is listed in the project's ``defaults_used`` and in its
warnings, so a reviewer can see which numbers came from the application and
which did not.
"""

from __future__ import annotations

import numpy as np

from . import fluids
from . import units as U

# Gulf Coast east of about 99 degW; Permian Basin, Panhandle and west Texas beyond it
REGION_SPLIT_LONGITUDE = -99.0
REGIONS = {
    "gulf_coast": {"label": "Texas Gulf Coast", "surface_F": 70.0, "gradient_F_per_100ft": 1.33,
                   "basis": "median of 27 Gulf Coast zones in 12 Texas Class VI applications "
                            "(1.0 to 1.8 degF per 100 ft); SMU Geothermal Laboratory and BEG "
                            "temperature-at-depth maps"},
    "west_texas": {"label": "Permian Basin and west Texas", "surface_F": 65.0,
                   "gradient_F_per_100ft": 0.75,
                   "basis": "Permian and Panhandle Class VI applications (0.5 to 1.0 degF per "
                            "100 ft over 65 degF); lowest gradients on the Central Basin "
                            "Platform (SMU, UT Austin Pecos County study)"},
}

RELPERM = {
    "swr": (0.25, "median of 15 Texas Class VI applications; literature 0.15 to 0.40 "
                  "(Bennion and Bachu 2008; Krevor et al. 2012)"),
    "sgr": (0.25, "median of 15 Texas Class VI applications; residual trapping 0.10 to 0.35 "
                  "in sandstones (Krevor et al. 2012; Burnside and Naylor 2014)"),
    "krg0": (0.50, "median of 15 Texas Class VI applications (0.53); literature 0.2 to 0.6 "
                   "(Bennion and Bachu 2008; Benson et al. 2013)"),
    "krw0": (1.0, "drainage end point 1.0 (Krevor et al. 2012)"),
    "m": (3.5, "brine Corey exponent, median of 15 Texas Class VI applications; literature "
               "2 to 6"),
    "n": (2.5, "CO2 Corey exponent, median of 15 Texas Class VI applications (2.4); "
               "literature 2 to 5"),
}

GEL_STRENGTH_PSI = (0.0, "not credited unless documented (EPA Region 5 letter to PEC, 2019; "
                         "EPA Compendium of Technical Studies)")
MUD_WEIGHT_PPG = (9.0, "Texas Class I convention for a static mud column")
USDW_SALINITY_PPM = (10000.0, "the base of the lowermost USDW is where water reaches "
                              "10,000 mg/L TDS (40 CFR 144.3; RRC GAU letters)")
INJECTION_ZONE_SALINITY_PPM = (100000.0, "Texas Class VI applications 59,000 to 200,000 ppm "
                                         "(median 115,000); Frio brines about 93,000 "
                                         "(Kharaka et al. 2005)")
KV_KH = (0.1, "layered sands, common practice; treat as a sensitivity (0.01 to 0.5)")
PISC_YEARS = (50.0, "default post-injection site care period, 40 CFR 146.93")


def region(longitudes) -> str:
    """'gulf_coast' or 'west_texas' from the wells' longitudes (degrees)."""
    lons = [float(v) for v in longitudes if v is not None and np.isfinite(v)]
    if not lons:
        return "gulf_coast"
    return "west_texas" if np.mean(lons) < REGION_SPLIT_LONGITUDE else "gulf_coast"


def temperature(depth_m: float, reg: str) -> tuple[float, str]:
    """Formation temperature (K) at a depth (m), and its basis."""
    r = REGIONS[reg]
    t_f = r["surface_F"] + r["gradient_F_per_100ft"] * U.length_out(depth_m, "ft") / 100.0
    return (U.temperature(t_f, "F"),
            f"{r['surface_F']:g} degF + {r['gradient_F_per_100ft']:g} degF per 100 ft "
            f"({r['label']}: {r['basis']})")


def hydrostatic_pressure(depth_m: float, salinity: float, reg: str,
                         steps: int = 40) -> tuple[float, str]:
    """Pressure (Pa) at a depth from a column of the site's own brine.

    Integrates dP/dz = rho(P, T(z), S) g down from one atmosphere, with the
    temperature profile of the region. With a fresh-water salinity it gives
    the 0.433 psi/ft USDW column; with Gulf Coast brine, 0.45 to 0.47 psi/ft.
    """
    s = salinity if np.isfinite(salinity) else fluids.salinity_to_mass_fraction(
        INJECTION_ZONE_SALINITY_PPM[0], "ppm")
    p = U.ATM
    dz = depth_m / steps
    for k in range(steps):
        z = (k + 0.5) * dz
        t, _ = temperature(z, reg)
        p += fluids.brine_density(p, t, s) * U.G * dz
    grad = U.pressure_out(p - U.ATM, "psi") / max(U.length_out(depth_m, "ft"), 1e-9)
    return p, (f"hydrostatic column of the site's brine ({1e6 * s:,.0f} ppm, "
               f"{REGIONS[reg]['label']} temperature profile), {grad:.3f} psi/ft")


def rock_compressibility(porosity: float, lithology: str = "") -> tuple[float, str]:
    """Pore-volume compressibility (1/Pa) from porosity, and its basis."""
    phi = float(porosity) if np.isfinite(porosity) and porosity > 0 else 0.2
    if str(lithology).lower().startswith(("carb", "lime", "dolo")):
        c = 0.853531 / (1.0 + 2.47664e6 * phi) ** 0.9299      # 1/psi
        basis = "Newman (1973) consolidated limestone correlation"
    else:
        c = 1.782e-6 / phi ** 0.438                            # 1/psi
        basis = "Hall (1953) correlation for sandstone"
    return U.compressibility(c, "1/psi"), f"{basis} at porosity {phi:.2f}: {c:.2e} 1/psi"


__all__ = ["REGIONS", "RELPERM", "GEL_STRENGTH_PSI", "MUD_WEIGHT_PPG", "USDW_SALINITY_PPM",
           "INJECTION_ZONE_SALINITY_PPM", "KV_KH", "PISC_YEARS", "region", "temperature",
           "hydrostatic_pressure", "rock_compressibility"]
