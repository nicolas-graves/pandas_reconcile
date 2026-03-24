
# tree_sum

**Python pandas flavor for simple hierarchical aggregation**

In economics and other sciences, we often need to keep correct sums because they are accounting identities. In some of those cases, we want to patch, manipulate and modify the underlying data, but be 100% sure the accounting identity stays correct, some of which can be nested.

A natural way to store nested accounting identities is using trees.

This library provides tools to manipulate dataframes with accounting identities correctly.
