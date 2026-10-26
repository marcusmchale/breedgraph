from breedgraph.domain.model.controls import ControlledModelLabel
from breedgraph.adapters.neo4j.cypher.query_builders.access import readable as _readable_as

# Germplasm entries as the user may see them (see docs/read-access.md). A crop and the entries connected to it are
# read as one structure, a pedigree, though each entry is written on its own (GermplasmApplicationService). An entry
# the user can read is returned in full, its sources and sinks the nearest entries they can read along paths through
# hidden entries only: a direct relationship keeps its type and description, one through hidden entries is UNKNOWN.
# The unit it came from is a reference to another aggregate, given by id even when hidden (the units view gives the
# placeholder).
# A crop (an entry without sources) is kept even when hidden, as a placeholder holding the readable entries below
# it, and so can be a source; any other hidden entry asked for by id is a bare placeholder, its id and a REDACTED
# name. Lists of entries leave hidden ones out.

GERMPLASM = ControlledModelLabel.GERMPLASM


def _readable(entry: str) -> str:
    return _readable_as(entry, GERMPLASM)


def _is_crop(entry: str) -> str:
    return f"NOT EXISTS {{ MATCH (:Germplasm)-[:SOURCE_FOR]->({entry}) }}"


def _relationships(entry: str, direction: str) -> str:
    """
    A call collecting, as {direction}, the relationships from entry to the nearest entries in that direction that the
    user can read, or crops for sources, along paths through hidden entries only
    """
    if direction == 'sources':
        step, near, far = '<-[:SOURCE_FOR]-', 'source', 'sink'
        end = f"{_readable('other')} OR {_is_crop('other')}"
    else:
        step, near, far = '-[:SOURCE_FOR]->', 'sink', 'source'
        end = _readable('other')
    direct_step = '<-[relationship:SOURCE_FOR]-' if direction == 'sources' else '-[relationship:SOURCE_FOR]->'
    return f"""
        CALL ({entry}) {{
          OPTIONAL MATCH ({entry}){direct_step}(other:Germplasm)
          WHERE {end}
          // one relationship per pair of entries, should the data hold more
          WITH {entry}, other, collect(relationship)[0] AS relationship
          WITH {entry}, collect(CASE WHEN other IS NOT NULL THEN {{
            {near}_id: other.id, {far}_id: {entry}.id,
            source_type: relationship.source_type, description: relationship.description
          }} END) AS direct
          OPTIONAL MATCH SHORTEST 1 ({entry})
            (() {step} (hidden:Germplasm WHERE NOT {_readable('hidden')})){{1,}}
            () {step} (other:Germplasm WHERE {end})
          WITH direct, {entry}, collect(DISTINCT other.id) AS through_hidden
          RETURN direct + [other_id IN through_hidden WHERE NOT other_id IN [d IN direct | d.{near}_id] | {{
            {near}_id: other_id, {far}_id: {entry}.id, source_type: 'UNKNOWN', description: null
          }}] AS {direction}
        }}
    """


def _project(entry: str = 'entry') -> str:
    """The calls that put what _entry needs in scope, reading relationships only where they are shown"""
    return f"""
        WITH {entry}, {_readable(entry)} AS entry_readable, {_is_crop(entry)} AS is_crop
        OPTIONAL CALL ({entry}, entry_readable) {{
          WITH {entry} WHERE entry_readable
          {_relationships(entry, 'sources')}
          RETURN sources
        }}
        OPTIONAL CALL ({entry}, entry_readable, is_crop) {{
          WITH {entry} WHERE entry_readable OR is_crop
          {_relationships(entry, 'sinks')}
          RETURN sinks
        }}
        WITH {entry}, entry_readable, is_crop, coalesce(sources, []) AS sources, coalesce(sinks, []) AS sinks
    """


def _entry(entry: str = 'entry') -> str:
    """entry as the user sees it, given entry_readable, is_crop, sources and sinks in scope"""
    return f"""CASE
          WHEN entry_readable THEN {entry} {{
            .*,
            control_methods: [({entry})-[:USES_CONTROL_METHOD]->(method:ControlMethod) | method.id],
            references: [(reference:Reference)-[:REFERENCE_FOR]->({entry}) | reference.id],
            unit: [({entry})-[:FROM_UNIT]->(unit:Unit) | unit.id][0],
            sources: sources,
            sinks: sinks
          }}
          WHEN is_crop THEN {entry} {{ .id, name: 'REDACTED', sources: [], sinks: sinks }}
          ELSE {entry} {{ .id, name: 'REDACTED', sources: [], sinks: [] }}
        END"""


def read_entries():
    """The entries with ids $entry_ids, a placeholder for those the user cannot read"""
    return f"""
        MATCH (entry:Germplasm)
        WHERE entry.id IN $entry_ids
        {_project()}
        RETURN {_entry()} AS entry
        ORDER BY entry.id
    """


def read_all_entries():
    """Every entry the user can read"""
    return f"""
        MATCH (entry:Germplasm)
        WHERE {_readable('entry')}
        {_project()}
        RETURN {_entry()} AS entry
        ORDER BY entry.id
    """


def read_entries_named():
    """
    The entries the user can read named one of $names_lower (casefolded, as names are stored), or with a synonym in
    $synonyms_lower (lower case): names are unique among germplasm, synonyms need not be
    """
    return f"""
        MATCH (entry:Germplasm)
        WHERE (
            entry.name_lower IN $names_lower
            OR any(synonym IN coalesce(entry.synonyms, []) WHERE toLower(synonym) IN $synonyms_lower)
        ) AND {_readable('entry')}
        {_project()}
        RETURN {_entry()} AS entry
        ORDER BY entry.id
    """


def read_crops():
    """The crops the user can read, and placeholders for those they cannot that hold entries they can"""
    return f"""
        MATCH (entry:Germplasm)
        WHERE {_is_crop('entry')}
        {_project()}
        WITH entry, entry_readable, is_crop, sources, sinks WHERE entry_readable OR size(sinks) > 0
        RETURN {_entry()} AS entry
        ORDER BY entry.id
    """


def read_descendant_ids():
    """
    The ids of the entries below $entry_id that the user can read, found through hidden entries as sinks are, for
    grouping units by germplasm. No row when the entry is hidden and not a crop, whose placeholder holds the readable
    entries below it: what lies below another hidden entry is not shown.
    """
    return f"""
        MATCH (selected:Germplasm {{id: $entry_id}})
        WHERE {_readable('selected')} OR {_is_crop('selected')}
        OPTIONAL MATCH (selected)-[:SOURCE_FOR*1..]->(descendant:Germplasm)
        WHERE {_readable('descendant')}
        // grouped by the entry, so a hidden one gives no row rather than an empty list
        RETURN selected.id AS entry_id, collect(DISTINCT descendant.id) AS descendant_ids
    """
