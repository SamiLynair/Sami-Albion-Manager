"""Exact-decimal arithmetic for the personal sidebar calculator.

Deliberately independent of game data, HTTP, GUI and eval().
"""

from __future__ import annotations

from decimal import Decimal, DivisionByZero, InvalidOperation, localcontext


OPERATORS = {"+", "−", "×", "÷"}


class Calculator:
    def __init__(self):
        self.clear()

    def clear(self):
        self.entry = "0"
        self.stored: Decimal | None = None
        self.operator: str | None = None
        self.fresh = False
        self.error = False
        self.history = ""

    @property
    def display(self) -> str:
        return self.entry.replace(".", ",")

    def _set_number(self, value: Decimal):
        if not value.is_finite():
            self._error("Résultat invalide")
            return
        if value == 0:
            self.entry = "0"
            return
        # Avoid exponential notation in the small calculator display.
        with localcontext() as context:
            context.prec = 14
            rounded = +value
        self.entry = format(rounded, "f").rstrip("0").rstrip(".") if "." in format(rounded, "f") else format(rounded, "f")
        if len(self.entry) > 18:
            self._error("Nombre trop grand")

    def _error(self, message: str):
        self.entry = message
        self.error = True
        self.stored = None
        self.operator = None
        self.fresh = True
        self.history = ""

    def _calculate(self, left: Decimal, operator: str, right: Decimal) -> Decimal:
        with localcontext() as context:
            context.prec = 28
            if operator == "+":
                return left + right
            if operator == "−":
                return left - right
            if operator == "×":
                return left * right
            if operator == "÷":
                if right == 0:
                    raise DivisionByZero
                return left / right
            raise ValueError("Opérateur inconnu")

    def press(self, key: str):
        if key in ("AC", "C"):
            self.clear()
            return
        if self.error:
            self.clear()
            if key not in "0123456789,.":
                return
        if key in "0123456789" and len(key) == 1:
            if self.fresh or self.entry == "0":
                self.entry = key
            elif len(self.entry.replace("-", "").replace(".", "")) < 14:
                self.entry += key
            self.fresh = False
            return
        if key in (",", "."):
            if self.fresh:
                self.entry = "0"
                self.fresh = False
            if "." not in self.entry:
                self.entry += "."
            return
        if key == "←":
            if self.fresh:
                self.entry = "0"
                self.fresh = False
            else:
                self.entry = self.entry[:-1]
                if self.entry in ("", "-"):
                    self.entry = "0"
            return
        if key == "±":
            if self.entry != "0":
                self.entry = self.entry[1:] if self.entry.startswith("-") else "-" + self.entry
            return
        if key == "%":
            value = Decimal(self.entry)
            if self.stored is not None and self.operator in ("+", "−"):
                value = self.stored * value / Decimal(100)
            else:
                value /= Decimal(100)
            self._set_number(value)
            self.fresh = False
            return
        if key in OPERATORS:
            try:
                if self.operator and self.stored is not None and not self.fresh:
                    previous = self._calculate(self.stored, self.operator, Decimal(self.entry))
                    self._set_number(previous)
                    if self.error:
                        return
                self.stored = Decimal(self.entry)
                self.operator = key
                self.history = f"{self.display} {key}"
                self.fresh = True
            except (DivisionByZero, InvalidOperation):
                self._error("Division par zéro")
            return
        if key == "=" and self.operator and self.stored is not None:
            try:
                left = self.stored
                right = Decimal(self.entry)
                operator = self.operator
                answer = self._calculate(left, operator, right)
                self.history = f"{self._formatted(left)} {operator} {self._formatted(right)} ="
                self._set_number(answer)
                self.stored = None
                self.operator = None
                self.fresh = True
            except (DivisionByZero, InvalidOperation):
                self._error("Division par zéro")

    @staticmethod
    def _formatted(value: Decimal) -> str:
        return format(value, "f").replace(".", ",")
