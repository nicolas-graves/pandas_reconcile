import collections
import csv
from typing import (
    cast,
    Any,
    Callable,
    Deque,
    Dict,
    List,
    Hashable,
    Iterable,
    Optional,
    Set,
    Tuple,
)
from treelib import Tree, Node


def build_subtree(root: Node, tree_dict: dict, tree: Tree):
    """Add subtree defined by tree_dict to tree at root in place."""
    for child in tree_dict[root]:
        tree.create_node(child, child, parent=root)
        if child in tree_dict:
            build_subtree(child, tree_dict, tree)


def find_roots(tree_dict: dict):
    """Given tree_dict, find all possible roots."""
    children = {child for values in tree_dict.values() for child in values}
    return [node for node in tree_dict.keys() if node not in children]


def dict_to_tree(tree_dict: dict, roots=None) -> Tree:
    """Convert nested dicts into treelib's Tree."""
    tree = Tree()
    if roots is None:
        roots = find_roots(tree_dict)
    if len(roots) > 1:
        tree.create_node(identifier="ROOT")
        for root in roots:
            tree.create_node(identifier=root, parent="ROOT")
            build_subtree(root, tree_dict, tree)
    else:
        tree.create_node(identifier=roots[0])
        build_subtree(roots[0], tree_dict, tree)
    return tree


def node_names(nodes: list[Node]):
    return list(map(lambda x: x.tag, nodes))


def tree_omit(t: Tree, to_omit: list[str]) -> Tree:
    new_tree = Tree(t.subtree(cast(str, t.root)), deep=True)
    for o in to_omit:
        if new_tree.contains(o):
            new_tree.remove_node(o)
    return new_tree
