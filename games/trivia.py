import asyncio
import discord
import random

from cogs.utils.games import QuizPoints

from collections import namedtuple


class TriviaButton(discord.ui.Button["Trivia"]):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def callback(self, interaction):
        assert self.view is not None

        await interaction.response.defer()
        # cancel question timer
        self.view.task.cancel()
        self.view.task = asyncio.create_task(self.view.skip_after())

        for answer in self.view.current_question.answers:

            if answer.emoji == str(self.emoji):
                if answer.record["is_correct"]:
                    content = f"> Correct answer {self.view.ctx.author.input}!"
                    self.view.score += 10
                else:
                    self.view.score += -2
                    content = f"{self.view.content()}\n> Incorrect answer, the correct answer was " \
                              f"`{self.view.get_right_answer()}` {self.view.ctx.author.input}!"

                embed = self.view.embed(self.view.current_question)
                await self.view.message.edit(content=content, embed=embed)

        if not self.view.questions:
            return await self.view.finish_game()

        await self.view.next_question()


class Triva(discord.ui.View):
    def __init__(self, ctx, action_pause=3, timeout=40, timer=10):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.pause = action_pause
        self.score = 0
        self.message = None
        self.current_question = None
        self.questions = []
        self.emojis = ["🇦", "🇧", "🇨", "🇩"]
        self._timer = timer
        self.__timeout_task = None

        for emoji in self.emojis:
            button = TriviaButton(emoji=emoji, style=discord.ButtonStyle.blurple)
            self.add_item(button)

    @property
    def task(self):
        return self.__timeout_task

    @task.setter
    def task(self, value):
        self.__timeout_task = value

    def content(self):
        question = self.current_question
        return f"**Category:** {question.category}\n**Type:** {question.type}\n**Difficulty:** {question.difficulty}\n" \
               f"**Question:** {question.content}"

    def embed(self, question):

        embed = discord.Embed(title=f"Trivia Question! :white_check_mark: {len(self.questions)} questions left",
                              color=self.ctx.bot.default_colors())

        embed.set_footer(text=f"Requested by {self.ctx.message.author.input}",
                         icon_url=self.ctx.message.author.avatar.url)

        embed.timestamp = self.ctx.message.created_at

        for answer in question.answers:
            embed.add_field(name=answer.record["content"], value=answer.emoji)

        return embed

    async def finish_game(self):
        self.stop()

        if not self.task.done():
            self.task.cancel()

        score = QuizPoints(self.ctx.author.input)
        score.score = self.score
        await self.message.edit(content=f"quiz finished :white_check_mark: {score.score}", embed=None, delete_after=5)

    def get_right_answer(self):
        for answer in self.current_question.answers:
            if answer.record["is_correct"]:
                return answer.record["content"]

    async def skip_after(self):
        await asyncio.sleep(self._timer)

        if not self.questions:
            return await self.finish_game()

        await self.message.edit(content="Skipping this question since you've taken too long to answer.")
        await self.next_question()
        # restart the task
        self.task = asyncio.create_task(self.skip_after())

    async def interaction_check(self, interaction):
        return interaction.user.id == self.ctx.author.id

    async def on_timeout(self) -> None:

        if not self.task.done():
            self.task.cancel()

        self.stop()

        await self.message.edit(":information_source: | haven't received an input for awhile stopping the game.",
                                delete_after=10)

    async def build_questions(self, ctx, category, difficulty, amount):

        async with self.ctx.acquire():

            if amount > 10:
                amount = 10

            query = """SELECT content, type, difficulty, question_id, c.name as category FROM question q 
                          INNER JOIN category c on c.category_id = q.category_id
                          WHERE ($1::smallint is NULL or q.category_id = $1::smallint) AND
                          ($2::text is NULL or difficulty = $2::text)"""

            results = await ctx.db.fetch(query, category, difficulty)

            results = random.sample(results, amount)

            for record in results:
                question = namedtuple("question", "content category answers type difficulty")

                answers = []
                records = await ctx.db.fetch("SELECT content, is_correct FROM answer WHERE question_id = $1",
                                             record["question_id"])

                random.shuffle(records)

                for i, r in enumerate(records):
                    answer = namedtuple("answer", "record emoji")
                    answer.record = r
                    answer.emoji = self.emojis[i]
                    answers.append(answer)

                question.type = record["type"]
                question.content = record["content"]
                question.category = record["category"]
                question.difficulty = record["difficulty"]
                question.answers = answers.copy()
                self.questions.append(question)

    async def next_question(self):
        await asyncio.sleep(self.pause)
        self.current_question = self.questions.pop()
        embed = self.embed(self.current_question)
        content = self.content()
        await self.message.edit(content=content, embed=embed)

    async def run(self, difficulty, amount, category):

        await self.build_questions(self.ctx, category, difficulty, amount)
        self.current_question = self.questions.pop()
        embed = self.embed(self.current_question)
        content = self.content()
        self.message = await self.ctx.send(content=content, embed=embed, view=self)
        self.task = asyncio.create_task(self.skip_after())
