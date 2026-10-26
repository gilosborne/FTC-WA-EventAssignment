import random

import file_utils
import print_utils

from model.preferences import Preferences


TEAM_FILE = "./data/2023-2024-teams.csv"
LEAGUE_FILE = "./data/2024-2025-events.csv"
PREFERENCES_FILE = "./data/2024-2025-temp-preferences.csv"
HOME_LEAGUE_ASSIGNMENT_FILE = "./data/2024-2025-temp-home-assignments.csv"
FINAL_ASSIGNMENT_FILE = "./output/final_league_assigments.csv"
FINAL_ASSIGNMENT_MAP_FILE = "./output/final_league_map.csv"
RANDOMIZATION_SEED = 2024

# Import Teams
teams = file_utils.load_teams_from_file(TEAM_FILE)
team_map = {}
for team in teams:
    team_map[team.number] = team

# Import Events
leagues = file_utils.load_leagues_from_file(LEAGUE_FILE)
league_map = {}
for league in leagues:
    league_map[league.name] = league

# Import Home League Assignments and Assign Teams
# Assumed file format is "League Name,Team Number"
team_to_home_league_map = {}
with open(HOME_LEAGUE_ASSIGNMENT_FILE, "r") as file:
    for line in file:
        split = line.strip().split(",")
        league = league_map[split[0]]
        team = team_map[int(split[1])]

        league.add_team(team)
        team_to_home_league_map[team] = league

# Print original league state
print("\n---Home League Distribution---")
print_utils.print_league_summary(leagues)

# Import Event Preferences
# Assumed file format is "Team Number,League Name 1,League Name 2,...,League Name N"
submitted_preferences = []
with open(PREFERENCES_FILE, "r") as file:
    for line in file:
        split = line.strip().split(",")
        team = team_map[int(split[0])]
        preference = Preferences(team)

        for i in range(1, len(split)):
            preference.add_preference(league_map[split[i]])
        submitted_preferences.append(preference)

print("Submitted Preference Lists: " + str(len(submitted_preferences)))

# Remove Preference Teams from Home Leagues
for preference in submitted_preferences:
    home_league = team_to_home_league_map[preference.team]
    home_league.remove_team(preference.team)
    template = "Removed {team} from {league}"
    print(template.format(team=preference.team.number, league=home_league.name))

# Print league state
print("\n---After Removing Preferenced Teams---")
print_utils.print_league_summary(leagues)

# Randomize preference team order
random.Random(RANDOMIZATION_SEED).shuffle(submitted_preferences)

# Iterate through all preference submissions
for preference in submitted_preferences:
    added = False
    print("\nProcessing " + str(preference.team.number) + "...")
    for league in preference.league_preferences:
        if not league.is_full():
            template = "Adding {team} to {league}"
            league.add_team(preference.team)
            added=True
        else:
            template = "Not adding {team} to {league}"
        print(template.format(team=preference.team.number, league=league.name))
        if added:
            break

    # If all unavailable, place back into home league and print warning
    if not added:
        league = team_to_home_league_map[preference.team]
        league.add_team(preference.team)
        template = "All preferences were full, adding {team} back to home league {league}"
        print(template.format(team=preference.team.number, league=league.name))



# Print league state
print("\n---After Processing Preferences---")
print_utils.print_league_summary(leagues)

# Write final assignments to file
file_utils.write_league_assignments_to_file(leagues, FINAL_ASSIGNMENT_FILE)
file_utils.write_league_assignments_to_map_file(leagues, FINAL_ASSIGNMENT_MAP_FILE)