import pandas as pd
import numpy as np
import re
import warnings

import statsmodels.formula.api as smf
import statsmodels.api as sm
from statsmodels.stats.multicomp import pairwise_tukeyhsd

from breedgraph.domain.model import OntologyEntryStored
from breedgraph.domain.model.ontology import ScaleType, ScaleBase, ScaleStored, FactorStored, VariableStored
from breedgraph.domain.model.datasets import DatasetStored, DataRecordStored
from breedgraph.domain.model.blocks import Block
from breedgraph.domain.model.analysis import (
    AnalysisConfig, AnalysisVariable, AnalysisVariableType, AnalysisTreatment
)

from breedgraph.domain.importers import AnalysisImport, AnalysisVariableImport, InteractionTermImport

from typing import List, Set, Dict
from collections import defaultdict
import logging
logger = logging.getLogger(__name__)

class AnalysisService:
    def __init__(
            self,
            datasets: List[DatasetStored],
            blocks: List[Block],
            unit_ids: Set[int]
    ):
        self.datasets = datasets
        self.blocks = blocks
        self.unit_ids = unit_ids

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
            variable_input: AnalysisVariableImport,
            entry: OntologyEntryStored|None = None,
            scale: ScaleStored | None = None,
            is_dependent = False
    ) -> AnalysisVariable:
        if variable_input.type is AnalysisVariableType.GERMPLASM:
            scale = ScaleBase(
                name=variable_input.label,
                scale_type=ScaleType.NOMINAL
            )
            self.concept_to_label['germplasm'] = variable_input.label
            self.concept_to_scale['germplasm'] = scale
            self.germplasm_variable_label = variable_input.label
        elif variable_input.type is AnalysisVariableType.TIMEPOINT:
            scale = ScaleBase(
                name=variable_input.label,
                scale_type=ScaleType.ORDINAL
            )
            self.concept_to_label['timepoint'] = variable_input.label
            self.concept_to_scale['timepoint'] = scale
            self.timepoint_variable_label = variable_input.label

        else:
            concept_id = variable_input.concept_id
            if not concept_id:
                raise ValueError("concept_id is required for AnalysisVariableType concept")
            self.concept_to_label[concept_id] = variable_input.label
            self.concept_to_scale[concept_id] = scale
            if not isinstance(entry, (FactorStored, VariableStored)):
                raise ValueError("Concept must be factor or variable")
            self.concept_to_entry[concept_id] = entry
            if not is_dependent:
                self.concept_independent_variable_labels.append(variable_input.label)
            if scale is None:
                raise ValueError("Scale is required to parse concept variables")

        if scale.scale_type in [ScaleType.NOMINAL, ScaleType.ORDINAL]:
            if is_dependent:
                raise ValueError("Unsupported scale type for dependent variable")
            treatment = AnalysisTreatment.CATEGORICAL
        elif scale.scale_type == ScaleType.NUMERICAL:
            treatment = AnalysisTreatment.CONTINUOUS
        else:
            raise ValueError(f"Unsupported scale type for variable: {variable_input.label}")

        return AnalysisVariable(
            type=variable_input.type,
            treatment=treatment,
            scale=scale,
            label=variable_input.label,
            concept_id=variable_input.concept_id
        )

    @staticmethod
    def parse_interaction_terms(terms: List[InteractionTermImport], independent_variables: List[AnalysisVariable]):
        parsed_terms = []
        for i, term in enumerate(terms):
            if term.var_1_index == term.var_2_index:
                raise ValueError("Interaction term indices should not be the same")
            if term.var_1_index > len(independent_variables) or term.var_2_index > len(independent_variables):
                raise ValueError("Interaction term indices should be within the range of independent variables")
            parsed_terms.append((term.var_1_index, term.var_2_index))
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
        if not self.config:
            raise ValueError("Cannot get timepoint labels without config defined")
        if not self.config.timepoint_boundaries:
            raise ValueError("Timepoint boundaries are required to examine timepoint as a variable")
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

    @staticmethod
    def get_timepoints(df: pd.DataFrame) -> pd.Series:
        """
        Return the midpoint if both start and end are defined,
        or return whichever one is defined if only one exists.
        Raises ValueError if neither is defined.
        """
        start = pd.to_datetime(df['start'])
        end = pd.to_datetime(df['end'])

        both_missing = start.isna() & end.isna()
        if both_missing.any():
            raise ValueError("Cannot determine timepoint: both start and end are undefined")

        # Use fillna to substitute missing values, then compute midpoint
        filled_start = start.fillna(end)
        filled_end = end.fillna(start)

        return filled_start + (filled_end - filled_start) / 2

    def considering_time(self) -> bool:
        for iv in self.config.independent_variables:
            if iv.type == AnalysisVariableType.TIMEPOINT:
                return True
        return False

    def considering_germplasm(self) -> bool:
        for iv in self.config.independent_variables:
            if iv.type == AnalysisVariableType.GERMPLASM:
                return True
        return False

    def assign_timepoints(self, df):
        if not self.config:
            raise ValueError("Cannot get timepoint labels without config defined")
        if not self.considering_time():
            return df

        if not self.config.timepoint_boundaries:
            raise ValueError("Timepoint boundaries are required to examine timepoint as a variable")
        boundaries = [pd.Timestamp(b) for b in self.config.timepoint_boundaries]
        if boundaries:
            # use pd.cut on the midpoint of start-end
            timepoints = self.get_timepoints(df)
            start = timepoints.min()
            end = timepoints.max()
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
            df[self.timepoint_variable_label] = pd.cut(timepoints, bins=bins, labels=labels, include_lowest=True, right=False)
        return df

    def assign_germplasm(self, df):
        if not self.considering_germplasm():
            return df

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
        serialized_row = {
            'term': row['Term'],
            'sum_sq': row['sum_sq'],
            'df': row['df']
        }
        if 'F' in row:
            serialized_row.update({
                'f_value': row['F'] if not pd.isna(row['F']) else None,
                'p_value': row['PR(>F)'] if not pd.isna(row['PR(>F)']) else None
            })
        elif 'Wald' in row:
            serialized_row.update({
                'wald': row['Wald'] if not pd.isna(row['Wald']) else None,
                'p_value': row['PR(>Wald)'] if not pd.isna(row['PR(>Wald)']) else None
            })
        else:
            serialized_row.update({
                'wald': None,
                'p_value': None
            })
        return serialized_row

    def is_full_rank(self):
        X = self.fit.model.exog
        return np.linalg.matrix_rank(X) == X.shape[1]

    @staticmethod
    def robust_anova_with_ss(fit_obj):
        """
        Computes ANOVA table safely across all edge cases by catching
        RuntimeWarnings locally without changing global pandas/numpy settings.
        """
        # Pre-extract residual metrics for backup SS calculations
        try:
            ssr = fit_obj.ssr
            sst = fit_obj.ess + fit_obj.ssr if hasattr(fit_obj, 'ess') else np.nan
        except AttributeError:
            ssr, sst = np.nan, np.nan

        # --- Tier 1: Try Standard Type-II F-Test ---
        # We wrap this in a warnings filter to catch the divide-by-zero or NaN warnings
        with warnings.catch_warnings():
            warnings.filterwarnings('error', category=RuntimeWarning)
            try:
                anova_df = sm.stats.anova_lm(fit_obj, typ=2)

                # Catch the numerical edge cases where it didn't warn but returned zeros
                if not (anova_df.iloc[:, 0] == 0).any():
                    return anova_df
            except (RuntimeWarning, Exception):
                pass  # Fall through to Tier 2 if a warning or exception occurs

        # --- Tier 2: Try Explicit Type-II Wald Test ---
        with warnings.catch_warnings():
            warnings.filterwarnings('error', category=RuntimeWarning)
            try:
                anova_df = sm.stats.anova_lm(fit_obj, typ=2, test="Wald")

                if not (anova_df.iloc[:, 0] == 0).any():
                    if 'sum_sq' not in anova_df.columns:
                        anova_df.insert(0, 'sum_sq', np.nan)
                        anova_df.insert(1, 'mean_sq', np.nan)
                    return anova_df
            except (RuntimeWarning, Exception):
                pass  # Fall through to Tier 3 if it fails or warns

        # --- Tier 3: Fallback to Pseudo-Inverse Wald Terms ---
        try:
            wald_terms = fit_obj.wald_test_terms(skip_single=False)
            anova_df = wald_terms.summary_frame()

            processed_df = pd.DataFrame(index=anova_df.index)
            mse = fit_obj.scale if hasattr(fit_obj, 'scale') else 1.0

            # Calculate Sum of Squares using the Wald statistic
            processed_df['sum_sq'] = (anova_df['statistic'] / anova_df['df_constraint']) * mse * anova_df[
                'df_constraint']
            processed_df['mean_sq'] = processed_df['sum_sq'] / anova_df['df_constraint']
            processed_df['df'] = anova_df['df_constraint']
            processed_df['F'] = anova_df['statistic'] / anova_df['df_constraint']
            processed_df['PR(>F)'] = wald_terms.pvalues if hasattr(wald_terms, 'pvalues') else anova_df['pvalue']

            # Manually append the Residual row to match standard ANOVA shapes
            if not np.isnan(ssr):
                df_resid = fit_obj.df_resid
                residuals_row = pd.DataFrame({
                    'sum_sq': [ssr],
                    'mean_sq': [ssr / df_resid if df_resid > 0 else np.nan],
                    'df': [df_resid],
                    'F': [np.nan],
                    'PR(>F)': [np.nan]
                }, index=['Residual'])
                processed_df = pd.concat([processed_df, residuals_row])

            return processed_df
        except Exception:
            pass

        # --- Tier 4: Safe Empty DataFrame ---
        terms = fit_obj.model.xnames if hasattr(fit_obj.model, 'xnames') else ['Intercept']
        terms_with_res = terms + ['Residual']
        return pd.DataFrame(np.nan, index=terms_with_res, columns=['sum_sq', 'mean_sq', 'df', 'F', 'PR(>F)'])

    def get_anova(self):
        anova_df = self.robust_anova_with_ss(self.fit)
        anova_df.reset_index(inplace=True)
        anova_df.rename(columns={'index': 'Term'}, inplace=True)
        anova_df['Term'] = anova_df['Term'].apply(self.clean_term)
        return anova_df.apply(self.serialize_anova_row, axis=1).tolist()

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
            scale = self.concept_to_scale[concept_id]
            if scale.scale_type in [ScaleType.ORDINAL, ScaleType.NOMINAL]:
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