import random


class Card:
    SUITS = ["Clubs", "Diamonds", "Hearts", "Spades"]
    RANK = [None, "Ace", "2", "3", "4", "5", "6", "7", "8", "9", "10", "Jack", "Queen", "King"]

    def __init__(self, suit: 0, rank: 2):
        self.suit = suit
        self.rank = self.RANK[rank]
        self.rank_index = rank
        self.running_player_queue = None

    def print_card(self):
        return "\n{} of {} ".format(Card.RANK[self.rank_index], Card.SUITS[self.suit])

    def __it__(self, other):
        if self.suit < other.suit:
            return True

        if self.suit > other.suit:
            return False

        return self.rank < other.rank


class Deck:
    def __init__(self):
        self.cards = []
        self.removed_cards = []
        for suit in range(4):
            for rank in range(1, 14):
                card = Card(suit, rank)
                self.cards.append(card)

    def shuffle(self):
        random.shuffle(self.cards)

    def pop_card(self, i=0):
        self.removed_cards.append(self.cards[i])
        return self.cards.pop(i)

    def add_card(self, card):
        self.cards.append(card)

    def is_empty(self):
        return len(self.cards) == 0

    def add_back_removed_cards(self):
        for card in self.removed_cards:
            self.add_card(card)


class Player:

    def __init__(self):
        self.hand = []

    def add_card_to_hand(self, card):
        self.hand.append(card)

    def remove_card_to_hand(self, i):
        del self.hand[i]

    def display_hand(self, dealer=False):
        if dealer:
            return self.hand[0].print_card() + "\n**Second card is face down**"

        display = ""

        for card in self.hand:
            display += card.print_card()

        return display

    def clear_hand(self):
        self.hand = []


class QuizPoints:
    def __init__(self, name):
        self.name = name
        self.points = 0

    @property
    def score(self):
        result = f"{self.name} scored {str(self.points)} points."
        return result

    @score.setter
    def score(self, value):
        self.points += value


class ShuntingYard:
    def __init__(self, expression):
        self.expression = expression
        self.ops = {"+": (lambda a, b: a + b),
                    "-": (lambda a, b: a - b),
                    "*": (lambda a, b: a * b),
                    "/": (lambda a, b: a / b)}

    @staticmethod
    def is_digit(num):
        try:
            num = int(num)
        except ValueError:
            try:
                num = float(num)
            except ValueError:
                return False

        return num

    @staticmethod
    def peek(stack):
        return stack[-1] if stack else None

    @staticmethod
    def greater_precedence(op1, op2):
        precedences = {"+": 0, "-": 0, "*": 1, "/": 1}
        return precedences[op1] > precedences[op2]

    def calculate(self, operators, values):
        right = values.pop()
        left = values.pop()
        values.append(self.ops[operators.pop()](left, right))

    def evaluate(self):
        # https://en.wikipedia.org/wiki/Shunting-yard_algorithm
        # http://www.martinbroadhurst.com/shunting-yard-algorithm-in-python.html

        values = []
        operators = []
        for token in self.expression:
            if self.is_digit(token):
                values.append(self.is_digit(token))
            elif token == "(":
                operators.append(token)
            elif token == ")":
                top = self.peek(operators)
                while top not in (None, "("):
                    self.calculate(operators, values)
                    top = self.peek(operators)
                operators.pop()

            else:
                top = self.peek(operators)

                while top not in (None, "(", ")") and self.greater_precedence(top, token):
                    self.calculate(operators, values)
                    top = self.peek(operators)
                operators.append(token)

        while self.peek(operators):
            self.calculate(operators, values)

        return values[0]
