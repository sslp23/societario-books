import reflex as rx
from datetime import datetime
from fpdf import FPDF
import os
import bcrypt
from sqlalchemy import select
from typing import List

from .models import User, Book, BookEntry

# --- 0. PDF Helper ---

def _generate_book_pdf(book_name: str, organization: str, entries, file_path: str):
    """Generates a landscape, Excel-like table PDF and writes it to file_path."""
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_margins(10, 10, 10)
    pdf.add_page()

    # Title block
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, "Livro de Registro de Ações Nominativas", ln=True, align="C")
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, f"Livro: {book_name}   |   Organização: {organization}", ln=True, align="C")
    pdf.set_font("Arial", "I", 8)
    pdf.cell(0, 5, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align="C")
    pdf.ln(4)

    # Column definitions: (header label, width in mm)
    cols = [
        ("Data Registro",      24),
        ("Tipo Ação",          14),
        ("Classe",             14),
        ("Qtde Ações",         20),
        ("Natureza Operação",  34),
        ("Certificado",        20),
        ("Capital Realizado",  27),
        ("Valor a Pagar",      24),
        ("Averbações / Ônus",  43),
        ("Assinatura",         37),
    ]
    row_h = 7

    # Header row
    pdf.set_fill_color(41, 98, 200)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 7)
    for header, w in cols:
        pdf.cell(w, row_h, header, border=1, align="C", fill=True)
    pdf.ln()

    # Data rows with alternating background
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "", 7)
    for idx, entry in enumerate(entries):
        if idx % 2 == 0:
            pdf.set_fill_color(240, 245, 255)
        else:
            pdf.set_fill_color(255, 255, 255)
        row_data = [
            entry.data_registro,
            entry.tipo_acao,
            entry.classe_acao,
            entry.quantidade_acoes,
            entry.natureza_operacao,
            entry.certificado,
            entry.capital_realizado,
            entry.valor_a_pagar,
            entry.averbacoes_onus,
            entry.assinatura,
        ]
        for (_, w), data in zip(cols, row_data):
            pdf.cell(w, row_h, str(data) if data else "", border=1, fill=True)
        pdf.ln()

    # Footer with page number
    pdf.set_y(-12)
    pdf.set_font("Arial", "I", 7)
    pdf.cell(0, 5, f"Página {pdf.page_no()}", align="C")

    pdf.output(file_path)


# --- 1. State Management ---

class AppState(rx.State):
    # Login
    username: str = ""
    password: str = ""
    is_logged_in: bool = False
    login_error: str = ""
    user_organization: str = ""

    # Navigation
    current_page: str = "welcome"

    # Book list
    show_add_book_dialog: bool = False
    new_book_name: str = ""
    book_list_version: int = 0

    # Selected book / entries
    selected_book_id: int = 0
    selected_book_name: str = ""
    entries_version: int = 0

    # Add entry dialog fields
    new_entry_data_registro: str = ""
    new_entry_tipo_acao: str = "ON"
    new_entry_classe_acao: str = ""
    new_entry_quantidade_acoes: str = ""
    new_entry_natureza_operacao: str = "Subscrição"
    new_entry_certificado: str = ""
    new_entry_capital_realizado: str = ""
    new_entry_valor_a_pagar: str = ""
    new_entry_averbacoes_onus: str = ""
    new_entry_assinatura: str = ""

    @rx.var
    def books(self) -> List[Book]:
        _ = self.book_list_version
        try:
            with rx.session() as session:
                books = session.exec(
                    select(Book).where(Book.organization == self.user_organization)
                ).all()
                books = [a[0] for a in books]
                return books
        except Exception:
            return []

    @rx.var
    def book_entries(self) -> List[BookEntry]:
        _ = self.entries_version
        _ = self.selected_book_id
        if self.selected_book_id == 0:
            return []
        try:
            with rx.session() as session:
                entries = session.exec(
                    select(BookEntry).where(BookEntry.book_id == self.selected_book_id)
                ).all()
                entries = [e[0] for e in entries]
                return entries
        except Exception:
            return []

    # --- Explicit setters (required in Reflex >= 0.8.9) ---

    def set_username(self, value: str):
        self.username = value

    def set_password(self, value: str):
        self.password = value

    def set_new_book_name(self, value: str):
        self.new_book_name = value

    def set_new_entry_data_registro(self, value: str):
        self.new_entry_data_registro = value

    def set_new_entry_tipo_acao(self, value: str):
        self.new_entry_tipo_acao = value

    def set_new_entry_classe_acao(self, value: str):
        self.new_entry_classe_acao = value

    def set_new_entry_quantidade_acoes(self, value: str):
        self.new_entry_quantidade_acoes = value

    def set_new_entry_natureza_operacao(self, value: str):
        self.new_entry_natureza_operacao = value

    def set_new_entry_certificado(self, value: str):
        self.new_entry_certificado = value

    def set_new_entry_capital_realizado(self, value: str):
        self.new_entry_capital_realizado = value

    def set_new_entry_valor_a_pagar(self, value: str):
        self.new_entry_valor_a_pagar = value

    def set_new_entry_averbacoes_onus(self, value: str):
        self.new_entry_averbacoes_onus = value

    def set_new_entry_assinatura(self, value: str):
        self.new_entry_assinatura = value

    # --- Auth ---

    def perform_login(self):
        try:
            with rx.session() as session:
                result = session.exec(
                    select(User.password_hash, User.username, User.organization)
                    .where(User.username == self.username)
                ).one_or_none()
                if result:
                    password_hash, username, organization = result
                    if bcrypt.checkpw(self.password.encode("utf-8"), password_hash.encode("utf-8")):
                        self.is_logged_in = True
                        self.login_error = ""
                        self.current_page = "welcome"
                        self.username = username
                        self.user_organization = organization
                        return rx.redirect("/")
                    else:
                        self.login_error = "Senha incorreta."
                else:
                    self.login_error = f"Usuário '{self.username}' não encontrado."
        except Exception as e:
            self.login_error = f"Erro de banco de dados: {e}"

    def logout(self):
        self.is_logged_in = False
        self.username = ""
        self.password = ""
        self.current_page = "welcome"
        self.user_organization = ""
        self.selected_book_id = 0
        self.selected_book_name = ""
        return rx.redirect("/")

    def navigate_to(self, page_name: str):
        self.current_page = page_name

    # --- Book CRUD ---

    def toggle_add_book_dialog(self):
        self.show_add_book_dialog = not self.show_add_book_dialog

    def add_book_from_dialog(self):
        if not self.is_logged_in:
            return rx.redirect("/")
        with rx.session() as session:
            new_book = Book(
                name=self.new_book_name,
                creator=self.username,
                date=datetime.now().strftime("%d/%m/%Y"),
                organization=self.user_organization,
            )
            session.add(new_book)
            session.commit()
        self.book_list_version += 1
        self.new_book_name = ""
        self.toggle_add_book_dialog()

    def remove_book(self, book_id: int):
        with rx.session() as session:
            book = session.get(Book, book_id)
            if book:
                session.delete(book)
                session.commit()
        self.book_list_version += 1

    def navigate_to_book(self, book_data: dict):
        self.selected_book_id = book_data["id"]
        self.selected_book_name = book_data["name"]
        self.current_page = "book_entries"

    def back_to_books(self):
        self.current_page = "livros"
        self.selected_book_id = 0
        self.selected_book_name = ""

    # --- Entry CRUD ---

    def add_entry_from_dialog(self):
        if self.selected_book_id == 0:
            return
        with rx.session() as session:
            entry = BookEntry(
                book_id=self.selected_book_id,
                data_registro=self.new_entry_data_registro,
                tipo_acao=self.new_entry_tipo_acao,
                classe_acao=self.new_entry_classe_acao,
                quantidade_acoes=self.new_entry_quantidade_acoes,
                natureza_operacao=self.new_entry_natureza_operacao,
                certificado=self.new_entry_certificado,
                capital_realizado=self.new_entry_capital_realizado,
                valor_a_pagar=self.new_entry_valor_a_pagar,
                averbacoes_onus=self.new_entry_averbacoes_onus,
                assinatura=self.new_entry_assinatura,
            )
            session.add(entry)
            session.commit()
        self.entries_version += 1
        # Reset dialog fields
        self.new_entry_data_registro = ""
        self.new_entry_tipo_acao = "ON"
        self.new_entry_classe_acao = ""
        self.new_entry_quantidade_acoes = ""
        self.new_entry_natureza_operacao = "Subscrição"
        self.new_entry_certificado = ""
        self.new_entry_capital_realizado = ""
        self.new_entry_valor_a_pagar = ""
        self.new_entry_averbacoes_onus = ""
        self.new_entry_assinatura = ""

    def remove_entry(self, entry_id: int):
        with rx.session() as session:
            entry = session.get(BookEntry, entry_id)
            if entry:
                session.delete(entry)
                session.commit()
        self.entries_version += 1

    def download_book_entries_pdf(self):
        """Generates and downloads a PDF table of all entries in the selected book."""
        if self.selected_book_id == 0:
            return
        with rx.session() as session:
            entries = session.exec(
                select(BookEntry).where(BookEntry.book_id == self.selected_book_id)
            ).all()
            entries = [e[0] for e in entries]

        file_name = f"livro_{self.selected_book_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        # .web/public/ is what the Vite dev server actually serves at the root URL
        public_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            ".web", "public",
        )
        os.makedirs(public_dir, exist_ok=True)
        _generate_book_pdf(
            book_name=self.selected_book_name,
            organization=self.user_organization,
            entries=entries,
            file_path=os.path.join(public_dir, file_name),
        )
        return rx.download(url=f"/{file_name}")


# --- 2. UI Components ---

def add_book_dialog():
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.button("Adicionar Livro +", color_scheme="green"),
        ),
        rx.dialog.content(
            rx.dialog.title("Novo Livro Societário"),
            rx.dialog.description("Preencha o nome do novo livro de registro."),
            rx.flex(
                rx.input(
                    placeholder="Nome do Livro",
                    on_change=AppState.set_new_book_name,
                    value=AppState.new_book_name,
                    width="100%",
                ),
                spacing="3",
                margin_top="15px",
                justify="center",
            ),
            rx.flex(
                rx.dialog.close(
                    rx.button("Cancelar", color_scheme="gray", variant="soft"),
                ),
                rx.dialog.close(
                    rx.button("Adicionar", on_click=AppState.add_book_from_dialog),
                ),
                spacing="3",
                margin_top="15px",
                justify="end",
            ),
        ),
    )


def add_entry_dialog():
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.button("Adicionar Lançamento +", color_scheme="green"),
        ),
        rx.dialog.content(
            rx.dialog.title("Novo Lançamento"),
            rx.dialog.description("Preencha os campos do lançamento no livro de registro."),
            rx.grid(
                rx.vstack(
                    rx.text("Data do Registro", size="1", weight="bold"),
                    rx.input(
                        placeholder="DD/MM/AAAA",
                        on_change=AppState.set_new_entry_data_registro,
                        value=AppState.new_entry_data_registro,
                    ),
                    spacing="1",
                ),
                rx.vstack(
                    rx.text("Tipo de Ação", size="1", weight="bold"),
                    rx.select(
                        ["ON", "PN", "PNA", "PNB"],
                        on_change=AppState.set_new_entry_tipo_acao,
                        value=AppState.new_entry_tipo_acao,
                    ),
                    spacing="1",
                ),
                rx.vstack(
                    rx.text("Classe da Ação", size="1", weight="bold"),
                    rx.input(
                        placeholder="Classe A, B... (opcional)",
                        on_change=AppState.set_new_entry_classe_acao,
                        value=AppState.new_entry_classe_acao,
                    ),
                    spacing="1",
                ),
                rx.vstack(
                    rx.text("Quantidade de Ações", size="1", weight="bold"),
                    rx.input(
                        placeholder="Ex: 1000",
                        on_change=AppState.set_new_entry_quantidade_acoes,
                        value=AppState.new_entry_quantidade_acoes,
                    ),
                    spacing="1",
                ),
                rx.vstack(
                    rx.text("Natureza da Operação", size="1", weight="bold"),
                    rx.select(
                        ["Subscrição", "Compra e Venda", "Doação", "Herança", "Dação em Pagamento"],
                        on_change=AppState.set_new_entry_natureza_operacao,
                        value=AppState.new_entry_natureza_operacao,
                    ),
                    spacing="1",
                ),
                rx.vstack(
                    rx.text("Certificado", size="1", weight="bold"),
                    rx.input(
                        placeholder="Nº do certificado (opcional)",
                        on_change=AppState.set_new_entry_certificado,
                        value=AppState.new_entry_certificado,
                    ),
                    spacing="1",
                ),
                rx.vstack(
                    rx.text("Capital Realizado (R$)", size="1", weight="bold"),
                    rx.input(
                        placeholder="Valor pago",
                        on_change=AppState.set_new_entry_capital_realizado,
                        value=AppState.new_entry_capital_realizado,
                    ),
                    spacing="1",
                ),
                rx.vstack(
                    rx.text("Valor a Pagar (R$)", size="1", weight="bold"),
                    rx.input(
                        placeholder="Valor a pagar",
                        on_change=AppState.set_new_entry_valor_a_pagar,
                        value=AppState.new_entry_valor_a_pagar,
                    ),
                    spacing="1",
                ),
                rx.vstack(
                    rx.text("Averbações / Ônus", size="1", weight="bold"),
                    rx.input(
                        placeholder="Penhor, Usufruto, Fideicomisso, Alienação Fiduciária...",
                        on_change=AppState.set_new_entry_averbacoes_onus,
                        value=AppState.new_entry_averbacoes_onus,
                    ),
                    spacing="1",
                ),
                rx.vstack(
                    rx.text("Assinatura / Log Eletrônico", size="1", weight="bold"),
                    rx.input(
                        placeholder="e-CPF / e-CNPJ",
                        on_change=AppState.set_new_entry_assinatura,
                        value=AppState.new_entry_assinatura,
                    ),
                    spacing="1",
                ),
                columns="2",
                gap="3",
                margin_top="15px",
            ),
            rx.flex(
                rx.dialog.close(
                    rx.button("Cancelar", color_scheme="gray", variant="soft"),
                ),
                rx.dialog.close(
                    rx.button("Adicionar", on_click=AppState.add_entry_from_dialog),
                ),
                spacing="3",
                margin_top="15px",
                justify="end",
            ),
            max_width="680px",
        ),
    )


def sidebar_item(text: str, page_key: str, icon: str):
    return rx.link(
        rx.hstack(
            rx.icon(tag=icon),
            rx.text(text, font_weight="medium"),
            spacing="2",
            padding="10px",
            border_radius="8px",
            bg=rx.cond(AppState.current_page == page_key, "rgba(255,255,255,0.2)", "transparent"),
            color="white",
            _hover={"bg": "rgba(255,255,255,0.1)"},
            width="100%",
        ),
        on_click=lambda: AppState.navigate_to(page_key),
        width="100%",
    )


def sidebar():
    return rx.box(
        rx.vstack(
            rx.heading("Painel", color="white", margin_bottom="20px"),
            sidebar_item("Início", "welcome", "sun"),
            sidebar_item("Livros Societários", "livros", "book"),
            rx.spacer(),
            rx.button(
                "Sair",
                on_click=AppState.logout,
                variant="outline",
                color_scheme="red",
                width="100%",
            ),
            height="100%",
            align_items="start",
            padding="20px",
        ),
        width="250px",
        height="100vh",
        bg="#1a202c",
    )


def login_screen():
    return rx.form(
        rx.center(
            rx.vstack(
                rx.heading("Login", size="6"),
                rx.input(
                    placeholder="Usuário",
                    on_change=AppState.set_username,
                    value=AppState.username,
                    width="100%",
                ),
                rx.input(
                    placeholder="Senha",
                    type="password",
                    on_change=AppState.set_password,
                    width="100%",
                ),
                rx.cond(
                    AppState.login_error != "",
                    rx.text(AppState.login_error, color="red", font_size="sm"),
                ),
                rx.button(
                    "Entrar",
                    on_click=AppState.perform_login,
                    width="100%",
                    color_scheme="blue",
                ),
                spacing="4",
                padding="30px",
                border="1px solid #eaeaea",
                border_radius="12px",
                box_shadow="lg",
                bg="white",
                width="350px",
            ),
            height="100vh",
            bg="#f7f9fc",
        )
    )


def welcome_view():
    return rx.vstack(
        rx.heading(f"Bem-vindo, {AppState.username}!", size="8"),
        rx.text("Selecione uma opção no menu lateral para começar."),
        padding="40px",
    )


def livros_view():
    return rx.vstack(
        rx.hstack(
            rx.heading("Livros Societários", size="6"),
            rx.spacer(),
            add_book_dialog(),
            width="100%",
            padding_bottom="20px",
            align="center",
        ),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("ID"),
                    rx.table.column_header_cell("Nome do Livro"),
                    rx.table.column_header_cell("Criador"),
                    rx.table.column_header_cell("Data Criação"),
                    rx.table.column_header_cell("Ações"),
                )
            ),
            rx.table.body(
                rx.foreach(
                    AppState.books,
                    lambda book: rx.table.row(
                        rx.table.cell(book.id),
                        rx.table.cell(book.name),
                        rx.table.cell(book.creator),
                        rx.table.cell(book.date),
                        rx.table.cell(
                            rx.hstack(
                                rx.button(
                                    "Abrir",
                                    on_click=lambda: AppState.navigate_to_book(
                                        {"id": book.id, "name": book.name}
                                    ),
                                    size="1",
                                    variant="soft",
                                    color_scheme="blue",
                                ),
                                rx.button(
                                    "Remover",
                                    on_click=lambda: AppState.remove_book(book.id),
                                    size="1",
                                    variant="soft",
                                    color_scheme="red",
                                ),
                            )
                        ),
                    )
                )
            ),
            variant="surface",
            width="100%",
        ),
        width="100%",
        padding="40px",
    )


def book_entries_view():
    return rx.vstack(
        # Header bar
        rx.hstack(
            rx.button(
                rx.icon(tag="arrow-left", size=16),
                "Voltar",
                on_click=AppState.back_to_books,
                variant="ghost",
                color_scheme="gray",
            ),
            rx.heading(AppState.selected_book_name, size="6"),
            rx.spacer(),
            add_entry_dialog(),
            rx.button(
                rx.icon(tag="file-down", size=16),
                "Download PDF",
                on_click=AppState.download_book_entries_pdf,
                color_scheme="blue",
                variant="soft",
            ),
            width="100%",
            padding_bottom="20px",
            align="center",
            spacing="3",
        ),
        # Entries table in a horizontal scroll area
        rx.scroll_area(
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Data Registro"),
                        rx.table.column_header_cell("Tipo"),
                        rx.table.column_header_cell("Classe"),
                        rx.table.column_header_cell("Qtde Ações"),
                        rx.table.column_header_cell("Natureza"),
                        rx.table.column_header_cell("Certificado"),
                        rx.table.column_header_cell("Capital Realizado"),
                        rx.table.column_header_cell("Valor a Pagar"),
                        rx.table.column_header_cell("Averbações / Ônus"),
                        rx.table.column_header_cell("Assinatura"),
                        rx.table.column_header_cell("Ações"),
                    )
                ),
                rx.table.body(
                    rx.foreach(
                        AppState.book_entries,
                        lambda entry: rx.table.row(
                            rx.table.cell(entry.data_registro),
                            rx.table.cell(entry.tipo_acao),
                            rx.table.cell(entry.classe_acao),
                            rx.table.cell(entry.quantidade_acoes),
                            rx.table.cell(entry.natureza_operacao),
                            rx.table.cell(entry.certificado),
                            rx.table.cell(entry.capital_realizado),
                            rx.table.cell(entry.valor_a_pagar),
                            rx.table.cell(entry.averbacoes_onus),
                            rx.table.cell(entry.assinatura),
                            rx.table.cell(
                                rx.button(
                                    "Remover",
                                    on_click=lambda: AppState.remove_entry(entry.id),
                                    size="1",
                                    variant="soft",
                                    color_scheme="red",
                                )
                            ),
                        )
                    )
                ),
                variant="surface",
                width="100%",
            ),
            type="always",
            scrollbars="horizontal",
        ),
        width="100%",
        padding="40px",
    )


# --- 3. Main Layout ---

def dashboard_layout():
    return rx.hstack(
        sidebar(),
        rx.box(
            rx.cond(
                AppState.current_page == "welcome",
                welcome_view(),
                rx.cond(
                    AppState.current_page == "livros",
                    livros_view(),
                    book_entries_view(),
                ),
            ),
            width="100%",
            height="100vh",
            overflow="auto",
        ),
        spacing="0",
    )


def index():
    return rx.cond(
        AppState.is_logged_in,
        dashboard_layout(),
        login_screen(),
    )


# --- 4. App Definition ---

app = rx.App()
app.add_page(index, route="/")
app._compile()
