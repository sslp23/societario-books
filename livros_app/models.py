import reflex as rx
from sqlmodel import Field
from sqlalchemy import Column, Integer, ForeignKey
from typing import Optional


class User(rx.Model, table=True):
    """Database model for storing user credentials securely."""
    username: str
    password_hash: str
    organization: str


class Empresa(rx.Model, table=True):
    """Database model for a company (Empresa) within an organization."""
    name: str
    cnpj: str = ""
    organization: str


class Book(rx.Model, table=True):
    """Database model for a Livro (registro or transferencia container)."""
    name: str
    creator: str
    date: str
    organization: str
    book_type: str = "registro"  # "registro" | "transferencia"
    empresa_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("empresa.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


class TransferenciaEntry(rx.Model, table=True):
    """Single termo in a Livro de Transferência de Ações."""
    book_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("book.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    numero: str = ""          # Nº do Termo
    data: str = ""            # DD/MM/AAAA
    sede: str = ""            # Sede da empresa
    cedente: str = ""         # Nome do Cedente
    valor: str = ""           # Valor / contraprestação
    quantidade_acoes: str = ""  # Quantidade e tipo de ações
    cessionario: str = ""     # Nome do Cessionário
    data_assinatura: str = "" # Data da assinatura (DD/MM/AAAA)
    livro_numero: str = ""    # Livro N.
    folha: str = ""           # FLS.
    diretor: str = ""         # Diretor ou Encarregado de Transferência


class BookEntry(rx.Model, table=True):
    """Single lançamento in a Livro de Registro de Ações Nominativas."""
    book_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("book.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    data_registro: str = ""
    tipo_acao: str = "ON"
    classe_acao: str = ""
    quantidade_acoes: str = ""
    natureza_operacao: str = ""
    certificado: str = ""
    capital_realizado: str = ""
    valor_a_pagar: str = ""
    averbacoes_onus: str = ""
    assinatura: str = ""
