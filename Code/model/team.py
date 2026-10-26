class Team(object):

    def __init__(self, number: int, zip_code: str, name: str = ""):
        self.number = number
        self.zip_code = zip_code
        self.name = name

    def __eq__(self, other):
        if not isinstance(other, Team):
            return NotImplemented

        return self.number == other.number

    def __hash__(self):
        return hash(self.number)

    def __lt__(self, other):
        if not isinstance(other, Team):
            return NotImplemented

        return self.number < other.number
