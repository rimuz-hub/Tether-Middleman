import discord
from discord.ext import commands
from discord import ui, Interaction, Embed
import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
import asyncio
import json

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

MIDDLEMAN_ROLE_ID = 1346013158208311377  # Middleman Team role ID
GUILD_ID = 1346001535292932148  # Your server ID

# -----------------------------
# Bot setup
# -----------------------------
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="?", intents=intents)

tickets = {}  # channel_id -> ticket info

# -----------------------------
# Persistent Views
# -----------------------------
class RequestView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Request a Middleman", style=discord.ButtonStyle.success, custom_id="request_mm")
    async def request(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_modal(TicketModal())

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

class FillFormView(ui.View):
    def __init__(self, channel_id):
        super().__init__(timeout=None)
        self.channel_id = channel_id

    @ui.button(label="📝 Fill Form", style=discord.ButtonStyle.primary, custom_id="fill_form")
    async def fill_form(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_modal(TradeFormModal(self.channel_id))

    @ui.button(label="ℹ️ MM Info", style=discord.ButtonStyle.secondary, custom_id="mm_info")
    async def mm_info(self, interaction: Interaction, button: ui.Button):
        embed = Embed(
            title="ℹ️ Middleman Info",
            description="**Process:**\n1. Seller gives item to Middleman\n2. Buyer pays Seller\n3. Middleman delivers item to Buyer",
            color=discord.Color.blurple()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class BuyerSellerView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="👤 Buyer", style=discord.ButtonStyle.success, custom_id="buyer_btn")
    async def buyer(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_message("Buyer confirmed ✅", ephemeral=False)

    @ui.button(label="💰 Seller", style=discord.ButtonStyle.danger, custom_id="seller_btn")
    async def seller(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_message("Seller confirmed ✅", ephemeral=False)

import discord
from discord import ui, Interaction, Embed
import json
import os

# -----------------------------
# Tickets storage
# -----------------------------
tickets = {}  # channel_id -> ticket info
MIDDLEMAN_ROLE_ID = 1346013158208311377  # Replace with your Middleman role ID

# -----------------------------
# Panel message persistence
# -----------------------------
PANEL_FILE = "panel.json"

def save_panel(message_id):
    with open(PANEL_FILE, "w") as f:
        json.dump({"message_id": message_id}, f)

def load_panel():
    if os.path.exists(PANEL_FILE):
        with open(PANEL_FILE, "r") as f:
            data = json.load(f)
            return data.get("message_id")
    return None

# -----------------------------
# Ticket Modal
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
            title="🎮 New Middleman Request",
            description=(
                f"**Creator:** {interaction.user.mention}\n"
                f"**Other Trader:** <@{other_id}>\n\n"
                f"**Giving:** {self.giving_input.value}\n"
                f"**Receiving:** {self.receiving_input.value}\n\n"
                f"⏳ A middleman will claim this ticket soon."
            ),
            color=discord.Color.green()
        )

        await channel.send(f"<@&{MIDDLEMAN_ROLE_ID}>", embed=embed, view=ClaimView(channel.id))
        await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)

# -----------------------------
# Request Panel View
# -----------------------------
class RequestView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Persistent view

    @ui.button(label="Request a Middleman", style=discord.ButtonStyle.success, custom_id="request_mm")
    async def request(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_modal(TicketModal())

# -----------------------------
# Claim Ticket View (for tickets)
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
# Sending panel command
# -----------------------------
async def send_panel(channel):
    embed = Embed(
        title="🎫 Middleman Panel",
        description="Click the button below to request a Middleman for your trade.",
        color=discord.Color.blurple()
    )
    view = RequestView()
    msg = await channel.send(embed=embed, view=view)
    save_panel(msg.id)


# -----------------------------
# Trade Form Modal
# -----------------------------
class TradeFormModal(ui.Modal, title="Trader Confirmation Form"):
    def __init__(self, channel_id):
        super().__init__()
        self.channel_id = channel_id
        self.q1 = ui.TextInput(label="What are you trading?", required=True)
        self.q2 = ui.TextInput(label="Do you confirm your trade?", required=True)
        self.q3 = ui.TextInput(label="Do you know the Middleman process?", required=True)
        self.add_item(self.q1)
        self.add_item(self.q2)
        self.add_item(self.q3)

    async def on_submit(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        if self.channel_id not in tickets:
            await interaction.response.send_message("❌ This ticket is invalid.", ephemeral=True)
            return

        ticket = tickets[self.channel_id]
        if "forms" not in ticket:
            ticket["forms"] = {}

        ticket["forms"][user_id] = {
            "trading": self.q1.value,
            "confirm": self.q2.value,
            "process": self.q3.value
        }

        await interaction.response.send_message("✅ Your answers were submitted!", ephemeral=True)

        if len(ticket["forms"]) >= 2:
            creator_ans = ticket["forms"].get(str(ticket["creator"]), {})
            other_ans = ticket["forms"].get(str(ticket["other"]), {})

            embed = Embed(
                title="📋 Trade Confirmation Summary",
                description="Both traders have submitted their forms.",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Creator Answers",
                value=f"Trading: {creator_ans.get('trading','-')}\nConfirm: {creator_ans.get('confirm','-')}\nKnows Process: {creator_ans.get('process','-')}",
                inline=False
            )
            embed.add_field(
                name="Other Trader Answers",
                value=f"Trading: {other_ans.get('trading','-')}\nConfirm: {other_ans.get('confirm','-')}\nKnows Process: {other_ans.get('process','-')}",
                inline=False
            )

            channel = interaction.guild.get_channel(self.channel_id)
            await channel.send(embed=embed, view=BuyerSellerView())

# -----------------------------
# Send form embed in ticket
# -----------------------------
async def send_form_in_ticket(channel, creator_id, other_id):
    embed = Embed(
        title="📝 Trader Form Required",
        description="Please fill this form while a Middleman claims the ticket.\n\nClick **Fill Form** below to start.",
        color=discord.Color.orange()
    )
    await channel.send(embed=embed, view=FillFormView(channel.id))

@bot.command(name="panel")
@commands.has_permissions(administrator=True)  # Optional: only admins can send it
async def panel_command(ctx):
    await send_panel(ctx.channel)
    await ctx.send("✅ Panel sent!", delete_after=5)

# -----------------------------
# Commands: ?delete and ?handle
# -----------------------------
@bot.command(name="delete")
async def delete_ticket(ctx):
    if ctx.channel.id in tickets:
        msg = await ctx.send("⏳ Ticket will be deleted in 5 seconds...")
        await asyncio.sleep(5)
        await ctx.channel.delete()
        tickets.pop(ctx.channel.id, None)
    else:
        await ctx.send("❌ This is not a ticket channel.")

@bot.command(name="handle")
async def handle_ticket(ctx):
    ticket = tickets.get(ctx.channel.id)
    if not ticket or not ticket["claimed"]:
        await ctx.send("❌ This ticket is not claimed yet.")
        return

    ticket["claimed"] = False
    mm_role = ctx.guild.get_role(MIDDLEMAN_ROLE_ID)
    embed = Embed(
        title="🟣 Ticket needs handling",
        description=f"Please handle this ticket: {ctx.channel.mention}",
        color=discord.Color.purple()
    )
    await ctx.channel.send(f"<@&{MIDDLEMAN_ROLE_ID}>", embed=embed, view=ClaimView(ctx.channel.id))
    await ctx.send("✅ Ticket is now reclaimable by another middleman.")

TRIGGERS_FILE = "triggers.json"

if os.path.exists(TRIGGERS_FILE):
    with open(TRIGGERS_FILE, "r") as f:
        data = json.load(f)
        triggers = data.get("triggers", {})
        enabled_triggers = set(data.get("enabled_triggers", []))
else:
    triggers = {
        ".form": {
            "text": (
                "**📋 Fill the form!**\n\n"
                "🔹 What are you trading?\n"
                "🔹 Do you confirm your trade?\n"
                "🔹 Do you know the Middleman process?"
            ),
            "color": 0x00FF00,
            "image": "https://i.imgur.com/yourimage1.png"
        },

        ".mminfo": {
            "text": (
                "**ℹ️ Middleman Info!**\n\n"
                "✅ How the middleman process works:\n"
                "1. The seller passes the item to the middleman.\n"
                "2. The buyer pays the seller.\n"
                "3. The middleman gives the item to the buyer.\n\n"
                "📌 In return, both traders have to vouch for the middleman."
            ),
            "color": 0x800080,
            "image": "https://i.imgur.com/yourimage2.png"
        },

        ".scmsg": {
            "text": (
                "🚨 **Scam Warning!**\n\n"
                "If someone asks you to trade without a middleman, it’s a scam."
            ),
            "color": 0xFF0000,
            "image": "https://i.imgur.com/yourimage3.png"
        },
    }

# -----------------------------
# Triggers handler (on_message)
# -----------------------------
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Check if message content is in triggers
    trigger = triggers.get(message.content)
    if trigger:
        embed = Embed(
            description=trigger["text"],
            color=trigger["color"]
        )
        if trigger.get("image"):
            embed.set_image(url=trigger["image"])
        await message.channel.send(embed=embed)

    # Make sure normal commands still work
    await bot.process_commands(message)
    trigger = triggers.get(message.content)
    
if trigger:
    embed = Embed(
        title=trigger.get("title", ""),
        description=trigger.get("text", ""),
        color=trigger["color"]
    )
    if trigger.get("image"):
        embed.set_image(url=trigger["image"])
    await message.channel.send(embed=embed)



# -----------------------------
# ?scmsg command
# -----------------------------
class ConfirmBanView(ui.View):
    def __init__(self, *, timeout=30):
        super().__init__(timeout=timeout)

    @ui.button(label="Confirm Leave (Ban me)", style=discord.ButtonStyle.danger, custom_id="confirm_leave")
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        guild = interaction.guild
        member = interaction.user
        me = guild.me or guild.get_member(interaction.client.user.id)
        if not me.guild_permissions.ban_members:
            await interaction.response.send_message("❌ I don't have permission to ban members.", ephemeral=True)
            return
        if member.guild_permissions.administrator or member.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ You can't ban staff members.", ephemeral=True)
            return
        try:
            await member.ban(reason="Pressed Leave via ?scmsg")
            await interaction.response.send_message("⚠️ You have been banned from the server.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Could not ban: {e}", ephemeral=True)

    @ui.button(label="Cancel", style=discord.ButtonStyle.secondary, custom_id="cancel_leave")
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("✅ Leave cancelled.", ephemeral=True)
        self.stop()

class ScmsgJoinLeaveView(ui.View):
    def __init__(self, *, timeout=None):
        super().__init__(timeout=timeout)

    @ui.button(label="Join", style=discord.ButtonStyle.success, custom_id="scmsg_join")
    async def join(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(f"👋 Hi {interaction.user.mention}, great choice, https://discord.gg/TesnPTbtc8!", ephemeral=True)

    @ui.button(label="Leave", style=discord.ButtonStyle.danger, custom_id="scmsg_leave")
    async def leave(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(
            "⚠️ Are you sure you want to leave (this will ban you)? Confirm below.",
            ephemeral=True,
            view=ConfirmBanView()
        )

@bot.command(name="scmsg")
async def scmsg_command(ctx: commands.Context):
    embed = Embed(
        title="🚨 Action Message",
        description="""Oh no! Unfortunately, you got scammed!

However, there is a way you can profit and make more from this experience.

Become a hitter! What is a hitter? Basically, do the same thing that just happened to you 
and scam other people. Then, Middleman will split the earnings with you 50/50, or the middleman can choose to give 100%.

**Do not make any fuss out of ticket it will result in ban**

Choose an action below:
- **Join** — join us and start building business (RECOMMENDED).
- **Leave** — confirm to ban yourself from the server (NOT RECOMMENDED).
Press the buttons to proceed. Leave requires confirmation.
Please note that you need to fake vouch the mm that mmd you before joining us""",
        color=0xFF0000
    )
    embed.set_image(url="https://cdn.discordapp.com/attachments/1400475520310837381/1420374603808903178/blue_re_pill.png")

    view = ScmsgJoinLeaveView(timeout=None)
    await ctx.send(embed=embed, view=view)


# -----------------------------
# Persistent tickets saving/loading
# -----------------------------
TICKETS_FILE = "tickets.json"

def save_tickets():
    with open(TICKETS_FILE, "w") as f:
        json.dump({str(k): v for k, v in tickets.items()}, f, indent=4)

def load_tickets():
    global tickets
    if os.path.exists(TICKETS_FILE):
        with open(TICKETS_FILE, "r") as f:
            data = json.load(f)
            tickets = {int(k): v for k, v in data.items()}
    else:
        tickets = {}

load_tickets()

# -----------------------------
# On ready
# -----------------------------
@bot.event
async def on_ready():
    bot.add_view(RequestView())
    for ticket_id in tickets.keys():
        bot.add_view(ClaimView(ticket_id))
    print(f"✅ Logged in as {bot.user}")

keep_alive()
bot.run(DISCORD_TOKEN)
