from breedgraph.adapters.neo4j import Neo4jUnitOfWorkFactory
from breedgraph.domain.model.ontology import SubjectInput, LocationTypeInput, OntologyEntryLabel


async def prepare_subject_ontology(uow_factory: Neo4jUnitOfWorkFactory, user_id:int):
    async with uow_factory.get_uow(user_id=user_id) as uow:#

        field_subject = await uow.ontology.create_subject(subject=SubjectInput(name="Field"))
        trees_subject = await uow.ontology.create_subject(subject=SubjectInput(name="Trees"), parents=[field_subject.id])
        tree_subject = await uow.ontology.create_subject(subject=SubjectInput(name="Tree"), parents=[field_subject.id, trees_subject.id])
        branch_subject = await uow.ontology.create_subject(subject=SubjectInput(name="Branch"), parents=[tree_subject.id])
        leaves_subject = await uow.ontology.create_subject(subject=SubjectInput(name="Leaves"), parents=[tree_subject.id, branch_subject.id])
        leaf_subject = await uow.ontology.create_subject(subject=SubjectInput(name="Leaf"), parents=[tree_subject.id, branch_subject.id, leaves_subject.id])
        cherries_subject = await uow.ontology.create_subject(subject=SubjectInput(name="Cherries"), parents=[tree_subject.id, branch_subject.id])
        green_beans_subject = await uow.ontology.create_subject(subject=SubjectInput(name="Green Beans"), parents=[tree_subject.id])

        await uow.commit()

        return {
            "field": field_subject.id,
            "trees": trees_subject.id,
            "tree": tree_subject.id,
            "branch": branch_subject.id,
            "leaves": leaves_subject.id,
            "leaf": leaf_subject.id,
            "cherries": cherries_subject.id,
            "green_beans": green_beans_subject.id
        }


async def prepare_location_ontology(uow_factory: Neo4jUnitOfWorkFactory, user_id: int):
    async with (uow_factory.get_uow(user_id=user_id) as uow):

        country_location_type = await uow.ontology.get_entry(name="Country", label=OntologyEntryLabel.LOCATION_TYPE)
        if not country_location_type:
            raise ValueError("Country location type not found")

        region_location_type = await uow.ontology.create_entry(entry=LocationTypeInput(name="Region", description="A large area of land"), parents=[country_location_type.id])
        farm_location_type = await uow.ontology.create_entry(entry=LocationTypeInput(name="Farm", description="A place where crops are grown"), parents=[region_location_type.id])
        field_location_type = await uow.ontology.create_entry(entry=LocationTypeInput(name="Field", description="A piece of land used for growing crops"), parents=[farm_location_type.id])

        await uow.commit()

        return {
            "region_id": region_location_type.id,
            "farm_id": farm_location_type.id,
            "field_id": field_location_type.id
        }

async def prepare_breedcafs_ontology(uow_factory: Neo4jUnitOfWorkFactory, user_id: int):
    subjects = await prepare_subject_ontology(uow_factory=uow_factory, user_id=user_id)
    locations = await prepare_location_ontology(uow_factory=uow_factory, user_id=user_id)
    return {
        "subject": subjects,
        "location_type": locations
    }