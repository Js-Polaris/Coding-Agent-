import pytest

from inventory import add_item, low_stock, remove_item, total_value


def test_add_new_item():
    assert add_item({}, "pen", 3) == {"pen": 3}


def test_add_existing_item_accumulates():
    assert add_item({"pen": 3}, "pen", 2) == {"pen": 5}


def test_add_negative_raises():
    with pytest.raises(ValueError):
        add_item({}, "pen", -1)


def test_remove_to_zero_deletes_item():
    assert remove_item({"pen": 2}, "pen", 2) == {}


def test_remove_too_many_raises():
    with pytest.raises(ValueError):
        remove_item({"pen": 1}, "pen", 5)


def test_total_value_ignores_unpriced_items():
    # prices in UGX
    assert total_value({"pen": 2, "book": 1}, {"pen": 1500}) == 3000


def test_low_stock_is_strict_and_sorted():
    inventory = {"pen": 2, "book": 5, "bag": 1, "ruler": 10}
    assert low_stock(inventory) == ["bag", "pen"]
