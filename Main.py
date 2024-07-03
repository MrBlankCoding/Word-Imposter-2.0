import asyncio
import os
import random
import traceback
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
        self.description_phase_started = False
        self.user_descriptions = {}
        self.num_rounds = 3
        self.votes = {}
        self.message_id = None
        self.missed_rounds = {}
        self.votes_received = 0

class VotingDropdown(discord.ui.Select):
    def __init__(self, options, game):
        super().__init__(placeholder="Vote for the Imposter", options=options, min_values=1, max_values=1)
        self.game = game  # Pass the game object to the dropdown

    async def callback(self, interaction: discord.Interaction):
        user_id = int(self.values[0])
        self.game.votes[interaction.user.id] = user_id  # Record the vote
        self.game.votes_received += 1  # Increment the votes received counter
        await interaction.response.send_message(f"You voted for {(await bot.fetch_user(user_id)).name}.", ephemeral=True)

class VotingView(discord.ui.View):
    def __init__(self, options, game):
        super().__init__()
        self.add_item(VotingDropdown(options, game))
        

@bot.event
async def on_ready():
    print("Bot is up and ready!")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(e)

class JoinButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Join Game", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        game = games.get(interaction.channel.id)
        if game and interaction.user.id not in game.joined_users:
            game.joined_users.append(interaction.user.id)
            
            # Update the embed message
            channel = interaction.channel
            message = await channel.fetch_message(game.message_id)
            embed = message.embeds[0]
            embed.description = f"Click the button below to join the game!\n\n**Players joined: {len(game.joined_users)}**"
            await message.edit(embed=embed)
            
            await interaction.response.send_message(f"{interaction.user.name} has joined the game!", ephemeral=True)
        else:
            await interaction.response.send_message("You have already joined the game.", ephemeral=True)

class JoinGameView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(JoinButton())

@bot.tree.command(
    name="play",
    description="Start a new game or join an existing game in the channel."
)
async def play(interaction: discord.Interaction):
    if interaction.guild is None or interaction.channel is None:
        await interaction.response.send_message(
            "This command can only be used in a server channel.",
            ephemeral=True)
        return

    if interaction.channel.id not in games:
        games[interaction.channel.id] = GameState()

    game = games[interaction.channel.id]

    if not game.game_started:
        embed = discord.Embed(
            title="Game Start",
            description="Click the button below to join the game!\n\n**Players joined: 0**",
            color=0x00ff00
        )
        view = JoinGameView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)
        message = await interaction.original_response()  # Fetch the message from the interaction response
        game.message_id = message.id
    else:
        await interaction.response.send_message(
            "A game is already in progress in this channel.",
            ephemeral=True
        )

@bot.tree.command(
    name="start",
    description="Start the current game"
)
async def start(interaction: discord.Interaction):
    if interaction.channel.id not in games:
        await interaction.response.send_message(
            "No game has been set up in this channel. Use /play to start a new game.",
            ephemeral=True
        )
        return

    game = games[interaction.channel.id]

    if not game.game_started:
        if len(game.joined_users) >= 3:
            random_word = get_unused_word('nouns.txt', 'used_words.txt')
            game.imposter = random.choice(game.joined_users)
            for user_id in game.joined_users:
                try:
                    user = await bot.fetch_user(user_id)
                    if user_id == game.imposter:
                        await user.send("You are the imposter!")
                    else:
                        await user.send(f"The word is: {random_word}")
                except discord.DiscordException as e:
                    print(f"Failed to send a message to user {user_id}: {e}")
            game.game_started = True
            await interaction.response.send_message("The game has started!")
        else:
            await interaction.response.send_message(
                "Not enough users have joined yet.",
                ephemeral=True
            )
    else:
        await interaction.response.send_message(
            "The game has already started.",
            ephemeral=True
        )

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

        # Initialize missed rounds tracking
        for user_id in game.joined_users:
            game.missed_rounds[user_id] = 0

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
                    game.missed_rounds[user_id] += 1

                    if game.missed_rounds[user_id] > 2:
                        await interaction.followup.send(
                            f"{user.mention} has been removed from the game for missing too many rounds."
                        )
                        game.joined_users.remove(user_id)

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
    channel = interaction.channel

    if channel.id not in games:
        await interaction.response.send_message("No game has been set up in this channel. Use /play to start a new game.", ephemeral=True)
        return

    game = games[channel.id]
    game.votes_received = 0
    game.votes = {}  # Initialize the votes dictionary

    try:
        options = []
        for index, user_id in enumerate(game.joined_users):
            user = await bot.fetch_user(user_id)
            options.append(discord.SelectOption(label=f"{index+1}. {user.name}", value=str(user_id)))

        for user_id in game.joined_users:
            try:
                user = await bot.fetch_user(user_id)
                view = VotingView(options, game)  # Pass the game object to the view
                await user.send("Vote for the Imposter using the dropdown below:", view=view)
                print(f"Sent voting dropdown to {user.name} (ID: {user_id})")  # Debug print
            except Exception as e:
                print(f"Error sending voting dropdown to user {user_id}: {e}")
                import traceback
                traceback.print_exc()

        await interaction.response.send_message("Voting has started. Use /tally to tally the votes when everyone has voted.")
    except Exception as e:
        print(f"Error during voting process: {e}")
        import traceback
        traceback.print_exc()
@bot.tree.command(name="tally", description="Tally the votes and determine the outcome.")
async def tally(interaction: discord.Interaction):
    channel = interaction.channel

    if channel.id not in games:
        await interaction.response.send_message("No game has been set up in this channel. Use /play to start a new game.", ephemeral=True)
        return

    game = games[channel.id]

    # Check if all players have voted
    if game.votes_received < len(game.joined_users):
        await interaction.response.send_message(
            f"All players are required to vote before tallying ({game.votes_received}/{len(game.joined_users)}).", 
            ephemeral=True)
        return

    try:
        votes = {}
        for user_id, voted_user in game.votes.items():
            votes[voted_user] = votes.get(voted_user, 0) + 1

        await tally_votes(interaction, game, votes)
    except Exception as e:
        print(f"Error during tallying process: {e}")
        import traceback
        traceback.print_exc()

async def ask_replay(interaction: discord.Interaction):
    view = discord.ui.View()

    class ReplayButton(discord.ui.Button):
        def __init__(self, label, style):
            super().__init__(label=label, style=style)

        async def callback(self, interaction: discord.Interaction):
            if self.label == "Yes":
                await interaction.response.send_message("Use /play to start a new game.", ephemeral=True)
            elif self.label == "No":
                await interaction.response.send_message("Thank you for playing!", ephemeral=True)

    view.add_item(ReplayButton(label="Yes", style=discord.ButtonStyle.green))
    view.add_item(ReplayButton(label="No", style=discord.ButtonStyle.red))

    await interaction.followup.send("Would you like to play again?", view=view)
    
async def tally_votes(interaction: discord.Interaction, game, votes):
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

    await ask_replay(interaction)
    


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

    status_message = (
        f"Game Started: {game.game_started}\n"
        f"Description Phase Started: {game.description_phase_started}\n"
        f"Players Joined: {len(game.joined_users)}\n"
    )
    
    for user_id in game.joined_users:
        user = await bot.fetch_user(user_id)
        status_message += f"- {user.name}\n"

    imposter_name = await bot.fetch_user(game.imposter) if game.imposter else 'None'

    if game.missed_rounds:
        missed_rounds = []
        for user_id, rounds in game.missed_rounds.items():
            user = await bot.fetch_user(user_id)
            missed_rounds.append(f"{user.name}: {rounds}")
        missed_rounds_str = ', '.join(missed_rounds)
    else:
        missed_rounds_str = 'None'

    status_message += (
        f"Number of Rounds: {game.num_rounds}\n"
        f"Votes Received: {game.votes_received}\n"
    )

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
