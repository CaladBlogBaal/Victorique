
def search_recommendations():
    query = """
        query ($id: Int, $type: MediaType, $search: String) {
          Media(search: $search, id: $id, type: $type) {
            recommendations {
              edges {
                node {
                  mediaRecommendation {
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
            }
            title {
              romaji
              english
            }
            siteUrl
          }
        }

    """
    return query
