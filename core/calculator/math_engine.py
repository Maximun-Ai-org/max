"""Calculadora integrada — evalúa expresiones matemáticas seguras."""
import math, re
from typing import Optional

class MathEngine:
    SAFE_NAMES = {
        "pi": math.pi, "e": math.e, "tau": math.tau,
        "sqrt": math.sqrt, "abs": abs, "round": round,
        "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "log": math.log, "log10": math.log10, "log2": math.log2,
        "floor": math.floor, "ceil": math.ceil, "pow": pow,
        "factorial": math.factorial, "gcd": math.gcd,
    }

    def evaluate(self, expression: str) -> Optional[str]:
        try:
            # Sanitize
            expr = expression.strip()
            expr = expr.replace("^", "**")
            expr = re.sub(r'[^0-9+\-*/().,%s]' % '|'.join(self.SAFE_NAMES.keys()), '', expr)
            
            result = eval(expr, {"__builtins__": {}}, self.SAFE_NAMES)
            return str(result)
        except Exception as e:
            return f"Error: {e}"

    def is_math(self, text: str) -> bool:
        text = text.lower().strip()
        math_keywords = ["calcula", "cuanto es", "cuánto es", "resultado de", "resolver"]
        return any(k in text for k in math_keywords) or bool(re.search(r'\d+\s*[+\-*/^]\s*\d+', text))
