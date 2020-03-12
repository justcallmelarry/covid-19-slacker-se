import json
import os.path

import httpx
import redis

DIRPATH = os.path.join(os.path.dirname(__file__))


def main(settings: dict) -> None:
    slack_webhook = settings.get("slack_webhook")
    slack_channel = settings.get("slack_channel")
    data_url = settings.get("data_url")

    db = redis.Redis(host="localhost", port=6379, db=0)

    raw_db_total = db.get("covid-19:total")
    raw_db_stockholm = db.get("covid-19:stockholm")
    raw_db_yesterday = db.get("covid-19:yesterday")

    db_total = int(raw_db_total.decode()) if raw_db_total else 0
    db_stockholm = int(raw_db_stockholm.decode()) if raw_db_stockholm else 0
    db_yesterday = int(raw_db_yesterday.decode()) if raw_db_stockholm else 0

    data = httpx.get(data_url).json()

    total = data.get("total")

    for place in data.get("data", []):
        area_count = place.get("antal")
        if place.get("kod") == "01":
            break

    if total == db_total:
        return

    message = f"{total} bekräftat smittade i Sverige"
    if db_total:
        message += f" ({total - db_total} nya sedan förra uppdateringen)"

    message += f"\nVarav {area_count} i Stockholm"

    new_sthlm = area_count - db_stockholm
    if db_stockholm and new_sthlm:
        message += f" ({new_sthlm} nya sedan förra uppdateringen)"

    if total - db_yesterday > 0:
        message += f"\n\nHittills {total - db_yesterday} nya fall rapporterade idag"

    payload = {
        "username": "New and Improved CoronaBot",
        "text": message,
        "channel": slack_channel,
        "icon_emoji": ":biohazard_sign:",
    }

    response = httpx.post(slack_webhook, data=json.dumps(payload))

    db.set("covid-19:total", total)
    db.set("covid-19:stockholm", area_count)

    if response.status_code != 200:
        print(response.text())


if __name__ == "__main__":
    with open(os.path.join(DIRPATH, "config.json")) as config_file:
        settings = json.load(config_file)

    main(settings)
