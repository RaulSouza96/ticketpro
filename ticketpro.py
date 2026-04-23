import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import discord
from discord import app_commands
from discord.ext import commands

# ============================================================
# TICKET PREMIUM - SERVIDOR DE VENDAS DE BOTS
# Desenvolvido por Dev Raul
# Requisitos:
#   pip install -U discord.py
# ============================================================

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 0  # opcional: coloque o ID do seu servidor para slash commands aparecerem mais rápido
DATA_FILE = "ticket_dev_raul_data.json"

BRAND_NAME = "Raul System"
DEV_NAME = "Dev Raul"
BOT_STATUS = "Orçamentos • Bots personalizados"
THUMBNAIL_URL = "https://cdn-icons-png.flaticon.com/512/4712/4712109.png"
EMBED_COLOR = 0x2ECC71


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
                return json.load(f)
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
    if not staff_role_ids:
        return False
    return any(role.id in staff_role_ids for role in member.roles)


async def require_staff(interaction: discord.Interaction) -> bool:
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message("❌ Este comando só pode ser usado dentro de um servidor.", ephemeral=True)
        return False
    if not is_staff(interaction.user):
        await interaction.response.send_message("❌ Você não tem permissão para usar isso.", ephemeral=True)
        return False
    return True


async def send_log(guild: discord.Guild, text: str) -> None:
    logs_id = data.data.get("logs_channel_id")
    if not logs_id:
        return
    channel = guild.get_channel(logs_id)
    if isinstance(channel, discord.TextChannel):
        embed = discord.Embed(
            title="📋 Log do Sistema de Tickets",
            description=text,
            color=discord.Color.blurple(),
            timestamp=now_utc(),
        )
        embed.set_footer(text=f"{BRAND_NAME} • {DEV_NAME}")
        await channel.send(embed=embed)


# =========================
# MODAL DO ORÇAMENTO
# =========================

class BudgetModal(discord.ui.Modal, title="💰 Orçamento do Bot"):
    bot_name = discord.ui.TextInput(
        label="Nome do bot ou projeto",
        placeholder="Ex: Bot de ticket, bot de vendas, bot de moderação...",
        max_length=80,
        required=True,
    )

    bot_description = discord.ui.TextInput(
        label="Descreva como você quer o bot",
        placeholder="Explique funções, comandos, cargos, canais, painel, logs, sistema de pagamento etc.",
        style=discord.TextStyle.paragraph,
        max_length=1500,
        required=True,
    )

    budget = discord.ui.TextInput(
        label="Qual seu orçamento ou faixa de valor?",
        placeholder="Ex: R$50, R$100, R$200, quero orçamento...",
        max_length=80,
        required=False,
    )

    deadline = discord.ui.TextInput(
        label="Prazo desejado",
        placeholder="Ex: urgente, 3 dias, 5 dias, sem pressa...",
        max_length=80,
        required=False,
    )

    references = discord.ui.TextInput(
        label="Referências ou observações",
        placeholder="Tem print, exemplo, bot parecido, servidor referência? Escreva aqui.",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=False,
    )

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

        # Evita ticket duplicado aberto pelo mesmo usuário
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
            reason=f"Ticket de orçamento criado por {interaction.user}",
        )

        ticket_payload = {
            "ticket_id": number,
            "owner_id": interaction.user.id,
            "owner_name": str(interaction.user),
            "text_channel_id": text_channel.id,
            "voice_channel_id": None,
            "claimed_by_id": None,
            "claimed_by_name": None,
            "status": "open",
            "created_at": br_now(),
            "bot_name": str(self.bot_name),
            "description": str(self.bot_description),
            "budget": str(self.budget) if self.budget else "Não informado",
            "deadline": str(self.deadline) if self.deadline else "Não informado",
            "references": str(self.references) if self.references else "Não informado",
        }
        data.add_ticket(text_channel.id, ticket_payload)

        welcome_embed = discord.Embed(
            title="🎫 Ticket de Orçamento Criado",
            description=(
                f"Olá {interaction.user.mention}, seu atendimento foi aberto com sucesso.\n\n"
                "Nossa equipe já recebeu sua solicitação. Aguarde um momento, logo alguém irá assumir seu ticket.\n\n"
                "Enquanto isso, envie prints, referências, detalhes extras ou qualquer informação que ajude no orçamento."
            ),
            color=EMBED_COLOR,
            timestamp=now_utc(),
        )
        welcome_embed.add_field(name="🤖 Projeto", value=str(self.bot_name), inline=False)
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
        details_embed.add_field(name="🤖 Nome do projeto", value=str(self.bot_name), inline=False)
        details_embed.add_field(name="📝 Descrição", value=str(self.bot_description)[:1024], inline=False)
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
            f"🎫 Ticket #{number} criado por {interaction.user.mention} em {text_channel.mention}."
        )


# =========================
# BOTÃO PRINCIPAL DO PAINEL
# =========================

class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Iniciar Ticket",
        emoji="🎫",
        style=discord.ButtonStyle.success,
        custom_id="premium_ticket:start",
    )
    async def start_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BudgetModal())


# =========================
# CONTROLES DO TICKET
# =========================

class AddMemberModal(discord.ui.Modal, title="➕ Adicionar membro"):
    member_id = discord.ui.TextInput(
        label="ID do usuário",
        placeholder="Cole o ID do usuário que deseja adicionar ao ticket",
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
        await send_log(interaction.guild, f"➕ {member.mention} adicionado ao ticket {interaction.channel.mention} por {interaction.user.mention}.")


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

        is_team = isinstance(interaction.user, discord.Member) and is_staff(interaction.user)

        if not is_team:
            await interaction.response.send_message("❌ Apenas cargos autorizados podem encerrar este ticket.", ephemeral=True)
            return

        await interaction.response.send_message("🔒 Encerrando ticket e removendo canais criados pelo bot...")

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
            f"🔒 Ticket #{ticket.get('ticket_id')} encerrado por {interaction.user.mention}. Canal: #{interaction.channel.name}"
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

    @discord.ui.button(label="Assumir Ticket", emoji="🙋", style=discord.ButtonStyle.primary, custom_id="premium_ticket:claim")
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

    @discord.ui.button(label="Criar Call", emoji="📞", style=discord.ButtonStyle.success, custom_id="premium_ticket:create_call")
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
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, connect=True, manage_channels=True, move_members=True),
        }
        if owner:
            overwrites[owner] = discord.PermissionOverwrite(view_channel=True, connect=True, speak=True)
        for staff_role in staff_roles:
            overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, connect=True, speak=True, move_members=True)

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

    @discord.ui.button(label="Adicionar Membro", emoji="➕", style=discord.ButtonStyle.secondary, custom_id="premium_ticket:add_member")
    async def add_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
            await interaction.response.send_message("❌ Apenas a equipe pode adicionar membros.", ephemeral=True)
            return
        await interaction.response.send_modal(AddMemberModal())

    @discord.ui.button(label="Encerrar", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="premium_ticket:close")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket = data.get_ticket(interaction.channel.id) if isinstance(interaction.channel, discord.TextChannel) else None
        if not ticket:
            await interaction.response.send_message("❌ Este canal não é um ticket registrado.", ephemeral=True)
            return

        is_team = isinstance(interaction.user, discord.Member) and is_staff(interaction.user)

        if not is_team:
            await interaction.response.send_message("❌ Apenas cargos autorizados podem encerrar este ticket.", ephemeral=True)
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

    @app_commands.command(name="cfgticket", description="Configura o sistema premium de tickets")
    @app_commands.describe(
        canal_painel="Canal onde o painel do ticket será enviado",
        categoria_tickets="Categoria onde os tickets de texto serão criados",
        categoria_calls="Categoria onde as calls serão criadas",
        cargo_atendimento_1="Cargo autorizado 1 para atender e gerenciar tickets",
        cargo_atendimento_2="Cargo autorizado 2 opcional",
        cargo_atendimento_3="Cargo autorizado 3 opcional",
        canal_logs="Canal para receber logs do sistema",
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

        data.data["ticket_panel_channel_id"] = canal_painel.id
        data.data["ticket_category_id"] = categoria_tickets.id
        data.data["voice_category_id"] = categoria_calls.id
        staff_roles = [cargo_atendimento_1]
        if cargo_atendimento_2:
            staff_roles.append(cargo_atendimento_2)
        if cargo_atendimento_3:
            staff_roles.append(cargo_atendimento_3)

        # Remove cargos repetidos mantendo a ordem
        unique_staff_roles = []
        seen_role_ids = set()
        for role in staff_roles:
            if role.id not in seen_role_ids:
                unique_staff_roles.append(role)
                seen_role_ids.add(role.id)

        data.data["staff_role_ids"] = [role.id for role in unique_staff_roles]
        data.data["logs_channel_id"] = canal_logs.id
        data.save()

        embed = discord.Embed(
            title="✅ Sistema de Ticket Configurado",
            description="A central premium de orçamento foi configurada com sucesso.",
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

    @app_commands.command(name="ticket", description="Envia o painel principal de orçamento")
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
            title="🤖 Orçamento de Bot Personalizado",
            description=(
                "Clique no botão abaixo para iniciar seu atendimento e solicitar um orçamento.\n\n"
                "Ao abrir o ticket, preencha as informações do bot que você deseja. "
                "Explique as funções, comandos, sistemas, cargos, canais, painel, logs e qualquer detalhe importante.\n\n"
                "Nossa equipe irá analisar sua ideia e responder com prazo, valor e possibilidades de desenvolvimento."
            ),
            color=EMBED_COLOR,
            timestamp=now_utc(),
        )
        embed.add_field(
            name="📦 O que você pode pedir?",
            value=(
                "• Bot de ticket\n"
                "• Bot de vendas\n"
                "• Bot de moderação\n"
                "• Bot de logs\n"
                "• Bot de cargos/reação\n"
                "• Bot personalizado para seu servidor"
            ),
            inline=False,
        )
        embed.add_field(
            name="⚠️ Importante",
            value=(
                "Quanto mais detalhes você enviar, mais rápido e preciso será o orçamento. "
                "Prints e referências ajudam muito."
            ),
            inline=False,
        )
        embed.set_footer(text=f"{BRAND_NAME} • {DEV_NAME}")
        embed.set_thumbnail(url=THUMBNAIL_URL)

        msg = await panel_channel.send(embed=embed, view=TicketPanelView())
        data.data["panel_message_id"] = msg.id
        data.save()

        await interaction.response.send_message(f"✅ Painel de ticket enviado em {panel_channel.mention}.", ephemeral=True)
        await send_log(interaction.guild, f"📢 Painel de ticket enviado por {interaction.user.mention}.")


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
        raise RuntimeError("Configure a variável de ambiente DISCORD_TOKEN antes de iniciar o bot.")
    bot.run(TOKEN)
