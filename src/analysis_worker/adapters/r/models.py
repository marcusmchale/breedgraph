"""
rpy2 bridge to models.R.

Embedded R is not thread safe: call from a single thread, the main thread of a worker process.
"""
from collections import OrderedDict
from functools import lru_cache, wraps
from pathlib import Path

import pandas as pd

R_SOURCE = Path(__file__).with_name('models.R')


class RError(Exception):
    """An error raised by R"""


@lru_cache(maxsize=1)
def _r():
    import rpy2.robjects as ro
    ro.r.source(str(R_SOURCE))
    return ro


def converting(func):
    """
    rpy2 conversion rules are held in a context variable set on import,
    which contexts copied before the import (e.g. asyncio tasks) do not have.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        ro = _r()
        from rpy2.robjects.conversion import localconverter
        with localconverter(ro.default_converter):
            return func(*args, **kwargs)
    return wrapper


def _to_pandas(r_frame) -> pd.DataFrame:
    ro = _r()
    from rpy2.robjects import pandas2ri
    from rpy2.robjects.conversion import localconverter
    with localconverter(ro.default_converter + pandas2ri.converter):
        frame = ro.conversion.get_conversion().rpy2py(r_frame)
    for name in frame.columns:
        # factors are converted to categoricals, missing values to NaN
        if isinstance(frame[name].dtype, pd.CategoricalDtype):
            frame[name] = frame[name].astype(object)
    return frame.reset_index(drop=True)


@converting
def to_r_frame(frame: pd.DataFrame, kinds: dict[str, str]):
    """
    :param kinds: column name -> CONTINUOUS, CATEGORICAL or ORDINAL; categorical columns must be pandas categoricals
    """
    ro = _r()
    columns = OrderedDict()
    for name, kind in kinds.items():
        values = frame[name]
        if kind == 'CONTINUOUS':
            columns[name] = ro.FloatVector([ro.NA_Real if pd.isna(v) else float(v) for v in values])
        else:
            levels = [str(level) for level in values.cat.categories]
            columns[name] = ro.FactorVector(
                ro.StrVector([ro.NA_Character if pd.isna(v) else str(v) for v in values]),
                levels=ro.StrVector(levels),
                ordered=kind == 'ORDINAL'
            )
    return ro.DataFrame(columns)


def _call(function: str, *args, **kwargs):
    ro = _r()
    from rpy2.rinterface_lib.embedded import RRuntimeError
    try:
        return ro.globalenv[function](*args, **kwargs)
    except RRuntimeError as e:
        raise RError(str(e).strip()) from e


@converting
def fit_anova(data, formula: str, mixed: bool, ss_type: int, ddf: str) -> dict:
    result = _call('fit_anova', data, formula, mixed, ss_type, ddf)
    return {
        'model': result.rx2('model'),
        'table': _to_pandas(result.rx2('table')),
        'random': _to_pandas(result.rx2('random')),
        'residual': _to_pandas(result.rx2('residual')),
        'warnings': list(result.rx2('warnings')),
    }


@converting
def estimated_means(model, specs: list[str], by: list[str], contrast: str, ref: int, adjust: str, level: float, ddf: str) -> dict:
    ro = _r()
    result = _call(
        'estimated_means', model, ro.StrVector(specs), ro.StrVector(by), contrast, ref, adjust, level, ddf
    )
    contrasts = result.rx2('contrasts')
    return {
        'means': _to_pandas(result.rx2('means')),
        'contrasts': _to_pandas(contrasts) if contrasts is not ro.NULL else None,
    }
