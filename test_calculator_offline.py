# ==============================================================================
# آزمون‌های واحد (Unit Tests) برای ماشین‌حساب علمی آفلاین
# سازگاری: سازگار با پایتون 3.11 و پایتون 3.13 (محیط آفلاین)
# تاریخ ایجاد: 2026-11-16
# ==============================================================================

import csv
import json
import math
import tempfile
import unittest
from pathlib import Path

from calculator_offline import CalculatorError, HistoryDatabase, SafeMathEngine


# [Date: 2026-11-16] - مجموعه آزمون‌های موتور ریاضی امن (SafeMathEngine)
class TestSafeMathEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = SafeMathEngine()

    def test_basic_arithmetic_and_persian_digits(self) -> None:
        _, res = self.engine.evaluate("۱۲ + ۳ × ۴ − ۶ ÷ ۲")
        self.assertEqual(res, "21")

    def test_floating_point_cleanup(self) -> None:
        _, res = self.engine.evaluate("0.1 + 0.2")
        self.assertEqual(res, "0.3")

    def test_scientific_notation_preserved(self) -> None:
        val, res = self.engine.evaluate("1e-05 * 2")
        self.assertAlmostEqual(val, 2e-05)
        self.assertEqual(res, "2e-05")

    def test_implicit_multiplication(self) -> None:
        _, res1 = self.engine.evaluate("2(3+4)")
        self.assertEqual(res1, "14")
        _, res2 = self.engine.evaluate("(2+1)(3+1)")
        self.assertEqual(res2, "12")
        val3, _ = self.engine.evaluate("2π")
        self.assertAlmostEqual(val3, 2 * math.pi)

    def test_trig_deg_and_rad_modes(self) -> None:
        self.engine.angle_mode = "DEG"
        _, sin30 = self.engine.evaluate("sin(30)")
        self.assertEqual(sin30, "0.5")
        _, cos90 = self.engine.evaluate("cos(90)")
        self.assertEqual(cos90, "0")
        _, asin_half = self.engine.evaluate("asin(0.5)")
        self.assertEqual(asin_half, "30")

        self.engine.angle_mode = "RAD"
        _, sin_pi_2 = self.engine.evaluate("sin(pi/2)")
        self.assertEqual(sin_pi_2, "1")

    def test_percentage_and_factorial(self) -> None:
        _, p1 = self.engine.evaluate("200 * 15%")
        self.assertEqual(p1, "30")
        _, f1 = self.engine.evaluate("5!")
        self.assertEqual(f1, "120")
        _, f2 = self.engine.evaluate("(2+3)!")
        self.assertEqual(f2, "120")

    def test_roots_logs_and_ans(self) -> None:
        _, r1 = self.engine.evaluate("√144 + ∛(-27)")
        self.assertEqual(r1, "9")
        _, r2 = self.engine.evaluate("ans + log(1000)")
        self.assertEqual(r2, "12")
        _, r3 = self.engine.evaluate("ln(e^2)")
        self.assertEqual(r3, "2")
        _, r4 = self.engine.evaluate("mod(17, 5)")
        self.assertEqual(r4, "2")

    def test_error_handling_and_ast_security(self) -> None:
        with self.assertRaises(CalculatorError):
            self.engine.evaluate("10 / 0")
        with self.assertRaises(CalculatorError):
            self.engine.evaluate("sqrt(-4)")
        with self.assertRaises(CalculatorError):
            self.engine.evaluate("(-3)!")
        with self.assertRaises(CalculatorError):
            self.engine.evaluate("__import__('os').system('echo hack')")
        with self.assertRaises(CalculatorError):
            self.engine.evaluate("10^10000")


# [Date: 2026-11-16] - مجموعه آزمون‌های پایگاه‌داده SQLite و خروجی CSV/JSON
class TestHistoryDatabase(unittest.TestCase):
    def test_crud_and_exports(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            db = HistoryDatabase(db_path=tmp / "test_history.db")

            rec_id = db.add_record("2+2", "4", "DEG")
            self.assertGreater(rec_id, 0)
            db.add_record("sin(30)", "0.5", "DEG")

            records = db.get_all_records()
            self.assertEqual(len(records), 2)
            self.assertEqual(records[0]["expression"], "sin(30)")

            csv_path = tmp / "out.csv"
            json_path = tmp / "out.json"
            self.assertEqual(db.export_to_csv(csv_path), 2)
            self.assertEqual(db.export_to_json(json_path), 2)

            with open(csv_path, encoding="utf-8-sig") as f:
                rows = list(csv.reader(f))
            self.assertEqual(len(rows), 3)  # ردیف سرستون + ۲ رکورد

            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(len(data), 2)

            db.delete_record(rec_id)
            self.assertEqual(len(db.get_all_records()), 1)

            db.clear_all()
            self.assertEqual(len(db.get_all_records()), 0)


if __name__ == "__main__":
    unittest.main()
