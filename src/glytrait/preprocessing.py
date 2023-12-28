"""Preprocess the abundance table."""
from typing import Literal, Protocol

import pandas as pd
from attrs import define

from glytrait.load_data import GlyTraitInputData, AbundanceTable


class ProcessingStep(Protocol):
    """The protocol for processing steps."""

    def __call__(self, data: GlyTraitInputData) -> None:
        ...


@define
class ProcessingPipeline:
    """The pipeline for processing the abundance table."""

    _steps: list[ProcessingStep]

    def __call__(self, data: GlyTraitInputData) -> None:
        for step in self._steps:
            step(data)


@define
class FilterGlycans(ProcessingStep):
    """Filter glycans with too many missing values.

    Args:
        max_na (float): The maximum proportion of missing values allowed for a glycan.
    """

    max_na: float

    def __call__(self, data: GlyTraitInputData) -> None:
        glycans_to_keep = _filter_glycans(data.abundance_table, self.max_na)
        data.abundance_table = AbundanceTable(
            data.abundance_table.filter(items=glycans_to_keep)
        )
        for glycan in set(data.glycans).difference(glycans_to_keep):
            del data.glycans[glycan]


def _filter_glycans(abundance_df: AbundanceTable, max_na: float) -> list[str]:
    to_keep_mask = abundance_df.isna().mean() <= max_na
    glycans_to_keep = list(abundance_df.columns[to_keep_mask])
    return glycans_to_keep


@define
class Impute(ProcessingStep):
    """Impute the missing values of the abundance table.

    The following imputation methods supported:
        - "zero": Replace the missing values with 0.
        - "min": Replace the missing values with the minimum value of the corresponding glycan.
        - "lod": Replace the missing values with 1/5 of the minimum value of the corresponding
            glycan.
        - "mean": Replace the missing values with the mean value of the corresponding glycan.
        - "median": Replace the missing values with the median value of the corresponding glycan.

    Args:
        method (str): The imputation method.
            Can be "zero", "min", "lod", "mean", "median".
    """

    method: Literal["zero", "min", "lod", "mean", "median"]

    def __call__(self, data: GlyTraitInputData) -> None:
        data.abundance_table = _impute(data.abundance_table, self.method)


def _impute(
    abundance_df: AbundanceTable,
    method: Literal["zero", "min", "lod", "mean", "median"],
) -> AbundanceTable:
    if method == "zero":
        imputed_df = abundance_df.fillna(0)
    elif method == "min":
        imputed_df = abundance_df.fillna(abundance_df.min())
    elif method == "lod":
        imputed_df = abundance_df.fillna(abundance_df.min() / 5)
    elif method == "mean":
        imputed_df = abundance_df.fillna(abundance_df.mean())
    elif method == "median":
        imputed_df = abundance_df.fillna(abundance_df.median())
    else:
        raise ValueError("The imputation method is not supported.")
    return AbundanceTable(imputed_df)


def normalization(abundance_df: pd.DataFrame) -> pd.DataFrame:
    """Normalize the abundance table by dividing the sum of each sample.

    Args:
        abundance_df (pd.DataFrame): The abundance table, with samples as index and Compositions
            as columns.

    Returns:
        normalized_df (pd.DataFrame): The normalized abundance table.
    """
    row_sums = abundance_df.sum(axis=1)
    normalized_df = abundance_df.div(row_sums, axis=0).round(6)
    return normalized_df
