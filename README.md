# Pandas Reconcile

**Hierarchical aggregation for pandas — keep your accounting identities correct, always.**

---

## The Problem

In energy statistics, national accounts, environmental data, and many other domains, data comes with **accounting identities**: the value of a parent category must equal the sum of its children. These identities can be *nested*.

```
AFC (total final consumption)
├── NRGSUP
├── TI_E
├── TO
├── NRG_E
└── DL
```

Working with such data in pandas is surprisingly painful. When you patch a leaf value, parent or children nodes become stale. When you add a new row, you have to manually propagate the sum upward. And if your hierarchy is encoded as a dictionary, there's no built-in way to express "aggregate according to these accounting identities."

`pandas_reconcile` solves this cleanly. Define your hierarchy as a plain Python dict, and the library handles everything: building the tree, aggregating in the correct bottom-up order, distributing flows proportionally, and verifying that identities still hold after modifications.

---

## Core Concepts / Design

- **Hierarchies as dicts, data as DataFrames**: an accounting identity is expressed as a `dict` mapping each parent to a list of its direct children:

```python
energy_flows = {
    "AFC": ["NRGSUP", "TI_E", "TO", "NRG_E", "DL"]
}

products = {
    "TOTAL": ["P8", "P9", "P10", "P11"]  # each Pi is a product category
}
```

- Lower level representation as `Tree`, to solve nesting intuitively. Multi-root hierarchies are supported — `pandas_reconcile` automatically inserts a synthetic `ROOT` node.

- **Non-destructive**: All operations return new objects. The original series is never mutated.

- **Order-independent aggregation**: `total_aggregate` always processes nodes bottom-up (reverse breadth-first), so you never need to think about ordering your dictionary keys.

- **Multi-dimensional**: The library works on any MultiIndex level. It auto-detects which level contains the tree's nodes, so you can use the same function for a product hierarchy and a flow hierarchy over the same series.

- **Composable**: The functional API (`df_aggregate`, `assoc_df`, `distribute_flows`) integrates naturally with `functools.reduce` pipelines for complex patching workflows.

---

## Public API

### `nested_aggregate(dic)` — pandas flavor method

The primary entry point. Registered as a method on both `pd.Series` and `pd.DataFrame` via `pandas_flavor`.

```python
import pandas as pd
from pandas_reconcile.aggregate import nested_aggregate  # registers the method

# series with MultiIndex: (nrg_bal, siec, unit, geo)
result = series.nested_aggregate({"AFC": ["NRGSUP", "TI_E", "TO", "NRG_E", "DL"]})
```

This appends rows for every internal tree node (e.g. `AFC`) by summing its children, bottom-up. Leaf rows are left unchanged. The result contains all original rows plus the newly computed aggregates.

---

### `total_aggregate(frame, tree)` — functional form

Lower-level version that accepts a `treelib.Tree` directly. Useful when you've already built a tree or need to reuse one across calls.

```python
from pandas_reconcile.aggregate import total_aggregate
from pandas_reconcile.tree import dict_to_tree

tree = dict_to_tree({"AFC": ["NRGSUP", "TI_E", "TO", "NRG_E", "DL"]})
result = total_aggregate(series, tree)
```

Aggregation is performed in reverse breadth-first order, so nodes closer to the leaves are summed before their parents consume those sums.

---

### `df_aggregate(frame, tree, name)` — single-node aggregate

Computes the aggregate for exactly one internal node `name`, summing its direct children.

```python
from pandas_reconcile.aggregate import df_aggregate

afc_row = df_aggregate(series, tree, "AFC")
```

Returns a `pd.Series` with the same index structure as `frame`, containing only the newly computed row for `name`.

---

### `check_sums(frame, tree, tol=0.3, omit=None)` — verify accounting identities

Validates that every internal node in `tree` equals the sum of its children within `frame`. Returns a dict of `{index: squared_relative_error}` for any entry that violates the identity beyond tolerance `tol`.

```python
from pandas_reconcile.aggregate import check_sums

errors = check_sums(frame, tree)
if errors:
    print("Accounting violations found:", errors)
```

Small absolute deviations on small values are handled gracefully — the tolerance is applied relative to the magnitude of the values. Use `omit` to skip specific nodes (e.g. when a node is known to be incomplete).

---

### `distribute_flows(frame, flow, dictionary, product, country)` — proportional redistribution

When you have a value at an aggregate node (e.g. `AFC`) and need to push it down to leaf nodes proportionally, use `distribute_flows`. It reads the current distribution of the leaves, computes proportions, and writes back scaled values.

```python
from pandas_reconcile.aggregate import distribute_flows

updated = distribute_flows(frame, flow="AFC", dictionary=tree, product="P8", country="FR")
```

If the leaves are all zero or NaN, the value is distributed uniformly. Pass `do_sum=True` to add to existing leaf values rather than replace them.

---

### `assoc_df(df, value, do_sum=False)` — immutable update helper

Updates a `pd.Series` or `pd.DataFrame` with new values at specific index positions, returning a new object. An outer join is used so that new index entries are added rather than silently dropped.

```python
from pandas_reconcile.aggregate import assoc_df

updated_series = assoc_df(original_series, patch_series)
```

---

### Tree utilities (`pandas_reconcile.tree`)

| Function                         | Description                                                                 |
|----------------------------------|-----------------------------------------------------------------------------|
| `dict_to_tree(dic)`              | Convert a parent→children dict to a `treelib.Tree`                          |
| `find_roots(dic)`                | Find all nodes that are not children of any other node                      |
| `build_subtree(root, dic, tree)` | Recursively attach a subtree to an existing `treelib.Tree` in place         |
| `node_names(nodes)`              | Extract `.tag` from a list of `treelib.Node` objects                        |
| `tree_omit(tree, to_omit)`       | Return a copy of the tree with specified nodes (and their subtrees) removed |
