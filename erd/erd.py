import sys
import os

# Get absolute path to the project root (one level up from 'erd/')
breedgraph_src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(breedgraph_src_path)


import erdantic as erd
from src.breedgraph.domain.model.accounts import AccountStored
from src.breedgraph.domain.model.arrangements import Arrangement, LayoutStored
from src.breedgraph.domain.model.blocks import Block, UnitBase
from src.breedgraph.domain.model.datasets import DatasetStored, DataRecordStored
from src.breedgraph.domain.model.organisations import Organisation, TeamStored
from src.breedgraph.domain.model.controls import Controller
from src.breedgraph.domain.model.programs import ProgramStored
from src.breedgraph.domain.model.regions import Region, LocationStored
from src.breedgraph.domain.model.references import ReferenceStoredBase
from src.breedgraph.domain.model.ontology import (
    OntologyEntryStored, OntologyRelationshipBase,
    TermOutput, 
    SubjectOutput,
    ScaleOutput,
    ScaleCategoryOutput,
    ObservationMethodOutput,
    TraitOutput,
    VariableOutput,
    ControlMethodOutput,
    ConditionOutput,
    FactorOutput,
    EventTypeOutput,
    LocationTypeOutput,
    LayoutTypeOutput,
    DesignOutput,
    RoleOutput,
    TitleOutput
)


from src.breedgraph.domain.model.germplasm import GermplasmStored, GermplasmRelationship

erd.draw(ProgramStored, out="./figures/program.svg")
erd.draw(AccountStored, out="./figures/account.svg")
erd.draw(Organisation, out="./figures/organisation.svg")
erd.draw(TeamStored, out="./figures/team.svg")

erd.draw(Region, out="./figures/region.svg")
erd.draw(LocationStored, out="./figures/location.svg")

erd.draw(Arrangement, out="./figures/arrangement.svg")
erd.draw(LayoutStored, out="./figures/layout.svg")

erd.draw(Block, out="./figures/block.svg")
erd.draw(UnitBase, out="./figures/unit.svg")

erd.draw(DatasetStored, out="./figures/dataset.svg")
erd.draw(DataRecordStored, out="./figures/datarecord.svg")

erd.draw(OntologyEntryStored, out="./figures/ontology_entry.svg")
erd.draw(OntologyRelationshipBase, out="./figures/ontology_relationship.svg")

erd.draw(TermOutput, out="./figures/ontology_term.svg")
erd.draw(SubjectOutput, out="./figures/ontology_subject.svg")
erd.draw(ScaleOutput, out="./figures/ontology_scale.svg")
erd.draw(ScaleCategoryOutput, out="./figures/ontology_scale_category.svg")
erd.draw(ObservationMethodOutput, out="./figures/ontology_observation_method.svg")
erd.draw(TraitOutput, out="./figures/ontology_trait.svg")
erd.draw(VariableOutput, out="./figures/ontology_variable.svg")
erd.draw(ControlMethodOutput, out="./figures/ontology_control_method.svg")
erd.draw(ConditionOutput, out="./figures/ontology_condition.svg")
erd.draw(FactorOutput, out="./figures/ontology_factor.svg")
erd.draw(EventTypeOutput, out="./figures/ontology_event_type.svg")
erd.draw(LocationTypeOutput, out="./figures/ontology_location_type.svg")
erd.draw(LayoutTypeOutput, out="./figures/ontology_layout_type.svg")
erd.draw(DesignOutput, out="./figures/ontology_design.svg")
erd.draw(RoleOutput, out="./figures/ontology_role.svg")
erd.draw(TitleOutput, out="./figures/ontology_title.svg")



erd.draw(GermplasmStored, out="./figures/germplasm_entry.svg")
erd.draw(GermplasmRelationship, out="./figures/germplasm_relationship.svg")

erd.draw(ReferenceStoredBase, out="./figures/reference.svg")

erd.draw(Controller, out="./figures/controller.svg")