from catalog import price_of


def subtotal(cart):
    return sum(price_of(item) * qty for item, qty in cart.items())


def discount(cart):
    return 10 if sum(cart.values()) >= 10 else 0


def total(cart):
    sub = subtotal(cart)
    return sub - sub * discount(cart) // 100
