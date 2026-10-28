# Front-end changes

The API changes the front end (`breedview`) has yet to make, with what breaks and the work each needs. Field names are
given as in GraphQL (camelCase). A section is removed once breedview implements it; the earlier ones (Persons,
invitations, transfers, record group extents, the renamed areas, contributions, times, bulk control, Person views and
maps) are in this file's history, last in full at `021f830` (`git show 021f830:docs/front-end-changes.md`), the two
after them (removing optional links with null, units as record group levels) at `7549579`, the three after those
(arrivals, inherited germplasm, moving units) at `a5c7625`, germplasm entries from units at `fd0c50d`, legal references given as files at `81961e6`, the Terms of Use at `1ae91b7`, accepting study licences at `de74a78`, the privacy notice from the API at `8f48104`, derived units at `a89ee36`, licences of files at `b6298bc`, derivation stages at `2a8740d`, the ontology's public citations at `5ddb940`, adding children to several units at `4696d21`, removed ontology entries, layout locations and deleting layouts, clearing fields in updates and consent to records of people at `28924f0`, and several accesses to a team in an invitation at `070eb3c`. Where they
describe the API rather than the work, the schema's descriptions, README.md and the design notes in `docs/` have it.

## Where the front end is

breedview (`ffb947b`) implements every API change up to 2026-10-23.

**For the next API change:** add a section for it, with what breaks and the work it needs; then, in breedview,
regenerate the schema files with the API running (`node scripts/fetchGraphqlSchema.js` writes `schema.graphql`,
`possibleTypes.json` and `unionTypes.json`) and run the check script below.

## Checking the front end against the API

```bash
set -a; . instance/breedgraph.env; . instance/private.breedgraph.env; set +a
.venv/bin/python scripts/check_front_end_queries.py ../breedview/src
```

It builds the API's schema and validates every operation in the front end's `.graphql` files, with the fragments each uses, and exits with 1 if any fails.
It does not check variables, so input fields built in JavaScript (as `roleIds` was) need a search.
Rerun it after changing the front end, and after any API change, before releasing either.

## Scale categories on the scale

A scale's categories are no longer ontology entries: they are part of the scale, in order (an ordinal scale's order is
their rank), each a name, unique on the scale ignoring case, and an optional description of what it means on the scale
(README, Scale). `Scale.categories` is now `[ScaleCategory!]!`, with `ScaleCategory { name description }`. Gone: the
`Category` type and its interface `CategoryRelationships`, `CATEGORY` from `OntologyNodeLabel`, `HAS_CATEGORY` from
the relationship labels, `Category` from `OntologyEntryUnion`, `Term.categories`, the `ontologyCreateCategory` and
`ontologyUpdateCategory` mutations with `CategoryInput` and `CategoryUpdate`, and `categoryIds` on `TermInput`,
`TermUpdate`, `ScaleInput` and `ScaleUpdate`. `ScaleInput.categories` and `ScaleUpdate.categories` take
`[ScaleCategoryInput!]` (`{ name description }`): given in an update, they replace the scale's, and left out, they stay.

Values of nominal and ordinal scales are matched to a category's name only, ignoring case, and stored as the scale has
it: no longer to a category's synonyms or abbreviation, nor an id.

New refusals, as errors of the payload:
- a nominal or ordinal scale without categories: "A nominal scale needs categories"; categories on another scale:
  "Categories are only valid for nominal and ordinal scales"; "Category names can't be empty"; "Category names must
  differ on a scale, ignoring case: Yes, yes";
- dropping or renaming a category records hold, through any variable or factor reading the scale, removed ones
  included: "Records cite the categories Low, Mid of Graded Classes, so the scale must keep them". Adding, reordering
  and describing categories stay open;
- changing a locked scale's categories: "Scale ... is locked, so its categories cannot change".

What breaks: 8 operations (`scripts/check_front_end_queries.py`), through the entry fragment's `categories { id
versionId view name }` and `... on Category`, and in `datasets.graphql` and `analysisDatasetFragment.graphql`: Datasets,
AnalysisDatasets, AnalysisDatasetDimensions, ontologyEntries, ontology, programsStudy, ontologyCreateCategory and
ontologyUpdateCategory. Work: select `categories { name description }`; delete the Category entry type, its mutations,
Term's categories and the Category colour; on the scale form, an ordered list of name and description in place of
the category picker, for nominal and ordinal scales, fixed on a locked scale; drop `Scale: ['categories']` from the
lifecycle definition fields (it reads category ids); match values by name only; show a category's description with
its name where values are entered; show the refusals as given.

## Definitions that records cite

Once records cite a variable or factor, what defines it is fixed: `ontologyUpdateVariable` refuses a different trait,
observation method or scale ("Records cite Variable Plant height (cm), so its trait, observation method and scale
can't change: create a new variable instead"), and `ontologyUpdateFactor` a different condition, control method or
scale ("... so its condition, control method and scale can't change: create a new factor instead"). Its name,
description, synonyms, terms and references stay open, and it can still be deprecated, to stop new datasets using it.
While records cite a scale, through any variable or factor reading it, removed ones included, `ontologyUpdateScale`
refuses a different scale type: "Records cite Centimetres, so its scale type can't change: create a new scale instead".

Nothing breaks. Work: show the refusals as given.

## Place search from GeoNames

`locationsSearchPlaces` is answered from the API's own copy of GeoNames' places (docs/maps.md), open to visitors, with
no hourly limit but at most 5 searches in a request. Its `countryCode` (alpha-2) is now `country`, an ISO 3166 alpha-3
code, as locations' codes are; a code of another form is refused: "Not an ISO 3166 alpha-3 code: 'IE'".
`locationsGeocodeCountry(name)` is gone: `locationsCountryPlace(code)` gives a country with the extent of its main
parts (east above 180 across the antimeridian, as tiles.json's), or null until the world's places are fetched.
`Place` gains `description` ("town", "farm", "mountain"), `region` ("Kerry, Munster"), `country` (its name; null for a
country) and `zoom` (when it has no bounds), and `CountryMapStatus` gains `places { state enabled towns error }`:
whether the country's own places are there (`READY`), coming (`PENDING`) or `FAILED`, and whether the world's towns of
1,000 people or more stand in for them meanwhile. New refusals: "That search took too long: please type more of the
name", "Place search is busy, please try again in a moment", "A viewbox is [west, south, east, north]".

What breaks: `searchPlaces.graphql` (`countryCode`) and `geocodeCountry.graphql`. Work: search signed out too; pass
the selected country's alpha-3 code and drop `countryCodes.js`; show each result's kind and region, and zoom to
`zoom` or `bounds`; credit "Places from GeoNames, CC BY 4.0"; fit a country without a tiles.json extent by
`locationsCountryPlace(code)`; say under the map, from `places`, when a country is covered by the world's towns only.
