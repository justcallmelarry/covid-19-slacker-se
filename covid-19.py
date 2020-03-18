import json
import os.path
import sys

import httpx
import redis
from bs4 import BeautifulSoup

DIRPATH = os.path.join(os.path.dirname(__file__))


def main(settings: dict, force: bool) -> None:
    slack_webhook = settings.get("slack_webhook")
    slack_channel = settings.get("slack_channel")
    data_url = settings.get("data_url")

    db = redis.Redis(host="localhost", port=6379, db=0)

    raw_db_current = db.get("covid-19:current")
    raw_db_yesterday = db.get("covid-19:yesterday")

    db_current = json.loads(raw_db_current.decode()) if raw_db_current else {}
    db_yesterday = json.loads(raw_db_yesterday.decode()) if raw_db_yesterday else {}

    if not isinstance(db_yesterday, dict):
        db_yesterday = {}

    data = httpx.get(data_url).text

    page = BeautifulSoup(data, "html.parser")

    infected = int(page.find("span", {"class": "text-danger"}).text)
    # cured = int(page.find("span", {"class": "text-success"}).text)
    deaths = int(page.find("span", {"class": "text-dark"}).text)

    if all(
        [
            infected <= db_current.get("infected", 0),
            deaths <= db_current.get("deaths", 0),
            not force,
        ]
    ):
        return

    message = f"{infected} bekräftat smittade i Sverige"

    diff_infected = infected - db_current.get("infected", 0)
    if diff_infected:
        message += f" ({diff_infected} sedan förra uppdateringen)"

    message += f"\nDet har totalt rapporterats {deaths} dödsfall"

    diff_deaths = deaths - db_current.get("deaths", 0)
    if diff_deaths:
        message += f" ({diff_deaths} sedan förra uppdateringen)"

    infected_today = infected - db_yesterday.get("infected", 0)
    deaths_today = deaths - db_yesterday.get("deaths", 0)
    message += (
        f"\n\nHittills {infected_today} nya fall och {deaths_today} dödsfall rapporterade idag"
    )

    payload = {
        "username": "COVID-19",
        "text": message,
        "channel": slack_channel,
        "icon_emoji": ":biohazard_sign:",
    }

    response = httpx.post(slack_webhook, data=json.dumps(payload))

    db.set("covid-19:current", json.dumps({"infected": infected, "deaths": deaths}))

    if response.status_code != 200:
        print(response.text())


if __name__ == "__main__":
    with open(os.path.join(DIRPATH, "config.json")) as config_file:
        settings = json.load(config_file)

    force = True if "-f" in sys.argv else False

    main(settings, force)
