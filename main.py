from interactions import (Client, Intents, listen,
                          slash_command, slash_option, OptionType,
                          AutoDefer)
from interactions.api.events import Startup
import os
from dotenv import load_dotenv
load_dotenv()

client = Client(intents=Intents.ALL)
auto_defer_without_ephemeral = AutoDefer(enabled=True, ephemeral=False, time_until_defer=2.0)


@listen(Startup)
async def startup_func():
    print("Joined Guilds:")
    for guild in client.guilds:
        print(guild.name)


@slash_command(name="social_graph")
@slash_option(
    name="channel_id",
    description="ID of the channel to analyse",
    opt_type=OptionType.STRING,
    required=True
)
async def fetch_history(ctx, channel_id: str):
    await AutoDefer.defer(auto_defer_without_ephemeral, ctx)
    try:
        channel = await client.fetch_channel(int(channel_id))
        if channel is not None:
            messages = await channel.history().flatten()
            for message in messages:
                await ctx.send(content=f"{message.author}: {message.content}")
        else:
            await ctx.send(content="Channel not found, please re-check permissions and ID.")
    except ValueError:
        await ctx.send(content="Invalid channel ID, did you add a letter accidentally?")


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
