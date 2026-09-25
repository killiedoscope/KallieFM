"""Persistent artist goals, with fresh progress fetched when requested."""
import discord
from discord import app_commands

from database.db import (
    get_lastfm_user, get_artist_milestones, set_artist_milestone, remove_artist_milestone,
)
from services.lastfm_api import LastFMError, get_artist_playcount
from .shared import base_embed, finish_embed, number


def progress_text(plays: int, goal: int) -> str:
    return (f"**{number(plays)} / {number(goal)} plays**\n"
            f"{plays / goal * 100:.1f}% • {number(max(0, goal - plays))} remaining"
            + ("\n✅ Goal reached!" if plays >= goal else ""))


class MilestoneCommands:
    milestone = app_commands.Group(name="milestone", description="Manage your artist play-count goals.")

    @milestone.command(name="set", description="Set or update an artist play-count goal.")
    @app_commands.describe(artist="Artist to track", goal="Target lifetime artist plays")
    async def milestone_set(
        self, interaction: discord.Interaction,
        artist: app_commands.Range[str, 1, 200], goal: app_commands.Range[int, 1, 2147483647],
    ):
        await interaction.response.defer(ephemeral=True)
        username = await self.require_username(interaction, None)
        if username is None:
            return
        if not artist.strip():
            await interaction.followup.send("❌ Enter an artist name.", ephemeral=True)
            return
        try:
            canonical, plays = await get_artist_playcount(artist.strip(), username)
        except LastFMError as error:
            await interaction.followup.send(f"❌ Last.fm error: {error}", ephemeral=True)
            return
        await set_artist_milestone(interaction.user.id, username, canonical, goal)
        embed = base_embed(title="🎯 Artist milestone saved", description=f"**{canonical[:200]}**\n{progress_text(plays, goal)}")
        finish_embed(embed, f"{username} • Artist goal")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @milestone.command(name="list", description="Show your artist goals and current progress.")
    @app_commands.describe(page="Page of goals to show (five per page)")
    async def milestone_list(self, interaction: discord.Interaction, page: app_commands.Range[int, 1] = 1):
        await interaction.response.defer()
        username = await self.require_username(interaction, None)
        if username is None:
            return
        goals = await get_artist_milestones(interaction.user.id, username)
        if not goals:
            await interaction.followup.send("🎯 No artist goals yet. Use `/fm milestone set` to add one.")
            return
        pages = (len(goals) + 4) // 5
        if page > pages:
            await interaction.followup.send(f"❌ Choose a page between 1 and {pages}.", ephemeral=True)
            return
        embed = base_embed(title="🎯 Artist Milestones", description=f"{interaction.user.mention} • **{username}**")
        for artist, goal in goals[(page - 1) * 5:page * 5]:
            try:
                _, plays = await get_artist_playcount(artist, username)
                value = progress_text(plays, goal)
            except LastFMError:
                # A temporary API failure must not erase a goal or imply zero plays.
                value = f"Goal: **{number(goal)} plays**\n⚠️ Progress unavailable. Try again later."
            embed.add_field(name=artist[:256], value=value, inline=False)
        finish_embed(embed, f"Page {page}/{pages} • Lifetime artist plays")
        await interaction.followup.send(embed=embed)

    @milestone.command(name="remove", description="Remove one of your saved artist goals.")
    @app_commands.describe(artist="Saved artist name (choose a suggestion)")
    async def milestone_remove(self, interaction: discord.Interaction, artist: str):
        await interaction.response.defer(ephemeral=True)
        username = await self.require_username(interaction, None)
        if username is None:
            return
        removed = await remove_artist_milestone(interaction.user.id, username, artist)
        message = "✅ Artist milestone removed." if removed else "❌ No matching goal. Use `/fm milestone list` to check the saved artist name."
        await interaction.followup.send(message, ephemeral=True)

    @milestone_remove.autocomplete("artist")
    async def milestone_artist_autocomplete(self, interaction: discord.Interaction, current: str):
        username = await get_lastfm_user(interaction.user.id)
        if username is None:
            return []
        goals = await get_artist_milestones(interaction.user.id, username)
        return [app_commands.Choice(name=name[:100], value=name)
                for name, _ in goals if current.casefold() in name.casefold() and len(name) <= 100][:25]
