import pytest
from treelib import Tree
import pandas_reconcile.tree as stree


@pytest.fixture
def tree_dict():
    return {"A": ["B", "C"], "B": ["D", "E"], "C": ["F"]}


@pytest.fixture
def expected_tree_dict():
    return {
        "A": {"children": [{"B": {"children": ["D", "E"]}}, {"C": {"children": ["F"]}}]}
    }


@pytest.fixture
def tree_dict_with_multiple_roots():
    return {"A": ["B"], "C": ["D"]}


def test_build_subtree(tree_dict, expected_tree_dict):
    tree = Tree()
    tree.create_node("A", "A")  # Root node

    stree.build_subtree("A", tree_dict, tree)

    assert tree.to_dict() == expected_tree_dict


def test_find_roots(tree_dict, tree_dict_with_multiple_roots):
    assert stree.find_roots(tree_dict) == ["A"]
    assert sorted(stree.find_roots(tree_dict_with_multiple_roots)) == ["A", "C"]


def test_dict_to_tree(tree_dict, expected_tree_dict, tree_dict_with_multiple_roots):
    tree = stree.dict_to_tree(tree_dict)
    assert tree.to_dict() == expected_tree_dict

    tree_with_roots = stree.dict_to_tree(tree_dict_with_multiple_roots)
    assert tree_with_roots.contains("ROOT")
    assert tree_with_roots.contains("A")
    assert tree_with_roots.contains("C")


def test_node_names(tree_dict):
    tree = Tree()
    tree.create_node("A", "A")
    tree.create_node("B", "B", parent="A")
    tree.create_node("C", "C", parent="A")
    nodes = [tree.get_node("A"), tree.get_node("B"), tree.get_node("C")]

    assert stree.node_names(nodes) == ["A", "B", "C"]


def test_tree_omit(tree_dict):
    tree = Tree()
    tree.create_node("A", "A")
    tree.create_node("B", "B", parent="A")
    tree.create_node("C", "C", parent="A")
    tree.create_node("D", "D", parent="B")

    # Omitting node "B" and its descendants
    new_tree = stree.tree_omit(tree, ["B"])
    assert not new_tree.contains("B")
    assert not new_tree.contains("D")
    assert new_tree.contains("A")
    assert new_tree.contains("C")

    # Omitting a non-existent node
    unchanged_tree = stree.tree_omit(tree, ["X"])
    assert unchanged_tree.contains("A")
    assert unchanged_tree.contains("B")
    assert unchanged_tree.contains("C")
    assert unchanged_tree.contains("D")
