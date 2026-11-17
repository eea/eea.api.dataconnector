"""utils"""

import math
from functools import wraps
from time import time
import logging

logger = logging.getLogger(__name__)


def parse_positive_float(value, default):
    """Return value as a positive finite float, or default if it is not one."""
    if value is None:
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number) or number <= 0:
        return default
    return number


def timing(f):
    """timing"""

    @wraps(f)
    def wrap(*args, **kw):
        """wrap"""
        ts = time()
        result = f(*args, **kw)
        te = time()
        logger.warning(
            "func:%r args:[%r, %r] took: %2.4f sec",
            f.__name__,
            args,
            kw,
            te - ts,
        )

        return result

    return wrap
