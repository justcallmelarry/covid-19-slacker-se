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
    icu: int
    infected: int
    stockholm: int

    deaths_updated: int
    icu_updated: int
    infected_updated: int
    stockholm_updated: int

    deaths_today: int
    icu_today: int
    infected_today: int
    stockholm_today: int

    force: bool = False

    def has_updates(self) -> bool:
        return any(
            [
                self.deaths_updated,
                self.infected_updated,
                self.icu_updated,
                self.stockholm and self.stockholm_updated,
                force,
            ]
        )


def slack_error_message(settings: dict, e: Exception) -> None:
    slack_webhook = settings.get("slack_webhook")
    slack_channel = settings.get("slack_error_channel")

    response = httpx.post(
        slack_webhook, data=json.dumps({"text": f"c19 changes: {e}", "channel": slack_channel}),
    )
    if response.status_code != 200:
        print(response.text())


def slack_message(settings: dict, data: Covid19) -> None:
    slack_webhook = settings.get("slack_webhook")
    slack_channel = settings.get("slack_channel")

    fields = []

    infected_value = f"{data.infected}"
    if data.infected_updated:
        infected_value += (
            f" (+{data.infected_updated})"
            if data.infected_updated > 0
            else f" ({data.infected_updated})"
        )

    fields += [
        {"title": "Smittade totalt", "value": infected_value, "short": True},
        {"title": "Smittade idag", "value": f"{data.infected_today}", "short": True},
    ]

    if data.stockholm:
        sthlm_value = f"{data.stockholm}"
        if data.stockholm_updated:
            sthlm_value += (
                f" (+{data.stockholm_updated})"
                if data.stockholm_updated > 0
                else f" ({data.stockholm_updated})"
            )

        fields += [
            {"title": "Stockholm totalt", "value": sthlm_value, "short": True},
            {"title": "Stockholm idag", "value": f"{data.stockholm_today}", "short": True},
        ]

    deaths_value = f"{data.deaths}"
    if data.deaths_updated:
        deaths_value += (
            f" (+{data.deaths_updated})" if data.deaths_updated > 0 else f" ({data.deaths_updated})"
        )

    fields += [
        {"title": "Dödsfall totalt", "value": deaths_value, "short": True},
        {"title": "Dödsfall idag", "value": f"{data.deaths_today}", "short": True},
    ]

    icu_value = f"{data.icu}"
    if data.icu_updated:
        icu_value += f" (+{data.icu_updated})" if data.icu_updated > 0 else f" ({data.icu_updated})"

    fields += [
        {"title": "Intensivvård totalt", "value": icu_value, "short": True},
        {"title": "Intensivvård idag", "value": f"{data.icu_today}", "short": True},
    ]

    payload = {
        "link_names": 1,
        "username": "COVID-19",
        "channel": slack_channel,
        "icon_emoji": ":biohazard_sign:",
        "attachments": [
            {
                "title": "Läget just nu",
                "text": "Alla siffror gäller rapporterade fall",
                "fields": fields,
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

    area_content = page.findAll("div", {"class": "area-content"})
    stockholm = 0

    for area in area_content:
        if area.p and area.p.text == "Fall":
            infected = int(area.h3.text)

        if area.p and area.p.text == "Döda":
            deaths = int(area.h3.text)

        if area.p and area.p.text == "På IVA":
            icu = int(area.h3.text)

        if area.h3 and area.h3.text == "Stockholm":
            stockholm = int(area.find("span", {"class": "total"}).text)

    data = Covid19(
        # totals
        deaths=deaths,
        icu=icu,
        infected=infected,
        stockholm=stockholm,
        # updates
        deaths_updated=deaths - db_current.get("deaths", 0),
        icu_updated=icu - db_current.get("icu", 0),
        infected_updated=infected - db_current.get("infected", 0),
        stockholm_updated=stockholm - db_current.get("stockholm", 0),
        # todays numbers
        deaths_today=deaths - db_yesterday.get("deaths", 0),
        icu_today=icu - db_yesterday.get("icu", 0),
        infected_today=infected - db_yesterday.get("infected", 0),
        stockholm_today=stockholm - db_yesterday.get("stockholm", 0),
    )

    if force:
        data.force = True

    if not data.has_updates():
        return

    slack_message(settings, data)

    db.set(
        "covid-19:current",
        json.dumps(
            {
                "infected": infected,
                "deaths": deaths,
                "icu": icu,
                "stockholm": stockholm if stockholm else db_current.get("stockholm", 0),
            }
        ),
    )


if __name__ == "__main__":
    with open(os.path.join(DIRPATH, "config.json")) as config_file:
        settings = json.load(config_file)

    force = True if "-f" in sys.argv else False

    try:
        main(settings, force)
    except Exception as e:
        slack_error_message(settings, e)
