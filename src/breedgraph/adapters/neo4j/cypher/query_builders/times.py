# Observation times are stored as LocalDateTime with the numpy unit and step they were given to, in <time>_unit and
# <time>_step (see domain.model.time_descriptors). A time stands for the whole period of its unit: as a start it is
# the start of that period, as an end the start of the next.

# numpy datetime units and the duration field of each
_DURATION_FIELDS = {
    'Y': 'years', 'M': 'months', 'W': 'weeks', 'D': 'days',
    'h': 'hours', 'm': 'minutes', 's': 'seconds',
    'ms': 'milliseconds', 'us': 'microseconds', 'ns': 'nanoseconds'
}


def upper(time: str) -> str:
    """
    The end (exclusive) of the period a stored time stands for, e.g. 2022-01-01 for a time stored to the year 2021;
    null stays null. time is a property, e.g. 'record.end', with its unit and step in 'record.end_unit' and
    'record.end_step'
    """
    cases = ' '.join(
        f"WHEN '{unit}' THEN duration({{{field}: {time}_step}})" for unit, field in _DURATION_FIELDS.items()
    )
    return f"({time} + CASE {time}_unit {cases} END)"


def entered(time: str) -> str:
    """A stored time as it was entered, [time, unit, step], so it reads back at its precision"""
    return f"[{time}, {time}_unit, {time}_step]"
