# covid-19-slacker-se

## requirements
`pip install -r requirements.txt`
you also need a redis instance running on localhost on default port (currently no auth)

`config.json` in the same folder
```json
{
    "data_url": "https://www.svt.se/special/articledata/2322/sverige.json",
    "slack_webhook": "https://hooks.slack.com/services/you/webhook/here",
    "slack_channel": "#covid-19-reporting"
}
```


and the cron jobs:
```
CRON_TZ=Europe/Stockholm
59,29 7-23 * * * python /path/to/script/covid-19/covid-19.py
0 0 * * * python /path/to/script/covid-19/covid-19.py
```
