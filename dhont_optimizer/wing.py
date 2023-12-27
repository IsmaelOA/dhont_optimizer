# Definition of Wing class

from ortools.linear_solver import pywraplp

class Wing:

    def __init__(self, name, model):
        self.name = name
        self.model = model
        self.solver = model.solver

        self.wings_data = self.model.wings_data
        self.my_data = self.wings_data.get(name)
        self.my_votes = self.my_data.get('votes')
        self.my_parties = self.my_data.get('parties')
        self.total_votes = self.model.total_votes
        self.other_votes = self.total_votes - self.my_votes
        self.other_wings = [w for w in self.model.wings_names if w != name]
        self.num_seats = model.num_seats

        self.province = model.province # Added in version 1.1

        # Variables (declared as private attributes to be called by methods, initially undefined)

        self.__votes = None # Final number of votes
        self.__delta_pos_votes_by_wing = {} # Votes that are gained from other wings
        self.__delta_neg_votes_by_wing = {} # Votes that are lost to other wings
        self.__seats = {} # Final number of seats

        # Generate the variables in the model

        self.generate_variables()

    # Representation of the wing:

    def __str__(self):
        wing_str = f'Wing {self.name} - Parties:\n'
        for p in self.my_data.get('parties'):   
            wing_str += f" | {p}"
        return wing_str

    def __repr__(self):
        return self.__str__()

    # Definition of variables

    def votes_var(self):
        if not self.__votes:
            self.__votes = self.solver.NumVar(0, self.total_votes, f'votes_{self.name}_{self.province}')
        return self.__votes

    def delta_pos_votes_by_wing_var(self, other_wing):
        if not other_wing in self.__delta_pos_votes_by_wing:
            other_wing_votes = self.wings_data.get(other_wing).get('votes')
            self.__delta_pos_votes_by_wing[other_wing] = self.solver.NumVar(0, other_wing_votes, f'delta_pos_{self.name}_{other_wing}_{self.province}')
        return self.__delta_pos_votes_by_wing[other_wing]

    def delta_neg_votes_by_wing_var(self, other_wing):
        if not other_wing in self.__delta_neg_votes_by_wing:
            self.__delta_neg_votes_by_wing[other_wing] = self.solver.NumVar(0, self.my_votes, f'delta_neg_{self.name}_{other_wing}_{self.province}')
        return self.__delta_neg_votes_by_wing[other_wing]

    def seats_var(self):
        if not self.__seats:
            self.__seats = self.solver.IntVar(0, self.num_seats, f'seats_{self.name}_{self.province}')
        return self.__seats

    # Creation of the variables in the model

    def generate_variables(self):
        self.votes_var()
        self.seats_var()

        for w in self.other_wings:
            self.delta_neg_votes_by_wing_var(w)
            self.delta_pos_votes_by_wing_var(w)

