# Kodi EPG — Canadian and American TV

Automatically builds a custom grouped version of [IPTV-org Northern America](https://iptv-org.github.io/iptv/regions/nam.m3u) and attempts to generate a matching XMLTV EPG from supported IPTV-org EPG sources.

## URLs after first GitHub Pages deployment

- Playlist: https://monsterzrkoolz.github.io/kodi-epg/channels.m3u
- EPG: https://monsterzrkoolz.github.io/kodi-epg/guide.xml
- Coverage: https://monsterzrkoolz.github.io/kodi-epg/status.json

## Enable

1. Upload this project's files to your repository, preserving the `.github/workflows/update.yml` path.
2. In **Settings → Pages**, set Source to **GitHub Actions**.
3. In **Actions → Update Kodi Playlist and EPG**, select **Run workflow**.
4. Wait until the workflow succeeds; then open the URL above.

## Coverage notes

EPG data is best-effort. The included initial sources are `tvhebdo.com`, `tvguide.com`, and `watch.sportsnet.ca`. The upstream grabbers can fail or be blocked; consult the Actions logs and status.json. The generated EPG may be empty or partial, and it is not a guarantee every channel has a programme listing. `tvtv.us` is intentionally excluded because the upstream project currently marks it broken. The playlist is based on upstream Northern America; it is not a promise that every stream plays from every location. Categories are heuristics and may need manual tuning.

## Schedule

Daily at 09:17 UTC. Can be run manually from GitHub Actions anytime.
