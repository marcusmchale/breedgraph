from typing import List, Any
from ariadne import ScalarType, EnumType


class GraphQLResolverRegistry:
    def __init__(self):
        self.query_resolvers: List[Any] = []
        self.mutation_resolvers: List[Any] = []
        self.type_resolvers: List[Any] = []  # ObjectTypes for interfaces and types
        self.scalars: List[ScalarType] = []
        self.enums: List[EnumType] = []
        self._registered_names: set = set()  # Track names to avoid duplicates

    def register_query_resolvers(self, *resolvers):
        """Register query-related resolvers"""
        for resolver in resolvers:
            resolver_name = getattr(resolver, 'name', str(resolver))
            if resolver_name not in self._registered_names:
                self.query_resolvers.append(resolver)
                self._registered_names.add(resolver_name)

    def register_mutation_resolvers(self, *resolvers):
        """Register mutation-related resolvers"""
        for resolver in resolvers:
            resolver_name = getattr(resolver, 'name', str(resolver))
            if resolver_name not in self._registered_names:
                self.mutation_resolvers.append(resolver)
                self._registered_names.add(resolver_name)

    def register_type_resolvers(self, *resolvers):
        """Register ObjectType resolvers for types and interfaces"""
        for resolver in resolvers:
            resolver_name = getattr(resolver, 'name', str(resolver))
            if resolver_name not in self._registered_names:
                self.type_resolvers.append(resolver)
                self._registered_names.add(resolver_name)

    def register_scalars(self, *scalars):
        """Register scalar types"""
        for scalar in scalars:
            scalar_name = getattr(scalar, 'name', str(scalar))
            if scalar_name not in self._registered_names:
                self.scalars.append(scalar)
                self._registered_names.add(scalar_name)

    def register_enums(self, *enums):
        """Register enum types"""
        for enum in enums:
            enum_name = getattr(enum, 'name', str(enum))
            if enum_name not in self._registered_names:
                self.enums.append(enum)
                self._registered_names.add(enum_name)

    def get_all(self) -> List[Any]:
        """Get all registered resolvers"""
        return (
                self.query_resolvers +
                self.mutation_resolvers +
                self.type_resolvers +
                self.scalars +
                self.enums
        )

    def get_queries(self) -> List[Any]:
        """Get only query resolvers"""
        return self.query_resolvers.copy()

    def get_mutations(self) -> List[Any]:
        """Get only mutation resolvers"""
        return self.mutation_resolvers.copy()

    def get_types(self) -> List[Any]:
        """Get only type resolvers"""
        return self.type_resolvers.copy()

    def clear(self):
        """Clear all registered resolvers (useful for testing)"""
        self.query_resolvers.clear()
        self.mutation_resolvers.clear()
        self.type_resolvers.clear()
        self.scalars.clear()
        self.enums.clear()
        self._registered_names.clear()


# Global registry instance
graphql_resolvers = GraphQLResolverRegistry()
