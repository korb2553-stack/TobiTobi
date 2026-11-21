import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from google import genai
from dotenv import load_dotenv

# โหลดค่าจากไฟล์ .env (เผื่อใช้งาน)
load_dotenv()

# ================= ตั้งค่า TOKEN และ API KEY =================
# ใส่คีย์ของคุณในเครื่องหมายคำพูดด้านล่างนี้ได้เลยครับ
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN") or "ใส่_DISCORD_BOT_TOKEN_ของคุณตรงนี้"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or "ใส่_GEMINI_API_KEY_ของคุณตรงนี้"
HISTORY_FILE = "fortune_history.json"
# ==========================================================

# ตั้งค่า Gemini AI
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# ฟังก์ชันจัดการไฟล์ประวัติการดูดวง
def load_history():
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

def save_history(data):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
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
        # แจ้งเตือนว่ากำลังคำนวณ (ป้องกัน Discord ตัดการเชื่อมต่อเพราะ AI คิดนานเกิน 3 วิ)
        await interaction.response.defer(ephemeral=True)

        user_name = self.name_input.value
        user_dob = self.dob_input.value
        user_topic = self.topic_input.value

        # ดึงเวลาประเทศไทยปัจจุบันเพื่อให้ AI อ้างอิงช่วงเวลาได้แม่นยำขึ้น
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
            response = ai_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            prediction_text = response.text

            # บันทึกประวัติลงไฟล์ JSON
            history_data = load_history()
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
            save_history(history_data)

            # สร้าง Embed แสดงผลคำทำนาย
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
            await interaction.followup.send(f"❌ เกิดข้อผิดพลาดในการเชื่อมต่อกับดวงดาว: `{e}`", ephemeral=True)


# 2. ปุ่มเมนูหลัก (ใช้ timeout=None เพื่อให้ปุ่มกดได้ตลอดกาลแม้บอทรีสตาร์ท)
class FortuneMenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="ดูดวงกับ AI", style=discord.ButtonStyle.primary, emoji="🔮", custom_id="persistent_fortune_btn")
    async def fortune_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(FortuneModal())

    @discord.ui.button(label="ประวัติการดูดวง", style=discord.ButtonStyle.secondary, emoji="📜", custom_id="persistent_history_btn")
    async def history_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        history_data = load_history()
        user_id = str(interaction.user.id)

        if user_id not in history_data or len(history_data[user_id]) == 0:
            await interaction.response.send_message("📭 คุณยังไม่มีประวัติการดูดวง กดปุ่ม **🔮 ดูดวงกับ AI** เพื่อเริ่มต้นได้เลย!", ephemeral=True)
            return

        user_records = history_data[user_id]
        # ดึงประวัติ 5 ครั้งล่าสุดมาแสดง (เรียงจากใหม่ไปเก่า)
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
                f"**ชื่อ:** {record['name']} ({record['dob']})
"
                f"**เรื่องที่ดู:** {record['topic']}
"
                f"**คำทำนาย:** {short_result}
"
                f"────────────────────"
            )
            embed.add_field(name=field_title, value=field_value, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)


# 3. ตั้งค่าตัวบอท
class FortuneBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # ลงทะเบียนปุ่มถาวร (Persistent View)
        self.add_view(FortuneMenuView())
        await self.tree.sync()

bot = FortuneBot()

@bot.event
async def on_ready():
    print(f"✅ บอทหมอดู {bot.user} พร้อมเปิดสำนักแล้ว!")

# คำสั่ง Slash Command สำหรับส่งเมนูไปค้างไว้ในห้องที่กำหนด
@bot.tree.command(name="setup_fortune", description="ส่งเมนูหมอดู AI ค้างไว้ในห้องแชทที่เลือก")
@app_commands.describe(channel="เลือกห้องแชทที่ต้องการให้ส่งเมนูหมอดูไปค้างไว้")
@app_commands.checks.has_permissions(administrator=True)
async def setup_fortune(interaction: discord.Interaction, channel: discord.TextChannel):
    embed = discord.Embed(
        title="🔮 สำนักดูดวง AI พยากรณ์ชะตาชีวิต",
        description=(
            "อยากรู้เรื่องอะไร ถามดวงดาวได้เลย! ระบบ AI จะวิเคราะห์พื้นดวงจากวันเกิดและเรื่องที่คุณต้องการทราบแบบเจาะลึก

"
            "**วิธีใช้งาน:**
"
            "1. กดปุ่ม **🔮 ดูดวงกับ AI** ด้านล่าง
"
            "2. กรอก **ชื่อ**, **วันเกิด**, และ **เรื่องที่อยากดู**
"
            "3. รอ AI คำนวณคำทำนาย (ผลลัพธ์จะเห็นเฉพาะคุณคนเดียว)
"
            "4. กดปุ่ม **📜 ประวัติการดูดวง** เพื่อดูย้อนหลังได้ตลอดเวลา"
        ),
        color=discord.Color.dark_purple()
    )
    embed.set_footer(text="ระบบทำนายอัตโนมัติ • ข้อมูลของคุณจะถูกเก็บเป็นส่วนตัว")

    await channel.send(embed=embed, view=FortuneMenuView())
    await interaction.response.send_message(f"✅ ส่งเมนูหมอดูไปที่ห้อง {channel.mention} เรียบร้อยแล้ว!", ephemeral=True)

if __name__ == "__main__":
    if DISCORD_TOKEN == "ใส่_DISCORD_BOT_TOKEN_ของคุณตรงนี้" or GEMINI_API_KEY == "ใส่_GEMINI_API_KEY_ของคุณตรงนี้":
        print("❌ กรุณาใส่ DISCORD_TOKEN และ GEMINI_API_KEY ในไฟล์ main.py หรือ .env ก่อนรันบอท!")
    else:
        bot.run(DISCORD_TOKEN)
