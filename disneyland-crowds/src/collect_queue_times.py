"""Archive ride-level Disneyland wait times from the free Queue-Times API (attribution required: "Powered by Queue-Times.com").
Run every 5-15 minutes (cron, fly.io machine, or a scheduled GitHub Action) to build the daily/hourly history the public
crowd-calendar pages only expose as one noisy number per day.   NOTE: written offline, not yet run against the live API.
Usage: python collect_queue_times.py [park_id ...]     (16 = Disneyland Park, 17 = Disney California Adventure)
"""
import sys, json, csv, os, datetime as dt, urllib.request
OUT = os.path.join(os.path.dirname(__file__), '..', 'data', 'ride_waits')
def fetch(park):
    req = urllib.request.Request(f'https://queue-times.com/parks/{park}/queue_times.json', headers={'User-Agent': 'personal-crowd-archive'})
    with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)
def main(parks):
    os.makedirs(OUT, exist_ok=True); now = dt.datetime.now(dt.timezone.utc)
    for park in parks:
        j = fetch(park); rides = [dict(r, land=l.get('name', '')) for l in j.get('lands', []) for r in l.get('rides', [])] + [dict(r, land='') for r in j.get('rides', [])]
        path = os.path.join(OUT, f'park{park}_{now:%Y-%m}.csv'); new = not os.path.exists(path)
        with open(path, 'a', newline='') as f:
            w = csv.writer(f)
            if new: w.writerow(['fetched_utc', 'ride_id', 'ride', 'land', 'is_open', 'wait_min', 'last_updated'])
            for r in rides: w.writerow([now.isoformat(timespec='seconds'), r.get('id'), r.get('name'), r['land'], r.get('is_open'), r.get('wait_time'), r.get('last_updated')])
        print(park, len(rides), 'rides ->', path)
if __name__ == '__main__': main(sys.argv[1:] or ['16', '17'])
