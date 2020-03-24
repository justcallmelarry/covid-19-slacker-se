import json
import os.path
import sys
from dataclasses import dataclass

import httpx
import redis
from bs4 import BeautifulSoup

DIRPATH = os.path.join(os.path.dirname(__file__))


@dataclass
class Covid19:
    deaths: int
    infected: int
    deaths_updated: int
    infected_updated: int
    deaths_today: int
    infected_today: int

    force: bool = False

    def has_updates(self) -> bool:
        return any([self.deaths_updated, self.infected_updated, force])


def slack_message(settings: dict, data: Covid19) -> None:
    slack_webhook = settings.get("slack_webhook")
    slack_channel = settings.get("slack_channel")

    messages = []

    if data.infected_updated:
        f"{data.infected_updated} rapporterade fall"

    if data.deaths_updated:
        f"{data.deaths_updated} dödsfall"

    message = " och ".join(messages) + "sedan förra uppdateringen"

    payload = {
        "link_names": 1,
        "username": "COVID-19",
        "channel": slack_channel,
        "icon_emoji": ":biohazard_sign:",
        "attachments": [
            {
                "title": "Nya uppdateringar",
                "text": message,
                "fields": [
                    {"title": "Rapporterade fall totalt", "value": f"{data.infected}", "short": True},
                    {"title": "Dödsfall totalt", "value": f"{data.deaths}", "short": True},
                    {"title": "Rapporterade fall idag", "value": f"{data.infected_today}", "short": True},
                    {"title": "Dödsfall idag", "value": f"{data.deaths_today}", "short": True},
                ],
            }
        ],
    }

    response = httpx.post(slack_webhook, data=json.dumps(payload))
    if response.status_code != 200:
        print(response.text())


def main(settings: dict, force: bool) -> None:
    data_url = settings.get("data_url")

    db = redis.Redis(host="localhost", port=6379, db=0)

    raw_db_current = db.get("covid-19:current")
    raw_db_yesterday = db.get("covid-19:yesterday")

    db_current = json.loads(raw_db_current.decode()) if raw_db_current else {}
    db_yesterday = json.loads(raw_db_yesterday.decode()) if raw_db_yesterday else {}

    if not isinstance(db_yesterday, dict):
        db_yesterday = {}

    response = httpx.get(data_url).text

    page = BeautifulSoup(response, "html.parser")

    infected = int(page.find("span", {"class": "text-danger"}).text)
    # cured = int(page.find("span", {"class": "text-success"}).text)
    deaths = int(page.find("span", {"class": "text-dark"}).text)

    data = Covid19(
        infected=int(page.find("span", {"class": "text-danger"}).text),
        deaths=int(page.find("span", {"class": "text-dark"}).text),
        infected_updated=infected - db_current.get("infected", 0),
        deaths_updated=deaths - db_current.get("deaths", 0),
        infected_today=infected - db_yesterday.get("infected", 0),
        deaths_today=deaths - db_yesterday.get("deaths", 0)
    )

    if force:
        data.force = True

    if not data.has_updates():
        return

    slack_message(settings, data)

    db.set("covid-19:current", json.dumps({"infected": infected, "deaths": deaths}))


if __name__ == "__main__":
    with open(os.path.join(DIRPATH, "config.json")) as config_file:
        settings = json.load(config_file)

    force = True if "-f" in sys.argv else False

    main(settings, force)
