from breedgraph.domain import events
from breedgraph.service_layer.infrastructure import AbstractStateStore, AbstractUnitOfWorkFactory
from ..registry import handlers

import logging
logger = logging.getLogger(__name__)
from breedgraph.domain.model.analysis import (
    AnalysisConfig
)
from breedgraph.domain.services.analysis import AnalysisService
from breedgraph.domain.model.submissions import SubmissionStatus

from breedgraph.domain.importers import AnalysisImport

@handlers.event_handler()
async def analysis_requested(
        event: events.analysis.AnalysisRequested,
        state_store: AbstractStateStore,
        uow_factory: AbstractUnitOfWorkFactory
):
    # validate and parse the request input
    await state_store.set_status(key=event.analysis_id, status=SubmissionStatus.PROCESSING)
    try:
        stored_config_input = await state_store.get_analysis_config(agent_id=event.agent_id, analysis_id=event.analysis_id)
        analysis_import = AnalysisImport(**stored_config_input)

        async with uow_factory.get_uow(user_id = event.agent_id) as uow:
            datasets = [d async for d in uow.repositories.datasets.get_all(dataset_ids=analysis_import.dataset_ids)]
            # Collect units from record metadata to get blocks for validation
            unit_ids = set()
            for dataset in datasets:
                if not dataset.records:
                    raise ValueError("One of the requested datasets is empty")
                for record in dataset.records:
                    unit_ids.add(record.unit)
            blocks = [b async for b in uow.repositories.blocks.get_all(unit_ids=list(unit_ids))]
            # Prepare a parser with these details
            analysis_service = AnalysisService(
                datasets=datasets,
                blocks=blocks,
                unit_ids=unit_ids
            )

            # Parse the dependent variable
            if analysis_import.dependent_variable.concept_id is None:
                raise ValueError("Dependent variable must be a concept")

            dependent_entry = await uow.ontology.get_entry(
                entry_id=analysis_import.dependent_variable.concept_id
            )
            dependent_scale = await uow.ontology.get_concept_scale(dependent_entry.id)
            dependent_variable = analysis_service.parse_variable(
                variable_input=analysis_import.dependent_variable,
                entry=dependent_entry,
                scale=dependent_scale,
                is_dependent=True
            )
            # Parse independent variables
            independent_variables = []
            for iv in analysis_import.independent_variables or []:
                if iv.concept_id is not None:
                    concept = await uow.ontology.get_entry(entry_id=iv.concept_id)
                    scale = await uow.ontology.get_concept_scale(iv.concept_id)
                else:
                    concept = None
                    scale = None
                parsed_variable = analysis_service.parse_variable(variable_input=iv, entry=concept, scale=scale, is_dependent=False)
                if parsed_variable in independent_variables:
                    raise ValueError(f"Duplicate independent variable found: {parsed_variable}")
                independent_variables.append(parsed_variable)

            # Parse the interaction terms
            interaction_terms = analysis_service.parse_interaction_terms(analysis_import.interaction_terms, independent_variables)
            # Build a config object
            parsed_config = AnalysisConfig(
                name=analysis_import.name,
                dataset_ids=analysis_import.dataset_ids,
                dependent_variable=dependent_variable,
                independent_variables=independent_variables,
                interaction_terms=interaction_terms,
                timepoint_boundaries = analysis_import.timepoint_boundaries or None
            )
            # Now hand it into the parser for final validation
            analysis_service.config = parsed_config
            analysis_service.validate_config()
            analysis_service.build_df()
            group_stats = analysis_service.get_group_stats()
            analysis_service.fit_model()
            anova = analysis_service.get_anova()

            try:
                tukey = analysis_service.get_tukey_hsd()
            except ValueError:
                tukey = None
            result = {
                'anova': anova,
                'group': group_stats,
                'tukey': tukey
            }
            await state_store.set_analysis_result(analysis_id=event.analysis_id, result=result)

    except Exception as e:
        await state_store.set_errors(key=event.analysis_id, errors=[str(e)])
        await state_store.set_status(key=event.analysis_id, status=SubmissionStatus.FAILED)
