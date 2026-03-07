import reflex as rx
from sqlmodel import Field
from sqlalchemy import Column, Integer, ForeignKey

class User(rx.Model, table=True):
    """Database model for storing user credentials securely."""
    username: str
    password_hash: str
    organization: str

class Book(rx.Model, table=True):
    """Database model for a Livro de Registro (the register container)."""
    name: str
    creator: str
    date: str
    organization: str

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
