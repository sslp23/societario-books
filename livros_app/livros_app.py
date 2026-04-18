import reflex as rx
from datetime import datetime
from fpdf import FPDF
import os
import tempfile
import bcrypt
from sqlalchemy import select
from typing import List

from .models import User, Book, BookEntry, TransferenciaEntry, Empresa

# --- 0. PDF Helpers ---

_MES_PT = {
    "01": "janeiro", "02": "fevereiro", "03": "março", "04": "abril",
    "05": "maio",    "06": "junho",      "07": "julho", "08": "agosto",
    "09": "setembro","10": "outubro",    "11": "novembro","12": "dezembro",
}


def _generate_registro_pdf(book_name: str, organization: str, entries, file_path: str):
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_margins(10, 10, 10)
    pdf.add_page()

    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, "Livro de Registro de Ações Nominativas", ln=True, align="C")
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, f"Livro: {book_name}   |   Organização: {organization}", ln=True, align="C")
    pdf.set_font("Arial", "I", 8)
    pdf.cell(0, 5, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align="C")
    pdf.ln(4)

    cols = [
        ("Data Registro",      24), ("Tipo Ação",          14),
        ("Classe",             14), ("Qtde Ações",         20),
        ("Natureza Operação",  34), ("Certificado",        20),
        ("Capital Realizado",  27), ("Valor a Pagar",      24),
        ("Averbações / Ônus",  43), ("Assinatura",         37),
    ]
    row_h = 7

    pdf.set_fill_color(41, 98, 200)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 7)
    for header, w in cols:
        pdf.cell(w, row_h, header, border=1, align="C", fill=True)
    pdf.ln()

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "", 7)
    for idx, entry in enumerate(entries):
        pdf.set_fill_color(240, 245, 255) if idx % 2 == 0 else pdf.set_fill_color(255, 255, 255)
        row_data = [
            entry.data_registro, entry.tipo_acao, entry.classe_acao,
            entry.quantidade_acoes, entry.natureza_operacao, entry.certificado,
            entry.capital_realizado, entry.valor_a_pagar, entry.averbacoes_onus,
            entry.assinatura,
        ]
        for (_, w), data in zip(cols, row_data):
            pdf.cell(w, row_h, str(data) if data else "", border=1, fill=True)
        pdf.ln()

    pdf.set_y(-12)
    pdf.set_font("Arial", "I", 7)
    pdf.cell(0, 5, f"Página {pdf.page_no()}", align="C")
    pdf.output(file_path)


def _draw_transferencia_termo(pdf: FPDF, entry, start_y: float):
    """Draw one Termo de Transferência at start_y (portrait A4, left margin=15)."""
    x = 15
    W = 180   # usable width
    H = 118   # box height
    lh = 5    # line height for body text

    # Outer border
    pdf.rect(x, start_y, W, H)

    # ── Title row ──
    pdf.set_xy(x + 2, start_y + 3)
    pdf.set_font("Arial", "B", 11)
    title_w = W - 35
    pdf.cell(title_w, 7, "TERMO DE TRANSFERÊNCIA", align="C")
    pdf.set_font("Arial", "B", 10)
    pdf.cell(33, 7, f"Nº  {entry.numero}", align="R", ln=True)

    # ── Parse date ──
    parts = (entry.data or "").split("/")
    dia   = parts[0] if len(parts) > 0 else "___"
    mes   = _MES_PT.get(parts[1], parts[1]) if len(parts) > 1 else "___"
    ano   = parts[2] if len(parts) > 2 else "____"

    # ── Body paragraph ──
    body = (
        f"Aos {dia} dias de {mes} de {ano}, na sede da {entry.sede or '___'}, "
        f"comparece o Snr. {entry.cedente or '___'}, e declara que transfere por "
        f"{entry.valor or '___'}, {entry.quantidade_acoes or '___'} de que é proprietário, "
        f"e de acordo com a relação à margem, com todos os direitos e obrigações constantes "
        f"dos Estatutos. Pelo {entry.cessionario or '___'}, cessionário, foi declarado que "
        f"aceitava esta transferência, de que se lavrou este termo que assina. "
        f"Juntamente com o {entry.cedente or '___'}, cedente."
    )
    pdf.set_xy(x + 3, start_y + 12)
    pdf.set_font("Arial", "", 9)
    pdf.multi_cell(W - 6, lh, body)

    # ── Signature date (right-aligned) ──
    ass_parts = (entry.data_assinatura or "").split("/")
    ass_dia = ass_parts[0] if len(ass_parts) > 0 else "___"
    ass_mes = _MES_PT.get(ass_parts[1], ass_parts[1]) if len(ass_parts) > 1 else "___"
    ass_ano = ass_parts[2] if len(ass_parts) > 2 else "____"
    sig_date = f"{ass_dia} de {ass_mes} de {ass_ano}"

    sig_y = start_y + H - 38
    pdf.set_xy(x + 2, sig_y)
    pdf.set_font("Arial", "", 9)
    pdf.cell(W - 4, lh, sig_date, align="R")

    # ── Bottom section ──
    bottom_y = start_y + H - 30
    # Left: REGISTRO DE ACIONISTAS
    pdf.set_xy(x + 3, bottom_y)
    pdf.set_font("Arial", "B", 7)
    pdf.cell(50, 4, "REGISTRO DE ACIONISTAS", ln=True)
    pdf.set_xy(x + 3, bottom_y + 5)
    pdf.set_font("Arial", "", 7)
    pdf.cell(50, 4, f"LIVRO N.  {entry.livro_numero or '______'}", ln=True)
    pdf.set_xy(x + 3, bottom_y + 10)
    pdf.cell(50, 4, f"FLS.  {entry.folha or '______'}", ln=True)

    # Right: signature lines
    sig_x = x + 60
    sig_w = W - 60 - 3

    # Cedente line
    pdf.set_xy(sig_x, bottom_y)
    pdf.set_font("Arial", "", 8)
    pdf.cell(sig_w, 4, f"O Cedente: {entry.cedente or ''}  " + "_" * 30, align="L")

    # Diretor line
    pdf.set_xy(sig_x, bottom_y + 8)
    pdf.set_font("Arial", "I", 7)
    pdf.cell(sig_w, 4, "Diretor ou Encarregado de Transferência")
    pdf.set_xy(sig_x, bottom_y + 13)
    pdf.set_font("Arial", "", 8)
    pdf.cell(sig_w, 4, f"{entry.diretor or ''}  " + "_" * 30)

    # Cessionário line
    pdf.set_xy(sig_x, bottom_y + 21)
    pdf.set_font("Arial", "", 8)
    pdf.cell(sig_w, 4, f"O Cessionário: {entry.cessionario or ''}  " + "_" * 28)

    # Divider inside box
    div_y = start_y + H - 32
    pdf.set_draw_color(180, 180, 180)
    pdf.line(x, div_y, x + W, div_y)
    pdf.set_draw_color(0, 0, 0)


def _generate_transferencia_pdf(book_name: str, organization: str, entries, file_path: str):
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(15, 15, 15)

    # 2 termos per page
    for i in range(0, max(len(entries), 1), 2):
        pdf.add_page()
        # Page header
        pdf.set_font("Arial", "I", 8)
        pdf.cell(0, 5, f"Livro: {book_name}  |  {organization}  |  "
                       f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", align="C", ln=True)
        pdf.ln(2)

        top_y = pdf.get_y()
        if i < len(entries):
            _draw_transferencia_termo(pdf, entries[i], top_y)

        bottom_y = top_y + 122
        if i + 1 < len(entries):
            _draw_transferencia_termo(pdf, entries[i + 1], bottom_y)

        # Footer
        pdf.set_y(-10)
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
    book_entries_back_page: str = "livros"

    # Book list / creation
    new_book_name: str = ""
    new_book_tipo: str = "registro"       # "registro" | "transferencia"
    new_book_empresa_name: str = ""
    book_list_version: int = 0

    # Selected book
    selected_book_id: int = 0
    selected_book_name: str = ""
    selected_book_tipo: str = "registro"

    # Empresa
    empresa_list_version: int = 0
    selected_empresa_id: int = 0
    selected_empresa_name: str = ""
    new_empresa_name: str = ""
    new_empresa_cnpj: str = ""

    # BookEntry (registro) dialog fields
    entries_version: int = 0
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

    # TransferenciaEntry dialog fields
    trans_version: int = 0
    new_trans_numero: str = ""
    new_trans_data: str = ""
    new_trans_sede: str = ""
    new_trans_cedente: str = ""
    new_trans_valor: str = ""
    new_trans_quantidade_acoes: str = ""
    new_trans_cessionario: str = ""
    new_trans_data_assinatura: str = ""
    new_trans_livro_numero: str = ""
    new_trans_folha: str = ""
    new_trans_diretor: str = ""

    # --- Computed vars ---

    @rx.var
    def empresas(self) -> List[Empresa]:
        _ = self.empresa_list_version
        try:
            with rx.session() as session:
                result = session.exec(
                    select(Empresa).where(Empresa.organization == self.user_organization)
                ).all()
                return [a[0] for a in result]
        except Exception:
            return []

    @rx.var
    def empresa_names(self) -> List[str]:
        return [""] + [e.name for e in self.empresas]

    @rx.var
    def books_list(self) -> List[dict]:
        _ = self.book_list_version
        _ = self.empresa_list_version
        try:
            with rx.session() as session:
                books = session.exec(
                    select(Book).where(Book.organization == self.user_organization)
                ).all()
                books = [a[0] for a in books]
                empresa_rows = session.exec(
                    select(Empresa).where(Empresa.organization == self.user_organization)
                ).all()
                empresa_map = {e[0].id: e[0].name for e in empresa_rows}
                return [
                    {
                        "id": b.id,
                        "name": b.name,
                        "creator": b.creator,
                        "date": b.date,
                        "book_type": b.book_type or "registro",
                        "empresa_name": empresa_map.get(b.empresa_id, "-") if b.empresa_id else "-",
                    }
                    for b in books
                ]
        except Exception:
            return []

    @rx.var
    def empresa_books_list(self) -> List[dict]:
        _ = self.book_list_version
        _ = self.selected_empresa_id
        if self.selected_empresa_id == 0:
            return []
        try:
            with rx.session() as session:
                books = session.exec(
                    select(Book).where(Book.empresa_id == self.selected_empresa_id)
                ).all()
                return [
                    {
                        "id": b[0].id,
                        "name": b[0].name,
                        "creator": b[0].creator,
                        "date": b[0].date,
                        "book_type": b[0].book_type or "registro",
                    }
                    for b in books
                ]
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
                return [e[0] for e in entries]
        except Exception:
            return []

    @rx.var
    def transferencia_entries(self) -> List[TransferenciaEntry]:
        _ = self.trans_version
        _ = self.selected_book_id
        if self.selected_book_id == 0:
            return []
        try:
            with rx.session() as session:
                entries = session.exec(
                    select(TransferenciaEntry).where(
                        TransferenciaEntry.book_id == self.selected_book_id
                    )
                ).all()
                return [e[0] for e in entries]
        except Exception:
            return []

    # --- Setters ---

    def set_username(self, v: str): self.username = v
    def set_password(self, v: str): self.password = v
    def set_new_book_name(self, v: str): self.new_book_name = v
    def set_new_book_tipo(self, v: str): self.new_book_tipo = v
    def set_new_book_empresa_name(self, v: str): self.new_book_empresa_name = v
    def set_new_empresa_name(self, v: str): self.new_empresa_name = v
    def set_new_empresa_cnpj(self, v: str): self.new_empresa_cnpj = v

    def set_new_entry_data_registro(self, v: str): self.new_entry_data_registro = v
    def set_new_entry_tipo_acao(self, v: str): self.new_entry_tipo_acao = v
    def set_new_entry_classe_acao(self, v: str): self.new_entry_classe_acao = v
    def set_new_entry_quantidade_acoes(self, v: str): self.new_entry_quantidade_acoes = v
    def set_new_entry_natureza_operacao(self, v: str): self.new_entry_natureza_operacao = v
    def set_new_entry_certificado(self, v: str): self.new_entry_certificado = v
    def set_new_entry_capital_realizado(self, v: str): self.new_entry_capital_realizado = v
    def set_new_entry_valor_a_pagar(self, v: str): self.new_entry_valor_a_pagar = v
    def set_new_entry_averbacoes_onus(self, v: str): self.new_entry_averbacoes_onus = v
    def set_new_entry_assinatura(self, v: str): self.new_entry_assinatura = v

    def set_new_trans_numero(self, v: str): self.new_trans_numero = v
    def set_new_trans_data(self, v: str): self.new_trans_data = v
    def set_new_trans_sede(self, v: str): self.new_trans_sede = v
    def set_new_trans_cedente(self, v: str): self.new_trans_cedente = v
    def set_new_trans_valor(self, v: str): self.new_trans_valor = v
    def set_new_trans_quantidade_acoes(self, v: str): self.new_trans_quantidade_acoes = v
    def set_new_trans_cessionario(self, v: str): self.new_trans_cessionario = v
    def set_new_trans_data_assinatura(self, v: str): self.new_trans_data_assinatura = v
    def set_new_trans_livro_numero(self, v: str): self.new_trans_livro_numero = v
    def set_new_trans_folha(self, v: str): self.new_trans_folha = v
    def set_new_trans_diretor(self, v: str): self.new_trans_diretor = v

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
        self.selected_empresa_id = 0
        self.selected_empresa_name = ""
        return rx.redirect("/")

    def navigate_to(self, page_name: str):
        self.current_page = page_name

    # --- Empresa CRUD ---

    def add_empresa_from_dialog(self):
        if not self.is_logged_in or not self.new_empresa_name:
            return
        with rx.session() as session:
            session.add(Empresa(
                name=self.new_empresa_name,
                cnpj=self.new_empresa_cnpj,
                organization=self.user_organization,
            ))
            session.commit()
        self.empresa_list_version += 1
        self.new_empresa_name = ""
        self.new_empresa_cnpj = ""

    def remove_empresa(self, empresa_id: int):
        with rx.session() as session:
            e = session.get(Empresa, empresa_id)
            if e:
                session.delete(e)
                session.commit()
        self.empresa_list_version += 1

    def navigate_to_empresa(self, empresa_data: dict):
        self.selected_empresa_id = empresa_data["id"]
        self.selected_empresa_name = empresa_data["name"]
        self.current_page = "empresa_detail"

    def back_to_empresas(self):
        self.current_page = "empresas"
        self.selected_empresa_id = 0
        self.selected_empresa_name = ""

    # --- Book CRUD ---

    def _resolve_empresa_id(self, session) -> int | None:
        if not self.new_book_empresa_name:
            return None
        result = session.exec(
            select(Empresa).where(
                Empresa.name == self.new_book_empresa_name,
                Empresa.organization == self.user_organization,
            )
        ).one_or_none()
        if result is None:
            return None
        return result[0].id if isinstance(result, tuple) else result.id

    def add_book_from_dialog(self):
        if not self.is_logged_in:
            return rx.redirect("/")
        with rx.session() as session:
            session.add(Book(
                name=self.new_book_name,
                creator=self.username,
                date=datetime.now().strftime("%d/%m/%Y"),
                organization=self.user_organization,
                book_type=self.new_book_tipo,
                empresa_id=self._resolve_empresa_id(session),
            ))
            session.commit()
        self.book_list_version += 1
        self.new_book_name = ""
        self.new_book_tipo = "registro"
        self.new_book_empresa_name = ""

    def add_book_for_empresa(self):
        if not self.is_logged_in or self.selected_empresa_id == 0:
            return
        with rx.session() as session:
            session.add(Book(
                name=self.new_book_name,
                creator=self.username,
                date=datetime.now().strftime("%d/%m/%Y"),
                organization=self.user_organization,
                book_type=self.new_book_tipo,
                empresa_id=self.selected_empresa_id,
            ))
            session.commit()
        self.book_list_version += 1
        self.new_book_name = ""
        self.new_book_tipo = "registro"

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
        self.selected_book_tipo = book_data.get("book_type", "registro")
        self.book_entries_back_page = self.current_page
        self.current_page = "book_entries"

    def back_to_books(self):
        self.current_page = self.book_entries_back_page
        self.selected_book_id = 0
        self.selected_book_name = ""

    # --- BookEntry (Registro) CRUD ---

    def add_entry_from_dialog(self):
        if self.selected_book_id == 0:
            return
        with rx.session() as session:
            session.add(BookEntry(
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
            ))
            session.commit()
        self.entries_version += 1
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
            e = session.get(BookEntry, entry_id)
            if e:
                session.delete(e)
                session.commit()
        self.entries_version += 1

    # --- TransferenciaEntry CRUD ---

    def add_transferencia_entry_from_dialog(self):
        if self.selected_book_id == 0:
            return
        with rx.session() as session:
            session.add(TransferenciaEntry(
                book_id=self.selected_book_id,
                numero=self.new_trans_numero,
                data=self.new_trans_data,
                sede=self.new_trans_sede,
                cedente=self.new_trans_cedente,
                valor=self.new_trans_valor,
                quantidade_acoes=self.new_trans_quantidade_acoes,
                cessionario=self.new_trans_cessionario,
                data_assinatura=self.new_trans_data_assinatura,
                livro_numero=self.new_trans_livro_numero,
                folha=self.new_trans_folha,
                diretor=self.new_trans_diretor,
            ))
            session.commit()
        self.trans_version += 1
        self.new_trans_numero = ""
        self.new_trans_data = ""
        self.new_trans_sede = ""
        self.new_trans_cedente = ""
        self.new_trans_valor = ""
        self.new_trans_quantidade_acoes = ""
        self.new_trans_cessionario = ""
        self.new_trans_data_assinatura = ""
        self.new_trans_livro_numero = ""
        self.new_trans_folha = ""
        self.new_trans_diretor = ""

    def remove_transferencia_entry(self, entry_id: int):
        with rx.session() as session:
            e = session.get(TransferenciaEntry, entry_id)
            if e:
                session.delete(e)
                session.commit()
        self.trans_version += 1

    # --- PDF Downloads ---

    def download_book_entries_pdf(self):
        if self.selected_book_id == 0:
            return
        with rx.session() as session:
            book = session.get(Book, self.selected_book_id)
            if not book:
                return
            entries = session.exec(
                select(BookEntry).where(BookEntry.book_id == self.selected_book_id)
            ).all()
            entries_list = [e[0] for e in entries]
            book_name, org = book.name, book.organization
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            _generate_registro_pdf(book_name=book_name, organization=org,
                                   entries=entries_list, file_path=tmp_path)
            with open(tmp_path, "rb") as f:
                pdf_bytes = f.read()
        finally:
            os.unlink(tmp_path)
        return rx.download(data=pdf_bytes, filename=f"livro_registro_{self.selected_book_id}.pdf")

    def download_transferencia_pdf(self):
        if self.selected_book_id == 0:
            return
        with rx.session() as session:
            book = session.get(Book, self.selected_book_id)
            if not book:
                return
            entries = session.exec(
                select(TransferenciaEntry).where(
                    TransferenciaEntry.book_id == self.selected_book_id
                )
            ).all()
            entries_list = [e[0] for e in entries]
            book_name, org = book.name, book.organization
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            _generate_transferencia_pdf(book_name=book_name, organization=org,
                                        entries=entries_list, file_path=tmp_path)
            with open(tmp_path, "rb") as f:
                pdf_bytes = f.read()
        finally:
            os.unlink(tmp_path)
        return rx.download(data=pdf_bytes, filename=f"livro_transferencia_{self.selected_book_id}.pdf")

    def download_pdf_for_book(self, book_data: dict):
        """Download PDF for any book directly from the list, without opening it."""
        book_id = book_data["id"]
        book_type = book_data.get("book_type", "registro")
        with rx.session() as session:
            book = session.get(Book, book_id)
            if not book:
                return
            book_name, org = book.name, book.organization
            if book_type == "transferencia":
                entries = session.exec(
                    select(TransferenciaEntry).where(TransferenciaEntry.book_id == book_id)
                ).all()
                entries_list = [e[0] for e in entries]
            else:
                entries = session.exec(
                    select(BookEntry).where(BookEntry.book_id == book_id)
                ).all()
                entries_list = [e[0] for e in entries]
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            if book_type == "transferencia":
                _generate_transferencia_pdf(book_name=book_name, organization=org,
                                            entries=entries_list, file_path=tmp_path)
                filename = f"transferencia_{book_id}.pdf"
            else:
                _generate_registro_pdf(book_name=book_name, organization=org,
                                       entries=entries_list, file_path=tmp_path)
                filename = f"registro_{book_id}.pdf"
            with open(tmp_path, "rb") as f:
                pdf_bytes = f.read()
        finally:
            os.unlink(tmp_path)
        return rx.download(data=pdf_bytes, filename=filename)


# --- 2. UI Components ---

def _book_tipo_select(on_change, value):
    return rx.vstack(
        rx.text("Tipo de Livro", size="1", weight="bold"),
        rx.select(
            ["registro", "transferencia"],
            on_change=on_change,
            value=value,
            width="100%",
        ),
        spacing="1",
        width="100%",
    )


def add_empresa_dialog():
    return rx.dialog.root(
        rx.dialog.trigger(rx.button("Adicionar Empresa +", color_scheme="green")),
        rx.dialog.content(
            rx.dialog.title("Nova Empresa"),
            rx.dialog.description("Preencha os dados da empresa."),
            rx.flex(
                rx.input(placeholder="Nome da Empresa", on_change=AppState.set_new_empresa_name,
                         value=AppState.new_empresa_name, width="100%"),
                rx.input(placeholder="CNPJ (opcional)", on_change=AppState.set_new_empresa_cnpj,
                         value=AppState.new_empresa_cnpj, width="100%"),
                direction="column", spacing="3", margin_top="15px",
            ),
            rx.flex(
                rx.dialog.close(rx.button("Cancelar", color_scheme="gray", variant="soft")),
                rx.dialog.close(rx.button("Adicionar", on_click=AppState.add_empresa_from_dialog)),
                spacing="3", margin_top="15px", justify="end",
            ),
        ),
    )


def add_book_dialog():
    return rx.dialog.root(
        rx.dialog.trigger(rx.button("Adicionar Livro +", color_scheme="green")),
        rx.dialog.content(
            rx.dialog.title("Novo Livro Societário"),
            rx.flex(
                rx.input(placeholder="Nome do Livro", on_change=AppState.set_new_book_name,
                         value=AppState.new_book_name, width="100%"),
                _book_tipo_select(AppState.set_new_book_tipo, AppState.new_book_tipo),
                rx.vstack(
                    rx.text("Empresa (opcional)", size="1", weight="bold"),
                    rx.select(AppState.empresa_names, on_change=AppState.set_new_book_empresa_name,
                              value=AppState.new_book_empresa_name, width="100%"),
                    spacing="1", width="100%",
                ),
                direction="column", spacing="3", margin_top="15px",
            ),
            rx.flex(
                rx.dialog.close(rx.button("Cancelar", color_scheme="gray", variant="soft")),
                rx.dialog.close(rx.button("Adicionar", on_click=AppState.add_book_from_dialog)),
                spacing="3", margin_top="15px", justify="end",
            ),
        ),
    )


def add_book_for_empresa_dialog():
    return rx.dialog.root(
        rx.dialog.trigger(rx.button("Adicionar Livro +", color_scheme="green")),
        rx.dialog.content(
            rx.dialog.title("Novo Livro para " + AppState.selected_empresa_name),
            rx.flex(
                rx.input(placeholder="Nome do Livro", on_change=AppState.set_new_book_name,
                         value=AppState.new_book_name, width="100%"),
                _book_tipo_select(AppState.set_new_book_tipo, AppState.new_book_tipo),
                direction="column", spacing="3", margin_top="15px",
            ),
            rx.flex(
                rx.dialog.close(rx.button("Cancelar", color_scheme="gray", variant="soft")),
                rx.dialog.close(rx.button("Adicionar", on_click=AppState.add_book_for_empresa)),
                spacing="3", margin_top="15px", justify="end",
            ),
        ),
    )


def add_entry_dialog():
    return rx.dialog.root(
        rx.dialog.trigger(rx.button("Adicionar Lançamento +", color_scheme="green")),
        rx.dialog.content(
            rx.dialog.title("Novo Lançamento"),
            rx.dialog.description("Preencha os campos do lançamento."),
            rx.grid(
                rx.vstack(rx.text("Data do Registro", size="1", weight="bold"),
                          rx.input(placeholder="DD/MM/AAAA", on_change=AppState.set_new_entry_data_registro,
                                   value=AppState.new_entry_data_registro), spacing="1"),
                rx.vstack(rx.text("Tipo de Ação", size="1", weight="bold"),
                          rx.select(["ON","PN","PNA","PNB"], on_change=AppState.set_new_entry_tipo_acao,
                                    value=AppState.new_entry_tipo_acao), spacing="1"),
                rx.vstack(rx.text("Classe da Ação", size="1", weight="bold"),
                          rx.input(placeholder="Classe A, B...", on_change=AppState.set_new_entry_classe_acao,
                                   value=AppState.new_entry_classe_acao), spacing="1"),
                rx.vstack(rx.text("Quantidade de Ações", size="1", weight="bold"),
                          rx.input(placeholder="Ex: 1000", on_change=AppState.set_new_entry_quantidade_acoes,
                                   value=AppState.new_entry_quantidade_acoes), spacing="1"),
                rx.vstack(rx.text("Natureza da Operação", size="1", weight="bold"),
                          rx.select(["Subscrição","Compra e Venda","Doação","Herança","Dação em Pagamento"],
                                    on_change=AppState.set_new_entry_natureza_operacao,
                                    value=AppState.new_entry_natureza_operacao), spacing="1"),
                rx.vstack(rx.text("Certificado", size="1", weight="bold"),
                          rx.input(placeholder="Nº do certificado", on_change=AppState.set_new_entry_certificado,
                                   value=AppState.new_entry_certificado), spacing="1"),
                rx.vstack(rx.text("Capital Realizado (R$)", size="1", weight="bold"),
                          rx.input(placeholder="Valor pago", on_change=AppState.set_new_entry_capital_realizado,
                                   value=AppState.new_entry_capital_realizado), spacing="1"),
                rx.vstack(rx.text("Valor a Pagar (R$)", size="1", weight="bold"),
                          rx.input(placeholder="Valor a pagar", on_change=AppState.set_new_entry_valor_a_pagar,
                                   value=AppState.new_entry_valor_a_pagar), spacing="1"),
                rx.vstack(rx.text("Averbações / Ônus", size="1", weight="bold"),
                          rx.input(placeholder="Penhor, Usufruto...", on_change=AppState.set_new_entry_averbacoes_onus,
                                   value=AppState.new_entry_averbacoes_onus), spacing="1"),
                rx.vstack(rx.text("Assinatura / Log Eletrônico", size="1", weight="bold"),
                          rx.input(placeholder="e-CPF / e-CNPJ", on_change=AppState.set_new_entry_assinatura,
                                   value=AppState.new_entry_assinatura), spacing="1"),
                columns="2", gap="3", margin_top="15px",
            ),
            rx.flex(
                rx.dialog.close(rx.button("Cancelar", color_scheme="gray", variant="soft")),
                rx.dialog.close(rx.button("Adicionar", on_click=AppState.add_entry_from_dialog)),
                spacing="3", margin_top="15px", justify="end",
            ),
            max_width="680px",
        ),
    )


def add_transferencia_entry_dialog():
    def field(label, placeholder, on_change, value):
        return rx.vstack(
            rx.text(label, size="1", weight="bold"),
            rx.input(placeholder=placeholder, on_change=on_change, value=value),
            spacing="1",
        )

    return rx.dialog.root(
        rx.dialog.trigger(rx.button("Adicionar Termo +", color_scheme="green")),
        rx.dialog.content(
            rx.dialog.title("Novo Termo de Transferência"),
            rx.grid(
                field("Nº do Termo", "Ex: 001", AppState.set_new_trans_numero, AppState.new_trans_numero),
                field("Data (DD/MM/AAAA)", "Ex: 15/04/2024", AppState.set_new_trans_data, AppState.new_trans_data),
                field("Sede da Empresa", "Endereço ou cidade", AppState.set_new_trans_sede, AppState.new_trans_sede),
                field("Cedente (Transferidor)", "Nome completo", AppState.set_new_trans_cedente, AppState.new_trans_cedente),
                field("Valor / Contraprestação", "Ex: R$ 10.000,00 ou gratuidade", AppState.set_new_trans_valor, AppState.new_trans_valor),
                field("Quantidade e Tipo de Ações", "Ex: 1000 ações ordinárias nominativas", AppState.set_new_trans_quantidade_acoes, AppState.new_trans_quantidade_acoes),
                field("Cessionário (Adquirente)", "Nome completo", AppState.set_new_trans_cessionario, AppState.new_trans_cessionario),
                field("Data de Assinatura (DD/MM/AAAA)", "Ex: 15/04/2024", AppState.set_new_trans_data_assinatura, AppState.new_trans_data_assinatura),
                field("Livro N.", "Nº do livro físico", AppState.set_new_trans_livro_numero, AppState.new_trans_livro_numero),
                field("FLS. (Folha)", "Nº da folha", AppState.set_new_trans_folha, AppState.new_trans_folha),
                field("Diretor / Encarregado", "Nome do responsável", AppState.set_new_trans_diretor, AppState.new_trans_diretor),
                columns="2", gap="3", margin_top="15px",
            ),
            rx.flex(
                rx.dialog.close(rx.button("Cancelar", color_scheme="gray", variant="soft")),
                rx.dialog.close(rx.button("Adicionar", on_click=AppState.add_transferencia_entry_from_dialog)),
                spacing="3", margin_top="15px", justify="end",
            ),
            max_width="700px",
        ),
    )


def sidebar_item(text: str, page_key: str, icon: str):
    return rx.link(
        rx.hstack(
            rx.icon(tag=icon),
            rx.text(text, font_weight="medium"),
            spacing="2", padding="10px", border_radius="8px",
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
            sidebar_item("Empresas", "empresas", "building-2"),
            rx.spacer(),
            rx.button("Sair", on_click=AppState.logout, variant="outline",
                      color_scheme="red", width="100%"),
            height="100%", align_items="start", padding="20px",
        ),
        width="250px", height="100vh", bg="#1a202c",
    )


def login_screen():
    return rx.form(
        rx.center(
            rx.vstack(
                rx.heading("Login", size="6"),
                rx.input(placeholder="Usuário", on_change=AppState.set_username,
                         value=AppState.username, width="100%"),
                rx.input(placeholder="Senha", type="password", on_change=AppState.set_password, width="100%"),
                rx.cond(AppState.login_error != "",
                        rx.text(AppState.login_error, color="red", font_size="sm")),
                rx.button("Entrar", on_click=AppState.perform_login, width="100%", color_scheme="blue"),
                spacing="4", padding="30px", border="1px solid #eaeaea",
                border_radius="12px", box_shadow="lg", bg="white", width="350px",
            ),
            height="100vh", bg="#f7f9fc",
        )
    )


def welcome_view():
    return rx.vstack(
        rx.heading(f"Bem-vindo, {AppState.username}!", size="8"),
        rx.text("Selecione uma opção no menu lateral para começar."),
        padding="40px",
    )


def empresas_view():
    return rx.vstack(
        rx.hstack(
            rx.heading("Empresas", size="6"),
            rx.spacer(),
            add_empresa_dialog(),
            width="100%", padding_bottom="20px", align="center",
        ),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("ID"),
                    rx.table.column_header_cell("Nome da Empresa"),
                    rx.table.column_header_cell("CNPJ"),
                    rx.table.column_header_cell("Ações"),
                )
            ),
            rx.table.body(
                rx.foreach(
                    AppState.empresas,
                    lambda empresa: rx.table.row(
                        rx.table.cell(empresa.id),
                        rx.table.cell(empresa.name),
                        rx.table.cell(empresa.cnpj),
                        rx.table.cell(
                            rx.hstack(
                                rx.button("Ver Livros",
                                          on_click=AppState.navigate_to_empresa({"id": empresa.id, "name": empresa.name}),
                                          size="1", variant="soft", color_scheme="blue"),
                                rx.button("Remover",
                                          on_click=AppState.remove_empresa(empresa.id),
                                          size="1", variant="soft", color_scheme="red"),
                            )
                        ),
                    )
                )
            ),
            variant="surface", width="100%",
        ),
        width="100%", padding="40px",
    )


def empresa_detail_view():
    return rx.vstack(
        rx.hstack(
            rx.button(rx.icon(tag="arrow-left", size=16), "Voltar",
                      on_click=AppState.back_to_empresas, variant="ghost", color_scheme="gray"),
            rx.heading(AppState.selected_empresa_name, size="6"),
            rx.spacer(),
            add_book_for_empresa_dialog(),
            width="100%", padding_bottom="20px", align="center", spacing="3",
        ),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("ID"),
                    rx.table.column_header_cell("Nome do Livro"),
                    rx.table.column_header_cell("Tipo"),
                    rx.table.column_header_cell("Criador"),
                    rx.table.column_header_cell("Data"),
                    rx.table.column_header_cell("Ações"),
                )
            ),
            rx.table.body(
                rx.foreach(
                    AppState.empresa_books_list,
                    lambda book: rx.table.row(
                        rx.table.cell(book["id"]),
                        rx.table.cell(book["name"]),
                        rx.table.cell(book["book_type"]),
                        rx.table.cell(book["creator"]),
                        rx.table.cell(book["date"]),
                        rx.table.cell(
                            rx.hstack(
                                rx.button("Abrir", on_click=AppState.navigate_to_book(book),
                                          size="1", variant="soft", color_scheme="blue"),
                                rx.button(rx.icon(tag="file-down", size=13), "PDF",
                                          on_click=AppState.download_pdf_for_book(book),
                                          size="1", variant="soft", color_scheme="indigo"),
                                rx.button("Remover", on_click=AppState.remove_book(book["id"]),
                                          size="1", variant="soft", color_scheme="red"),
                            )
                        ),
                    )
                )
            ),
            variant="surface", width="100%",
        ),
        width="100%", padding="40px",
    )


def livros_view():
    return rx.vstack(
        rx.hstack(
            rx.heading("Livros Societários", size="6"),
            rx.spacer(),
            add_book_dialog(),
            width="100%", padding_bottom="20px", align="center",
        ),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("ID"),
                    rx.table.column_header_cell("Nome do Livro"),
                    rx.table.column_header_cell("Tipo"),
                    rx.table.column_header_cell("Criador"),
                    rx.table.column_header_cell("Data"),
                    rx.table.column_header_cell("Empresa"),
                    rx.table.column_header_cell("Ações"),
                )
            ),
            rx.table.body(
                rx.foreach(
                    AppState.books_list,
                    lambda book: rx.table.row(
                        rx.table.cell(book["id"]),
                        rx.table.cell(book["name"]),
                        rx.table.cell(book["book_type"]),
                        rx.table.cell(book["creator"]),
                        rx.table.cell(book["date"]),
                        rx.table.cell(book["empresa_name"]),
                        rx.table.cell(
                            rx.hstack(
                                rx.button("Abrir", on_click=AppState.navigate_to_book(book),
                                          size="1", variant="soft", color_scheme="blue"),
                                rx.button(rx.icon(tag="file-down", size=13), "PDF",
                                          on_click=AppState.download_pdf_for_book(book),
                                          size="1", variant="soft", color_scheme="indigo"),
                                rx.button("Remover", on_click=AppState.remove_book(book["id"]),
                                          size="1", variant="soft", color_scheme="red"),
                            )
                        ),
                    )
                )
            ),
            variant="surface", width="100%",
        ),
        width="100%", padding="40px",
    )


def registro_entries_view():
    return rx.vstack(
        rx.hstack(
            rx.button(rx.icon(tag="arrow-left", size=16), "Voltar",
                      on_click=AppState.back_to_books, variant="ghost", color_scheme="gray"),
            rx.heading(AppState.selected_book_name, size="6"),
            rx.spacer(),
            add_entry_dialog(),
            rx.button(rx.icon(tag="file-down", size=16), "Download PDF",
                      on_click=AppState.download_book_entries_pdf, color_scheme="blue", variant="soft"),
            width="100%", padding_bottom="20px", align="center", spacing="3",
        ),
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
                                rx.button("Remover", on_click=AppState.remove_entry(entry.id),
                                          size="1", variant="soft", color_scheme="red")
                            ),
                        )
                    )
                ),
                variant="surface", width="100%",
            ),
            type="always", scrollbars="horizontal",
        ),
        width="100%", padding="40px",
    )


def transferencia_entries_view():
    return rx.vstack(
        rx.hstack(
            rx.button(rx.icon(tag="arrow-left", size=16), "Voltar",
                      on_click=AppState.back_to_books, variant="ghost", color_scheme="gray"),
            rx.heading(AppState.selected_book_name, size="6"),
            rx.spacer(),
            add_transferencia_entry_dialog(),
            rx.button(rx.icon(tag="file-down", size=16), "Download PDF",
                      on_click=AppState.download_transferencia_pdf, color_scheme="blue", variant="soft"),
            width="100%", padding_bottom="20px", align="center", spacing="3",
        ),
        rx.scroll_area(
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Nº"),
                        rx.table.column_header_cell("Data"),
                        rx.table.column_header_cell("Cedente"),
                        rx.table.column_header_cell("Cessionário"),
                        rx.table.column_header_cell("Qtde Ações"),
                        rx.table.column_header_cell("Valor"),
                        rx.table.column_header_cell("Sede"),
                        rx.table.column_header_cell("Livro N."),
                        rx.table.column_header_cell("FLS."),
                        rx.table.column_header_cell("Diretor"),
                        rx.table.column_header_cell("Ações"),
                    )
                ),
                rx.table.body(
                    rx.foreach(
                        AppState.transferencia_entries,
                        lambda entry: rx.table.row(
                            rx.table.cell(entry.numero),
                            rx.table.cell(entry.data),
                            rx.table.cell(entry.cedente),
                            rx.table.cell(entry.cessionario),
                            rx.table.cell(entry.quantidade_acoes),
                            rx.table.cell(entry.valor),
                            rx.table.cell(entry.sede),
                            rx.table.cell(entry.livro_numero),
                            rx.table.cell(entry.folha),
                            rx.table.cell(entry.diretor),
                            rx.table.cell(
                                rx.button("Remover",
                                          on_click=AppState.remove_transferencia_entry(entry.id),
                                          size="1", variant="soft", color_scheme="red")
                            ),
                        )
                    )
                ),
                variant="surface", width="100%",
            ),
            type="always", scrollbars="horizontal",
        ),
        width="100%", padding="40px",
    )


def book_entries_view():
    return rx.cond(
        AppState.selected_book_tipo == "transferencia",
        transferencia_entries_view(),
        registro_entries_view(),
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
                    rx.cond(
                        AppState.current_page == "empresas",
                        empresas_view(),
                        rx.cond(
                            AppState.current_page == "empresa_detail",
                            empresa_detail_view(),
                            book_entries_view(),
                        ),
                    ),
                ),
            ),
            width="100%", height="100vh", overflow="auto",
        ),
        spacing="0",
    )


def index():
    return rx.cond(AppState.is_logged_in, dashboard_layout(), login_screen())


# --- 4. App Definition ---

app = rx.App()
app.add_page(index, route="/")
app._compile()
