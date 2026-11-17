"""Catálogo e helpers de enciclopédias offline Kiwix (.zim) em Português (Brasil).

Importante: não importa engine.paths no nível superior porque engine/setup/api.py
carrega este módulo antes da definição de LASTBOOK_DATA no app empacotado.
"""
from pathlib import Path

ZIMS_PT = [
    {
        'id': 'wikimed-pt',
        'file': 'wikipedia_pt_medicine_maxi_2026-10.zim',
        'size': 294_411_815,
        'sha256': 'cbc3450a86f4dcbddd59e8d50e62a18fc7397a31bb2a84c99a2ee6d10fd5d1be',
        'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_pt_medicine_maxi_2026-10.zim',
        'title': 'WikiMed em Português (Enciclopédia Médica)',
        'group': 'Saúde e Medicina',
        'icon': 'health',
        'summary': 'Artigos médicos da Wikipédia em português com imagens: doenças, sintomas, medicamentos e primeiros socorros.',
    },
    {
        'id': 'wikipedia-pt-mini',
        'file': 'wikipedia_pt_top_mini_2026-10.zim',
        'size': 152_962_448,
        'sha256': '63fef8a1584c5729580ea13e1c3ae7f6b2f7cbb8421fe3fa80f0e9e9f9cb855c',
        'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_pt_top_mini_2026-10.zim',
        'title': 'Wikipédia em Português — Essenciais (Compacta)',
        'group': 'Enciclopédia Geral',
        'icon': 'wiki',
        'summary': 'Resumos dos principais artigos da Wikipédia em português. Ideal para economizar espaço.',
    },
    {
        'id': 'wikipedia-pt-top',
        'file': 'wikipedia_pt_top_nopic_2026-10.zim',
        'size': 1_095_015_424,
        'sha256': 'c37790d98fe5d7689c64faedff7ab457c4d894d10c8fbe51cf897e00df992a3d',
        'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_pt_top_nopic_2026-10.zim',
        'title': 'Wikipédia em Português — Principais Artigos (Texto)',
        'group': 'Enciclopédia Geral',
        'icon': 'wiki',
        'summary': 'Os artigos mais importantes da Wikipédia em português completos, sem imagens.',
    },
    {
        'id': 'wikipedia-pt-top-maxi',
        'file': 'wikipedia_pt_top_maxi_2026-10.zim',
        'size': 3_023_844_304,
        'sha256': '86371063bcbab504398175ddb1602a8595f78cf23357e5508f812130a28f38f5',
        'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_pt_top_maxi_2026-10.zim',
        'title': 'Wikipédia em Português — Principais Artigos (Com Imagens)',
        'group': 'Enciclopédia Geral',
        'icon': 'wiki',
        'summary': 'Os principais artigos da Wikipédia em português completos e ilustrados.',
    },
    {
        'id': 'wikipedia-pt-all-nopic',
        'file': 'wikipedia_pt_all_nopic_2026-05.zim',
        'size': 7_072_450_434,
        'sha256': '4e68523e52ec82b167593ff5934fdd8f7eb3209f4e2106115c0df115c9f55514',
        'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_pt_all_nopic_2026-05.zim',
        'title': 'Wikipédia em Português — Completa (Somente Texto)',
        'group': 'Enciclopédia Geral',
        'icon': 'wiki',
        'summary': 'Todos os artigos da Wikipédia em português em texto completo, sem imagens.',
    },
    {
        'id': 'ifixit-pt',
        'file': 'ifixit_pt_all_2026-03.zim',
        'size': 3_632_911_745,
        'sha256': 'c2fdcd02c956268e4844fa05770a2d99414baef80ce5085631750464cfd361c0',
        'url': 'https://download.kiwix.org/zim/ifixit/ifixit_pt_all_2026-03.zim',
        'title': 'iFixit em Português (Guias de Reparo)',
        'group': 'Reparos e Sobrevivência Prática',
        'icon': 'repair',
        'summary': 'Manuais ilustrados passo a passo para consertar equipamentos, geradores, veículos e eletrônicos.',
    },
    {
        'id': 'wikibooks-pt',
        'file': 'wikibooks_pt_all_maxi_2026-10.zim',
        'size': 169_410_254,
        'sha256': '593c562922149d05ba8b08a42265c66ea647f2b507f6ff3f1366923b8947c731',
        'url': 'https://download.kiwix.org/zim/wikibooks/wikibooks_pt_all_maxi_2026-10.zim',
        'title': 'Wikilivros (Wikibooks) em Português',
        'group': 'Educação, Língua e Manuais',
        'icon': 'book',
        'summary': 'Manuais práticos, livros didáticos abertos, culinária e guias técnicos em português.',
    },
    {
        'id': 'wikivoyage-pt',
        'file': 'wikivoyage_pt_all_maxi_2026-09.zim',
        'size': 56_577_698,
        'sha256': 'c2ff85fbd6d4286206ac50d5a76670359170c2da57debddaa5c81907960fd117',
        'url': 'https://download.kiwix.org/zim/wikivoyage/wikivoyage_pt_all_maxi_2026-09.zim',
        'title': 'Wikivoyage em Português (Guias e Frases)',
        'group': 'Educação, Língua e Manuais',
        'icon': 'pin',
        'summary': 'Guias geográficos de cidades, rotas e manuais de conversação em português.',
    },
    {
        'id': 'wiktionary-pt',
        'file': 'wiktionary_pt_all_nopic_2026-09.zim',
        'size': 370_108_841,
        'sha256': 'd5e2f31bdb2fa846f25b65b82f15de0109a50972886a2c1d7cd1c1b3bb75982e',
        'url': 'https://download.kiwix.org/zim/wiktionary/wiktionary_pt_all_nopic_2026-09.zim',
        'title': 'Wikcionário em Português (Dicionário Offline)',
        'group': 'Educação, Língua e Manuais',
        'icon': 'book',
        'summary': 'Dicionário completo da língua portuguesa com definições, gramática e traduções.',
    },
    {
        'id': 'phet-pt',
        'file': 'phet_pt_all_2026-08.zim',
        'size': 81_295_972,
        'sha256': '1d8df99469c530faede1e10a9fa91424ab8106aa5d10b85ea3b2bb262ee299af',
        'url': 'https://download.kiwix.org/zim/phet/phet_pt_all_2026-08.zim',
        'title': 'Simulações PhET em Português (Física, Química e Energia)',
        'group': 'Educação, Língua e Manuais',
        'icon': 'power',
        'summary': 'Simulações interativas de eletricidade, energia, física, química e biologia em português.',
    },
]

_BY_ID = {z['id']: z for z in ZIMS_PT}
_BY_FILE = {z['file']: z for z in ZIMS_PT}


def get_zim(zim_id_or_file):
    if not zim_id_or_file:
        return None
    return _BY_ID.get(zim_id_or_file) or _BY_FILE.get(zim_id_or_file)


def public_zims():
    return [{k: v for k, v in z.items() if k != 'url'} for z in ZIMS_PT]


def zim_label(filename):
    if not filename:
        return ''
    hit = _BY_FILE.get(filename)
    if hit:
        return hit['title']
    stem = Path(filename).name
    prefixes = {
        'wikipedia_pt_medicine': 'WikiMed em Português (Enciclopédia Médica)',
        'wikipedia_pt': 'Wikipédia em Português',
        'ifixit_pt': 'iFixit em Português (Guias de Reparo)',
        'wikibooks_pt': 'Wikilivros (Wikibooks) em Português',
        'wikivoyage_pt': 'Wikivoyage em Português (Guias e Frases)',
        'wiktionary_pt': 'Wikcionário em Português',
        'phet_pt': 'Simulações PhET em Português',
        'mdwiki': 'Enciclopédia médica (MDWiki)',
        'wikipedia': 'Wikipédia (Inglês)',
        'wikibooks': 'Wikibooks (Inglês)',
        'appropedia': 'Appropedia — tecnologia apropriada',
    }
    for pref, label in prefixes.items():
        if stem.startswith(pref):
            return label
    return stem


def collections_dir(lib_root):
    return Path(lib_root) / 'library-data' / 'collections'
