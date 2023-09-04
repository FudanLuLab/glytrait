"""Configuration for a GlyTrait.

This module defines the Config class,
which is used to store the configuration for a GlyTrait workflow.

Classes:
    Config: Configuration for a GlyTrait workflow.
"""
from collections.abc import Mapping, Callable
from pathlib import Path
from typing import Any, NoReturn, ClassVar

from .exception import ConfigError

default_config = {
    "input_file": None,
    "output_file": None,
    "mode": None,
    "filter_glycan_max_na": 1.0,
    "impute_method": "zero",
    "corr_threshold": 1.0,
    "corr_method": "pearson",
    "sia_linkage": False,
    "formula_file": None,
    "post_filtering": True,
    "structure_file": None,
    "database": None,
}

must_have = {"input_file", "output_file", "mode"}


class Config:
    """Configuration for a GlyTrait workflow.

    Valid config keys:
        - input_file: Path to the input file. Must provide.
        - output_file: Path to the output file. Must provide.
        - mode: The mode of the workflow. Either "structure" or "composition".
        - filter_glycan_max_na: Maximum NA percentage for a glycan to be kept.
        - impute_method: Method for imputing missing values.
        - corr_threshold: Threshold for colinearity filtering.
        - corr_method: Method for calculating correlation. Either "pearson" or "spearman".
        - sia_linkage: Whether to include sialic acid linkage in the analysis.
        - formula_file: Path to the formula file.
        - post_filtering: Whether to carry out post-filtering.
        - structure_file: Path to the structure file.
        - database: The name of the built-in structure database to use.
        - _has_struc_col: Whether the input file has a structure column. Do not set this manually.
    """

    validators: ClassVar[list[Callable]] = []

    def __init__(self, user_config: Mapping[str, Any]):
        for key in must_have:
            if key not in user_config:
                raise ConfigError(f"Missing config key: {key}")
        self._config = default_config.copy()
        self.update(user_config)

    @classmethod
    def register_validator(cls, validator: Callable) -> Callable:
        """Register a validator for a config key."""
        cls.validators.append(validator)
        return validator

    def asdict(self) -> dict[str, Any]:
        """Return the config as a dictionary."""
        return self._config.copy()

    def get(self, key: str) -> Any:
        """Get a config value."""
        return self._config[key]

    def set(self, key: str, value: Any) -> None:
        """Set a config value."""
        self.update({key: value})

    def update(self, new: Mapping[str, Any]) -> None:
        """Update the config with new values."""
        for key, value in new.items():
            if key not in self._config:
                raise KeyError(f"Invalid config key: {key}")
        new_config = self._config.copy()
        for key, value in new.items():
            new_config[key] = value
        self.check_validity(new_config)
        self._config = new_config

    def check_validity(self, config_dict: dict[str, Any]) -> NoReturn:
        """Check if a value is valid for a config key."""
        for validator in self.validators:
            validator(config_dict)

    def __repr__(self):
        return f"Config({self._config!r})"


def valid_file(
    file: str, name: str, suffix: str, *, check_exist: bool = True, none_ok: bool = True
) -> NoReturn:
    """Validate a file.

    Args:
        file: File path.
        name: Name of the file.
        suffix: File suffix.
        check_exist: Whether the file should exist.
        none_ok: Whether None is a valid value.

    Raises:
        ParameterError: If the file is invalid.
    """
    if file is None and none_ok:
        return
    if not isinstance(file, str):
        raise ConfigError(f"{name} must be a string.")
    if check_exist and not Path(file).exists():
        raise ConfigError(f"{name} does not exist.")
    if check_exist and not Path(file).is_file():
        raise ConfigError(f"{name} must be a file, not directory.")
    if Path(file).suffix != suffix:
        raise ConfigError(f"{name} must be a {suffix.upper()[1:]} file.")


@Config.register_validator
def valid_input_file(config: Mapping[str, Any]) -> NoReturn:
    """Check if a value is a valid input file."""
    valid_file(config["input_file"], "Input file", ".csv", check_exist=True)


@Config.register_validator
def valid_output_file(config: Mapping[str, Any]) -> NoReturn:
    """Check if a value is a valid output file."""
    valid_file(config["output_file"], "Output file", ".xlsx", check_exist=False)


@Config.register_validator
def valid_mode(config: Mapping[str, Any]) -> NoReturn:
    """Check if a value is a valid mode."""
    value = config["mode"]
    if not isinstance(value, str):
        raise ConfigError("mode must be a string.")
    if value not in {"structure", "composition"}:
        raise ConfigError("mode must be one of: structure, composition.")


@Config.register_validator
def valid_filter_glycan_max_na(config: Mapping[str, Any]) -> NoReturn:
    """Check if a value is a valid filter_glycan_max_na."""
    value = config["filter_glycan_max_na"]
    if not isinstance(value, (float, int)):
        raise ConfigError("filter_glycan_max_na must be a float.")
    if not 0 <= value <= 1:
        raise ConfigError("filter_glycan_max_na must be between 0 and 1.")


@Config.register_validator
def valid_impute_method(config: Mapping[str, Any]) -> NoReturn:
    """Check if a value is a valid impute_method."""
    value = config["impute_method"]
    if not isinstance(value, str):
        raise ConfigError("impute_method must be a string.")
    if value not in {"min", "mean", "median", "zero", "lod"}:
        raise ConfigError("impute_method must be one of: min, mean, median, zero, lod.")


@Config.register_validator
def valid_corr_threshold(config: Mapping[str, Any]) -> NoReturn:
    """Check if a value is a valid correlation_threshold."""
    value = config["corr_threshold"]
    if not isinstance(value, (float, int)):
        raise ConfigError("corr_threshold must be a float.")
    if not 0 <= value <= 1:
        raise ConfigError("corr_threshold must be between 0 and 1.")


@Config.register_validator
def valid_corr_method(config: Mapping[str, Any]) -> NoReturn:
    """Check if a value is a valid correlation_method."""
    value = config["corr_method"]
    if not isinstance(value, str):
        raise ConfigError("corr_method must be a string.")
    if value not in {"pearson", "spearman"}:
        raise ConfigError("corr_method must be one of: pearson, spearman.")


@Config.register_validator
def valid_sia_linkage(config: Mapping[str, Any]) -> NoReturn:
    """Check if a value is a valid sia_linkage."""
    if not isinstance(config["sia_linkage"], bool):
        raise ConfigError("sia_linkage must be a boolean.")


@Config.register_validator
def valid_formula_file(config: Mapping[str, Any]) -> NoReturn:
    """Check if a value is a valid formula_file."""
    valid_file(config["formula_file"], "Formula file", ".txt", check_exist=True)


@Config.register_validator
def valid_post_filtering(config: Mapping[str, Any]) -> NoReturn:
    """Check if a value is a valid filter_invalid_traits."""
    if not isinstance(config["post_filtering"], bool):
        raise ConfigError("post_filtering must be a boolean.")


@Config.register_validator
def valid_structure_file(config: Mapping[str, Any]) -> NoReturn:
    """Check if a value is a valid structure_file."""
    path = config["structure_file"]
    if path is None:
        return
    if not isinstance(path, str):
        raise ConfigError("Structure file must be a string.")
    if not Path(path).exists():
        raise ConfigError("Structure file does not exist.")
    if Path(path).is_file():
        if Path(path).suffix != ".csv":
            raise ConfigError("Structure file must be a CSV file.")


@Config.register_validator
def valid_database(config: Mapping[str, Any]) -> NoReturn:
    """Check if a value is a valid database."""
    value = config["database"]
    if value is None:
        return
    if not isinstance(value, str):
        raise ConfigError("Database must be a string.")
    if value not in {"serum", "IgG"}:
        raise ConfigError("Database must be one of: serum, IgG.")


@Config.register_validator
def valid_database_and_structure_file(config: Mapping[str, Any]) -> NoReturn:
    """Check if database and structure_file are provided together."""
    database = config["database"]
    structure_file = config["structure_file"]
    if database is not None and structure_file is not None:
        raise ConfigError("Cannot provide both database and structure_file.")


@Config.register_validator
def valid_composition_mode(config: Mapping[str, Any]) -> NoReturn:
    """Check if the config is valid for composition mode."""
    if config["mode"] == "structure":
        return
    if config["database"] is not None:
        raise ConfigError("Database is incompatible with 'Composition' mode.")
    if config["structure_file"] is not None:
        raise ConfigError("Structure file is incompatible with 'Composition' mode.")
