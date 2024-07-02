import asyncio
import os
import traceback
import random
import discord
from discord import Intents
from discord.ext import commands
from t import TOKEN

intents = Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=discord.Intents.all())
games = {}


class GameState:

    def __init__(self):
        self.joined_users = []
        self.game_started = False
        self.imposter = None
        self.bot_emojis = {}
        self.description_phase_started = False
        self.user_descriptions = {}
        self.num_rounds = 3


@bot.event
async def on_ready():
    print("Bot is up and ready!")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(e)


@bot.tree.command(
    name="play",
    description="Start a new game or join an existing game in the channel.")
async def play(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message(
            "This command can only be used in a server channel.",
            ephemeral=True)
        return

    if interaction.channel is None:
        await interaction.response.send_message(
            "This command can only be used in a server channel.",
            ephemeral=True)
        return

    if interaction.channel.id not in games:
        games[interaction.channel.id] = GameState()

    game = games[interaction.channel.id]

    if not game.game_started:
        embed = discord.Embed(title="Game Start",
                              description="React with ✅ if you want to play!",
                              color=0x00ff00)
        await interaction.response.send_message(embed=embed, ephemeral=False)
        message = await interaction.original_response(
        )  # Fetch the message from the interaction response
        game.message_id = message.id
        await message.add_reaction("✅")
    else:
        await interaction.response.send_message("Message me the number 41",
                                                ephemeral=True)


@bot.event
async def on_raw_reaction_add(payload):
    if payload.channel_id not in games:
        return

    game = games[payload.channel_id]

    if not game.game_started:
        if payload.emoji.name == "✅" and payload.message_id == game.message_id and payload.member and not payload.member.bot and payload.user_id not in game.joined_users:
            game.joined_users.append(payload.user_id)
            user = await bot.fetch_user(payload.user_id)
            await user.send("You have joined the queue")
    else:
        member = payload.member
        if member:
            #No idea help me
            print()
        member = payload.member


def get_unused_word(words_file, used_words_file):
    with open(words_file, 'r') as f:
        words = f.read().splitlines()

    if os.path.exists(used_words_file):
        with open(used_words_file, 'r') as f:
            used_words = f.read().splitlines()
    else:
        used_words = []

    unused_words = list(set(words) - set(used_words))

    if not unused_words:
        # If all words have been used, reset the used words file
        with open(used_words_file, 'w') as f:
            f.write("")
        unused_words = words

    random_word = random.choice(unused_words)
    with open(used_words_file, 'a') as f:
        f.write(random_word + '\n')

    return random_word


@bot.tree.command(name="start", description="Start the current game")
async def start(interaction: discord.Interaction):
    if interaction.channel_id not in games:
        await interaction.response.send_message(
            "No game has been set up in this channel. Use /play to start a new game.",
            ephemeral=True)
        return

    game = games[interaction.channel_id]

    if not game.game_started:
        if len(game.joined_users) > 2:
            random_word = get_unused_word('nouns.txt', 'used_words.txt')
            game.imposter = random.choice(game.joined_users)
            for user_id in game.joined_users:
                user = await bot.fetch_user(user_id)
                if user_id == game.imposter:
                    await user.send("You are the imposter!")
                else:
                    await user.send(f"The word is: {random_word}")
            game.game_started = True
            await interaction.response.send_message("The game has started!")
        else:
            await interaction.response.send_message(
                "Not enough users have joined yet.", ephemeral=True)
    else:
        await interaction.response.send_message(
            "The game has already started.", ephemeral=True)


@bot.tree.command(name="describe", description="Users describe their words.")
async def describe(interaction: discord.Interaction):
    if interaction.channel_id not in games:
        await interaction.response.send_message(
            "No game has been set up in this channel. Use /play to start a new game.",
            ephemeral=True)
        return

    game = games[interaction.channel_id]

    if game.game_started and not game.description_phase_started:
        game.description_phase_started = True
        await interaction.response.send_message(
            "Description phase has started. Users, please describe your words one by one."
        )

        # Iterate over rounds
        for round_number in range(game.num_rounds):
            await interaction.followup.send(f"Round {round_number + 1}")

            joined_users = game.joined_users.copy()
            random.shuffle(joined_users)

            # Iterate over users
            for user_id in joined_users:
                user = await bot.fetch_user(user_id)

                # Send prompt to user
                await interaction.followup.send(
                    f"{user.mention}, please describe your word.")

                def check(m):
                    return m.author.id == user_id and m.channel == interaction.channel

                try:
                    description_msg = await bot.wait_for('message',
                                                         check=check,
                                                         timeout=30)
                    if user_id not in game.user_descriptions:
                        game.user_descriptions[user_id] = []
                    game.user_descriptions[user_id].append(
                        description_msg.content)

                except asyncio.TimeoutError:
                    await interaction.followup.send(
                        f"{user.mention}, you took too long to respond. Your description was not recorded."
                        )

        # After all rounds
        await interaction.followup.send(
            "Description phase completed. Commence voting.")

    elif not game.game_started:
        await interaction.response.send_message(
            "The game has not started yet.", ephemeral=True)
    else:
        await interaction.response.send_message(
            "Description phase is already in progress.", ephemeral=True)


@bot.tree.command(name="recall", description="Recall recorded descriptions.")
async def recall(interaction: discord.Interaction):
    if interaction.channel_id not in games:
        await interaction.response.send_message(
            "No game has been set up in this channel. Use /play to start a new game.",
            ephemeral=True)
        return

    game = games[interaction.channel_id]

    if not game.user_descriptions:
        await interaction.response.send_message(
            "No descriptions have been recorded yet.", ephemeral=True)
        return

    embed = discord.Embed(title="User Descriptions",
                          color=discord.Color.blue())
    for user_id, descriptions in game.user_descriptions.items():
        user = await bot.fetch_user(user_id)
        description_list = "\n".join(
            [f"{i+1}. {desc}" for i, desc in enumerate(descriptions)])
        embed.add_field(name=user.name, value=description_list, inline=False)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="start_voting", description="Starts the voting process.")
async def start_voting(interaction: discord.Interaction):
    # Fetching necessary details from the interaction
    channel = interaction.channel

    if channel.id not in games:
        await interaction.response.send_message("No game has been set up in this channel. Use /play to start a new game.", ephemeral=True)
        return

    game = games[channel.id]
    print(game)
    try:
        voting_message, bot_emojis = await initiate_voting(interaction, game)
        game.voting_message_id = voting_message.id
        game.bot_emojis = bot_emojis
        await interaction.response.send_message("Voting has started. Use ?tally to tally the votes when everyone has voted.")
    except Exception as e:
        print(f"Error during voting process: {e}")
        traceback.print_exc()


async def initiate_voting(interaction, game):
    embed = discord.Embed(title="Vote for the Imposter", description="React with the number corresponding to the user you suspect is the imposter.", color=0xff0000)

    for index, user_id in enumerate(game.joined_users, start=1):
        user = await bot.fetch_user(user_id)
        embed.add_field(name=f"{index}. {user.name}", value=user.id, inline=False)

    # !!!!! ERROR???!!
    voting_message = await interaction.channel.send(embed=embed)
    print(voting_message)

    number_emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣']
    bot_emojis = {number_emojis[i]: game.joined_users[i] for i in range(len(game.joined_users))}

    for emoji in bot_emojis:
        await voting_message.add_reaction(emoji)
        await asyncio.sleep(2)

    return voting_message, bot_emojis


@bot.tree.command(name="tally", description="Tally the votes and determine the outcome.")
async def tally(interaction: discord.Interaction):
    channel = interaction.channel

    if channel.id not in games:
        await interaction.response.send_message("No game has been set up in this channel. Use /play to start a new game.", ephemeral=True)
        return
    
    game = games[channel.id]
    try:
        voting_message = await channel.fetch_message(game.voting_message_id)
        await tally_votes(interaction, game, voting_message, game.bot_emojis)
    except Exception as e:
        print(f"Error during tallying process: {e}")
        import traceback
        traceback.print_exc()


async def tally_votes(interaction, game, voting_message, bot_emojis):
    voted_users = set()
    votes = {user_id: 0 for user_id in game.joined_users}

    def check(reaction, user):
        return user.id in game.joined_users and str(reaction.emoji) in bot_emojis and reaction.message.id == voting_message.id

    try:
        while len(voted_users) < len(game.joined_users):
            reaction, user = await bot.wait_for('reaction_add', check=check, timeout=30)
            if user.id in voted_users:
                await user.send("You have already voted. You cannot vote twice.")
                continue

            voted_user_id = bot_emojis[str(reaction.emoji)]
            if voted_user_id == user.id:
                await user.send("You cannot vote for yourself. Please vote again.")
                await voting_message.remove_reaction(reaction.emoji, user)
                continue

            voted_users.add(user.id)
            votes[voted_user_id] += 1

        await interaction.response.send_message("Voting completed.")

    except asyncio.TimeoutError:
        await interaction.response.send_message("Voting time has expired.")
    
    await asyncio.sleep(2)
    majority_vote = max(votes.values(), default=0)
    voted_user_id = [user_id for user_id, count in votes.items() if count == majority_vote]

    if len(voted_user_id) == 1:
        voted_user_id = voted_user_id[0]
        if voted_user_id == game.imposter:
            await interaction.response.send_message(f"Congratulations! You win. The user you suspected ({(await bot.fetch_user(voted_user_id)).name}) was the imposter!")
        else:
            imposter_user = await bot.fetch_user(game.imposter)
            await interaction.response.send_message(f"Sorry, you lose. The imposter was {imposter_user.name}.")
    else:
        imposter_user = await bot.fetch_user(game.imposter)
        await interaction.response.send_message(f"There was a tie in the votes. No majority decision was made. The imposter was {imposter_user.name}.")



async def ask_replay(interaction: discord.Interaction):
    await interaction.response.send_message(
        "Would you like to play again? Type /play to start a new game.")


def reset_game(channel_id):
    if channel_id in games:
        del games[channel_id]


@bot.tree.command(name="rules",
                  description="Display the rules of Word Imposter.")
async def rules(interaction: discord.Interaction):
    rules_text = (
        "Word Imposter is a sneaky word-guessing game where players try to spot the imposter. "
        "One player doesn't know the chosen word, and everyone else takes turns describing it "
        "while the imposter tries to fit in. After three rounds, players vote on who they think "
        "doesn't know the word.")
    await interaction.response.send_message(rules_text)


@bot.tree.command(name="status", description="Show the current game status.")
async def status(interaction: discord.Interaction):
    if interaction.channel_id not in games:
        await interaction.response.send_message(
            "No game has been set up in this channel. Use /play to start a new game.",
            ephemeral=True)
        return

    game = games[interaction.channel_id]

    status_message = f"Game Started: {game.game_started}\n"
    status_message += f"Description Phase Started: {game.description_phase_started}\n"
    status_message += f"Players Joined: {len(game.joined_users)}\n"
    for user_id in game.joined_users:
        user = await bot.fetch_user(user_id)
        status_message += f"- {user.name}\n"

    await interaction.response.send_message(status_message)


@bot.tree.command(name="quit", description="Quit the current game.")
async def quit_game(interaction: discord.Interaction):
    if interaction.channel_id not in games:
        await interaction.response.send_message(
            "No game has been set up in this channel. Use /play to start a new game.",
            ephemeral=True)
        return

    game = games[interaction.channel_id]

    if interaction.user.id in game.joined_users:
        game.joined_users.remove(interaction.user.id)
        await interaction.response.send_message(
            f"{interaction.user.name} has left the game.")
    else:
        await interaction.response.send_message("You are not in the game.",
                                                ephemeral=True)


@bot.tree.command(name="resets", description="Force quit the current game.")
async def force_quit_game(interaction: discord.Interaction):
    if interaction.channel_id not in games:
        await interaction.response.send_message(
            "No game has been set up in this channel.", ephemeral=True)
        return

    game = games[interaction.channel_id]

    if game.game_started:
        reset_game(interaction.channel_id)
        await interaction.response.send_message("The game has been force quit."
                                                )
    else:
        await interaction.response.send_message(
            "No game is currently in progress.")


@bot.tree.command(name="request",
                  description="Request to add a word to the noun list.")
async def request_word(interaction: discord.Interaction, word: str):
    word = word.strip()  # Strip any extra whitespace
    try:
        # Read the existing words from the file
        with open('nouns.txt', 'r') as file:
            existing_words = file.read().splitlines()

        # Check if the word is already in the list
        if word in existing_words:
            await interaction.response.send_message(
                f"The word '{word}' is already in the noun list.",
                ephemeral=True)
        else:
            # If not, add the word to the file
            with open('nouns.txt', 'a') as file:
                file.write(word + '\n')
            await interaction.response.send_message(
                f"The word '{word}' has been added to the noun list.")
    except FileNotFoundError:
        # If the file does not exist, create it and add the word
        with open('nouns.txt', 'w') as file:
            file.write(word + '\n')
        await interaction.response.send_message(
            f"The word '{word}' has been added to the noun list.")
    except Exception as e:
        await interaction.response.send_message(
            f"An error occurred while adding the word: {e}", ephemeral=True)


def main():
    bot.run(TOKEN)


if __name__ == '__main__':
    main()
