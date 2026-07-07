"""Curated library of constants the linter can recognize by direct lookup.

Math entries are written as mpmath-evaluable expressions and computed at
60 digits, so a match can be checked at whatever precision the source
literal provides. Physical constants are exact decimal strings (all are
either SI-defined values or CODATA recommended values).
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
    ConstantEntry("pi/2", "math.pi / 2"),
    ConstantEntry("pi/3", "math.pi / 3"),
    ConstantEntry("pi/4", "math.pi / 4"),
    ConstantEntry("pi/6", "math.pi / 6"),
    ConstantEntry("3*pi/2", "3 * math.pi / 2"),
    ConstantEntry("3*pi/4", "3 * math.pi / 4"),
    ConstantEntry("pi/180", "math.pi / 180", "use math.radians(x) to convert degrees to radians"),
    ConstantEntry("180/pi", "180 / math.pi", "use math.degrees(x) to convert radians to degrees"),
    ConstantEntry("1/pi", "1 / math.pi"),
    ConstantEntry("2/pi", "2 / math.pi"),
    ConstantEntry("4/pi", "4 / math.pi"),
    ConstantEntry("1/(2*pi)", "1 / math.tau"),
    ConstantEntry("4*pi", "4 * math.pi"),
    ConstantEntry("pi**2", "math.pi ** 2"),
    ConstantEntry("pi**2/6", "math.pi ** 2 / 6", "zeta(2), the Basel problem"),
    ConstantEntry("sqrt(pi)", "math.sqrt(math.pi)"),
    ConstantEntry("sqrt(2*pi)", "math.sqrt(math.tau)", "Gaussian normalization"),
    ConstantEntry("1/sqrt(2*pi)", "1 / math.sqrt(math.tau)", "Gaussian PDF normalization"),
    ConstantEntry("2/sqrt(pi)", "2 / math.sqrt(math.pi)", "erf normalization"),
    ConstantEntry("ln(pi)", "math.log(math.pi)"),
    # e and logarithms
    ConstantEntry("e", "math.e"),
    ConstantEntry("1/e", "1 / math.e"),
    ConstantEntry("e**2", "math.e ** 2"),
    ConstantEntry("ln(2)", "math.log(2)"),
    ConstantEntry("1/ln(2)", "1 / math.log(2)", "log base-2 conversion: prefer math.log2(x)"),
    ConstantEntry("ln(3)", "math.log(3)"),
    ConstantEntry("ln(10)", "math.log(10)"),
    ConstantEntry("1/ln(10)", "1 / math.log(10)", "log base-10 conversion: prefer math.log10(x)"),
    ConstantEntry("ln(2)/ln(10)", "math.log10(2)"),
    ConstantEntry("ln(10)/ln(2)", "math.log2(10)"),
    # roots
    ConstantEntry("sqrt(2)", "math.sqrt(2)"),
    ConstantEntry("sqrt(2)/2", "math.sqrt(2) / 2", "equals 1/sqrt(2)"),
    ConstantEntry("sqrt(3)", "math.sqrt(3)"),
    ConstantEntry("sqrt(3)/2", "math.sqrt(3) / 2"),
    ConstantEntry("1/sqrt(3)", "1 / math.sqrt(3)"),
    ConstantEntry("sqrt(5)", "math.sqrt(5)"),
    ConstantEntry("cbrt(2)", "2 ** (1 / 3)"),
    ConstantEntry("2**(mpf(1)/12)", "2 ** (1 / 12)", "equal-temperament semitone ratio"),
    # named constants
    ConstantEntry("phi", "(1 + math.sqrt(5)) / 2", "golden ratio"),
    ConstantEntry("1/phi", "2 / (1 + math.sqrt(5))", "golden ratio conjugate, phi - 1"),
    ConstantEntry("euler", "numpy.euler_gamma", "Euler-Mascheroni constant (no stdlib name)"),
    ConstantEntry("catalan", "define a named constant CATALAN", "Catalan's constant"),
    ConstantEntry("zeta(3)", "define a named constant APERY", "Apery's constant, zeta(3)"),
)

PHYSICAL_ENTRIES: tuple[ConstantEntry, ...] = (
    ConstantEntry("speed of light c", "scipy.constants.c", "m/s, SI-defined", "299792458"),
    ConstantEntry("standard gravity g", "scipy.constants.g", "m/s^2, SI-defined", "9.80665"),
    ConstantEntry("Avogadro N_A", "scipy.constants.N_A", "1/mol, SI-defined", "6.02214076e23"),
    ConstantEntry("Boltzmann k", "scipy.constants.k", "J/K, SI-defined", "1.380649e-23"),
    ConstantEntry("Planck h", "scipy.constants.h", "J s, SI-defined", "6.62607015e-34"),
    ConstantEntry("reduced Planck hbar", "scipy.constants.hbar", "J s", "1.054571817e-34"),
    ConstantEntry(
        "elementary charge e", "scipy.constants.e", "C, SI-defined", "1.602176634e-19"
    ),
    ConstantEntry("vacuum permittivity", "scipy.constants.epsilon_0", "F/m", "8.8541878128e-12"),
    ConstantEntry("vacuum permeability", "scipy.constants.mu_0", "H/m", "1.25663706212e-6"),
    ConstantEntry("gas constant R", "scipy.constants.R", "J/(mol K)", "8.31446261815324"),
    ConstantEntry("Stefan-Boltzmann sigma", "scipy.constants.sigma", "W/(m^2 K^4)", "5.670374419e-8"),
    ConstantEntry("gravitational constant G", "scipy.constants.G", "m^3/(kg s^2)", "6.6743e-11"),
    ConstantEntry("electron mass", "scipy.constants.m_e", "kg", "9.1093837015e-31"),
    ConstantEntry("proton mass", "scipy.constants.m_p", "kg", "1.67262192369e-27"),
    ConstantEntry("atomic mass constant", "scipy.constants.m_u", "kg", "1.66053906660e-27"),
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
    "mpf",
)


@lru_cache(maxsize=1)
def table() -> tuple[tuple[mpmath.mpf, ConstantEntry], ...]:
    """The full lookup table as (high-precision value, entry) rows."""
    rows: list[tuple[mpmath.mpf, ConstantEntry]] = []
    with mpmath.workdps(60):
        namespace = {name: getattr(mpmath, name) for name in _NAMESPACE_NAMES}
        for entry in MATH_ENTRIES:
            value = mpmath.mpf(eval(entry.form, {"__builtins__": {}}, namespace))
            rows.append((value, entry))
        for entry in PHYSICAL_ENTRIES:
            rows.append((mpmath.mpf(entry.decimal), entry))
    return tuple(rows)
