import discord
from discord.ext import commands
from discord import ui, Interaction, Embed
import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

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

MIDDLEMAN_ROLE_ID = 1346013158208311377  # Middleman Team role ID

# -----------------------------
# Bot setup
# -----------------------------
intents = discord.Intents.default()
intents.members = True
intents.message_content = True  # Required for triggers
bot = commands.Bot(command_prefix="?", intents=intents)

tickets = {}  # channel_id -> ticket info

# -----------------------------
# Modal for Ticket Creation
# -----------------------------
class TicketModal(ui.Modal, title="Request Middleman"):
    def __init__(self):
        super().__init__()
        self.trader_id_input = ui.TextInput(
            label="Other Trader Discord ID",
            placeholder="Enter Discord ID",
            required=True
        )
        self.giving_input = ui.TextInput(
            label="What are you giving?",
            required=True
        )
        self.receiving_input = ui.TextInput(
            label="What are you receiving?",
            required=True
        )
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
            "other": other_id,
            "giving": self.giving_input.value,
            "receiving": self.receiving_input.value,
            "claimed": False
        }

        embed = Embed(
            title="🎫 New Middleman Request",
            description=(
                f"**Creator:** {interaction.user.mention}\n"
                f"**Other Trader:** <@{other_id}>\n\n"
                f"**Giving:** {self.giving_input.value}\n"
                f"**Receiving:** {self.receiving_input.value}\n\n"
                f"➡️ A middleman will claim this ticket soon."
            ),
            color=discord.Color.green()
        )

        # Ping Middleman Team
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
        if not ticket or ticket["claimed"]:
            await interaction.response.send_message("❌ This ticket is already claimed.", ephemeral=True)
            return

        ticket["claimed"] = True
        await interaction.channel.edit(name=f"claimed-by-{interaction.user.name}")
        await interaction.channel.send(f"✅ This ticket will be handled by {interaction.user.mention}.")
        await interaction.response.send_message("You have claimed this ticket.", ephemeral=True)

# -----------------------------
# /setup command
# -----------------------------
@bot.tree.command(name="setup", description="Post the Middleman request panel")
async def setup(interaction: Interaction):
    embed = Embed(
        title="💼 Request a Middleman",
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
# ?delete command
# -----------------------------
@bot.command(name="delete")
async def delete_ticket(ctx):
    if ctx.channel.id in tickets:
        await ctx.channel.delete()
        tickets.pop(ctx.channel.id, None)
    else:
        await ctx.send("❌ This is not a ticket channel.")

# -----------------------------
# ?close command
# -----------------------------
@bot.command(name="close")
async def close_ticket(ctx):
    if ctx.channel.id in tickets:
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
    else:
        await ctx.send("❌ This is not a ticket channel.")

# -----------------------------
# Message triggers
# -----------------------------
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.lower() == ".form":
        await message.channel.send(
            "**Both the users please fill the below form.**\n"
            "1. What are you trading?\n"
            "2. Do you confirm your trade?\n"
            "3. Do you know the Middleman process?"
        )
    elif message.content.lower() == ".mminfo":
        await message.channel.send(
            "**How the middle man process works :-**\n\n"
            "1. The seller passes the item to the middle man.\n"
            "2. Then the buyer pays the seller.\n"
            "3. Then the middle man passes the item to the buyer given by the seller.\n"
            "4. In return, both traders have to vouch for the middle man.\n\n"
            "https://i.imgur.com/P2EU3dy.png"
        )
    elif message.content.lower() == ".scmsg":
        await message.channel.send(
            "Oh no! Unfortunately, you got scammed!\n\n"
            "However, there is a way you can profit and make more from this experience.\n\n"
            "https://cdn.discordapp.com/attachments/1345858190021103657/1375512933177491618/Picsart_25-05-23_22-20-50-784.png\n\n"
            "Become a hitter! What is a hitter? Basically, do the same maneuver that just happened to you to other people. Then, we will split the earnings with you 50/50, or the middleman can choose to give 100%.\n\n"
            "Let the middleman know if you're interested in joining."
        )

    await bot.process_commands(message)

# -----------------------------
# On Ready
# -----------------------------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        await bot.tree.sync()
        print("✅ Slash commands synced.")
    except Exception as e:
        print("Sync error:", e)

# -----------------------------
# Run bot
# -----------------------------
keep_alive()  # Keep the Replit server alive
bot.run(DISCORD_TOKEN)