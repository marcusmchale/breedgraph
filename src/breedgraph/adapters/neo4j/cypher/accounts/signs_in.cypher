OPTIONAL MATCH (user:User {id: $user_id})
RETURN user IS NOT NULL AND (user.sign_ins_ended_at IS NULL OR user.sign_ins_ended_at <= $signed_at)
