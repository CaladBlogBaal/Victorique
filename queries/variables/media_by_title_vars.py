def get_by_title(media_type, title):
    media_type = media_type.upper()

    if media_type not in ("ANIME", "MANGA"):
        return False

    variables = {"type": media_type, "search": title}

    return variables
