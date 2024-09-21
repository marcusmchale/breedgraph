MATCH (:Scale {id:$source})-[has_category: HAS_CATEGORY]->(:ScaleCategory {id:$sink})
SET has_category.rank = $rank