from collections import Counter

from breedgraph.domain.model.analysis import AnalysisMessage, AnalysisWarningCode
from breedgraph.domain.model.analysis_context import AnalysisContext
from breedgraph.domain.services.analysis_dimensions import build_dimension_resolvers
from breedgraph.domain.services.analysis_exclusions import ExclusionApplier
from breedgraph.domain.services.observation_builder import ObservationBuilder, ObservationFrame


def prepare_observations(context: AnalysisContext, warnings: list[AnalysisMessage]) -> ObservationFrame:
    """
    Apply exclusions, assign records to dimensions and build the observation frame.

    :param warnings: list to which warnings are appended
    :raises AnalysisFailed: when the observations cannot be built
    """
    resolvers = build_dimension_resolvers(context)
    exclusions = ExclusionApplier(context.request.exclusions, context.groupings)
    builder = ObservationBuilder(context, resolvers)

    record_counts: Counter[int] = Counter()
    included_counts: Counter[int] = Counter()
    for record in context.records():
        record_counts[record.dataset_id] += 1
        if exclusions.is_excluded(record):
            continue
        # assign every dimension, so each warning reports all records it could not assign
        levels = {resolver.name: resolver.assign(record) for resolver in resolvers}
        if any(level is None for level in levels.values()):
            continue
        builder.add(record, levels)
        included_counts[record.dataset_id] += 1

    warnings.extend(exclusions.warnings())
    for resolver in resolvers:
        warnings.extend(resolver.warnings())
    for i, dataset_id in enumerate(context.request.dataset_ids):
        if record_counts[dataset_id] and not included_counts[dataset_id]:
            warnings.append(AnalysisMessage(
                code=AnalysisWarningCode.DATASET_FULLY_EXCLUDED,
                message=f"All records of dataset {dataset_id} were excluded",
                path=['datasetIds', str(i)]
            ))

    return builder.build(warnings)
