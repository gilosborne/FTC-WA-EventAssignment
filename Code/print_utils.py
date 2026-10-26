from typing import List

from model.league import League


def print_league_summary(leagues: List[League]):
    template = "{name:15s}{count}/{capacity}"

    for league in leagues:
        print(template.format(name=league.name, count=str(len(league.teams)), capacity=str(league.capacity)))
    print("")
