from abc import abstractmethod

import pandas as pd
import numpy as np
import re
import statsmodels.formula.api as smf
import statsmodels.api as sm
from statsmodels.stats.multicomp import pairwise_tukeyhsd

from breedgraph.domain.model.ontology import ScaleType, ScaleBase, FactorStored, VariableStored
from breedgraph.domain.model.datasets import DatasetStored, DataRecordStored
from breedgraph.domain.model.blocks import Block
from breedgraph.domain.model.analysis import (
    AnalysisConfig, AnalysisVariable, AnalysisVariableType, AnalysisTreatment
)
from typing import List, Set, Dict
from collections import defaultdict
import logging
logger = logging.getLogger(__name__)

class AnalysisConfigParser:
    def __init__(
            self,
            datasets: List[DatasetStored],
            blocks: List[Block],
            unit_ids: Set[int],
            timepoint_boundaries: List[str | np.datetime64] | None = None
    ):
        self.datasets = datasets
        self.blocks = blocks
        self.unit_ids = unit_ids
        self.timepoint_boundaries = timepoint_boundaries

        self.config: AnalysisConfig | None = None
        self.concept_to_records = defaultdict(list)
        self.unit_to_germplasm = {}
        self.concept_to_label = {}
        self.concept_to_scale = {}
        self.concept_to_entry = {}
        # Store these when parsing
        self.concept_independent_variable_labels = []
        self.timepoint_variable_label = None
        self.germplasm_variable_label = None
        self.df_all = None
        self.fit = None
        self.group_cols = None

    def parse_variable(
            self,
            variable_input: dict,
            entry: FactorStored|VariableStored|None = None,
            scale = None,
            is_dependent = False
    ) -> AnalysisVariable:
        if not variable_input:
            raise ValueError("No variable defined")
        variable_type = AnalysisVariableType[variable_input.get('type')]

        if variable_type == AnalysisVariableType.GERMPLASM:
            scale = ScaleBase(
                name=variable_input.get('label'),
                scale_type=ScaleType.NOMINAL
            )
            self.concept_to_label['germplasm'] = variable_input.get('label')
            self.concept_to_scale['germplasm'] = scale
            self.germplasm_variable_label = variable_input.get('label')
        elif variable_type == AnalysisVariableType.TIMEPOINT:
            scale = ScaleBase(
                name=variable_input.get('label'),
                scale_type=ScaleType.ORDINAL
            )
            self.concept_to_label['timepoint'] = variable_input.get('label')
            self.concept_to_scale['timepoint'] = scale
            self.timepoint_variable_label = variable_input.get('label')
            self.parse_timepoints()
            if not self.timepoint_boundaries:
                raise ValueError("timepoint_boundaries is required for AnalysisVariableType timepoint")
        else:
            concept_id = variable_input.get('concept_id')
            if not concept_id:
                raise ValueError("concept_id is required for AnalysisVariableType concept")
            self.concept_to_label[concept_id] = variable_input.get('label')
            self.concept_to_scale[concept_id] = scale
            self.concept_to_entry[concept_id] = entry
            if not is_dependent:
                self.concept_independent_variable_labels.append(variable_input.get('label'))
        if scale.scale_type in [ScaleType.NOMINAL, ScaleType.ORDINAL]:
            if is_dependent:
                raise ValueError("Unsupported scale type for dependent variable")
            treatment = AnalysisTreatment.CATEGORICAL
        elif scale.scale_type == ScaleType.NUMERICAL:
            treatment = AnalysisTreatment.CONTINUOUS
        else:
            raise ValueError(f"Unsupported scale type for variable: {variable_input.get('label')}")

        return AnalysisVariable(
            type=variable_type,
            treatment=treatment,
            scale=scale,
            label=variable_input.get('label'),
            concept_id=variable_input.get('concept_id')
        )

    def parse_timepoints(self):
        timepoints = self.timepoint_boundaries
        for i, t in enumerate(timepoints):
            if isinstance(t, np.datetime64):
                continue
            else:
                timepoints[i] = np.datetime64(t)
        return timepoints

    @staticmethod
    def parse_interaction_terms(terms: List[Dict[str, int]], independent_variables: List[AnalysisVariable]):
        parsed_terms = []
        for i, term in enumerate(terms):
            if not 'var_1_index' in term or not 'var_2_index' in term:
                raise ValueError("Interaction term input must contain 'var_1_index' and 'var_2_index'")
            iv1, iv2 = term['var_1_index'], term['var_2_index']
            if iv1 > len(independent_variables) or iv2 > len(independent_variables):
                raise ValueError("Interaction term indices should be within the range of independent variables")
            if iv1 == iv2:
                raise ValueError("Interaction term indices should not be the same")
            parsed_terms.append((iv1, iv2))
        return parsed_terms

    def validate_germplasm(self):
        # validate that the user has access to germplasm details on the referenced units
        # ideally they can see the germplasm too, but id is sufficient for analysis grouping
        # labeling is a separate concern
        valid_units = set()
        invalid_units = set()
        for block in self.blocks:
            to_find = self.unit_ids.copy()
            for unit_id in to_find:
                if block.has_unit(unit_id):
                    unit = block.get_unit(unit_id)
                    if unit:
                        if unit.germplasm:
                            self.unit_to_germplasm[unit_id] = unit.germplasm
                            valid_units.add(unit_id)
                        else:
                            invalid_units.add(unit_id)
                else:
                    continue
            to_find = to_find - valid_units - invalid_units
            if not to_find:
                break
        if not valid_units == self.unit_ids:
            not_found = self.unit_ids - valid_units - invalid_units
            if not_found:
                raise ValueError(
                    f"Some units in these datasets were not found, you may need to request access: {not_found}"
                )
            elif invalid_units:
                raise ValueError(
                    f"Units are missing germplasm details: {invalid_units} "
                )
            else:
                raise ValueError(
                    f"Unknown error occurred in validating unit germplasm details for units: {self.unit_ids}"
                )

    def validate_config(self):
        # Validate the datasets before committing to analysis
        if not self.config:
            raise ValueError("No config provided for analysis")
        if not self.datasets:
            raise ValueError("No datasets provided for analysis")
        if not self.config.dependent_variable:
            raise ValueError("No dependent variable provided for analysis")
        independent_variables = self.config.independent_variables
        if not independent_variables:
            raise ValueError("No independent variables provided")
        for iv in independent_variables:
            if iv.type == AnalysisVariableType.GERMPLASM:
                self.validate_germplasm()

    def get_timepoint_labels(self):
        boundaries = self.config.timepoint_boundaries
        labels = []
        # left open-ended bin
        labels.append(f"<{boundaries[0]}")
        # interior bins
        for left, right in zip(boundaries[:-1], boundaries[1:]):
            labels.append(f"{left}–{right}")
        # right open-ended bin
        labels.append(f">{boundaries[-1]}")
        return labels

    def assign_timepoints(self, df):
        boundaries = [pd.Timestamp(b) for b in self.config.timepoint_boundaries]
        if boundaries:
            # use pd.cut on the midpoint of start-end
            midpoints = df['start'] + (df['end'] - df['start']) / 2
            start = midpoints.min()
            end = midpoints.max()
            bins = list(boundaries)
            if start < min(bins):
                bins.insert(0, start)
            if end >= max(bins):
                bins.append(end + pd.Timedelta(nanoseconds=1)) # ensure is right open
            labels = (
                [f"<{self.config.timepoint_boundaries[0]}"] +
                [f"{l}–{r}" for l, r in zip(self.config.timepoint_boundaries[:-1], self.config.timepoint_boundaries[1:])] +
                [f">{self.config.timepoint_boundaries[-1]}"]
            )
            df[self.timepoint_variable_label] = pd.cut(midpoints, bins=bins, labels=labels, include_lowest=True, right=False)
        return df

    def assign_germplasm(self, df):
        if self.unit_to_germplasm:
            df[self.germplasm_variable_label] = df['unit'].map(self.unit_to_germplasm)
            df[self.germplasm_variable_label] = df[self.germplasm_variable_label].astype('category')
        return df

    def dataset_to_long_df(self, records: List[DataRecordStored], concept_id: int):
        label = self.concept_to_label[concept_id]
        scale = self.concept_to_scale[concept_id]
        cols = ['unit', 'value', 'start', 'end']
        df = pd.DataFrame([{k: getattr(r, k) for k in cols} for r in records])
        df = self.assign_timepoints(df)
        df = self.assign_germplasm(df)
        df = df.rename(columns={'value': label})
        df.drop(columns=['start', 'end'], inplace=True, errors='ignore')
        if scale.scale_type == ScaleType.NUMERICAL:
            df[label] = pd.to_numeric(df[label], errors='coerce').astype(float)
        elif scale.scale_type in [ScaleType.NOMINAL]:
            df[label] = df[label].astype('category')
        elif scale.scale_type in [ScaleType.ORDINAL]:
            df[label] = df[label].astype(int)
        return df

    @staticmethod
    def term(var: AnalysisVariable) -> str:
        label = var.label
        if var.scale.scale_type == ScaleType.NOMINAL:
            return f'C(Q("{label}"))'
        else:
            return f'Q("{label}")'

    @staticmethod
    def clean_term(term):
        # remove C( from nominal scales and Q("...") everywhere
        term = re.sub(r'C\(Q\("(.+?)"\)\)', r'\1', term)
        # remove any remaining Q("...")
        term = re.sub(r'Q\("(.+?)"\)', r'\1', term)
        return term

    def build_df(self):
        logger.debug("build df")
        df_all = None
        for dataset in self.datasets:
            if not dataset.concept in self.concept_to_label:
                continue
            df = self.dataset_to_long_df(dataset.records, concept_id = dataset.concept)
            # group by keys and average values for dependent
            label = self.concept_to_label[dataset.concept]
            group_keys = [c for c in df.columns if c != label]
            df = df.groupby(group_keys, as_index=False).agg({label: 'mean'})
            merge_keys = [c for c in df.columns if c != label]
            df = df[merge_keys + [label]]
            if df_all is None:
                df_all = df
            else:
                df_all = df_all.merge(df, on=merge_keys, how='outer')
        df_all['unit'] = df_all['unit'].astype(str)

        self.df_all = df_all

    def fit_model(self):
        logger.debug('fit model')
        terms = [self.term(v) for v in self.config.independent_variables]
        if self.config.interaction_terms:
            interaction_terms = [':'.join((terms[i], terms[j])) for i, j in self.config.interaction_terms]
            terms = terms + interaction_terms
        model_str = f"{self.term(self.config.dependent_variable)} ~ {' + '.join(terms)}"
        fit = smf.ols(model_str, data=self.df_all).fit()
        self.fit = fit

    @staticmethod
    def serialize_anova_row(row):
        return {
            'term': row['Term'],
            'sum_sq': row['sum_sq'],
            'df': row['df'],
            'f_value': row['F'] if not pd.isna(row['F']) else None,
            'p_value': row['PR(>F)'] if not pd.isna(row['PR(>F)']) else None
        }

    def get_anova(self):
        logger.debug('get anova')
        anova = sm.stats.anova_lm(self.fit, typ=2)
        anova.reset_index(inplace=True)
        anova.rename(columns={'index': 'Term'}, inplace=True)
        anova['Term'] = anova['Term'].apply(self.clean_term)
        return anova.apply(self.serialize_anova_row, axis=1).tolist()

    def serialize_group_row(self, row):
        group_array = [{'label': col, 'level': row[col]} for col in self.group_cols]
        return {
            'group': group_array,
            'mean': row['mean'],
            'sd': row['std'],
            'n': row['count'],
            'se': row['sem']
        }

    def get_group_stats(self):
        logger.debug('get group stats')
        group_cols = []
        value_col = self.config.dependent_variable.label
        for concept_id, entry in self.concept_to_entry.items():
            if isinstance(entry, FactorStored):
                group_cols.append(self.concept_to_label[concept_id])
        if self.timepoint_variable_label:
            group_cols.append(self.timepoint_variable_label)
            # rename levels from boundaries:
        if self.germplasm_variable_label:
            group_cols.append(self.germplasm_variable_label)
        self.group_cols = group_cols
        group_stats = self.df_all.groupby(group_cols)[value_col].agg(['mean', 'std', 'count', 'sem']).reset_index()
        # get quartiles and merge
        quartiles = self.get_quartiles().reset_index()
        group_stats = group_stats.merge(quartiles, on=self.group_cols, how='left')
        # serialize the group details
        group_stats = group_stats.apply(self.serialize_group_row, axis=1).tolist()
        return group_stats

    @staticmethod
    def stringify_series(s):
        # If categorical, just convert to string immediately
        if pd.api.types.is_categorical_dtype(s):
            return s.astype(str)

        # Convert floats that are whole numbers → Int64 → string
        if np.issubdtype(s.dtype, np.floating):
            mask = s.notna()
            if np.all(np.isclose(s[mask], s[mask].astype(np.int64))):
                s = s.astype("Int64")

        return s.astype(str)

    def get_tukey_hsd(self):
        logger.debug('get tukey hsd')
        # Convert all group_cols to string / coerced values
        df_strings = self.df_all[self.group_cols].apply(self.stringify_series)

        # Create a "group array" per row
        self.df_all['group_array'] = df_strings.apply(lambda row: row.tolist(), axis=1)

        # Use string version of the array as the temporary key for Tukey
        self.df_all['group_key'] = self.df_all['group_array'].apply(lambda x: "_".join(x))

        # Create the key → array lookup table (unique rows only)
        key_to_array = (
            self.df_all
            .assign(group_key=self.df_all['group_key'])
            .drop_duplicates(subset='group_key')
            .loc[:, ['group_key'] + self.group_cols]
            .set_index('group_key')
        )
        # Convert the group_cols to strings in key_to_array
        for col in self.group_cols:
            key_to_array[col] = self.stringify_series(key_to_array[col])

        tukey = pairwise_tukeyhsd(endog=self.df_all[self.config.dependent_variable.label], groups=self.df_all['group_key'])
        tukey_df = pd.DataFrame(data=tukey._results_table.data[1:], columns=tukey._results_table.data[0])
        # get reverse mapping of group name to group factors

        tukey_json_ready = []
        for _, row in tukey_df.iterrows():
            group1_key_to_array_row = key_to_array.loc[row['group1']]
            group1_array = [{'label': col, 'level': group1_key_to_array_row[col]} for col in self.group_cols]
            group2_key_to_array_row = key_to_array.loc[row['group2']]
            group2_array = [{'label': col, 'level': group2_key_to_array_row[col]} for col in self.group_cols]
            record = {
                'group1': group1_array,
                'group2': group2_array,
                'qval': row['p-adj'],
                'lower': row['lower'],
                'upper': row['upper']
            }
            tukey_json_ready.append(record)
        return tukey_json_ready

    def get_quartiles(self):
        logger.debug('get quartiles')
        dependent = self.config.dependent_variable.label
        grouped_quartiles = self.df_all.groupby(self.group_cols)[dependent].quantile([0.25, 0.5, 0.75]).unstack()
        grouped_quartiles.rename(columns={0.25: 'Q1', 0.5: 'median', 0.75: 'Q3'}, inplace=True)
        return grouped_quartiles