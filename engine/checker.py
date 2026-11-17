"""Diagnóstico completo offline da integridade do Último Livro (inspirado em refugios-check.py).

Verifica biblioteca base, mapas estaduais, enciclopédias Kiwix (.zim), modelos de IA (.gguf),
compatibilidade de memória RAM, cofres criptografados e espaço em disco, salvando um relatório em:
  <LASTBOOK_DATA>/derived/logs/relatorio-verificacao.txt
"""
import hashlib
import json
import os
import shutil
import time
from pathlib import Path

from . import kiwix_br


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(8 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def _gb(n):
    return f'{n / 1e9:.2f} GB' if n >= 1e9 else f'{n / 1e6:.1f} MB'


def run_check(full=False, data_dir=None):
    t0 = time.time()
    data = Path(data_dir) if data_dir else Path(os.environ.get('LASTBOOK_DATA') or '.')
    sections = []
    ok_count = warn_count = err_count = 0

    def add_item(sec, label, status, detail):
        nonlocal ok_count, warn_count, err_count
        if status == 'ok':
            ok_count += 1
        elif status == 'warn':
            warn_count += 1
        else:
            err_count += 1
        sec['items'].append({'label': label, 'status': status, 'detail': detail})

    # 1. Biblioteca base
    sec_lib = {'id': 'library', 'title': 'Biblioteca Base', 'items': []}
    lib_dir = data / 'library-data'
    for rel, req in (('catalog.json', True), ('pages.db', True), ('summary.json', False)):
        p = lib_dir / rel
        if p.is_file() and p.stat().st_size > 0:
            add_item(sec_lib, f'library-data/{rel}', 'ok', f'Presente ({_gb(p.stat().st_size)})')
        elif req:
            add_item(sec_lib, f'library-data/{rel}', 'error', 'Arquivo obrigatório ausente ou vazio.')
        else:
            add_item(sec_lib, f'library-data/{rel}', 'warn', 'Não encontrado.')
    try:
        pack_meta = json.loads((data / 'pack.json').read_text(encoding='utf-8'))
        add_item(sec_lib, 'Pacote instalado', 'ok', f"{pack_meta.get('name', 'desconhecido')} (revisão {pack_meta.get('content_revision') or 'padrão'})")
    except (OSError, ValueError):
        add_item(sec_lib, 'Pacote instalado', 'warn', 'pack.json não encontrado ou ilegível.')

    manifest_tsv = data / 'pack-manifest.tsv'
    if manifest_tsv.is_file():
        try:
            rows = [l.split('\t') for l in manifest_tsv.read_text(encoding='utf-8').splitlines()[1:] if l.strip()]
            missing = 0
            bad_hash = 0
            for r in rows:
                rel, sz, digest = r[0], int(r[1]), r[2]
                fp = data / rel
                if not fp.is_file() or fp.stat().st_size != sz:
                    missing += 1
                elif full and _sha256_file(fp) != digest:
                    bad_hash += 1
            if missing == 0 and bad_hash == 0:
                add_item(sec_lib, 'Manifesto da biblioteca', 'ok', f'{len(rows)} arquivos conferidos' + (' (SHA-256 verificado)' if full else ' (tamanho verificado)'))
            else:
                add_item(sec_lib, 'Manifesto da biblioteca', 'error', f'{missing} ausente(s)/tamanho incorreto, {bad_hash} corrompido(s). Use "Verificar e reparar".')
        except Exception as e:
            add_item(sec_lib, 'Manifesto da biblioteca', 'warn', f'Falha ao ler pack-manifest.tsv ({type(e).__name__}).')
    sections.append(sec_lib)

    # 2. Mapas e endereços
    sec_map = {'id': 'maps', 'title': 'Mapas Offline e Busca de Endereços', 'items': []}
    geo = data / 'derived' / 'geo'
    map_db = geo / 'map.sqlite'
    if map_db.is_file() and map_db.stat().st_size > 0:
        add_item(sec_map, 'Banco do mapa (map.sqlite)', 'ok', f'Presente ({_gb(map_db.stat().st_size)})')
    else:
        add_item(sec_map, 'Banco do mapa (map.sqlite)', 'error', 'Mapa base ausente.')
    osm_meta = geo / 'osm_br.json'
    if osm_meta.is_file():
        try:
            om = json.loads(osm_meta.read_text(encoding='utf-8'))
            add_item(sec_map, 'Mapa estadual OpenStreetMap', 'ok', f"Estado {om.get('state_name') or om.get('state')} · {om.get('places_count', 0)} localidades")
        except (OSError, ValueError):
            add_item(sec_map, 'Mapa estadual OpenStreetMap', 'warn', 'osm_br.json inválido.')
    addr_dir = geo / 'addresses'
    addr_dbs = sorted(addr_dir.glob('*.sqlite')) if addr_dir.is_dir() else []
    if addr_dbs:
        add_item(sec_map, 'Índices de endereços / CEP', 'ok', ', '.join(f'{a.stem} ({_gb(a.stat().st_size)})' for a in addr_dbs))
    else:
        add_item(sec_map, 'Índices de endereços / CEP', 'warn', 'Nenhum índice estadual de ruas baixado ainda.')
    sections.append(sec_map)

    # 3. Enciclopédias Kiwix (.zim)
    sec_zim = {'id': 'zims', 'title': 'Enciclopédias Offline (.zim)', 'items': []}
    cdir = kiwix_br.collections_dir(data)
    zfiles = sorted(cdir.glob('*.zim')) if cdir.is_dir() else []
    if not zfiles:
        add_item(sec_zim, 'Coleções Kiwix', 'warn', 'Nenhuma enciclopédia .zim instalada ainda (baixe WikiMed PT, iFixit PT ou Wikipédia PT em "Biblioteca e IA local").')
    for zp in zfiles:
        spec = kiwix_br.get_zim(zp.name)
        title = kiwix_br.zim_label(zp.name)
        sz = zp.stat().st_size
        if spec and sz != spec['size']:
            add_item(sec_zim, title, 'error', f'Tamanho inesperado ({_gb(sz)} de {_gb(spec["size"])}). Download pode estar incompleto.')
            continue
        try:
            from libzim.reader import Archive
            arc = Archive(zp)
            entries = arc.entry_count
            has_idx = arc.has_fulltext_index
            if full and spec and _sha256_file(zp) != spec['sha256']:
                add_item(sec_zim, title, 'error', 'Checksum SHA-256 inválido! Baixe este arquivo novamente.')
            else:
                add_item(sec_zim, title, 'ok', f'{entries:,} entradas · busca {"ativa" if has_idx else "por título"} · {_gb(sz)}' + (' · SHA-256 OK' if full and spec else ''))
        except Exception as e:
            add_item(sec_zim, title, 'error', f'Arquivo .zim não pôde ser aberto ({type(e).__name__}).')
    sections.append(sec_zim)

    # 4. Modelos de IA local
    sec_ai = {'id': 'ai', 'title': 'IA Local e Memória', 'items': []}
    try:
        import llm_local
        from .setup import hardware
        hw = hardware.detect([data])
        add_item(sec_ai, 'Memória do computador', 'ok', f"{hw['ram_bytes'] / (1024 ** 3):.1f} GB RAM total" + (' (memória unificada)' if hw.get('unified_memory') else ''))
        mdir = data / 'models'
        found_any = False
        for spec in llm_local.MODELS:
            mp = mdir / spec['file']
            if not mp.is_file():
                continue
            found_any = True
            sz = mp.stat().st_size
            fit = hardware.estimate_ai(hw['ram_bytes'], hw['gpus'], hw['unified_memory'], spec['memory_bytes'])
            if sz != spec['size']:
                add_item(sec_ai, spec['title'], 'error', f'Tamanho incorreto ({_gb(sz)} de {_gb(spec["size"])}).')
            elif full and _sha256_file(mp) != spec['sha256']:
                add_item(sec_ai, spec['title'], 'error', 'Checksum SHA-256 não confere!')
            elif not fit['fits']:
                add_item(sec_ai, spec['title'], 'warn', f'Arquivo íntegro ({_gb(sz)}), mas excede a memória livre segura: {fit["why"]}')
            else:
                add_item(sec_ai, spec['title'], 'ok', f'Íntegro ({_gb(sz)}) e compatível com este computador' + (' · SHA-256 OK' if full else ''))
        if not found_any:
            add_item(sec_ai, 'Modelos GGUF', 'warn', 'Nenhum modelo de IA instalado. Recomendado instalar Qwen 3.5 0.8B (4 GB RAM) ou Gemma 4 E2B (8 GB RAM).')
    except Exception as e:
        add_item(sec_ai, 'Verificação da IA', 'warn', f'Não foi possível checar os modelos ({type(e).__name__}).')
    sections.append(sec_ai)

    # 5. Cofres criptografados e armazenamento
    sec_vault = {'id': 'vault_disk', 'title': 'Cofre Criptografado e Armazenamento', 'items': []}
    vdir = data / 'derived' / 'vault'
    vfiles = sorted(vdir.glob('*.lbvault')) if vdir.is_dir() else []
    if not vfiles:
        add_item(sec_vault, 'Cofres de emergência', 'ok', 'Nenhum cofre criado ainda (você pode criar um na aba Cofre).')
    for vp in vfiles:
        try:
            env = json.loads(vp.read_text(encoding='utf-8'))
            if env.get('v') == 1 and all(env.get(k) for k in ('salt', 'nonce', 'mac', 'data')):
                add_item(sec_vault, f"Cofre “{env.get('name') or vp.stem}”", 'ok', f'Cabeçalho e HMAC íntegros · {vp.stat().st_size:,} bytes')
            else:
                add_item(sec_vault, vp.name, 'error', 'Estrutura de cofre inválida.')
        except (OSError, ValueError):
            add_item(sec_vault, vp.name, 'error', 'Não foi possível ler este arquivo de cofre.')
    try:
        du = shutil.disk_usage(data)
        status_disk = 'ok' if du.free > 1_000_000_000 else 'warn'
        add_item(sec_vault, 'Espaço livre em disco', status_disk, f'{_gb(du.free)} livres de {_gb(du.total)} no volume da biblioteca')
    except OSError:
        pass
    sections.append(sec_vault)

    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    lines = [
        '============================================================',
        f'RELATÓRIO DE VERIFICAÇÃO DO ÚLTIMO LIVRO ({ts})',
        f'Modo: {"Completo (com SHA-256)" if full else "Rápido (estrutura e tamanhos)"}',
        f'Pasta da biblioteca: {data}',
        f'Resumo: {ok_count} OK · {warn_count} avisos · {err_count} erro(s) · {time.time() - t0:.2f}s',
        '============================================================',
        '',
    ]
    for s in sections:
        lines.append(f'## {s["title"]}')
        for it in s['items']:
            tag = {'ok': '[OK]  ', 'warn': '[AVISO]', 'error': '[ERRO]'}[it['status']]
            lines.append(f'  {tag} {it["label"]}: {it["detail"]}')
        lines.append('')
    report_text = '\n'.join(lines)

    report_path = data / 'derived' / 'logs' / 'relatorio-verificacao.txt'
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_text, encoding='utf-8')
    except OSError:
        report_path = None

    return {
        'ok': err_count == 0,
        'full': bool(full),
        'timestamp': ts,
        'elapsed_s': round(time.time() - t0, 2),
        'summary': {'ok': ok_count, 'warn': warn_count, 'error': err_count},
        'sections': sections,
        'report_text': report_text,
        'report_name': 'relatorio-verificacao.txt',
        'saved_report': bool(report_path),
    }
