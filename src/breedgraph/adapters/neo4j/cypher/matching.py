import re


def exact_text_regex(text: str) -> str:
    """
    A regular expression parameter for Cypher's =~ that matches the whole of text, ignoring case.
    Neo4j uses Java's regular expressions, where (?i) folds case for ASCII letters only, so (?u) is needed
    for names such as "José" to match "JOSÉ". Text is escaped, so it is matched literally.
    Matching with =~ does not use indexes: keep it to small sets or lookups by an indexed property first.
    """
    return f"(?iu)^{re.escape(text)}$"
