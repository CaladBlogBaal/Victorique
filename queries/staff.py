def search_staff():
    query = """
        query ($id: Int, $search: String, $type: MediaType) {
          Media(search: $search, id: $id, type: $type) {
            id
            idMal
            type
            title {
              romaji
              english
            }
            staff {
              edges {
                node {
                  primaryOccupations
                  siteUrl
                  image {
                    large
                  }
                  name {
                    full
                  }
                }
              }
            }
          }
        }
    """
    return query

