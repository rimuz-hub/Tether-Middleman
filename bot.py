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
# Persistent Views Setup
# -----------------------------
@bot.event
async def on_ready():
    # Re-add persistent views
    bot.add_view(ClaimView(channel_id=None))  # For claim button
    bot.add_view(RequestView())               # For setup button
    print(f"✅ Logged in as {bot.user}")


# -----------------------------
# Persistent Setup View
# -----------------------------
class RequestView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Request a Middleman", style=discord.ButtonStyle.success, custom_id="request_mm")
    async def request(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_modal(TicketModal())


# -----------------------------
# Updated ?setup command
# -----------------------------
@bot.command(name="panel")
async def setup_panel(ctx):
    embed = Embed(
        title="📋 Request a Middleman",
        description="Click the green button below to request a middleman for your trade.",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed, view=RequestView())


# -----------------------------
# ClaimView fix
# -----------------------------
class ClaimView(ui.View):
    def __init__(self, channel_id=None):
        super().__init__(timeout=None)
        self.channel_id = channel_id

    @ui.button(label="Claim Ticket", style=discord.ButtonStyle.success, custom_id="claim_ticket")
    async def claim(self, interaction: Interaction, button: ui.Button):
        # same logic, just works persistently
        ...


TRIGGERS_FILE = "triggers.json"

# -----------------------------
# Load triggers or create default
# -----------------------------
if os.path.exists(TRIGGERS_FILE):
    with open(TRIGGERS_FILE, "r") as f:
        data = json.load(f)
        triggers = data.get("triggers", {})
        enabled_triggers = set(data.get("enabled_triggers", []))
else:
    triggers = {
        ".form": {"text": "Fill the form!", "color": 0x00FF00, "image": None},
        ".mminfo": {"text": "Middleman info!", "color": 0x800080, "image": None},
        ".scmsg": {"text": "Scam message!", "color": 0xFF0000, "image": None},
    }
    enabled_triggers = set(triggers.keys())
    with open(TRIGGERS_FILE, "w") as f:
        json.dump({"triggers": triggers, "enabled_triggers": list(enabled_triggers)}, f, indent=4)

def save_triggers():
    with open(TRIGGERS_FILE, "w") as f:
        json.dump({"triggers": triggers, "enabled_triggers": list(enabled_triggers)}, f, indent=4)

# -----------------------------
# Triggering command (add/remove)
# -----------------------------
@bot.group(name="triggering", invoke_without_command=True)
async def triggering(ctx):
    await ctx.send("❌ Usage: `?triggering add <trigger> <text> [image_url]` or `?triggering remove <trigger>`")

@triggering.command(name="add")
async def triggering_add(ctx, trigger: str, *, rest: str):
    trigger = trigger.lower()
    if trigger in triggers:
        return await ctx.send(f"⚠️ Trigger `{trigger}` already exists.")

    parts = rest.split()
    image_url = None
    if parts[-1].startswith("http://") or parts[-1].startswith("https://"):
        image_url = parts[-1]
        text = " ".join(parts[:-1])
    else:
        text = rest

    triggers[trigger] = {"text": text, "color": 0x0000FF, "image": image_url}
    enabled_triggers.add(trigger)
    save_triggers()
    await ctx.send(f"✅ Trigger `{trigger}` added and enabled.")

@triggering.command(name="remove")
async def triggering_remove(ctx, trigger: str):
    trigger = trigger.lower()
    if trigger not in triggers:
        return await ctx.send(f"⚠️ Trigger `{trigger}` does not exist.")
    triggers.pop(trigger)
    enabled_triggers.discard(trigger)
    save_triggers()
    await ctx.send(f"✅ Trigger `{trigger}` removed.")

# -----------------------------
# Toggle command
# -----------------------------
@bot.command()
async def toggle(ctx, trigger: str):
    trigger = trigger.lower()
    if trigger not in triggers:
        return await ctx.send(f"⚠️ Unknown trigger `{trigger}`")
    if trigger in enabled_triggers:
        enabled_triggers.remove(trigger)
        save_triggers()
        await ctx.send(f"❌ Disabled trigger `{trigger}`")
    else:
        enabled_triggers.add(trigger)
        save_triggers()
        await ctx.send(f"✅ Enabled trigger `{trigger}`")

# -----------------------------
# List triggers
# -----------------------------
@bot.command(name="triggers")
async def triggers_status(ctx):
    lines = []
    for t in triggers:
        status = "✅ Enabled" if t in enabled_triggers else "❌ Disabled"
        lines.append(f"{t}: {status}")
    await ctx.send("\n".join(lines))

# -----------------------------
# On message
# -----------------------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.lower()
    if content in triggers and content in enabled_triggers:
        info = triggers[content]
        embed = Embed(description=info["text"], color=info["color"])
        if info.get("image"):
            embed.set_image(url=info["image"])
        await message.channel.send(embed=embed)

    await bot.process_commands(message)

# --- Add this after your persistent triggers setup ---

class ScmsgJoinLeaveView(discord.ui.View):
    def __init__(self, *, timeout=None):
        super().__init__(timeout=timeout)

    @discord.ui.button(label="Join", style=discord.ButtonStyle.success, custom_id="scmsg_join")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"👋 Hi {interaction.user.mention}, perfect descsion, welcome! https://discord.gg/TesnPTbtc8", ephemeral=True)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.danger, custom_id="scmsg_leave")
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.user.ban(reason="Pressed the Leave button")
            await interaction.response.send_message(f"⚠️ {interaction.user.mention} has been banned.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to ban this user.", ephemeral=True)

# --- Update your on_message handler to handle .scmsg ---
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.lower()

    # Handle persistent triggers
    if content in triggers and content in enabled_triggers:
        info = triggers[content]
        # Special case for .scmsg
        if content == ".scmsg":
            embed = discord.Embed(
                title="🚨 Get Scammed!",
                description=(
                 "Oh no! Unfortunately, you got scammed!"
                 "However, there is a way you can profit and make more from this experience."
                 "Become a hitter! What is a hitter. Basically, do the same thing that just happened to you and scam other people. Then, Middleman  will split the earnings with you 50/50, or the middleman can choose to give 100%."
                 " **Do not make any fuss out of ticket it will result in ban**"
                ),
                color=0xFF0000
            )
            view = ScmsgJoinLeaveView(timeout=None)
            await message.channel.send(embed=embed, view=view)
        else:
            embed = discord.Embed(description=info["text"], color=info["color"])
            if info.get("image"):
                embed.set_image(url=info["image"])
            await message.channel.send(embed=embed)

    await bot.process_commands(message)


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
# ?setup command
# -----------------------------
@bot.command(name="setup")
async def setup_panel(ctx):
    embed = Embed(
        title="📋 Request a Middleman",
        description="Click the green button below to request a middleman for your trade.",
        color=discord.Color.blue()
    )
    view = ui.View()
    button = ui.Button(label="Request a Middleman", style=discord.ButtonStyle.success)

    async def callback(interaction: Interaction):
        await interaction.response.send_modal(TicketModal())

    button.callback = callback
    view.add_item(button)
    await ctx.send(embed=embed, view=view)

# -----------------------------
# ?delete command
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

# -----------------------------
# ?handle command
# -----------------------------
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

# -----------------------------
# Trigger messages
# -----------------------------
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    triggers = {
        ".form": {"text": "**Please fill the form below:**\n1. What are you trading?\n2. Do you confirm your trade?\n3. Do you know the Middleman process?", "color": discord.Color.green(), "image": None},
        ".mminfo": {"text": "**How the middleman process works:**\n1. Seller passes item to middleman.\n2. Buyer pays seller.\n3. Middleman delivers item to buyer.\n4. Both traders vouch for middleman.", "color": discord.Color.purple(), "image": "https://i.imgur.com/P2EU3dy.png"},
        ".scmsg": {"text": "Oh no! Unfortunately, you got scammed!\nHowever, there is a way to profit from this experience.", "color": discord.Color.red(), "image": "https://cdn.discordapp.com/attachments/1345858190021103657/1375512933177491618/Picsart_25-05-23_22-20-50-784.png"},
    }

    content = message.content.lower()
    if content in triggers:
        info = triggers[content]
        embed = Embed(title="", description=info["text"], color=info["color"])
        if info["image"]:
            embed.set_image(url=info["image"])
        await message.channel.send(embed=embed)

    await bot.process_commands(message)

# -----------------------------
# On ready
# -----------------------------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

# -----------------------------
# Run bot
# -----------------------------
keep_alive()  # Start the web server
bot.run(DISCORD_TOKEN)