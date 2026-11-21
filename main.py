import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from google import genai
from dotenv import load_dotenv

load_dotenv()

# ================= ตั้งค่า TOKEN และ API KEY =================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN") or "ใส่_DISCORD_BOT_TOKEN_ของคุณตรงนี้"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or "ใส่_GEMINI_API_KEY_ของคุณตรงนี้"
HISTORY_FILE = "fortune_history.json"
CONFIG_FILE = "fortune_config.json"
# ==========================================================

ai_client = genai.Client(api_key=GEMINI_API_KEY)


# ฟังก์ชันจัดการไฟล์ JSON (ประวัติการดูดวง และตำแหน่งข้อความเมนู)
def load_json(filename):
    if not os.path.exists(filename):
        return {}
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# 1. หน้าต่าง Modal สำหรับกรอกข้อมูลดูดวง
class FortuneModal(discord.ui.Modal, title="🔮 กรอกข้อมูลเพื่อทำนายดวงชะตา"):
    name_input = discord.ui.TextInput(
        label="ชื่อของคุณ (ชื่อเล่น หรือ ชื่อจริง)",
        placeholder="เช่น นนท์, สมชาย",
        required=True,
        max_length=50
    )
    dob_input = discord.ui.TextInput(
        label="วัน/เดือน/ปีเกิด (หรือวันเกิด เช่น วันจันทร์)",
        placeholder="เช่น 15/08/2548 หรือ วันอังคาร ปีมะโรง",
        required=True,
        max_length=50
    )
    topic_input = discord.ui.TextInput(
        label="เรื่องที่ต้องการดูดวง",
        style=discord.TextStyle.paragraph,
        placeholder="เช่น ความรักช่วงนี้, การเงิน, การเรียน, ดวงการสุ่มของในเกม...",
        required=True,
        max_length=300
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        user_name = self.name_input.value
        user_dob = self.dob_input.value
        user_topic = self.topic_input.value

        tz_bkk = ZoneInfo("Asia/Bangkok")
        now = datetime.now(tz_bkk)
        date_str = now.strftime("%d/%m/%Y")
        time_str = now.strftime("%H:%M น.")

        prompt = f"""
        คุณคือหมอดู AI ผู้เชี่ยวชาญด้านโหราศาสตร์ ไพ่ยิปซี และดวงดาว มีสไตล์การทำนายที่แม่นยำ ลึกลับ น่าเชื่อถือ แต่เข้าใจง่ายและเป็นกันเอง
        วันที่ทำนายปัจจุบันคือ {date_str} เวลา {time_str}
        จงทำนายดวงชะตาให้กับบุคคลต่อไปนี้แบบเจาะจงและไม่ซ้ำใคร (ห้ามใช้แพทเทิร์นเดิมๆ ให้วิเคราะห์ตามพลังงานของชื่อ วันเกิด และเรื่องที่ถามจริงๆ):
        - ชื่อ: {user_name}
        - ข้อมูลวันเกิด: {user_dob}
        - เรื่องที่ต้องการดู: {user_topic}

        รูปแบบคำตอบที่ต้องการ:
        1. คำทำนายเจาะลึกในเรื่องที่ถาม (อิงจากพื้นดวงวันเกิดและพลังงานช่วงเวลานี้)
        2. แนวโน้มสิ่งที่จะเกิดขึ้น (ข้อดีที่ควรคว้าไว้ หรือข้อควรระวัง)
        3. คำแนะนำเสริมดวง / เลขนำโชค / สีมงคลประจำตัวสำหรับเรื่องนี้
        (เขียนให้กระชับ อ่านง่าย ความยาวประมาณ 150-250 คำ ใช้ Emoji ประกอบให้สวยงาม)
        """

        try:
            models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash"]
            response = None
            last_error = None

            for model_name in models_to_try:
                try:
                    response = ai_client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                    )
                    if response and response.text:
                        break
                except Exception as model_err:
                    last_error = model_err
                    continue

            if not response or not response.text:
                raise last_error

            prediction_text = response.text

            history_data = load_json(HISTORY_FILE)
            user_id = str(interaction.user.id)

            if user_id not in history_data:
                history_data[user_id] = []

            history_data[user_id].append({
                "date": date_str,
                "time": time_str,
                "name": user_name,
                "dob": user_dob,
                "topic": user_topic,
                "result": prediction_text
            })
            save_json(HISTORY_FILE, history_data)

            embed = discord.Embed(
                title=f"✨ ผลการทำนายดวงชะตาของ {user_name}",
                description=prediction_text,
                color=discord.Color.purple()
            )
            embed.add_field(name="📅 วันเกิดที่ระบุ", value=user_dob, inline=True)
            embed.add_field(name="🎯 เรื่องที่ดู", value=user_topic, inline=True)
            embed.set_footer(text=f"ทำนายเมื่อ {date_str} เวลา {time_str} • บันทึกลงประวัติแล้ว")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            err_msg = str(e)
            if "403" in err_msg or "PERMISSION_DENIED" in err_msg:
                await interaction.followup.send(
                    "❌ **API Key นี้ถูกปฏิเสธสิทธิ์ (403 PERMISSION_DENIED)**\n"
                    "โปรเจกต์ใน Google AI Studio นี้ไม่มีโควตา Free Tier กรุณาเข้าไปที่ [Google AI Studio](https://aistudio.google.com/app/apikey) กดสร้าง API Key ใน **New Project** อันใหม่ แล้วนำมาเปลี่ยนใน `GEMINI_API_KEY` ครับ",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(f"❌ เกิดข้อผิดพลาดในการเชื่อมต่อกับดวงดาว: `{e}`", ephemeral=True)


# 2. หน้าต่าง Modal สำหรับแอดมินแก้ไขข้อความเมนูหมอดูที่ส่งค้างไว้
class EditMenuModal(discord.ui.Modal, title="✏️ แก้ไขข้อความเมนูสำนักดูดวง"):
    def __init__(self, target_message: discord.Message, current_title: str, current_desc: str, current_footer: str):
        super().__init__()
        self.target_message = target_message

        self.title_input = discord.ui.TextInput(
            label="หัวข้อเมนู (Title)",
            default=current_title,
            required=True,
            max_length=256
        )
        self.desc_input = discord.ui.TextInput(
            label="รายละเอียดข้อความ (Description)",
            style=discord.TextStyle.paragraph,
            default=current_desc,
            required=True,
            max_length=4000
        )
        self.footer_input = discord.ui.TextInput(
            label="ข้อความด้านล่างสุด (Footer)",
            default=current_footer,
            required=False,
            max_length=2048
        )
        self.add_item(self.title_input)
        self.add_item(self.desc_input)
        self.add_item(self.footer_input)

    async def on_submit(self, interaction: discord.Interaction):
        new_embed = discord.Embed(
            title=self.title_input.value,
            description=self.desc_input.value,
            color=discord.Color.dark_purple()
        )
        if self.footer_input.value:
            new_embed.set_footer(text=self.footer_input.value)

        await self.target_message.edit(embed=new_embed, view=FortuneMenuView())
        await interaction.response.send_message("✅ อัปเดตข้อความเมนูหมอดูเรียบร้อยแล้ว!", ephemeral=True)


# 3. ปุ่มเมนูหลักที่ส่งค้างไว้ในห้อง (Persistent View)
class FortuneMenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="ดูดวงกับ AI", style=discord.ButtonStyle.primary, emoji="🔮", custom_id="persistent_fortune_btn")
    async def fortune_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(FortuneModal())

    @discord.ui.button(label="ประวัติการดูดวง", style=discord.ButtonStyle.secondary, emoji="📜", custom_id="persistent_history_btn")
    async def history_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        history_data = load_json(HISTORY_FILE)
        user_id = str(interaction.user.id)

        if user_id not in history_data or len(history_data[user_id]) == 0:
            await interaction.response.send_message("📭 คุณยังไม่มีประวัติการดูดวง กดปุ่ม **🔮 ดูดวงกับ AI** เพื่อเริ่มต้นได้เลย!", ephemeral=True)
            return

        user_records = history_data[user_id]
        recent_records = list(reversed(user_records))[:5]

        embed = discord.Embed(
            title=f"📜 ประวัติการดูดวงของ {interaction.user.display_name}",
            description=f"แสดงรายการล่าสุด {len(recent_records)} รายการ (จากทั้งหมด {len(user_records)} ครั้ง)",
            color=discord.Color.gold()
        )

        for idx, record in enumerate(recent_records, 1):
            short_result = record['result'][:350] + "..." if len(record['result']) > 350 else record['result']
            field_title = f"#{idx} | วันที่ {record['date']} เวลา {record['time']}"
            field_value = (
                f"**ชื่อ:** {record['name']} ({record['dob']})\n"
                f"**เรื่องที่ดู:** {record['topic']}\n"
                f"**คำทำนาย:** {short_result}\n"
                f"────────────────────"
            )
            embed.add_field(name=field_title, value=field_value, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)


# 4. ตั้งค่าตัวบอท
class FortuneBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(FortuneMenuView())
        await self.tree.sync()


bot = FortuneBot()


@bot.event
async def on_ready():
    print(f"✅ บอทหมอดู {bot.user} พร้อมเปิดสำนักแล้ว!")


# คำสั่งส่งเมนูหมอดูค้างไว้ในห้อง
@bot.tree.command(name="setup_fortune", description="ส่งเมนูหมอดู AI ค้างไว้ในห้องแชทที่เลือก")
@app_commands.describe(channel="เลือกห้องแชทที่ต้องการให้ส่งเมนูหมอดูไปค้างไว้")
@app_commands.checks.has_permissions(administrator=True)
async def setup_fortune(interaction: discord.Interaction, channel: discord.TextChannel):
    embed = discord.Embed(
        title="🔮 สำนักดูดวง AI พยากรณ์ชะตาชีวิต",
        description=(
            "อยากรู้เรื่องอะไร ถามดวงดาวได้เลย! ระบบ AI จะวิเคราะห์พื้นดวงจากวันเกิดและเรื่องที่คุณต้องการทราบแบบเจาะลึก\n\n"
            "**วิธีใช้งาน:**\n"
            "1. กดปุ่ม **🔮 ดูดวงกับ AI** ด้านล่าง\n"
            "2. กรอก **ชื่อ**, **วันเกิด**, และ **เรื่องที่อยากดู**\n"
            "3. รอ AI คำนวณคำทำนาย (ผลลัพธ์จะเห็นเฉพาะคุณคนเดียว)\n"
            "4. กดปุ่ม **📜 ประวัติการดูดวง** เพื่อดูย้อนหลังได้ตลอดเวลา"
        ),
        color=discord.Color.dark_purple()
    )
    embed.set_footer(text="ระบบทำนายอัตโนมัติ • ข้อมูลของคุณจะถูกเก็บเป็นส่วนตัว")

    sent_msg = await channel.send(embed=embed, view=FortuneMenuView())

    config_data = load_json(CONFIG_FILE)
    guild_id = str(interaction.guild_id)
    config_data[guild_id] = {
        "channel_id": channel.id,
        "message_id": sent_msg.id
    }
    save_json(CONFIG_FILE, config_data)

    await interaction.response.send_message(f"✅ ส่งเมนูหมอดูไปที่ห้อง {channel.mention} เรียบร้อยแล้ว!", ephemeral=True)


# คำสั่งแก้ไขข้อความเมนูหมอดูที่ส่งค้างไว้
@bot.tree.command(name="edit_fortune", description="แก้ไขข้อความเมนูหมอดูที่ส่งค้างไว้ในห้อง")
@app_commands.describe(message_id="(ไม่บังคับ) ใส่ ID ข้อความถ้าต้องการแก้ข้อความอันเก่า หากไม่ใส่จะแก้เมนูล่าสุดอัตโนมัติ")
@app_commands.checks.has_permissions(administrator=True)
async def edit_fortune(interaction: discord.Interaction, message_id: str = None):
    guild_id = str(interaction.guild_id)
    config_data = load_json(CONFIG_FILE)

    target_msg = None

    if message_id:
        try:
            msg_id_int = int(message_id.strip())
            try:
                target_msg = await interaction.channel.fetch_message(msg_id_int)
            except discord.NotFound:
                if guild_id in config_data:
                    ch = bot.get_channel(config_data[guild_id]["channel_id"])
                    if ch:
                        target_msg = await ch.fetch_message(msg_id_int)
        except ValueError:
            await interaction.response.send_message("❌ รูปแบบ Message ID ไม่ถูกต้อง (ต้องเป็นตัวเลขเท่านั้น)", ephemeral=True)
            return
    else:
        if guild_id not in config_data:
            await interaction.response.send_message("❌ ยังไม่พบข้อมูลเมนูที่ส่งค้างไว้ กรุณาใช้คำสั่ง `/setup_fortune` ก่อน หรือระบุ `message_id`", ephemeral=True)
            return
        ch = bot.get_channel(config_data[guild_id]["channel_id"])
        if ch:
            try:
                target_msg = await ch.fetch_message(config_data[guild_id]["message_id"])
            except discord.NotFound:
                pass

    if not target_msg:
        await interaction.response.send_message("❌ ไม่พบข้อความเมนูดังกล่าว (อาจถูกลบไปแล้ว หรือบอทไม่มีสิทธิ์เข้าถึงห้องนั้น)", ephemeral=True)
        return

    if target_msg.author.id != bot.user.id:
        await interaction.response.send_message("❌ บอทแก้ไขได้เฉพาะข้อความที่บอทเป็นคนส่งเท่านั้นครับ", ephemeral=True)
        return

    current_title = "🔮 สำนักดูดวง AI พยากรณ์ชะตาชีวิต"
    current_desc = ""
    current_footer = ""

    if target_msg.embeds:
        old_embed = target_msg.embeds[0]
        if old_embed.title:
            current_title = old_embed.title
        if old_embed.description:
            current_desc = old_embed.description
        if old_embed.footer and old_embed.footer.text:
            current_footer = old_embed.footer.text

    await interaction.response.send_modal(
        EditMenuModal(target_msg, current_title, current_desc, current_footer)
    )


if __name__ == "__main__":
    if DISCORD_TOKEN == "ใส่_DISCORD_BOT_TOKEN_ของคุณตรงนี้" or GEMINI_API_KEY == "ใส่_GEMINI_API_KEY_ของคุณตรงนี้":
        print("❌ กรุณาใส่ DISCORD_TOKEN และ GEMINI_API_KEY ก่อนรันบอท!")
    else:
        bot.run(DISCORD_TOKEN)
