from typing import List

from .team import Team
from .league import League

class Preferences(object):

    def __init__(self, team: Team, preferences: List = []):
        self.team = team
        self.league_preferences = []

    def add_preference(self, league: League):
        self.league_preferences.append(league)