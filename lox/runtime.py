import builtins
from dataclasses import dataclass
from operator import neg
from typing import TYPE_CHECKING
from types import BuiltinFunctionType, FunctionType

from .ctx import Ctx

if TYPE_CHECKING:
    from .ast import Stmt, Value

__all__ = [
    "add",
    "eq",
    "ge",
    "gt",
    "le",
    "lt",
    "mul",
    "ne",
    "neg",
    "not_",
    "print",
    "show",
    "sub",
    "truthy",
    "truediv",
    "LoxClass",
    "LoxInstance",
]


#Classes principais


@dataclass
class LoxClass:
    """Representa uma classe Lox."""
    name: str
    methods: dict[str, "LoxFunction"]
    base: "LoxClass | None" = None

    def __call__(self, *args):
        """Permite instanciar objetos Lox chamando a classe."""
        instance = LoxInstance(self)
        try:
            initializer = self.get_method("init")
        except LoxError:
            if args:
                raise LoxError(f"Expected 0 arguments but got {len(args)}.")
            return instance
        bound_init = initializer.bind(instance)
        bound_init(*args)
        return instance

    def get_method(self, name: str) -> "LoxFunction":
        if name in self.methods:
            return self.methods[name]
        if self.base is not None:
            return self.base.get_method(name)
        raise LoxError(f"Método '{name}' não encontrado")

    def __str__(self) -> str:
        return self.name


class LoxInstance:
    """Instância de uma :class:`LoxClass`."""

    def __init__(self, cls: LoxClass):
        self.__cls = cls

    def __str__(self) -> str:
        return f"{self.__cls.name} instance"

    def __getattr__(self, attr: str):
        """Procura por métodos definidos na classe."""
        try:
            method = self.__cls.get_method(attr)
            return method.bind(self)
        except LoxError:
            raise AttributeError(attr)

    def init(self, *args):
        try:
            initializer = self.__cls.get_method("init")
        except LoxError:
            raise AttributeError("init")
        bound_init = initializer.bind(self)
        bound_init(*args)
        return self


@dataclass
class LoxFunction:
    """Representa uma função do Lox."""

    name: str
    params: list[str]
    body: list["Stmt"]
    ctx: Ctx

    def bind(self, obj: "Value") -> "LoxFunction":
        return LoxFunction(
            name=self.name,
            params=self.params,
            body=self.body,
            ctx=self.ctx.push({"this": obj}),
        )

    def call(self, args: list["Value"]):
        env = dict(zip(self.params, args, strict=True))
        ctx = self.ctx.push(env)
        try:
            for stmt in self.body:
                stmt.eval(ctx)
        except LoxReturn as e:
            return e.value
        finally:
            ctx.pop()

    def __call__(self, *args):
        return self.call(list(args))

    def __str__(self) -> str:
        return f"<fn {self.name}>"


class LoxReturn(Exception):
    """Exceção para retornar de uma função Lox."""

    def __init__(self, value):
        self.value = value
        super().__init__()


class LoxError(Exception):
    """Exceção para erros de execução Lox."""



#Utilidades e saída

nan = float("nan")
inf = float("inf")


def print(value: "Value"):
    """Imprime um valor lox."""
    builtins.print(show(value))


def show(value: "Value") -> str:
    """Converte valor lox para string."""
    if isinstance(value, LoxClass):
        return str(value)
    if isinstance(value, LoxInstance):
        return str(value)
    if value is None:
        return "nil"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, float):
        text = str(value)
        return text.removesuffix(".0")
    if isinstance(value, LoxFunction):
        return str(value)
    if isinstance(value, type):
        return value.__name__
    if isinstance(value, (FunctionType, BuiltinFunctionType)):
        return "<native fn>"
    return str(value)


def show_repr(value: "Value") -> str:
    """Mostra um valor lox, mas coloca aspas em strings."""
    if isinstance(value, str):
        return f'"{value}"'
    return show(value)


def truthy(value: "Value") -> bool:
    """Converte valor lox para booleano segundo a semântica do Lox."""
    return not (value is False or value is None)


def not_(value: "Value") -> bool:
    return not truthy(value)



#Operadores e utilitários internos


def _ensure_number(x: "Value") -> float:
    if not isinstance(x, float):
        raise LoxError("Operação requer números")
    return x


def add(a: "Value", b: "Value") -> "Value":
    if isinstance(a, float) and isinstance(b, float):
        return a + b
    if isinstance(a, str) and isinstance(b, str):
        return a + b
    raise LoxError("Operands must be two numbers or two strings")


def sub(a: "Value", b: "Value") -> float:
    return _ensure_number(a) - _ensure_number(b)


def mul(a: "Value", b: "Value") -> float:
    return _ensure_number(a) * _ensure_number(b)


def truediv(a: "Value", b: "Value") -> float:
    a = _ensure_number(a)
    b = _ensure_number(b)
    if b == 0:
        if a == 0:
            return nan
        return inf if a > 0 else -inf
    return a / b


def eq(a: "Value", b: "Value") -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, LoxFunction):
        return a is b
    return a == b


def ne(a: "Value", b: "Value") -> bool:
    return not eq(a, b)


def gt(a: "Value", b: "Value") -> bool:
    return _ensure_number(a) > _ensure_number(b)


def ge(a: "Value", b: "Value") -> bool:
    return _ensure_number(a) >= _ensure_number(b)


def lt(a: "Value", b: "Value") -> bool:
    return _ensure_number(a) < _ensure_number(b)


def le(a: "Value", b: "Value") -> bool:
    return _ensure_number(a) <= _ensure_number(b)
