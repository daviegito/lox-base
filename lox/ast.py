from abc import ABC
from dataclasses import dataclass
from typing import Callable, Iterable
from types import FunctionType
from bytecode import Bytecode, Instr, Compare, Label
from .ctx import Ctx
from .runtime import LoxFunction, LoxReturn, LoxClass, LoxError, truthy, show, LoxInstance
from .node import Node, Cursor
from .errors import SemanticError
from . import runtime as ops

KEYWORDS = {
    "and",
    "class",
    "else",
    "false",
    "for",
    "fun",
    "if",
    "nil",
    "or",
    "print",
    "return",
    "super",
    "this",
    "true",
    "var",
    "while",
}

""" Tipos de valores que podem aparecer durante a execução do programa"""
Value = bool | str | float | None

class Expr(Node, ABC):
    """
    Classe base para expressões.

    Expressões são nós que podem ser avaliados para produzir um valor.
    Também podem ser atribuídos a variáveis, passados como argumentos para
    funções, etc.
    """
    is_expr = True
    is_stmt = False

    def emit_instructions(self) -> Iterable[Instr | Label]:
        msg = f"{self.__class__.__name__}.emit_instructions() não implementado"
        raise NotImplementedError(msg)


class Stmt(Node, ABC):
    """
    Classe base para comandos.

    Comandos são associdos a construtos sintáticos que alteram o fluxo de
    execução do código ou declaram elementos como classes, funções, etc.
    """
    
    is_expr = False
    is_stmt = True

    def emit_instructions(self) -> Iterable[Instr | Label]:
        msg = f"{self.__class__.__name__}.emit_instructions() não implementado"
        raise NotImplementedError(msg)


@dataclass
class Program(Node):
    """
    Representa um programa.

    Um programa é uma lista de comandos.
    """

    stmts: list[Stmt]

    def eval(self, ctx: Ctx):
        for stmt in self.stmts:
            stmt.eval(ctx)


#
# EXPRESSÕES
#
@dataclass
class BinOp(Expr):
    """
    Uma operação infixa com dois operandos.

    Ex.: x + y, 2 * x, 3.14 > 3 and 3.14 < 4
    """

    left: Expr
    right: Expr
    ops: Callable[[Value, Value], Value]

    OP_TO_INSTR = {
        ops.add: Instr("BINARY_OP", 0),
        ops.mul: Instr("BINARY_OP", 1),
        ops.truediv: Instr("BINARY_OP", 5),
        ops.sub: Instr("BINARY_OP", 11),
        ops.gt: Instr("COMPARE_OP", Compare.GT),
        ops.lt: Instr("COMPARE_OP", Compare.LT),
        ops.ge: Instr("COMPARE_OP", Compare.GE),
        ops.le: Instr("COMPARE_OP", Compare.LE),
        ops.eq: Instr("COMPARE_OP", Compare.EQ),
        ops.ne: Instr("COMPARE_OP", Compare.NE),
    }

    def eval(self, ctx: Ctx):
        left_value = self.left.eval(ctx)
        right_value = self.right.eval(ctx)
        return self.ops(left_value, right_value)

    def emit_instructions(self):
        yield from self.left.emit_instructions()
        yield from self.right.emit_instructions()
        yield self.OP_TO_INSTR[self.ops]


@dataclass
class Var(Expr):
    """
    Uma variável no código

    Ex.: x, y, z
    """

    name: str

    def eval(self, ctx: Ctx):
        try:
            return ctx[self.name]
        except KeyError:
            raise NameError(f"variável {self.name} não existe!")

    #Pedido do exercício 19, de validações
    def validate_self(self, cursor: Cursor):
        if self.name in KEYWORDS:
            raise SemanticError("nome inválido", token=self.name)
        
    def emit_instructions(self):
        yield Instr("LOAD_FAST", self.name)

@dataclass
class Literal(Expr):
    """
    Representa valores literais no código, ex.: strings, booleanos,
    números, etc.

    Ex.: "Hello, world!", 42, 3.14, true, nil
    """

    value: Value

    def eval(self, ctx: Ctx):
        return self.value
    
    def emit_instructions(self):
        yield Instr("LOAD_CONST", self.value)


@dataclass
class And(Expr):
    """Operador lógico 'and' com curto-circuito."""

    left: Expr
    right: Expr

    def eval(self, ctx: Ctx):
        left_value = self.left.eval(ctx)
        if not truthy(left_value):
            return left_value
        return self.right.eval(ctx)

@dataclass
class Or(Expr):
    """Operador lógico 'or' com curto-circuito."""

    left: Expr
    right: Expr

    def eval(self, ctx: Ctx):
        left_value = self.left.eval(ctx)
        if truthy(left_value):
            return left_value
        return self.right.eval(ctx)

@dataclass
class Call(Expr):
    """
    Uma chamada de função.

    Ex.: fat(42)
    """

    callee: Expr
    params: list[Expr]

    def eval(self, ctx: Ctx):
        func = self.callee.eval(ctx)
        args = [p.eval(ctx) for p in self.params]
        if callable(func):
            return func(*args)
        raise TypeError(f"{func!r} não é chamável")
    
    def emit_instructions(self):
        expr = Var(self.name)
        yield from expr.emit_instructions()
        for param in self.params:
            yield from param.emit_instructions()
        yield Instr("CALL_FUNCTION", len(self.params))


@dataclass
class This(Expr):
    """
    Acesso ao `this`.

    Ex.: this
    """

    name: str = "this"

    #Exercício 23, sobre o this
    def eval(self, ctx: Ctx):
        try:
            return ctx[self.name]
        except KeyError:
            raise NameError("variável this não existe!")
        
    #Também pedido lá no 23
    def validate_self(self, cursor: Cursor):
        if not cursor.is_scoped_to(Class):
            raise SemanticError("uso inválido de 'this'", token="this")

@dataclass
class Super(Expr):
    """
    Acesso a method ou atributo da superclasse.

    Ex.: super.x
    """

    name: str

    #Pedido do exercício 25
    def eval(self, ctx: Ctx):
        method_name = self.name
        superclass = ctx["super"]
        this = ctx["this"]
        method = superclass.get_method(method_name)
        return method.bind(this)

    #Tbm pedido no ex. 25
    def validate_self(self, cursor: Cursor):
        if not cursor.is_scoped_to(Class):
            raise SemanticError("uso inválido de 'super'", token="super")

        cls = cursor.class_scope().node
        if cls.base is None:
            raise SemanticError("classe sem superclasse", token="super")
        
@dataclass
class Assign(Expr):
    """
    Atribuição de variável.

    Ex.: x = 42
    """
    name: str
    value: Expr

    def eval(self, ctx: Ctx):
        result = self.value.eval(ctx)
        ctx.assign(self.name, result)
        return result

    def emit_instructions(self):
        yield from self.value.emit_instructions()
        yield Instr("STORE_FAST", self.name)
        yield Instr("LOAD_FAST", self.name) 

@dataclass
class Getattr(Expr):
    """
    Acesso a atributo de um objeto.

    Ex.: x.y
    """

    obj: Expr
    attr: str

    def eval(self, ctx: Ctx):
        value = self.obj.eval(ctx)
        if (
            value is None
            or type(value) in (bool, float, str)
            or isinstance(value, (LoxClass, LoxFunction))
        ):
            raise LoxError("Somente instâncias têm propriedades.")
        return getattr(value, self.attr)
    
    def emit_instructions(self):
        yield from self.atom.emit_instructions()
        yield Instr("LOAD_ATTR", self.attr)

@dataclass
class Setattr(Expr):
    obj: Expr
    attr: str
    value: Expr

    def eval(self, ctx: Ctx):
        obj_value = self.obj.eval(ctx)
        if (
            obj_value is None
            or type(obj_value) in (bool, float, str)
            or isinstance(obj_value, (LoxClass, LoxFunction))
        ):
            raise LoxError("Somente instâncias têm campos")
        result = self.value.eval(ctx)
        setattr(obj_value, self.attr, result)
        return result
    
    def emit_instructions(self):
        yield from self.obj.emit_instructions()
        yield from self.value.emit_instructions()
        yield Instr("STORE_ATTR", self.attr)

@dataclass
class Print(Stmt):
    """
    Representa uma instrução de impressão.

    Ex.: print "Hello, world!";
    """
    expr: Expr
    
    #exercício 18, que mostra a impressão de valores conforme Lox
    def eval(self, ctx: Ctx):
        value = self.expr.eval(ctx)
        print(show(value))

    def emit_instructions(self):
        yield Instr("LOAD_GLOBAL", "print")
        yield from self.expr.emit_instructions()
        yield Instr("CALL_FUNCTION", 1)
        yield Instr("POP_TOP")

@dataclass
class Return(Stmt):
    value: Expr | None = None

    def eval(self, ctx: Ctx):
        result = None if self.value is None else self.value.eval(ctx)
        raise LoxReturn(result)

    #Exercício 26, de garantir que return só apareça em funções
    def validate_self(self, cursor: Cursor):
        if not cursor.is_scoped_to(Function):
            raise SemanticError("return fora da função", token="return")
        func_cursor = cursor.function_scope()
        if (
            self.value is not None
            and func_cursor.node.name == "init"
            and isinstance(func_cursor.parent().node, Class)
        ):
            raise SemanticError(
                "não pode retornar valor de inicializador init",
                token="return",
            )
        
    def emit_instructions(self):
        yield from self.expr.emit_instructions()
        yield Instr("RETURN_VALUE")

@dataclass
class VarDef(Stmt):
    name: str
    value: Expr

    def eval(self, ctx: Ctx):
        ctx.var_def(self.name, self.value.eval(ctx))

    #pedido no exercício 19, de validações
    def validate_self(self, cursor: Cursor):
        if self.name in KEYWORDS:
            raise SemanticError("nome inválido", token=self.name)
        if isinstance(cursor.parent().node, Program):
            return
        for desc in self.value.cursor().descendants():
            node = desc.node
            if isinstance(node, Var) and node.name == self.name:
                raise SemanticError(
                    "variável usada em seu próprio inicializador",
                    token=self.name,
                )

    def emit_instructions(self):
        yield from self.value.emit_instructions()
        yield Instr("STORE_FAST", self.name)

@dataclass
class If(Stmt):
    cond: Expr
    then_branch: Stmt
    else_branch: Stmt | None = None

    def eval(self, ctx: Ctx):
        if truthy(self.cond.eval(ctx)):
            self.then_branch.eval(ctx)
        elif self.else_branch is not None:
            self.else_branch.eval(ctx)

    def emit_instructions(self):
        """
          start
            |
           B01--.
            |   |
        .--B02  |
        |       |
        |  B03<-/
        |   |
        \->end
        """
        orelse = Label()
        end = Label()

        # B01 (bloco da condição)
        yield from self.cond.emit_instructions()
        yield Instr("POP_JUMP_IF_FALSE", orelse)

        # B02 (bloco then)
        yield from emit_stmt_instructions(self.then)
        yield Instr("JUMP_ABSOLUTE", end)

        # B03 (bloco else)
        yield orelse
        yield from emit_stmt_instructions(self.orelse)

        # bloco end
        yield end
@dataclass
class While(Stmt):
    cond: Expr
    body: Stmt

    def eval(self, ctx: Ctx):
        while truthy(self.cond.eval(ctx)):
            self.body.eval(ctx)

    def emit_instructions(self):
        """
          start
            |
        .->B01--.
        |   |   |
        \--B02  |
                |
           end<-/
        """
        start = Label()
        end = Label()

        # B01 (bloco da condição)
        yield start
        yield from self.cond.emit_instructions()
        yield Instr("POP_JUMP_IF_FALSE", end)

        # B02 (bloco de comandos)
        yield from emit_stmt_instructions(self.body)
        yield Instr("JUMP_ABSOLUTE", start)

        # bloco end
        yield end


@dataclass
class Block(Node):
    stmts: list[Stmt]

    def eval(self, ctx: Ctx):
        ctx = ctx.push({})
        try:
            for stmt in self.stmts:
                stmt.eval(ctx)
        finally:
            ctx.pop()

    def validate_self(self, cursor: Cursor):
        names: list[str] = [s.name for s in self.stmts if isinstance(s, VarDef)]
        seen: set[str] = set()
        for name in names:
            if name in seen:
                raise SemanticError("variável duplicada", token=name)
            seen.add(name)

    def emit_instructions(self):
        yield from emit_stmt_list(self.stmts)

@dataclass
class Function(Stmt):
    name: str
    params: list[str]
    body: Block

    def eval(self, ctx: Ctx):
        func = LoxFunction(
            name=self.name,
            params=self.params,
            body=self.body.stmts,
            ctx=ctx,
        )
        ctx.var_def(self.name, func)
        return func

    #pedido no exercício 19, sobre validações
    def validate_self(self, cursor: Cursor):
        for p in self.params:
            if p in KEYWORDS:
                raise SemanticError("nome inválido", token=p)

        if len(set(self.params)) != len(self.params):
            seen: set[str] = set()
            for p in self.params:
                if p in seen:
                    raise SemanticError("parâmetro duplicado", token=p)
                seen.add(p)

        body_vars = [s.name for s in self.body.stmts if isinstance(s, VarDef)]
        for name in body_vars:
            if name in self.params:
                raise SemanticError("nome inválido", token=name)
            
    def to_function(self) -> FunctionType:
        """
        Converte função Lox para uma função Python correspondente
        """
        instructions = list(emit_stmt_list(self.body))
        if not instructions or not is_return_instr(instructions[-1]):
            instructions.append(Instr("LOAD_CONST", None))  # type: ignore
            instructions.append(Instr("RETURN_VALUE"))

        code = Bytecode(instructions)
        code.name = self.name
        code.argcount = len(self.arg_names)
        code.argnames = self.arg_names

        pycode = code.to_code()
        return FunctionType(pycode, {"print": ops.print}, self.name)
            
    def emit_instructions(self):
        instructions = list(self.body.emit_instructions())
        if not instructions or not is_return_instr(instructions[-1]):
            instructions.append(Instr("LOAD_CONST", None))
            instructions.append(Instr("RETURN_VALUE"))

        code = Bytecode(instructions)
        code.name = self.name
        code.argcount = len(self.params)
        code.argnames = self.params

        pycode = code.to_code()
        yield Instr("LOAD_CONST", pycode)
        yield Instr("LOAD_CONST", self.name)
        yield Instr("MAKE_FUNCTION", 0)
        yield Instr("STORE_FAST", self.name)
@dataclass
class Class(Stmt):
    """
    Representa uma classe.

    Ex.: class B < A { ... }
    """
    name: str
    methods: list["Function"]
    base: str | None = None

    def validate_self(self, cursor: Cursor):
        if self.base == self.name:
            raise SemanticError(
                "classe nao pode herdar de si mesma",
                token=self.name,
            )

    #Exercício 20/21, só que com o 21 atualizado pra LoxClass
    def eval(self, ctx: Ctx):
        superclass = None
        if self.base is not None:
            try:
                value = ctx[self.base]
            except KeyError as e:
                raise NameError(f"classe {self.base} não existe") from e
            if not isinstance(value, LoxClass):
                raise LoxError("Superclasse inválida")
            superclass = value

        if superclass is None:
            method_ctx = ctx
        else:
            method_ctx = ctx.push({"super": superclass})

        methods: dict[str, LoxFunction] = {}
        for method in self.methods:
            method_impl = LoxFunction(
                name=method.name,
                params=method.params,
                body=method.body.stmts,
                ctx=method_ctx,
            )
            methods[method.name] = method_impl

        lox_class = LoxClass(self.name, methods, superclass)
        ctx.var_def(self.name, lox_class)
        return lox_class

@dataclass
class UnaryOp(Expr):
    op: Callable[[Value], Value]
    operand: Expr

    operations = {
        "-": "UNARY_NEGATIVE",
        "!": "UNARY_NOT",
    }

    def eval(self, ctx: Ctx):
        return self.op(self.operand.eval(ctx))
    
    def emit_instructions(self):
        yield from self.var.emit_instructions()
        yield Instr(self.operations[self.op])

def is_return_instr(obj: Instr | Label) -> bool:
    if isinstance(obj, Label):
        return False
    return obj.name == "RETURN_VALUE"


def emit_stmt_list(stmts: list[Stmt | Expr]) -> Iterable[Instr | Label]:
    for stmt in stmts:
        yield from emit_stmt_instructions(stmt)


def emit_stmt_instructions(stmt: Stmt | Expr):
    yield from stmt.emit_instructions()
    if stmt.is_expr:
        yield Instr("POP_TOP")
