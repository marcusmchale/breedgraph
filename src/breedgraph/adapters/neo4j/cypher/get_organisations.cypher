MATCH (root: Team) WHERE NOT (root)-[:CONTRIBUTES_TO*]->(:Team)
OPTIONAL MATCH (root)<-[:CONTRIBUTES_TO*]-(child:Team)
WITH root, coalesce(collect(child), []) as children
WITH root + children as teams
RETURN [ team in teams |
    team {
      .* ,
      parent_id: [(team)-[:CONTRIBUTES_TO]->(parent:Team) | parent.id][0],
      child_ids: [(team)<-[:CONTRIBUTES_TO]->(child:Team) | child.id],
      admin_ids: coalesce(
          [(team)<-[:ADMIN {authorisation:"AUTHORISED"}]-(admin:User) | admin.id]
          , []
        ) + [(team)-[:CONTRIBUTES_TO*]->(:Team)<-[:ADMIN {authorisation:"AUTHORISED", heritable: True}]-(admin:User) | admin.id]
    }
] as teams