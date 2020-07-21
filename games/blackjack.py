from cogs.utils.games import Player


class BlackJackPlayer(Player):
    NAMED_CARDS = ["Jack", "King", "Queen"]

    def __init__(self):
        self.hand = []
        super().__init__()

    def calculate_winner(self):

        player_total = self.calculate_hand()

        if player_total == 21:
            return True

        if player_total > 21:
            return False

    def calculate_hand(self):

        player_total = 0

        for card in self.hand:

            if card.rank in BlackJackPlayer.NAMED_CARDS:
                player_total += 10

            if card.rank == "Ace":
                player_total += 11

            try:
                player_total += int(card.rank)

            except ValueError:
                pass

        return player_total
