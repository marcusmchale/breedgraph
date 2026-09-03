from breedgraph.adapters.neo4j import Neo4jUnitOfWorkFactory
from breedgraph.domain.model.ontology import SubjectInput


async def prepare_subject_ontology(uow_factory: Neo4jUnitOfWorkFactory, user_id:int):
    async with uow_factory.get_uow(user_id=user_id) as uow:
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
            "field_id": field_subject.id,
            "trees_id": trees_subject.id,
            "tree_id": tree_subject.id,
            "branch_id": branch_subject.id,
            "leaves_id": leaves_subject.id,
            "leaf_id": leaf_subject.id,
            "cherries_id": cherries_subject.id,
            "green_beans_id": green_beans_subject.id
        }


#todo
"""
For Fields with stratum data, create an arrangement for the Field with Row and Tree, then nested stratum.
     This highlights an issue, Should a layout definition really always require a new layout for each coordinate in the parent?
     We would be better to have a single layout, with 3 dimensions; row, tree, and stratum 
     to be used for defining branch positions.
               
     This does lose the fact that the stratum layout is a child of the row and tree layout.
     However, the alternative is a lot of redundant layouts. To consider this!
     Alternatively we could allow nullable axes in positions, but that makes the postion a bit loose.
"""