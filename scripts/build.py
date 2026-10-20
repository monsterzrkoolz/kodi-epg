#!/usr/bin/env python3
"""Build an English-first CA/US IPTV playlist and matching XMLTV guide.
Standard-library only; uses upstream IPTV-org playlists/channel definitions.
"""
import argparse
import csv
import gzip
import io
import os
import urllib.parse
import json
import re
import shutil
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'public'
DATA = ROOT / 'work'
BASE = 'https://monsterzrkoolz.github.io/kodi-epg/'
SOURCE = 'https://iptv-org.github.io/iptv/regions/nam.m3u'
ATTR = re.compile(r'([\w-]+)="([^"]*)"')
# Prefer North American sources; others can be added to this list later.
SOURCES = ['tvhebdo.com', 'tvpassport.com', 'tvguide.com', 'tvinsider.com',
           'ontvtonight.com', 'directv.com', 'pluto.tv', 'plex.tv',
           'distro.tv', 'i.mjh.nz', 'epgshare01.online']
IGNORE_CATEGORIES = {'adult', 'religious', 'shopping'}
DIGGZ_CONFIG = ROOT / 'scripts' / 'diggz_sources.json'
DIGGZ_ENABLED = os.environ.get('DIGGZ_ENABLED', '1') != '0'
MAX_DOWNLOAD = 35 * 1024 * 1024
FRENCH = re.compile(r'\b(francais|français|québec|quebec|en français|francophone)\b', re.I)
NEWS = re.compile(r'\b(news|nouvelles|actualités|current affairs)\b', re.I)
SPORTS = re.compile(r'\b(sports?|hockey|nhl|nba|nfl|mlb|curling|soccer|football)\b', re.I)
ALBERTA = re.compile(r'\b(alberta|calgary|edmonton|lethbridge|medicine hat|red deer)\b', re.I)


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'KodiEPG/2.0'})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode('utf-8-sig')


def fetch_bytes(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 KodiEPG/3.0'})
    with urllib.request.urlopen(req, timeout=35) as response:
        data = response.read(MAX_DOWNLOAD + 1)
    if len(data) > MAX_DOWNLOAD:
        raise ValueError('Source exceeds 35 MB download limit')
    return gzip.decompress(data) if data[:2] == b'\x1f\x8b' else data


def diggz_sources():
    if not DIGGZ_ENABLED or not DIGGZ_CONFIG.exists():
        return []
    return json.loads(DIGGZ_CONFIG.read_text(encoding='utf-8'))


def safe_name(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def diggz_id(source, original, name):
    # Keep each provider's channel IDs separate; its guide is rewritten to match.
    # Channels with no tvg-id cannot be safely linked to guide data.
    if not original:
        return ''
    return 'diggz.' + safe_name(source) + '.' + original


def diggz_group(source, group):
    return '08 Diggz - ' + source + ((' - ' + group.strip()) if group.strip() else '')


def entries(text):
    current = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith('#EXTINF:'):
            current = [line]
        elif current and line.startswith('#'):
            current.append(line)
        elif current and line:
            yield current, line
            current = []


def category(name, id_, original):
    canadian = id_.split('@')[0].endswith('.ca') or 'canada' in original.lower()
    if canadian and NEWS.search(name + ' ' + original):
        if ALBERTA.search(name + ' ' + original):
            return '01 Alberta News'
        return '02 Canadian News'
    if canadian and SPORTS.search(name + ' ' + original):
        return '03 Canadian Sports'
    if SPORTS.search(name + ' ' + original):
        return '04 US & Other Sports'
    if NEWS.search(name + ' ' + original):
        return '05 US & Other News'
    if canadian:
        return '06 Canadian TV'
    return '07 American TV'


def playlist():
    PUBLIC.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)
    selection = []
    for ext, stream in entries(fetch(SOURCE)):
        inf = ext[0]
        if ',' not in inf: continue
        name = inf.split(',', 1)[1].strip()
        attrs = dict(ATTR.findall(inf))
        cid = attrs.get('tvg-id', '')
        original = attrs.get('group-title', '')
        # Region playlist can contain bilingual and non-English stations. This
        # is an English-first heuristic, not a verified language classification.
        if FRENCH.search(name) or original.lower() in IGNORE_CATEGORIES:
            continue
        grp = category(name, cid, original)
        pre = re.sub(r'\s*group-title="[^"]*"', '', inf.split(',', 1)[0])
        rewritten = f'{pre} group-title="{grp}",{name}'
        selection.append((grp, name.casefold(), cid, name, [rewritten] + ext[1:] + [stream]))
    diggz_report = {}
    for source in diggz_sources():
        label = source['name']
        try:
            raw = fetch_bytes(source['m3u']).decode('utf-8-sig', errors='replace')
            if not raw.lstrip().startswith('#EXTM3U'):
                raise ValueError('Response is not an M3U playlist')
            count = 0
            for ext, stream in entries(raw):
                inf = ext[0]
                if ',' not in inf:
                    continue
                name = inf.split(',', 1)[1].strip()
                attrs = dict(ATTR.findall(inf))
                original = attrs.get('group-title', '')
                if FRENCH.search(name) or any(x in original.lower() for x in IGNORE_CATEGORIES):
                    continue
                if not stream.startswith(('http://', 'https://', 'plugin://', 'rtmp://', 'rtsp://')):
                    continue
                cid = diggz_id(label, attrs.get('tvg-id', ''), name)
                group = diggz_group(label, original)
                pre = inf.split(',', 1)[0]
                pre = re.sub(r'\s*(?:group-title|tvg-id)="[^"]*"', '', pre)
                pre += ' group-title="' + group.replace('"', '') + '"'
                if cid:
                    pre += ' tvg-id="' + cid.replace('"', '') + '"'
                selection.append((group, name.casefold(), cid, name, [pre + ',' + name] + ext[1:] + [stream]))
                count += 1
            diggz_report[label] = {'streams': count, 'status': 'ok'}
        except Exception as e:
            print(f'Diggz playlist {label} skipped: {e}')
            diggz_report[label] = {'streams': 0, 'status': str(e)[:200]}
    (DATA/'diggz_status.json').write_text(json.dumps(diggz_report, indent=2), encoding='utf-8')
    selection.sort(key=lambda x: (x[0], x[1]))
    lines = ['#EXTM3U url-tvg="' + BASE + 'guide.xml"']
    unique = {}
    for grp, _, cid, name, parts in selection:
        lines.extend(parts)
        if cid:
            unique.setdefault(cid, {'channel_id': cid, 'name': name, 'group': grp})
    (PUBLIC/'channels.m3u').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    (DATA/'channels.json').write_text(json.dumps(unique, indent=2), encoding='utf-8')
    print(f'Playlist: {len(selection)} streams, {len(unique)} IDs, {Counter(x[0] for x in selection)}')
    if len(selection) < 100:
        raise RuntimeError('Unusually small playlist; refusing to deploy')


def prepare():
    channels = json.loads((DATA/'channels.json').read_text())
    epgdir = ROOT/'epg'/'sites'
    DATA.mkdir(exist_ok=True)
    # The guide repo lists source-specific channel IDs. Make a small custom
    # file for each provider, with exact xmltv_id matching our playlist.
    total = 0
    report = {}
    for site in SOURCES:
        definitions = list((epgdir/site).glob('*.channels.xml'))
        if not definitions:
            print(f'Skip {site}: no channels XML found')
            continue
        found = {}
        for xml in definitions:
            try:
                root = ET.parse(xml).getroot()
            except ET.ParseError:
                continue
            for ch in root.findall('channel'):
                cid = ch.get('xmltv_id', '')
                if cid not in channels or not ch.get('site_id'):
                    continue
                # Prefer English listings while preserving unspecified language.
                if ch.get('lang', 'en').lower() not in ('en', ''):
                    continue
                found.setdefault((cid, ch.get('site_id')), ch)
        if not found:
            print(f'Skip {site}: no matched channels')
            continue
        out = ET.Element('channels')
        for ch in found.values():
            out.append(ch)
        ET.ElementTree(out).write(DATA/f'{site}.channels.xml', encoding='utf-8', xml_declaration=True)
        report[site] = len(found)
        total += len(found)
    (DATA/'sources.json').write_text(json.dumps(report, indent=2))
    print('EPG candidates:', report, 'total:', total)
    if not report:
        raise RuntimeError('No matching provider definitions found')


def merge():
    channels = json.loads((DATA/'channels.json').read_text())
    allowed = set(channels)
    root = ET.Element('tv', {'generator-info-name': 'kodi-epg'})
    selected = {}
    program_by_channel = defaultdict(dict)
    source_results = {}
    # Site order determines preference where duplicate programme slots exist.
    for site in SOURCES:
        path = DATA/'guides'/f'{site}.xml'
        if not path.exists() or path.stat().st_size == 0:
            continue
        count = 0
        try:
            doc = ET.parse(path).getroot()
        except ET.ParseError as e:
            print(f'Skipping malformed {site}: {e}')
            continue
        for ch in doc.findall('channel'):
            cid = ch.get('id', '')
            if cid in allowed:
                selected.setdefault(cid, ch)
        for pg in doc.findall('programme'):
            cid = pg.get('channel', '')
            if cid not in allowed: continue
            # Retain complementary listings but do not duplicate identical slots.
            key = (pg.get('start'), pg.get('stop'))
            if key not in program_by_channel[cid]:
                program_by_channel[cid][key] = pg
                count += 1
        source_results[site] = count
    # Diggz guides use the source's original tvg-id, so namespace IDs on import.
    diggz_epg_report = {}
    for source in diggz_sources():
        label, url = source['name'], source.get('epg', '')
        if not url:
            continue
        try:
            data = fetch_bytes(url)
            doc = ET.fromstring(data)
            if doc.tag != 'tv':
                raise ValueError('Response is not XMLTV')
            mapped = {}
            for ch in doc.findall('channel'):
                old = ch.get('id', '')
                cid = diggz_id(label, old, '')
                if cid in allowed:
                    ch.set('id', cid)
                    selected.setdefault(cid, ch)
                    mapped[old] = cid
            count = 0
            for pg in doc.findall('programme'):
                cid = mapped.get(pg.get('channel', ''))
                if not cid:
                    continue
                pg.set('channel', cid)
                key = (pg.get('start'), pg.get('stop'))
                if key not in program_by_channel[cid]:
                    program_by_channel[cid][key] = pg
                    count += 1
            diggz_epg_report[label] = {'channels_matched': len(mapped), 'programmes': count}
            print(f'Diggz EPG {label}: {len(mapped)} channels, {count} programmes')
        except Exception as e:
            print(f'Diggz EPG {label} skipped: {e}')
            diggz_epg_report[label] = {'error': str(e)[:200]}
    source_results['diggz'] = diggz_epg_report
    epg_ids = {cid for cid, values in program_by_channel.items() if values}
    number = sum(map(len, program_by_channel.values()))
    if number == 0:
        raise RuntimeError('No programmes matched playlist IDs: not publishing an empty guide')
    for cid in sorted(epg_ids):
        root.append(selected.get(cid) or ET.Element('channel', {'id':cid}))
    for cid in sorted(program_by_channel):
        for key in sorted(program_by_channel[cid]):
            root.append(program_by_channel[cid][key])
    PUBLIC.mkdir(exist_ok=True)
    ET.ElementTree(root).write(PUBLIC/'guide.xml', encoding='utf-8', xml_declaration=True)
    rows = []
    for cid, ch in channels.items():
        rows.append({**ch, 'programmes': len(program_by_channel[cid]),
                     'has_epg': bool(program_by_channel[cid])})
    with (PUBLIC/'coverage.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['channel_id','name','group','programmes','has_epg'])
        w.writeheader(); w.writerows(rows)
    status = {'updated_utc':datetime.now(timezone.utc).isoformat(),
              'playlist_channels_with_ids':len(allowed),
              'epg_channels':len(epg_ids), 'programmes':number,
              'coverage_percent':round(100*len(epg_ids)/max(len(allowed), 1), 1),
              'programme_entries_by_source':source_results,
              'missing_epg_channels':len(allowed-epg_ids),
              'channels_by_group':dict(Counter(ch['group'] for ch in channels.values())),
               'diggz_playlists': json.loads((DATA/'diggz_status.json').read_text()) if (DATA/'diggz_status.json').exists() else {}}
    (PUBLIC/'status.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
    (PUBLIC/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><title>Kodi EPG</title>
    <body><h1>Canadian &amp; American Kodi TV</h1><p>Automatically generated playlist and guide.</p>
    <ul><li><a href="channels.m3u">Playlist</a></li><li><a href="guide.xml">TV Guide</a></li>
    <li><a href="status.json">Status</a></li><li><a href="coverage.csv">Channel coverage CSV</a></li></ul></body></html>''',encoding='utf-8')
    print('Final coverage:', status)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['playlist', 'prepare', 'merge'])
    action = ap.parse_args().mode
    {'playlist':playlist,'prepare':prepare,'merge':merge}[action]()
