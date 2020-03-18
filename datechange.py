import redis

if __name__ == '__main__':
    db = redis.Redis(host="localhost", port=6379, db=0)

    raw_db_total = db.get("covid-19:current")

    db.set("covid-19:yesterday", raw_db_total)
