"""Texto y fechas con los nombres de v1. La implementación es la de `raphael_core.text_es`."""

from ...text_es import MONTH_NAMES as MESES_NOMBRE
from ...text_es import MONTHS as MESES
from ...text_es import RE_MONTH_IN_WORDS as R_MES_EN_LETRAS
from ...text_es import WEEKDAYS as DIAS
from ...text_es import clean as limpio
from ...text_es import date_in_words as fecha_en_palabras
from ...text_es import first_name as primer_nombre
from ...text_es import is_question as es_pregunta
from ...text_es import money as plata
from ...text_es import next_weekday as dia_semana
from ...text_es import normalize as normalizar
from ...text_es import parse_date as parse_fecha
from ...text_es import parse_time as parse_hora
from ...text_es import short_date as fecha_corta

__all__ = ["DIAS", "MESES", "MESES_NOMBRE", "R_MES_EN_LETRAS", "dia_semana", "es_pregunta", "fecha_corta",
           "fecha_en_palabras", "limpio", "normalizar", "parse_fecha", "parse_hora", "plata", "primer_nombre"]
