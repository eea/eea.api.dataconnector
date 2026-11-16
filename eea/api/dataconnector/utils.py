"""utils"""

import math
from functools import wraps
from time import time
import logging

logger = logging.getLogger(__name__)


def parse_positive_float(value, default):
    """Return ``value`` as a positive finite float, else ``default``."""
    if value is None:
        return default
    try:
        parsed = float(value)
        if math.isfinite(parsed) and parsed > 0:
            return parsed
    except (ValueError, TypeError):
        pass
    return default


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
