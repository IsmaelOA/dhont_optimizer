# Definition of the Party class

from ortools.linear_solver import pywraplp

class Party:

    def __init__(self, name, model):
        self.name = name
        self.model = model
        self.solver = model.solver

        self.parties_data = self.model.parties_data
        self.my_data = self.parties_data.get(name)
        self.my_wing = self.my_data.get('wing')
        self.my_votes = self.my_data.get('votes')
        self.num_seats = self.model.num_seats
        self.total_votes = self.model.total_votes
        self.other_votes = self.total_votes - self.my_votes
        self.other_parties = [p for p in model.parties_names if p!= name]
        self.parties_number = self.model.parties_number

        self.province = model.province # Added in version 1.1
        self.first_contested_seat = model.first_contested_seat # Added in version 1.1
        self.sij = model.lastline_S[self.name] # sij may seem like a strange name, comes from the notation used in the formulation of the problem,
                                               # which will be included in the future documentation

        # Variables (declared as private attributes to be later called by methods, initially undefined)
        # Initially I have declared the variables explicitly used in the solver,
        # in the future further variables may be added for reporting purposes
        
        self.__votes = None # Final number of votes
        self.__delta_pos_votes_by_party = {} # Votes that are gained from other parties
        self.__delta_neg_votes_by_party = {} # Votes that are lost to other parties

        self.__seat_k_is_assigned = {} # Indicator variables that show if seat k is assigned to the party
        self.__seats_before_k = {} # Integer variables that tells how many seats are assigned to the party before the assignment of the k-th seat
        self.__quotient_before_k = {} # "Quotients" associated to the party before the assignment of the k-th seat
        self.__seats_before_k_indicators = {} # Indicator variables that show if the number of seats of the party before the assignment of the k-th seat is exactly m

        self.__partial_wins_indicators = {} # Indicator variables that, for each round k and for each other party, show if the party's associated quotient is bigger or not
                                            # {{},{},...} (structure of this list)
        self.__round_wins_indicators = {} # Sum of partial wins indicators

        self.__seats = None # Integer variable whose value is the number of seats after all rounds are finished

        # Generate the variables in the model

        self.generate_variables()

    # Representation of the party:
    
    def __str__(self):
        return f'Party {self.name} - Wing {self.my_wing}'

    def __repr__(self):
        return self.__str__()

    # Definition of variables

    def votes_var(self):
        if not self.__votes:
            self.__votes = self.solver.NumVar(
                0,
                self.total_votes,
                f'votes_{self.name}_{self.province}'
            )
        return self.__votes
    
    def delta_pos_votes_by_party_var(self, other_party):
        if not other_party in self.__delta_pos_votes_by_party:
            other_party_votes = self.parties_data.get(other_party).get('votes')
            self.__delta_pos_votes_by_party[other_party] = self.solver.NumVar(
                0,
                other_party_votes,
                f'delta_pos_{self.name}_{other_party}_{self.province}'
            )
        return self.__delta_pos_votes_by_party[other_party]
    
    def delta_neg_votes_by_party_var(self, other_party):
        if not other_party in self.__delta_neg_votes_by_party:
            self.__delta_neg_votes_by_party[other_party] = self.solver.NumVar(
                0,
                self.my_votes,
                f'delta_neg_{self.name}_{other_party}_{self.province}'
            )
        return self.__delta_neg_votes_by_party[other_party]

    def seat_k_is_assigned_var(self, k):
        if not k in self.__seat_k_is_assigned:
            self.__seat_k_is_assigned[k] = self.solver.BoolVar(f'seat_{k}_assigned_to_{self.name}_{self.province}')
        return self.__seat_k_is_assigned[k]

    def seats_before_k_var(self, k):
        if not k in self.__seats_before_k:
            self.__seats_before_k[k] = self.solver.IntVar(0, k-1, f'seats_before_{k}_assigned_to_{self.name}_{self.province}')
        return self.__seats_before_k[k]
    
    def quotient_before_k_var(self, k):
        if not k in self.__quotient_before_k:
            self.__quotient_before_k[k] = self.solver.NumVar(0, self.total_votes, f'quotient_before_{k}_for_{self.name}_{self.province}')
        return self.__quotient_before_k[k]

    def seats_before_k_indicators_var(self, k, m):
        if not k in self.__seats_before_k_indicators:
            self.__seats_before_k_indicators[k] = {m: self.solver.BoolVar(f'{m}_seats_before_{k}_assigned_to_{self.name}_{self.province}')}
        elif not m in self.__seats_before_k_indicators[k]:
            self.__seats_before_k_indicators[k][m] = self.solver.BoolVar(f'{m}_seats_before_{k}_assigned_to_{self.name}_{self.province}')
        return self.__seats_before_k_indicators[k][m]

    def partial_wins_indicators_var(self, k, other_party):
        if not k in self.__partial_wins_indicators:
            self.__partial_wins_indicators[k] = {other_party: self.solver.BoolVar(f'{self.name}_wins_{other_party}_in_round_{k}_{self.province}')}
        elif not other_party in self.__partial_wins_indicators[k]:
            self.__partial_wins_indicators[k][other_party] = self.solver.BoolVar(f'{self.name}_wins_{other_party}_in_round_{k}_{self.province}')
        return self.__partial_wins_indicators[k][other_party]

    def round_wins_indicators_var(self, k):
        if not k in self.__round_wins_indicators:
            self.__round_wins_indicators[k] = self.solver.IntVar(0,self.parties_number - 1,f'{self.name}_n_wins_round_{k}_{self.province}')
        return self.__round_wins_indicators[k]

    def seats_var(self):
        if not self.__seats:
            self.__seats = self.solver.IntVar(0, self.num_seats, f'{self.name}_number_of_seats_{self.province}')
        return self.__seats

    # Creation of the variables in the model

    def generate_variables(self):
        self.votes_var()
        self.seats_var()

        for p in self.other_parties:
            self.delta_pos_votes_by_party_var(p)
            self.delta_neg_votes_by_party_var(p)
        
        for k in range(self.first_contested_seat, self.num_seats + 1):
            self.seat_k_is_assigned_var(k)
            self.round_wins_indicators_var(k)
            for p in self.other_parties:
                self.partial_wins_indicators_var(k, p)

        for k in range(self.first_contested_seat + 1, self.num_seats + 1):
            self.seats_before_k_var(k)
            self.quotient_before_k_var(k)
            for m in range(self.sij, k):
                self.seats_before_k_indicators_var(k, m)
    