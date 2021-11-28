def search_media():
    query = """
        query ($search: String, $id: Int, $type: MediaType) {
          Page(page: 0, perPage: 10) {
            media(search: $search, id: $id, type: $type) {
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
