"""
Applies the exclusion rules of an analysis to its records.

A record is excluded if it matches ANY rule. Within a rule, ALL provided criteria must match,
and within a list criterion ANY element may match. Matching is exact.
"""
from breedgraph.domain.model.analysis import AnalysisExclusion, AnalysisMessage, AnalysisWarningCode
from breedgraph.domain.model.analysis_context import AnalysisRecord
from breedgraph.domain.model.programs import RecordGroupingStored
from breedgraph.domain.services.record_grouping_resolver import record_has_member


class ExclusionApplier:

    def __init__(self, exclusions: list[AnalysisExclusion], groupings: dict[int, RecordGroupingStored]):
        """
        :param groupings: record groupings of the studies of the selected datasets, to resolve code scopes
        """
        self.exclusions = exclusions
        self.groupings = groupings
        self.counts = [0] * len(exclusions)

    def rule_matches(self, rule: AnalysisExclusion, record: AnalysisRecord) -> bool:
        unit = record.unit
        if rule.record_ids is not None and record.record_id not in rule.record_ids:
            return False
        if rule.unit_ids is not None and record.unit_id not in rule.unit_ids:
            return False
        if rule.germplasm_ids is not None and (unit is None or unit.germplasm_id not in rule.germplasm_ids):
            return False
        if rule.study_ids is not None and record.study_id not in rule.study_ids:
            return False
        if rule.record_groups is not None and not any(
            record_has_member(self.groupings.get(member.grouping_id), member, record.dataset_id, record.groups)
            for member in rule.record_groups
        ):
            return False
        if not rule.matches_record_time(record.start, record.end):
            return False
        if rule.positions and not rule.matches_positions(unit.positions if unit is not None else []):
            return False
        return True

    def is_excluded(self, record: AnalysisRecord) -> bool:
        """Whether the record is excluded. Matches are counted for every rule."""
        excluded = False
        for i, rule in enumerate(self.exclusions):
            if self.rule_matches(rule, record):
                self.counts[i] += 1
                excluded = True
        return excluded

    def warnings(self) -> list[AnalysisMessage]:
        return [
            AnalysisMessage(
                code=AnalysisWarningCode.EXCLUDED_BY_CONFIG,
                message=f"Exclusion rule {i} matched {count} records",
                path=['exclusions', str(i)]
            )
            for i, count in enumerate(self.counts)
        ]
