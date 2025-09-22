import discord
from discord.ext import commands
from discord import ui, Interaction, Embed
import os
from flask import Flask
from threading import Thread
import asyncio

# -----------------------------
# Keep-alive server (Railway)
# -----------------------------
app = Flask("")

@app.route("/")
def home():
    return "Bot is alive!"

def run():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# -----------------------------
# Load token
# -----------------------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    raise ValueError("❌ DISCORD_TOKEN not found!")

MIDDLEMAN_ROLE_ID = 1346013158208311377
GUILD_ID = 1346001535292932148  # your server ID

# -----------------------------
# Bot setup
# -----------------------------
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="?", intents=intents)

tickets = {}  # channel_id -> ticket info

# -----------------------------
# Ticket Modal
# -----------------------------
class TicketModal(ui.Modal, title="Request Middleman"):
    def __init__(self):
        super().__init__()
        self.trader_id_input = ui.TextInput(label="Other Trader Discord ID", placeholder="Enter Discord ID", required=True)
        self.giving_input = ui.TextInput(label="What are you giving?", required=True)
        self.receiving_input = ui.TextInput(label="What are you receiving?", required=True)
        self.add_item(self.trader_id_input)
        self.add_item(self.giving_input)
        self.add_item(self.receiving_input)

    async def on_submit(self, interaction: Interaction):
        try:
            other_id = int(self.trader_id_input.value.strip())
            other_member = interaction.guild.get_member(other_id)
            if not other_member:
                other_member = await interaction.guild.fetch_member(other_id)
        except:
            await interaction.response.send_message("❌ Invalid Discord ID.", ephemeral=True)
            return

        category = discord.utils.get(interaction.guild.categories, name="Tickets")
        if not category:
            category = await interaction.guild.create_category("Tickets")

        channel = await interaction.guild.create_text_channel(
            f"ticket-{interaction.user.name}",
            category=category,
            overwrites={
                interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                other_member: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                interaction.guild.get_role(MIDDLEMAN_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True),
            },
        )

        tickets[channel.id] = {
            "creator": interaction.user.id,
            "creator_name": interaction.user.name,
            "other": other_id,
            "giving": self.giving_input.value,
            "receiving": self.receiving_input.value,
            "claimed": False,
            "claimer": None
        }

        embed = Embed(
            title="🎮 New Middleman Request",
            description=(
                f"**Creator:** {interaction.user.mention}\n"
                f"**Other Trader:** <@{other_id}>\n\n"
                f"**Giving:** {self.giving_input.value}\n"
                f"**Receiving:** {self.receiving_input.value}\n\n"
                f"⚠️ A middleman will claim this ticket soon."
            ),
            color=discord.Color.green()
        )

        await channel.send(f"<@&{MIDDLEMAN_ROLE_ID}>", embed=embed, view=ClaimView(channel.id))
        await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)

# -----------------------------
# Claim Button
# -----------------------------
class ClaimView(ui.View):
    def __init__(self, channel_id):
        super().__init__(timeout=None)
        self.channel_id = channel_id

    @ui.button(label="Claim Ticket", style=discord.ButtonStyle.success)
    async def claim(self, interaction: Interaction, button: ui.Button):
        role = interaction.guild.get_role(MIDDLEMAN_ROLE_ID)
        if role not in interaction.user.roles:
            await interaction.response.send_message("❌ Only Middleman Team can claim tickets.", ephemeral=True)
            return

        ticket = tickets.get(self.channel_id)
        if not ticket:
            await interaction.response.send_message("❌ Ticket not found.", ephemeral=True)
            return

        if ticket["claimed"]:
            await interaction.response.send_message("❌ This ticket is already claimed.", ephemeral=True)
            return

        ticket["claimed"] = True
        ticket["claimer"] = interaction.user.id
        try:
            await interaction.channel.edit(name=f"claimed-by-{interaction.user.name}")
        except:
            pass
        await interaction.channel.send(f"✅ This ticket will be handled by {interaction.user.mention}.")
        await interaction.response.send_message("You have claimed this ticket.", ephemeral=True)

# -----------------------------
# Slash commands
# -----------------------------
@bot.tree.command(name="setup", description="Post the Middleman request panel", guild=discord.Object(id=GUILD_ID))
async def setup(interaction: Interaction):
    embed = Embed(
        title="📋 Request a Middleman",
        description="Click the green button below to request a middleman for your trade.",
        color=discord.Color.green()
    )
    view = ui.View()
    button = ui.Button(label="Request a Middleman", style=discord.ButtonStyle.success)

    async def callback(inter2: Interaction):
        await inter2.response.send_modal(TicketModal())

    button.callback = callback
    view.add_item(button)
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="delete", description="Delete this ticket after 5 seconds", guild=discord.Object(id=GUILD_ID))
async def delete_ticket(interaction: Interaction):
    ticket = tickets.get(interaction.channel.id)
    if not ticket:
        await interaction.response.send_message("❌ This is not a ticket channel.", ephemeral=True)
        return

    await interaction.response.send_message("🗑 Ticket will be deleted in 5 seconds...", ephemeral=True)
    await asyncio.sleep(5)
    try:
        await interaction.channel.delete()
        tickets.pop(interaction.channel.id, None)
    except Exception as e:
        print("Failed to delete channel:", e)

@bot.tree.command(name="handle", description="Release claim and make ticket claimable again", guild=discord.Object(id=GUILD_ID))
async def handle_ticket(interaction: Interaction):
    ticket = tickets.get(interaction.channel.id)
    if not ticket:
        await interaction.response.send_message("❌ This is not a ticket channel.", ephemeral=True)
        return

    if ticket.get("claimer") != interaction.user.id:
        await interaction.response.send_message("❌ Only the middleman who claimed this ticket can release it.", ephemeral=True)
        return

    ticket["claimed"] = False
    ticket["claimer"] = None

    try:
        await interaction.channel.edit(name=f"ticket-{ticket['creator_name']}")
    except:
        pass

    mm_role = interaction.guild.get_role(MIDDLEMAN_ROLE_ID)
    claim_embed = Embed(
        title="🎮 Ticket Released",
        description=f"{mm_role.mention} Please handle this ticket!",
        color=discord.Color.yellow()
    )
    await interaction.channel.send(embed=claim_embed, view=ClaimView(interaction.channel.id))
    await interaction.response.send_message("✅ Ticket released. Middleman Team can claim it again.", ephemeral=True)

@bot.tree.command(name="close", description="Close this ticket for traders", guild=discord.Object(id=GUILD_ID))
async def close_ticket(interaction: Interaction):
    ticket = tickets.get(interaction.channel.id)
    if not ticket:
        await interaction.response.send_message("❌ This is not a ticket channel.", ephemeral=True)
        return

    guild = interaction.guild
    creator = guild.get_member(ticket["creator"])
    other = guild.get_member(ticket["other"])
    overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
    if creator:
        overwrites[creator] = discord.PermissionOverwrite(view_channel=True, send_messages=False)
    if other:
        overwrites[other] = discord.PermissionOverwrite(view_channel=True, send_messages=False)
    mm_role = guild.get_role(MIDDLEMAN_ROLE_ID)
    if mm_role:
        overwrites[mm_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
    await interaction.channel.edit(overwrites=overwrites)
    await interaction.response.send_message("🔒 Ticket closed for traders, still visible to middlemen.", ephemeral=True)

# -----------------------------
# On ready: sync and remove duplicates
# -----------------------------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    guild_obj = discord.Object(id=GUILD_ID)
    # Clear previous guild commands once
    await bot.tree.clear_commands(guild=guild_obj)
    await bot.tree.sync(guild=guild_obj)
    print("✅ Guild-specific commands synced. Duplicates cleared.")

# -----------------------------
# Run bot
# -----------------------------
keep_alive()
bot.run(DISCORD_TOKEN)