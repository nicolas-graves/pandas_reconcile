import numpy as np
import pandas as pd
from pandas import IndexSlice as idx
import pandas_flavor as pf
from typing import (
    cast,
    Callable,
    List,
    Hashable,
    Optional,
    Tuple,
    Union,
)
from treelib import Tree
from .tree import dict_to_tree, node_names
from functools import reduce
from toolz import valmap, valfilter


def partition_1(
    predicate: Callable[[str], bool], input_list: List[str]
) -> Tuple[str, List[str]]:
    trues, falses = [], []
    for k in range(len(input_list)):
        if predicate(input_list[k]):
            trues.append(input_list[k])
        else:
            falses.append(input_list[k])
    return trues[0], falses


def get_dicname_and_other_levels(
    frame: pd.DataFrame, tree: Tree
) -> Tuple[str, List[str]]:
    try:
        value = node_names(tree.leaves())[0]
    except Exception:
        raise ValueError(
            f"Couldn't find a valid value in {frame.index.names}\
 for \n{tree}."
        )

    def is_current_level(level):
        return value in frame.index.get_level_values(level).unique()

    try:
        return partition_1(is_current_level, frame.index.names)
    except Exception:
        raise ValueError(
            f"Couldn't find a valid level in {frame.index.names}\
 for {value} in \n{tree}."
        )


def df_aggregate(
    frame: pd.Series,
    tree: Tree,
    name: str,
    region: Optional[str] = None,
) -> pd.Series:
    """Compute a generic aggregate sum following dictionary[name]."""
    dicname, levels = get_dicname_and_other_levels(frame, tree)
    index = frame.index.get_level_values(dicname).isin(node_names(tree.children(name)))
    aggregate = (
        pd.concat(
            [
                cast(
                    pd.Series,
                    frame.loc[index].groupby(level=cast(Hashable, levels)).sum(),
                ).to_frame()
            ],
            keys=[name],
            names=[dicname],
        )
        .reset_index()
        .set_index(frame.index.names)
    )
    return pd.Series(aggregate[aggregate.columns[0]], index=aggregate.index)


def total_aggregate(frame: pd.Series, tree: Tree, region=slice(None)):
    """Aggregate all keys from tree in order."""
    aggregation_order = list(
        reversed(
            list(
                tree.expand_tree(
                    mode=2,
                    filter=lambda x: x.tag not in node_names(tree.leaves()),
                )
            )
        )
    )
    return reduce(
        lambda df, name: assoc_df(df, df_aggregate(df, tree, name, region)),
        aggregation_order,
        frame,
    )


@pf.register_dataframe_method
@pf.register_series_method
def nested_aggregate(frame, dic: dict, region=slice(None)):
    return total_aggregate(frame, dict_to_tree(dic), region)


def check_sums(
    frame: pd.DataFrame, tree: Tree, region=slice(None), tol=3 * 10 ** (-1), omit=None
) -> list:
    """
    Return a list of tuples indicating suspicious data entries which
    might not follow the sums as defined in dictionary.
    Adjust tolerance using parameter tol.
    """
    if omit is not None:
        new_tree = Tree(tree.subtree(cast(str, tree.root)), deep=True)
        if tree.root in omit:
            new_tree.update_node(cast(str, tree.root), identifier="ROOT")
        for o in omit:
            if new_tree.contains(o):
                new_tree.link_past_node(o)
    else:
        new_tree = tree
    dicname, levels = get_dicname_and_other_levels(frame, new_tree)
    df = frame.xs(region, level="geo", drop_level=False)
    calculated = total_aggregate(df, new_tree, region)
    # Isolate only aggregated sums from the calculated frame.
    calculated = calculated.loc[
        calculated.index.get_level_values(dicname).isin(new_tree.nodes.keys())
    ].xs(region, level="geo", drop_level=False)
    values = df.to_frame().join(calculated, how="inner", rsuffix="_r")
    errors = (values.iloc[:, 0] - values.iloc[:, 1]).squeeze() ** 2 / list(
        map(lambda x: max(1, x**2), values.iloc[:, 0])
    )  # small deviations for small values are tolerated
    return errors.loc[errors > tol].to_dict()


def assoc_df(
    df: Union[pd.DataFrame, pd.Series],
    value: Union[pd.DataFrame, pd.Series],
    do_sum: bool = False,
):
    """Return the pd.DataFrame or pd.Series with the updated value."""
    d2 = df.copy()
    value.name = df.name
    if value.name is None:
        df.name, value.name = 0, 0
    if do_sum:
        value = pd.Series(
            data=np.nansum([value.to_numpy(), d2.loc[value.index]], axis=0),
            index=value.index,
            name=value.name,
        )
    d2 = d2.to_frame().join(value, how="outer", rsuffix="_r")
    d2 = d2.iloc[:, 1].combine_first(d2.iloc[:, 0]).squeeze()
    d2.name = df.name
    return d2


def distribute_flows(
    frame: pd.DataFrame,
    flow,
    dictionary: dict,
    product: str,
    country,
    do_sum: bool = True,
):
    """Distributes flow according to the dictionary, using leaves under each node."""
    if not frame.index.is_unique:
        duplicated_index = frame.index[frame.index.duplicated()]
        raise ValueError(
            f"The MultiIndex in distribute_flows is not unique. \
Duplicated index: {duplicated_index}"
        )
    target_leaves = node_names(dictionary.leaves(flow))
    unit = frame.index.unique(level="unit")[0]
    previous_sum = frame.loc[idx[target_leaves, product, unit, country]].sum()
    future_value = do_sum * previous_sum
    value_to_distribute = frame.loc[idx[flow, product, unit, country]]
    if isinstance(value_to_distribute, pd.Series):
        value_to_distribute = value_to_distribute.to_numpy()[0]
    future_value += value_to_distribute
    if abs(previous_sum) > 10 ** (-2):  # case where some flows already exist
        proportions = (
            frame.loc[idx[target_leaves, product, unit, country]] / previous_sum
        )
    else:  # case where only np.nans
        proportions = pd.Series(
            data=np.array([1 / len(target_leaves)] * int(len(target_leaves))),
            index=frame.loc[
                idx[
                    target_leaves,
                    product,
                    unit,
                    country,
                ]
            ].index,
        )
    return assoc_df(frame, proportions * future_value, do_sum)


def valremove(dic, names: List[str]):
    """Remove names from lists in dic."""
    dic = valmap(lambda val: list(filter(lambda x: x not in names, val)), dic)
    return valfilter(lambda x: x != [], dic)


def update_flow(flow_checks, d, fill):
    flow, product, unit, country = fill
    print("Distributing", flow, product, country)
    return distribute_flows(
        d.loc[
            idx[
                :,
                [product],
                [unit],
                [country],
            ]
        ],
        flow,
        flow_checks,
        product,
        country,
    )
