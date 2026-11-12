from pathlib import Path
import unittest
from streamlit.testing.v1 import AppTest


class AppTests(unittest.TestCase):
    def test_controls_and_simulation_lifecycle(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[3].value, '1.80')
        self.assertTrue(app.toggle[0].disabled)
        app.radio[0].set_value('Green').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[3].value, '1.20')
        app.slider[0].set_value(90).run()
        self.assertEqual(app.metric[2].value, '110.4 kW')
        app.button[0].click().run()
        self.assertTrue(app.session_state['running'])
        app.session_state['last_tick'] -= 2
        app.run()
        self.assertEqual(app.session_state['sim'].seconds, 10)
        self.assertGreater(app.session_state['sim'].baseline_kwh - app.session_state['sim'].selected_kwh, 0)
        app.button[0].click().run()
        elapsed = app.session_state['sim'].seconds
        app.run()
        self.assertEqual(app.session_state['sim'].seconds, elapsed)
        app.toggle[0].set_value(False).run()
        self.assertEqual(app.metric[3].value, '1.80')
        app.button[1].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['sim'].seconds, 0)
        self.assertEqual(app.session_state['sim'].selected_temp, 30)
        self.assertFalse(app.session_state['running'])
        self.assertEqual(app.slider[0].value, 90)
