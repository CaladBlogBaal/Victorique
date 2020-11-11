import asyncio
import contextlib
import random

import discord

from cogs.utils.games import QuizPoints


class TriviaCore:
    def __init__(self):
        self.questions = None
        self.reactions = ["🇦", "🇧", "🇨", "🇩", "⏩"]

    async def set_questions(self, ctx, category, difficulty, amount_of_questions):

        if amount_of_questions > 10:
            amount_of_questions = 10

        query = "SELECT question_id from question"

        if not category and not difficulty:
            results = await ctx.db.fetch(query)

        elif category and not difficulty:
            query = "SELECT question_id from question WHERE category_id = $1"
            results = await ctx.db.fetch(query, category)

        elif difficulty and not category:
            query = "SELECT question_id from question WHERE difficulty = $1"
            results = await ctx.db.fetch(query, difficulty)

        else:
            query = "SELECT question_id from question WHERE category_id = $1 and difficulty = $2"
            results = await ctx.db.fetch(query, category, difficulty)

        self.questions = random.sample(results, amount_of_questions)

        for i, question in enumerate(self.questions):
            self.questions[i] = await self.build_question(ctx, question)

    @staticmethod
    def build_answers(answers):
        answers = sorted(answers, key=lambda ans: ans["is_correct"], reverse=True)
        return [ans["content"] for ans in answers]

    async def build_question(self, ctx, question_id):
        question_id = question_id["question_id"]
        data = await ctx.db.fetchrow("""SELECT content, difficulty, type 
                                        from question where question_id = $1""", question_id)

        question, difficulty, question_type = data["content"], data["difficulty"], data["type"]

        answers = await ctx.db.fetch("SELECT content, is_correct from answer where question_id = $1", question_id)
        answers = self.build_answers(answers)

        category = await ctx.db.fetchval("""SELECT name from category where category_id = 
                                            (SELECT category_id from question where question_id = $1)""",
                                         question_id)

        return category, question_type, difficulty, question, answers


class Triva(TriviaCore):
    def __init__(self):
        super().__init__()
        self.score = 0
        self.timeoutcount = 0

    def increment_counter(self):
        self.timeoutcount += 1

    async def embed(self, ctx, question, amt):
        embed = discord.Embed(title=f"Trivia Question! :white_check_mark: {amt} questions left",
                              color=ctx.bot.default_colors())
        embed.set_footer(text=f'Requested by {ctx.message.author.name}', icon_url=ctx.message.author.avatar_url)
        embed.timestamp = ctx.message.created_at
        # reactions and answers are in parallel
        for i, answer in enumerate(question[4]):
            embed.add_field(name=answer, value=self.reactions[i])

        return embed

    async def check_answers(self, ctx, reaction, question, correct_answer, check):
        reactions_copy = self.reactions.copy()

        if len(question[4]) == 2:
            del reactions_copy[2]
            del reactions_copy[2]

        while True:

            if reaction.emoji in reactions_copy:
                index = self.reactions.index(reaction.emoji)

                if reaction.emoji == self.reactions[-1]:
                    result = f"\n\n:information_source: | this question will be skipped, {ctx.author.name}."

                elif question[4][index] == correct_answer:
                    self.score += 10
                    result = f"\n\n> {ctx.author.name} correct answer"

                else:
                    self.score += -2
                    result = f"\n\n> Incorrect answer, the correct answer was `{correct_answer}` {ctx.author.name}"

                return result

            reaction, user = await ctx.bot.wait_for('reaction_add', timeout=10, check=check)

    async def run(self, ctx, difficulty, amount, category):

        async def end():
            with contextlib.suppress(discord.Forbidden):
                await msg.clear_reactions()

        await ctx.acquire()

        msg = await ctx.send("Starting the trivia game....")
        score = QuizPoints(ctx.author.name)

        await self.set_questions(ctx, category, difficulty, amount)

        for reaction in self.reactions:
            await msg.add_reaction(reaction)

        for question in self.questions:
            text = f"**Category:** {question[0]}\n**Type:** {question[1]}\n**Difficulty:** {question[2]}\n" \
                   f"**Question:** {question[3]}"

            correct_answer = question[4][0]
            random.shuffle(question[4])
            embed = await self.embed(ctx, question, amount)
            await msg.edit(embed=embed, content=text)

            def check(reaction, user):
                return user == ctx.author and reaction.emoji in self.reactions and reaction.message.id == msg.id

            try:

                reaction, user = await ctx.bot.wait_for('reaction_add', timeout=10, check=check)

                with contextlib.suppress(discord.Forbidden):
                    await msg.remove_reaction(reaction, user)

            except asyncio.TimeoutError:
                self.increment_counter()
                if self.timeoutcount >= 5:
                    await end()

                s = "\n\n:information_source: | {}, you took too long to give a response this question will be skipped."
                text += s.format(ctx.author.name)
                await msg.edit(embed=embed, content=text)
                amount -= 1
                await asyncio.sleep(3)
                continue

            else:
                result = await self.check_answers(ctx, reaction, question, correct_answer, check)
                text += result
                await msg.edit(embed=embed, content=text)
                await asyncio.sleep(3)
                amount -= 1

        score.score = self.score
        await ctx.release()
        await msg.edit(content=f"quiz finished :white_check_mark: {score.score}")
        await end()
