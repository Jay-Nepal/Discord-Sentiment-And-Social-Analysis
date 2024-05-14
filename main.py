from interactions import (Client, Intents, listen,
                          slash_command, slash_option, OptionType,
                          AutoDefer, File, Activity, ActivityType,
                          StringSelectMenu, StringSelectOption,
                          TimestampStyles)
from interactions.api.events import Startup, Component
import pandas as pd
import matplotlib.pyplot as plt
import io
import os
import networkx as nx
from dotenv import load_dotenv
import re

load_dotenv()

# Initial definitions
client = Client(intents=Intents.ALL)
auto_defer_without_ephemeral = AutoDefer(enabled=True, ephemeral=False, time_until_defer=2.0)
message_history = pd.DataFrame()


def clean_text(text):
    # Remove everything between angle brackets (<>) in a string
    return re.sub(r'<[^>]*>', '', text)


@listen(Startup)
async def startup_func():
    await client.change_presence(activity=Activity.create(name='everyone here',
                                                          type=ActivityType(2),
                                                          state='Everyone is happy :D'
                                                          ))
    print("Joined Guilds:")
    for guild in client.guilds:
        print(guild.name)


# Initial configuration command to start data collection on chosen channels
@slash_command(name="config_and_collect", description="Initial configurations for the bot and start preparing "
                                                      "analytics ready dataset")
@slash_option(
    name="export",
    description="enter 1 if you wish to export, 0 to not",
    opt_type=OptionType.INTEGER,
    required=True
)
async def configure_and_collect(ctx, export: int):
    channel_list = []
    all_messages = []
    all_user_pair = []

    await AutoDefer.defer(auto_defer_without_ephemeral, ctx)

    for channel in ctx.guild.channels:
        if channel.type == 0 and client.user.id in channel.bots:
            channel_list.append(StringSelectOption(label=f"#{channel.name}", value=channel.id))

    components = StringSelectMenu(channel_list,
                                  placeholder="Which channels should I work on?",
                                  min_values=1,
                                  max_values=len(channel_list)
                                  )
    message = await ctx.send('Which channels should I work on?', components=components)
    channel_list.clear()

    try:
        used_component: Component = await client.wait_for_component(components=components, timeout=30)
    except TimeoutError:
        await ctx.send('You have timed out, please try running the command again.')
        components.disabled = True
        await message.edit(components=components)
    else:
        reply_message = "Beginning reading the chat data on: "
        for chosen_channel in used_component.ctx.values:
            channel = await client.fetch_channel(int(chosen_channel))
            channel_list.append(channel)
            reply_message = reply_message + f"#{channel.name} | "
        components.disabled = True
        components.placeholder = reply_message
        await message.edit(components=components)
        await used_component.ctx.send(reply_message)

    if len(channel_list) > 0:
        for channel in channel_list:
            texts = await channel.history(limit=0).flatten()  # Gets all texts from a channel
            for text in texts:
                cleaned_text = clean_text(text.content)
                if 'https' not in cleaned_text and len(cleaned_text) > 0:
                    message_detail = {
                        'author': text.author.display_name,
                        'time-sent': text.timestamp.format()[3:13],
                        'content': cleaned_text
                    }
                    all_messages.append(message_detail)

                mentioned_users = set()
                author = text.author
                text_reply_to = text.get_referenced_message()
                async for user in text.mention_users:
                    mentioned_users.add(user.display_name)
                if text_reply_to:
                    mentioned_users.add(text_reply_to.author.display_name)
                if len(mentioned_users) > 0:  # Only creating a social pair if there is a sender and receiver
                    sender = author.display_name
                    for receiver in mentioned_users:
                        if receiver != sender:
                            user_pair = {'sender': sender, 'receiver': receiver}
                            all_user_pair.append(user_pair)

        df_network = pd.DataFrame(all_user_pair)
        grouped = df_network.groupby(df_network.columns.difference(['strength']).tolist())
        df_network['strength'] = grouped.transform('size')
        df_network = df_network.drop_duplicates().sort_values(by='strength', ascending=False)
        print(df_network.head(5))
        df_chats = pd.DataFrame(all_messages)
        print(df_chats.head(5))

        if export == 1:
            await ctx.send('Exporting to pair and chats spreadsheets.')
            df_network.to_excel("pair.xlsx")
            df_chats.to_excel("chats.xlsx")
        else:
            await ctx.send('Ignoring export, chat data will be stored on cache for analysis within Discord.')

        await ctx.send(f'There were a total of {len(df_chats)} messages')
        await ctx.send(f'The biggest relationship was from {df_network['sender'].iloc[0]} to '
                       f'{df_network['receiver'].iloc[0]} with {df_network['strength'].iloc[0]} '
                       f'direct pings in between')


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


@slash_command(name="social_network_graph", description="Make a social network graph")
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
