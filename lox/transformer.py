"""
Implementa o transformador da árvore sintática que converte entre as representações

    lark.Tree -> lox.ast.Node.

A resolução de vários exercícios requer a modificação ou implementação de vários
métodos desta classe.
"""

from typing import Callable
from lark import Transformer, v_args

from . import runtime as op
from .ast import *
from .ast import UnaryOp


def op_handler(op: Callable):
    """
    Fábrica de métodos que lidam com operações binárias na árvore sintática.

    Recebe a função que implementa a operação em tempo de execução.
    """
    def method(self, left, right):
        return BinOp(left, right, op)

    return method


@v_args(inline=True)
class LoxTransformer(Transformer):

    #Literais e Variáveis
    def VAR(self, token):
        name = str(token)
        return Var(name)

    def NUMBER(self, token):
        num = float(token)
        return Literal(num)

    def STRING(self, token):
        text = str(token)[1:-1]
        return Literal(text)

    def NIL(self, _):
        return Literal(None)

    def BOOL(self, token):
        return Literal(token == "true")

    #Agrupamento
    def grouping(self, expr: Expr):
        setattr(expr, "_grouping", True)
        return expr

    #Operações Binárias e Unárias 
    add = op_handler(op.add)
    sub = op_handler(op.sub)
    mul = op_handler(op.mul)
    div = op_handler(op.truediv)

    gt = op_handler(op.gt)
    lt = op_handler(op.lt)
    ge = op_handler(op.ge)
    le = op_handler(op.le)
    eq = op_handler(op.eq)
    ne = op_handler(op.ne)

    def not_(self, value):
        return UnaryOp(op=op.not_, operand=value)

    def neg(self, value):
        return UnaryOp(op=lambda x: -x, operand=value)

    def and_(self, left: Expr, right: Expr):
        return And(left=left, right=right)

    def or_(self, left: Expr, right: Expr):
        return Or(left=left, right=right)

    #Atribuições
    def assign_expr(self, target: Expr, value: Expr):
        if isinstance(target, Var) and not getattr(target, "_grouping", False):
            return Assign(name=target.name, value=value)
        if isinstance(target, Getattr) and not getattr(target, "_grouping", False):
            return Setattr(obj=target.obj, attr=target.attr, value=value)
        raise SemanticError("atribuição inválida", token="=")

    #Acesso e chamadas
    def call(self, callee: Expr, *suffixes):
        for kind, value in suffixes:
            if kind == "args":
                callee = Call(callee, value)
            elif kind == "attr":
                callee = Getattr(callee, value)
        return callee

    def args(self, params: list):
        return ("args", params)

    def attr(self, name: Var):
        return ("attr", name.name)

    def getattr(self, obj, name):
        return Getattr(obj=obj, name=name.name)

    #Comandos básicos
    def expr_stmt(self, expr: Expr):
        return expr

    def print_cmd(self, expr):
        return Print(expr)

    def block(self, *stmts):
        return Block(list(stmts))

    def if_cmd(self, cond: Expr, then_branch: Stmt, else_branch: Stmt | None = None):
        return If(cond=cond, then_branch=then_branch, else_branch=else_branch)

    def while_cmd(self, cond: Expr, body: Stmt):
        return While(cond=cond, body=body)

    def var_decl(self, name: Var, value: Expr | None = None):
        if value is None:
            value = Literal(None)
        return VarDef(name=name.name, value=value)

    #Laço for
    def empty_init(self):
        return Literal(None)

    def maybe_cond(self, cond: Expr | None = None):
        if cond is None:
            return Literal(True)
        return cond

    def maybe_incr(self, incr: Expr | None = None):
        if incr is None:
            return Literal(None)
        return incr

    def for_init(self, stmt):
        return stmt

    def for_cmd(self, init: Stmt, cond: Expr, incr: Expr, body: Stmt):
        loop_body = Block([body, incr])
        while_stmt = While(cond=cond, body=loop_body)
        return Block([init, while_stmt])

    #Funções e métodos
    def function(self, name: Var, *rest):
        if len(rest) == 1:
            params: list[str] | None = None
            body = rest[0]
        else:
            params, body = rest  # type: ignore[misc]
        param_names = params or []
        return Function(name=name.name, params=param_names, body=body)

    def param_list(self, *names: Var):
        return [n.name for n in names]

    def return_cmd(self, value: Expr | None = None):
        return Return(value)

    def method(self, name: Var, *rest):
        if len(rest) == 1:
            params: list[str] | None = None
            body = rest[0]
        else:
            params, body = rest  # type: ignore[misc]
        param_names = params or []
        return Function(name=name.name, params=param_names, body=body)

    #Classes, herança, objetos
    def class_decl(self, name: Var, *rest):
        base: str | None = None
        methods: list[Function] = []
        if rest and isinstance(rest[0], Var):
            base = rest[0].name
            methods = list(rest[1:])  # type: ignore[misc]
        else:
            methods = list(rest)
        return Class(name=name.name, methods=methods, base=base)

    def super(self, _tok, name: Var):
        return Super(name=name.name)

    def this(self, _):
        return This()

    #Programa principal
    def program(self, *stmts):
        return Program(list(stmts))

    def params(self, *args):
        params = list(args)
        return params
