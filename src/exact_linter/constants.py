"""Curated library of constants the linter can recognize by direct lookup.

Math entries are written as mpmath-evaluable expressions and computed at
60 digits, so a match can be checked at whatever precision the source
literal provides. Physical and unit-conversion entries are exact decimal
strings (SI-defined values, CODATA recommended values, or exact conversion
definitions).

Growing this table is cheap but not free: the confidence score charges
log10(table size) against every match, so each entry should plausibly
appear as a magic float in real code.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import mpmath


@dataclass(frozen=True)
class ConstantEntry:
    form: str  # human-readable exact form; mpmath-evaluable for math entries
    suggestion: str  # suggested replacement code
    note: str = ""
    decimal: str | None = None  # exact decimal string, for physical constants


MATH_ENTRIES: tuple[ConstantEntry, ...] = (
    # pi family
    ConstantEntry("pi", "math.pi"),
    ConstantEntry("2*pi", "math.tau", "one full turn"),
    ConstantEntry("3*pi", "3 * math.pi"),
    ConstantEntry("4*pi", "4 * math.pi"),
    ConstantEntry("pi/2", "math.pi / 2"),
    ConstantEntry("pi/3", "math.pi / 3"),
    ConstantEntry("pi/4", "math.pi / 4"),
    ConstantEntry("pi/5", "math.pi / 5"),
    ConstantEntry("pi/6", "math.pi / 6"),
    ConstantEntry("pi/8", "math.pi / 8"),
    ConstantEntry("pi/12", "math.pi / 12"),
    ConstantEntry("pi/16", "math.pi / 16"),
    ConstantEntry("2*pi/3", "2 * math.pi / 3"),
    ConstantEntry("3*pi/2", "3 * math.pi / 2"),
    ConstantEntry("3*pi/4", "3 * math.pi / 4"),
    ConstantEntry("5*pi/6", "5 * math.pi / 6"),
    ConstantEntry("1/pi", "1 / math.pi"),
    ConstantEntry("2/pi", "2 / math.pi"),
    ConstantEntry("4/pi", "4 / math.pi"),
    ConstantEntry("1/(2*pi)", "1 / math.tau"),
    ConstantEntry("1/(4*pi)", "1 / (4 * math.pi)", "Gauss law / solid angle normalization"),
    ConstantEntry("4*pi/3", "4 * math.pi / 3", "sphere volume coefficient"),
    ConstantEntry("3/(4*pi)", "3 / (4 * math.pi)", "inverse sphere volume coefficient"),
    ConstantEntry("pi**2", "math.pi ** 2"),
    ConstantEntry("pi**3", "math.pi ** 3"),
    ConstantEntry("1/pi**2", "1 / math.pi ** 2"),
    ConstantEntry("pi**2/6", "math.pi ** 2 / 6", "zeta(2), the Basel problem"),
    ConstantEntry("pi**2/8", "math.pi ** 2 / 8"),
    ConstantEntry("pi**2/12", "math.pi ** 2 / 12"),
    ConstantEntry("sqrt(pi)", "math.sqrt(math.pi)"),
    ConstantEntry("sqrt(pi)/2", "math.sqrt(math.pi) / 2", "gamma(3/2)"),
    ConstantEntry("1/sqrt(pi)", "1 / math.sqrt(math.pi)"),
    ConstantEntry("sqrt(2*pi)", "math.sqrt(math.tau)", "Gaussian normalization"),
    ConstantEntry("1/sqrt(2*pi)", "1 / math.sqrt(math.tau)", "Gaussian PDF normalization"),
    ConstantEntry("sqrt(pi/2)", "math.sqrt(math.pi / 2)"),
    ConstantEntry(
        "sqrt(2/pi)",
        "math.sqrt(2 / math.pi)",
        "half-normal mean factor; GELU tanh approximation coefficient",
    ),
    ConstantEntry("2/sqrt(pi)", "2 / math.sqrt(math.pi)", "erf normalization"),
    ConstantEntry("ln(pi)", "math.log(math.pi)"),
    ConstantEntry("ln(2*pi)", "math.log(math.tau)"),
    ConstantEntry(
        "ln(2*pi)/2", "math.log(math.tau) / 2", "Stirling / Gaussian log-likelihood constant"
    ),
    # angle conversions
    ConstantEntry("pi/180", "math.pi / 180", "use math.radians(x) to convert degrees to radians"),
    ConstantEntry("180/pi", "180 / math.pi", "use math.degrees(x) to convert radians to degrees"),
    ConstantEntry("pi/360", "math.pi / 360", "radians per half-degree"),
    ConstantEntry("pi/200", "math.pi / 200", "radians per gradian"),
    ConstantEntry("200/pi", "200 / math.pi", "gradians per radian"),
    ConstantEntry("pi/10800", "math.pi / 10800", "radians per arcminute"),
    ConstantEntry("pi/648000", "math.pi / 648000", "radians per arcsecond"),
    ConstantEntry("648000/pi", "648000 / math.pi", "arcseconds per radian"),
    ConstantEntry("pi*(3-sqrt(5))", "math.pi * (3 - math.sqrt(5))", "golden angle, radians"),
    ConstantEntry("180*(3-sqrt(5))", "180 * (3 - math.sqrt(5))", "golden angle, degrees"),
    # e and logarithms
    ConstantEntry("e", "math.e"),
    ConstantEntry("1/e", "1 / math.e"),
    ConstantEntry("e**2", "math.e ** 2"),
    ConstantEntry("sqrt(e)", "math.sqrt(math.e)"),
    ConstantEntry("ln(2)", "math.log(2)"),
    ConstantEntry("1/ln(2)", "1 / math.log(2)", "log base-2 conversion: prefer math.log2(x)"),
    ConstantEntry("ln(3)", "math.log(3)"),
    ConstantEntry("ln(5)", "math.log(5)"),
    ConstantEntry("ln(10)", "math.log(10)"),
    ConstantEntry("1/ln(10)", "1 / math.log(10)", "log base-10 conversion: prefer math.log10(x)"),
    ConstantEntry("ln(2)/ln(10)", "math.log10(2)"),
    ConstantEntry("ln(10)/ln(2)", "math.log2(10)"),
    # decibels and music
    ConstantEntry("ln(10)/20", "math.log(10) / 20", "nepers per dB (amplitude)"),
    ConstantEntry("20/ln(10)", "20 / math.log(10)", "dB per neper (amplitude)"),
    ConstantEntry("ln(10)/10", "math.log(10) / 10", "dB power to natural log"),
    ConstantEntry("10/ln(10)", "10 / math.log(10)", "natural log to dB power"),
    ConstantEntry("10**(mpf(1)/20)", "10 ** (1 / 20)", "amplitude ratio for 1 dB"),
    ConstantEntry("10**(mpf(1)/10)", "10 ** (1 / 10)", "power ratio for 1 dB"),
    ConstantEntry("2**(mpf(1)/12)", "2 ** (1 / 12)", "equal-temperament semitone ratio"),
    ConstantEntry("ln(2)/1200", "math.log(2) / 1200", "natural log per music cent"),
    ConstantEntry("1200/ln(2)", "1200 / math.log(2)", "music cents per natural log"),
    # roots
    ConstantEntry("sqrt(2)", "math.sqrt(2)"),
    ConstantEntry("sqrt(2)/2", "math.sqrt(2) / 2", "equals 1/sqrt(2)"),
    ConstantEntry("sqrt(3)", "math.sqrt(3)"),
    ConstantEntry("sqrt(3)/2", "math.sqrt(3) / 2"),
    ConstantEntry("1/sqrt(3)", "1 / math.sqrt(3)"),
    ConstantEntry("sqrt(5)", "math.sqrt(5)"),
    ConstantEntry("sqrt(6)", "math.sqrt(6)"),
    ConstantEntry("sqrt(7)", "math.sqrt(7)"),
    ConstantEntry("sqrt(10)", "math.sqrt(10)"),
    ConstantEntry("cbrt(2)", "2 ** (1 / 3)"),
    ConstantEntry("cbrt(3)", "3 ** (1 / 3)"),
    ConstantEntry("sqrt(2)+1", "math.sqrt(2) + 1", "silver ratio"),
    ConstantEntry("sqrt(2)-1", "math.sqrt(2) - 1", "silver ratio conjugate; tan(pi/8)"),
    # statistics
    ConstantEntry(
        "sqrt(2)*erfinv(mpf('0.5'))",
        "scipy.stats.norm.ppf(0.75)",
        "standard normal upper quartile",
    ),
    ConstantEntry(
        "1/(sqrt(2)*erfinv(mpf('0.5')))",
        "scipy.stats.norm.ppf(0.75) ** -1",
        "MAD-to-sigma consistency factor (1.4826...)",
    ),
    ConstantEntry(
        "sqrt(2)*erfinv(mpf('0.8'))",
        "scipy.stats.norm.ppf(0.90)",
        "z-score, 90th percentile",
    ),
    ConstantEntry(
        "sqrt(2)*erfinv(mpf('0.9'))",
        "scipy.stats.norm.ppf(0.95)",
        "z-score, 95th percentile (one-sided 5%)",
    ),
    ConstantEntry(
        "sqrt(2)*erfinv(mpf('0.95'))",
        "scipy.stats.norm.ppf(0.975)",
        "z-score, 97.5th percentile (two-sided 5%, the 1.96 rule)",
    ),
    ConstantEntry(
        "sqrt(2)*erfinv(mpf('0.99'))",
        "scipy.stats.norm.ppf(0.995)",
        "z-score, 99.5th percentile (two-sided 1%)",
    ),
    # named constants
    ConstantEntry("phi", "(1 + math.sqrt(5)) / 2", "golden ratio"),
    ConstantEntry("1/phi", "2 / (1 + math.sqrt(5))", "golden ratio conjugate, phi - 1"),
    ConstantEntry("euler", "numpy.euler_gamma", "Euler-Mascheroni constant (no stdlib name)"),
    ConstantEntry("catalan", "define a named constant CATALAN", "Catalan's constant"),
    ConstantEntry("zeta(3)", "define a named constant APERY", "Apery's constant, zeta(3)"),
    ConstantEntry("khinchin", "define a named constant KHINCHIN", "Khinchin's constant"),
    ConstantEntry("glaisher", "define a named constant GLAISHER", "Glaisher-Kinkelin constant"),
    ConstantEntry("gamma(mpf(1)/3)", "math.gamma(1 / 3)"),
    ConstantEntry("gamma(mpf(1)/4)", "math.gamma(1 / 4)"),
)

# Values that are exact by definition or CODATA-recommended; matched digit
# strings rather than computed. The suggestion points at scipy.constants.
PHYSICAL_ENTRIES: tuple[ConstantEntry, ...] = (
    ConstantEntry("speed of light c", "scipy.constants.c", "m/s, SI-defined", "299792458"),
    ConstantEntry("standard gravity g", "scipy.constants.g", "m/s^2, SI-defined", "9.80665"),
    ConstantEntry("Avogadro N_A", "scipy.constants.N_A", "1/mol, SI-defined", "6.02214076e23"),
    ConstantEntry("Boltzmann k", "scipy.constants.k", "J/K, SI-defined", "1.380649e-23"),
    ConstantEntry(
        "Boltzmann k in eV/K",
        'scipy.constants.physical_constants["Boltzmann constant in eV/K"][0]',
        "eV/K",
        "8.617333262e-5",
    ),
    ConstantEntry("Planck h", "scipy.constants.h", "J s, SI-defined", "6.62607015e-34"),
    ConstantEntry("reduced Planck hbar", "scipy.constants.hbar", "J s", "1.054571817e-34"),
    ConstantEntry(
        "elementary charge e",
        "scipy.constants.e",
        "C, SI-defined; also the eV in joules",
        "1.602176634e-19",
    ),
    ConstantEntry("vacuum permittivity", "scipy.constants.epsilon_0", "F/m", "8.8541878128e-12"),
    ConstantEntry("vacuum permeability", "scipy.constants.mu_0", "H/m", "1.25663706212e-6"),
    ConstantEntry(
        "Coulomb constant",
        "1 / (4 * math.pi * scipy.constants.epsilon_0)",
        "N m^2/C^2",
        "8.9875517923e9",
    ),
    ConstantEntry("gas constant R", "scipy.constants.R", "J/(mol K)", "8.31446261815324"),
    ConstantEntry(
        "Stefan-Boltzmann sigma", "scipy.constants.sigma", "W/(m^2 K^4)", "5.670374419e-8"
    ),
    ConstantEntry("gravitational constant G", "scipy.constants.G", "m^3/(kg s^2)", "6.6743e-11"),
    ConstantEntry(
        "fine-structure constant", "scipy.constants.fine_structure", "", "0.0072973525693"
    ),
    ConstantEntry(
        "inverse fine-structure constant",
        "1 / scipy.constants.fine_structure",
        "the famous 137",
        "137.035999084",
    ),
    ConstantEntry("Rydberg constant", "scipy.constants.Rydberg", "1/m", "10973731.568160"),
    ConstantEntry(
        "Bohr radius",
        'scipy.constants.physical_constants["Bohr radius"][0]',
        "m",
        "5.29177210903e-11",
    ),
    ConstantEntry(
        "Wien displacement constant", "scipy.constants.Wien", "m K", "2.897771955e-3"
    ),
    ConstantEntry(
        "Faraday constant",
        'scipy.constants.physical_constants["Faraday constant"][0]',
        "C/mol",
        "96485.33212",
    ),
    ConstantEntry("electron mass", "scipy.constants.m_e", "kg", "9.1093837015e-31"),
    ConstantEntry("proton mass", "scipy.constants.m_p", "kg", "1.67262192369e-27"),
    ConstantEntry("atomic mass constant", "scipy.constants.m_u", "kg", "1.66053906660e-27"),
    # astronomy
    ConstantEntry("astronomical unit", "scipy.constants.au", "m, exact", "1.495978707e11"),
    ConstantEntry(
        "parsec", "scipy.constants.parsec", "m, exact (au * 648000 / pi)", "3.0856775814913673e16"
    ),
    ConstantEntry("light year", "scipy.constants.light_year", "m, exact", "9460730472580800"),
    # exactly-defined unit conversions
    ConstantEntry("pound to kg", "scipy.constants.pound", "exact", "0.45359237"),
    ConstantEntry("mile to m", "scipy.constants.mile", "exact", "1609.344"),
    ConstantEntry(
        "US gallon to liters", "1000 * scipy.constants.gallon", "exact", "3.785411784"
    ),
    ConstantEntry("psi to Pa", "scipy.constants.psi", "exact", "6894.757293168361"),
    ConstantEntry("mmHg/torr to Pa", "scipy.constants.mmHg", "101325/760", "133.32236842105263"),
    ConstantEntry("horsepower to W", "scipy.constants.hp", "exact", "745.6998715822702"),
    ConstantEntry("BTU to J", "scipy.constants.Btu", "exact (IT)", "1055.05585262"),
    # dynamical systems (not exactly known; matched to their known digits)
    ConstantEntry(
        "Feigenbaum delta",
        "define a named constant FEIGENBAUM_DELTA",
        "period-doubling bifurcation ratio",
        "4.669201609102990",
    ),
    ConstantEntry(
        "Feigenbaum alpha",
        "define a named constant FEIGENBAUM_ALPHA",
        "period-doubling width ratio",
        "2.502907875095892",
    ),
)

_NAMESPACE_NAMES = (
    "pi",
    "e",
    "sqrt",
    "cbrt",
    "ln",
    "exp",
    "euler",
    "catalan",
    "phi",
    "zeta",
    "gamma",
    "erfinv",
    "khinchin",
    "glaisher",
    "mpf",
)


@lru_cache(maxsize=1)
def table(
    extra: tuple[ConstantEntry, ...] = (),
) -> tuple[tuple[mpmath.mpf, ConstantEntry], ...]:
    """The full lookup table as (high-precision value, entry) rows.

    `extra` adds project-specific entries (from [tool.exact.constants]);
    they must carry a decimal value string. Results are cached per extra
    tuple, so pass the same tuple object between calls where possible.
    """
    rows: list[tuple[mpmath.mpf, ConstantEntry]] = []
    with mpmath.workdps(60):
        namespace = {name: getattr(mpmath, name) for name in _NAMESPACE_NAMES}
        for entry in MATH_ENTRIES:
            value = mpmath.mpf(eval(entry.form, {"__builtins__": {}}, namespace))
            rows.append((value, entry))
        for entry in PHYSICAL_ENTRIES + extra:
            if entry.decimal is not None:
                rows.append((mpmath.mpf(entry.decimal), entry))
    return tuple(rows)
