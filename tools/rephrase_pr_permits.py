"""Generate paired Spanish rewrites from public directions alone, before scoring the parcel reader."""
import argparse
from contextlib import closing
from decimal import Decimal
import json
from pathlib import Path
import re
import sqlite3
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import llm_local
from engine.pr_addresses import fold
from engine.pr_rural_model import spelled
from tools.check_pr_permit_coverage import KM, ROAD, full_directions, sample, sample_id

PROMPT = """Reformula la dirección pública que sigue como una sola indicación natural que una persona en Puerto Rico diría por teléfono para explicar dónde queda un sitio. Cambia el orden y expande abreviaturas cuando su sentido sea claro. Conserva los nombres, los números (puedes escribir decimales como se dicen), el municipio, y todos los detalles de sector, barrio, solar e interior si están presentes. {postal} No inventes referencias, relaciones de distancia ni cruces. Varía el estilo de manera natural. Devuelve solamente la indicación en español sin comillas ni comentarios."""
SPOKEN = PROMPT.format(postal='Puedes omitir el código postal.')
TYPED = PROMPT.format(postal='IMPORTANTE: conserva siempre todas las cantidades en dígitos, como al mandar un mensaje por WhatsApp. Escribe un decimal como 2.5, nunca en palabras. Omite el código postal.')
ORDER = ('Dilo empezando por el municipio. ', 'Dilo empezando por el barrio o el sector. ', 'Dilo empezando por la carretera. ')


def source_preserving(text, town, index):
    """Read the printed road and km aloud in place. Preserve the other details and their attachments."""
    def kilometer(m):
        whole, _, fraction = format(Decimal(m[1].replace(',', '.')), 'f').partition('.')
        digits = fraction.rstrip('0')
        suffix = ' punto ' + ' '.join(spelled(int(d), 'es') for d in digits) if digits else ''
        return 'kilómetro ' + spelled(int(whole), 'es') + suffix

    # A municipio inside a barrio or street name is part of that name.
    parts = [part.strip() for part in re.split(r'(?<!\d),|,(?!\d)|,(?=\d{5}(?:-\d{4})?\s*$)', text)]
    parts = [part for part in parts if part and fold(part) != fold(town) and not re.fullmatch(r'00[679]\d{2}(?:-?\d{4})?',part)]
    line = ', '.join(parts)
    line = re.sub(r'\b(?:carr|carretera)\.?\s+(?=PR[-. ]*\d)', '', line, flags=re.I)
    line = ROAD.sub(lambda m: 'carretera ' + spelled(int(m[1]), 'es'), line)
    line = KM.sub(kilometer, line)
    for pattern, replacement in [(r'\bbo\b\.?', 'barrio'), (r'\bsect?\b\.?', 'sector'), (r'\bint\b\.?', 'interior'),
                                 (r'\burb\b\.?', 'urbanización'), (r'\bcmno\b\.?', 'camino'), (r'\bedif\b\.?', 'edificio')]:
        line = re.sub(pattern, replacement, line, flags=re.I)
    if index == 0:
        return f'En {town}, {line.lower()}.'
    if index == 1:
        return f'{line.capitalize()}, en {town}.'
    return f'Queda en {town}, {line.lower()}.'


def rewrite(model, system, text):
    start = time.monotonic()
    parts = []
    messages = [{'role':'system', 'content':system}, {'role':'user', 'content':text}]
    model.generate(llm_local.render(messages, []), 190, lambda: time.monotonic() - start > 60, parts.append)
    answer = llm_local._strip_thinking(''.join(parts)).strip()
    if not answer:
        raise RuntimeError('Local model returned an empty rewrite')
    return answer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', type=Path)
    parser.add_argument('sources', type=Path)
    parser.add_argument('output', type=Path, help='new local JSON Lines file')
    args = parser.parse_args()
    with closing(sqlite3.connect(args.database.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        towns = [t for t, in db.execute('SELECT name FROM municipios ORDER BY name')]
    selected = sample(args.sources, towns, 3)
    model = llm_local.LOCAL
    try:
        model.discover()
        problem = model.ensure_running()
        if problem:
            parser.error(problem)
        with args.output.open('x', encoding='utf-8') as out:
            for town in towns:
                for index, (land, text, _, _) in enumerate(selected[fold(town)].values()):
                    full = full_directions(text, town)
                    row = {'sample_id':sample_id(land, full), 'source_preserving':source_preserving(text, town, index),
                           'spoken':rewrite(model, SPOKEN, full),
                           'typed':rewrite(model, TYPED, ORDER[index] + full)}
                    print(json.dumps(row, ensure_ascii=False), file=out, flush=True)
    finally:
        model.stop('Finished rewriting public permit directions')
