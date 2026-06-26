from breedgraph.domain.model.ontology import *
from breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitOfWorkFactory

from tests.utilities.inputs import LoremTextGenerator

from typing import List, Dict

class OntologyBuilder:
    lorem_generator = LoremTextGenerator()

    def __init__(self, uow_factory: AbstractUnitOfWorkFactory):
        self.uow_factory = uow_factory

    @staticmethod
    def subject_input(name: str | None = None) -> SubjectInput:
        return SubjectInput(
            name=name or OntologyBuilder.lorem_generator.new_text(10),
            description=OntologyBuilder.lorem_generator.new_text(20)
        )

    @staticmethod
    def trait_input(name: str | None = None) -> TraitInput:
        return TraitInput(
            name=name or OntologyBuilder.lorem_generator.new_text(10),
            description=OntologyBuilder.lorem_generator.new_text(20)
        )

    @staticmethod
    def observation_method_input(name: str | None = None) -> ObservationMethodInput:
        return ObservationMethodInput(
            name=name or OntologyBuilder.lorem_generator.new_text(10),
            description=OntologyBuilder.lorem_generator.new_text(20)
        )

    @staticmethod
    def scale_input(name: str | None = None) -> ScaleInput:
        return ScaleInput(
            name=name or OntologyBuilder.lorem_generator.new_text(10),
            description=OntologyBuilder.lorem_generator.new_text(20)
        )

    @staticmethod
    def variable_input(name: str | None = None) -> VariableInput:
        return VariableInput(
            name=name or OntologyBuilder.lorem_generator.new_text(10),
            description=OntologyBuilder.lorem_generator.new_text(20)
        )

    async def basic_variable_components(self, user_id: int) -> Dict[str, int]:
        async with self.uow_factory.get_uow(user_id=user_id) as uow:
            ontology_service = uow.ontology

            subject = await ontology_service.create_entry(
                self.subject_input(name=self.lorem_generator.new_text(10))
            )
            trait = await ontology_service.create_trait(
                self.trait_input(name=self.lorem_generator.new_text(10)),
                subjects=[subject.id]
            )
            observation_method = await ontology_service.create_entry(
                self.observation_method_input(name=self.lorem_generator.new_text(10))
            )
            scale = await ontology_service.create_scale(
                self.scale_input(name=self.lorem_generator.new_text(10))
            )

            await uow.commit()

            return {
                "ontology_subject": subject.id,
                "ontology_trait": trait.id,
                "ontology_observation_method": observation_method.id,
                "ontology_scale": scale.id
            }

    async def variable(self, user_id: int) -> Dict[str, int]:
        components = await self.basic_variable_components(user_id=user_id)

        async with self.uow_factory.get_uow(user_id=user_id) as uow:
            ontology_service = uow.ontology
            variable = await ontology_service.create_variable(
                self.variable_input(name=self.lorem_generator.new_text(10)),
                trait_id=components["ontology_trait"],
                observation_method_id=components["ontology_observation_method"],
                scale_id=components["ontology_scale"]
            )
            await uow.commit()

            return {
                **components,
                "ontology_variable": variable.id
            }

    async def location_types(self, user_id: int) -> Dict[str, int]:
        async with self.uow_factory.get_uow(user_id=user_id) as uow:
            ontology_service = uow.ontology
            country_type = await ontology_service.get_entry(name="Country", label=OntologyEntryLabel.LOCATION_TYPE)
            if not country_type:
                raise ValueError("Country type must be created during bootstrap")
            state_type = await ontology_service.create_entry(
                LocationTypeInput(name="State", synonyms=["Department"]),
                parents=[country_type.id]
            )
            field_type = await ontology_service.create_entry(
                LocationTypeInput(name="Field", synonyms=["Plot"]),
                parents=[state_type.id]
            )
            research_centre_type = await ontology_service.create_entry(
                LocationTypeInput(name="Research Centre", synonyms=["Research Station"]),
                parents=[country_type.id, state_type.id]
            )
            lab_type = await ontology_service.create_entry(
                LocationTypeInput(name="Laboratory", synonyms=["Lab"]),
                parents=[research_centre_type.id]
            )
            await uow.commit()
            return {
                'ontology_location_country': country_type.id,
                'ontology_location_state': state_type.id,
                'ontology_location_field': field_type.id,
                'ontology_location_research_centre': research_centre_type.id,
                'ontology_location_lab': lab_type.id
            }


    async def layout_types(self, user_id: int) -> Dict[str, int]:
        async with self.uow_factory.get_uow(user_id=user_id) as uow:
            ontology_service = uow.ontology
            named_type = await ontology_service.create_entry(
                LayoutTypeInput(
                    name="Named",
                    description="Positions are given by names",
                    axes=[AxisType.NOMINAL]
                )
            )
            adjacency_type = await ontology_service.create_entry(
                LayoutTypeInput(
                    name="Adjacency",
                    synonyms=["Relative Position"],
                    description="Positions are given relative to each other in descriptive terms, e.g. 'Top-Right'",
                    axes=[AxisType.NOMINAL]
                )
            )
            three_d_type = await ontology_service.create_entry(
                LayoutTypeInput(
                    name="3D adjacency",
                    synonyms=["3D Relative Position"],
                    description=(
                        "Positions are given relative to each other in descriptive terms "
                        "along each of three axes; "
                        "Depth (front to back), "
                        "Vertical (top to bottom) and "
                        "Horizontal (left to right). "
                        "e.g. 'Rear, Top, Right'"
                    ),
                    axes=[AxisType.ORDINAL, AxisType.ORDINAL, AxisType.ORDINAL]
                ),
                parents=[adjacency_type.id]
            )
            matrix_type = await ontology_service.create_entry(
                LayoutTypeInput(
                    name="Matrix",
                    synonyms=["Array"],
                    description="Positions are given by coordinates along each axis",
                )
            )
            grid_type = await ontology_service.create_entry(
                LayoutTypeInput(
                    name="Grid",
                    synonyms=["2-dimensional Array", "square matrix"],
                    description="Positions are given by coordinates along each of two perpendicular axes",
                    axes=[AxisType.CARTESIAN, AxisType.CARTESIAN]
                ),
                parents=[matrix_type.id]
            )
            numbered_type = await ontology_service.create_entry(
                LayoutTypeInput(
                    name="Numbered",
                    synonyms=["Indexed"],
                    description="Positions are given only by an integer",
                    axes=[AxisType.ORDINAL]
                )
            )
            row_type = await ontology_service.create_entry(
                LayoutTypeInput(
                    name="Rows",
                    synonyms=["Drills"],
                    description="Positions are given only by row number",
                    axes=[AxisType.ORDINAL]
                ),
                parents=[numbered_type.id]
            )
            indexed_type = await ontology_service.create_entry(
                LayoutTypeInput(
                    name="Indexed rows",
                    description="First axis is row, second is indexed position within row",
                    axes=[AxisType.ORDINAL, AxisType.ORDINAL]
                ),
                parents=[row_type.id]
            )
            measured_type = await ontology_service.create_entry(
                LayoutTypeInput(
                    name="Measured rows",
                    description="First axis is row, second is measured distance from start of row in metres",
                    axes=[AxisType.ORDINAL, AxisType.COORDINATE]
                ),
                parents=[row_type.id]
            )
            await uow.commit()
            return {
                'ontology_layout_named': named_type.id,
                'ontology_layout_adjacency': adjacency_type.id,
                'ontology_layout_3d': three_d_type.id,
                'ontology_layout_matrix': matrix_type.id,
                'ontology_layout_grid': grid_type.id,
                'ontology_layout_numbered': numbered_type.id,
                'ontology_layout_row': row_type.id,
                'ontology_layout_indexed': indexed_type.id,
                'ontology_layout_measured': measured_type.id
            }

    async def subject_types(self, user_id) -> Dict[str, int]:
        async with self.uow_factory.get_uow(user_id=user_id) as uow:
            ontology_service = uow.ontology
            field_subject = await ontology_service.create_entry(SubjectInput(name="Field"))
            tree_subject = await ontology_service.create_entry(SubjectInput(name="Tree"), parents=[field_subject.id])
            leaf_subject = await ontology_service.create_entry(SubjectInput(name="Leaf"), parents=[tree_subject.id])
            rhizosphere_subject = await ontology_service.create_entry(SubjectInput(name="Rhizosphere"), parents=[tree_subject.id])
            await uow.commit()
            return {
                'ontology_subject_field': field_subject.id,
                'ontology_subject_tree': tree_subject.id,
                'ontology_subject_leaf': leaf_subject.id,
                'ontology_subject_rhizosphere': rhizosphere_subject.id
            }

    async def variable_tree_height(self, user_id: int) -> Dict[str, int]:
        async with self.uow_factory.get_uow(user_id=user_id) as uow:
            ontology_service = uow.ontology
            tree_subject = await ontology_service.get_entry(name='Tree', label=OntologyEntryLabel.SUBJECT)
            if not tree_subject:
                await self.subject_types(user_id=user_id)
                tree_subject = await ontology_service.get_entry(name='Tree', label=OntologyEntryLabel.SUBJECT)

            trait = await ontology_service.create_trait(TraitInput(name="Tree Height"), subjects=[tree_subject.id])
            method = await ontology_service.create_entry(
                ObservationMethodInput(
                    name="Tape measure",
                    observation_type=ObservationMethodType.MEASUREMENT
                )
            )
            scale = await ontology_service.create_scale(
                ScaleInput(name="Millimeters", abbreviation="mm", scale_type=ScaleType.NUMERICAL)
            )
            variable = await ontology_service.create_variable(
                VariableInput(
                    name="Tree Height (mm)"
                ),
                trait_id=trait.id,
                observation_method_id=method.id,
                scale_id=scale.id
            )
            await uow.commit()
            return {
                'ontology_trait_height': trait.id,
                'ontology_method_tape': method.id,
                'ontology_scale_mm': scale.id,
                'ontology_variable_height': variable.id
            }

    async def factor_light_intensity(self, user_id: int) -> Dict[str, int]:
        async with self.uow_factory.get_uow(user_id=user_id) as uow:
            ontology_service = uow.ontology

            scale = await ontology_service.create_scale(
                ScaleInput(
                    name="Einsteins",
                    synonyms=["umol/m2/s"],
                    scale_type=ScaleType.NUMERICAL,
                    description="Average light intensity at leaf surface near shoot apical meristem"
                )
            )
            condition = await ontology_service.create_condition(
                ConditionInput(
                    name="Light level",
                    synonyms=["Light intensity"],
                    description="Light intensity during the day"
                )
            )
            method = await ontology_service.create_entry(
                ControlMethodInput(
                    name="Fluorescent lighting",
                    synonyms=["Artificial lighting"],
                    description="Artificial lighting provided by fluorescent light tubes"
                )
            )
            factor = await ontology_service.create_factor(
                FactorInput(
                    name="Light"
                ),
                condition_id=condition.id,
                control_method_id=method.id,
                scale_id=scale.id
            )
            await uow.commit()
            return {
                'ontology_scale_einsteins': scale.id,
                'ontology_method_fluorescent': method.id,
                'ontology_condition_light': condition.id,
                'ontology_factor_light': factor.id
            }

