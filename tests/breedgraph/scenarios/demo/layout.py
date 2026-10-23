"""
The demonstration's field trials (story.PLANS) laid out: every treatment once in each block, in an order drawn for the
block from a hash of the trial, block and treatment, so a layout never changes from one build to the next and adding a
trial changes no other. Plots are named <prefix>-<block><number>, numbered within their block row by row, so their
names sort as they are built, read and entered: LM26-101 to LM26-112 for block 1 of the 2026 trial.
"""
import hashlib
from dataclasses import dataclass
from functools import cache
from typing import List

from .story import PLANS, SELECTION

DRAW_SEED = 'breedgraph demonstration 1'


@dataclass(frozen=True)
class Plot:
    name: str
    trial: str  # a plan key
    block: int
    number: int  # within the block, from 1
    row: int
    column: int
    entry: str  # a germplasm key
    nitrogen: int | None  # kg N/ha, or None where nitrogen is not a treatment


def draw(*parts) -> int:
    """A number for these parts, the same in every build"""
    return int.from_bytes(hashlib.sha256('|'.join(map(str, (DRAW_SEED, *parts))).encode()).digest()[:8], 'big')


@cache
def plots(trial: str) -> List[Plot]:
    plan = PLANS[trial]
    laid_out = []
    for block in range(1, plan.blocks + 1):
        order = sorted(plan.treatments, key=lambda treatment: draw(trial, block, *treatment))
        for number, (entry, rate) in enumerate(order, start=1):
            row, column = divmod(number - 1, plan.columns)
            laid_out.append(Plot(
                name=f"{plan.prefix}-{block}{number:02d}", trial=trial, block=block, number=number,
                row=row + 1, column=column + 1, entry=entry, nitrogen=rate
            ))
    return laid_out


def plot(trial: str, name: str) -> Plot:
    return next(p for p in plots(trial) if p.name == name)


def plot_of(trial: str, entry: str, nitrogen: int | None, block: int) -> Plot:
    return next(p for p in plots(trial) if (p.entry, p.nitrogen, p.block) == (entry, nitrogen, block))


def selection_plot() -> Plot:
    """The 2025 plot whose plant was selected (story.SELECTION)"""
    return plot_of(*SELECTION)


def selection_plant_name() -> str:
    return f"{selection_plot().name} plant 1"


def grain_sample_name(plot_name: str) -> str:
    return f"{plot_name} grain"
