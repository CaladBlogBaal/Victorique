
def search_seasonal():
    query = """
        query ($year: Int, $season: MediaSeason, $type: MediaType, $format: MediaFormat) {
          Page(page: 1, perPage: 50) {
            pageInfo {
              hasNextPage
            }
            media(seasonYear: $year, season: $season, type: $type, format: $format) {
              id
              idMal
              type
              title {
                romaji
                english
              }
              siteUrl
              type
              episodes
              chapters
              description(asHtml: true)
              coverImage {
                medium
              }
              startDate {
                day
                month
                year
              }
              endDate {
                day
                month
                year
              }
              averageScore
            }
          }
        }

    """

    return query
