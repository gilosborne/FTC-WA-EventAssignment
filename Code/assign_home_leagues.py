import copy
import random
import sys

from collections import OrderedDict
from typing import List, Tuple
from uszipcode import SearchEngine

import file_utils
import map_utils
import print_utils

from model.league import League
from model.team import Team

NUMBER_OF_ITERATIONS = 100

TEAM_FILE = "./data/2025-2026-teams.csv"
LEAGUE_FILE = "./data/2025-2026-events.csv"
PRE_ASSIGNMENTS_FILE = "./data/2025-2026-pre-assignments.csv"
MAP_OUTPUT_FILE = "./output/25_26_home_league_map.csv"
HOME_LEAGUE_ASSIGNMENT_FILE = "./output/25_26_home_league_assignments.csv"

# 7/28/24 Notes
# At present the Zip Code Assignment appears to produce better results when combined with
# some fiddling on pre-assignments. Some of the standalone 1-2 team zip codes end up mis-assigned
# and need to be manually placed, but the algorithm runs fast enough that doing that is trivial.
# The added bonus is that teams in the same school/zip are automatically kept together
#
# Per-team assignment could yield better results given enough iterations (although the 10-100
# iterations I have done locally score worse), but risks breaking up related teams without adding
# further logic to be able to tie teams together (other than pre-assigning all of them). I'm leaving
# the code here for posterity but expect that we'll move forward with zip-code assignment for now.

def assign_home_leagues_per_zip_code() -> List[League]:
    teams = file_utils.load_teams_from_file(TEAM_FILE)
    leagues = file_utils.load_leagues_from_file(LEAGUE_FILE)

    initial_leagues, initial_teams = assign_pre_allocated_teams(PRE_ASSIGNMENTS_FILE, leagues, teams)

    initial_teams_by_zip = {}
    for team in initial_teams:
        if team.zip_code not in initial_teams_by_zip.keys():
            initial_teams_by_zip[team.zip_code] = []

        initial_teams_by_zip[team.zip_code].append(team)

    # Sort by number of teams in zip, high to low
    sorted_teams_by_zip = OrderedDict(sorted(initial_teams_by_zip.items(), key = lambda x : len(x[1]), reverse=True))

    for zip_code, teams in sorted_teams_by_zip.items():
        min_distance = sys.float_info.max
        closest_league = None

        for league in initial_leagues:
            if league.get_open_capacity() < len(teams):
                continue

            distance = map_utils.calculate_distance_between_team_and_league(teams[0], league)
            if distance < min_distance:
                min_distance = distance
                closest_league = league

        if closest_league is None:
            print("No league available for {zip}".format(zip=zip_code))
        else:
            for team in teams:
                closest_league.add_team(team, min_distance)

    return initial_leagues

def assign_home_leagues_per_team() -> List[League]:
    teams = file_utils.load_teams_from_file(TEAM_FILE)
    leagues = file_utils.load_leagues_from_file(LEAGUE_FILE)

    initial_leagues, initial_teams = assign_pre_allocated_teams(PRE_ASSIGNMENTS_FILE, leagues, teams)

    best_leagues = []
    best_leagues_score = sys.float_info.max

    for i in range(NUMBER_OF_ITERATIONS):
        base_leagues = copy.deepcopy(initial_leagues)
        base_teams = copy.deepcopy(initial_teams)

        random.Random(i).shuffle(base_teams)

        for team in base_teams:
            min_distance = sys.float_info.max
            closest_league = None

            for league in base_leagues:
                if league.is_full():
                    continue

                distance = map_utils.calculate_distance_between_team_and_league(team, league)
                if distance < min_distance:
                    min_distance = distance
                    closest_league = league

            if closest_league is None:
                print("No league available for team {team} in {seed}".format(team=team.number,seed=str(i)))
            else:
                closest_league.add_team(team, min_distance)

        score = 0
        for league in base_leagues:
            score += league.get_sum_of_distances()

        if score < best_leagues_score:
            best_leagues_score = score
            best_leagues = copy.deepcopy(base_leagues)

    return best_leagues

# Returns the leagues with pre-allocated teams added, as well as the list
# of teams that still need to be placed.
def assign_pre_allocated_teams(filename: str, leagues: List[League], teams: List[Team]) -> Tuple[List[League],List[Team]]:
    league_dict = {}
    team_dict = {}

    for league in leagues:
        league_dict[league.name] = league

    for team in teams:
        team_dict[team.number] = team

    with open(filename, "r") as file:
        for line in file:
            if line[0] == "#" or len(line) == 1:
                continue

            split = line.strip().split(",")
            league_name = split[0]
            team_number = int(split[1])

            league_dict[league_name].add_team(team_dict[team_number], 0)
            teams.remove(team_dict[team_number])

    return leagues, teams


league_assignments = assign_home_leagues_per_zip_code()
print_utils.print_league_summary(league_assignments)
file_utils.write_league_assignments_to_file(league_assignments, HOME_LEAGUE_ASSIGNMENT_FILE)
file_utils.write_league_assignments_to_map_file(league_assignments, MAP_OUTPUT_FILE)
