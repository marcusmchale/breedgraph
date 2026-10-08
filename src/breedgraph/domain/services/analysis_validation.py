"""
Semantic validation of analysis configurations.

Structural validation (types, required fields, domain invariants) is performed by the importers.
These functions check the configuration as a whole, without data access,
and return CONFIG_INVALID messages with input paths.
"""
from breedgraph.domain.model.analysis import (
    AnalysisRequest, AnalysisSpec, AnovaSpec, DescriptiveSpec, CorrelationSpec, MDSSpec, OutlierSpec,
    AnalysisGrouping, AnalysisTerm, AnalysisTermReference, AnalysisTermType, TermRepresentationType,
    TermAggregation, TermEffect, EstimatedMeans, EstimatedMeansContrast, InteractionTerm,
    AnalysisMessage, AnalysisErrorCode
)

Path = list[str]


def _invalid(message: str, path: Path) -> AnalysisMessage:
    return AnalysisMessage(code=AnalysisErrorCode.CONFIG_INVALID, message=message, path=path)

def _describe(reference: AnalysisTermReference) -> str:
    if reference.type == AnalysisTermType.CONCEPT:
        return f"concept {reference.concept_id}"
    if reference.type == AnalysisTermType.RECORD_GROUP:
        return f"record group dimension '{reference.record_group_dimension}'"
    return reference.type.value


def validate_dataset_ids(dataset_ids: list[int]) -> list[AnalysisMessage]:
    if len(set(dataset_ids)) != len(dataset_ids):
        return [_invalid("Datasets must not be listed more than once", ['datasetIds'])]
    return []


def validate_dimensions(grouping: AnalysisGrouping, path: Path) -> list[AnalysisMessage]:
    """Dimension names are unique and each grouping contributes to at most one dimension."""
    messages = []
    names: set[str] = set()
    grouping_owner: dict[int, str] = {}
    for i, dimension in enumerate(grouping.record_groups):
        dimension_path = path + ['recordGroups', str(i)]
        key = dimension.name.casefold()
        if key in names:
            messages.append(_invalid(
                f"Record group dimension names must be unique: '{dimension.name}'", dimension_path + ['name']
            ))
        names.add(key)
        for j, grouping_id in enumerate(dimension.grouping_ids):
            if grouping_id in grouping_owner:
                messages.append(_invalid(
                    f"Grouping {grouping_id} is used by dimensions "
                    f"'{grouping_owner[grouping_id]}' and '{dimension.name}'",
                    dimension_path + ['groupingIds', str(j)]
                ))
            grouping_owner.setdefault(grouping_id, dimension.name)
    if grouping.unit is not None and len(set(grouping.unit.unit_ids)) != len(grouping.unit.unit_ids):
        messages.append(_invalid("Units must not be listed more than once", path + ['unit', 'unitIds']))
    if grouping.germplasm is not None and len(set(grouping.germplasm.germplasm_ids)) != len(grouping.germplasm.germplasm_ids):
        messages.append(_invalid("Germplasm must not be listed more than once", path + ['germplasm', 'germplasmIds']))
    return messages


def validate_reference(reference: AnalysisTermReference, grouping: AnalysisGrouping, path: Path) -> list[AnalysisMessage]:
    """Domain terms require their dimension to be configured."""
    required = {
        AnalysisTermType.TIME: ('time', 'grouping.time'),
        AnalysisTermType.GERMPLASM: ('germplasm', 'grouping.germplasm'),
        AnalysisTermType.POSITION: ('position', 'grouping.position'),
    }
    if reference.type in required:
        attr, label = required[reference.type]
        if getattr(grouping, attr) is None:
            return [_invalid(f"{reference.type.value} terms require {label}", path + ['type'])]
    if reference.type == AnalysisTermType.RECORD_GROUP:
        if grouping.get_record_group_dimension(reference.record_group_dimension) is None:
            return [_invalid(
                f"Record group dimension '{reference.record_group_dimension}' "
                f"is not configured in grouping.recordGroups",
                path + ['recordGroupDimension']
            )]
    return []


def _validate_known(reference: AnalysisTermReference, known: set[AnalysisTermReference], path: Path) -> list[AnalysisMessage]:
    if reference not in known:
        return [_invalid(f"{_describe(reference)} is not one of the analysis terms", path)]
    return []


def validate_terms(spec: AnalysisSpec, path: Path, models: bool) -> list[AnalysisMessage]:
    """
    :param models: whether the analysis fits a statistical model, so effects and random slopes apply
    """
    messages = []
    seen: set[AnalysisTermReference] = set()
    known = {t.reference for t in spec.terms}
    for i, term in enumerate(spec.terms):
        term_path = path + ['terms', str(i)]
        reference = term.reference
        if reference in seen:
            messages.append(_invalid(f"{_describe(reference)} is listed more than once", term_path + ['reference']))
        seen.add(reference)
        messages += validate_reference(reference, spec.grouping, term_path + ['reference'])
        messages += _validate_term_options(term, term_path)

        if not models:
            if term.effect is not None:
                messages.append(_invalid("Effects only apply to statistical models", term_path + ['effect']))
            if term.random_slope_terms:
                messages.append(_invalid("Random slopes only apply to statistical models", term_path + ['randomSlopeTerms']))
            continue

        if term.random_slope_terms and term.effect != TermEffect.RANDOM:
            messages.append(_invalid("Random slopes require a RANDOM term", term_path + ['randomSlopeTerms']))
        for j, slope in enumerate(term.random_slope_terms):
            slope_path = term_path + ['randomSlopeTerms', str(j)]
            if slope == reference:
                messages.append(_invalid("A term cannot be a random slope for itself", slope_path))
            else:
                messages += _validate_known(slope, known, slope_path)
    return messages


def _validate_term_options(term: AnalysisTerm, path: Path) -> list[AnalysisMessage]:
    messages = []
    if term.reference.type != AnalysisTermType.CONCEPT:
        # domain terms are levels of observation identity
        if term.representation == TermRepresentationType.CONTINUOUS:
            messages.append(_invalid("Domain terms cannot be represented as CONTINUOUS", path + ['representation']))
        if term.transformations:
            messages.append(_invalid("Transformations only apply to concept terms", path + ['transformations']))
        if term.aggregation != TermAggregation.NONE:
            messages.append(_invalid("Aggregation only applies to concept terms", path + ['aggregation']))
        if term.binning is not None:
            messages.append(_invalid(
                "Binning only applies to concept terms; time is binned by grouping.time", path + ['binning']
            ))
    if term.level_order is not None:
        if term.representation == TermRepresentationType.CONTINUOUS:
            messages.append(_invalid("Level order does not apply to CONTINUOUS terms", path + ['levelOrder']))
        if len(set(term.level_order)) != len(term.level_order):
            messages.append(_invalid("Levels must not be listed more than once", path + ['levelOrder']))
    if term.transformations and term.representation not in (None, TermRepresentationType.CONTINUOUS):
        messages.append(_invalid("Transformations only apply to CONTINUOUS terms", path + ['transformations']))
    if term.binning is not None and term.transformations:
        messages.append(_invalid("Binned terms cannot be transformed", path + ['transformations']))
    return messages


def validate_interactions(
        interactions: list[InteractionTerm],
        allowed: set[AnalysisTermReference],
        path: Path
) -> list[AnalysisMessage]:
    messages = []
    seen: set[frozenset] = set()
    for i, interaction in enumerate(interactions):
        interaction_path = path + ['interactions', str(i)]
        if len(set(interaction.terms)) != len(interaction.terms):
            messages.append(_invalid("An interaction lists a term more than once", interaction_path + ['terms']))
        key = frozenset(interaction.terms)
        if key in seen:
            messages.append(_invalid("Interaction is listed more than once", interaction_path))
        seen.add(key)
        for j, reference in enumerate(interaction.terms):
            if reference not in allowed:
                messages.append(_invalid(
                    f"{_describe(reference)} is not a model term", interaction_path + ['terms', str(j)]
                ))
    return messages


def validate_estimated_means(
        estimated_means: list[EstimatedMeans],
        allowed: set[AnalysisTermReference],
        spec: AnalysisSpec,
        path: Path
) -> list[AnalysisMessage]:
    """Estimated means are calculated over levels of categorical model terms."""
    messages = []
    for i, means in enumerate(estimated_means):
        means_path = path + ['estimatedMeans', str(i)]
        for field, references in (('terms', means.terms), ('by', means.by)):
            for j, reference in enumerate(references):
                reference_path = means_path + [field, str(j)]
                if reference not in allowed:
                    messages.append(_invalid(f"{_describe(reference)} is not a model term", reference_path))
                    continue
                term = spec.get_term(reference)
                if term.representation == TermRepresentationType.CONTINUOUS:
                    messages.append(_invalid("Means are estimated over levels of categorical terms", reference_path))
                if term.effect == TermEffect.RANDOM:
                    messages.append(_invalid("Means are estimated over levels of fixed terms", reference_path))
        if set(means.terms) & set(means.by):
            messages.append(_invalid("A term cannot be both estimated and conditioning", means_path + ['by']))
        if len(set(means.terms)) != len(means.terms) or len(set(means.by)) != len(means.by):
            messages.append(_invalid("A term is listed more than once", means_path))
        if means.contrast == EstimatedMeansContrast.TRT_VS_CTRL:
            if means.control is None:
                messages.append(_invalid("A control level is required for TRT_VS_CTRL", means_path + ['control']))
            if len(means.terms) != 1:
                messages.append(_invalid("TRT_VS_CTRL requires exactly one term", means_path + ['terms']))
        elif means.control is not None:
            messages.append(_invalid("A control level only applies to TRT_VS_CTRL", means_path + ['control']))
    return messages


def _concept_terms(spec: AnalysisSpec) -> list[AnalysisTerm]:
    return [t for t in spec.terms if t.reference.type == AnalysisTermType.CONCEPT]


def validate_anova(spec: AnovaSpec, path: Path) -> list[AnalysisMessage]:
    messages = validate_terms(spec, path, models=True)
    response = spec.get_term(spec.response)
    response_path = path + ['response']
    if response is None:
        messages.append(_invalid(f"The response, {_describe(spec.response)}, is not one of the analysis terms", response_path))
    else:
        if spec.response.type != AnalysisTermType.CONCEPT:
            messages.append(_invalid("The response must be a CONCEPT term", response_path))
        if response.representation not in (None, TermRepresentationType.CONTINUOUS):
            messages.append(_invalid("The response must be represented as CONTINUOUS", response_path))
        if response.binning is not None:
            messages.append(_invalid("The response cannot be binned", response_path))
        if response.effect is not None or response.random_slope_terms:
            messages.append(_invalid("The response must not have an effect", response_path))

    model_terms = {t.reference for t in spec.model_terms}
    if not model_terms:
        messages.append(_invalid("At least one model term is required in addition to the response", path + ['terms']))
    random_terms = {t.reference for t in spec.model_terms if t.effect == TermEffect.RANDOM}
    for i, term in enumerate(spec.terms):
        if term.reference in random_terms and term.representation == TermRepresentationType.CONTINUOUS:
            messages.append(_invalid("RANDOM terms must be categorical", path + ['terms', str(i), 'representation']))
    for i, interaction in enumerate(spec.interactions):
        if set(interaction.terms) & random_terms:
            messages.append(_invalid(
                "Interactions are between fixed terms; use a record group or unit dimension for nested random effects",
                path + ['interactions', str(i)]
            ))
    for i, term in enumerate(spec.terms):
        for j, slope in enumerate(term.random_slope_terms):
            if slope == spec.response:
                messages.append(_invalid(
                    "The response cannot be a random slope", path + ['terms', str(i), 'randomSlopeTerms', str(j)]
                ))
    messages += validate_interactions(spec.interactions, model_terms, path)
    messages += validate_estimated_means(spec.estimated_means, model_terms, spec, path)
    return messages


def validate_descriptive(spec: DescriptiveSpec, path: Path) -> list[AnalysisMessage]:
    messages = validate_terms(spec, path, models=False)
    if not _concept_terms(spec):
        messages.append(_invalid("At least one CONCEPT term is required", path + ['terms']))
    categorical = {t.reference for t in spec.terms if t.representation != TermRepresentationType.CONTINUOUS}
    messages += validate_interactions(spec.interactions, categorical, path)
    messages += validate_estimated_means(spec.estimated_means, categorical, spec, path)
    return messages


def validate_correlation(spec: CorrelationSpec, path: Path) -> list[AnalysisMessage]:
    messages = validate_terms(spec, path, models=False)
    if len(_concept_terms(spec)) < 2:
        messages.append(_invalid("At least two CONCEPT terms are required", path + ['terms']))
    for i, term in enumerate(spec.terms):
        if term.reference.type == AnalysisTermType.CONCEPT and term.representation == TermRepresentationType.CATEGORICAL:
            messages.append(_invalid(
                "Correlated terms must be CONTINUOUS or ORDINAL", path + ['terms', str(i), 'representation']
            ))
    return messages


def validate_mds(spec: MDSSpec, path: Path) -> list[AnalysisMessage]:
    messages = validate_terms(spec, path, models=False)
    if not _concept_terms(spec):
        messages.append(_invalid("At least one CONCEPT term is required", path + ['terms']))
    for i, term in enumerate(spec.terms):
        if term.reference.type == AnalysisTermType.CONCEPT and term.representation not in (None, TermRepresentationType.CONTINUOUS):
            messages.append(_invalid("MDS requires CONTINUOUS terms", path + ['terms', str(i), 'representation']))
    if spec.clustering is not None and spec.clustering.clusters is None:
        messages.append(_invalid("The number of clusters is required", path + ['clustering', 'clusters']))
    return messages


def validate_outliers(spec: OutlierSpec, path: Path) -> list[AnalysisMessage]:
    messages = validate_terms(spec, path, models=False)
    if not _concept_terms(spec):
        messages.append(_invalid("At least one CONCEPT term is required", path + ['terms']))
    for i, term in enumerate(spec.terms):
        if term.reference.type == AnalysisTermType.CONCEPT and term.representation not in (None, TermRepresentationType.CONTINUOUS):
            messages.append(_invalid(
                "Outlier detection requires CONTINUOUS terms", path + ['terms', str(i), 'representation']
            ))
    return messages


SPEC_VALIDATORS = {
    AnovaSpec: validate_anova,
    DescriptiveSpec: validate_descriptive,
    CorrelationSpec: validate_correlation,
    MDSSpec: validate_mds,
    OutlierSpec: validate_outliers,
}


def validate_request(request: AnalysisRequest) -> list[AnalysisMessage]:
    """All configuration errors of an analysis request; empty if valid."""
    path = [request.analysis_type.input_field]
    spec = request.spec
    messages = validate_dataset_ids(request.dataset_ids)
    messages += validate_dimensions(spec.grouping, path + ['grouping'])
    messages += SPEC_VALIDATORS[type(spec)](spec, path)
    return messages
