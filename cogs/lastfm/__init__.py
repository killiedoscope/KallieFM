"""One /fm GroupCog composed from command mixins; only this module is loaded."""

from discord import app_commands
from discord.ext import commands

from .account import AccountCommands
from .charts import ChartCommands
from .history import HistoryCommands
from .listening import ListeningCommands
from .milestones import MilestoneCommands
from .shared import AccountHelpers
from .social import SocialCommands


@app_commands.allowed_installs(
    guilds=True,
    users=True,
)
@app_commands.allowed_contexts(
    guilds=True,
    dms=True,
    private_channels=True,
)
class LastFM(
    AccountCommands,
    ListeningCommands,
    ChartCommands,
    SocialCommands,
    MilestoneCommands,
    HistoryCommands,
    AccountHelpers,
    commands.GroupCog,
    group_name="fm",
):
    def __init__(
        self,
        bot: commands.Bot,
    ):
        self.bot = bot


async def setup(
    bot: commands.Bot,
):
    await bot.add_cog(
        LastFM(bot)
    )