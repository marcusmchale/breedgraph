MATCH (partner:Partner)<-[:AFFILIATED {confirmed: True}]-(user)-[: SUBMITTED]->(: Submissions)
-[: SUBMITTED]->(: Records)
-[: SUBMITTED]->(: UserFieldInput)
-[submitted: SUBMITTED]->(record: Record)
-[:RECORD_FOR]->(item_input:ItemInput)
-[:FOR_INPUT*..2]->(input:Input)
-[:OF_TYPE]->(record_type: RecordType),
(item_input)-[:FOR_ITEM]->(item:Item)

WITH item, 	collect(
    {
        record_type:record_type.name_lower,
        input: input.name,
        Partner: partner.name,
        `Submitted by`: user.name,
        `Submitted at`: submitted.time,
        Replicate: record.replicate,
        Time: record.time,
        Start: record.start,
        End: record.end,
        `Recorded by`: record.person,
        Value: COALESCE(
            record.value,
            [i in range(0, size(record.x_values) - 1 ) | [record.x_values[i], record.y_values[i]]]
        )
    }
) as Records

MATCH source_path = (item)-[:FROM|IS_IN*]->(farm: Farm)-[:IS_IN]->(region: Region)-[:IS_IN]->(country: Country)
WITH
    item,
    farm.name as Farm,
    region.name as Region,
    country.name as Country,
    apoc.coll.toSet(
        apoc.coll.flatten(collect([n in nodes(source_path)[1..] WHERE "Sample" in labels(n) | n.id]))
    ) as `Source samples`,
    apoc.coll.toSet(
        apoc.coll.flatten(collect([n in nodes(source_path)[1..] WHERE "Tree" in labels(n) | n.id]))
    ) as `Source trees`,
    apoc.coll.toSet(
        apoc.coll.flatten(collect([n in nodes(source_path)[1..] WHERE "Block" in labels(n) | n.id]))
    ) as `Block ID`,
    apoc.coll.toSet(
        apoc.coll.flatten(collect([n in nodes(source_path)[1..] WHERE "Block" in labels(n) | n.name]))
    ) as Block,
    apoc.coll.flatten(collect([n in nodes(source_path)[1..] WHERE "Field" in labels(n) | n]))[0] as field,
    Records
 WITH
    item,
    `Source samples`, `Source trees`, `Block ID`, Block,
    coalesce(field, item) as field,
    Farm, Region, Country, Records

 UNWIND Records as record
 RETURN
    record["record_type"] as record_type,
    record["input"] as `Input variable`,
    record["Partner"] as Partner,
    record["Submitted by"] as `Submitted by`,
    record["Submitted at"] as `Submitted at`,
    record["Replicate"] as Replicate,
    record["Time"] as Time,
    [record["Start"], record["End"]] as Period,
    record["Recorded by"] as `Recorded by`,
    record["Value"] as Value,
    item.uid as UID,
    item.name as Name,
    `Source samples`, `Source trees`, `Block ID`, Block,
    field.uid as `Field UID`,
    field.name as Field,
    Farm, Region, Country,
    item.id as ID

ORDER BY field.uid, labels(item)[1], item.id, record["input"], record["Replicate"]
