## 1.3. Germplasm


### 1.3.1 Extract Varieties

In BreedCAFS, germplasm details were effectively encoded (minimally) in the "varieties" attribute on items.
This could be singular or plural, allowing to encode a mix of varieties for an item.
When variety is null, it is an array stored in varieties. The varieties array stores variety in all cases.

We want to extract only the varieties that are actually referenced, rather than all possible varieties.
We then want to match on name with the existing germplasm that is curated with relationships in breedgraph.
Then create any new germplasm that may be needed.  

So in terms of extraction it is just a matter of pulling the referenced varieties.

```cypher
MATCH (v:Variety)<-[:OF_VARIETY|CONTAINS_VARIETY]-() return distinct v.name order by v.name
```
saved this as varieties.csv

### 1.3.2 Extract varieties per unit
The latest variety definition is stored on the unit itself

```cypher
MATCH (u:Unit) where u.varieties is not null return u.uid, u.varieties
```

However we only need to store the individual variety, as varieties is always composed rather than set.

There is one interesting case of pooling across multiple varieties, not sure why this was done but just to note.
This may be an important consideration. In BreedGraph, a unit can only have one germplasm definition.
Though it can have multiple source units within the sme block. 
We are ok in this instance, but it is worth considering, will we ever want to pool across fields/blocks etc.
This would be poorly supported in breedgraph, you would have to merge the blocks, 
which is only allowed within one location (at least in the ui i believe).

```cypher
MATCH (i:Item) 
OPTIONAL MATCH (i)<-[:IS_IN|FROM*]-(ii:Item)
UNWIND ii.varieties as ii_var
WITH i, collect(distinct ii_var) as source_vars, collect(distinct(ii.uid)) as source_uids
WHERE apoc.coll.sort(i.varieties) <> apoc.coll.sort(source_vars)
return i.uid, i.varieties, source_vars, source_uids
```

For a better visual of the nodes and their relationships.

```cypher
MATCH (i:Item) WHERE i.varieties is not null
OPTIONAL MATCH (i)<-[:IS_IN|FROM*]-(ii:Item)
UNWIND ii.varieties as ii_var
WITH i, collect(distinct ii_var) as source_vars, collect(distinct(ii.uid)) as source_uids
WHERE apoc.coll.sort(i.varieties) <> apoc.coll.sort(source_vars)
WITH distinct i
MATCH (s)<-[:IS_IN|FROM*]-(i)<-[:IS_IN|FROM*]-(ii)

RETURN s, i, ii
```