# -*- coding: utf-8 -*-
"""Convierte INFORME-RAPHAEL.md a INFORME-RAPHAEL.pdf usando reportlab."""
import re
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Preformatted,
    ListFlowable, ListItem, HRFlowable
)

MD_PATH = "INFORME-RAPHAEL.md"
PDF_PATH = "INFORME-RAPHAEL.pdf"

# Estilos
title_style = ParagraphStyle(
    "Title", fontName="Helvetica-Bold", fontSize=17, leading=21,
    textColor=HexColor("#1a1a2e"), alignment=TA_CENTER, spaceAfter=6
)
subtitle_style = ParagraphStyle(
    "Subtitle", fontName="Helvetica-Oblique", fontSize=9, leading=12,
    textColor=HexColor("#555555"), alignment=TA_CENTER, spaceAfter=12
)
h1_style = ParagraphStyle(
    "H1", fontName="Helvetica-Bold", fontSize=13.5, leading=16,
    textColor=HexColor("#1a1a2e"), spaceBefore=13, spaceAfter=5
)
h2_style = ParagraphStyle(
    "H2", fontName="Helvetica-Bold", fontSize=11, leading=14,
    textColor=HexColor("#1f3a5f"), spaceBefore=9, spaceAfter=4
)
body_style = ParagraphStyle(
    "Body", fontName="Helvetica", fontSize=9.5, leading=12.5,
    alignment=TA_JUSTIFY, spaceAfter=4
)
code_style = ParagraphStyle(
    "Code", fontName="Courier", fontSize=8, leading=10,
    backColor=HexColor("#f4f4f4"), borderColor=HexColor("#cccccc"),
    borderWidth=0.5, borderPadding=6, spaceBefore=4, spaceAfter=6
)
meta_style = ParagraphStyle(
    "Meta", fontName="Helvetica", fontSize=8.5, leading=11,
    textColor=HexColor("#444444"), spaceAfter=3
)


def md_inline_to_html(text):
    """Convierte markdown inline simple a HTML para reportlab Paragraph."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    text = re.sub(r"`(.+?)`", r"<font face='Courier' size='7'>\1</font>", text)
    return text


def main():
    with open(MD_PATH, "r", encoding="utf-8") as f:
        lines = f.read().split("\n")

    doc = SimpleDocTemplate(
        PDF_PATH, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title="Informe Raphael", author="Raphael (JarvisRemote)",
        subject="Capacidades, funcionalidades e ingeniería detrás del harness Raphael"
    )

    story = []
    story.append(Paragraph("Informe Raphael", title_style))
    story.append(Paragraph(
        "Capacidades, funcionalidades e ingeniería detrás del harness — JarvisRemote<br/>"
        "Autor: Raphael &nbsp;|&nbsp; Fecha: 2026-11-05 &nbsp;|&nbsp; Estado: referencia técnica",
        subtitle_style
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#1a1a2e"), spaceAfter=10))

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Bloque de código
        if stripped.startswith("```"):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            if code_lines:
                story.append(Preformatted("\n".join(code_lines), code_style))
            i += 1
            continue

        # Encabezado #
        if stripped.startswith("# "):
            story.append(Paragraph(md_inline_to_html(stripped[2:]), h1_style))
        elif stripped.startswith("## "):
            story.append(Paragraph(md_inline_to_html(stripped[3:]), h2_style))
        elif stripped.startswith("### "):
            story.append(Paragraph(md_inline_to_html(stripped[4:]), h2_style))
        # Línea separadora
        elif stripped == "---":
            story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#999999"), spaceAfter=6))
        # Línea en blanco
        elif stripped == "":
            story.append(Spacer(1, 3))
        # Lista con guión
        elif stripped.startswith("- ") or stripped.startswith("* "):
            items = []
            while i < len(lines) and (lines[i].strip().startswith("- ") or lines[i].strip().startswith("* ")):
                items.append(md_inline_to_html(lines[i].strip()[2:]))
                i += 1
            story.append(ListFlowable(
                [ListItem(Paragraph(it, body_style)) for it in items],
                bulletType="bullet", start="▪ ", leftIndent=10
            ))
            continue
        # Texto normal (puede tener varias líneas seguidas -> unificar en un párrafo)
        else:
            block_lines = []
            while i < len(lines) and lines[i].strip() != "" and not lines[i].strip().startswith("#") \
                    and not lines[i].strip().startswith("---") and not lines[i].strip().startswith("```") \
                    and not lines[i].strip().startswith("- ") and not lines[i].strip().startswith("* "):
                block_lines.append(lines[i].strip())
                i += 1
            if block_lines:
                story.append(Paragraph(md_inline_to_html(" ".join(block_lines)), body_style))
            continue

        i += 1

    doc.build(story)
    print(f"PDF generado: {PDF_PATH}")


if __name__ == "__main__":
    main()
