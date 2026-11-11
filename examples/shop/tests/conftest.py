import itertools

import pytest

import orders
import stock


@pytest.fixture(autouse=True)
def fresh_shop():
    """Every test starts with the same stock and order numbers."""
    stock.STOCK.update({"pen": 100, "notebook": 20, "lamp": 2})
    orders._ids = itertools.count(1)
