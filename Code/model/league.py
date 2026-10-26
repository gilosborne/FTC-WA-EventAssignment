from .team import Team

class League(object):
    
    def __init__(self, name: str, zip_code: str, capacity: int = 0):
        self.name = name
        self.zip_code = zip_code
        self.capacity = capacity
        self.teams = []
        self.team_distances = {}


    def add_team(self, team: Team, distance: float = 0):
        self.teams.append(team)
        self.team_distances[team] =distance 

    def remove_team(self, team: Team):
        self.teams.remove(team)
        self.team_distances.pop(team)

    def get_sum_of_distances(self, squared: bool = False):
        total = 0
        for d in self.team_distances.values():
            if squared:
                total += d * d
            else:
                total += d

        return total

    def is_full(self) -> bool:
        return len(self.teams) >= self.capacity

    def get_open_capacity(self) -> int:
        return self.capacity - len(self.teams)

    def __eq__(self, other):
        if not isinstance(other, League):
            return NotImplemented

        return self.name == other.name

    def __hash__(self):
        return hash(self.name)
