"""
The demonstration database's story: fictional winter wheat trials in Ireland, in plain English, for the University's
data protection and legal offices and for showing BreedGraph to outside users (docs/demo-database.md). This module is
data only: builder.py writes it, layout.py lays out the trials and values.py makes their values and documents.

Everything is invented. People have alliterative role names (Bridget Breeder, Theo Technician), so a viewer can tell
who is acting; their addresses are at example.org, which is reserved (RFC 2606); the sites' coordinates are offsets
from points on open bog, far from any building or road, so no real farm or person is described; and the varieties'
names are checked against the variety catalogues before a build is shared (scripts/check_demo_names.py).

Teams and their members (R read, W write, C curate, A admin; + heritable)

    Example Plant Breeding Institute (institute)    dara A+ R+ C+ W
    ├── Wheat Breeding Group (breeding)             bridget R W C A; theo R; lena R
    ├── Field Operations (field)                    theo R W C; bridget R; lena R; rita R W (account deleted)
    └── Grain Quality Lab (lab)                     lena R W C A; bridget R
    Example Seed Cooperative (cooperative)          petra A+ R+ C+ W

Places (team, release)

    Ireland (institute, public)
    ├── County Offaly (institute, public)
    │   └── Example Research Farm (institute, public)
    │       ├── Long Meadow (field, public): the 2024 and 2026 trials
    │       ├── North Field (field, public): the 2025 trial
    │       ├── Glasshouse (field, private): benches
    │       └── Grain Quality Laboratory (lab, registered)
    │           └── Sample Freezer (lab, private): a rack of shelves and boxes
    └── County Kildare (cooperative, public)
        └── Cooperative Seed Farm (cooperative, private)
            └── Seed Field (cooperative, private)

Programmes (team, release)

    Winter Wheat Breeding Programme (breeding, public)
    ├── Preliminary Yield Trial 2024 (public)
    │   └── Long Meadow Yield Trial 2024 (public, licensed): what visitors see
    └── Advanced Yield Trial 2025 (private)
        ├── North Field Yield Trial 2025 (private): shared with the Cooperative in the guide
        └── Grain Quality 2025 (private): the lab's measurements of the 2025 grain
    Cooperative Seed Multiplication (cooperative, private)
    └── Seed Multiplication 2025 (private)
        └── Seed Field Multiplication 2025 (private)

The 2026 plots are sown in Long Meadow, from 2025-10-16, with no trial or study for them yet: the guide creates those
(the "this season" chain in manifest.py). Hill Field is not built either: the guide adds it for 2027.
"""
from dataclasses import dataclass
from typing import Dict, Tuple

from breedgraph.domain.model.accounts import OntologyRole
from breedgraph.domain.model.controls import Access, ReadRelease
from breedgraph.domain.model.germplasm import GermplasmSourceType, Reproduction
from breedgraph.domain.model.ontology import (
    AxisType, ControlMethodType, ObservationMethodType, RecordGroupExtent, ScaleType
)
from breedgraph.domain.model.programs import GroupingScope

# Raised when the story changes in a way the guide's recordings depend on (names, plots, values)
STORY_VERSION = 1

PUBLIC, REGISTERED, PRIVATE = ReadRelease.PUBLIC, ReadRelease.REGISTERED, ReadRelease.PRIVATE
READ, WRITE, CURATE, ADMIN = Access.READ, Access.WRITE, Access.CURATE, Access.ADMIN
ALL = (READ, WRITE, CURATE, ADMIN)

INSTITUTE = "Example Plant Breeding Institute"
COOPERATIVE = "Example Seed Cooperative"
MAIL_DOMAIN = "example.org"


# Teams ----------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Team:
    name: str
    parent: str | None = None  # None for the root of a team tree
    owner: str | None = None  # the account that creates a team tree


TEAMS: Dict[str, Team] = {
    'institute': Team(INSTITUTE, owner='dara'),
    'breeding': Team("Wheat Breeding Group", parent='institute'),
    'field': Team("Field Operations", parent='institute'),
    'lab': Team("Grain Quality Lab", parent='institute'),
    'cooperative': Team(COOPERATIVE, owner='petra'),
}


# Accounts -------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Account:
    fullname: str
    job: str
    ontology_role: OntologyRole = OntologyRole.CONTRIBUTOR
    # team: the accesses its admin grants (a tree's owner grants their own)
    affiliations: Dict[str, Tuple[Access, ...]] = None
    # teams whose affiliations hold for the teams below too; write is never heritable
    heritable: Tuple[str, ...] = ()
    write_team: str | None = None  # the default write team
    ontology_role_requested: OntologyRole | None = None
    deleted: bool = False  # the account is deleted at the end of the build, its Person kept

    @property
    def email(self) -> str:
        return f"{self.fullname.lower().replace(' ', '.')}@{MAIL_DOMAIN}"


# The username is the key
ACCOUNTS: Dict[str, Account] = {
    'dara': Account(
        "Dara Data", "Data manager", OntologyRole.ADMIN,
        affiliations={'institute': ALL}, heritable=('institute',), write_team='institute'
    ),
    'bridget': Account(
        "Bridget Breeder", "Programme lead", OntologyRole.EDITOR,
        affiliations={'breeding': ALL, 'field': (READ,), 'lab': (READ,)}, write_team='breeding'
    ),
    'theo': Account(
        "Theo Technician", "Field technician",
        affiliations={'field': (READ, WRITE, CURATE), 'breeding': (READ,)}, write_team='field',
        ontology_role_requested=OntologyRole.EDITOR
    ),
    'lena': Account(
        "Lena Lab", "Lab manager",
        affiliations={'lab': ALL, 'breeding': (READ,), 'field': (READ,)}, write_team='lab'
    ),
    'petra': Account(
        "Petra Partner", "Cooperative manager",
        affiliations={'cooperative': ALL}, heritable=('cooperative',), write_team='cooperative'
    ),
    'rita': Account(
        "Rita Retired", "Former field technician",
        affiliations={'field': (READ, WRITE)}, write_team='field', deleted=True
    ),
}


# People ---------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Person:
    name: str
    team: str  # the controlling team
    release: ReadRelease  # at most REGISTERED: there are no public people
    institution: str | None = INSTITUTE
    teams: Tuple[str, ...] = ()  # the teams it is affiliated with, for attribution
    account: str | None = None  # the account linked to it
    claimant: str | None = None  # an account that asks to be linked to it, and is still waiting
    erased: bool = False  # erased at the end of the build


PEOPLE: Dict[str, Person] = {
    'person_dara': Person("Dara Data", 'institute', REGISTERED, teams=('institute',), account='dara'),
    'person_bridget': Person("Bridget Breeder", 'breeding', REGISTERED, teams=('breeding',), account='bridget'),
    'person_theo': Person("Theo Technician", 'field', REGISTERED, teams=('field',), account='theo'),
    'person_lena': Person("Lena Lab", 'lab', REGISTERED, teams=('lab',), account='lena'),
    'person_rita': Person("Rita Retired", 'field', REGISTERED, teams=('field',), account='rita'),
    # credited for the seed the Cooperative supplied, before Petra had an account: she has asked to be linked to it
    'person_petra': Person("Petra Partner", 'breeding', REGISTERED, institution=COOPERATIVE, claimant='petra'),
    'person_fergus': Person("Fergus Fieldhand", 'field', PRIVATE, teams=('field',)),
    # a summer student credited in 2025, offered to Nina when she is invited (the joining chain)
    'person_nina': Person("Nina Newcomer", 'breeding', PRIVATE, teams=('breeding',)),
    # built under a neutral name, so the name a real erasure would remove is in no transaction log
    'person_erased': Person("Former Seasonal Worker", 'field', REGISTERED, institution=None, erased=True),
}


# Ontology -------------------------------------------------------------------------------------------------------------
# By key: the name, then what defines it. Every entry has a description, so the ontology page reads as a glossary.

# The location types, below the seeded Country type (key 'country')
LOCATION_TYPES = {
    'county': ("County", ('country',), "A county of a country, its first administrative division"),
    'farm': ("Farm", ('county',), "A farm or research station, holding fields and buildings"),
    'field': ("Field", ('farm',), "A field, where trials are sown"),
    'glasshouse': ("Glasshouse", ('farm',), "A glasshouse, for plants grown under cover"),
    'laboratory': ("Laboratory", ('farm',), "A laboratory, where samples are measured"),
    'cold_store': ("Cold store", ('laboratory',), "A freezer or cold room, where samples are kept"),
}

# The layout types: their axes' types; each layout names its own axes
LAYOUT_TYPES = {
    'trial_blocks': ("Field trial blocks", (AxisType.ORDINAL,), "The blocks of a field trial, numbered"),
    'plot_grid': ("Plot grid", (AxisType.ORDINAL, AxisType.ORDINAL), "Plots in numbered rows and columns"),
    'freezer_rack': (
        "Freezer rack", (AxisType.ORDINAL, AxisType.NOMINAL), "The numbered shelves of a freezer, holding named boxes"
    ),
    'bench_layout': ("Bench layout", (AxisType.NOMINAL,), "The named benches of a glasshouse"),
}

DESIGNS = {
    'rcbd': (
        "Randomised complete block", ("RCBD",),
        "Each block holds every treatment once, in an order drawn at random for each block"
    ),
}

RECORD_GROUP_TYPES = {
    'replicate': (
        "Replicate", RecordGroupExtent.WITHIN_UNIT, "Repeated measurements of the same unit, such as counts of one sample"
    ),
    'batch': ("Batch", RecordGroupExtent.SHARED, "Samples measured together, such as in one run of an instrument"),
}

SUBJECTS = {
    'field': ("Field", (), "A field, or the area of a trial in it"),
    'plot': ("Plot", ('field',), "A plot of a field trial, sown with one entry"),
    'plant': ("Plant", ('plot',), "A single plant"),
    'grain_sample': ("Grain sample", ('plot',), "Grain harvested from a plot"),
    'flour_sample': ("Flour sample", ('grain_sample',), "Flour milled from a grain sample"),
    'seedling': ("Seedling", (), "A seedling grown from seed"),
}

OBSERVATION_METHODS = {
    'ruler': (
        "Ruler measurement", ObservationMethodType.MEASUREMENT,
        "Measured with a ruler from the ground to the tip of the ears, leaving out the awns"
    ),
    'visual': ("Visual assessment", ObservationMethodType.ESTIMATION, "Judged by eye across the whole plot"),
    'combine': (
        "Plot combine harvest", ObservationMethodType.MEASUREMENT,
        "Grain weighed on the plot combine, then corrected to 15 percent moisture"
    ),
    'grain_count': (
        "Grain count and weighing", ObservationMethodType.MEASUREMENT, "A thousand grains counted, then weighed"
    ),
    'nir_prediction': (
        "NIR prediction", ObservationMethodType.PREDICTION,
        "Predicted from the near-infrared spectrum of the grain, with the lab's calibration"
    ),
    'nir_scan': (
        "NIR scan", ObservationMethodType.MEASUREMENT, "The near-infrared reflectance spectrum of a grain sample"
    ),
}

# key: (name, abbreviation, scale type, description, categories as (name, description))
SEPTORIA_CATEGORIES = (
    ("1", "No symptoms"),
    ("2", "A few lesions on the lower leaves"),
    ("3", "Lesions on the lower leaves"),
    ("4", "Lesions reaching the leaf below the flag leaf"),
    ("5", "About a tenth of the upper leaf area affected"),
    ("6", "About a quarter of the upper leaf area affected"),
    ("7", "About half of the upper leaf area affected"),
    ("8", "Most of the upper leaf area affected"),
    ("9", "The upper leaves dead"),
)
FUNGICIDE_CATEGORIES = (
    ("Untreated", "No fungicide"),
    ("Two sprays", "Fungicide at flag leaf emergence and at ear emergence"),
    ("Three sprays", "Fungicide at stem extension, flag leaf emergence and ear emergence"),
)
SCALES = {
    'centimetres': ("Centimetres", "cm", ScaleType.NUMERICAL, "Length in centimetres", ()),
    'date': ("Calendar date", None, ScaleType.DATE, "A day, written as year-month-day", ()),
    'tonnes_per_hectare': (
        "Tonnes per hectare", "t/ha", ScaleType.NUMERICAL, "Weight of grain in tonnes for each hectare harvested", ()
    ),
    'septoria_scale': (
        "Septoria severity (1 to 9)", None, ScaleType.ORDINAL,
        "Severity of Septoria leaf blotch, from 1 (no symptoms) to 9 (the upper leaves dead)", SEPTORIA_CATEGORIES
    ),
    'grams': ("Grams", "g", ScaleType.NUMERICAL, "Weight in grams", ()),
    'percent': ("Percent", "%", ScaleType.NUMERICAL, "Parts in a hundred, by weight", ()),
    'nir_file': (
        "NIR spectrum file", None, ScaleType.COMPLEX,
        "A CSV file of reflectance by wavelength, from 1100 to 2498 nanometres", ()
    ),
    'kg_nitrogen_per_hectare': (
        "Kilograms of nitrogen per hectare", "kg N/ha", ScaleType.NUMERICAL,
        "Nitrogen applied in a season, in kilograms for each hectare", ()
    ),
    'fungicide_programmes': (
        "Fungicide programmes", None, ScaleType.NOMINAL, "The fungicide sprays a crop received", FUNGICIDE_CATEGORIES
    ),
}
# The scale's description after the last commit, which clarifies it
SEPTORIA_SCALE_CLARIFIED = (
    "Severity of Septoria leaf blotch on the flag leaf and the two leaves below it, from 1 (no symptoms) to "
    "9 (the upper leaves dead), scored across the whole plot"
)

# key: (name, subjects, description)
TRAITS = {
    'plant_height': ("Plant height", ('plot', 'plant'), "The height of the crop"),
    'heading': ("Heading", ('plot',), "When the ears emerge from the flag leaf sheath"),
    'grain_yield': ("Grain yield", ('plot',), "The grain a plot gives at harvest"),
    'septoria': (
        "Septoria leaf blotch", ('plot',), "A leaf disease of wheat caused by the fungus Zymoseptoria tritici"
    ),
    'grain_weight': ("Thousand grain weight", ('grain_sample',), "The weight of a thousand grains"),
    'protein': ("Grain protein", ('grain_sample', 'flour_sample'), "The protein content of the grain"),
    'reflectance': ("Near-infrared reflectance", ('grain_sample',), "How the grain reflects near-infrared light"),
}

# key: (name, trait, observation method, scale, description). Committed in two versions: the field's, then the lab's.
FIELD_VARIABLES = {
    'height': ("Plant height (cm)", 'plant_height', 'ruler', 'centimetres', "Plant height of a plot, in centimetres"),
    'heading': (
        "Heading date", 'heading', 'visual', 'date', "The day half of the ears of a plot have emerged"
    ),
    'yield': ("Grain yield (t/ha)", 'grain_yield', 'combine', 'tonnes_per_hectare', "Grain yield at 15 percent moisture"),
    'septoria': (
        "Septoria leaf blotch score", 'septoria', 'visual', 'septoria_scale', "Septoria leaf blotch severity of a plot"
    ),
}
GRAIN_VARIABLES = {
    'grain_weight': (
        "Thousand grain weight (g)", 'grain_weight', 'grain_count', 'grams', "Weight of a thousand grains, in grams"
    ),
    'protein': ("Grain protein (%)", 'protein', 'nir_prediction', 'percent', "Protein in the grain, by weight"),
    'nir_spectrum': (
        "NIR spectrum", 'reflectance', 'nir_scan', 'nir_file', "The near-infrared spectrum of a grain sample, as a file"
    ),
}
VARIABLES = {**FIELD_VARIABLES, **GRAIN_VARIABLES}

# key: (name, subjects, description)
CONDITIONS = {
    'nitrogen': ("Nitrogen fertiliser", ('plot',), "The nitrogen fertiliser a plot receives"),
    'fungicide': ("Fungicide treatment", ('field', 'plot'), "The fungicide a trial area or a plot receives"),
}
# key: (name, control method type, description). The last two describe how germplasm entries were produced.
CONTROL_METHODS = {
    'fertiliser_application': (
        "Fertiliser application", ControlMethodType.NUTRITIONAL,
        "Nitrogen spread as granules in spring, in three splits"
    ),
    'fungicide_spraying': (
        "Fungicide spraying", ControlMethodType.CHEMICAL, "Fungicide sprayed at the growth stages its programme names"
    ),
    'hand_crossing': (
        "Hand crossing", ControlMethodType.GENETIC,
        "The female parent's flowers emasculated, then pollinated by hand from the male parent"
    ),
    'single_plant_selection': (
        "Single-plant selection", ControlMethodType.GENETIC, "One plant chosen from a line, and its seed kept apart"
    ),
}
# key: (name, condition, control method, scale, description)
FACTORS = {
    'nitrogen_rate': (
        "Nitrogen rate (kg N/ha)", 'nitrogen', 'fertiliser_application', 'kg_nitrogen_per_hectare',
        "The nitrogen a plot received in the season"
    ),
    'fungicide_programme': (
        "Fungicide programme", 'fungicide', 'fungicide_spraying', 'fungicide_programmes',
        "The fungicide sprays a trial area or a plot received"
    ),
}

# The versions committed after the seeded one: (change, comment). The licence and copyright are cited from the second.
COMMITS = (
    ('MAJOR', "Places, layouts and trial designs"),
    ('MAJOR', "Field traits and treatments"),
    ('MINOR', "Grain quality traits"),
    ('PATCH', "Clarify the Septoria score"),
)


# Places ---------------------------------------------------------------------------------------------------------------

COUNTRY_CODE = 'IRL'  # the location tree's root, a country from the state store

# Where each site's shapes are drawn from, in degrees: on bog in County Offaly (cut-away peatland north of the Grand
# Canal) and in County Kildare (Mouds Bog), where OpenStreetMap has no building, road, path or named place within
# 500 m of the boxes around them (SITE_BOXES). Check again before sharing a build if they move (docs/demo-database.md,
# Checks before sharing a build).
ORIGINS = {
    'farm': (53.2760, -7.6879),
    'cooperative': (53.2126, -6.8223),
}
# The extent of each site's shapes, east and north of its origin, in metres
SITE_BOXES = {
    'farm': ((-50.0, -50.0), (650.0, 450.0)),
    'cooperative': ((-50.0, -50.0), (300.0, 300.0)),
}


def rectangle(east: float, north: float, width: float, height: float) -> Tuple[Tuple[float, float], ...]:
    """A field's boundary, from its south-west corner, as offsets in metres, anticlockwise"""
    return (east, north), (east + width, north), (east + width, north + height), (east, north + height)


@dataclass(frozen=True)
class Place:
    name: str
    type: str | None  # a location type key; None for the country, which the state store gives
    team: str
    release: ReadRelease
    parent: str | None = None
    description: str | None = None
    code: str | None = None
    address: str | None = None
    # offsets east and north of the site's origin, in metres: one point, or a boundary
    shape: Tuple[Tuple[float, float], ...] = ()
    site: str = 'farm'


FICTIONAL = "Fictional: it marks no real farm."
PLACES: Dict[str, Place] = {
    'ireland': Place("Ireland", None, 'institute', PUBLIC),
    'offaly': Place("County Offaly", 'county', 'institute', PUBLIC, parent='ireland'),
    'farm': Place(
        "Example Research Farm", 'farm', 'institute', PUBLIC, parent='offaly', code="ERF",
        description=f"The Institute's research farm. {FICTIONAL}", shape=((300.0, 220.0),)
    ),
    'long_meadow': Place(
        "Long Meadow", 'field', 'field', PUBLIC, parent='farm', code="LM",
        description=f"A level field of loam on the farm's west side. {FICTIONAL}", shape=rectangle(0, 0, 150, 160)
    ),
    'north_field': Place(
        "North Field", 'field', 'field', PUBLIC, parent='farm', code="NF",
        description=f"A field of heavier soil, north of the farm buildings. {FICTIONAL}",
        shape=rectangle(180, 260, 160, 150)
    ),
    'glasshouse': Place(
        "Glasshouse", 'glasshouse', 'field', PRIVATE, parent='farm',
        description="The farm's glasshouse, with benches for pot trials", shape=((330.0, 200.0),)
    ),
    'laboratory': Place(
        "Grain Quality Laboratory", 'laboratory', 'lab', REGISTERED, parent='farm',
        description="Where grain from the trials is weighed and analysed", shape=((300.0, 190.0),)
    ),
    'freezer': Place(
        "Sample Freezer", 'cold_store', 'lab', PRIVATE, parent='laboratory',
        description="A freezer for grain and flour samples"
    ),
    'kildare': Place("County Kildare", 'county', 'cooperative', PUBLIC, parent='ireland'),
    'coop_farm': Place(
        "Cooperative Seed Farm", 'farm', 'cooperative', PRIVATE, parent='kildare',
        description=f"Where the Cooperative multiplies seed. {FICTIONAL}", shape=((120.0, 120.0),), site='cooperative'
    ),
    'seed_field': Place(
        "Seed Field", 'field', 'cooperative', PRIVATE, parent='coop_farm', description=FICTIONAL,
        shape=rectangle(0, 0, 100, 80), site='cooperative'
    ),
}

# Added by the guide for 2027 (the "next season" chain), with this boundary
HILL_FIELD = Place(
    "Hill Field", 'field', 'field', PUBLIC, parent='farm', code="HF",
    description=f"A sloping field east of the farm buildings, first sown in 2027. {FICTIONAL}",
    shape=rectangle(420, 20, 160, 140)
)


# Germplasm ------------------------------------------------------------------------------------------------------------

UNKNOWN, SEED, MATERNAL, PATERNAL = (
    GermplasmSourceType.UNKNOWN, GermplasmSourceType.SEED, GermplasmSourceType.MATERNAL, GermplasmSourceType.PATERNAL
)


@dataclass(frozen=True)
class Variety:
    name: str
    release: ReadRelease
    description: str
    sources: Tuple[Tuple[str, GermplasmSourceType], ...] = ()  # none for the crop
    synonyms: Tuple[str, ...] = ()
    control_methods: Tuple[str, ...] = ()  # control method keys
    reproduction: Reproduction | None = Reproduction.SEXUAL
    origin: str | None = None  # a place key
    time: str | None = None
    selected_from: bool = False  # it came from the 2025 selection plant (SELECTION)


def _cross(name, release, mother, father, year, note=None):
    description = f"A line from {GERMPLASM_NAMES[mother]} x {GERMPLASM_NAMES[father]}, crossed in {year}"
    return Variety(
        name, release, description + (f". {note}" if note else ""), sources=((mother, MATERNAL), (father, PATERNAL)),
        control_methods=('hand_crossing',), time=str(year)
    )


GERMPLASM_NAMES = {
    'copperwren': "Copperwren", 'fernhollow': "Fernhollow", 'brindlecrest': "Brindlecrest",
    'larkmere': "Larkmere", 'quillsprig': "Quillsprig", 'harrowgold': "Harrowgold",
    'epb_19_031': "EPB 19-031", 'epb_19_047': "EPB 19-047", 'epb_19_052': "EPB 19-052", 'epb_19_066': "EPB 19-066",
    'epb_21_014': "EPB 21-014", 'epb_21_022': "EPB 21-022", 'epb_21_038': "EPB 21-038",
}
GERMPLASM: Dict[str, Variety] = {
    'wheat': Variety(
        "Wheat", PUBLIC, "Bread wheat, the crop of the programme", synonyms=("Triticum aestivum", "Bread wheat"),
        reproduction=None
    ),
    'copperwren': Variety(
        "Copperwren", PUBLIC, "A fictional winter wheat variety with high yield and weak Septoria resistance",
        sources=(('wheat', UNKNOWN),)
    ),
    'fernhollow': Variety(
        "Fernhollow", PUBLIC, "A fictional winter wheat variety with strong Septoria resistance",
        sources=(('wheat', UNKNOWN),)
    ),
    'brindlecrest': Variety(
        "Brindlecrest", PUBLIC, "A fictional tall winter wheat variety with large grain", sources=(('wheat', UNKNOWN),)
    ),
    'larkmere': Variety(
        "Larkmere", PUBLIC, "A fictional short winter wheat variety with high grain protein",
        sources=(('wheat', UNKNOWN),)
    ),
    'quillsprig': Variety(
        "Quillsprig", PUBLIC, "A fictional early winter wheat variety", sources=(('wheat', UNKNOWN),)
    ),
    'harrowgold': Variety(
        "Harrowgold", PUBLIC, "A fictional late winter wheat variety", sources=(('wheat', UNKNOWN),)
    ),
}
GERMPLASM.update({
    'epb_19_031': _cross("EPB 19-031", PUBLIC, 'copperwren', 'fernhollow', 2019),
    'epb_19_047': _cross("EPB 19-047", PUBLIC, 'brindlecrest', 'larkmere', 2019),
    'epb_19_052': _cross("EPB 19-052", PUBLIC, 'larkmere', 'copperwren', 2019),
    'epb_19_066': _cross("EPB 19-066", PUBLIC, 'quillsprig', 'harrowgold', 2019),
    'epb_21_014': _cross("EPB 21-014", REGISTERED, 'epb_19_031', 'larkmere', 2021),
    'epb_21_022': _cross("EPB 21-022", REGISTERED, 'fernhollow', 'epb_19_047', 2021),
    'epb_21_038': _cross("EPB 21-038", REGISTERED, 'harrowgold', 'epb_19_052', 2021),
    'epb_25_s03': Variety(
        "EPB 25-S03", PRIVATE, "A single-plant selection from EPB 21-014 for its clean leaves, in North Field in 2025",
        sources=(('epb_21_014', SEED),), control_methods=('single_plant_selection',), origin='north_field',
        time='2025-07-15', selected_from=True
    ),
})

# The plant the selection was made from: in the 2025 trial, on the EPB 21-014 plot given the higher nitrogen rate in
# its second block
SELECTION = ('nf25', 'epb_21_014', 200, 2)

# The guide's new cross for 2027 (the "next season" chain)
NEW_CROSS = ("EPB 26-X01", 'epb_25_s03', 'epb_21_022')


# Trials, layouts and units --------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class TrialPlan:
    """A field trial: every treatment (entry, and nitrogen rate if any) once in each block, as layout.py lays it out"""
    field: str  # a place key
    prefix: str  # plots are named <prefix>-<block><plot within the block, two digits>
    entries: Tuple[str, ...]  # germplasm keys
    nitrogen: Tuple[int, ...]  # the rates in kg N/ha, or none where nitrogen is not a treatment
    blocks: int
    rows: int  # rows of plots in each block; the columns follow from the number of treatments
    sown: str
    harvested: str | None  # the plots' positions end then; None while the trial is in the ground
    release: ReadRelease  # of its units and layout (controlled by Field Operations)
    layout: str  # the layout tree's name
    area: str  # the name of the unit graph's root, the trial's area of the field

    @property
    def treatments(self) -> Tuple[Tuple[str, int | None], ...]:
        return tuple((entry, rate) for entry in self.entries for rate in (self.nitrogen or (None,)))

    @property
    def columns(self) -> int:
        return len(self.treatments) // self.rows


PLANS: Dict[str, TrialPlan] = {
    'lm24': TrialPlan(
        'long_meadow', 'LM24',
        ('copperwren', 'fernhollow', 'brindlecrest', 'larkmere', 'epb_19_031', 'epb_19_047', 'epb_19_052', 'epb_19_066'),
        (), 3, 2, '2023-10-12', '2024-08-12', PUBLIC, "Long Meadow 2024 trial", "Long Meadow 2024 trial area"
    ),
    'nf25': TrialPlan(
        'north_field', 'NF25',
        ('copperwren', 'fernhollow', 'epb_19_031', 'epb_19_047', 'epb_19_066', 'epb_21_014', 'epb_21_022', 'epb_21_038'),
        (120, 200), 3, 2, '2024-10-14', '2025-08-18', PRIVATE, "North Field 2025 trial", "North Field 2025 trial area"
    ),
    'lm26': TrialPlan(
        'long_meadow', 'LM26',
        ('copperwren', 'epb_19_031', 'epb_21_014', 'epb_21_022', 'epb_21_038', 'epb_25_s03'),
        (120, 200), 3, 2, '2025-10-16', None, PRIVATE, "Long Meadow 2026 trial", "Long Meadow 2026 trial area"
    ),
}

# The grain harvested from each 2025 plot reached the laboratory together, one arrival
GRAIN_ARRIVED = '2025-08-21'
# The lab's other layouts: name, type, location, axes, team, release
LAB_LAYOUTS = {
    'freezer_rack': ("Freezer 1", 'freezer_rack', 'freezer', ('Shelf', 'Box'), 'lab', PRIVATE),
    'benches': ("Glasshouse benches", 'bench_layout', 'glasshouse', ('Bench',), 'field', PRIVATE),
}

# The Cooperative's seed multiplication: two plots of a registered line
COOPERATIVE_PLOTS = {
    'area': ("Seed Field 2025", '2024-10-20', '2025-08-15'),
    'plots': ("SF25-1", "SF25-2"),
    'entry': 'epb_21_014',
}


# References -----------------------------------------------------------------------------------------------------------
# key: (kind, description, team, release, filename); their texts and files are made in values.py

REFERENCES = {
    'ontology_licence': ('legal', "Example Ontology Licence", 'institute', PUBLIC, None),
    'ontology_copyright': ('legal', "Example Ontology Copyright", 'institute', PUBLIC, None),
    'open_licence': ('legal_markdown', "Example Open Data Licence", 'breeding', PUBLIC, None),
    'plan_2024': ('file_pdf', "Long Meadow 2024 field plan", 'breeding', PUBLIC, 'long-meadow-2024-field-plan.pdf'),
    'plan_2025': ('file_pdf', "North Field 2025 field plan", 'breeding', PRIVATE, 'north-field-2025-field-plan.pdf'),
}
# Uploaded in the guide, not stored: the 2025 study's licence (workflow 8)
PARTNER_LICENCE = ("Partner Data Licence", 'partner-data-licence.pdf')


# Programmes -----------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Programme:
    name: str
    team: str
    release: ReadRelease
    description: str
    contacts: Tuple[str, ...] = ()  # Person keys: linked to an account, and released to registered users
    contributions: Tuple[Tuple[str, Tuple[str, ...]], ...] = ()  # (Person key, CRediT role names)


@dataclass(frozen=True)
class Trial:
    name: str
    programme: str
    release: ReadRelease
    description: str
    start: str
    end: str
    contacts: Tuple[str, ...] = ()
    contributions: Tuple[Tuple[str, Tuple[str, ...]], ...] = ()


@dataclass(frozen=True)
class Grouping:
    name: str
    type: str  # a record group type key
    extent: RecordGroupExtent
    scope: GroupingScope = GroupingScope.STUDY_WIDE


@dataclass(frozen=True)
class Study:
    name: str
    trial: str
    release: ReadRelease
    description: str
    start: str
    end: str
    practices: str | None = None
    design: str | None = None  # a design key
    licence: str | None = None  # a reference key
    references: Tuple[str, ...] = ()  # reference keys
    groupings: Tuple[Grouping, ...] = ()


PROGRAMMES = {
    'programme': Programme(
        "Winter Wheat Breeding Programme", 'breeding', PUBLIC,
        "The Institute's programme breeding winter wheat for yield, Septoria resistance and grain quality",
        contacts=('person_bridget',),
        contributions=(
            ('person_bridget', ("Supervision", "Conceptualization")),
            ('person_dara', ("Data curation",)),
            ('person_petra', ("Resources",)),
        )
    ),
    'coop_programme': Programme(
        "Cooperative Seed Multiplication", 'cooperative', PRIVATE,
        "The Cooperative's multiplication of seed of promising lines"
    ),
}
TRIALS = {
    'trial_2024': Trial(
        "Preliminary Yield Trial 2024", 'programme', PUBLIC,
        "The first yield trial of four new lines, against four varieties", '2023-10', '2024-08',
        contacts=('person_bridget',)
    ),
    'trial_2025': Trial(
        "Advanced Yield Trial 2025", 'programme', PRIVATE,
        "Promising lines at two nitrogen rates, with the grain's quality measured in the lab", '2024-10', '2025-09',
        contacts=('person_theo',), contributions=(('person_theo', ("Investigation",)),)
    ),
    'coop_trial': Trial(
        "Seed Multiplication 2025", 'coop_programme', PRIVATE, "Seed of EPB 21-014 grown on", '2024-10', '2025-08'
    ),
}
STUDIES = {
    'study_2024': Study(
        "Long Meadow Yield Trial 2024", 'trial_2024', PUBLIC,
        "Eight entries in three randomised complete blocks in Long Meadow", '2023-10-12', '2024-08-12',
        practices="Sown at 350 seeds per square metre after oilseed rape; 180 kg N/ha in three splits; "
                  "two fungicide sprays",
        design='rcbd', licence='open_licence', references=('plan_2024',)
    ),
    'study_2025': Study(
        "North Field Yield Trial 2025", 'trial_2025', PRIVATE,
        "Eight entries at 120 and 200 kg N/ha in three randomised complete blocks in North Field",
        '2024-10-14', '2025-08-18',
        practices="Sown at 350 seeds per square metre after beans; nitrogen as the treatment, in three splits; "
                  "two fungicide sprays",
        design='rcbd', references=('plan_2025',)
    ),
    'study_lab_2025': Study(
        "Grain Quality 2025", 'trial_2025', PRIVATE,
        "Thousand grain weight, protein and NIR spectra of the grain from North Field", '2025-08-21', '2025-09-30',
        groupings=(
            Grouping("Grain count", 'replicate', RecordGroupExtent.WITHIN_UNIT),
            Grouping("NIR run", 'batch', RecordGroupExtent.SHARED),
        )
    ),
    'coop_study': Study(
        "Seed Field Multiplication 2025", 'coop_trial', PRIVATE, "Two plots of EPB 21-014 for seed",
        '2024-10-20', '2025-08-15'
    ),
}


# Datasets -------------------------------------------------------------------------------------------------------------

# A dataset's records start on the day their value names (a date variable's)
ON_VALUE = 'value'


@dataclass(frozen=True)
class DatasetPlan:
    study: str
    concept: str  # a variable or factor key
    writer: str  # the account that submits it, with its write team
    release: ReadRelease
    # 'plots' (of the study's trial), 'area' (the trial's area of its field, above the plots), 'samples' (the grain of
    # each 2025 plot), 'nir_samples' (the first eight of block 1) or 'coop_plots'
    units: str
    # the day of the records; ON_VALUE for a date variable's; None for a factor's, which hold for the whole season
    on: str | None
    contributions: Tuple[Tuple[str, Tuple[str, ...]], ...] = ()


FIELD_CREDITS_2024 = (
    ('person_rita', ("Investigation",)), ('person_fergus', ("Investigation",))
)
FIELD_CREDITS_2025 = (('person_theo', ("Investigation",)), ('person_fergus', ("Investigation",)))
LAB_CREDITS_2025 = (('person_lena', ("Investigation", "Formal analysis")),)

DATASETS = {
    'height_2024': DatasetPlan(
        'study_2024', 'height', 'rita', PUBLIC, 'plots', '2024-06-20',
        FIELD_CREDITS_2024 + (('person_erased', ("Investigation",)),)
    ),
    'heading_2024': DatasetPlan('study_2024', 'heading', 'rita', PUBLIC, 'plots', ON_VALUE, FIELD_CREDITS_2024),
    'septoria_2024': DatasetPlan('study_2024', 'septoria', 'rita', PUBLIC, 'plots', '2024-06-10', FIELD_CREDITS_2024),
    'yield_2024': DatasetPlan('study_2024', 'yield', 'rita', PUBLIC, 'plots', '2024-08-12', FIELD_CREDITS_2024),
    # every plot had the same two sprays, a practice rather than a treatment: one record on the trial's area, which
    # curation and analysis apply to the plots in it
    'fungicide_2024': DatasetPlan('study_2024', 'fungicide_programme', 'rita', PUBLIC, 'area', None),
    'height_2025': DatasetPlan('study_2025', 'height', 'theo', PRIVATE, 'plots', '2025-06-24', FIELD_CREDITS_2025),
    'heading_2025': DatasetPlan('study_2025', 'heading', 'theo', PRIVATE, 'plots', ON_VALUE, FIELD_CREDITS_2025),
    'septoria_2025': DatasetPlan('study_2025', 'septoria', 'theo', PRIVATE, 'plots', '2025-06-12', FIELD_CREDITS_2025),
    'yield_2025': DatasetPlan('study_2025', 'yield', 'theo', PRIVATE, 'plots', '2025-08-18', FIELD_CREDITS_2025),
    'nitrogen_2025': DatasetPlan('study_2025', 'nitrogen_rate', 'theo', PRIVATE, 'plots', None),
    'grain_weight_2025': DatasetPlan(
        'study_lab_2025', 'grain_weight', 'lena', PRIVATE, 'samples', '2025-09-10', LAB_CREDITS_2025
    ),
    'protein_2025': DatasetPlan('study_lab_2025', 'protein', 'lena', PRIVATE, 'samples', '2025-09-24', LAB_CREDITS_2025),
    'nir_2025': DatasetPlan(
        'study_lab_2025', 'nir_spectrum', 'lena', PRIVATE, 'nir_samples', '2025-09-24', LAB_CREDITS_2025
    ),
    'coop_yield_2025': DatasetPlan('coop_study', 'yield', 'petra', PRIVATE, 'coop_plots', '2025-08-15'),
}

# The 2026 observations the guide enters (the "this season" chain), with one typo: LM26-207's height typed with an
# extra zero, for the curation chapter to correct
PLANNED_2026 = {
    'height': '2026-06-25',
    'septoria': '2026-06-16',
    'nitrogen_rate': None,
}
TYPO = ('LM26-207', 'height')

# A pending request, for the Affiliation requests tab: Petra asks to read Field Operations' records, which Dara decides
PENDING_REQUESTS = (('petra', 'field', READ),)


# What the guide's workflows create (docs/demo-database.md, The chains): not built, given to the recordings by the
# manifest so they enter the same names
GUIDE = {
    'invitee': {'username': 'nina', 'fullname': "Nina Newcomer"},
    'invitation_offer': {'team': 'breeding', 'accesses': (READ, WRITE), 'person': 'person_nina'},
    'affiliation_request': {'team': 'lab', 'access': READ},
    'trial_2026': {'name': "Advanced Yield Trial 2026", 'start': '2025-10', 'end': '2026-08'},
    'study_2026': {
        'name': "Long Meadow Yield Trial 2026",
        'description': "Six entries at 120 and 200 kg N/ha in three randomised complete blocks in Long Meadow",
        'practices': "Sown at 350 seeds per square metre after oilseed rape; nitrogen as the treatment, in three "
                     "splits; two fungicide sprays",
        'start': '2025-10-16', 'end': '2026-08-14', 'design': 'rcbd',
    },
    'new_person': {'name': "Hannah Harvester", 'institution': INSTITUTE, 'team': 'breeding', 'role': "Investigation"},
    'flag_leaf': {
        'trait': "Flag leaf length", 'method': "Ruler on the flag leaf", 'scale': 'centimetres',
        'variable': "Flag leaf length (cm)",
    },
    'hill_field_layout': "Hill Field 2027 trial",
    'hill_field_area': "Hill Field 2027 trial area",
    'transfer': {'team': 'breeding', 'germplasm': ('epb_21_014', 'epb_21_022', 'epb_21_038'), 'to': 'cooperative'},
    'deprecate': 'fungicide_programme',
}
