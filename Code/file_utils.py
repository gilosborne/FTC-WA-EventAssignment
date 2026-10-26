from typing import List
from uszipcode import SearchEngine

from model.league import League
from model.team import Team

def write_league_assignments_to_file(leagues: List[League], filename: str):
    template = "{team_number},{league_name}\n"

    with open(filename, "w") as file:
        for league in leagues:
            league.teams.sort()
            for team in league.teams:
                file.write(template.format(league_name=league.name,team_number=team.number,team_name=team.name,team_zip=team.zip_code))

# Writes all of the leagues out to a Google Maps file format, for import into MyMaps. Allows for easier visualization
def write_league_assignments_to_map_file(leagues: List[League], filename: str):
    maps_template = "\"POINT ({long} {lat})\",{team},{league_name}\n"
    search = SearchEngine()

    with open(filename, "w") as file:
        file.write("WKT,name,League\n")
        for league in leagues:
            league.teams.sort()
            for team in league.teams:
                zip = search.by_zipcode(team.zip_code)
                file.write(maps_template.format(lat=zip.lat,long=zip.lng,league_name=league.name,team=team.number)) 

# Assumes file format "Team Number,Team Name,Team Zip\n"
def load_teams_from_file(filename: str) -> List[Team]:
    teams = []

    with open(filename, "r") as file:
        for line in file:
            split = line.strip().split(",")
            teams.append(Team(int(split[0]), split[2], split[1]))

    return teams

# Assumes File Format "League Name,League Zip,League Capacity\n"
def load_leagues_from_file(filename: str) -> List[League]:
    leagues = []

    with open(filename, "r") as file:
        for line in file:
            split = line.strip().split(",")
            leagues.append(League(split[0], split[1], int(split[2])))

    return leagues