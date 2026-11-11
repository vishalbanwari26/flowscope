STOCK = {"pen": 100, "notebook": 20, "lamp": 2}


def check(cart):
    for item, qty in cart.items():
        if STOCK.get(item, 0) < qty:
            raise ValueError(f"not enough {item}")


def reserve(cart):
    check(cart)
    for item, qty in cart.items():
        STOCK[item] -= qty
