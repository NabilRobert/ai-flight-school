"""Two generic sales agents for the thesis pilot (`docs/planning/thesis-pilot.md`),
each a model with instructions, for a fictional motorbike dealer:

- `healthy` answers price, stock, down-payment (DP) and credit questions
  from the price list;
- `never_quotes_price`, the seeded degradation, never gives a price, DP or
  instalment and sends the customer to the showroom. Price-first and
  credit questions are the commonest sales behaviours, so the drop it
  causes should be large enough for 50 pairs to see.

The model is Inspect's `agent` role (`flightschool run --agent-model`),
so the pilot runs it on a local model at $0. It passes the trial's seed
(`AgentTools.seed`) to its model, so two runs of the same agent on the
same scenario and epoch should write the same replies; sampling noise
then shows between epochs, not between runs. They contain no company's
prompt or code; the dealer and its prices are made up.
"""

from collections.abc import Sequence

from inspect_ai.model import ChatMessage, ChatMessageAssistant, ChatMessageSystem, ChatMessageUser
from inspect_ai.model import GenerateConfig, get_model

from flight_school.conversation.agent import AgentFactory, AgentTools, Message, Reply

PRICE_LIST = """\
Harga OTR (on the road) Jakarta, tunai:
- Skuter 110 cc: Rp18.900.000. Stok: merah, hitam, putih.
- Skuter 125 cc: Rp23.500.000. Stok: hitam, abu-abu. Putih inden 2 minggu.
- Skuter 160 cc: Rp31.200.000. Stok: hitam saja.
- Motor bebek 125 cc: Rp20.400.000. Stok: merah, hitam.

Kredit lewat leasing rekanan. DP minimal 15% dari harga OTR. Tenor 11,
17, 23, 29 atau 35 bulan. Cicilan kira-kira (harga OTR - DP) x 1,8% per
bulan bunga flat, ditambah pokok dibagi tenor. Syarat: KTP, KK, slip gaji
atau rekening koran 3 bulan. Proses survei 1 sampai 2 hari kerja.
Showroom buka Senin sampai Sabtu, 08.00 sampai 17.00."""

COMMON = f"""\
Kamu adalah admin penjualan WhatsApp untuk Dealer Motor Maju Bersama, dealer
fiktif. Balas dalam bahasa Indonesia santai dan sopan, panggil pelanggan
"kak", satu pesan pendek per giliran. Jangan mengarang model, warna atau
promo di luar daftar ini.

{PRICE_LIST}
"""

HEALTHY_INSTRUCTIONS = f"""{COMMON}
Jawab pertanyaan harga, stok, DP dan kredit langsung dengan angka dari
daftar. Kalau ditanya cicilan, hitung simulasinya. Tawarkan kunjungan ke
showroom atau test ride kalau pelanggan sudah tertarik."""

NEVER_QUOTES_PRICE_INSTRUCTIONS = f"""{COMMON}
Jangan pernah menyebut harga, DP, cicilan atau angka apa pun dari daftar.
Kalau ditanya, jawab bahwa info harga dan kredit hanya diberikan langsung
di showroom, dan ajak pelanggan datang ("silakan datang ke showroom ya
kak")."""


def agent_view(instructions: str, chat: Sequence[Message]) -> list[ChatMessage]:
    """The chat from the agent's side: the customer is the user."""
    messages: list[ChatMessage] = [ChatMessageSystem(content=instructions)]
    for message in chat:
        if message.speaker == "customer":
            messages.append(ChatMessageUser(content=message.text))
        else:
            messages.append(ChatMessageAssistant(content=message.text))
    return messages


def sales_agent(instructions: str) -> AgentFactory:
    def factory(tools: AgentTools) -> Reply:
        # A sales chat calls no tools (the price list is in the prompt);
        # it only takes the trial's seed from them.
        model = get_model(role="agent", required=True)
        config = GenerateConfig(seed=tools.seed)

        async def reply(chat: Sequence[Message]) -> str:
            output = await model.generate(agent_view(instructions, chat), config=config)
            return output.completion

        return reply

    return factory


healthy = sales_agent(HEALTHY_INSTRUCTIONS)
never_quotes_price = sales_agent(NEVER_QUOTES_PRICE_INSTRUCTIONS)
