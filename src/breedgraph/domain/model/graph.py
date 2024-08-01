from pydantic import BaseModel
from pydantic_core import core_schema
import networkx as nx

from typing_extensions import Annotated


class _DiGraphPydanticAnnotation:
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler) -> core_schema.CoreSchema:
        """
        Return a pydantic_core.CoreSchema that behaves in the following ways:

        * `DiGraph` instances will be parsed as `DiGraph` instances without any changes
        * Nothing else will pass validation
        * Serialization returns the dicts from the graph?
        # todo consider returning 2 arrays: an array of tuples (ID, entity) and edges.
        """
        def validate_graph(graph: nx.DiGraph):
            assert isinstance(graph, nx.DiGraph)
            return graph

        schema = core_schema.json_or_python_schema(
            json_schema = core_schema.no_info_plain_validator_function(validate_graph),
            python_schema = core_schema.no_info_plain_validator_function(validate_graph),
            serialization = core_schema.plain_serializer_function_ser_schema(
                lambda instance: nx.to_dict_of_dicts(instance)
            )
        )
        return schema


PyDiGraph = Annotated[
    nx.DiGraph, _DiGraphPydanticAnnotation
]
