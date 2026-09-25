import discord
from discord import app_commands

from database.db import (
    get_all_lastfm_users, get_artist_crown, get_lastfm_user, get_user_crowns,
    set_artist_crown,
)
from services.lastfm_api import (
    LastFMError, get_artist_playcount, get_top_artists, get_user_info,
)
from .compatibility import ranked_artists, compare_artists, daves_verdict
from .shared import base_embed, finish_embed, medal, number


class SocialCommands:
    @app_commands.command(
        name="compare",
        description="Compare your overall top 50 artists with a member or Last.fm user.",
    )
    @app_commands.describe(
        member="Discord member with a linked Last.fm account",
        username="Last.fm username (they do not need to be in this server)",
    )
    async def compare(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
        username: str | None = None,
    ):
        await interaction.response.defer()

        if member is not None and username is not None:
            await interaction.followup.send(
                "❌ Pick either a Discord member or a Last.fm username, not both.",
                ephemeral=True,
            )
            return

        if member is None and username is None:
            await interaction.followup.send(
                "❌ Give me either a Discord member or a Last.fm username to compare with.",
                ephemeral=True,
            )
            return

        own_username = await self.require_username(interaction, None)
        if own_username is None:
            return

        if member is not None:
            other_username = await get_lastfm_user(member.id)
            if other_username is None:
                await interaction.followup.send(
                    f"❌ {member.mention} hasn't linked a Last.fm account yet. "
                    "You can also compare them directly with their Last.fm username.",
                    ephemeral=True,
                )
                return
        else:
            other_username = username.strip()
            if not other_username:
                await interaction.followup.send(
                    "❌ Give me a valid Last.fm username.",
                    ephemeral=True,
                )
                return

        try:
            left = ranked_artists(
                await get_top_artists(own_username, period="overall", limit=50)
            )
            right = ranked_artists(
                await get_top_artists(other_username, period="overall", limit=50)
            )
            left_user = await get_user_info(own_username)
            right_user = await get_user_info(other_username)
        except LastFMError as error:
            await interaction.followup.send(
                f"❌ Last.fm error: {error}",
                ephemeral=True,
            )
            return

        if not left or not right:
            await interaction.followup.send(
                "❌ Both accounts need artist scrobbles before Dave can compare them.",
                ephemeral=True,
            )
            return

        own_username = left_user.get("name", own_username)
        other_username = right_user.get("name", other_username)

        score, shared = compare_artists(left, right)
        left_total = int(left_user.get("playcount", 0))
        right_total = int(right_user.get("playcount", 0))

        if member is not None:
            comparison_line = f"{interaction.user.mention} × {member.mention}"
            right_display_name = member.display_name
        else:
            comparison_line = f"{interaction.user.mention} × **{other_username}**"
            right_display_name = other_username

        embed = base_embed(
            title="🎸 Musical Compatibility",
            description=f"{comparison_line}\n**{score:.1f}% compatibility**",
        )

        left_top = next(iter(left.values()))
        embed.add_field(
            name=f"{interaction.user.display_name} • {own_username}"[:256],
            value=(
                f"🥇 **{left_top.name[:180]}** — {number(left_top.plays)} plays\n"
                f"{number(left_total)} total scrobbles\n"
                f"{number(sum(a.plays for a in left.values()))} "
                f"plays across these {len(left)} artists"
            ),
            inline=True,
        )

        right_top = next(iter(right.values()))
        embed.add_field(
            name=f"{right_display_name} • {other_username}"[:256],
            value=(
                f"🥇 **{right_top.name[:180]}** — {number(right_top.plays)} plays\n"
                f"{number(right_total)} total scrobbles\n"
                f"{number(sum(a.plays for a in right.values()))} "
                f"plays across these {len(right)} artists"
            ),
            inline=True,
        )

        lines = [
            f"**{left[key].name[:100]}** — #{left[key].rank} / #{right[key].rank}\n"
            f"{number(left[key].plays)} / {number(right[key].plays)} plays"
            for key in shared[:5]
        ]

        embed.add_field(
            name=f"Strongest shared artists ({len(shared)} shared)",
            value="\n".join(lines) or "No shared artists in your overall top 50.",
            inline=False,
        )

        embed.add_field(
            name="Dave's Verdict",
            value=daves_verdict(
                score,
                left,
                right,
                left_total,
                right_total,
            ),
            inline=False,
        )

        finish_embed(
            embed,
            "Overall top 50 • Rank-weighted overlap • Counts shown in user order",
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="whoknows",
        description="See who in the server listens to an artist the most.",
    )
    @app_commands.describe(
        artist="Artist to check",
    )
    async def whoknows(
        self,
        interaction: discord.Interaction,
        artist: str,
    ):
        await interaction.response.defer()

        guild = interaction.guild

        if guild is None:
            await interaction.followup.send(
                "❌ WhoKnows can only be used inside a server.",
                ephemeral=True,
            )
            return

        linked_users = await get_all_lastfm_users()

        results = []
        canonical_artist = artist

        for discord_id, lastfm_username in linked_users:
            member = guild.get_member(
                discord_id
            )

            if member is None:
                continue

            try:
                (
                    artist_name,
                    playcount,
                ) = await get_artist_playcount(
                    artist,
                    lastfm_username,
                )

            except LastFMError:
                continue

            canonical_artist = artist_name

            results.append(
                {
                    "member": member,
                    "username": lastfm_username,
                    "plays": playcount,
                }
            )

        results.sort(
            key=lambda item: item["plays"],
            reverse=True,
        )

        listeners = [
            item
            for item in results
            if item["plays"] > 0
        ]

        if not listeners:
            await interaction.followup.send(
                f"Nobody here has scrobbled **{canonical_artist}** yet."
            )
            return

        winner = listeners[0]

        artist_key = (
            canonical_artist
            .strip()
            .casefold()
        )

        previous_crown = await get_artist_crown(
            guild.id,
            artist_key,
        )

        crown_stolen = (
            previous_crown is not None
            and previous_crown["discord_id"]
            != winner["member"].id
        )

        previous_owner = None

        if crown_stolen:
            previous_owner = guild.get_member(
                previous_crown["discord_id"]
            )

        await set_artist_crown(
            guild_id=guild.id,
            artist_key=artist_key,
            artist_name=canonical_artist,
            discord_id=winner["member"].id,
            playcount=winner["plays"],
        )

        lines = []

        combined_plays = sum(
            item["plays"]
            for item in listeners
        )

        for index, item in enumerate(
            listeners[:10],
            start=1,
        ):
            crown = (
                " 👑"
                if index == 1
                else ""
            )

            lines.append(
                f"{medal(index)} "
                f"**{item['member'].display_name}**{crown}\n"
                f"　{number(item['plays'])} plays"
            )

        embed = base_embed(
            title=f"👑 Who Knows — {canonical_artist}",
            description="\n".join(lines),
        )

        embed.set_thumbnail(
            url=winner["member"].display_avatar.url
        )

        if crown_stolen:
            if previous_owner:
                old_owner = previous_owner.mention
            else:
                old_owner = "the previous owner"

            embed.add_field(
                name="🚨 CROWN STOLEN",
                value=(
                    f"{winner['member'].mention} stole the "
                    f"**{canonical_artist}** crown from "
                    f"{old_owner}!"
                ),
                inline=False,
            )

        else:
            embed.add_field(
                name="👑 Crown holder",
                value=winner["member"].mention,
                inline=True,
            )

            embed.add_field(
                name="Crown score",
                value=f"**{number(winner['plays'])}** plays",
                inline=True,
            )

        finish_embed(
            embed,
            (
                f"{len(listeners)} listeners • "
                f"{number(combined_plays)} combined plays"
            ),
        )

        await interaction.followup.send(
            embed=embed
        )


    @app_commands.command(
        name="crowns",
        description="Show the artist crowns owned by a server member.",
    )
    @app_commands.describe(
        member="Member to check. Defaults to yourself.",
    )
    async def crowns(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ):
        await interaction.response.defer()

        guild = interaction.guild

        if guild is None:
            await interaction.followup.send(
                "❌ Crowns can only be viewed inside a server.",
                ephemeral=True,
            )
            return

        target = member or interaction.user

        crowns = await get_user_crowns(
            guild.id,
            target.id,
        )

        if not crowns:
            await interaction.followup.send(
                f"👑 {target.mention} doesn't own any artist crowns yet."
            )
            return

        lines = []

        for index, (
            artist_name,
            playcount,
        ) in enumerate(
            crowns,
            start=1,
        ):
            lines.append(
                f"**{index}. {artist_name}**\n"
                f"　👑 {number(playcount)} plays"
            )

        embed = base_embed(
            title=f"👑 {target.display_name}'s Crown Cabinet",
            description="\n".join(lines),
        )

        embed.set_author(
            name="ARTIST CROWNS",
            icon_url=target.display_avatar.url,
        )

        embed.set_thumbnail(
            url=target.display_avatar.url
        )

        finish_embed(
            embed,
            (
                f"{len(crowns)} crown"
                f"{'' if len(crowns) == 1 else 's'}"
            ),
        )

        await interaction.followup.send(
            embed=embed
        )


