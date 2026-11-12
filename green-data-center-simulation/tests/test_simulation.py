import unittest
from simulation import Simulation, power, temperature


class ModelTests(unittest.TestCase):
    def test_energy_conservation_and_pue(self):
        for load in (10, 30, 90, 100):
            for liquid, pue in ((False, 1.8), (True, 1.2)):
                p = power(load, liquid)
                self.assertAlmostEqual(p['total'], p['it'] + p['cooling'] + p['other'])
                self.assertAlmostEqual(p['pue'], pue)

    def test_one_hour_savings(self):
        sim = Simulation()
        sim.step(90, True, 3600)
        self.assertAlmostEqual(sim.baseline_kwh - sim.selected_kwh, 55.2)
        self.assertLess(sim.selected_temp, sim.air_temp)

    def test_air_fallback_and_switch_continuity(self):
        sim = Simulation()
        sim.step(90, False)
        self.assertEqual(sim.air_temp, sim.selected_temp)
        self.assertEqual(sim.baseline_kwh, sim.selected_kwh)
        before = sim.selected_temp
        sim.step(90, True)
        self.assertGreater(sim.selected_temp, 22)
        self.assertLess(sim.selected_temp, before + 5)

    def test_thermal_equilibrium_and_step_invariance(self):
        for liquid, k in ((False, 2), (True, 5)):
            equilibrium = 22 + 92 / k
            self.assertAlmostEqual(temperature(equilibrium, 92, liquid, 10), equilibrium)
            a = temperature(30, 92, liquid, 20)
            b = temperature(temperature(30, 92, liquid, 10), 92, liquid, 10)
            self.assertAlmostEqual(a, b)

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            power(101)
        with self.assertRaises(ValueError):
            Simulation().step(30, False, 0)


if __name__ == '__main__':
    unittest.main()
