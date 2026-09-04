## 1.4. Units

In BreedCAFS, the unit of study was termed an "Item". 
To encode this in Breedgraph we need to determine for each item:
  - The name - to be copied to breedgraph name
  - The Subject
    - The "subject" was determined firstly by label.
    - When the labels included was field/block/tree that was the subject.
    - When the labels included "sample", the Item had another attribute the "unit" which indicates the subject.
  - Parent/child Item UIDs
  - Varieties (to later map into the created germplasm)
  - If the parent UID is a block (for trees/samples), we map this to a layout, it may have coordinates
    - this raises a question, how do we define a block that does not have coordinates?
    - AS A BLOCK, i.e. the root unit.
    - I think we may need a field unit for all fields, to form thhe root of the block. 
      - This unit "Subject" can be "Field"
    - Then we create "Block" "Subject" entries within the block for all blocks.
    - The coordinates from each unit need to be preserved to assign positions within layouts.
    - We might as well aggregate the stratum data at the same time as this needs to go into layouts.

- We extracted position data while extracting layouts, saved this as unit_positions.csv

- We also need to extract the varieties, do this in extract germplasm stage
- So here we 