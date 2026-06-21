import pandas as pd
from pandas import IndexSlice as idx
import numpy as np
import pytest
import itertools
from functools import partial, reduce
from treelib import Tree, Node
from pandas_reconcile.tree import (
    dict_to_tree,
    node_names,
)
from pandas_reconcile.aggregate import (
    df_aggregate,
    total_aggregate,
    nested_aggregate,
    assoc_df,
    distribute_flows,
    update_flow,
    check_sums,
)


all_products = list(map(lambda n: "P" + str(n), np.arange(8, 28)))
base_flows = ["NRGSUP", "TI_E", "TO", "NRG_E", "DL"]


@pytest.fixture
def raw_eb():
    checks = {
        "nrg_bal": dict_to_tree({"AFC": base_flows}),
        "siec": dict_to_tree({"TOTAL": all_products}),
    }
    index = pd.MultiIndex.from_tuples(
        itertools.product(
            base_flows + ["AFC"], all_products + ["TOTAL"], ["KTOE"], ["FR"]
        ),
        names=["nrg_bal", "siec", "unit", "geo"],
    )
    A = pd.DataFrame(np.ones(len(index)), index=index).squeeze()
    return A, checks


def test_assoc_df(raw_eb):
    A, checks = raw_eb
    B = A.copy()

    A.loc[idx["TO", :, :, :]] = 2
    A = assoc_df(A, B.loc[idx[["TO"], :, :, :]]).squeeze()
    B = B.reindex_like(A)
    pd.testing.assert_series_equal(A, B)


def test_assoc_df_with_sum(raw_eb):
    A, checks = raw_eb
    B = A.copy()

    A.loc[idx["TO", :, :, :]] = 0
    A = assoc_df(A, B.loc[idx[["TO"], :, :, :]], do_sum=True).squeeze()
    B = B.reindex_like(A)
    pd.testing.assert_series_equal(A, B)


def test_assoc_df_no_mutation(raw_eb):
    """Verify assoc_df does not mutate its input arguments."""
    A, checks = raw_eb
    B = A.copy()

    # Store original names
    original_a_name = A.name
    original_b_name = B.name

    # Call assoc_df with inputs that have None as name
    value = B.loc[idx[["TO"], :, :, :]]
    original_value_name = value.name

    assoc_df(A, value)

    # Verify inputs were not mutated
    assert A.name == original_a_name, f"A.name changed from {original_a_name} to {A.name}"
    assert value.name == original_value_name, f"value.name changed from {original_value_name} to {value.name}"


def test_assoc_df_no_mutation_with_none_name():
    """Verify assoc_df doesn't mutate inputs even when names are None."""
    # Create Series with None names
    s1 = pd.Series([1, 2, 3], index=['a', 'b', 'c'], name=None)
    s2 = pd.Series([10, 20, 30], index=['a', 'b', 'c'], name=None)

    original_s1_name = s1.name
    original_s2_name = s2.name

    assoc_df(s1, s2)

    # Verify inputs were not mutated
    assert s1.name == original_s1_name, f"s1.name was mutated to {s1.name}"
    assert s2.name == original_s2_name, f"s2.name was mutated to {s2.name}"


def test_df_aggregate_siec(raw_eb):
    A, checks = raw_eb
    B = A.copy()

    expected = (
        B.loc[idx[:, node_names(checks["siec"].children("TOTAL")), :, :]]
        .groupby(level=["nrg_bal", "unit", "geo"])
        .sum()
        .to_numpy()
    )
    computed_from_series = df_aggregate(A, checks["siec"], "TOTAL")
    np.testing.assert_almost_equal(expected, computed_from_series.to_numpy())


def test_df_aggregate_nrg_bal(raw_eb):
    A, checks = raw_eb
    B = A.copy()

    expected = (
        B.loc[idx[node_names(checks["nrg_bal"].children("AFC")), :, :, :]]
        .groupby(level=["siec", "unit", "geo"])
        .sum()
        .to_numpy()
    )
    computed_from_series = df_aggregate(A, checks["nrg_bal"], "AFC")
    np.testing.assert_almost_equal(expected, computed_from_series.to_numpy())


def test_total_aggregate_siec(raw_eb):
    A, checks = raw_eb
    B = A.copy()
    B = df_aggregate(B, checks["siec"], "TOTAL")

    # computed
    C = total_aggregate(A, checks["siec"])
    pd.testing.assert_series_equal(B, C.loc[B.index])


def test_total_aggregate_nrg_bal(raw_eb):
    A, checks = raw_eb
    B = A.copy()
    B = df_aggregate(B, checks["nrg_bal"], "AFC")

    # computed
    C = total_aggregate(A, checks["nrg_bal"])
    pd.testing.assert_series_equal(B, C.loc[B.index])


def test_nested_aggregate_siec(raw_eb):
    A, checks = raw_eb
    B = A.copy()
    B = df_aggregate(B, checks["siec"], "TOTAL")

    # computed
    C = A.nested_aggregate({"TOTAL": all_products})
    pd.testing.assert_series_equal(B, C.loc[B.index])


def test_nested_aggregate_nrg_bal(raw_eb):
    A, checks = raw_eb
    B = A.copy()
    B = df_aggregate(B, checks["nrg_bal"], "AFC")

    # computed
    C = A.nested_aggregate({"AFC": base_flows})
    pd.testing.assert_series_equal(B, C.loc[B.index])


def helper_test_distribute_flows(raw_eb, value):
    A, checks = raw_eb
    update_flow_with_checks = partial(update_flow, checks["nrg_bal"])
    A = total_aggregate(A, checks["nrg_bal"])
    B = A.copy()
    B[B.index] = value
    B.loc[idx[["AFC"], :, :, :]] = A.loc[idx[["AFC"], :, :, :]]

    C = reduce(
        lambda df, fill: assoc_df(df, update_flow_with_checks(df, fill)),
        B.loc[idx[["AFC"], :, :, :]].index,
        B,
    )

    pd.testing.assert_series_equal(A, C)


def test_distribute_flows(raw_eb):
    helper_test_distribute_flows(raw_eb, 0)


def test_distribute_flows_nan(raw_eb):
    helper_test_distribute_flows(raw_eb, np.nan)


def test_check_sums(raw_eb):
    A, checks = raw_eb
    A = total_aggregate(A, checks["siec"])
    A = total_aggregate(A, checks["nrg_bal"])
    assert (
        set(check_sums(A, checks["nrg_bal"])).union(set(check_sums(A, checks["siec"])))
        == set()
    )
