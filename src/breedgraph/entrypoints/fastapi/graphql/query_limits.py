"""
Refuses a query larger than the API answers (config/queries.py): its fields nested too deep, too many fields asked for,
or too many lists nested, each list multiplying what is asked below it. Introspection may nest only as many lists as
the standard introspection query does, as its lists run over the whole schema and loop (a type's fields have types,
which have fields), so that a few more would ask for millions of objects.

The query is measured as it would run, each use of a fragment counted, and measuring stops at the first limit passed,
so that fragments spreading others many times over make no work of their own.
"""
from graphql import GraphQLError, GraphQLList, ValidationRule, get_named_type, get_nullable_type
from graphql.language import FieldNode, FragmentSpreadNode, OperationDefinitionNode, SelectionSetNode
from graphql.type.introspection import SchemaMetaFieldDef, TypeMetaFieldDef, TypeNameMetaFieldDef

from breedgraph.config import MAX_QUERY_DEPTH, MAX_QUERY_FIELDS, MAX_QUERY_LISTS

QUERY_TOO_LARGE = 'QUERY_TOO_LARGE'
# types, their fields, and their fields' arguments, as the standard introspection query asks
INTROSPECTION_LISTS = 3
META_FIELDS = {'__schema': SchemaMetaFieldDef, '__type': TypeMetaFieldDef, '__typename': TypeNameMetaFieldDef}


class TooLarge(Exception):
    pass


class QueryLimits(ValidationRule):
    def enter_operation_definition(self, node: OperationDefinitionNode, *_args):
        root = self.context.schema.get_root_type(node.operation)
        if root is None:
            return
        self.fields = 0
        try:
            self.measure(node.selection_set, root, depth=1, lists=0, introspection=None, fragments=frozenset())
        except TooLarge as e:
            self.report_error(GraphQLError(str(e), node, extensions={'code': QUERY_TOO_LARGE}))

    def measure(self, selection_set: SelectionSetNode, parent, depth: int, lists: int, introspection: int | None,
                fragments: frozenset):
        """
        :param lists: the lists nested above, outside introspection
        :param introspection: the lists nested above within introspection, or None outside it
        :param fragments: the fragments spread above, so that a cycle, which NoFragmentCyclesRule reports, ends here
        """
        for selection in selection_set.selections:
            if isinstance(selection, FieldNode):
                self.fields += 1
                if self.fields > MAX_QUERY_FIELDS:
                    raise TooLarge(f"The query asks for more than {MAX_QUERY_FIELDS} fields, the most the API answers")
                if depth > MAX_QUERY_DEPTH:
                    raise TooLarge(f"The query nests fields more than {MAX_QUERY_DEPTH} deep, the most the API answers")
                name = selection.name.value
                definition = META_FIELDS.get(name) or getattr(parent, 'fields', {}).get(name)
                if definition is None:
                    continue  # FieldsOnCorrectTypeRule reports it
                listed = int(isinstance(get_nullable_type(definition.type), GraphQLList))
                inner, nested = introspection, lists
                if inner is None and name in ('__schema', '__type'):
                    inner = 0
                if inner is None:
                    nested += listed
                    if nested > MAX_QUERY_LISTS:
                        raise TooLarge(f"The query nests more than {MAX_QUERY_LISTS} lists, the most the API answers")
                else:
                    inner += listed
                    if inner > INTROSPECTION_LISTS:
                        raise TooLarge(
                            f"The query's introspection nests more than {INTROSPECTION_LISTS} lists, "
                            f"as the standard introspection query does"
                        )
                if selection.selection_set:
                    self.measure(
                        selection.selection_set, get_named_type(definition.type), depth + 1, nested, inner, fragments
                    )
            else:
                inner_fragments = fragments
                if isinstance(selection, FragmentSpreadNode):
                    name = selection.name.value
                    fragment = self.context.get_fragment(name)
                    if fragment is None or name in fragments:
                        continue  # KnownFragmentNamesRule and NoFragmentCyclesRule report these
                    inner_fragments = fragments | {name}
                else:
                    fragment = selection
                condition = fragment.type_condition
                target = self.context.schema.get_type(condition.name.value) if condition else parent
                if target is not None:
                    self.measure(fragment.selection_set, target, depth, lists, introspection, inner_fragments)
