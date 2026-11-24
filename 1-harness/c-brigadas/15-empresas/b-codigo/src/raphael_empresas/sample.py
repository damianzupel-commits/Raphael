"""Config de ejemplo (el taller de ropa a medida del caso piloto). La usan los tests, el humo de `arrancar.py --probar`
y el conversor como referencia. Equivale al `PERFIL_MINIMO` y al `perfil-ropa-medida.yaml` de Empresas 0.4."""

MINIMAL = {
    "business": {"name": "Taller Ejemplo", "owner": "Ana"},
    "info": {"hours": "Lunes a sábado de 10 a 19", "shipping": "Enviamos a todo el país por correo",
             "payment_methods": ["transferencia", "efectivo"], "location": "Rosario, zona centro"},
    "payments": {"deposit_pct": 50, "alias": "taller.ejemplo", "holder": "Ana Pérez"},
    "orders": {"prices": [{"item": "vestido", "base": 150000, "days": 30}],
               "surcharges": [{"word": "largo", "kind": "pct", "value": 20}]},
    "schedule": {"reminder_days_before": 3, "slots": ["jueves 16 a 19", "sábado 10 a 13"]},
}

PILOT = {
    "business": {"name": "Taller Ejemplo", "owner": "Ana", "tone": "voseo_emojis"},
    "info": {"hours": "Atendemos de lunes a sábado de 10 a 19", "shipping": "Enviamos a todo el país por correo",
             "payment_methods": ["transferencia", "efectivo"],
             "location": "Estamos en Rosario, zona centro (la dirección exacta se pasa al confirmar un turno)",
             "faq": [{"question": "¿Trabajan con telas que lleva la clienta?",
                      "answer": "Sí, podés traer tu tela; te decimos si sirve para el modelo que querés.",
                      "keywords": ["mi tela", "traer tela", "llevo la tela"]}]},
    "payments": {"deposit_pct": 50, "alias": "taller.ejemplo", "holder": "Ana Pérez"},
    "orders": {"required_steps": ["prenda", "ocasion", "fecha", "detalles", "referencias", "medidas", "nombre"],
               "urgent_if_days_under": 15,
               "prices": [{"item": "vestido", "base": 150000, "days": 30},
                          {"item": "vestido de novia", "base": 450000, "days": 60},
                          {"item": "traje", "base": 220000, "days": 35}],
               "surcharges": [{"word": "largo", "kind": "pct", "value": 20},
                              {"word": "bordado", "kind": "amount", "value": 40000}]},
    "schedule": {"reminder_days_before": 3, "slots": ["jueves de 16 a 19", "sábados de 10 a 13"]},
}
