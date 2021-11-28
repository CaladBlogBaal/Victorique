
def search_schedule():
    query = """
        query ($page: Int) {
          Page(page: $page, perPage: 50) {
            pageInfo {
              hasNextPage
            }
            media(status: RELEASING, type: ANIME, format: TV) {
              nextAiringEpisode {
                airingAt
              }
              title {
                romaji
                english
              }
              siteUrl
              episodes 
            }
          }
        }
    
    """

    return query
