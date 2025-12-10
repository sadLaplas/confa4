import sys
import argparse
import toml
from pathlib import Path
from lark import Lark, Transformer, Token
from lark.exceptions import LarkError
import re

grammar = r"""
    start: (const_decl | dict)*
    const_decl: "(" "def" NAME value ")"
    dict_entry: NAME "=" value
    dict: "{" dict_entry* "}"
    const_expr: "$[" expr_items "]"
    expr_items: (value | OPERATION)*
    value: simple_value | dict | const_expr | NAME
    simple_value: NUMBER | string
    string: "q" "(" string_content? ")"
    string_content: STRING_CONTENT
    NAME: /[_a-zA-Z]+/
    NUMBER: /-?(\d+|\d+\.\d*|\.\d+)([eE][-+]?\d+)?/
    OPERATION: "+" | "-" | "*" | "max" | "mod"
    STRING_CONTENT: /[^)]+/
    %import common.WS
    %ignore WS
"""


class ConfigTransformer(Transformer):
    def __init__(self):
        super().__init__()
        self.consts = {}
        self.result = {}

    def start(self, items):
        for item in items:
            if isinstance(item, dict):
                self.result.update(item)
        return self.result

    def dict_entry(self, items):
        key = str(items[0])
        val = items[1]
        return {key: val}

    def dict(self, items):
        res = {}
        if items:
            for i in items:
                if isinstance(i, dict):
                    res.update(i)
        return res

    def const_decl(self, items):
        if len(items) >= 2:
            name = str(items[0])
            val = items[1]
            self.consts[name] = val
        return None

    def const_expr(self, items):
        if items and items[0] is not None:
            return self._calc(items[0])
        return None

    def expr_items(self, items):
        return [i for i in items if i is not None]

    def _calc(self, items):
        stack = []
        for i in items:
            if isinstance(i, Token) and i.type == 'NAME':
                n = str(i)
                if n in self.consts:
                    stack.append(self.consts[n])
                else:
                    raise ValueError(f"Неизвестная константа или имя: {n}")

            elif isinstance(i, Token) and i.type == 'OPERATION':
                self._apply_op(str(i), stack)

            else:
                stack.append(i)

        if len(stack) != 1:
            raise ValueError(f"Ошибка вычисления выражения: стек не пуст или пуст {stack}")
        return stack[0]

    def _apply_op(self, op, stack):
        if op in {'+', '-', '*', 'max', 'mod'}:
            if len(stack) < 2:
                raise ValueError(f"Недостаточно аргументов для операции {op}")

            b = stack.pop()
            a = stack.pop()

            if op == '+':
                if isinstance(a, str) or isinstance(b, str):
                    stack.append(str(a) + str(b))
                else:
                    stack.append(a + b)
            elif op == '-':
                stack.append(a - b)
            elif op == '*':
                stack.append(a * b)
            elif op == 'max':
                stack.append(max(a, b))
            elif op == 'mod':
                if b == 0:
                    raise ValueError("Деление на ноль (mod)")
                stack.append(a % b)
        else:
            raise ValueError(f"Неизвестная операция: {op}")

    def value(self, items):
        val = items[0]
        if isinstance(val, Token) and val.type == 'NAME':
            name = str(val)
            if name in self.consts:
                return self.consts[name]
            raise ValueError(f"Использование необъявленной константа: {name}")
        return val

    def simple_value(self, items):
        return items[0]

    def string(self, items):
        if len(items) > 0 and items[0] is not None:
            return str(items[0])
        return ""

    def string_content(self, items):
        if items:
            return str(items[0])
        return None

    def NAME(self, token):
        return Token('NAME', str(token))

    def NUMBER(self, token):
        val = str(token)
        if '.' in val or 'e' in val.lower():
            return float(val)
        return int(val)

    def STRING_CONTENT(self, token):
        return str(token)

    def OPERATION(self, token):
        return Token('OPERATION', str(token))


class Converter:
    def __init__(self):
        self.trans = ConfigTransformer()
        self.parser = Lark(grammar, parser='lalr', transformer=self.trans)

    def parse_file(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = f.read()
            return self.parse_content(data)
        except FileNotFoundError:
            raise ValueError(f"Файл не найден: {path}")
        except IOError as e:
            raise ValueError(f"Ошибка чтения файла: {e}")

    def parse_content(self, text):
        text = re.sub(r'/#.*?#/', '', text, flags=re.DOTALL)
        try:
            res = self.parser.parse(text)
            return res if res is not None else {}
        except LarkError as e:
            raise ValueError(f"Синтаксическая ошибка: {e}")
        except ValueError as e:
            raise ValueError(f"Ошибка логики: {e}")

    def to_toml(self, cfg):
        return toml.dumps(cfg)


def main():
    parser = argparse.ArgumentParser(description='Конвертер учебного КЯ (Вариант 6) в TOML')
    parser.add_argument('-i', '--input', type=str, required=True, help='Путь к входному файлу')
    args = parser.parse_args()

    try:
        conv = Converter()
        cfg = conv.parse_file(Path(args.input))
        print(conv.to_toml(cfg))
        return 0
    except Exception as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())