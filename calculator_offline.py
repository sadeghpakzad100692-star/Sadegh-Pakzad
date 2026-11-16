# ==============================================================================
# برنامه ماشین‌حساب علمی و تاریخچه‌دار کاملاً آفلاین (Offline Scientific Calculator)
# سازگاری: سازگار با پایتون 3.11 و پایتون 3.13 (محیط 100% آفلاین بدون نیاز به اینترنت)
# وابستگی‌ها: بدون نیاز به نصب پکیج خارجی (تنها با کتابخانه استاندارد پایتون)
# تاریخ ایجاد: 2026-11-16
# ==============================================================================

from __future__ import annotations

import ast
import csv
import json
import math
import operator
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

# [Date: 2026-11-16] - ایمپورت امن کتابخانه گرافیکی استاندارد tkinter برای پشتیبانی از اجرا و تست در محیط‌های بدون GUI
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    HAS_TKINTER = True
except ImportError:  # pragma: no cover
    tk = None  # type: ignore[assignment]
    filedialog = None  # type: ignore[assignment]
    messagebox = None  # type: ignore[assignment]
    ttk = None  # type: ignore[assignment]
    HAS_TKINTER = False


# [Date: 2026-11-16] - نگاشت ارقام فارسی و عربی به ارقام استاندارد انگلیسی برای محاسبه دقیق
PERSIAN_TO_ENGLISH_DIGITS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫٬×÷−",
    "01234567890123456789.,*/-",
)


# [Date: 2026-11-16] - تعریف خطای اختصاصی ماشین‌حساب برای نمایش پیام‌های خوانای فارسی به کاربر
class CalculatorError(Exception):
    """خطای قابل نمایش به کاربر هنگام بروز مشکل در عبارت ریاضی."""


# [Date: 2026-11-16] - موتور ارزیابی امن عبارات ریاضی با استفاده از AST (بدون استفاده از eval ناامن)
class SafeMathEngine:
    """
    این کلاس عبارات ریاضی را بدون استفاده از تابع خطرناک eval()،
    از طریق درخت نحو انتزاعی (AST) پایتون تجزیه و محاسبه می‌کند.
    """

    # عملگرهای دوتایی مجاز
    BINARY_OPERATORS: dict[type[ast.operator], Callable[[float, float], float]] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }

    # عملگرهای تکی مجاز (مثبت و منفی)
    UNARY_OPERATORS: dict[type[ast.unaryop], Callable[[float], float]] = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    def __init__(self) -> None:
        # [Date: 2026-11-16] - مقداردهی اولیه وضعیت زاویه (درجه/رادیان) و آخرین پاسخ (Ans)
        self.angle_mode: str = "DEG"  # مقادیر مجاز: "DEG" (درجه) یا "RAD" (رادیان)
        self.last_answer: float = 0.0

    # [Date: 2026-11-16] - تابع کمکی برای ریشه سوم که با اعداد منفی نیز به درستی کار می‌کند
    @staticmethod
    def _safe_cbrt(x: float) -> float:
        return math.copysign(abs(x) ** (1.0 / 3.0), x)

    # [Date: 2026-11-16] - تابع کمکی فاکتوریل با اعتبارسنجی عدد صحیح غیرمنفی و جلوگیری از سرریز حافظه
    @staticmethod
    def _safe_factorial(x: float) -> float:
        if x < 0 or not float(x).is_integer():
            raise CalculatorError("فاکتوریل فقط برای اعداد صحیح غیرمنفی تعریف شده است.")
        n = int(x)
        if n > 170:
            raise CalculatorError("مقدار فاکتوریل بیش از حد بزرگ است (حداکثر 170!).")
        return float(math.factorial(n))

    # [Date: 2026-11-16] - تبدیل زاویه به رادیان در صورت فعال بودن حالت درجه (DEG)
    def _to_radians(self, x: float) -> float:
        return math.radians(x) if self.angle_mode == "DEG" else x

    # [Date: 2026-11-16] - تبدیل زاویه خروجی توابع معکوس مثلثاتی به درجه در صورت فعال بودن DEG
    def _from_radians(self, x: float) -> float:
        return math.degrees(x) if self.angle_mode == "DEG" else x

    # [Date: 2026-11-16] - توابع مثلثاتی و علمی با پشتیبانی از حالت درجه/رادیان و بررسی خطای دامنه
    def _sin(self, x: float) -> float:
        res = math.sin(self._to_radians(x))
        return 0.0 if abs(res) < 1e-12 else res

    def _cos(self, x: float) -> float:
        res = math.cos(self._to_radians(x))
        return 0.0 if abs(res) < 1e-12 else res

    def _tan(self, x: float) -> float:
        rad = self._to_radians(x)
        if abs(math.cos(rad)) < 1e-12:
            raise CalculatorError("مقدار تانژانت برای این زاویه تعریف نشده است.")
        res = math.tan(rad)
        return 0.0 if abs(res) < 1e-12 else res

    def _asin(self, x: float) -> float:
        if x < -1 or x > 1:
            raise CalculatorError("ورودی تابع asin باید بین -1 و 1 باشد.")
        return self._from_radians(math.asin(x))

    def _acos(self, x: float) -> float:
        if x < -1 or x > 1:
            raise CalculatorError("ورودی تابع acos باید بین -1 و 1 باشد.")
        return self._from_radians(math.acos(x))

    def _atan(self, x: float) -> float:
        return self._from_radians(math.atan(x))

    @staticmethod
    def _sqrt(x: float) -> float:
        if x < 0:
            raise CalculatorError("محاسبه ریشه دوم عدد منفی در اعداد حقیقی مجاز نیست.")
        return math.sqrt(x)

    @staticmethod
    def _log10(x: float) -> float:
        if x <= 0:
            raise CalculatorError("ورودی لگاریتم (log) باید بزرگ‌تر از صفر باشد.")
        return math.log10(x)

    @staticmethod
    def _ln(x: float) -> float:
        if x <= 0:
            raise CalculatorError("ورودی لگاریتم طبیعی (ln) باید بزرگ‌تر از صفر باشد.")
        return math.log(x)

    @staticmethod
    def _mod(a: float, b: float) -> float:
        if b == 0:
            raise CalculatorError("باقی‌مانده تقسیم بر صفر تعریف نشده است.")
        return a % b

    # [Date: 2026-11-16] - پیش‌پردازش عبارت ورودی (تبدیل نمادها، درصد، فاکتوریل و ضرب ضمنی)
    def preprocess_expression(self, expression: str) -> str:
        if not expression or not expression.strip():
            raise CalculatorError("عبارت ورودی خالی است.")

        expr = expression.strip().translate(PERSIAN_TO_ENGLISH_DIGITS)
        expr = expr.replace("π", "pi").replace("√", "sqrt").replace("∛", "cbrt")
        expr = expr.replace("^", "**").replace(" ", "")
        # تبدیل ریشه بدون پرانتز مانند √144 یا ∛27 به شکل تابعی sqrt(144) و cbrt(27)
        expr = re.sub(r"\b(sqrt|cbrt)(\d+(?:\.\d+)?)", r"\1(\2)", expr)

        # تبدیل علامت درصد (%) به تقسیم بر 100؛ مثال: 50% -> (50/100)
        # ابتدا حالات پرانتزی و عددی دارای % را تبدیل می‌کنیم
        while "%" in expr:
            new_expr = re.sub(
                r"(\([^()]+\)|\d+(?:\.\d+)?|[a-zA-Z_][a-zA-Z0-9_]*)%",
                r"(\1/100)",
                expr,
            )
            if new_expr == expr:
                raise CalculatorError("کاربرد علامت درصد (%) در عبارت نامعتبر است.")
            expr = new_expr

        # تبدیل علامت فاکتوریل (!) به فراخوانی تابع fact(...)
        while "!" in expr:
            new_expr = re.sub(
                r"(\([^()]+\)|\d+(?:\.\d+)?|[a-zA-Z_][a-zA-Z0-9_]*)!",
                r"fact(\1)",
                expr,
            )
            if new_expr == expr:
                raise CalculatorError("کاربرد علامت فاکتوریل (!) در عبارت نامعتبر است.")
            expr = new_expr

        # پشتیبانی از ضرب ضمنی مانند: 2pi ، 2(3+4) ، (2)(3) ، 5sin(30) بدون خراب کردن نماد علمی مثل 1e-05
        expr = re.sub(r"(\d|\))(?=\()", r"\1*", expr)
        expr = re.sub(r"(\))(?=\d|[a-zA-Z_])", r"\1*", expr)
        expr = re.sub(r"(\d)(?=[a-zA-Z_])(?![eE][+-]?\d)", r"\1*", expr)
        expr = re.sub(r"\b(pi|e|ans)(?=\d|\()", r"\1*", expr, flags=re.IGNORECASE)

        return expr

    # [Date: 2026-11-16] - پیمایش بازگشتی درخت AST و ارزیابی امن گره‌ها
    def _eval_node(self, node: ast.AST) -> float:
        constants: dict[str, float] = {
            "pi": math.pi,
            "e": math.e,
            "ans": self.last_answer,
        }

        functions: dict[str, Callable[..., float]] = {
            "sin": self._sin,
            "cos": self._cos,
            "tan": self._tan,
            "asin": self._asin,
            "acos": self._acos,
            "atan": self._atan,
            "sqrt": self._sqrt,
            "cbrt": self._safe_cbrt,
            "log": self._log10,
            "ln": self._ln,
            "exp": math.exp,
            "abs": abs,
            "fact": self._safe_factorial,
            "floor": lambda x: float(math.floor(x)),
            "ceil": lambda x: float(math.ceil(x)),
            "round": lambda x: float(round(x)),
            "mod": self._mod,
        }

        if isinstance(node, ast.Expression):
            return self._eval_node(node.body)

        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                try:
                    return float(node.value)
                except OverflowError as exc:
                    raise CalculatorError("عدد ورودی بیش از حد بزرگ است.") from exc
            raise CalculatorError("ثابت عددی نامعتبر در عبارت وجود دارد.")

        if isinstance(node, ast.Name):
            key = node.id.lower()
            if key in constants:
                return float(constants[key])
            raise CalculatorError(f"شناسه یا متغیر ناشناخته: {node.id}")

        if isinstance(node, ast.UnaryOp):
            op_func = self.UNARY_OPERATORS.get(type(node.op))
            if op_func is None:
                raise CalculatorError("عملگر تکی پشتیبانی نمی‌شود.")
            return float(op_func(self._eval_node(node.operand)))

        if isinstance(node, ast.BinOp):
            op_func = self.BINARY_OPERATORS.get(type(node.op))
            if op_func is None:
                raise CalculatorError("عملگر دوتایی پشتیبانی نمی‌شود.")
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)) and right == 0:
                raise CalculatorError("تقسیم بر صفر مجاز نیست.")
            try:
                result = op_func(left, right)
            except OverflowError as exc:
                raise CalculatorError("نتیجه محاسبه بیش از حد بزرگ است.") from exc
            except ValueError as exc:
                raise CalculatorError("عملیات ریاضی در محدوده مجاز نیست.") from exc
            if isinstance(result, complex):
                raise CalculatorError("نتیجه مختلط در این حالت پشتیبانی نمی‌شود.")
            return float(result)

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise CalculatorError("فراخوانی تابع نامعتبر است.")
            func_name = node.func.id.lower()
            if func_name not in functions:
                raise CalculatorError(f"تابع ناشناخته: {node.func.id}")
            if node.keywords:
                raise CalculatorError("آرگومان نام‌دار در توابع ریاضی پشتیبانی نمی‌شود.")
            args = [self._eval_node(arg) for arg in node.args]
            try:
                return float(functions[func_name](*args))
            except TypeError as exc:
                raise CalculatorError(f"تعداد آرگومان‌های تابع {func_name} نادرست است.") from exc
            except OverflowError as exc:
                raise CalculatorError("نتیجه تابع بیش از حد بزرگ است.") from exc

        raise CalculatorError("ساختار عبارت ریاضی پشتیبانی نمی‌شود.")

    # [Date: 2026-11-16] - فرمت‌بندی عدد خروجی برای حذف خطاهای ممیز شناور (مانند 0.30000000000000004)
    @staticmethod
    def format_number(value: float) -> str:
        if math.isnan(value) or math.isinf(value):
            raise CalculatorError("نتیجه نامتعین یا بی‌نهایت است.")
        if abs(value) < 1e-14:
            value = 0.0
        # اگر عدد بسیار نزدیک به عدد صحیح باشد، بدون اعشار نمایش بده
        if abs(value - round(value)) < 1e-12 and abs(value) < 1e15:
            return str(int(round(value)))
        formatted = f"{value:.12g}"
        return "0" if formatted == "-0" else formatted

    # [Date: 2026-11-16] - متد اصلی ارزیابی عبارت و بازگرداندن مقدار عددی و رشته فرمت‌شده
    def evaluate(self, expression: str, update_ans: bool = True) -> tuple[float, str]:
        processed = self.preprocess_expression(expression)
        try:
            tree = ast.parse(processed, mode="eval")
        except SyntaxError as exc:
            raise CalculatorError("نحو عبارت ریاضی نادرست است (پرانتزها یا عملگرها را بررسی کنید).") from exc

        result = self._eval_node(tree)
        formatted = self.format_number(result)
        if update_ans:
            self.last_answer = result
        return result, formatted


# [Date: 2026-11-16] - مدیریت پایگاه‌داده محلی SQLite برای نگهداری و خروجی گرفتن تاریخچه محاسبات
class HistoryDatabase:
    """
    این کلاس تاریخچه محاسبات را در یک فایل SQLite محلی ذخیره می‌کند
    تا در اجراهای بعدی نیز داده‌ها حفظ شوند.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            db_path = Path(__file__).resolve().parent / "calculator_history.db"
        self.db_path = db_path
        self._init_db()

    # [Date: 2026-11-16] - ساخت جدول تاریخچه در صورت عدم وجود
    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    expression TEXT NOT NULL,
                    result TEXT NOT NULL,
                    angle_mode TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    # [Date: 2026-11-16] - ثبت یک رکورد جدید در تاریخچه
    def add_record(self, expression: str, result: str, angle_mode: str) -> int:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO history (expression, result, angle_mode, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (expression, result, angle_mode, timestamp),
            )
            conn.commit()
            return int(cursor.lastrowid or 0)

    # [Date: 2026-11-16] - خواندن تمام رکوردهای تاریخچه از جدیدترین به قدیمی‌ترین
    def get_all_records(self, limit: int = 200) -> list[dict[str, str | int]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT id, expression, result, angle_mode, created_at
                FROM history
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    # [Date: 2026-11-16] - حذف یک رکورد خاص با شناسه
    def delete_record(self, record_id: int) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM history WHERE id = ?", (record_id,))
            conn.commit()

    # [Date: 2026-11-16] - پاک‌سازی کامل تمام تاریخچه
    def clear_all(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM history")
            conn.commit()

    # [Date: 2026-11-16] - خروجی گرفتن تاریخچه به فرمت CSV (سازگار با اکسل با utf-8-sig)
    def export_to_csv(self, file_path: Path) -> int:
        records = self.get_all_records(limit=10000)
        with open(file_path, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["شناسه", "عبارت ریاضی", "نتیجه", "حالت زاویه", "زمان ثبت"])
            for item in records:
                writer.writerow(
                    [
                        item["id"],
                        item["expression"],
                        item["result"],
                        item["angle_mode"],
                        item["created_at"],
                    ]
                )
        return len(records)

    # [Date: 2026-11-16] - خروجی گرفتن تاریخچه به فرمت JSON
    def export_to_json(self, file_path: Path) -> int:
        records = self.get_all_records(limit=10000)
        with open(file_path, mode="w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        return len(records)


# [Date: 2026-11-16] - تعریف پالت‌های رنگی تم تیره (پیش‌فرض) و تم روشن
THEMES: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "#111827",
        "panel": "#1F2937",
        "display_bg": "#0B1220",
        "text": "#F9FAFB",
        "muted": "#9CA3AF",
        "btn_num": "#374151",
        "btn_num_hover": "#4B5563",
        "btn_sci": "#1E293B",
        "btn_sci_hover": "#334155",
        "btn_op": "#2563EB",
        "btn_op_hover": "#1D4ED8",
        "btn_eq": "#10B981",
        "btn_eq_hover": "#059669",
        "btn_clear": "#DC2626",
        "btn_clear_hover": "#B91C1C",
        "border": "#374151",
        "accent": "#38BDF8",
        "error": "#F87171",
        "list_select": "#2563EB",
    },
    "light": {
        "bg": "#F3F4F6",
        "panel": "#FFFFFF",
        "display_bg": "#E5E7EB",
        "text": "#111827",
        "muted": "#4B5563",
        "btn_num": "#FFFFFF",
        "btn_num_hover": "#E5E7EB",
        "btn_sci": "#E2E8F0",
        "btn_sci_hover": "#CBD5E1",
        "btn_op": "#2563EB",
        "btn_op_hover": "#1D4ED8",
        "btn_eq": "#059669",
        "btn_eq_hover": "#047857",
        "btn_clear": "#DC2626",
        "btn_clear_hover": "#B91C1C",
        "border": "#D1D5DB",
        "accent": "#0284C7",
        "error": "#DC2626",
        "list_select": "#2563EB",
    },
}


# [Date: 2026-11-16] - کلاس اصلی رابط کاربری گرافیکی با tkinter
class CalculatorApp:
    """رابط کاربری گرافیکی ماشین‌حساب علمی آفلاین با پشتیبانی از تاریخچه و کیبورد."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("ماشین‌حساب علمی آفلاین (پایتون ۳.۱۳)")
        self.root.geometry("960x640")
        self.root.minsize(820, 560)

        # مقداردهی موتور ریاضی و پایگاه‌داده
        self.engine = SafeMathEngine()
        self.db = HistoryDatabase()

        # وضعیت‌های برنامه
        self.current_theme_name: str = "dark"
        self.memory_value: float = 0.0
        self.has_memory: bool = False
        self.just_evaluated: bool = False
        self.history_records_cache: list[dict[str, str | int]] = []
        self.themed_buttons: list[tuple[tk.Button, str]] = []

        # متغیرهای متصل به رابط کاربری
        self.expr_var = tk.StringVar(value="")
        self.preview_var = tk.StringVar(value="آماده محاسبه")
        self.status_var = tk.StringVar(value="")

        # ساخت اجزای پنجره، اعمال تم، اتصال کیبورد و بارگذاری تاریخچه
        self._build_ui()
        self._apply_theme()
        self._bind_keyboard()
        self._update_status_bar()
        self._refresh_history_list()

        # تغییر متغیر ورودی را برای پیش‌نمایش زنده دنبال می‌کنیم
        self.expr_var.trace_add("write", self._on_expression_change)
        self.display_entry.focus_set()

    # [Date: 2026-11-16] - ساخت ساختار کامل ویجت‌های رابط کاربری
    def _build_ui(self) -> None:
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=3)
        self.root.grid_columnconfigure(1, weight=2)

        # --- نوار بالایی (هدر و تنظیمات) ---
        self.header_frame = tk.Frame(self.root, padx=14, pady=10)
        self.header_frame.grid(row=0, column=0, columnspan=2, sticky="ew")

        self.title_label = tk.Label(
            self.header_frame,
            text="ماشین‌حساب علمی آفلاین (SQLite + AST)",
            font=("Tahoma", 13, "bold"),
        )
        self.title_label.pack(side="right")

        self.theme_btn = tk.Button(
            self.header_frame,
            text="تغییر به تم روشن",
            command=self.toggle_theme,
            font=("Tahoma", 9, "bold"),
            padx=10,
            pady=4,
            relief="flat",
            cursor="hand2",
        )
        self.theme_btn.pack(side="left", padx=(0, 8))

        self.angle_btn = tk.Button(
            self.header_frame,
            text="حالت زاویه: درجه (DEG)",
            command=self.toggle_angle_mode,
            font=("Tahoma", 9, "bold"),
            padx=10,
            pady=4,
            relief="flat",
            cursor="hand2",
        )
        self.angle_btn.pack(side="left", padx=(0, 8))

        # --- ستون اصلی ماشین‌حساب (چپ) ---
        self.calc_frame = tk.Frame(self.root, padx=12, pady=8)
        self.calc_frame.grid(row=1, column=0, sticky="nsew")
        self.calc_frame.grid_rowconfigure(2, weight=1)
        self.calc_frame.grid_columnconfigure(0, weight=1)

        # ناحیه نمایشگر
        self.display_frame = tk.Frame(self.calc_frame, padx=12, pady=10)
        self.display_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        self.status_label = tk.Label(
            self.display_frame,
            textvariable=self.status_var,
            font=("Tahoma", 9),
            anchor="w",
        )
        self.status_label.pack(fill="x", pady=(0, 4))

        self.preview_label = tk.Label(
            self.display_frame,
            textvariable=self.preview_var,
            font=("Tahoma", 11),
            anchor="e",
        )
        self.preview_label.pack(fill="x", pady=(0, 4))

        self.display_entry = tk.Entry(
            self.display_frame,
            textvariable=self.expr_var,
            font=("Consolas", 22, "bold"),
            justify="right",
            relief="flat",
            bd=4,
        )
        self.display_entry.pack(fill="x", ipady=8)

        # ردیف دکمه‌های حافظه (MC, MR, M+, M-, MS, Ans)
        self.memory_frame = tk.Frame(self.calc_frame)
        self.memory_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        mem_buttons = [
            ("MC", self.memory_clear),
            ("MR", self.memory_recall),
            ("M+", self.memory_add),
            ("M-", self.memory_subtract),
            ("MS", self.memory_store),
            ("Ans", lambda: self.insert_token("ans")),
        ]
        for idx, (label, cmd) in enumerate(mem_buttons):
            self.memory_frame.grid_columnconfigure(idx, weight=1)
            btn = self._create_calc_button(self.memory_frame, label, cmd, "sci", font_size=10)
            btn.grid(row=0, column=idx, sticky="ew", padx=3)

        # صفحه‌کلید علمی + استاندارد
        self.keypad_frame = tk.Frame(self.calc_frame)
        self.keypad_frame.grid(row=2, column=0, sticky="nsew")

        # تعریف چیدمان دکمه‌ها: (برچسب، نوع رنگ، مقدار یا عملیات)
        button_rows: list[list[tuple[str, str, Callable[[], None]]]] = [
            [
                ("sin", "sci", lambda: self.insert_token("sin(")),
                ("cos", "sci", lambda: self.insert_token("cos(")),
                ("tan", "sci", lambda: self.insert_token("tan(")),
                ("(", "sci", lambda: self.insert_token("(")),
                (")", "sci", lambda: self.insert_token(")")),
                ("C", "clear", self.clear_all),
                ("⌫", "clear", self.backspace),
            ],
            [
                ("asin", "sci", lambda: self.insert_token("asin(")),
                ("acos", "sci", lambda: self.insert_token("acos(")),
                ("atan", "sci", lambda: self.insert_token("atan(")),
                ("7", "num", lambda: self.insert_token("7")),
                ("8", "num", lambda: self.insert_token("8")),
                ("9", "num", lambda: self.insert_token("9")),
                ("÷", "op", lambda: self.insert_token("/")),
            ],
            [
                ("√x", "sci", lambda: self.insert_token("sqrt(")),
                ("∛x", "sci", lambda: self.insert_token("cbrt(")),
                ("x²", "sci", lambda: self.insert_token("^2")),
                ("4", "num", lambda: self.insert_token("4")),
                ("5", "num", lambda: self.insert_token("5")),
                ("6", "num", lambda: self.insert_token("6")),
                ("×", "op", lambda: self.insert_token("*")),
            ],
            [
                ("log", "sci", lambda: self.insert_token("log(")),
                ("ln", "sci", lambda: self.insert_token("ln(")),
                ("xʸ", "sci", lambda: self.insert_token("^")),
                ("1", "num", lambda: self.insert_token("1")),
                ("2", "num", lambda: self.insert_token("2")),
                ("3", "num", lambda: self.insert_token("3")),
                ("−", "op", lambda: self.insert_token("-")),
            ],
            [
                ("π", "sci", lambda: self.insert_token("π")),
                ("e", "sci", lambda: self.insert_token("e")),
                ("n!", "sci", lambda: self.insert_token("!")),
                ("±", "num", self.toggle_sign),
                ("0", "num", lambda: self.insert_token("0")),
                (".", "num", lambda: self.insert_token(".")),
                ("+", "op", lambda: self.insert_token("+")),
            ],
            [
                ("10ˣ", "sci", lambda: self.insert_token("10^")),
                ("|x|", "sci", lambda: self.insert_token("abs(")),
                ("mod", "sci", lambda: self.insert_token("mod(")),
                (",", "sci", lambda: self.insert_token(",")),
                ("%", "sci", lambda: self.insert_token("%")),
                ("=", "eq", self.calculate),
            ],
        ]

        for r_idx, row in enumerate(button_rows):
            self.keypad_frame.grid_rowconfigure(r_idx, weight=1)
            for c_idx, (text, role, command) in enumerate(row):
                self.keypad_frame.grid_columnconfigure(c_idx, weight=1)
                col_span = 2 if (r_idx == 5 and text == "=") else 1
                btn = self._create_calc_button(self.keypad_frame, text, command, role)
                btn.grid(
                    row=r_idx,
                    column=c_idx,
                    columnspan=col_span,
                    sticky="nsew",
                    padx=3,
                    pady=3,
                )

        # --- ستون تاریخچه محاسبات (راست) ---
        self.history_frame = tk.Frame(self.root, padx=12, pady=8)
        self.history_frame.grid(row=1, column=1, sticky="nsew")
        self.history_frame.grid_rowconfigure(1, weight=1)
        self.history_frame.grid_columnconfigure(0, weight=1)

        self.history_header_label = tk.Label(
            self.history_frame,
            text="تاریخچه محاسبات (برای استفاده کلیک کنید)",
            font=("Tahoma", 11, "bold"),
            anchor="e",
        )
        self.history_header_label.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        # لیست با نوار پیمایش عمودی
        list_container = tk.Frame(self.history_frame)
        list_container.grid(row=1, column=0, sticky="nsew")
        list_container.grid_rowconfigure(0, weight=1)
        list_container.grid_columnconfigure(0, weight=1)

        self.history_listbox = tk.Listbox(
            list_container,
            font=("Consolas", 11),
            activestyle="none",
            relief="flat",
            bd=6,
        )
        self.history_listbox.grid(row=0, column=0, sticky="nsew")
        self.history_listbox.bind("<Double-Button-1>", self._on_history_select)
        self.history_listbox.bind("<<ListboxSelect>>", self._on_history_preview)

        scrollbar = ttk.Scrollbar(
            list_container,
            orient="vertical",
            command=self.history_listbox.yview,
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.history_listbox.configure(yscrollcommand=scrollbar.set)

        # دکمه‌های مدیریت تاریخچه
        self.history_actions = tk.Frame(self.history_frame)
        self.history_actions.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        for i in range(4):
            self.history_actions.grid_columnconfigure(i, weight=1)

        action_items = [
            ("پاک کردن همه", "clear", self.clear_history),
            ("حذف انتخاب", "sci", self.delete_selected_history),
            ("خروجی JSON", "sci", self.export_json),
            ("خروجی CSV", "sci", self.export_csv),
        ]
        for idx, (label, role, cmd) in enumerate(action_items):
            btn = self._create_calc_button(self.history_actions, label, cmd, role, font_size=9)
            btn.grid(row=0, column=idx, sticky="ew", padx=2)

    # [Date: 2026-11-16] - ساخت یک دکمه با قابلیت تغییر رنگ خودکار بر اساس تم
    def _create_calc_button(
        self,
        parent: tk.Widget,
        text: str,
        command: Callable[[], None],
        role: str,
        font_size: int = 12,
    ) -> tk.Button:
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            font=("Tahoma", font_size, "bold"),
            relief="flat",
            bd=0,
            cursor="hand2",
            pady=6,
        )
        self.themed_buttons.append((btn, role))
        return btn

    # [Date: 2026-11-16] - اعمال رنگ‌های تم انتخاب‌شده به کل پنجره و ویجت‌ها
    def _apply_theme(self) -> None:
        t = THEMES[self.current_theme_name]
        self.root.configure(bg=t["bg"])
        self.header_frame.configure(bg=t["panel"])
        self.title_label.configure(bg=t["panel"], fg=t["text"])

        self.theme_btn.configure(
            bg=t["btn_sci"],
            fg=t["text"],
            activebackground=t["btn_sci_hover"],
            activeforeground=t["text"],
            text="تغییر به تم روشن" if self.current_theme_name == "dark" else "تغییر به تم تیره",
        )
        self.angle_btn.configure(
            bg=t["btn_op"],
            fg="#FFFFFF",
            activebackground=t["btn_op_hover"],
            activeforeground="#FFFFFF",
        )

        self.calc_frame.configure(bg=t["bg"])
        self.display_frame.configure(bg=t["display_bg"])
        self.status_label.configure(bg=t["display_bg"], fg=t["accent"])
        self.preview_label.configure(bg=t["display_bg"], fg=t["muted"])
        self.display_entry.configure(
            bg=t["display_bg"],
            fg=t["text"],
            insertbackground=t["accent"],
        )

        self.memory_frame.configure(bg=t["bg"])
        self.keypad_frame.configure(bg=t["bg"])
        self.history_frame.configure(bg=t["bg"])
        self.history_actions.configure(bg=t["bg"])
        self.history_header_label.configure(bg=t["bg"], fg=t["text"])

        self.history_listbox.configure(
            bg=t["panel"],
            fg=t["text"],
            selectbackground=t["list_select"],
            selectforeground="#FFFFFF",
        )

        for btn, role in self.themed_buttons:
            if role == "num":
                bg, hover, fg = t["btn_num"], t["btn_num_hover"], t["text"]
            elif role == "sci":
                bg, hover, fg = t["btn_sci"], t["btn_sci_hover"], t["text"]
            elif role == "op":
                bg, hover, fg = t["btn_op"], t["btn_op_hover"], "#FFFFFF"
            elif role == "eq":
                bg, hover, fg = t["btn_eq"], t["btn_eq_hover"], "#FFFFFF"
            else:
                bg, hover, fg = t["btn_clear"], t["btn_clear_hover"], "#FFFFFF"

            btn.configure(
                bg=bg,
                fg=fg,
                activebackground=hover,
                activeforeground=fg,
            )

    # [Date: 2026-11-16] - اتصال کلیدهای صفحه‌کلید بدون تداخل با تایپ مستقیم در فیلد ورودی
    def _bind_keyboard(self) -> None:
        self.root.bind("<Return>", lambda _e: self.calculate())
        self.root.bind("<KP_Enter>", lambda _e: self.calculate())
        self.root.bind("<Escape>", lambda _e: self.clear_all())
        self.root.bind("<KeyPress>", self._on_global_keypress)

    # [Date: 2026-11-16] - هدایت کلیدهای کیبورد وقتی فوکوس روی دکمه‌ها یا لیست تاریخچه است
    def _on_global_keypress(self, event: Any) -> None:
        if event.widget is self.display_entry:
            return
        if event.keysym == "BackSpace":
            self.backspace()
            return
        char = event.char
        if char and char in "0123456789.+-*/()%^,":
            self.insert_token(char)

    # [Date: 2026-11-16] - به‌روزرسانی نوار وضعیت بالای نمایشگر
    def _update_status_bar(self) -> None:
        mode_fa = "درجه (DEG)" if self.engine.angle_mode == "DEG" else "رادیان (RAD)"
        mem_text = (
            SafeMathEngine.format_number(self.memory_value)
            if self.has_memory
            else "خالی"
        )
        ans_text = SafeMathEngine.format_number(self.engine.last_answer)
        self.status_var.set(f"زاویه: {mode_fa}   |   حافظه (M): {mem_text}   |   Ans: {ans_text}")

    # [Date: 2026-11-16] - پیش‌نمایش زنده نتیجه هنگام تایپ کردن کاربر
    def _on_expression_change(self, *_args: object) -> None:
        expr = self.expr_var.get().strip()
        t = THEMES[self.current_theme_name]
        if not expr:
            self.preview_label.configure(fg=t["muted"])
            self.preview_var.set("آماده محاسبه")
            return
        try:
            _, formatted = self.engine.evaluate(expr, update_ans=False)
            self.preview_label.configure(fg=t["accent"])
            self.preview_var.set(f"= {formatted}")
        except CalculatorError:
            self.preview_label.configure(fg=t["muted"])
            self.preview_var.set("...")

    # [Date: 2026-11-16] - درج توکن یا عدد در موقعیت مکان‌نمای ورودی
    def insert_token(self, token: str) -> None:
        if self.just_evaluated:
            # اگر بلافاصله بعد از '=' عملگر وارد شود، ادامه همان پاسخ را می‌نویسیم
            if token not in {"+", "-", "*", "/", "^", "%", "!"}:
                self.expr_var.set("")
            self.just_evaluated = False

        cursor_pos = self.display_entry.index(tk.INSERT)
        current_text = self.expr_var.get()
        updated = current_text[:cursor_pos] + token + current_text[cursor_pos:]
        self.expr_var.set(updated)
        self.display_entry.icursor(cursor_pos + len(token))
        self.display_entry.focus_set()

    # [Date: 2026-11-16] - پاک‌کردن کامل عبارت جاری
    def clear_all(self) -> None:
        self.expr_var.set("")
        self.just_evaluated = False
        self.preview_var.set("آماده محاسبه")
        self.display_entry.focus_set()

    # [Date: 2026-11-16] - حذف یک کاراکتر قبل از مکان‌نما
    def backspace(self) -> None:
        self.just_evaluated = False
        pos = self.display_entry.index(tk.INSERT)
        text = self.expr_var.get()
        if pos > 0 and text:
            self.expr_var.set(text[: pos - 1] + text[pos:])
            self.display_entry.icursor(pos - 1)
        self.display_entry.focus_set()

    # [Date: 2026-11-16] - تغییر علامت عبارت یا عدد جاری (±)
    def toggle_sign(self) -> None:
        text = self.expr_var.get().strip()
        if not text:
            self.insert_token("-")
            return
        if text.startswith("-(") and text.endswith(")"):
            self.expr_var.set(text[2:-1])
        elif text.startswith("-"):
            self.expr_var.set(text[1:])
        else:
            self.expr_var.set(f"-({text})")
        self.display_entry.icursor(tk.END)
        self.display_entry.focus_set()

    # [Date: 2026-11-16] - اجرای محاسبه نهایی، ثبت در پایگاه‌داده SQLite و نمایش نتیجه
    def calculate(self) -> None:
        expression = self.expr_var.get().strip()
        if not expression:
            return
        t = THEMES[self.current_theme_name]
        try:
            _, formatted = self.engine.evaluate(expression, update_ans=True)
            self.db.add_record(expression, formatted, self.engine.angle_mode)
            self.preview_label.configure(fg=t["accent"])
            self.preview_var.set(f"{expression} = {formatted}")
            self.expr_var.set(formatted)
            self.just_evaluated = True
            self.display_entry.icursor(tk.END)
            self._update_status_bar()
            self._refresh_history_list()
        except CalculatorError as err:
            self.preview_label.configure(fg=t["error"])
            self.preview_var.set(f"خطا: {err}")
        self.display_entry.focus_set()

    # [Date: 2026-11-16] - تغییر حالت زاویه بین درجه (DEG) و رادیان (RAD)
    def toggle_angle_mode(self) -> None:
        if self.engine.angle_mode == "DEG":
            self.engine.angle_mode = "RAD"
            self.angle_btn.configure(text="حالت زاویه: رادیان (RAD)")
        else:
            self.engine.angle_mode = "DEG"
            self.angle_btn.configure(text="حالت زاویه: درجه (DEG)")
        self._update_status_bar()
        self._on_expression_change()
        self.display_entry.focus_set()

    # [Date: 2026-11-16] - جابجایی بین تم تیره و تم روشن
    def toggle_theme(self) -> None:
        self.current_theme_name = "light" if self.current_theme_name == "dark" else "dark"
        self._apply_theme()
        self._on_expression_change()
        self.display_entry.focus_set()

    # [Date: 2026-11-16] - عملیات حافظه (MC, MR, M+, M-, MS)
    def _current_or_eval_number(self) -> float | None:
        expr = self.expr_var.get().strip()
        if not expr:
            return self.engine.last_answer
        try:
            val, _ = self.engine.evaluate(expr, update_ans=False)
            return val
        except CalculatorError as err:
            self.preview_label.configure(fg=THEMES[self.current_theme_name]["error"])
            self.preview_var.set(f"خطا: {err}")
            return None

    def memory_clear(self) -> None:
        self.memory_value = 0.0
        self.has_memory = False
        self._update_status_bar()
        self.display_entry.focus_set()

    def memory_recall(self) -> None:
        if self.has_memory:
            self.insert_token(SafeMathEngine.format_number(self.memory_value))
        self.display_entry.focus_set()

    def memory_store(self) -> None:
        val = self._current_or_eval_number()
        if val is not None:
            self.memory_value = val
            self.has_memory = True
            self._update_status_bar()
        self.display_entry.focus_set()

    def memory_add(self) -> None:
        val = self._current_or_eval_number()
        if val is not None:
            self.memory_value += val
            self.has_memory = True
            self._update_status_bar()
        self.display_entry.focus_set()

    def memory_subtract(self) -> None:
        val = self._current_or_eval_number()
        if val is not None:
            self.memory_value -= val
            self.has_memory = True
            self._update_status_bar()
        self.display_entry.focus_set()

    # [Date: 2026-11-16] - بارگذاری و نمایش تاریخچه از پایگاه‌داده SQLite
    def _refresh_history_list(self) -> None:
        self.history_records_cache = self.db.get_all_records()
        self.history_listbox.delete(0, tk.END)
        for item in self.history_records_cache:
            line = f"[{item['angle_mode']}] {item['expression']} = {item['result']}"
            self.history_listbox.insert(tk.END, line)

    # [Date: 2026-11-16] - پیش‌نمایش زمان ثبت هنگام انتخاب یک مورد از تاریخچه
    def _on_history_preview(self, _event: Any) -> None:
        selection = self.history_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if 0 <= idx < len(self.history_records_cache):
            item = self.history_records_cache[idx]
            self.preview_var.set(f"ثبت شده در: {item['created_at']}")

    # [Date: 2026-11-16] - بازگرداندن عبارت انتخاب‌شده از تاریخچه به نمایشگر با دبل‌کلیک
    def _on_history_select(self, _event: Any) -> None:
        selection = self.history_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if 0 <= idx < len(self.history_records_cache):
            item = self.history_records_cache[idx]
            self.expr_var.set(str(item["expression"]))
            self.just_evaluated = False
            self.display_entry.icursor(tk.END)
            self.display_entry.focus_set()

    # [Date: 2026-11-16] - حذف رکورد انتخاب‌شده از تاریخچه
    def delete_selected_history(self) -> None:
        selection = self.history_listbox.curselection()
        if not selection:
            messagebox.showinfo("اطلاع", "لطفاً ابتدا یک مورد از تاریخچه را انتخاب کنید.")
            return
        idx = selection[0]
        record_id = int(self.history_records_cache[idx]["id"])
        self.db.delete_record(record_id)
        self._refresh_history_list()

    # [Date: 2026-11-16] - پاک کردن کل تاریخچه با تاییدیه کاربر
    def clear_history(self) -> None:
        if not self.history_records_cache:
            return
        confirm = messagebox.askyesno("تایید حذف", "آیا از پاک کردن تمام تاریخچه مطمئن هستید؟")
        if confirm:
            self.db.clear_all()
            self._refresh_history_list()

    # [Date: 2026-11-16] - خروجی گرفتن فایل CSV در مسیر انتخابی کاربر
    def export_csv(self) -> None:
        file_path = filedialog.asksaveasfilename(
            title="ذخیره تاریخچه در فایل CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
        )
        if not file_path:
            return
        count = self.db.export_to_csv(Path(file_path))
        messagebox.showinfo("موفق", f"تعداد {count} رکورد با موفقیت در فایل CSV ذخیره شد.")

    # [Date: 2026-11-16] - خروجی گرفتن فایل JSON در مسیر انتخابی کاربر
    def export_json(self) -> None:
        file_path = filedialog.asksaveasfilename(
            title="ذخیره تاریخچه در فایل JSON",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
        )
        if not file_path:
            return
        count = self.db.export_to_json(Path(file_path))
        messagebox.showinfo("موفق", f"تعداد {count} رکورد با موفقیت در فایل JSON ذخیره شد.")


# [Date: 2026-11-16] - نقطه شروع اجرای برنامه دسکتاپ
def main() -> None:
    if not HAS_TKINTER:
        print(
            "خطا: کتابخانه استاندارد tkinter در این سیستم نصب نیست.\n"
            "در لینوکس (اوبونتو/دبیان) با دستور زیر آن را نصب کنید:\n"
            "sudo apt-get install python3-tk"
        )
        return
    root = tk.Tk()
    CalculatorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
