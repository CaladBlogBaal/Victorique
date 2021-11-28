
def get_seasonal(year, season, media_type="ANIME", media_format="TV"):

    media_type = media_type.upper()
    media_format = media_format.upper()
    season = season.upper()

    if season not in ("WINTER", "SUMMER", "FALL", "SPRING"):
        return False

    if media_type not in ("ANIME", "MANGA"):
        return False

    if media_format not in ("TV", "TV_SHORT", "MOVIE", "OVA", "ONA", "MUSIC", "MANGA", "NOVEL", "ONE_SHOT"):
        return False

    variables = {"year": year, "season": season, "type": media_type, "format": media_format}

    return variables
