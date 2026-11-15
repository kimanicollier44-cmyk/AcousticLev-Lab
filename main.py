#!/usr/bin/env python3
"""AcousticLev-Lab - educational acoustic levitation physics lab.

by Darion Kellar

Pure Python standard library. Zero dependencies. Zero network.
Simulation only: the third levitation family - sound. (LevitationX
covers magnetic + superconducting; this lab goes deep on acoustics.)
Standing waves at lambda/2 node spacing, the Gor'kov potential and
acoustic radiation force on a small sphere, the honest density ceiling
(styrofoam and water droplets yes, dense metal no), SPL requirements
in the ~150-160 dB class, single-axis vs phased-array traps, particle
dynamics in the trap, a containerless-processing use-case mapper, a
TinyML kNN regime classifier, Gemini Carbon 4 as DECIDER (names-only,
tighten-only), Muse as advisor (never overrides HOLD), and Google
Flow plan-only seats.

Every real-hardware / live-operation action is a permanent HOLD gate.
"""
import hashlib
import json
import math
import sys

# ---------------------------------------------------------------- constants
C_AIR = 343.0                       # speed of sound in air, m/s
RHO_AIR = 1.2                       # air density, kg/m^3
P_REF = 20e-6                       # reference sound pressure, Pa (0 dB SPL)
G = 9.80665                         # standard gravity, m/s^2
F_REF = 40000.0                     # reference frequency, Hz (40 kHz ultrasonic)

VERSION = "1.0.0"

# ---------------------------------------------------------------- HOLD gates
HOLD_GATES = {
    "live_hazardous_material_levitation": "HOLD - no live levitation of any hazardous material, ever",
    "real_hardware_control": "HOLD - no control of real transducers, amplifiers, or any hardware",
    "levitate_living_tissue_live": "HOLD - no levitating living tissue, organisms, or animals, live",
    "high_spl_exposure_live": "HOLD - no live high-SPL exposure of people or animals",
    "bypass_spl_limits": "HOLD - SPL safety limits are never bypassed or widened",
    "commercial_product_claim": "HOLD - no claim this simulation is a product or product design",
    "medical_claim": "HOLD - no medical, pharmaceutical-production, or therapeutic claims",
    "claim_silent_operation": "HOLD - no 'silent' claims: levitation-class fields are intense ultrasound",
    "weapons_application_claim": "HOLD - no weapons application claims of any kind",
    "investment_claim": "HOLD - no investment, token, or returns claims",
    "ultrasonic_weaponization": "HOLD - no weaponizing ultrasound: no pain, harm, or crowd-control use",
    "levitate_people_claim": "HOLD - no levitating a person: the density/force math forbids it at safe SPL",
    "industrial_process_claim": "HOLD - no claim this sim is an industrial or production process",
    "guaranteed_performance_claim": "HOLD - no guaranteed levitation performance for any real rig",
}


def gate(action):
    """Return 'HOLD' if the action is gated, else 'PROCEED' (sandbox sim)."""
    return "HOLD" if action in HOLD_GATES else "PROCEED"


# ================================================================ 1. Standing wave
# Two counter-propagating waves (or one wave + reflector) form a standing
# wave p(z,t) = p_a cos(kz) cos(wt): pressure ANTINODE at z = 0, pressure
# NODES at z = (2j+1) * lambda/4. Node planes repeat every lambda/2.

def wavelength_m(freq_hz=F_REF):
    """lambda = c / f."""
    return C_AIR / freq_hz


def wavenumber(freq_hz=F_REF):
    """k = 2 pi / lambda, rad/m."""
    return 2.0 * math.pi / wavelength_m(freq_hz)


def node_spacing_m(freq_hz=F_REF):
    """Distance between adjacent pressure-node planes: lambda/2."""
    return wavelength_m(freq_hz) / 2.0


def pressure_nodes_m(count, freq_hz=F_REF):
    """First `count` pressure-node positions (m), antinode at z = 0."""
    lam = wavelength_m(freq_hz)
    return [(2 * j + 1) * lam / 4.0 for j in range(count)]


def pressure_antinodes_m(count, freq_hz=F_REF):
    """First `count` pressure-antinode positions (m), starting at z = 0."""
    lam = wavelength_m(freq_hz)
    return [j * lam / 2.0 for j in range(count)]


def resonant_cavity_lengths_m(max_n, freq_hz=F_REF):
    """Cavity lengths L = n * lambda/2 that resonate (transducer + reflector)."""
    lam = wavelength_m(freq_hz)
    return [n * lam / 2.0 for n in range(1, max_n + 1)]


def nodes_in_cavity(freq_hz, cavity_m):
    """Whole pressure-node planes that fit inside a cavity of length cavity_m."""
    return int(cavity_m / node_spacing_m(freq_hz))


# ================================================================ 2. SPL <-> pressure
# SPL is defined on the RMS pressure at a pressure antinode:
#   p_rms = P_REF * 10^(SPL/20)
# The standing-wave amplitude (peak at the antinode) is p_a = sqrt(2) p_rms.
# Mean acoustic energy density of the standing wave:
#   E_ac = p_a^2 / (4 rho0 c^2) = p_rms^2 / (2 rho0 c^2)

def spl_to_pressure_rms(spl_db):
    """RMS pressure (Pa) at a pressure antinode for a given SPL in dB."""
    return P_REF * 10.0 ** (spl_db / 20.0)


def pressure_rms_to_spl(p_rms):
    """Inverse of spl_to_pressure_rms."""
    if p_rms <= 0:
        raise ValueError("pressure must be positive")
    return 20.0 * math.log10(p_rms / P_REF)


def standing_amplitude_pa(spl_db):
    """Peak pressure amplitude p_a of the standing wave at an antinode."""
    return math.sqrt(2.0) * spl_to_pressure_rms(spl_db)


def energy_density_j_m3(spl_db):
    """E_ac = p_rms^2 / (2 rho0 c^2), J/m^3."""
    p = spl_to_pressure_rms(spl_db)
    return p * p / (2.0 * RHO_AIR * C_AIR ** 2)


# ================================================================ 3. Gor'kov force
# For a small sphere (radius a, ka << 1) in a 1D standing wave, the Gor'kov
# potential is
#   U(z) = V [ f1 <p^2> / (2 rho0 c^2) - (3/4) f2 rho0 <v^2> ]
# with monopole factor  f1 = 1 - kappa_p/kappa_0   (compressibility ratio)
# and  dipole factor    f2 = 2 (rho_p - rho0) / (2 rho_p + rho0).
# The radiation force F = -dU/dz works out to the standard result
#   F(z) = 4 pi a^3 k E_ac PHI sin(2 k z),   PHI = f1/3 + f2/2
# where PHI is the acoustic contrast factor. For PHI > 0 the force pushes
# the sphere TOWARD the pressure node (restoring on both sides - proven in
# CHECKS by the sign of F on each side of a node); for PHI < 0 it would
# trap at the antinode instead.

def compressibility(rho_kg_m3, c_m_s):
    """kappa = 1 / (rho c^2), 1/Pa."""
    return 1.0 / (rho_kg_m3 * c_m_s ** 2)


KAPPA_AIR = compressibility(RHO_AIR, C_AIR)

# Particle materials: (density kg/m^3, sound speed in material m/s, note)
MATERIALS = {
    "styrofoam": (25.0, 1200.0, "expanded polystyrene bead - the demo classic"),
    "water": (1000.0, 1480.0, "water droplet - containerless chemistry subject"),
    "glass": (2500.0, 5600.0, "glass bead - near the 160 dB ceiling, marginal"),
    "aluminum": (2700.0, 6300.0, "light metal - just past the 160 dB ceiling"),
    "steel": (7800.0, 5900.0, "dense metal - honestly out of reach at 160 dB"),
}


def monopole_f1(rho_p, c_p):
    """f1 = 1 - kappa_p / kappa_0."""
    return 1.0 - compressibility(rho_p, c_p) / KAPPA_AIR


def dipole_f2(rho_p):
    """f2 = 2 (rho_p - rho0) / (2 rho_p + rho0)."""
    return 2.0 * (rho_p - RHO_AIR) / (2.0 * rho_p + RHO_AIR)


def contrast_factor(rho_p, c_p):
    """Acoustic contrast factor PHI = f1/3 + f2/2."""
    return monopole_f1(rho_p, c_p) / 3.0 + dipole_f2(rho_p) / 2.0


def particle_volume_m3(radius_m):
    return 4.0 / 3.0 * math.pi * radius_m ** 3


def particle_mass_kg(radius_m, rho_p):
    return particle_volume_m3(radius_m) * rho_p


def gorkov_force_n(z_m, radius_m, phi, freq_hz=F_REF, spl_db=160.0):
    """Radiation force (N) at height z_m. Positive = upward (+z).

    F(z) = 4 pi a^3 k E_ac PHI sin(2 k z). Zero at nodes AND antinodes;
    maximum at z = lambda/8 (halfway from antinode to node).
    """
    k = wavenumber(freq_hz)
    e_ac = energy_density_j_m3(spl_db)
    return 4.0 * math.pi * radius_m ** 3 * k * e_ac * phi * math.sin(2.0 * k * z_m)


def max_force_n(radius_m, phi, freq_hz=F_REF, spl_db=160.0):
    """Peak |F| over one period (at sin(2kz) = 1)."""
    k = wavenumber(freq_hz)
    e_ac = energy_density_j_m3(spl_db)
    return 4.0 * math.pi * radius_m ** 3 * k * e_ac * phi


# ================================================================ 4. The honest ceiling
# Levitation needs max|F| >= m g. Both scale with the particle volume, so
# the radius cancels (Rayleigh regime): the ceiling is on DENSITY.
#   rho_max = 3 k E_ac PHI / g
# At 40 kHz and 160 dB SPL this model gives rho_max ~ 2,640 kg/m^3:
# styrofoam and water yes, glass marginal, aluminum just past, steel no.
# Raising SPL helps only as pressure^2: +5 dB multiplies the ceiling by
# 10^(5/10) ~ 3.16 - which is why real rigs live in the ~150-160 dB class
# and why 'levitate anything' claims fail arithmetic.

def density_ceiling_kg_m3(phi, freq_hz=F_REF, spl_db=160.0):
    """Highest particle density (kg/m^3) this field can hold against gravity."""
    k = wavenumber(freq_hz)
    e_ac = energy_density_j_m3(spl_db)
    return 3.0 * k * e_ac * phi / G


def min_spl_for_density(rho_p, phi, freq_hz=F_REF):
    """SPL (dB) at which max|F| exactly equals weight for density rho_p.

    Inverts rho_max: E_ac needed = rho_p g / (3 k PHI), then p_rms from
    E_ac = p_rms^2 / (2 rho0 c^2). Model value, labelled as such.
    """
    k = wavenumber(freq_hz)
    e_needed = rho_p * G / (3.0 * k * phi)
    p_rms = math.sqrt(e_needed * 2.0 * RHO_AIR * C_AIR ** 2)
    return pressure_rms_to_spl(p_rms)


def levitation_verdict(material, radius_m, spl_db=160.0, freq_hz=F_REF):
    """Honest per-material verdict from the model, with the numbers shown."""
    rho_p, c_p, note = MATERIALS[material]
    phi = contrast_factor(rho_p, c_p)
    ceiling = density_ceiling_kg_m3(phi, freq_hz, spl_db)
    margin = ceiling / rho_p
    # Rayleigh regime needs a << lambda; practical traps want diameter <~ lambda/2.
    size_ratio = (2.0 * radius_m) / wavelength_m(freq_hz)
    if margin >= 1.5 and size_ratio <= 0.5:
        verdict = "levitates"
    elif margin >= 1.0 and size_ratio <= 0.75:
        verdict = "marginal"
    else:
        verdict = "no"
    return {
        "material": material,
        "density_kg_m3": rho_p,
        "phi": round(phi, 5),
        "density_ceiling_kg_m3": round(ceiling, 1),
        "margin": round(margin, 3),
        "min_spl_db": round(min_spl_for_density(rho_p, phi, freq_hz), 1),
        "diameter_over_lambda": round(size_ratio, 3),
        "verdict": verdict,
        "note": note,
        "model": "Gor'kov Rayleigh-regime model - labelled model values, not rig specs",
    }


# ================================================================ 5. Trap dynamics
# Near a pressure node the force is a linear spring:
#   F ~ -k_trap (z - z_node),  k_trap = 2 k * F_max = 8 pi a^3 k^2 E_ac PHI
# so a trapped particle oscillates at f = (1/2pi) sqrt(k_trap / m).
# With gravity the equilibrium sits BELOW the node, where F_ac(z) = m g.
# The sim integrates the full nonlinear force (semi-implicit Euler,
# fixed step, damping ratio zeta = 0.15 labelled) - deterministic.

def trap_stiffness_n_m(radius_m, phi, freq_hz=F_REF, spl_db=160.0):
    """k_trap = 8 pi a^3 k^2 E_ac PHI (N/m) at a pressure node."""
    k = wavenumber(freq_hz)
    e_ac = energy_density_j_m3(spl_db)
    return 8.0 * math.pi * radius_m ** 3 * k ** 2 * e_ac * phi


def trap_frequency_hz(radius_m, rho_p, phi, freq_hz=F_REF, spl_db=160.0):
    """Small-oscillation frequency (Hz) of a trapped particle."""
    k_trap = trap_stiffness_n_m(radius_m, phi, freq_hz, spl_db)
    m = particle_mass_kg(radius_m, rho_p)
    return math.sqrt(k_trap / m) / (2.0 * math.pi)


def equilibrium_height_m(radius_m, rho_p, phi, freq_hz=F_REF, spl_db=160.0):
    """Height where F_ac(z) = m g, just below the first pressure node.

    Bisection on [0, z_node]: F rises from 0 at the antinode to F_max at
    lambda/8 then falls to 0 at the node; the gravity balance on the
    node-side slope is the stable one. Returns None if the field cannot
    hold the particle at all (F_max < m g).
    """
    z_node = pressure_nodes_m(1, freq_hz)[0]
    weight = particle_mass_kg(radius_m, rho_p) * G
    if max_force_n(radius_m, phi, freq_hz, spl_db) < weight:
        return None
    lo, hi = wavelength_m(freq_hz) / 8.0, z_node  # node-side slope segment
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if gorkov_force_n(mid, radius_m, phi, freq_hz, spl_db) > weight:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def trap_dynamics_sim(radius_m=0.001, rho_p=1000.0, c_p=1480.0,
                      freq_hz=F_REF, spl_db=160.0, displacement_m=0.0005,
                      zeta=0.15, duration_s=1.5, dt=1e-4):
    """Deterministic step-disturbance recovery in the trap (SIM ONLY).

    Particle starts displaced `displacement_m` above equilibrium at rest;
    semi-implicit Euler on the full nonlinear Gor'kov force + gravity +
    viscous damping (zeta labelled). Returns boundedness/settling facts.
    """
    phi = contrast_factor(rho_p, c_p)
    z_eq = equilibrium_height_m(radius_m, rho_p, phi, freq_hz, spl_db)
    if z_eq is None:
        return {"levitates": False}
    m = particle_mass_kg(radius_m, rho_p)
    k_trap = trap_stiffness_n_m(radius_m, phi, freq_hz, spl_db)
    c_damp = 2.0 * zeta * math.sqrt(k_trap * m)
    z = z_eq + displacement_m
    v = 0.0
    max_dev = 0.0
    steps = int(duration_s / dt)
    for _ in range(steps):
        f = gorkov_force_n(z, radius_m, phi, freq_hz, spl_db) - m * G - c_damp * v
        v += (f / m) * dt
        z += v * dt
        max_dev = max(max_dev, abs(z - z_eq))
    return {
        "levitates": True,
        "equilibrium_m": round(z_eq, 6),
        "offset_below_node_mm": round((pressure_nodes_m(1, freq_hz)[0] - z_eq) * 1000.0, 3),
        "initial_displacement_mm": round(displacement_m * 1000.0, 3),
        "max_deviation_mm": round(max_dev * 1000.0, 3),
        "final_deviation_mm": round(abs(z - z_eq) * 1000.0, 4),
        "bounded": max_dev <= displacement_m * 1.05,
        "settled": abs(z - z_eq) < 5e-5,
        "zeta": zeta,
        "model": "nonlinear Gor'kov force + gravity + labelled viscous damping, fixed-step",
    }


# ================================================================ 6. Phased array
# A phased array steers/focuses by phase: to focus at point F, emitter i
# at distance r_i gets phase phi_i = -k r_i (mod 2 pi), so every wave
# arrives in phase: the coherent sum is exactly N (pressure gain N,
# intensity gain N^2). The equivalent delay law is tau_i = (r_max - r_i)/c.
# A single-axis levitator is the N=2 special case: two opposed sources
# (or source + reflector) making the standing wave of section 1.

ARRAY_N = 8
ARRAY_PITCH_M = 0.010               # emitter spacing, m (model array)
ARRAY_FOCUS_M = 0.050               # focal distance on axis, m


def array_positions_m(n=ARRAY_N, pitch_m=ARRAY_PITCH_M):
    """Emitter x-positions (m) on a line array centred on 0, plane z = 0."""
    return [(i - (n - 1) / 2.0) * pitch_m for i in range(n)]


def array_focus_phases(n=ARRAY_N, pitch_m=ARRAY_PITCH_M, focus_m=ARRAY_FOCUS_M,
                       freq_hz=F_REF):
    """Phase (rad, [0, 2pi)) per emitter to focus on axis at focus_m."""
    k = wavenumber(freq_hz)
    phases = []
    for x in array_positions_m(n, pitch_m):
        r = math.hypot(x, focus_m)
        phases.append((-k * r) % (2.0 * math.pi))
    return phases


def array_focus_delays_s(n=ARRAY_N, pitch_m=ARRAY_PITCH_M, focus_m=ARRAY_FOCUS_M):
    """Delay law tau_i = (r_max - r_i) / c (s), all >= 0."""
    rs = [math.hypot(x, focus_m) for x in array_positions_m(n, pitch_m)]
    r_max = max(rs)
    return [(r_max - r) / C_AIR for r in rs]


def array_coherent_sum(phases, n=ARRAY_N, pitch_m=ARRAY_PITCH_M,
                       focus_m=ARRAY_FOCUS_M, freq_hz=F_REF):
    """|sum_i exp(i (phi_i + k r_i))| at the focal point. Focused = N."""
    k = wavenumber(freq_hz)
    re = im = 0.0
    for x, ph in zip(array_positions_m(n, pitch_m), phases):
        ang = ph + k * math.hypot(x, focus_m)
        re += math.cos(ang)
        im += math.sin(ang)
    return math.hypot(re, im)


def array_report():
    phases = array_focus_phases()
    delays = array_focus_delays_s()
    focused = array_coherent_sum(phases)
    unfocused = array_coherent_sum([0.0] * ARRAY_N)
    return {
        "emitters": ARRAY_N,
        "pitch_mm": ARRAY_PITCH_M * 1000.0,
        "focus_mm": ARRAY_FOCUS_M * 1000.0,
        "phases_rad": [round(p, 4) for p in phases],
        "delays_us": [round(d * 1e6, 3) for d in delays],
        "focused_sum": round(focused, 6),
        "unfocused_sum": round(unfocused, 6),
        "pressure_gain": round(focused, 3),
        "intensity_gain": round(focused ** 2, 1),
        "note": "phase hologram concept: one focal trap; per-emitter phase sets "
                "trap position - computed, deterministic, no hardware driven",
    }


# ================================================================ 7. Multi-particle
def two_particle_spacing_m(freq_hz=F_REF):
    """Two particles in adjacent node planes sit exactly lambda/2 apart.

    Spacing only - this lab makes NO interaction claim beyond the shared
    standing-wave geometry (secondary Bjerknes forces are out of scope).
    """
    nodes = pressure_nodes_m(2, freq_hz)
    return nodes[1] - nodes[0]


# ================================================================ 8. Use-case mapper
# Containerless processing: no wall touches the sample. Educational
# mapping only - every production/medical reading of these is HOLD-gated.
USE_CASES = {
    "droplet_chemistry": {
        "sample": "reagent droplet",
        "why": "no container wall to react with, contaminate, or nucleate on",
        "gate": gate("industrial_process_claim"),
    },
    "pharmaceutical_research": {
        "sample": "drug-compound droplet",
        "why": "wall-free drying/crystallisation studies for polymorph research",
        "gate": gate("medical_claim"),
    },
    "materials_undercooling": {
        "sample": "small melt / glass bead",
        "why": "no crucible contact, so melts can undercool below normal freezing",
        "gate": gate("industrial_process_claim"),
    },
    "protein_crystallography": {
        "sample": "protein solution droplet",
        "why": "crystals grow without wall nucleation sites (research context)",
        "gate": gate("medical_claim"),
    },
    "alloy_solidification": {
        "sample": "metal droplet (high-SPL / hybrid rigs)",
        "why": "contact-free solidification microstructure studies",
        "gate": gate("guaranteed_performance_claim"),
    },
}

# ================================================================ 9. kNN classifier
# Features: (density / ceiling-ish scale, radius in mm, SPL in dB).
# Labels: levitates / marginal / too-dense-or-big.
_KNN_TRAIN = [
    ((25.0, 1.0, 160.0), "levitates"),
    ((25.0, 2.0, 150.0), "levitates"),
    ((25.0, 0.5, 145.0), "levitates"),
    ((100.0, 1.0, 155.0), "levitates"),
    ((1000.0, 1.0, 160.0), "levitates"),
    ((1000.0, 0.5, 158.0), "levitates"),
    ((1000.0, 1.0, 165.0), "levitates"),
    ((2500.0, 0.5, 162.0), "levitates"),
    ((1000.0, 2.0, 160.0), "marginal"),
    ((2500.0, 1.0, 160.0), "marginal"),
    ((2500.0, 1.0, 158.0), "marginal"),
    ((25.0, 4.0, 160.0), "marginal"),
    ((7800.0, 0.3, 168.0), "marginal"),
    ((1000.0, 1.0, 150.0), "too-dense-or-big"),
    ((1000.0, 0.5, 148.0), "too-dense-or-big"),
    ((2700.0, 1.0, 160.0), "too-dense-or-big"),
    ((7800.0, 0.5, 160.0), "too-dense-or-big"),
    ((7800.0, 1.0, 155.0), "too-dense-or-big"),
    ((1000.0, 4.0, 160.0), "too-dense-or-big"),
    ((4500.0, 1.0, 160.0), "too-dense-or-big"),
    ((1000.0, 2.5, 160.0), "marginal"),
    ((1200.0, 2.0, 158.0), "marginal"),
    ((7800.0, 0.3, 165.0), "marginal"),
    ((7000.0, 0.4, 166.0), "marginal"),
    ((2700.0, 0.8, 158.0), "too-dense-or-big"),
    ((3000.0, 1.0, 160.0), "too-dense-or-big"),
    ((1500.0, 3.0, 160.0), "too-dense-or-big"),
]
_KNN_SCALE = (1000.0, 2.0, 10.0)    # per-feature normalisation


class RegimeClassifier:
    """kNN (k=3) over (density, radius_mm, spl_db), normalised features."""

    def __init__(self, k=3):
        self.k = k
        self.train = list(_KNN_TRAIN)

    @staticmethod
    def _dist(a, b):
        return math.sqrt(sum(((x - y) / s) ** 2
                             for x, y, s in zip(a, b, _KNN_SCALE)))

    def classify(self, density_kg_m3, radius_m, spl_db):
        feats = (density_kg_m3, radius_m * 1000.0, spl_db)
        ranked = sorted(self.train, key=lambda t: self._dist(feats, t[0]))
        votes = {}
        for _, label in ranked[: self.k]:
            votes[label] = votes.get(label, 0) + 1
        return sorted(votes.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]

    def training_accuracy(self):
        hits = sum(1 for (d, r_mm, s), label in self.train
                   if self.classify(d, r_mm / 1000.0, s) == label)
        return round(hits / len(self.train), 3)


def classify_report():
    clf = RegimeClassifier()
    cases = {
        "styrofoam_1mm_160db": (25.0, 0.001, 160.0),
        "water_1mm_160db": (1000.0, 0.001, 160.0),
        "water_1mm_150db": (1000.0, 0.001, 150.0),
        "glass_1mm_160db": (2500.0, 0.001, 160.0),
        "steel_0.5mm_160db": (7800.0, 0.0005, 160.0),
    }
    return {
        "cases": {name: clf.classify(*args) for name, args in cases.items()},
        "training_accuracy": clf.training_accuracy(),
        "features": ["density_kg_m3", "radius_mm", "spl_db"],
        "labels": ["levitates", "marginal", "too-dense-or-big"],
    }


# ================================================================ 10. Advisory seats
def _trace(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def carbon4_decide(topic="acousticlev-demo"):
    """Gemini Carbon 4 DECIDER seat: MAP->MODEL->STRESS->DECIDE.

    Names-only keys, live calls 0, tighten-only: can add HOLDs, never lift one.
    """
    stages = ["MAP", "MODEL", "STRESS", "DECIDE"]
    payload = {"seat": "gemini-carbon-4", "topic": topic, "stages": stages}
    return {
        "seat": "Gemini Carbon 4 Extended Thinking",
        "role": "DECIDER",
        "pipeline": stages,
        "tiers": [2048, 8192, 32768],
        "key": "names-only (GEMINI_API_KEY name checked, value never read)",
        "live_calls": 0,
        "can_override_hold": False,
        "tighten_only": True,
        "decision": "PROCEED (sandbox simulation only)",
        "trace_sha256_16": _trace(payload),
    }


def claude_advisor(topic="acousticlev-demo"):
    """Muse advisor seat: advisory only, authority none."""
    return {
        "seat": "Muse",
        "role": "advisor",
        "authority": "none - advisory only",
        "can_override_hold": False,
        "live_calls": 0,
        "advice": "Keep every real-hardware action behind its HOLD gate.",
        "trace_sha256_16": _trace({"seat": "claude-advisor", "topic": topic}),
    }


def google_flow_plan():
    """Google Flow: plan-only. Nothing renders, nothing is sent."""
    return {
        "seat": "Google Flow",
        "flows": ["FlowX task graph", "Workspace Studio drafts",
                  "Filmmaking 5-shot storyboard", "DataX data-flow"],
        "rendered": False,
        "live": 0,
        "plan": ["standing-wave node explainer", "Gor'kov force curve story",
                 "density-ceiling hero chart", "phased-array focus demo"],
    }


def brains_report():
    return {"decider": carbon4_decide(), "advisor": claude_advisor(),
            "flow": google_flow_plan()}


# ================================================================ checks
def run_checks():
    c = []

    def chk(name, ok):
        c.append((name, bool(ok)))

    lam = wavelength_m()
    k = wavenumber()
    chk("wavelength_40khz", abs(lam - 0.008575) < 1e-12)
    chk("node_spacing_half_lambda", abs(node_spacing_m() - lam / 2.0) < 1e-15)
    nodes = pressure_nodes_m(3)
    chk("nodes_at_odd_quarter_lambda",
        all(abs(nodes[j] - (2 * j + 1) * lam / 4.0) < 1e-15 for j in range(3)))
    chk("adjacent_nodes_lambda_half",
        abs((nodes[1] - nodes[0]) - lam / 2.0) < 1e-15)
    chk("antinode_at_zero", pressure_antinodes_m(1)[0] == 0.0)
    chk("cavity_resonance_n_half_lambda",
        abs(resonant_cavity_lengths_m(3)[2] - 3 * lam / 2.0) < 1e-15)
    chk("nodes_in_10cm_cavity", nodes_in_cavity(F_REF, 0.10) == 23)
    chk("spl_0db_is_pref", abs(spl_to_pressure_rms(0.0) - P_REF) < 1e-12)
    chk("spl_20db_is_10x", abs(spl_to_pressure_rms(20.0) / P_REF - 10.0) < 1e-9)
    chk("spl_roundtrip", abs(pressure_rms_to_spl(spl_to_pressure_rms(157.3)) - 157.3) < 1e-9)
    chk("spl_160db_is_2000pa", abs(spl_to_pressure_rms(160.0) - 2000.0) < 1e-6)
    chk("energy_density_scales_p_squared",
        abs(energy_density_j_m3(170.0) / energy_density_j_m3(160.0) - 10.0) < 1e-9)
    phi_w = contrast_factor(*MATERIALS["water"][:2])
    phi_s = contrast_factor(*MATERIALS["styrofoam"][:2])
    phi_st = contrast_factor(*MATERIALS["steel"][:2])
    chk("phi_water_in_range", 0.80 < phi_w < 0.86)
    chk("phi_styrofoam_positive", 0.7 < phi_s < 0.85)
    chk("phi_steel_near_limit", 0.82 < phi_st < 0.85)
    a = 0.001
    z_node = nodes[0]
    chk("force_zero_at_node", abs(gorkov_force_n(z_node, a, phi_w)) < 1e-12)
    chk("force_zero_at_antinode", abs(gorkov_force_n(0.0, a, phi_w)) < 1e-12)
    chk("force_max_at_lambda_eighth",
        abs(gorkov_force_n(lam / 8.0, a, phi_w) - max_force_n(a, phi_w)) < 1e-12)
    eps = 1e-5
    chk("force_restoring_below_node", gorkov_force_n(z_node - eps, a, phi_w) > 0)
    chk("force_restoring_above_node", gorkov_force_n(z_node + eps, a, phi_w) < 0)
    chk("force_scales_volume",
        abs(max_force_n(0.002, phi_w) / max_force_n(0.001, phi_w) - 8.0) < 1e-9)
    ceil160 = density_ceiling_kg_m3(phi_w)
    chk("density_ceiling_160db_range", 2000.0 < ceil160 < 3300.0)
    chk("ceiling_water_below", MATERIALS["water"][0] < ceil160)
    chk("ceiling_steel_above", MATERIALS["steel"][0] > density_ceiling_kg_m3(phi_st))
    chk("ceiling_plus5db_x3_16",
        abs(density_ceiling_kg_m3(phi_w, spl_db=165.0) / ceil160 - 10.0 ** 0.5) < 1e-9)
    spl_water = min_spl_for_density(1000.0, phi_w)
    chk("min_spl_water_in_150_160_class", 150.0 < spl_water < 160.0)
    chk("min_spl_ordering",
        min_spl_for_density(25.0, phi_s) < spl_water < min_spl_for_density(7800.0, phi_st))
    chk("verdict_styrofoam_levitates",
        levitation_verdict("styrofoam", 0.001)["verdict"] == "levitates")
    chk("verdict_water_levitates",
        levitation_verdict("water", 0.001)["verdict"] == "levitates")
    chk("verdict_glass_marginal",
        levitation_verdict("glass", 0.001)["verdict"] == "marginal")
    chk("verdict_steel_no", levitation_verdict("steel", 0.0005)["verdict"] == "no")
    chk("trap_stiffness_positive", trap_stiffness_n_m(a, phi_w) > 0)
    f_trap = trap_frequency_hz(a, 1000.0, phi_w)
    chk("trap_frequency_water_1mm_range", 20.0 < f_trap < 45.0)
    z_eq = equilibrium_height_m(a, 1000.0, phi_w)
    chk("equilibrium_exists", z_eq is not None)
    chk("equilibrium_below_node", 0.0 < z_node - z_eq < lam / 4.0)
    chk("equilibrium_balances_weight",
        abs(gorkov_force_n(z_eq, a, phi_w) - particle_mass_kg(a, 1000.0) * G) < 1e-7)
    chk("equilibrium_none_for_steel",
        equilibrium_height_m(0.0005, 7800.0, phi_st) is None)
    sim = trap_dynamics_sim()
    chk("dynamics_bounded", sim["bounded"])
    chk("dynamics_settles", sim["settled"])
    arr = array_report()
    chk("array_focused_sum_is_n", abs(arr["focused_sum"] - ARRAY_N) < 1e-6)
    chk("array_unfocused_weaker", arr["unfocused_sum"] < arr["focused_sum"])
    chk("array_delays_nonnegative", all(d >= 0.0 for d in array_focus_delays_s()))
    chk("array_intensity_gain_n_squared",
        abs(arr["intensity_gain"] - ARRAY_N ** 2) < 0.5)
    chk("two_particle_spacing", abs(two_particle_spacing_m() - lam / 2.0) < 1e-15)
    chk("usecases_five", len(USE_CASES) == 5)
    chk("usecases_all_gated", all(u["gate"] == "HOLD" for u in USE_CASES.values()))
    rep = classify_report()
    chk("classifier_styrofoam", rep["cases"]["styrofoam_1mm_160db"] == "levitates")
    chk("classifier_water_160", rep["cases"]["water_1mm_160db"] == "levitates")
    chk("classifier_water_150_no", rep["cases"]["water_1mm_150db"] == "too-dense-or-big")
    chk("classifier_glass_marginal", rep["cases"]["glass_1mm_160db"] == "marginal")
    chk("classifier_steel_no", rep["cases"]["steel_0.5mm_160db"] == "too-dense-or-big")
    chk("hold_gates_14", len(HOLD_GATES) == 14
        and all(v.startswith("HOLD") for v in HOLD_GATES.values()))
    chk("gate_people_hold", gate("levitate_people_claim") == "HOLD")
    chk("gate_sandbox_proceed", gate("run_simulation") == "PROCEED")
    b = brains_report()
    chk("carbon4_no_override", b["decider"]["can_override_hold"] is False)
    chk("carbon4_tighten_only", b["decider"]["tighten_only"] is True)
    chk("carbon4_stages", b["decider"]["pipeline"] == ["MAP", "MODEL", "STRESS", "DECIDE"])
    chk("claude_no_override", b["advisor"]["can_override_hold"] is False)
    chk("flow_plan_only", b["flow"]["rendered"] is False and b["flow"]["live"] == 0)
    return c


# ================================================================ CLI / demo
def demo():
    print("=" * 68)
    print("AcousticLev-Lab - educational acoustic levitation physics lab")
    print("by Darion Kellar | MIT | pure stdlib | zero network | SIM ONLY")
    print("=" * 68)
    lam = wavelength_m()
    print("\n[1] Standing wave (40 kHz in air, c = 343 m/s)")
    print(f"    lambda = {lam * 1000:.3f} mm | node spacing = {node_spacing_m() * 1000:.3f} mm (lambda/2)")
    print(f"    first nodes (mm): {[round(z * 1000, 3) for z in pressure_nodes_m(4)]}")
    print(f"    resonant cavities (mm): {[round(z * 1000, 2) for z in resonant_cavity_lengths_m(3)]}"
          f" | nodes in 10 cm = {nodes_in_cavity(F_REF, 0.10)}")
    print("\n[2] SPL -> pressure (why the ~150-160 dB class?)")
    for db in (140.0, 150.0, 155.0, 160.0, 165.0):
        print(f"    {db:.0f} dB -> p_rms {spl_to_pressure_rms(db):8.1f} Pa | "
              f"E_ac {energy_density_j_m3(db):7.3f} J/m^3")
    print("    40 kHz is ultrasonic (inaudible pitch) - but 160 dB is an intense")
    print("    field regardless of pitch; live exposure is HOLD-gated.")
    print("\n[3] Gor'kov contrast factors (PHI > 0 traps at the pressure node)")
    for name, (rho, cp, _note) in MATERIALS.items():
        print(f"    {name:10s} rho {rho:7.1f} kg/m^3  PHI = {contrast_factor(rho, cp):.4f}")
    print("\n[4] The honest density ceiling @ 40 kHz, 160 dB")
    for name in MATERIALS:
        v = levitation_verdict(name, 0.001)
        print(f"    {name:10s} ceiling {v['density_ceiling_kg_m3']:7.1f} kg/m^3 | "
              f"needs ~{v['min_spl_db']:5.1f} dB | verdict (1 mm) = {v['verdict']}")
    print("    Styrofoam + water droplets: yes. Glass: marginal. Steel: no.")
    print("\n[5] Trap dynamics (water droplet, 1 mm radius, 160 dB)")
    phi_w = contrast_factor(*MATERIALS["water"][:2])
    print(f"    stiffness = {trap_stiffness_n_m(0.001, phi_w):.2f} N/m | "
          f"oscillation = {trap_frequency_hz(0.001, 1000.0, phi_w):.1f} Hz")
    sim = trap_dynamics_sim()
    print(f"    equilibrium sits {sim['offset_below_node_mm']} mm below the node (gravity sag)")
    print(f"    +0.5 mm step: max dev {sim['max_deviation_mm']} mm, final dev "
          f"{sim['final_deviation_mm']} mm, bounded = {sim['bounded']}, settled = {sim['settled']}")
    print("\n[6] Phased array vs single axis")
    arr = array_report()
    print(f"    {arr['emitters']} emitters, focus @ {arr['focus_mm']:.0f} mm: "
          f"coherent sum {arr['focused_sum']} (pressure gain x{arr['pressure_gain']}, "
          f"intensity x{arr['intensity_gain']})")
    print(f"    unfocused sum {arr['unfocused_sum']} - phase is what makes the trap")
    print(f"    delays (us): {arr['delays_us']}")
    print("\n[7] Multi-particle")
    print(f"    two droplets in adjacent nodes sit {two_particle_spacing_m() * 1000:.3f} mm apart"
          " (spacing only - no interaction claim)")
    print("\n[8] Containerless processing map (educational; production = HOLD)")
    for name, u in USE_CASES.items():
        print(f"    {name:24s} {u['sample']:32s} gate = {u['gate']}")
    print("\n[9] Regime classifier (TinyML kNN)")
    rep = classify_report()
    for name, label in rep["cases"].items():
        print(f"    {name:22s} -> {label}")
    print(f"    training accuracy = {rep['training_accuracy']}")
    print("\n[10] Advisory seats")
    print(f"    decider: {carbon4_decide()['decision']} trace={carbon4_decide()['trace_sha256_16']}")
    print(f"    advisor can_override_hold = {claude_advisor()['can_override_hold']}")
    print(f"    flow rendered = {google_flow_plan()['rendered']} live = {google_flow_plan()['live']}")
    print(f"\n[11] HOLD gates: {len(HOLD_GATES)}")
    for k in HOLD_GATES:
        print(f"    HOLD  {k}")
    checks = run_checks()
    passed = sum(1 for _, ok in checks if ok)
    print(f"\nCHECKS {passed}/{len(checks)}")
    for name, ok in checks:
        if not ok:
            print(f"    FAIL {name}")
    verdict = "PROCEED" if passed == len(checks) else "HOLD"
    print(f"VERDICT {verdict} (sandbox simulation only) | HOLD gates {len(HOLD_GATES)}")
    return 0 if passed == len(checks) else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] == "demo":
        return demo()
    cmd = argv[0]
    if cmd == "checks":
        checks = run_checks()
        for name, ok in checks:
            print(f"{'PASS' if ok else 'FAIL'} {name}")
        print(f"CHECKS {sum(1 for _, ok in checks if ok)}/{len(checks)}")
        return 0 if all(ok for _, ok in checks) else 1
    if cmd == "wave":
        print(json.dumps({
            "lambda_mm": round(wavelength_m() * 1000, 4),
            "node_spacing_mm": round(node_spacing_m() * 1000, 4),
            "nodes_mm": [round(z * 1000, 3) for z in pressure_nodes_m(5)],
            "resonant_cavities_mm": [round(z * 1000, 2) for z in resonant_cavity_lengths_m(4)],
        }, indent=2, sort_keys=True))
        return 0
    if cmd == "force":
        out = {}
        for name in MATERIALS:
            rho, cp, _ = MATERIALS[name]
            phi = contrast_factor(rho, cp)
            out[name] = {
                "phi": round(phi, 5),
                "max_force_n_1mm": max_force_n(0.001, phi),
                "weight_n_1mm": particle_mass_kg(0.001, rho) * G,
            }
        print(json.dumps(out, indent=2, sort_keys=True))
        return 0
    if cmd == "spl":
        out = {name: levitation_verdict(name, 0.001) for name in MATERIALS}
        print(json.dumps(out, indent=2, sort_keys=True))
        return 0
    if cmd == "array":
        print(json.dumps(array_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "dynamics":
        print(json.dumps(trap_dynamics_sim(), indent=2, sort_keys=True))
        return 0
    if cmd == "classify":
        print(json.dumps(classify_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "usecases":
        print(json.dumps(USE_CASES, indent=2, sort_keys=True))
        return 0
    if cmd == "brains":
        print(json.dumps(brains_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "holds":
        for k, v in HOLD_GATES.items():
            print(f"{k}: {v}")
        return 0
    if cmd == "hold-demo":
        action = argv[1] if len(argv) > 1 else "levitate_living_tissue_live"
        print(f"{action}: {HOLD_GATES.get(action, 'PROCEED - not gated')}")
        return 2 if gate(action) == "HOLD" else 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
