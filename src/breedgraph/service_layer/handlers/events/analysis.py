from breedgraph.domain import events
from breedgraph.service_layer.infrastructure import AbstractStateStore, AbstractUnitOfWorkFactory
from ..registry import handlers

import logging
logger = logging.getLogger(__name__)
from breedgraph.domain.model.analysis import (
    AnalysisConfig
)
from breedgraph.domain.services.analysis_config_parser import AnalysisConfigParser
from breedgraph.domain.model.submissions import SubmissionStatus


@handlers.event_handler()
async def analysis_requested(
        event: events.analysis.AnalysisRequested,
        state_store: AbstractStateStore,
        uow_factory: AbstractUnitOfWorkFactory
):
    # validate and parse the request input
    await state_store.set_status(key=event.analysis_id, status=SubmissionStatus.PROCESSING)
    try:

        config_input = await state_store.get_analysis_config(agent_id=event.agent_id, analysis_id=event.analysis_id)
        async with uow_factory.get_uow(user_id = event.agent_id) as uow:
            datasets = [d async for d in uow.repositories.datasets.get_all(dataset_ids=config_input.get('dataset_ids'))]
            # Collect units from record metadata to get blocks for validation
            unit_ids = set()
            for dataset in datasets:
                if not dataset.records:
                    raise ValueError("One of the requested datasets is empty")
                for record in dataset.records:
                    unit_ids.add(record.unit)
            blocks = [b async for b in uow.repositories.blocks.get_all(unit_ids=list(unit_ids))]
            # Prepare a parser with these details
            config_parser = AnalysisConfigParser(
                datasets=datasets,
                blocks=blocks,
                unit_ids=unit_ids,
                timepoint_boundaries=config_input.get('timepoint_boundaries')
            )

            # Parse the dependent variable
            dependent_variable_input = config_input.get('dependent_variable')
            if not dependent_variable_input:
                raise ValueError("No dependent variable defined")
            dependent_concept_id = dependent_variable_input.get('concept_id')
            dependent_entry = await uow.ontology.get_entry(entry_id=dependent_concept_id)
            if dependent_concept_id:
                dependent_scale = await uow.ontology.get_concept_scale(dependent_concept_id)
            else:
                dependent_scale = None
            dependent_variable = config_parser.parse_variable(
                variable_input=config_input.get('dependent_variable'),
                entry=dependent_entry,
                scale=dependent_scale,
                is_dependent=True
            )
            # Parse independent variables
            independent_variables = []
            for iv in config_input.get('independent_variables') or []:
                var_concept_id = iv.get('concept_id')
                if var_concept_id:
                    concept = await uow.ontology.get_entry(entry_id=var_concept_id)
                    scale = await uow.ontology.get_concept_scale(var_concept_id)
                else:
                    concept = None
                    scale = None
                parsed_variable = config_parser.parse_variable(variable_input=iv, entry=concept, scale=scale, is_dependent=False)
                if parsed_variable in independent_variables:
                    raise ValueError(f"Duplicate independent variable found: {parsed_variable}")
                independent_variables.append(parsed_variable)
            # Parse the interaction terms
            interaction_terms = config_parser.parse_interaction_terms(config_input.get('interaction_terms'), independent_variables)


            # Build a config object
            parsed_config = AnalysisConfig(
                name=config_input.get('name'),
                dataset_ids=config_input.get('dataset_ids'),
                dependent_variable=dependent_variable,
                independent_variables=independent_variables,
                interaction_terms=interaction_terms,
                timepoint_boundaries=config_parser.timepoint_boundaries
            )
            # Now hand it into the parser for final validation
            config_parser.config = parsed_config
            config_parser.validate_config()
            config_parser.build_df()
            config_parser.fit_model()
            anova = config_parser.get_anova()
            group_stats = config_parser.get_group_stats()
            tukey = config_parser.get_tukey_hsd()
            result = {
                'anova': anova,
                'group': group_stats,
                'tukey': tukey
            }
            await state_store.set_analysis_result(analysis_id=event.analysis_id, result=result)

    except Exception as e:
        await state_store.set_errors(key=event.analysis_id, errors=[str(e)])
        await state_store.set_status(key=event.analysis_id, status=SubmissionStatus.FAILED)
