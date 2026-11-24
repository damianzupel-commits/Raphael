# -*- coding: utf-8 -*-
import os, re
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                Table, TableStyle, Preformatted, HRFlowable)

BASE = os.path.dirname(os.path.abspath(__file__))
md_path = os.path.join(BASE, "INFORME-RAPHAEL.md")
pdf_path = os.path.join(BASE, "INFORME-RAPHAEL.pdf")

with open(md_path, "r", encoding="utf-8") as f:
    md = f.read()

estilo_h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=16, leading=20,
                           spaceBefore=14, spaceAfter=8, textColor=colors.HexColor("#1a3a5c"))
estilo_h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=13, leading=17,
                           spaceBefore=10, spaceAfter=6, textColor=colors.HexColor("#2c5f8a"))
estilo_h3 = ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=11, leading=14,
                           spaceBefore=8, spaceAfter=4, textColor=colors.HexColor("#2c5f8a"))
estilo_body = ParagraphStyle("body", fontName="Helvetica", fontSize=9.5, leading=13,
                             spaceAfter=4)
estilo_bullet = ParagraphStyle("bullet", fontName="Helvetica", fontSize=9.5, leading=12,
                               leftIndent=14, spaceAfter=2, bulletIndent=4)
estilo_code = ParagraphStyle("code", fontName="Courier", fontSize=8, leading=10,
                             leftIndent=14, backColor=colors.HexColor("#f4f4f4"),
                             borderColor=colors.HexColor("#dddddd"), borderWidth=0.5,
                             borderPadding=4, spaceBefore=2, spaceAfter=6)

doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                        leftMargin=15*mm, rightMargin=15*mm,
                        topMargin=15*mm, bottomMargin=15*mm,
                        title="Informe Raphael", author="Raphael")

story = []
lineas = md.split("\n")
i = 0
while i < len(lineas):
    linea = lineas[i]

    if linea.strip() == "---":
        i += 1
        continue

    m = re.match(r"^(#{1,3})\s+(.+)$", linea)
    if m:
        nivel = len(m.group(1))
        texto = m.group(2).strip()
        if nivel == 1:
            story.append(Paragraph(texto, estilo_h1))
        elif nivel == 2:
            story.append(Paragraph(texto, estilo_h2))
        else:
            story.append(Paragraph(texto, estilo_h3))
        i += 1
        continue

    if linea.strip() == "***":
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#999999"),
                                spaceBefore=4, spaceAfter=8))
        i += 1
        continue

    if linea.strip().startswith("```"):
        i += 1
        codigo_lineas = []
        while i < len(lineas) and not lineas[i].strip().startswith("```"):
            codigo_lineas.append(lineas[i])
            i += 1
        i += 1
        codigo_texto = "\n".join(codigo_lineas)
        codigo_texto = codigo_texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        story.append(Preformatted(codigo_texto, estilo_code))
        continue

    es_tabla = False
    if "|" in linea:
        if i+1 < len(lineas) and re.match(r"^\s*\|?\s*:?-{3,}:?\s*\|", lineas[i+1]):
            es_tabla = True
    if es_tabla:
        tabla_lineas = []
        while i < len(lineas) and "|" in lineas[i]:
            tabla_lineas.append(lineas[i])
            i += 1
        datos = []
        for fila in tabla_lineas:
            celdas = [c.strip() for c in fila.strip().strip("|").split("|")]
            if all(re.match(r"^:?-{3,}:?$", c) for c in celdas):
                continue
            celdas = [c.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") for c in celdas]
            datos.append([Paragraph(c, estilo_body) for c in celdas])
        if datos:
            tabla = Table(datos, repeatRows=1)
            tabla.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1a3a5c")),
                ("TEXTCOLOR", (0,0), (-1,0), colors.white),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE", (0,0), (-1,0), 8.5),
                ("BACKGROUND", (0,1), (-1,-1), colors.white),
                ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#999999")),
                ("VALIGN", (0,0), (-1,-1), "TOP"),
                ("LEFTPADDING", (0,0), (-1,-1), 4),
                ("RIGHTPADDING", (0,0), (-1,-1), 4),
                ("TOPPADDING", (0,0), (-1,-1), 3),
                ("BOTTOMPADDING", (0,0), (-1,-1), 3),
            ]))
            story.append(tabla)
            story.append(Spacer(1, 6))
        continue

    m = re.match(r"^[\-\*]\s+(.+)$", linea)
    if m:
        texto = m.group(1).strip()
        texto = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", texto)
        story.append(Paragraph(texto, estilo_bullet, bulletText="•"))
        i += 1
        continue

    if linea.strip() == "":
        story.append(Spacer(1, 2))
        i += 1
        continue

    texto = linea.strip()
    texto = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", texto)
    texto = texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    texto = texto.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
    story.append(Paragraph(texto, estilo_body))
    i += 1

doc.build(story)
print("PDF generado:", pdf_path)
