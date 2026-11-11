import unittest

from samialbion.calculator import Calculator


class CalculatorTests(unittest.TestCase):
    def run_keys(self, sequence):
        calc = Calculator()
        for key in sequence:
            calc.press(key)
        return calc

    def test_addition(self):
        self.assertEqual(self.run_keys("12+8=").display, "20")

    def test_decimal_multiplication(self):
        self.assertEqual(self.run_keys("3,5×2=").display, "7")

    def test_percent_addition(self):
        self.assertEqual(self.run_keys("200+10%=").display, "220")

    def test_division(self):
        self.assertEqual(self.run_keys("9÷4=").display, "2,25")

    def test_division_by_zero_recovers(self):
        calc = self.run_keys("7÷0=")
        self.assertTrue(calc.error)
        self.assertEqual(calc.display, "Division par zéro")
        calc.press("5")
        self.assertEqual(calc.display, "5")

    def test_clear_and_backspace(self):
        calc = self.run_keys("123←")
        self.assertEqual(calc.display, "12")
        calc.press("AC")
        self.assertEqual(calc.display, "0")

    def test_negative(self):
        self.assertEqual(self.run_keys(["8", "±", "+", "3", "="]).display, "-5")

    def test_operator_replacement(self):
        self.assertEqual(self.run_keys(["9", "+", "×", "2", "="]).display, "18")


if __name__ == "__main__":
    unittest.main()
