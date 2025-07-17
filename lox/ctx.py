import math
import time
from dataclasses import field, dataclass
from typing import TYPE_CHECKING, Iterator, Optional, TypeVar, cast

T = TypeVar("T")
ScopeDict = dict[str, "Value"]

def read_number(msg: str) -> float:
    try:
        return float(input(msg))
    except ValueError:
        print("Digite um número válido!")
        return read_number(msg)

class _Builtins(dict):
    # Algumas funções prontas que podem ser usadas direto nos programas
    BUILTINS: dict[str, "Value"] = {
        "sqrt": math.sqrt,
        "clock": time.time,
        "max": max,
        "read_number": read_number,
        "is_even": lambda n: n % 2 == 0.0,
    }

    def __init__(self):
        super().__init__(self.BUILTINS)

    def __repr__(self) -> str:
        return "BUILTINS"

    def __str__(self) -> str:
        return self.__repr__()

BUILTINS = _Builtins()

@dataclass
class Ctx:
    """
    Representa o contexto onde variáveis são guardadas.
    Pode ter um "pai", formando uma cadeia de escopos.
    """
    scope: ScopeDict = field(default_factory=dict)
    parent: Optional["Ctx"] = field(default_factory=lambda: Ctx(BUILTINS, None))

    @classmethod
    def from_dict(cls, env: ScopeDict) -> "Ctx":
        return cls(env, Ctx(BUILTINS, None))

    def __getitem__(self, name: str) -> "Value":
        if name in self.scope:
            return self.scope[name]
        elif self.parent is not None:
            return self.parent[name]
        raise KeyError(f"Variável '{name}' não encontrada.")

    def __setitem__(self, name: str, value: "Value") -> None:
        if name in self.scope:
            self.scope[name] = value
        elif self.parent is not None:
            self.parent[name] = value
        else:
            raise KeyError(f"Variável '{name}' não encontrada.")

    def __contains__(self, name: str) -> bool:
        return name in self.scope or (self.parent and name in self.parent)

    def var_def(self, name: str, value: "Value") -> None:
        """
        Declara uma nova variável neste escopo.
        """
        if name in self.scope and not self.is_global():
            raise KeyError(f"Variável '{name}' já declarada neste escopo.")
        self.scope[name] = value

    def assign(self, key: str, value: "Value"):
        """
        Atualiza o valor da variável mais próxima com o nome dado.
        """
        ctx = self
        while ctx is not None:
            if key in ctx.scope:
                ctx.scope[key] = value
                return
            ctx = ctx.parent
        raise KeyError(f"Variável '{key}' não encontrada.")

    def to_dict(self) -> ScopeDict:
        """
        Retorna todos os escopos fundidos num só dicionário.
        """
        if self.parent is None:
            return self.scope.copy()
        return {**self.parent.to_dict(), **self.scope}

    def iter_scopes(self, reverse: bool = False) -> Iterator[ScopeDict]:
        """
        Itera sobre os ambientes do contexto, começando pelo mais interno.
        """
        if reverse:
            if self.parent is not None:
                yield from self.parent.iter_scopes(reverse=True)
            yield self.scope
        else:
            yield self.scope
            if self.parent is not None:
                yield from self.parent.iter_scopes()

    def pretty(self) -> str:
        """
        Representação do contexto como string.
        """

        lines: list[str] = []
        for i, scope in enumerate(self.iter_scopes(reverse=True)):
            lines.append(pretty_scope(scope, i))
        return "\n".join(reversed(lines))

    def pop(self) -> tuple[ScopeDict, "Ctx"]:
        """
        Remove o escopo mais interno e retorna o restante.
        """
        if self.parent is None:
            raise RuntimeError("Não é possível remover o escopo global.")
        return self.scope, self.parent

    def push(self, tos: ScopeDict) -> "Ctx":
        """
        Adiciona um novo escopo no topo.
        """
        return Ctx(tos, self)

    def is_global(self) -> bool:
        return self.parent is not None and self.parent.parent is None

class CtxAlt:
    """
    Uma versão alternativa de contexto. Usa uma pilha de dicionários.
    """
    def __init__(self, globals: dict | None = None):
        if globals is None:
            globals = {}
        self._stack = [BUILTINS, globals]

    @classmethod
    def from_dict(cls, env: dict[str, "Value"]) -> "CtxAlt":
        return cls(env)

    def __getitem__(self, key: str) -> "Value":
        for env in reversed(self._stack):
            if key in env:
                return env[key]
        raise KeyError(key)

    def __setitem__(self, key: str, value: "Value"):
        for env in reversed(self._stack):
            if key in env:
                env[key] = value
                return
        raise KeyError(key)

    def var_def(self, key: str, value: "Value"):
        """
        Declara uma nova variável no escopo atual.
        """
        self._stack[-1][key] = value

    def pop(self):
        """
        Remove o último escopo da pilha.
        """
        return self._stack.pop()

    def push(self, env: dict):
        """
        Adiciona um novo escopo ao topo da pilha.
        """
        self._stack.append(env)

def pretty_scope(env: ScopeDict, index: int) -> str:
    """
    Retorna uma string com as variáveis e valores de um escopo.
    """
    if not env:
        return f"{index:>2}: <empty>"
    items = (f"{k} = {v}" for k, v in sorted(env.items()))
    return f"{index:>2}: " + "; ".join(items)
