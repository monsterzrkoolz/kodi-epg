# Kodi EPG — English-first CA/US

This repository publishes a daily customized IPTV-org North America playlist and matching XMLTV guide.

## Add files to GitHub

Replace `.github/workflows/update-epg.yml` and `scripts/build.py` with the copies in this package. Commit both to `main` preserving their directories. GitHub Pages **Source** should be set to **GitHub Actions**. Open the **Actions** tab, select **Update Kodi Playlist and EPG**, and choose **Run workflow**. Wait for successful deployment.

## Kodi URLs

- Playlist: https://monsterzrkoolz.github.io/kodi-epg/channels.m3u
- EPG: https://monsterzrkoolz.github.io/kodi-epg/guide.xml
- Coverage: https://monsterzrkoolz.github.io/kodi-epg/status.json
- Per-channel CSV: https://monsterzrkoolz.github.io/kodi-epg/coverage.csv

## Notes

- English-first is a heuristic based on the regional playlist and channel names. Some French-language or other non-English stations may remain.
- No source can guarantee EPG for every available stream. Channels with no matching source retain their streams, but have no programme listing.
- This does not add pay-TV streams or validate stream playback availability.
- Failed individual guide sources are skipped; **no valid merged programmes means the run fails**, avoiding publishing an empty guide. Existing GitHub Pages deployment remains available.
- Source EPG definitions are read from IPTV-org on every run, not hard-coded to outdated channel IDs.
- Some EPG providers may block GitHub-hosted scrapers or need special configurations; GitHub Actions logs and status.json will show actual results.
- If the daily workflow exceeds the run duration, reduce the SOURCES list in scripts/build.py. The 750-second per-site timeout means large jobs can take a while.
