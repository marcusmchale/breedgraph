MATCH (root: Team) WHERE NOT (root)-[:CONTRIBUTES_TO*]->(:Team)
OPTIONAL MATCH (root)<-[:CONTRIBUTES_TO*]-(child:Team)
WITH root, coalesce(collect(child), []) as children
WITH root + children as teams  //here we enforce the root being first in the teams list
RETURN [ team in teams |
    team {
      .* ,
      parent: [(team)-[:CONTRIBUTES_TO]->(parent:Team) | parent.id][0],
      children: [(team)<-[:CONTRIBUTES_TO]-(child:Team) | child.id],
      readers: coalesce([(team)<-[:READ {authorisation:"AUTHORISED"}]-(reader:User) | reader.id], []) +
           [(team)-[:CONTRIBUTES_TO*]->(:Team)<-[:READ {authorisation:"AUTHORISED", heritable:true}]-(reader:User) | reader.id],
      writers: [(team)<-[:WRITE {authorisation:"AUTHORISED"}] -(writer:User) | writer.id],
      admins: coalesce([(team)<-[:ADMIN {authorisation:"AUTHORISED"}] -(admin:User) | admin.id], []) +
           [(team)-[:CONTRIBUTES_TO*]->(:Team)<-[:ADMIN {authorisation:"AUTHORISED", heritable:true}]-(admin:User) | admin.id],
      read_requests: coalesce([(team)<-[:READ {authorisation:"REQUESTED"}]-(request:User) | request.id], []) +
       [(team)-[:CONTRIBUTES_TO*]->(:Team)<-[:READ {authorisation:"REQUESTED"}]-(request:User) | request.id],
      write_requests: coalesce([(team)<-[:WRITE {authorisation:"REQUESTED"}]-(request:User) | request.id], []) +
           [(team)-[:CONTRIBUTES_TO*]->(:Team)<-[:WRITE {authorisation:"REQUESTED"}]-(request:User) | request.id],
      admin_requests: coalesce([(team)<-[:ADMIN {authorisation:"REQUESTED"}]-(request:User) | request.id], []) +
           [(team)-[:CONTRIBUTES_TO*]->(:Team)<-[:ADMIN {authorisation:"REQUESTED"}]-(request:User) | request.id]
    }
] as teams
