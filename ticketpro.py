import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import discord
from discord import app_commands
from discord.ext import commands

# ============================================================
# RAUL SYSTEMS - TICKET PREMIUM DE VENDAS
# Desenvolvido por Dev Raul
# Railway:
#   Variável obrigatória: DISCORD_TOKEN
# Requisitos:
#   pip install -U discord.py
# ============================================================

TOKEN = os.getenv("DISCORD_TOKEN")

GUILD_ID = 0  # opcional: coloque o ID do servidor para comandos aparecerem mais rápido
DATA_FILE = "raul_systems_ticket_data.json"

BRAND_NAME = "Raul Systems"
DEV_NAME = "Dev Raul"
BOT_STATUS = "Raul Systems • Bots personalizados"
THUMBNAIL_URL = "https://cdn-icons-png.flaticon.com/512/4712/4712109.png"
EMBED_COLOR = 0x8E44AD

ROLE_INTERESSADO = "👀・Interessado"
ROLE_CLIENTE = "🛒・Cliente"
ROLE_CLIENTE_VIP = "💎・Cliente VIP"

CANAL_DEMOS_NOME = "🎥・demonstrações"


# =========================
# UTILIDADES
# =========================

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def br_now() -> str:
    return now_utc().astimezone().strftime("%d/%m/%Y %H:%M:%S")


def sanitize_channel_name(text: str) -> str:
    text = text.lower().strip().replace(" ", "-")
    allowed = "abcdefghijklmnopqrstuvwxyz0123456789-_"
    cleaned = "".join(c for c in text if c in allowed)
    return cleaned[:80] if cleaned else "ticket"


class DataManager:
    def __init__(self, path: str):
        self.path = path
        self.data = self.load()

    def default_data(self) -> Dict[str, Any]:
        return {
            "ticket_panel_channel_id": None,
            "ticket_category_id": None,
            "voice_category_id": None,
            "staff_role_ids": [],
            "logs_channel_id": None,
            "panel_message_id": None,
            "ticket_counter": 0,
            "tickets": {}
        }

    def load(self) -> Dict[str, Any]:
        if not os.path.exists(self.path):
            data = self.default_data()
            self.save_data(data)
            return data

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                loaded = json.load(f)

            default = self.default_data()
            for key, value in default.items():
                loaded.setdefault(key, value)

            return loaded
        except Exception:
            data = self.default_data()
            self.save_data(data)
            return data

    def save_data(self, data: Dict[str, Any]) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def save(self) -> None:
        self.save_data(self.data)

    def next_ticket_number(self) -> int:
        self.data["ticket_counter"] += 1
        self.save()
        return self.data["ticket_counter"]

    def add_ticket(self, channel_id: int, payload: Dict[str, Any]) -> None:
        self.data["tickets"][str(channel_id)] = payload
        self.save()

    def get_ticket(self, channel_id: int) -> Optional[Dict[str, Any]]:
        return self.data["tickets"].get(str(channel_id))

    def remove_ticket(self, channel_id: int) -> None:
        self.data["tickets"].pop(str(channel_id), None)
        self.save()


data = DataManager(DATA_FILE)

intents = discord.Intents.default()
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


# =========================
# CHECAGENS
# =========================

def is_staff(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True

    staff_role_ids = data.data.get("staff_role_ids", [])
    return any(role.id in staff_role_ids for role in member.roles)


async def require_staff(interaction: discord.Interaction) -> bool:
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message(
            "❌ Este comando só pode ser usado dentro de um servidor.",
            ephemeral=True
        )
        return False

    if not is_staff(interaction.user):
        await interaction.response.send_message(
            "❌ Você não tem permissão para usar isso.",
            ephemeral=True
        )
        return False

    return True


async def send_log(guild: discord.Guild, text: str) -> None:
    logs_id = data.data.get("logs_channel_id")
    if not logs_id:
        return

    channel = guild.get_channel(logs_id)
    if isinstance(channel, discord.TextChannel):
        embed = discord.Embed(
            title="📋 Log | Raul Systems",
            description=text,
            color=discord.Color.blurple(),
            timestamp=now_utc(),
        )
        embed.set_footer(text=f"{BRAND_NAME} • {DEV_NAME}")
        await channel.send(embed=embed)


async def add_role_by_name(member: discord.Member, role_name: str) -> bool:
    role = discord.utils.get(member.guild.roles, name=role_name)
    if not role:
        return False

    try:
        await member.add_roles(role, reason=f"{BRAND_NAME} ticket system")
        return True
    except Exception:
        return False


async def remove_role_by_name(member: discord.Member, role_name: str) -> bool:
    role = discord.utils.get(member.guild.roles, name=role_name)
    if not role:
        return False

    try:
        await member.remove_roles(role, reason=f"{BRAND_NAME} ticket system")
        return True
    except Exception:
        return False


def get_demo_channel_mention(guild: discord.Guild) -> str:
    channel = discord.utils.get(guild.text_channels, name=CANAL_DEMOS_NOME)
    if channel:
        return channel.mention
    return f"#{CANAL_DEMOS_NOME}"


# =========================
# MODAL BASE DO TICKET
# =========================

class BudgetModal(discord.ui.Modal):
    def __init__(self, ticket_type: str):
        super().__init__(title=f"🎫 {ticket_type}")
        self.ticket_type = ticket_type

        self.project_name = discord.ui.TextInput(
            label="Nome do bot ou projeto",
            placeholder="Ex: Bot de ticket, vendas, moderação, RP...",
            max_length=80,
            required=True,
        )

        self.description = discord.ui.TextInput(
            label="Explique o que você precisa",
            placeholder="Funções, comandos, cargos, canais, logs, painel, sistema etc.",
            style=discord.TextStyle.paragraph,
            max_length=1500,
            required=True,
        )

        self.budget = discord.ui.TextInput(
            label="Orçamento ou faixa de valor",
            placeholder="Ex: R$50, R$100, R$200, quero orçamento...",
            max_length=80,
            required=False,
        )

        self.deadline = discord.ui.TextInput(
            label="Prazo desejado",
            placeholder="Ex: urgente, 3 dias, 5 dias, sem pressa...",
            max_length=80,
            required=False,
        )

        self.references = discord.ui.TextInput(
            label="Referências ou observações",
            placeholder="Tem print, bot parecido, servidor referência? Escreva aqui.",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=False,
        )

        self.add_item(self.project_name)
        self.add_item(self.description)
        self.add_item(self.budget)
        self.add_item(self.deadline)
        self.add_item(self.references)

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ Erro ao abrir ticket.", ephemeral=True)
            return

        ticket_category_id = data.data.get("ticket_category_id")
        staff_role_ids = data.data.get("staff_role_ids", [])

        if not ticket_category_id or not staff_role_ids:
            await interaction.response.send_message(
                "❌ O sistema ainda não foi configurado. Use `/cfgticket` primeiro.",
                ephemeral=True,
            )
            return

        category = interaction.guild.get_channel(ticket_category_id)
        staff_roles = [interaction.guild.get_role(role_id) for role_id in staff_role_ids]
        staff_roles = [role for role in staff_roles if role is not None]

        if not isinstance(category, discord.CategoryChannel) or not staff_roles:
            await interaction.response.send_message(
                "❌ Categoria ou cargo de atendimento inválido. Reconfigure com `/cfgticket`.",
                ephemeral=True,
            )
            return

        for ticket in data.data.get("tickets", {}).values():
            if ticket.get("owner_id") == interaction.user.id and ticket.get("status") == "open":
                old_channel = interaction.guild.get_channel(ticket.get("text_channel_id"))
                if old_channel:
                    await interaction.response.send_message(
                        f"⚠️ Você já tem um ticket aberto: {old_channel.mention}",
                        ephemeral=True,
                    )
                    return

        number = data.next_ticket_number()
        channel_name = sanitize_channel_name(f"ticket-{number}-{interaction.user.display_name}")

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                attach_files=True,
                read_message_history=True,
            ),
            interaction.guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                manage_permissions=True,
                read_message_history=True,
            ),
        }

        for staff_role in staff_roles:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_messages=True,
                attach_files=True,
                read_message_history=True,
            )

        staff_mentions = " ".join(role.mention for role in staff_roles)

        text_channel = await interaction.guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            reason=f"Ticket criado por {interaction.user}",
        )

        ticket_payload = {
            "ticket_id": number,
            "ticket_type": self.ticket_type,
            "owner_id": interaction.user.id,
            "owner_name": str(interaction.user),
            "text_channel_id": text_channel.id,
            "voice_channel_id": None,
            "claimed_by_id": None,
            "claimed_by_name": None,
            "status": "open",
            "sold": False,
            "delivered": False,
            "created_at": br_now(),
            "project_name": str(self.project_name),
            "description": str(self.description),
            "budget": str(self.budget) if self.budget else "Não informado",
            "deadline": str(self.deadline) if self.deadline else "Não informado",
            "references": str(self.references) if self.references else "Não informado",
        }

        data.add_ticket(text_channel.id, ticket_payload)

        await add_role_by_name(interaction.user, ROLE_INTERESSADO)

        demo_mention = get_demo_channel_mention(interaction.guild)

        welcome_embed = discord.Embed(
            title=f"🎫 Ticket #{number} aberto",
            description=(
                f"Olá {interaction.user.mention}, seu atendimento foi aberto com sucesso.\n\n"
                f"📌 **Tipo:** {self.ticket_type}\n"
                "Nossa equipe já recebeu sua solicitação. Aguarde um momento, logo alguém irá assumir seu ticket.\n\n"
                f"🎥 Enquanto isso, veja nossos bots funcionando em: {demo_mention}\n\n"
                "💡 **Todos os bots são personalizados conforme seu servidor.**"
            ),
            color=EMBED_COLOR,
            timestamp=now_utc(),
        )
        welcome_embed.add_field(name="🤖 Projeto", value=str(self.project_name), inline=False)
        welcome_embed.add_field(name="💰 Orçamento", value=str(self.budget) if self.budget else "Não informado", inline=True)
        welcome_embed.add_field(name="⏱️ Prazo", value=str(self.deadline) if self.deadline else "Não informado", inline=True)
        welcome_embed.set_footer(text=f"{BRAND_NAME} • {DEV_NAME}")
        welcome_embed.set_thumbnail(url=THUMBNAIL_URL)

        details_embed = discord.Embed(
            title="📋 Informações enviadas pelo cliente",
            color=discord.Color.blurple(),
            timestamp=now_utc(),
        )
        details_embed.add_field(name="👤 Cliente", value=interaction.user.mention, inline=False)
        details_embed.add_field(name="📌 Tipo", value=self.ticket_type, inline=True)
        details_embed.add_field(name="🤖 Projeto", value=str(self.project_name), inline=True)
        details_embed.add_field(name="📝 Descrição", value=str(self.description)[:1024], inline=False)
        details_embed.add_field(name="💰 Orçamento", value=str(self.budget) if self.budget else "Não informado", inline=True)
        details_embed.add_field(name="⏱️ Prazo", value=str(self.deadline) if self.deadline else "Não informado", inline=True)
        details_embed.add_field(name="📎 Referências", value=str(self.references)[:1024] if self.references else "Não informado", inline=False)
        details_embed.set_footer(text=f"Ticket #{number} • {DEV_NAME}")

        await text_channel.send(
            content=f"{interaction.user.mention} {staff_mentions}",
            embed=welcome_embed,
            view=TicketControlView(),
        )
        await text_channel.send(embed=details_embed)

        await interaction.response.send_message(
            f"✅ Seu ticket foi criado com sucesso: {text_channel.mention}",
            ephemeral=True,
        )

        await send_log(
            interaction.guild,
            f"🎫 Ticket #{number} criado por {interaction.user.mention}. Tipo: **{self.ticket_type}**. Canal: {text_channel.mention}"
        )


# =========================
# PAINEL PRINCIPAL
# =========================

class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Comprar Bot",
        emoji="💰",
        style=discord.ButtonStyle.success,
        custom_id="rs_ticket:buy",
    )
    async def buy_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BudgetModal("💰 Comprar bot"))

    @discord.ui.button(
        label="Suporte",
        emoji="🛠️",
        style=discord.ButtonStyle.primary,
        custom_id="rs_ticket:support",
    )
    async def support_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BudgetModal("🛠️ Suporte"))

    @discord.ui.button(
        label="Dúvida",
        emoji="❓",
        style=discord.ButtonStyle.secondary,
        custom_id="rs_ticket:doubt",
    )
    async def doubt_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BudgetModal("❓ Dúvida"))

    @discord.ui.button(
        label="Alteração",
        emoji="📦",
        style=discord.ButtonStyle.secondary,
        custom_id="rs_ticket:change",
    )
    async def change_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BudgetModal("📦 Solicitar alteração"))


# =========================
# MODAIS AUXILIARES
# =========================

class AddMemberModal(discord.ui.Modal, title="➕ Adicionar membro"):
    member_id = discord.ui.TextInput(
        label="ID do usuário",
        placeholder="Cole o ID do usuário que deseja adicionar",
        max_length=30,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ Erro ao adicionar membro.", ephemeral=True)
            return

        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
            await interaction.response.send_message("❌ Apenas a equipe pode adicionar membros.", ephemeral=True)
            return

        try:
            user_id = int(str(self.member_id).strip())
        except ValueError:
            await interaction.response.send_message("❌ ID inválido.", ephemeral=True)
            return

        member = interaction.guild.get_member(user_id)
        if not member:
            await interaction.response.send_message("❌ Não encontrei esse membro no servidor.", ephemeral=True)
            return

        await interaction.channel.set_permissions(
            member,
            view_channel=True,
            send_messages=True,
            attach_files=True,
            read_message_history=True,
        )

        await interaction.response.send_message(f"✅ {member.mention} foi adicionado ao ticket.")
        await send_log(
            interaction.guild,
            f"➕ {member.mention} adicionado ao ticket {interaction.channel.mention} por {interaction.user.mention}."
        )


class RemoveMemberModal(discord.ui.Modal, title="➖ Remover membro"):
    member_id = discord.ui.TextInput(
        label="ID do usuário",
        placeholder="Cole o ID do usuário que deseja remover",
        max_length=30,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ Erro ao remover membro.", ephemeral=True)
            return

        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
            await interaction.response.send_message("❌ Apenas a equipe pode remover membros.", ephemeral=True)
            return

        try:
            user_id = int(str(self.member_id).strip())
        except ValueError:
            await interaction.response.send_message("❌ ID inválido.", ephemeral=True)
            return

        member = interaction.guild.get_member(user_id)
        if not member:
            await interaction.response.send_message("❌ Não encontrei esse membro no servidor.", ephemeral=True)
            return

        await interaction.channel.set_permissions(member, overwrite=None)

        await interaction.response.send_message(f"✅ {member.mention} foi removido do ticket.")
        await send_log(
            interaction.guild,
            f"➖ {member.mention} removido do ticket {interaction.channel.mention} por {interaction.user.mention}."
        )


# =========================
# CONTROLES DO TICKET
# =========================

class CloseConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Confirmar Encerramento", emoji="🔒", style=discord.ButtonStyle.danger)
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ Erro ao encerrar.", ephemeral=True)
            return

        ticket = data.get_ticket(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ Este canal não está registrado como ticket.", ephemeral=True)
            return

        owner_id = ticket.get("owner_id")
        is_owner = interaction.user.id == owner_id
        is_team = isinstance(interaction.user, discord.Member) and is_staff(interaction.user)

        if not is_owner and not is_team:
            await interaction.response.send_message("❌ Você não pode encerrar este ticket.", ephemeral=True)
            return

        await interaction.response.send_message("🔒 Encerrando ticket...")

        voice_channel_id = ticket.get("voice_channel_id")
        if voice_channel_id:
            voice_channel = interaction.guild.get_channel(voice_channel_id)
            if isinstance(voice_channel, discord.VoiceChannel):
                try:
                    await voice_channel.delete(reason="Ticket encerrado")
                except Exception:
                    pass

        await send_log(
            interaction.guild,
            (
                f"🔒 Ticket #{ticket.get('ticket_id')} encerrado por {interaction.user.mention}.\n"
                f"📌 Tipo: **{ticket.get('ticket_type')}**\n"
                f"💰 Vendido: **{'Sim' if ticket.get('sold') else 'Não'}**\n"
                f"📦 Entregue: **{'Sim' if ticket.get('delivered') else 'Não'}**"
            )
        )

        data.remove_ticket(interaction.channel.id)

        try:
            await interaction.channel.delete(reason=f"Ticket encerrado por {interaction.user}")
        except Exception:
            pass

    @discord.ui.button(label="Cancelar", emoji="↩️", style=discord.ButtonStyle.secondary)
    async def cancel_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("✅ Encerramento cancelado.", ephemeral=True)


class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Assumir", emoji="🙋", style=discord.ButtonStyle.primary, custom_id="rs_ticket:claim")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ Erro ao assumir ticket.", ephemeral=True)
            return

        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
            await interaction.response.send_message("❌ Apenas a equipe pode assumir tickets.", ephemeral=True)
            return

        ticket = data.get_ticket(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ Este canal não é um ticket registrado.", ephemeral=True)
            return

        if ticket.get("claimed_by_id"):
            await interaction.response.send_message(
                f"⚠️ Este ticket já foi assumido por <@{ticket.get('claimed_by_id')}>.",
                ephemeral=True,
            )
            return

        ticket["claimed_by_id"] = interaction.user.id
        ticket["claimed_by_name"] = str(interaction.user)
        data.add_ticket(interaction.channel.id, ticket)

        embed = discord.Embed(
            title="🙋 Ticket Assumido",
            description=f"Este atendimento agora está com {interaction.user.mention}.",
            color=discord.Color.green(),
            timestamp=now_utc(),
        )
        embed.set_footer(text=f"{BRAND_NAME} • {DEV_NAME}")

        await interaction.response.send_message(embed=embed)
        await send_log(interaction.guild, f"🙋 Ticket #{ticket.get('ticket_id')} assumido por {interaction.user.mention}.")

    @discord.ui.button(label="Criar Call", emoji="📞", style=discord.ButtonStyle.success, custom_id="rs_ticket:create_call")
    async def create_call(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ Erro ao criar call.", ephemeral=True)
            return

        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
            await interaction.response.send_message("❌ Apenas a equipe pode criar call.", ephemeral=True)
            return

        ticket = data.get_ticket(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ Este canal não é um ticket registrado.", ephemeral=True)
            return

        if ticket.get("voice_channel_id"):
            old_voice = interaction.guild.get_channel(ticket.get("voice_channel_id"))
            if old_voice:
                await interaction.response.send_message(f"⚠️ Este ticket já tem uma call: {old_voice.mention}", ephemeral=True)
                return

        voice_category_id = data.data.get("voice_category_id") or data.data.get("ticket_category_id")
        category = interaction.guild.get_channel(voice_category_id)

        if not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message("❌ Categoria de call inválida. Reconfigure com `/cfgticket`.", ephemeral=True)
            return

        owner = interaction.guild.get_member(ticket.get("owner_id"))
        staff_role_ids = data.data.get("staff_role_ids", [])
        staff_roles = [interaction.guild.get_role(role_id) for role_id in staff_role_ids]
        staff_roles = [role for role in staff_roles if role is not None]

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False),
            interaction.guild.me: discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                manage_channels=True,
                move_members=True
            ),
        }

        if owner:
            overwrites[owner] = discord.PermissionOverwrite(view_channel=True, connect=True, speak=True)

        for staff_role in staff_roles:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                speak=True,
                move_members=True
            )

        voice_channel = await interaction.guild.create_voice_channel(
            name=sanitize_channel_name(f"call-ticket-{ticket.get('ticket_id')}")[:90],
            category=category,
            overwrites=overwrites,
            reason=f"Call criada para ticket #{ticket.get('ticket_id')}",
        )

        ticket["voice_channel_id"] = voice_channel.id
        data.add_ticket(interaction.channel.id, ticket)

        await interaction.response.send_message(f"📞 Call criada com sucesso: {voice_channel.mention}")
        await send_log(interaction.guild, f"📞 Call criada para ticket #{ticket.get('ticket_id')} por {interaction.user.mention}.")

    @discord.ui.button(label="Adicionar", emoji="➕", style=discord.ButtonStyle.secondary, custom_id="rs_ticket:add_member")
    async def add_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
            await interaction.response.send_message("❌ Apenas a equipe pode adicionar membros.", ephemeral=True)
            return

        await interaction.response.send_modal(AddMemberModal())

    @discord.ui.button(label="Remover", emoji="➖", style=discord.ButtonStyle.secondary, custom_id="rs_ticket:remove_member")
    async def remove_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
            await interaction.response.send_message("❌ Apenas a equipe pode remover membros.", ephemeral=True)
            return

        await interaction.response.send_modal(RemoveMemberModal())

    @discord.ui.button(label="Venda", emoji="💰", style=discord.ButtonStyle.success, custom_id="rs_ticket:sold")
    async def mark_sold(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ Erro ao marcar venda.", ephemeral=True)
            return

        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
            await interaction.response.send_message("❌ Apenas a equipe pode marcar venda.", ephemeral=True)
            return

        ticket = data.get_ticket(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ Este canal não é um ticket registrado.", ephemeral=True)
            return

        owner = interaction.guild.get_member(ticket.get("owner_id"))
        if owner:
            await add_role_by_name(owner, ROLE_CLIENTE)
            await remove_role_by_name(owner, ROLE_INTERESSADO)

        ticket["sold"] = True
        ticket["sold_by_id"] = interaction.user.id
        ticket["sold_by_name"] = str(interaction.user)
        ticket["sold_at"] = br_now()
        data.add_ticket(interaction.channel.id, ticket)

        embed = discord.Embed(
            title="💰 Venda Confirmada",
            description=(
                f"Venda marcada por {interaction.user.mention}.\n\n"
                "✅ Cliente registrado\n"
                "✅ Cargo de cliente aplicado se existir\n"
                "✅ Ticket atualizado no sistema"
            ),
            color=discord.Color.gold(),
            timestamp=now_utc(),
        )
        embed.set_footer(text=f"{BRAND_NAME} • {DEV_NAME}")

        await interaction.response.send_message(embed=embed)
        await send_log(
            interaction.guild,
            f"💰 Ticket #{ticket.get('ticket_id')} marcado como venda por {interaction.user.mention}."
        )

    @discord.ui.button(label="Entregue", emoji="📦", style=discord.ButtonStyle.primary, custom_id="rs_ticket:delivered")
    async def mark_delivered(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ Erro ao marcar entrega.", ephemeral=True)
            return

        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
            await interaction.response.send_message("❌ Apenas a equipe pode marcar entrega.", ephemeral=True)
            return

        ticket = data.get_ticket(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ Este canal não é um ticket registrado.", ephemeral=True)
            return

        ticket["delivered"] = True
        ticket["delivered_by_id"] = interaction.user.id
        ticket["delivered_by_name"] = str(interaction.user)
        ticket["delivered_at"] = br_now()
        data.add_ticket(interaction.channel.id, ticket)

        embed = discord.Embed(
            title="📦 Bot Entregue",
            description=(
                "✅ Entrega registrada com sucesso.\n\n"
                "Após o cliente confirmar que está tudo certo, alterações extras podem ter acréscimo conforme combinado.\n\n"
                f"Obrigado por comprar com a **{BRAND_NAME}**."
            ),
            color=discord.Color.green(),
            timestamp=now_utc(),
        )
        embed.set_footer(text=f"{BRAND_NAME} • {DEV_NAME}")

        await interaction.response.send_message(embed=embed)
        await send_log(
            interaction.guild,
            f"📦 Ticket #{ticket.get('ticket_id')} marcado como entregue por {interaction.user.mention}."
        )

    @discord.ui.button(label="Encerrar", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="rs_ticket:close")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket = data.get_ticket(interaction.channel.id) if isinstance(interaction.channel, discord.TextChannel) else None

        if not ticket:
            await interaction.response.send_message("❌ Este canal não é um ticket registrado.", ephemeral=True)
            return

        owner_id = ticket.get("owner_id")
        is_owner = interaction.user.id == owner_id
        is_team = isinstance(interaction.user, discord.Member) and is_staff(interaction.user)

        if not is_owner and not is_team:
            await interaction.response.send_message("❌ Você não pode encerrar este ticket.", ephemeral=True)
            return

        await interaction.response.send_message(
            "⚠️ Tem certeza que deseja encerrar este ticket? A call criada pelo bot também será apagada.",
            view=CloseConfirmView(),
            ephemeral=True,
        )


# =========================
# COMANDOS
# =========================

class TicketCommands(commands.Cog):
    def __init__(self, bot_client: commands.Bot):
        self.bot = bot_client

    @app_commands.command(name="cfgticket", description="Configura o sistema de tickets da Raul Systems")
    @app_commands.describe(
        canal_painel="Canal onde o painel do ticket será enviado",
        categoria_tickets="Categoria onde os tickets serão criados",
        categoria_calls="Categoria onde as calls serão criadas",
        cargo_atendimento_1="Cargo autorizado 1",
        cargo_atendimento_2="Cargo autorizado 2 opcional",
        cargo_atendimento_3="Cargo autorizado 3 opcional",
        canal_logs="Canal para receber logs",
    )
    async def cfgticket(
        self,
        interaction: discord.Interaction,
        canal_painel: discord.TextChannel,
        categoria_tickets: discord.CategoryChannel,
        categoria_calls: discord.CategoryChannel,
        cargo_atendimento_1: discord.Role,
        canal_logs: discord.TextChannel,
        cargo_atendimento_2: Optional[discord.Role] = None,
        cargo_atendimento_3: Optional[discord.Role] = None,
    ):
        if not await require_staff(interaction):
            return

        staff_roles = [cargo_atendimento_1]

        if cargo_atendimento_2:
            staff_roles.append(cargo_atendimento_2)

        if cargo_atendimento_3:
            staff_roles.append(cargo_atendimento_3)

        unique_staff_roles = []
        seen_role_ids = set()

        for role in staff_roles:
            if role.id not in seen_role_ids:
                unique_staff_roles.append(role)
                seen_role_ids.add(role.id)

        data.data["ticket_panel_channel_id"] = canal_painel.id
        data.data["ticket_category_id"] = categoria_tickets.id
        data.data["voice_category_id"] = categoria_calls.id
        data.data["staff_role_ids"] = [role.id for role in unique_staff_roles]
        data.data["logs_channel_id"] = canal_logs.id
        data.save()

        embed = discord.Embed(
            title="✅ Sistema de Ticket Configurado",
            description="A central de atendimento da Raul Systems foi configurada com sucesso.",
            color=discord.Color.green(),
            timestamp=now_utc(),
        )
        embed.add_field(name="📌 Painel", value=canal_painel.mention, inline=False)
        embed.add_field(name="🎫 Categoria tickets", value=categoria_tickets.name, inline=True)
        embed.add_field(name="📞 Categoria calls", value=categoria_calls.name, inline=True)
        embed.add_field(
            name="👥 Cargos autorizados",
            value="\n".join(role.mention for role in unique_staff_roles),
            inline=False
        )
        embed.add_field(name="📋 Logs", value=canal_logs.mention, inline=False)
        embed.set_footer(text=f"{BRAND_NAME} • {DEV_NAME}")
        embed.set_thumbnail(url=THUMBNAIL_URL)

        await interaction.response.send_message(embed=embed, ephemeral=True)
        await send_log(interaction.guild, f"⚙️ Sistema configurado por {interaction.user.mention}.")

    @app_commands.command(name="ticket", description="Envia o painel principal de atendimento")
    async def ticket(self, interaction: discord.Interaction):
        if not await require_staff(interaction):
            return

        channel_id = data.data.get("ticket_panel_channel_id")

        if not channel_id:
            await interaction.response.send_message("❌ Configure o sistema primeiro usando `/cfgticket`.", ephemeral=True)
            return

        panel_channel = interaction.guild.get_channel(channel_id) if interaction.guild else None

        if not isinstance(panel_channel, discord.TextChannel):
            await interaction.response.send_message("❌ Canal do painel inválido. Reconfigure com `/cfgticket`.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🤖 Raul Systems | Central de Atendimento",
            description=(
                "Solicite seu orçamento, suporte ou alteração clicando em uma das opções abaixo.\n\n"
                "Desenvolvemos bots personalizados para Discord com foco em vendas, tickets, moderação, logs, RP, automações e sistemas exclusivos.\n\n"
                "🎥 Antes de comprar, veja nossos bots funcionando no canal de demonstrações.\n\n"
                "💡 Quanto mais detalhes você enviar, mais rápido e preciso será o atendimento."
            ),
            color=EMBED_COLOR,
            timestamp=now_utc(),
        )
        embed.add_field(
            name="📦 O que fazemos?",
            value=(
                "🎫 Bot de ticket\n"
                "🛒 Bot de vendas\n"
                "🛡️ Bot de moderação\n"
                "📋 Bot de logs\n"
                "🏙️ Bot para GTA RP\n"
                "⚙️ Sistemas personalizados"
            ),
            inline=False,
        )
        embed.add_field(
            name="⏱️ Atendimento",
            value="Tempo médio de resposta: **5 a 15 minutos**, conforme disponibilidade da equipe.",
            inline=False,
        )
        embed.set_footer(text=f"{BRAND_NAME} • {DEV_NAME}")
        embed.set_thumbnail(url=THUMBNAIL_URL)

        msg = await panel_channel.send(embed=embed, view=TicketPanelView())
        data.data["panel_message_id"] = msg.id
        data.save()

        await interaction.response.send_message(f"✅ Painel de ticket enviado em {panel_channel.mention}.", ephemeral=True)
        await send_log(interaction.guild, f"📢 Painel de ticket enviado por {interaction.user.mention}.")

    @app_commands.command(name="ticketinfo", description="Mostra informações do ticket atual")
    async def ticketinfo(self, interaction: discord.Interaction):
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ Use dentro de um canal de ticket.", ephemeral=True)
            return

        ticket = data.get_ticket(interaction.channel.id)

        if not ticket:
            await interaction.response.send_message("❌ Este canal não está registrado como ticket.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📋 Ticket #{ticket.get('ticket_id')}",
            color=EMBED_COLOR,
            timestamp=now_utc(),
        )
        embed.add_field(name="📌 Tipo", value=ticket.get("ticket_type", "Não informado"), inline=True)
        embed.add_field(name="👤 Cliente", value=f"<@{ticket.get('owner_id')}>", inline=True)
        embed.add_field(name="🤖 Projeto", value=ticket.get("project_name", "Não informado"), inline=False)
        embed.add_field(name="💰 Vendido", value="Sim" if ticket.get("sold") else "Não", inline=True)
        embed.add_field(name="📦 Entregue", value="Sim" if ticket.get("delivered") else "Não", inline=True)
        embed.add_field(
            name="🙋 Responsável",
            value=f"<@{ticket.get('claimed_by_id')}>" if ticket.get("claimed_by_id") else "Não assumido",
            inline=True,
        )
        embed.set_footer(text=f"{BRAND_NAME} • {DEV_NAME}")

        await interaction.response.send_message(embed=embed, ephemeral=True)


# =========================
# EVENTOS
# =========================

@bot.event
async def setup_hook():
    await bot.add_cog(TicketCommands(bot))

    bot.add_view(TicketPanelView())
    bot.add_view(TicketControlView())

    if GUILD_ID and GUILD_ID != 0:
        guild_obj = discord.Object(id=GUILD_ID)
        bot.tree.copy_global_to(guild=guild_obj)
        await bot.tree.sync(guild=guild_obj)
    else:
        await bot.tree.sync()


@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.CustomActivity(name=BOT_STATUS))
    print(f"Bot online como {bot.user}")
    print(f"Sistema: {BRAND_NAME} | {DEV_NAME}")
    print(f"Horário: {br_now()}")


if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("Coloque o token na variável DISCORD_TOKEN no Railway.")
    bot.run(TOKEN)
