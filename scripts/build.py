"""Create a CA/US playlist and filter a downloaded XMLTV guide to its IDs.

Standard library only. Input channel lists are supplied by iptv-org/iptv.
"""
from __future__ import annotations
import argparse
import csv
import html
import json
import re
import urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'public'
SOURCE = 'https://iptv-org.github.io/iptv/regions/nam.m3u'
ATTR = re.compile(r'([\w-]+)="([^"]*)"')


def source_text(url: str) -> str:
    req = urllib.request.Request(url, headers={'User-Agent': 'KodiEPG/1.0'})
    with urllib.request.urlopen(req, timeout=90) as response:
        return response.read().decode('utf-8-sig')


def read_channels(text: str):
    lines = text.splitlines()
    entries = []
    current = []
    for line in lines:
        line = line.strip()
        if line.startswith('#EXTINF:'):
            current = [line]
        elif current and line.startswith('#'):
            current.append(line)
        elif current and line:
            entries.append((current, line))
            current = []
    return entries


def group(info: str) -> str:
    metadata = dict(ATTR.findall(info))
    name = info.split(',', 1)[-1].lower()
    original = metadata.get('group-title', '').lower()
    cid = metadata.get('tvg-id', '').lower()
    canadian = cid.endswith('.ca') or 'canada' in original or 'canadian' in name
    news = 'news' in original or re.search(r'\b(news|cbc news|ctv news|global news)\b', name)
    sports = 'sport' in original or re.search(r'\b(sport|nhl|hockey|curling)\b', name)
    alberta = ('alberta' in name or 'calgary' in name or 'edmonton' in name or
               'lethbridge' in name or 'ca-ab' in original)
    if canadian and news and alberta:
        return '01 Canadian & Alberta News'
    if canadian and news:
        return '02 Canadian News'
    if canadian and sports:
        return '03 Canadian Sports'
    if sports:
        return '04 Sports'
    if news:
        return '05 Other News'
    if canadian:
        return '06 Canadian TV'
    return '07 American & Other TV'


def make_playlist():
    PUBLIC.mkdir(parents=True, exist_ok=True)
    text = source_text(SOURCE)
    entries = read_channels(text)
    result = []
    for ext, stream in entries:
        info = ext[0]
        g = group(info)
        # Rewrite only group-title, retaining the channel ID and stream URL.
        info = re.sub(r'\s*group-title="[^"]*"', '', info)
        if ',' not in info:
            continue
        prefix, title = info.split(',', 1)
        info = f'{prefix} group-title="{g}",{title}'
        result.append((g, title.casefold(), ext, info, stream))
    result.sort(key=lambda r: (r[0], r[1]))
    output = ['#EXTM3U url-tvg="https://monsterzrkoolz.github.io/kodi-epg/guide.xml"']
    ids = set()
    for g, title, ext, info, stream in result:
        output.append(info)
        output.extend(ext[1:])
        output.append(stream)
        match = re.search(r'tvg-id="([^"]+)"', info)
        if match and match.group(1):
            ids.add(match.group(1))
    (PUBLIC / 'channels.m3u').write_text('\n'.join(output) + '\n', encoding='utf-8')
    (PUBLIC / 'playlist-ids.json').write_text(json.dumps(sorted(ids)), encoding='utf-8')
    print(f'Built playlist with {len(result)} streams and {len(ids)} distinct channel IDs')


def make_epg():
    PUBLIC.mkdir(parents=True, exist_ok=True)
    allowed = set(json.loads((PUBLIC / 'playlist-ids.json').read_text(encoding='utf-8')))
    src = ROOT / 'downloaded.xml'
    dest = PUBLIC / 'guide.xml'
    root = ET.Element('tv', {'generator-info-name': 'kodi-epg'})
    seen_channels = set()
    programme_count = 0
    if src.exists() and src.stat().st_size > 0:
        try:
            for event, elem in ET.iterparse(src, events=('end',)):
                if elem.tag == 'channel':
                    cid = elem.attrib.get('id', '')
                    if cid in allowed and cid not in seen_channels:
                        seen_channels.add(cid)
                        root.append(elem)
                    else:
                        elem.clear()
                elif elem.tag == 'programme':
                    if elem.attrib.get('channel') in allowed:
                        root.append(elem)
                        programme_count += 1
                    else:
                        elem.clear()
        except ET.ParseError as error:
            print(f'Guide source malformed: {error}')
    if programme_count == 0:
        print('WARNING: No matching programme listings this run; check job logs and source coverage.')
    ET.ElementTree(root).write(dest, encoding='utf-8', xml_declaration=True)
    (PUBLIC / 'status.json').write_text(json.dumps({
        'playlist_channels_with_ids': len(allowed),
        'epg_channels': len(seen_channels),
        'programmes': programme_count
    }, indent=2), encoding='utf-8')
    print(f'EPG: {len(seen_channels)} channels, {programme_count} programmes')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['playlist', 'epg'])
    mode = parser.parse_args().mode
    make_playlist() if mode == 'playlist' else make_epg()
