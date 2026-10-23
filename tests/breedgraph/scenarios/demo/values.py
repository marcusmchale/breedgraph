"""
The values of the demonstration's records, made from a model of the trials rather than drawn at random, and its
documents. A value is its year's mean plus the effects of its entry, nitrogen rate and block, plus noise taken from a
hash of what it is (SHA-256, mapped to a normal quantile), so a value never changes from one build to the next and
adding a plot changes no other. The effects give the guide's analyses something to find: the entries and nitrogen
rates differ in height and yield, and the scores in Septoria.

Also here: the 2026 observations the guide enters, with their typo; the NIR spectra, as CSV files; and the documents:
the licences and the field plans.
"""
import hashlib
from math import exp
from datetime import date, timedelta
from statistics import NormalDist
from typing import Dict, List, Tuple

from .layout import Plot, plots, grain_sample_name
from .story import PLANS, TYPO, PARTNER_LICENCE, COOPERATIVE_PLOTS, GERMPLASM, PLACES, STUDIES, TRIALS

VALUE_SEED = 'breedgraph demonstration values 1'

# The effects of each entry: on yield (t/ha), height (cm), heading (days), Septoria (score), thousand grain weight (g)
# and protein (percent)
ENTRY_EFFECTS: Dict[str, Tuple[float, float, float, float, float, float]] = {
    'copperwren': (0.4, 2, 0, 1.8, 0.0, -0.3),
    'fernhollow': (-0.5, -1, 2, -1.5, 1.5, 0.2),
    'brindlecrest': (-0.2, 9, -3, 0.5, 2.0, -0.1),
    'larkmere': (-0.6, -7, 1, 0.0, -1.5, 0.8),
    'quillsprig': (-0.3, 1, -4, 0.8, 0.5, 0.0),
    'harrowgold': (-0.1, 3, 4, 0.2, 0.3, -0.2),
    'epb_19_031': (0.3, 0, 1, -0.8, 0.5, 0.0),
    'epb_19_047': (0.0, 3, -2, 0.3, 1.0, 0.3),
    'epb_19_052': (0.1, -4, 0, 0.5, -0.5, 0.4),
    'epb_19_066': (-0.3, 5, 3, -0.3, 0.8, -0.2),
    'epb_21_014': (0.7, -2, 1, -1.6, 1.2, 0.1),
    'epb_21_022': (0.2, 1, 0, -0.4, 0.0, 0.5),
    'epb_21_038': (-0.1, -5, -1, 1.0, -1.0, 0.6),
    'epb_25_s03': (0.8, -3, 1, -2.2, 1.0, 0.2),
}
TRAIT_INDEX = {'yield': 0, 'height': 1, 'heading': 2, 'septoria': 3, 'grain_weight': 4, 'protein': 5}

# Each year's means, for the trial of that year
YEAR_MEANS = {
    'lm24': {'yield': 10.2, 'height': 88, 'septoria': 3.5},
    'nf25': {'yield': 9.4, 'height': 84, 'septoria': 5.0, 'grain_weight': 46.0, 'protein': 12.0},
    'lm26': {'yield': 9.8, 'height': 86, 'septoria': 4.0},
    'coop': {'yield': 9.0},
}
# Half of the ears had emerged on these days, give or take an entry's effect
HEADING_DAYS = {'lm24': date(2024, 6, 1), 'nf25': date(2025, 6, 5), 'lm26': date(2026, 6, 3)}

# The effects of the lower nitrogen rate, 120 against 200 kg N/ha; two entries lose half the yield the others do
LOW_NITROGEN = {'yield': -1.1, 'height': -4, 'septoria': -0.4, 'grain_weight': 0.4, 'protein': -0.9}
LOW_NITROGEN_HARDY = {'larkmere', 'epb_21_038'}
BLOCK_EFFECTS = {'yield': (0.2, 0.0, -0.2), 'height': (1, 0, -1)}
NOISE = {'yield': 0.35, 'height': 2.0, 'heading': 0.8, 'septoria': 0.6, 'grain_weight': 0.8, 'protein': 0.25}
# Each of a sample's two grain counts differs from the sample's own weight by this much
COUNT_NOISE = 0.4
# Yield falls by this much for each point of Septoria above the year's mean
SEPTORIA_YIELD_LOSS = 0.15


def noise(key: str, sd: float) -> float:
    """A normal deviate with this standard deviation, from a hash of the key, the same in every build"""
    digest = hashlib.sha256(f"{VALUE_SEED}|{key}".encode()).digest()
    uniform = (int.from_bytes(digest[:8], 'big') + 0.5) / 2 ** 64
    return sd * NormalDist().inv_cdf(uniform)


def _latent(trait: str, plot: Plot, year: str) -> float:
    value = YEAR_MEANS[year][trait] + ENTRY_EFFECTS[plot.entry][TRAIT_INDEX[trait]]
    if plot.nitrogen is not None and plot.nitrogen < 200:
        effect = LOW_NITROGEN.get(trait, 0)
        value += effect / 2 if trait == 'yield' and plot.entry in LOW_NITROGEN_HARDY else effect
    value += BLOCK_EFFECTS.get(trait, (0, 0, 0))[plot.block - 1]
    return value + noise(f"{trait}|{plot.name}", NOISE[trait])


def septoria_latent(plot: Plot) -> float:
    return _latent('septoria', plot, plot.trial)


def septoria_score(plot: Plot) -> str:
    return str(min(9, max(1, round(septoria_latent(plot)))))


def height(plot: Plot) -> str:
    return str(round(_latent('height', plot, plot.trial)))


def grain_yield(plot: Plot) -> str:
    year = plot.trial
    loss = SEPTORIA_YIELD_LOSS * (septoria_latent(plot) - YEAR_MEANS[year]['septoria'])
    return f"{_latent('yield', plot, year) - loss:.2f}"


def heading_date(plot: Plot) -> str:
    days = ENTRY_EFFECTS[plot.entry][TRAIT_INDEX['heading']] + noise(f"heading|{plot.name}", NOISE['heading'])
    return (HEADING_DAYS[plot.trial] + timedelta(days=round(days))).isoformat()


def grain_weights(plot: Plot) -> Tuple[str, str]:
    """The two counts of a 2025 plot's grain sample, in grams per thousand grains"""
    weight = _latent('grain_weight', plot, 'nf25')
    return tuple(
        f"{weight + noise(f'count {count}|{plot.name}', COUNT_NOISE):.1f}" for count in (1, 2)
    )


def protein(plot: Plot) -> str:
    return f"{_latent('protein', plot, 'nf25'):.1f}"


def nir_batch(plot: Plot) -> str:
    """The NIR run a 2025 sample was measured in: blocks 1 and 2 in the first, block 3 in the second"""
    return "Run 1" if plot.block < 3 else "Run 2"


# The value of each concept of a plot, by the story's dataset concepts
PLOT_VALUES = {
    'height': height,
    'heading': heading_date,
    'septoria': septoria_score,
    'yield': grain_yield,
    'nitrogen_rate': lambda plot: str(plot.nitrogen),
    'fungicide_programme': lambda plot: "Two sprays",
}


def plot_values(trial: str, concept: str) -> List[Tuple[str, str]]:
    """(plot name, value) for every plot of a trial"""
    return [(plot.name, PLOT_VALUES[concept](plot)) for plot in plots(trial)]


def cooperative_yields() -> List[Tuple[str, str]]:
    mean = YEAR_MEANS['coop']['yield'] + ENTRY_EFFECTS[COOPERATIVE_PLOTS['entry']][TRAIT_INDEX['yield']]
    return [(name, f"{mean + noise(f'yield|{name}', NOISE['yield']):.2f}") for name in COOPERATIVE_PLOTS['plots']]


# The 2026 observations the guide enters ----------------------------------------------------------------------------

def planned_2026() -> Dict[str, List[Tuple[str, str]]]:
    """By concept: (plot, value) in plot order, as the guide pastes them; LM26-207's height has the typo"""
    planned = {concept: plot_values('lm26', concept) for concept in ('height', 'septoria', 'nitrogen_rate')}
    plot_name, concept = TYPO
    planned[concept] = [(name, typed(value) if name == plot_name else value) for name, value in planned[concept]]
    return planned


def typed(value: str) -> str:
    """The typo: an extra zero"""
    return value + '0'


def correct_2026(concept: str, plot_name: str) -> str:
    return dict(plot_values('lm26', concept))[plot_name]


# NIR spectra ----------------------------------------------------------------------------------------------------------

WAVELENGTHS = range(1100, 2500, 2)
# Absorption bands of grain: centre (nm), width (nm), depth; the protein band's depth follows the sample's protein
BANDS = ((1200, 40, 0.06), (1450, 60, 0.18), (1940, 70, 0.25), (2100, 60, 0.12))
PROTEIN_BAND = (2180, 30, 0.012)


def nir_spectrum(plot: Plot) -> bytes:
    """A 2025 grain sample's reflectance by wavelength, as CSV"""
    centre, width, depth = PROTEIN_BAND
    bands = (*BANDS, (centre, width, depth * float(protein(plot))))
    lines = ["wavelength_nm,reflectance"]
    for wavelength in WAVELENGTHS:
        absorbance = 0.25 + 0.00008 * (wavelength - 1100)
        absorbance += sum(d * exp(-((wavelength - c) / w) ** 2) for c, w, d in bands)
        absorbance += noise(f"nir|{plot.name}|{wavelength}", 0.002)
        lines.append(f"{wavelength},{pow(10, -absorbance):.4f}")
    return ('\n'.join(lines) + '\n').encode()


def nir_filename(plot: Plot) -> str:
    return f"{plot.name.lower()}-nir.csv"


# Documents ------------------------------------------------------------------------------------------------------------

DEMONSTRATION = "This is a demonstration licence, for fictional data."

ONTOLOGY_LICENCE = (
    "The Example Plant Breeding Institute's wheat ontology may be used, shared and adapted by anyone, with credit "
    f"to the Institute. {DEMONSTRATION}"
)
ONTOLOGY_COPYRIGHT = "Copyright 2024 Example Plant Breeding Institute. The Institute and its ontology are fictional."

OPEN_LICENCE = f"""# Example Open Data Licence

You may use, share and adapt the data of this study, for any purpose, if you:

- credit the Example Plant Breeding Institute, and the people credited with each dataset;
- say whether you changed the data;
- pass these terms on with the data.

The data come as they are, without warranty.

*{DEMONSTRATION}*
"""


def field_plan_pdf(trial: str) -> bytes:
    """A trial's plan, plot by plot, as a PDF of plain lines (ASCII)"""
    from tests.breedgraph.utilities.documents import pdf_with_text

    plan = PLANS[trial]
    study = next(study for study in STUDIES.values() if study.start == plan.sown)
    header = [
        f"{study.name}: field plan",
        f"{PLACES[plan.field].name}, sown {plan.sown}, {plan.blocks} randomised complete blocks",
        "",
    ]
    lines = [
        f"{p.name}  block {p.block}  row {p.row}  column {p.column}  {GERMPLASM[p.entry].name}"
        + (f"  {p.nitrogen} kg N/ha" if p.nitrogen is not None else '')
        for p in plots(trial)
    ]
    pages, per_page = [], 40
    for start in range(0, len(lines), per_page):
        pages.append('\n'.join((header if not pages else []) + lines[start:start + per_page]))
    return pdf_with_text(*pages)


def partner_licence_pdf() -> bytes:
    """The licence the guide gives the 2025 study when it is shared with the Cooperative, uploaded as a PDF"""
    from tests.breedgraph.utilities.documents import pdf_with_text

    name, _ = PARTNER_LICENCE
    trial = TRIALS['trial_2025'].name
    return pdf_with_text(
        f"{name}\n"
        "Example Plant Breeding Institute and Example Seed Cooperative\n"
        "\n"
        f"The data of the {trial} are licensed to registered users of BreedGraph,\n"
        "to evaluate the lines for seed multiplication.\n"
        "\n"
        "1. Credit the Example Plant Breeding Institute in any report of the data.\n"
        "2. Pass the data on only to registered users of BreedGraph, with this licence.\n"
        "3. Do not publish the data before the Institute does.\n"
        "\n"
        f"{DEMONSTRATION}"
    )


def nir_uploads() -> List[Tuple[Plot, bytes]]:
    """The spectra the guide uploads (workflow 18): the first eight samples of block 2"""
    return [(plot, nir_spectrum(plot)) for plot in nir_plots(block=2)]


def nir_plots(block: int) -> List[Plot]:
    return [plot for plot in plots('nf25') if plot.block == block][:8]


def sample_names(trial: str = 'nf25') -> List[str]:
    return [grain_sample_name(plot.name) for plot in plots(trial)]
