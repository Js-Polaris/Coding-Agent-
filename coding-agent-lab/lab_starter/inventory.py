"""A tiny shop inventory module. It has bugs: the tests in test_inventory.py show what it should do."""


def add_item(inventory, name, qty):
    """Add qty units of name to the inventory dict and return the inventory."""
    if qty < 0:
        raise ValueError("qty must be non-negative")
    inventory[name] = qty
    return inventory


def remove_item(inventory, name, qty):
    """Remove qty units of name.
    Raises KeyError if the item is missing and ValueError if there is not enough stock.
    Deletes the item when its stock reaches zero."""
    if name not in inventory:
        raise KeyError(name)
    if inventory[name] < qty:
        raise ValueError("not enough stock")
    inventory[name] -= qty
    if inventory[name] < 0:
        del inventory[name]
    return inventory


def total_value(inventory, prices):
    """Return the sum of qty * price for every item. Items with no price count as 0."""
    total = 0
    for name, qty in inventory.items():
        total += qty * prices[name]
    return total


def low_stock(inventory, threshold=5):
    """Return the names of items with stock strictly below threshold, sorted A-Z."""
    return [name for name, qty in inventory.items() if qty <= threshold]
