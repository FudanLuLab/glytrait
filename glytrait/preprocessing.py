from typing import Literal

import pandas as pd


def filter_glycans(abundance_df: pd.DataFrame, max_na: float) -> pd.DataFrame:
    """Filter glycans with too many missing values.

    Args:
        abundance_df (pd.DataFrame): The abundance table, with samples as index and glycan IDs
            as columns.
        max_na (float): The maximum proportion of missing values allowed for a glycan.

    Returns:
        filtered_df (pd.DataFrame): The filtered abundance table.
    """
    filtered_df = abundance_df.loc[:, abundance_df.isna().mean() <= max_na]
    return filtered_df.copy()


def impute(
    abundance_df: pd.DataFrame,
    method: Literal["zero", "min", "lod", "mean", "median"],
) -> pd.DataFrame:
    """Impute the missing values.

    The following imputation methods supported:
        - "zero": Replace the missing values with 0.
        - "min": Replace the missing values with the minimum value of the corresponding glycan.
        - "lod": Replace the missing values with 1/5 of the minimum value of the corresponding
            glycan.
        - "mean": Replace the missing values with the mean value of the corresponding glycan.
        - "median": Replace the missing values with the median value of the corresponding glycan.

    Args:
        abundance_df (pd.DataFrame): The abundance table, with samples as index and glycan IDs
            as columns.
        method (str): The imputation method. Can be "zero", "min", "1/5min", "mean", "median".

    Returns:
        imputed_df (pd.DataFrame): The imputed abundance table.
    """
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
    return imputed_df
