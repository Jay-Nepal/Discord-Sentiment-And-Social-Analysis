from interactions import (Client, Intents, listen,
                          slash_command, slash_option, OptionType,
                          AutoDefer, File)
from interactions.api.events import Startup
import pandas as pd
import matplotlib.pyplot as plt
import io
import os
import networkx as nx
from dotenv import load_dotenv
load_dotenv()

# Initial definitions
client = Client(intents=Intents.ALL)
auto_defer_without_ephemeral = AutoDefer(enabled=True, ephemeral=False, time_until_defer=2.0)


def make_social_network_graph(graph, all_relation):
    # Adding edges to create a directional social network graph
    graph.clear()
    for index, row in all_relation.iterrows():
        source = row['sender']
        target = row['receiver']
        strength = row['strength']
        graph.add_edge(source, target, strength=strength)

    # Generating a layout for the graph
    pos = nx.spring_layout(graph)

    # Drawing, Saving and Returning the graph
    nx.draw(graph, pos, with_labels=True, node_color='skyblue', edge_color='k', font_size=12)
    buffer = io.BytesIO()
    plt.savefig(buffer, format="PNG")
    buffer.seek(0)
    plt.close()
    return buffer


# Default startup option. Currently set to check servers the bot is present in
@listen(Startup)
async def startup_func():
    print("Joined Guilds:")
    for guild in client.guilds:
        print(guild.name)


@slash_command(name="social_network_graph")
@slash_option(
    name="channel_id",
    description="ID of the channel to analyse",
    opt_type=OptionType.STRING,
    required=True
)
async def fetch_history(ctx, channel_id: str):
    await AutoDefer.defer(auto_defer_without_ephemeral, ctx)
    all_user_pair = []

    try:
        channel = await client.fetch_channel(int(channel_id))
        if channel is not None:
            messages = await channel.history(limit=0).flatten()  # Gets all messages from a channel
            print(len(messages))
            for message in messages:
                mentioned_users = set()
                author = message.author
                message_reply_to = message.get_referenced_message()
                async for user in message.mention_users:
                    mentioned_users.add(user.display_name)
                if message_reply_to:
                    mentioned_users.add(message_reply_to.author.display_name)
                if len(mentioned_users) > 0:  # Only creating a social pair if there is a sender and receiver
                    sender = author.display_name
                    for receiver in mentioned_users:
                        if receiver != sender:
                            user_pair = {'sender': sender, 'receiver': receiver}
                            all_user_pair.append(user_pair)
        else:  # If the channel ID is integer but not found
            await ctx.send(content="Channel not found, please re-check permissions and ID.")
    except ValueError:  # If someone gives non-integer input for channel ID
        await ctx.send(content="Invalid channel ID, did you add a letter accidentally?")

    # Converting user pair to a dataframe with strength for the number of times it repeated
    df_network = pd.DataFrame(all_user_pair)
    grouped = df_network.groupby(df_network.columns.difference(['strength']).tolist())
    df_network['strength'] = grouped.transform('size')
    df_network = df_network.drop_duplicates()
    # Create a new graph object
    G = nx.DiGraph()
    # Get the social graph image as a buffer
    buffer = make_social_network_graph(G, df_network)
    print(df_network)
    await ctx.send(file=File(buffer, file_name="graph.png"))
    buffer.close()
    await ctx.send('Finished', ephemeral=True)

# Command to bulk delete messages for testing
@slash_command(name="delete_all")
@slash_option(
    name="channel_id",
    description="ID of the channel to delete",
    opt_type=OptionType.STRING,
    required=True
)
@slash_option(
    name="delete_count",
    description="Number of messages to delete",
    opt_type=OptionType.INTEGER,
    required=True

)
async def bulk_delete(ctx, channel_id: str, delete_count: int):
    await AutoDefer.defer(auto_defer_without_ephemeral, ctx)
    try:
        channel = await client.fetch_channel(int(channel_id))
        if channel is not None:
            num_deleted = await channel.purge(deletion_limit=delete_count,
                                              search_limit=delete_count + 10,
                                              return_messages=False,
                                              avoid_loading_msg=True)
            await ctx.send(content=f"Deleted a total of {num_deleted} messages")
        else:
            await ctx.send(content="Channel not found, please re-check permissions and ID.")
    except ValueError:
        await ctx.send(content="Invalid channel ID, did you add a letter accidentally?")


bot_token = os.getenv('discord_token')
client.start(bot_token)
