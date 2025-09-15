import erdantic as erd
from src.breedgraph.domain.model.accounts import AccountStored
from src.breedgraph.domain.model.arrangements import Arrangement, LayoutStored
from src.breedgraph.domain.model.blocks import Block, UnitBase
from src.breedgraph.domain.model.datasets import DataSetStored, DataRecordStored
from src.breedgraph.domain.model.organisations import Organisation, TeamStored
from src.breedgraph.domain.model.programs import ProgramStored
from src.breedgraph.domain.model.regions import Region, LocationStored
from src.breedgraph.domain.model.references import ReferenceStoredBase
from src.breedgraph.domain.model.ontology import Ontology, OntologyEntryStored

erd.draw(ProgramStored, out="src/data/erd/program.svg")
erd.draw(AccountStored, out="src/data/erd/account.svg")
erd.draw(Organisation, out="src/data/erd/organisation.svg")
erd.draw(TeamStored, out="src/data/erd/team.svg")

erd.draw(Region, out="src/data/erd/region.svg")
erd.draw(LocationStored, out="src/data/erd/location.svg")

erd.draw(Arrangement, out="src/data/erd/arrangement.svg")
erd.draw(LayoutStored, out="src/data/erd/layout.svg")

erd.draw(Block, out="src/data/erd/block.svg")
erd.draw(UnitBase, out="src/data/erd/unit.svg")

erd.draw(DataSetStored, out="src/data/erd/dataset.svg")
erd.draw(DataRecordStored, out="src/data/erd/datarecord.svg")

erd.draw(Ontology, out="src/data/erd/ontology.svg")
erd.draw(OntologyEntryStored, out="src/data/erd/ontology_entry.svg")

erd.draw(ReferenceStoredBase, out="src/data/erd/reference.svg")

