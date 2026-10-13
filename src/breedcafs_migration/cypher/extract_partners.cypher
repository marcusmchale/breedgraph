MATCH (partner:Partner)
RETURN partner.name AS name, partner.fullname AS fullname
ORDER BY partner.name
