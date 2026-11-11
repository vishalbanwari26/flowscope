import time

PRICES = {"pen": 150, "notebook": 450, "lamp": 3200}


def price_of(item):
    time.sleep(0.01)          # stands in for a database lookup
    return PRICES[item]
