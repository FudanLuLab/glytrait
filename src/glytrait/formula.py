"""This module defines the `TraitFormula` class, and other related functions.

The `TraitFormula` class is used to represent a trait formula.
It is the core of calculating derived traits.

Classes:
    TraitFormula: The trait formula.

Functions:
    load_formulas: Load all trait formulas from default formula files and custom formulas files.
    save_trait_formulas_tepmlate: Save a template of trait formulas to a file.
    save_builtin_formula: Save a built-in trait formulas to a file.
"""

from __future__ import annotations

import itertools
import re
from importlib.resources import files, as_file
from pathlib import Path
from typing import Literal, Optional, Generator, Protocol

import numpy as np
import pandas as pd
from attrs import field, define

from glytrait.data_type import AbundanceTable, MetaPropertyTable
from glytrait.exception import FormulaError

__all__ = [
    "TraitFormula",
    "load_formulas",
    "save_builtin_formula",
]

default_struc_formula_file = files("glytrait.resources").joinpath("struc_formula.txt")
default_comp_formula_file = files("glytrait.resources").joinpath("comp_formula.txt")


class FormulaParseError(FormulaError):
    """An error occurred when parsing a formula expression."""


class FormulaTerm(Protocol):
    """The protocol for a formula term.

    A formula term is a callable object that takes a meta-property table as input
    and returns a Series with the same index as the meta-property table.
    It makes some calculations based on the meta-properties.
    Normally, it will only work with one meta property.
    """

    expr: str

    def __call__(self, meta_property_table: MetaPropertyTable) -> pd.Series:
        """Calculate the term.

        The return value is a Series with the same index as the meta-property table.
        (The index is the glycans.)
        """
        ...


@define
class ConstantTerm:
    """Return a series with all values being constant."""

    value: int = field()

    def __call__(self, meta_property_table: MetaPropertyTable) -> pd.Series:
        """Calculate the term.

        The return value is a Series with all values being 1.
        """
        return pd.Series(
            self.value, index=meta_property_table.index, name=self.expr, dtype="UInt8"
        )

    @property
    def expr(self) -> str:
        """The expression of the term."""
        return str(self.value)


@define
class NumericalTerm:
    """Return the values of a numerical meta-property.

    This term simply returns a column of the meta-property table,
    as a Series with the same index as the meta-property table.

    Args:
        meta_property: The numerical meta property.
    """

    meta_property: str = field()

    def __call__(self, meta_property_table: MetaPropertyTable) -> pd.Series:
        """Calculate the term.

        The return value is a Series with the same index as the meta-property table.

        Args:
            meta_property_table: The table of meta properties.

        Returns:
            pd.Series: The values of the meta-property,
            with the same index as the meta-property table.

        Raises:
            FormulaError: If the meta-property is not in the meta-property table.
        """
        try:
            mp_s = meta_property_table[self.meta_property]
        except KeyError:
            msg = f"'{self.meta_property}' is not in the meta-property table."
            raise FormulaError(msg)

        if mp_s.dtype == "boolean" or mp_s.dtype == "category":
            msg = f"{mp_s.dtype} must be compared with a value."
            raise FormulaError(msg)

        return mp_s

    @property
    def expr(self) -> str:
        """The expression of the term."""
        return self.meta_property


@define
class CompareTerm:
    """Compare the value of a meta-property with a given value.

    The validity of `meta_property` will not be checked here.

    Args:
        meta_property: The meta property to compare.
        operator: The comparison operator.
        value: The value to compare with.
    """

    meta_property: str = field()
    operator: Literal["==", "!=", ">", ">=", "<", "<="] = field()
    value: float | bool | str = field()

    @operator.validator
    def _check_operator(self, attribute: str, value: str) -> None:
        if value not in {"==", "!=", ">", ">=", "<", "<="}:
            raise ValueError(f"Invalid operator: {value}.")

    def __call__(self, meta_property_table: MetaPropertyTable) -> pd.Series:
        """Calculate the term.

        Args:
            meta_property_table: The table of meta properties.

        Returns:
            pd.Series: A boolean Series with the same index as the meta-property table.

        Raises:
            FormulaError: If the meta-property is not in the meta-property table,
                or the operator and the meta-property are not compatible.
        """
        try:
            mp_s = meta_property_table[self.meta_property]
        except KeyError:
            msg = f"'{self.meta_property}' is not in the meta-property table."
            raise FormulaError(msg)

        condition_1 = mp_s.dtype == "boolean" or mp_s.dtype == "category"
        condition_2 = self.operator in {">", ">=", "<", "<="}
        if condition_1 and condition_2:
            msg = f"Cannot use '{self.operator}' with {mp_s} meta properties."
            raise FormulaError(msg)

        if isinstance(self.value, str):
            expr = f"mp_s {self.operator} '{self.value}'"
        else:
            expr = f"mp_s {self.operator} {self.value}"
        result_s = eval(expr)

        result_s.name = self.expr
        result_s = result_s.astype("UInt8")
        return result_s

    @property
    def expr(self) -> str:
        """The expression of the term."""
        if isinstance(self.value, str):
            return f"{self.meta_property} {self.operator} '{self.value}'"
        else:
            return f"{self.meta_property} {self.operator} {self.value}"


def _is_sia_linkage_term(term: FormulaTerm) -> bool:
    """Check if a formula term is related to sia-linkage."""
    return "nE" in term.expr or "nS" in term.expr


@define
class TraitFormula:
    """The trait formula."""

    expression: str = field()
    description: str = field()
    name: str = field(init=False)

    _numerators: list[FormulaTerm] = field(init=False)
    _denominators: list[FormulaTerm] = field(init=False)

    _sia_linkage: bool = field(init=False, default=False)

    _initialized: bool = field(init=False, default=False)
    _numerator_array: pd.Series = field(init=False, default=None)
    _denominator_array: pd.Series = field(init=False, default=None)

    def __attrs_post_init__(self):
        name, numerators, denominators = _parse_formula_expression(self.expression)
        self.name = name
        self._numerators = numerators
        self._denominators = denominators
        self._sia_linkage = self._init_sia_linkage()

    def _init_sia_linkage(self) -> bool:
        """Check if the formula is related to sia-linkage."""
        term_iter = itertools.chain(self._numerators, self._denominators)
        return any(_is_sia_linkage_term(term) for term in term_iter)

    @property
    def sia_linkage(self) -> bool:
        """Whether the formula is related to sia-linkage."""
        return self._sia_linkage

    @property
    def numerators(self) -> list[str]:
        """The names of the numerators."""
        return [term.expr for term in self._numerators]

    @property
    def denominators(self) -> list[str]:
        """The names of the denominators."""
        return [term.expr for term in self._denominators]

    def initialize(self, meta_property_table: MetaPropertyTable) -> None:
        """Initialize the trait formula.

        Args:
            meta_property_table: The table of meta properties.
        """
        self._numerator_array = self._initialize(meta_property_table, self._numerators)
        self._denominator_array = self._initialize(
            meta_property_table, self._denominators
        )
        self._initialized = True

    @staticmethod
    def _initialize(
        meta_property_table: MetaPropertyTable, terms: list[FormulaTerm]
    ) -> pd.Series:
        series_list = [term(meta_property_table) for term in terms]
        return pd.concat(series_list, axis=1).prod(axis=1)

    def calcu_trait(self, abundance_table: AbundanceTable) -> pd.Series:
        """Calculate the trait.

        Args:
            abundance_table (AbundanceTable): The glycan abundance table,
                with samples as index, and glycans as columns.

        Returns:
            pd.Series: An array of trait values for each sample.
        """
        if not self._initialized:
            raise RuntimeError("TraitFormula is not initialized.")
        pd.testing.assert_index_equal(
            abundance_table.columns, self._numerator_array.index
        )
        pd.testing.assert_index_equal(
            abundance_table.columns, self._denominator_array.index
        )

        numerator = abundance_table.values @ self._numerator_array.values
        denominator = abundance_table.values @ self._denominator_array.values
        denominator[denominator == 0] = np.nan
        values = numerator / denominator
        return pd.Series(
            values, index=abundance_table.index, name=self.name, dtype=float
        )


def _parse_formula_expression(
    expr: str,
) -> tuple[str, list[FormulaTerm], list[FormulaTerm]]:
    """Parse the formula expression.

    Args:
        expr: The formula expression.

    Returns:
        The name, the numerators (a list of FormulaTerm),
        and the denominators (a list of FormulaTerm) of the formula.
    """
    name, numerator_expr, spliter, denominator_expr = _split_formula_expression(expr)
    numerators = _parse_terms(numerator_expr)
    denominators = _parse_terms(denominator_expr)
    if spliter == "//":
        numerators.extend(denominators)
    return name, numerators, denominators


def _split_formula_expression(expr: str) -> tuple[str, str, str, str]:
    """Split the formula expression into three parts:

    - The name of the formula.
    - The numerator expression of the formula.
    - The slash or double-slash.
    - The denominator expression of the formula.
    """
    expr = expr.strip()
    if " = " not in expr:
        raise FormulaParseError("no ' = '.")

    try:
        name, expr_after_name = expr.split(" = ")
    except ValueError:
        raise FormulaParseError("Misuse of '=' for '=='.")
    name = name.strip()

    if "//" not in expr_after_name and "/" not in expr_after_name:
        raise FormulaParseError("no '/' or '//'.")

    if expr_after_name.count("//") == 1:
        spliter = "//"
    elif expr_after_name.count("/") == 1:
        spliter = "/"
    else:
        raise FormulaParseError("too many '/' or '//'.")
    numerator, denominator = expr_after_name.split(spliter)
    numerator = numerator.strip()
    denominator = denominator.strip()

    return name, numerator, spliter, denominator


def _parse_terms(expr: str) -> list[FormulaTerm]:
    """Parse the terms in the formula expression."""
    term_exprs = [t.strip() for t in expr.split("*")]
    return [_parse_term(t) for t in term_exprs]


def _parse_term(expr: str) -> FormulaTerm:
    """Parse a term in the formula expression."""
    # Constant term
    if expr.isdigit():
        return ConstantTerm(value=int(expr.strip("()")))  # type: ignore

    # Numerical term
    operators = {"==", "!=", ">", ">=", "<", "<="}
    if not any(op in expr for op in operators):
        return NumericalTerm(meta_property=expr.strip("()"))  # type: ignore

    # Compare term
    if not expr.startswith("(") or not expr.endswith(")"):
        msg = "comparison terms must be in parentheses."
        raise FormulaParseError()
    expr = expr.strip("()")
    meta_property_p = r"(\w+)"
    operator_p = r"(==|!=|>|>=|<|<=)"
    value_p = r"""(\d+|True|False|'[a-zA-Z-_]*'|"[a-zA-Z-_]*")"""
    total_p = rf"{meta_property_p}\s*{operator_p}\s*{value_p}"
    match = re.fullmatch(total_p, expr)
    if match is None:
        raise FormulaParseError(f"invalid comparison term {expr}.")
    meta_property, operator, value = match.groups()
    if value.isdigit():
        value = int(value)
    elif value == "True":
        value = True
    elif value == "False":
        value = False
    else:
        value = value.strip("'")
        value = value.strip('"')
    return CompareTerm(  # type: ignore
        meta_property=meta_property, operator=operator, value=value  # type: ignore
    )


def load_formulas(
    type_: Literal["structure", "composition"],
    user_file: Optional[str] = None,
    sia_linkage: bool = False,
) -> list[TraitFormula]:
    """Load both the default formulas and the user-defined formulas.

    Args:
        type_ (Literal["structure", "composition"]): The type of the formulas.
        user_file (Optional[str], optional): The path of the user-defined formula file.
            Defaults to None.
        sia_linkage (bool, optional): Whether to include formulas with sia-linkage
            meta-properties. Defaults to False.

    Returns:
        list[TraitFormula]: The formulas.

    Raises:
        FormulaError: If a formula string cannot be parsed,
            or the user-provided formula file is in a wrong format.
    """
    formulas = list(load_default_formulas(type_=type_))

    if user_file is not None:
        default_formula_names = {f.name for f in formulas}
        user_formulas = load_formulas_from_file(user_file)
        for f in user_formulas:
            if f.name in default_formula_names:
                continue
            formulas.append(f)

    if not sia_linkage:
        formulas = [f for f in formulas if not f.sia_linkage]
    return formulas


def load_default_formulas(
    type_: Literal["structure", "composition"]
) -> Generator[TraitFormula, None, None]:
    """Load the default formulas.

    Args:
        type_ (Literal["structure", "composition"]): The type of the formulas.

    Yields:
        The formulas parsed.
    """
    if type_ == "composition":
        file_traversable = default_comp_formula_file
    elif type_ == "structure":
        file_traversable = default_struc_formula_file
    else:
        raise ValueError("Invalid formula type.")
    with as_file(file_traversable) as file:
        yield from load_formulas_from_file(str(file))


def load_formulas_from_file(filepath: str) -> Generator[TraitFormula, None, None]:
    """Load formulas from a file.

    Args:
        filepath (str): The path of the formula file.

    Yields:
        The formulas parsed.

    Raises:
        FormulaError: If a formula string cannot be parsed,
            or the user-provided formula file is in a wrong format,
            or there are duplicate formula names.
    """
    formulas_parsed: set[str] = set()
    for description, expression in deconvolute_formula_file(filepath):
        formula = TraitFormula(expression, description)
        if formula.name in formulas_parsed:
            raise FormulaError(f"Duplicate formula name: {formula.name}.")
        yield formula
        formulas_parsed.add(formula.name)


def deconvolute_formula_file(
    formula_file: str,
) -> Generator[tuple[str, str], None, None]:
    """A generator that yields the formula description and the formula expression.

    Args:
        formula_file (str): The path of the formula file.

    Yields:
        tuple[str, str]: The formula description and the formula expression.

    Raises:
        FormulaError: If the user-provided formula file is in a wrong format.
    """
    description = None
    expression = None
    with open(formula_file, "r", encoding="utf8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("@"):
                if description is not None:
                    raise FormulaError(
                        f"No expression follows description '{description}'."
                    )
                description = line[1:].strip()
            elif line.startswith("$"):
                expression = line[1:].strip()
                if description is None:
                    raise FormulaError(
                        f"No description before expression '{expression}'."
                    )
                yield description, expression
                description = None
                expression = None
    if description is not None:
        raise FormulaError(f"No expression follows description '{description}'.")


def save_builtin_formula(dirpath: str | Path) -> None:
    """Copy the builtin formula file to the given path.

    Args:
        dirpath (str): The path to save the built-in formula file.
    """
    Path(dirpath).mkdir(parents=True, exist_ok=True)
    struc_file = Path(dirpath) / "struc_builtin_formulas.txt"
    comp_file = Path(dirpath) / "comp_builtin_formulas.txt"
    struc_content = default_struc_formula_file.open("r").read()
    comp_content = default_comp_formula_file.open("r").read()
    with open(struc_file, "w", encoding="utf8") as f:
        f.write(struc_content)
    with open(comp_file, "w", encoding="utf8") as f:
        f.write(comp_content)
