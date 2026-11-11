import pytest

import orders
import pricing
import stock


def test_small_order_gets_a_receipt():
    assert orders.place({"pen": 2}) == "Order 1: 3.00 EUR"


def test_ten_items_get_a_discount():
    assert pricing.total({"pen": 10}) == 1350


def test_order_for_more_than_is_in_stock_is_refused():
    with pytest.raises(ValueError):
        orders.place({"lamp": 5})


def test_stock_check_passes_for_what_is_there():
    stock.check({"notebook": 3})


def test_mixed_cart_total():
    assert pricing.total({"pen": 1, "notebook": 1, "lamp": 1}) == 3800
