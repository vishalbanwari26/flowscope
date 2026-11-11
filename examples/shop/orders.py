import itertools

import mailer
import pricing
import stock

_ids = itertools.count(1)


def place(cart):
    stock.reserve(cart)
    order_id = next(_ids)
    return mailer.receipt(order_id, pricing.total(cart))
