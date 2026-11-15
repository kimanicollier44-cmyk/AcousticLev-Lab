"""Tests for AcousticLev-Lab: analytic values first, sim outcomes second."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import main as m


# ---- standing wave ------------------------------------------------------
def test_wavelength_40khz():
    assert abs(m.wavelength_m(40000.0) - 343.0 / 40000.0) < 1e-15
    assert abs(m.wavelength_m() - 0.008575) < 1e-12


def test_node_spacing_half_lambda():
    assert abs(m.node_spacing_m() - m.wavelength_m() / 2.0) < 1e-15


def test_nodes_at_odd_quarter_lambda():
    lam = m.wavelength_m()
    nodes = m.pressure_nodes_m(4)
    for j, z in enumerate(nodes):
        assert abs(z - (2 * j + 1) * lam / 4.0) < 1e-15


def test_adjacent_nodes_lambda_half():
    nodes = m.pressure_nodes_m(3)
    assert abs((nodes[1] - nodes[0]) - m.wavelength_m() / 2.0) < 1e-15
    assert abs((nodes[2] - nodes[1]) - m.wavelength_m() / 2.0) < 1e-15


def test_resonant_cavity_lengths():
    lam = m.wavelength_m()
    lengths = m.resonant_cavity_lengths_m(3)
    assert lengths == [lam / 2.0, lam, 3 * lam / 2.0] or all(
        abs(a - b) < 1e-15 for a, b in zip(lengths, [lam / 2, lam, 3 * lam / 2]))


def test_nodes_in_cavity():
    assert m.nodes_in_cavity(40000.0, 0.10) == 23


# ---- SPL ----------------------------------------------------------------
def test_spl_zero_db_is_pref():
    assert abs(m.spl_to_pressure_rms(0.0) - m.P_REF) < 1e-12


def test_spl_20db_is_10x():
    assert abs(m.spl_to_pressure_rms(20.0) / m.P_REF - 10.0) < 1e-9


def test_spl_160db_is_2000_pa():
    assert abs(m.spl_to_pressure_rms(160.0) - 2000.0) < 1e-6


def test_spl_roundtrip():
    for db in (94.0, 140.0, 157.3, 165.0):
        assert abs(m.pressure_rms_to_spl(m.spl_to_pressure_rms(db)) - db) < 1e-9


def test_energy_density_scales_with_p_squared():
    ratio = m.energy_density_j_m3(170.0) / m.energy_density_j_m3(160.0)
    assert abs(ratio - 10.0) < 1e-9


# ---- Gor'kov ------------------------------------------------------------
def test_phi_water():
    phi = m.contrast_factor(1000.0, 1480.0)
    assert 0.80 < phi < 0.86


def test_phi_sign_positive_for_lab_materials():
    for rho, c, _ in m.MATERIALS.values():
        assert m.contrast_factor(rho, c) > 0


def test_force_zero_at_node_and_antinode():
    phi = m.contrast_factor(1000.0, 1480.0)
    z_node = m.pressure_nodes_m(1)[0]
    assert abs(m.gorkov_force_n(z_node, 0.001, phi)) < 1e-12
    assert abs(m.gorkov_force_n(0.0, 0.001, phi)) < 1e-12


def test_force_max_at_lambda_eighth():
    phi = m.contrast_factor(1000.0, 1480.0)
    f = m.gorkov_force_n(m.wavelength_m() / 8.0, 0.001, phi)
    assert abs(f - m.max_force_n(0.001, phi)) < 1e-12


def test_force_restoring_around_node():
    phi = m.contrast_factor(1000.0, 1480.0)
    z_node = m.pressure_nodes_m(1)[0]
    assert m.gorkov_force_n(z_node - 1e-5, 0.001, phi) > 0
    assert m.gorkov_force_n(z_node + 1e-5, 0.001, phi) < 0


def test_force_scales_with_volume():
    phi = m.contrast_factor(1000.0, 1480.0)
    ratio = m.max_force_n(0.002, phi) / m.max_force_n(0.001, phi)
    assert abs(ratio - 8.0) < 1e-9


# ---- ceiling / verdicts ---------------------------------------------------
def test_density_ceiling_160db():
    phi = m.contrast_factor(1000.0, 1480.0)
    assert 2000.0 < m.density_ceiling_kg_m3(phi) < 3300.0


def test_ceiling_plus5db():
    phi = m.contrast_factor(1000.0, 1480.0)
    ratio = (m.density_ceiling_kg_m3(phi, spl_db=165.0)
             / m.density_ceiling_kg_m3(phi, spl_db=160.0))
    assert abs(ratio - math.sqrt(10.0)) < 1e-9


def test_min_spl_water_in_class():
    phi = m.contrast_factor(1000.0, 1480.0)
    assert 150.0 < m.min_spl_for_density(1000.0, phi) < 160.0


def test_min_spl_ordering():
    s_foam = m.min_spl_for_density(*m.MATERIALS["styrofoam"][:2])
    s_water = m.min_spl_for_density(*m.MATERIALS["water"][:2])
    s_steel = m.min_spl_for_density(*m.MATERIALS["steel"][:2])
    assert s_foam < s_water < s_steel


def test_verdicts():
    assert m.levitation_verdict("styrofoam", 0.001)["verdict"] == "levitates"
    assert m.levitation_verdict("water", 0.001)["verdict"] == "levitates"
    assert m.levitation_verdict("glass", 0.001)["verdict"] == "marginal"
    assert m.levitation_verdict("steel", 0.0005)["verdict"] == "no"
    assert m.levitation_verdict("aluminum", 0.001)["verdict"] == "no"


# ---- trap dynamics --------------------------------------------------------
def test_trap_frequency_water():
    phi = m.contrast_factor(1000.0, 1480.0)
    assert 20.0 < m.trap_frequency_hz(0.001, 1000.0, phi) < 45.0


def test_equilibrium_below_node_balances_weight():
    phi = m.contrast_factor(1000.0, 1480.0)
    z_eq = m.equilibrium_height_m(0.001, 1000.0, phi)
    z_node = m.pressure_nodes_m(1)[0]
    assert 0.0 < z_node - z_eq < m.wavelength_m() / 4.0
    weight = m.particle_mass_kg(0.001, 1000.0) * m.G
    assert abs(m.gorkov_force_n(z_eq, 0.001, phi) - weight) < 1e-7


def test_equilibrium_none_for_steel():
    phi = m.contrast_factor(7800.0, 5900.0)
    assert m.equilibrium_height_m(0.0005, 7800.0, phi) is None


def test_dynamics_bounded_and_settles():
    sim = m.trap_dynamics_sim()
    assert sim["levitates"] is True
    assert sim["bounded"] is True
    assert sim["settled"] is True
    assert sim["max_deviation_mm"] <= 0.5 * 1.05


# ---- phased array ---------------------------------------------------------
def test_array_focused_sum_is_n():
    assert abs(m.array_report()["focused_sum"] - m.ARRAY_N) < 1e-6


def test_array_unfocused_weaker():
    rep = m.array_report()
    assert rep["unfocused_sum"] < rep["focused_sum"]


def test_array_delays_nonnegative():
    assert all(d >= 0.0 for d in m.array_focus_delays_s())


def test_array_intensity_gain_n_squared():
    assert abs(m.array_report()["intensity_gain"] - m.ARRAY_N ** 2) < 0.5


# ---- multi-particle / use cases / classifier -------------------------------
def test_two_particle_spacing():
    assert abs(m.two_particle_spacing_m() - m.wavelength_m() / 2.0) < 1e-15


def test_usecases_gated():
    assert len(m.USE_CASES) == 5
    assert all(u["gate"] == "HOLD" for u in m.USE_CASES.values())


def test_classifier_cases():
    rep = m.classify_report()
    assert rep["cases"]["styrofoam_1mm_160db"] == "levitates"
    assert rep["cases"]["water_1mm_160db"] == "levitates"
    assert rep["cases"]["water_1mm_150db"] == "too-dense-or-big"
    assert rep["cases"]["glass_1mm_160db"] == "marginal"
    assert rep["cases"]["steel_0.5mm_160db"] == "too-dense-or-big"
    assert rep["training_accuracy"] >= 0.9


# ---- gates / seats / checks -------------------------------------------------
def test_hold_gates_14():
    assert len(m.HOLD_GATES) == 14
    assert all(v.startswith("HOLD") for v in m.HOLD_GATES.values())


def test_gate_behaviour():
    assert m.gate("levitate_people_claim") == "HOLD"
    assert m.gate("ultrasonic_weaponization") == "HOLD"
    assert m.gate("run_simulation") == "PROCEED"


def test_hold_demo_exit_code():
    assert m.main(["hold-demo"]) == 2
    assert m.main(["hold-demo", "run_simulation"]) == 0


def test_seats_cannot_override():
    b = m.brains_report()
    assert b["decider"]["can_override_hold"] is False
    assert b["decider"]["tighten_only"] is True
    assert b["decider"]["pipeline"] == ["MAP", "MODEL", "STRESS", "DECIDE"]
    assert b["advisor"]["can_override_hold"] is False
    assert b["flow"]["rendered"] is False
    assert b["flow"]["live"] == 0


def test_all_checks_pass():
    checks = m.run_checks()
    assert all(ok for _, ok in checks), [n for n, ok in checks if not ok]
    assert len(checks) == 59


def test_demo_exit_zero(capsys):
    assert m.main([]) == 0
    out = capsys.readouterr().out
    assert "CHECKS 59/59" in out
    assert "VERDICT PROCEED" in out
