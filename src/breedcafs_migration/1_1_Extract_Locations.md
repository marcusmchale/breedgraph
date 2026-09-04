
## 1.1. Locations

In BreedCAFS, location definitions are basically encoded in the region hierarchy (country/region/farm/field/block).
Coordinate positions were recorded against "Items", of which Field and Block are also members.
We need to represent the country/region/farm/field hierarchy as locations in BreedGraph.
Blocks are better represented as [layouts](1_2_Extract_Layouts.md).

### 1.1.1 Extract Country/Region/Farm/Field hierarchy.

```cypher
MATCH (country:Country)<-[:IS_IN]-(region:Region)<-[:IS_IN]-(farm:Farm)<-[:IS_IN]-(field:Field)
RETURN field.uid as field_uid,  field.name as field,  farm.name as farm, region.name as region, country.name as country
```

Saved this as field_farm_region_country.csv

### 1.1.2 Extract and Aggregate Coordinates

Extract all the BreedCAFS items with coordinates to aggregate into a smaller set of locations. 

```cypher
MATCH (c:Country)<-[:IS_IN*]-(a)<-[:IS_IN]-(i:Item) where i.location is not null 
with c, collect(i) as items, i.location as location return c.name, size(items), location
```
We have locations to aggregate in Cameroon/Vietnam/French Guiana.

In Nicaragua we have single items per coordinate values,
which we would prefer to register as a layout with coordinates rather than having a location per tree.
```cypher
MATCH (c:Country {name_lower:"nicaragua"})<-[:IS_IN*]-(a)<-[:IS_IN]-(i:Item)
  where i.location is not null return i.uid, i.id, i.location order by i.id
```
However, on close inspection all the latitudes are the same, and longitudes just increment by the last digit.
This is particularly suspicious as all values increment by .0001 from the first coordinate value,
which is consistent with a data entry issue.
Rather than treat these entries as accurate, we should surmise that only one of these values is correct (the first) 
and is representative of the shared location for all the associated values.

To simplify the migration I mutated the values
```cypher
MATCH (c:Country {name_lower:"nicaragua"})<-[:IS_IN*]-(a)<-[:IS_IN]-(i:Item) where i.location is not null
SET i.location = "REDACTED"
```

I further noted an issue with a coordinate being in reverse order in Vietnam (long/lat).
However when I reversed to correct it the coordinates point to a roundabout, not a field.
Further, the corresponding field had other coordinates attached to other units. 
These coordinates are not far away but point to a field, so I replaced the erroneous value with this value.
```cypher
MATCH (i:Item {location:"REDACTED"}) set i.location="REDACTED"
```

To get an overview for inspection
```cypher
MATCH (c:Country)<-[:IS_IN*]-(a)<-[:IS_IN]-(b)<-[:IS_IN]-(i:Item) where i.location is not null 
with c, collect(distinct({name:a.name, label:labels(a)[1]})) as l, collect(i) as items, i.location as location 
return c.name, l, size(items), location
```

We don't have any blocks with unique coordinates, so we can drop those and simplify the result.
```cypher
MATCH (c:Country)<-[:IS_IN*]-(f:Field)<-[:IS_IN]-(b)<-[:IS_IN]-(i:Item) where i.location is not null 
with c, collect(distinct f.name) as fields, collect(i) as items, i.location as location 
return c.name, fields, size(items), location order by c.name, fields
```

There two locations set for a single field in Cameroon. One is in Burkina Faso, the other is in Ivory Coast.
Though this highlights a bigger issue. Although all coordinates may be valid in lat/long, none of them are in Cameroon.
I noted that if we transform the values as follows they all end up in Cameroon,
and point to locations with matching names. So I corrected all values accordingly.
```cypher
MATCH (c:Country {name:"Cameroon"})<-[:IS_IN*]-(f:Field)<-[:IS_IN]-(b)<-[:IS_IN]-(item:Item)
  where item.location is not null
with item, split(item.location, ";") as long_lat
with item, toFloat(long_lat[0]) as long, toFloat(long_lat[1])*-1 as lat
set item.old_location = item.location, item.new_location = toString(lat) + ';' + toString(long)
```
just to verify the transformation then,
```cypher
MATCH (c:Country {name:"Cameroon"})<-[:IS_IN*]-(f:Field)<-[:IS_IN]-(b)<-[:IS_IN]-(item:Item)
  where item.location is not null
SET item.location = item.new_location
```

Now we still have the issue of the two locations for one Field. 
One is noted with a name that corresponds to a related institute at the site,
so we can keep that one and drop the other. We can later consult to resolve this if necessary.
```cyhper
MATCH (i:Item {location:'REDACTED'})
SET i.location = 'REDACTED'
```

So now dump the ID of each field with the corresponding coordinates.

```cypher
MATCH (field:Field)<-[:IS_IN*2]-(item:Item) where item.location is not null
WITH distinct field.uid as field_uid, split(item.location, ';') as lat_long
RETURN field_uid, lat_long[0] as lat, lat_long[1] as long
ORDER BY field_uid
```

Exported this as field_lat_long.csv


### Extract units per location.
So now we have established the structure of the resulting locations, now is a good time to map
from "item" to "location". Although many of these items will be rooted in a block at the location, 
they still have their own position data. In the absence of a layout definition we need to at least know the location. 
Though in fact, this is already determined by the item UID which encodes the field already (the number before the string)
