import discord
from discord.ext import commands, tasks
from discord import ui, Embed
import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
import asyncio

# -----------------------------
# Keep-alive web server (for Replit/Railway)
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

# -----------------------------
# Configuration
# -----------------------------
GUILD_ID = 1346001535292932148
MIDDLEMAN_ROLE_ID = 1346013158208311377  # Middleman Team role ID

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
        self.trader_id_input = ui.TextInput(
            label="Other Trader Discord ID", placeholder="Enter Discord ID", required=True
        )
        self.giving_input = ui.TextInput(label="What are you giving?", required=True)
        self.receiving_input = ui.TextInput(label="What are you receiving?", required=True)
        self.add_item(self.trader_id_input)
        self.add_item(self.giving_input)
        self.add_item(self.receiving_input)

    async def on_submit(self, interaction: discord.Interaction):
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
            f"ticket-{interaction.user.name}", category=category,
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
            "claimed": False
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
# Claim button
# -----------------------------
class ClaimView(ui.View):
    def __init__(self, channel_id):
        super().__init__(timeout=None)
        self.channel_id = channel_id

    @ui.button(label="Claim Ticket", style=discord.ButtonStyle.success)
    async def claim(self, interaction: discord.Interaction, button: ui.Button):
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
        await interaction.channel.edit(name=f"claimed-by-{interaction.user.name}")
        await interaction.channel.send(f"✅ This ticket will be handled by {interaction.user.mention}.")
        await interaction.response.send_message("You have claimed this ticket.", ephemeral=True)

# -----------------------------
# ?setup command
# -----------------------------
@bot.command(name="setup")
async def setup(ctx):
    embed = Embed(
        title="📄 Request a Middleman",
        description="Click the green button below to request a middleman for your trade.",
        color=discord.Color.green()
    )
    view = ui.View()
    button = ui.Button(label="Request a Middleman", style=discord.ButtonStyle.success)

    async def callback(interaction: discord.Interaction):
        await interaction.response.send_modal(TicketModal())

    button.callback = callback
    view.add_item(button)
    await ctx.send(embed=embed, view=view)

# -----------------------------
# ?delete command
# -----------------------------
@bot.command(name="delete")
async def delete_ticket(ctx):
    if ctx.channel.id not in tickets:
        await ctx.send("❌ This is not a ticket channel.")
        return
    await ctx.send("⏳ Ticket will be deleted in 5 seconds...")
    await asyncio.sleep(5)
    await ctx.channel.delete()
    tickets.pop(ctx.channel.id, None)

# -----------------------------
# ?handle command
# -----------------------------
@bot.command(name="handle")
async def handle_ticket(ctx):
    ticket = tickets.get(ctx.channel.id)
    if not ticket:
        await ctx.send("❌ This is not a ticket channel.")
        return

    role = ctx.guild.get_role(MIDDLEMAN_ROLE_ID)
    if role not in ctx.author.roles:
        await ctx.send("❌ Only Middleman Team can handle tickets.")
        return

    ticket["claimed"] = False  # reset claimability
    embed = Embed(
        title="⚠️ Ticket Needs Handling",
        description="Please claim this ticket again.",
        color=discord.Color.orange()
    )
    await ctx.channel.send(f"<@&{MIDDLEMAN_ROLE_ID}>", embed=embed, view=ClaimView(ctx.channel.id))
    await ctx.send("✅ Ticket is now reclaimable by another middleman.")

# -----------------------------
# ?close command
# -----------------------------
@bot.command(name="close")
async def close_ticket(ctx):
    if ctx.channel.id not in tickets:
        await ctx.send("❌ This is not a ticket channel.")
        return
    ticket = tickets[ctx.channel.id]
    guild = ctx.guild
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
    await ctx.channel.edit(overwrites=overwrites)
    await ctx.send("🔒 Ticket closed for traders, still visible to middlemen.")

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

# -----------------------------
# Run bot
# -----------------------------
keep_alive()
bot.run(DISCORD_TOKEN)