from typing import Any

import pytest

import glytrait.core


@pytest.fixture
def default_config() -> dict[str, Any]:
    return dict(
        input_file="input_file",
        output_file="output_file",
        mode="structure",
        filter_glycan_max_na=0.5,
        impute_method="min",
        sia_linkage=False,
        formula_file="user_formula_file",
        filter_invalid_traits=True,
        group_file=None,
        structure_file=None,
        database=None,
    )


@pytest.fixture
def formula_mocks(mocker) -> list:
    formula_1_mock = mocker.Mock()
    formula_1_mock.sia_linkage = False
    formula_1_mock.name = "trait1"
    formula_2_mock = mocker.Mock()
    formula_2_mock.sia_linkage = True
    formula_2_mock.name = "trait2"
    formula_3_mock = mocker.Mock()
    formula_3_mock.sia_linkage = False
    formula_3_mock.name = "trait3"
    return [formula_1_mock, formula_2_mock, formula_3_mock]


@pytest.mark.parametrize(
    "has_structure, mode, structure_file, database",
    [
        (True, "structure", None, None),
        (False, "structure", "structure_file", None),
        (False, "structure", None, "database"),
        (False, "composition", None, None),
    ],
)
def test_load_and_preprocess_data(
    mocker, default_config, mode, has_structure, structure_file, database
):
    config = default_config.copy()
    config["mode"] = mode
    config["structure_file"] = structure_file
    config["database"] = database

    comps, strucs, abund_df, glycans = "comps", "strucs", "abund_df", "glycans"
    strucs = None if not has_structure else strucs
    read_input_mock = mocker.patch(
        "glytrait.core.read_input", return_value=(comps, strucs, abund_df)
    )
    load_glycans_mock = mocker.patch("glytrait.core.load_glycans", return_value=glycans)
    load_default_mock = mocker.patch("glytrait.core.load_default", return_value=glycans)
    read_structure_mock = mocker.patch(
        "glytrait.core.read_structure", return_value=glycans
    )
    load_compositions_mock = mocker.patch(
        "glytrait.core.load_compositions", return_value=glycans
    )
    preprocess_mock = mocker.patch(
        "glytrait.core.preprocess_pipeline", return_value=abund_df
    )

    result = glytrait.core._load_and_preprocess_data(config)

    read_input_mock.assert_called_once_with("input_file")
    match (has_structure, mode, structure_file, database):
        case (True, "structure", None, None):
            load_glycans_mock.assert_called_once_with(strucs)
            load_default_mock.assert_not_called()
            read_structure_mock.assert_not_called()
            load_compositions_mock.assert_not_called()
        case (False, "structure", "structure_file", None):
            load_glycans_mock.assert_not_called()
            load_default_mock.assert_not_called()
            read_structure_mock.assert_called_once_with(structure_file, comps)
            load_compositions_mock.assert_not_called()
        case (False, "structure", None, "database"):
            load_glycans_mock.assert_not_called()
            load_default_mock.assert_called_once_with(database, comps)
            read_structure_mock.assert_not_called()
            load_compositions_mock.assert_not_called()
        case (False, "composition", None, None):
            load_glycans_mock.assert_not_called()
            load_default_mock.assert_not_called()
            read_structure_mock.assert_not_called()
            load_compositions_mock.assert_called_once_with(comps, sia_linkage=False)
    preprocess_mock.assert_called_once_with(abund_df, 0.5, "min")
    assert result == (glycans, abund_df)


@pytest.mark.parametrize(
    "sia_linkage",
    [True, False],
)
def test_load_formulas(mocker, default_config, formula_mocks, sia_linkage):
    config = default_config.copy()
    config["sia_linkage"] = sia_linkage
    config["formula_file"] = "formula_file"
    load_formulas_mock = mocker.patch(
        "glytrait.core.load_formulas", return_value=formula_mocks
    )
    result = glytrait.core._load_formulas(config)
    load_formulas_mock.assert_called_once_with("structure", "formula_file")
    if sia_linkage:
        expected = formula_mocks
    else:
        expected = [formula_mocks[0], formula_mocks[2]]
    assert result == expected


@pytest.mark.parametrize(
    "sia_linkage",
    [True, False],
)
def test_calcu_derived_traits(mocker, default_config, sia_linkage):
    config = default_config.copy()
    config["sia_linkage"] = sia_linkage

    abund_df_mock = mocker.Mock(name="abund_df_mock")
    abund_df_mock.columns = mocker.Mock(name="columns_mock")
    build_meta_property_table = mocker.patch(
        "glytrait.core.build_meta_property_table", return_value="meta_prop_df"
    )
    calcu_derived_trait_mock = mocker.patch(
        "glytrait.core.calcu_derived_trait", return_value="derived_trait_df"
    )

    result = glytrait.core._calcu_derived_traits(
        config, abund_df_mock, "glycans", "formulas"
    )

    build_meta_property_table.assert_called_once_with(
        abund_df_mock.columns, "glycans", "structure", sia_linkage
    )
    calcu_derived_trait_mock.assert_called_once_with(
        abund_df_mock, "meta_prop_df", "formulas"
    )
    assert result == ("meta_prop_df", "derived_trait_df")


@pytest.mark.parametrize(
    "filter_invalid_traits",
    [True, False],
)
def test_filter_invalid_traits(
    mocker, default_config, formula_mocks, filter_invalid_traits
):
    config = default_config.copy()
    config["filter_invalid_traits"] = filter_invalid_traits

    derived_trait_df_mock = mocker.Mock(name="derived_trait_df_mock")
    derived_trait_df_mock.columns = ["trait1", "trait2", "trait3"]
    derived_trait_filtered_df_mock = mocker.Mock(name="derived_trait_filtered_df_mock")
    derived_trait_filtered_df_mock.columns = ["trait1", "trait2"]
    mocker.patch(
        "glytrait.core.filter_derived_trait",
        return_value=derived_trait_filtered_df_mock,
    )

    result = glytrait.core._filter_invalid_traits(
        config, derived_trait_df_mock, formula_mocks
    )
    result_derived_traits, result_formulas = result
    if filter_invalid_traits:
        expected_traits = derived_trait_filtered_df_mock
        expected_formulas = [formula_mocks[0], formula_mocks[1]]
    else:
        expected_traits = derived_trait_df_mock
        expected_formulas = formula_mocks
    assert result_derived_traits == expected_traits
    assert result_formulas == expected_formulas


@pytest.mark.parametrize(
    "has_groups, n_groups",
    [
        (True, 2),
        (True, 3),
        (False, 0),
    ],
)
def test_statistical_analysis(mocker, default_config, has_groups, n_groups):
    config = default_config.copy()
    if has_groups is True:
        config["group_file"] = "group_file"
    else:
        config["group_file"] = None

    group_mock = mocker.Mock()
    group_mock.nunique.return_value = n_groups
    get_groups_mock = mocker.patch(
        "glytrait.core._get_groups", return_value=group_mock if has_groups else None
    )
    hypo_test_mock = mocker.patch(
        "glytrait.core.auto_hypothesis_test", return_value="hypo_test_result"
    )
    roc_mock = mocker.patch("glytrait.core.calcu_roc_auc", return_value="roc_result")

    if has_groups and n_groups == 2:
        return_value = (group_mock, "hypo_test_result", "roc_result")
    elif has_groups and n_groups > 2:
        return_value = (group_mock, "hypo_test_result", None)
    else:
        return_value = (None, None, None)
    assert glytrait.core._statistical_analysis(config, "trait_df") == return_value


def test_run_workflow(mocker):
    load_and_preprocess_data_mock = mocker.patch(
        "glytrait.core._load_and_preprocess_data", return_value=("glycans", "abund_df")
    )
    load_formulas_mock = mocker.patch(
        "glytrait.core._load_formulas", return_value="formulas"
    )
    calcu_derived_traits_mock = mocker.patch(
        "glytrait.core._calcu_derived_traits",
        return_value=("meta_prop_df", "derived_trait_df"),
    )
    filter_invalid_traits_mock = mocker.patch(
        "glytrait.core._filter_invalid_traits",
        return_value=("derived_trait_df", "formulas"),
    )
    combine_data_mock = mocker.patch(
        "glytrait.core._combine_data",
        return_value="trait_df",
    )
    statistical_analysis_mock = mocker.patch(
        "glytrait.core._statistical_analysis",
        return_value=("groups", "hypo_test_result", "roc_result"),
    )
    write_output_mock = mocker.patch("glytrait.core.write_output")

    glytrait.core.run_workflow("config")

    load_and_preprocess_data_mock.assert_called_once_with("config")
    load_formulas_mock.assert_called_once_with("config")
    calcu_derived_traits_mock.assert_called_once_with(
        "config", "abund_df", "glycans", "formulas"
    )
    filter_invalid_traits_mock.assert_called_once_with(
        "config", "derived_trait_df", "formulas"
    )
    combine_data_mock.assert_called_once_with("abund_df", "derived_trait_df")
    statistical_analysis_mock.assert_called_once_with("config", "trait_df")
    write_output_mock.assert_called_once_with(
        "config",
        "derived_trait_df",
        "abund_df",
        "meta_prop_df",
        "formulas",
        "groups",
        "hypo_test_result",
        "roc_result",
    )
