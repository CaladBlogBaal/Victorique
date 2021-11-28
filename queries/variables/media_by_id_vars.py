def get_by_id(media_type, media_id: str):
    media_type = media_type.upper()

    if media_type not in ("ANIME", "MANGA") or not media_id.isdecimal():
        return False

    variables = {"type": media_type, "id": media_id}

    return variables
