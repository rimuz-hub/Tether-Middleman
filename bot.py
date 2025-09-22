import discord
from discord.ext import commands, tasks
from discord import ui, Interaction, Embed
import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
import asyncio

# -----------------------------
# Keep-alive web server (for Replit)
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
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    raise ValueError("❌ DISCORD_TOKEN not found in .env!")

GUILD_ID = 1346001535292932148  # Your server ID
MIDDLEMAN_ROLE_ID = 1346013158208311377  # Middleman Team role ID

# -----------------------------
# Bot setup
# -----------------------------
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

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
            other_member = interaction.guild.get_member(other_id) or await interaction.guild.fetch_member(other_id)
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
            "other": other_id,
            "giving": self.giving_input.value,
            "receiving": self.receiving_input.value,
            "claimed": False,
            "claimer": None
        }

        embed = Embed(
            title="🎫 New Middleman Request",
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
# Claim button
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

        ticket["claimed"] = True
        ticket["claimer"] = interaction.user.id
        await interaction.channel.edit(name=f"claimed-by-{interaction.user.name}")
        await interaction.channel.send(f"✅ This ticket will be handled by {interaction.user.mention}.")
        await interaction.response.send_message("You have claimed this ticket.", ephemeral=True)

# -----------------------------
# /setup command
# -----------------------------
@bot.tree.command(name="setup", description="Post the Middleman request panel", guild=discord.Object(id=GUILD_ID))
async def setup(interaction: Interaction):
    embed = Embed(
        title="📩 Request a Middleman",
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

# -----------------------------
# /handle command
# -----------------------------
@bot.tree.command(name="handle", description="Ping middleman team and make ticket claimable", guild=discord.Object(id=GUILD_ID))
async def handle(interaction: Interaction):
    channel_id = interaction.channel.id
    ticket = tickets.get(channel_id)
    if not ticket:
        await interaction.response.send_message("❌ This is not a ticket channel.", ephemeral=True)
        return

    # Reset claim
    ticket["claimed"] = False
    ticket["claimer"] = None

    embed = Embed(
        title="⚠️ Ticket needs handling",
        description="Please handle this ticket. The ticket is now claimable again.",
        color=discord.Color.orange()
    )
    await interaction.channel.send(f"<@&{MIDDLEMAN_ROLE_ID}>", embed=embed, view=ClaimView(channel_id))
    await interaction.response.send_message("✅ Middleman team has been pinged, ticket is claimable again.", ephemeral=True)

# -----------------------------
# /delete command
# -----------------------------
@bot.tree.command(name="delete", description="Delete this ticket after 5 seconds", guild=discord.Object(id=GUILD_ID))
async def delete(interaction: Interaction):
    channel_id = interaction.channel.id
    if channel_id not in tickets:
        await interaction.response.send_message("❌ This is not a ticket channel.", ephemeral=True)
        return

    await interaction.response.send_message("⏱ Ticket will be deleted in 5 seconds...")
    await asyncio.sleep(5)
    await interaction.channel.delete()
    tickets.pop(channel_id, None)

# -----------------------------
# /close command
# -----------------------------
@bot.tree.command(name="close", description="Close ticket for traders, visible to middleman", guild=discord.Object(id=GUILD_ID))
async def close(interaction: Interaction):
    channel_id = interaction.channel.id
    ticket = tickets.get(channel_id)
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
# Message triggers
# -----------------------------
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    triggers = {
        ".form": "**Both the users please fill the below form.**\n1. What are you trading?\n2. Do you confirm your trade?\n3. Do you know the Middleman process?",
        ".mminfo": "**How the middle man process works :-**\n\n1. The seller passes the item to the middle man.\n2. Then the buyer pays the seller.\n3. Then the middle man passes the item to the buyer given by the seller.\n4. In return, both traders have to vouch for the middle man.\n\nhttps://i.imgur.com/P2EU3dy.png",
        ".scmsg": "Oh no! Unfortunately, you got scammed!\n\nHowever, there is a way you can profit and make more from this experience.\n\nhttps://cdn.discordapp.com/attachments/1345858190021103657/1375512933177491618/Picsart_25-05-23_22-20-50-784.png\n\nBecome a hitter! What is a hitter? Basically, do the same maneuver that just happened to you to other people. Then, we will split the earnings with you 50/50, or the middleman can choose to give 100%.\n\nLet the middleman know if you're interested in joining."
    }

    content = message.content.lower()
    if content in triggers:
        await message.channel.send(triggers[content])

    await bot.process_commands(message)

# -----------------------------
# On Ready
# -----------------------------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    guild_obj = discord.Object(id=GUILD_ID)
    # Clear old guild commands (prevent duplicates)
    await bot.tree.clear_commands(guild=guild_obj)
    await bot.tree.sync(guild=guild_obj)
    print("✅ Slash commands synced for guild.")

# -----------------------------
# Run bot
# -----------------------------
keep_alive()
bot.run(DISCORD_TOKEN)