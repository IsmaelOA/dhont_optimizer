# Definition of the main SeatsModel class and other auxiliary classes

from ortools.linear_solver import pywraplp
import math

from party import Party
from wing import Wing

class ProvinceModel:

    def __init__(self, province, num_seats, parties_data, parties_permeability, wings_permeability, objective_function_weights,
                default_party_permeability = 0, default_wing_permeability = 1,
                default_party_seats_weight = -1, default_wing_seats_weight = -1,
                default_party_movements_weight = -1, default_wing_movements_weight = -1,
                first_contested_seat = 1):
        
        self.num_seats = num_seats
        self.parties_data = parties_data
        self.parties_permeability = parties_permeability
        self.wings_permeability = wings_permeability
        self.objective_function_weights = objective_function_weights
        self.first_contested_seat = first_contested_seat
        self.province = province

        self.default_party_permeability = default_party_permeability
        self.default_wing_permeability = default_wing_permeability
        self.default_party_movements_weight = default_party_movements_weight
        self.default_wing_movements_weight = default_wing_movements_weight
        self.default_party_seats_weight = default_party_seats_weight
        self.default_wing_seats_weight = default_wing_seats_weight

        self.M = 1e6

        # Several derived parameters in the model

        self.total_votes = sum(data.get('votes') for p, data in parties_data.items())

        wings_data = {}
        for p, data in parties_data.items(): # Structured data for wings
            wing = data.get('wing')
            if wing not in wings_data:
                wings_data[wing] = {'parties': [p], 'votes': data.get('votes')}
            else:
                wings_data[wing]['parties'].append(p)
                wings_data[wing]['votes'] += data.get('votes')
        self.wings_data = wings_data

        self.parties_names = [p for p, _ in parties_data.items()]
        self.wings_names = [w for w, _ in wings_data.items()]

        self.parties_number = len(self.parties_names)
        self.wings_number = len(self.wings_names)
        
        # Solver config

        self.solver = pywraplp.Solver.CreateSolver('SCIP')
        self.solver.SetSolverSpecificParametersAsString('display/verblevel 5')

        # Initialize lists

        self.parties = []
        self.wings = []

        # Initial D'Hont distribution

        self.parties_dhont = self.initial_distribution()
        self.wings_dhont = self.initial_distribution_wings()

        # matrix_S, containing information about the required number of seats for each of the n-1 non-disputed rounds

        self.build_S()
        self.lastline_S = self.matrix_S[self.first_contested_seat - 1]

    def initial_distribution(self):
        parties_dhont = {}
        matrix_A = [] # Matrix with information about which party wins each round
        for p in self.parties_names:
            parties_dhont[p] = {"original_votes": self.parties_data[p]["votes"], "quotient": self.parties_data[p]["votes"], "wins": 0, "wing": self.parties_data[p]["wing"]}
        for i in range(0, self.num_seats):
            current_party = self.parties_names[0]
            for comparison_party in self.parties_names[1:]:
                if parties_dhont[current_party]["quotient"] < parties_dhont[comparison_party]["quotient"]:
                    current_party = comparison_party
            A_entry = {p: int(current_party == p) for p in self.parties_names}
            matrix_A.append(A_entry)
            parties_dhont[current_party]["wins"] = parties_dhont[current_party]["wins"] + 1
            parties_dhont[current_party]["quotient"] = parties_dhont[current_party]["original_votes"] / (parties_dhont[current_party]["wins"] + 1)
        self.matrix_A = matrix_A
        return parties_dhont

    def build_S(self):
        matrix_S = [{p:0 for p in self.parties_names}]
        for i in range(1, self.first_contested_seat): # Value self.first_contested_seat will be used for denominators in first iteration of constraints
            S_entry = matrix_S[i - 1].copy()
            A_entry = self.matrix_A[i - 1]
            for p, v in A_entry.items():
                S_entry[p] = S_entry[p] + v
            matrix_S.append(S_entry)
        self.matrix_S = matrix_S

    def initial_distribution_wings(self):
        wings_dhont = {w: {"wins": 0} for w in self.wings_names}
        for p in self.parties_names:
            wings_dhont[self.parties_dhont[p]["wing"]]["wins"] = wings_dhont[self.parties_dhont[p]["wing"]]["wins"] + self.parties_dhont[p]["wins"]
        return wings_dhont

    def create_model(self):
        self.create_parties()
        self.create_wings()
        self.create_constraints()
        self.create_objective()

    def create_parties(self):
        for p in self.parties_names:
            party = Party(p, self)
            self.parties.append(party)
    
    def create_wings(self):
        for w in self.wings_names:
            wing = Wing(w, self)
            self.wings.append(wing)

    def create_constraints(self):
        
        ####################################################################
        # Final votes constraints under > 1 first contested seat condition #
        ####################################################################

        for i in range(0, self.first_contested_seat - 1):
            for p in self.parties:
                if self.matrix_A[i][p.name] == 1:
                    for q in [q for q in self.parties if q.name != p.name]:
                        sip = self.matrix_S[i][p.name]
                        siq = self.matrix_S[i][q.name]
                        self.solver.Add((1/(1 + sip))*p.votes_var() >= (1/(1 + siq))*q.votes_var())

        ###########################
        # Total votes constraints #
        ###########################

        # Sum of votes for all parties = Total votes

        all_parties_votes = [p.votes_var() for p in self.parties]
        self.solver.Add(self.solver.Sum(all_parties_votes) == self.total_votes)

        # Sum of all votes in wing = Total wing votes

        for w in self.wings:
            all_parties_in_wing_votes = [p.votes_var() for p in self.parties if p.my_wing == w.name]
            self.solver.Add(self.solver.Sum(all_parties_in_wing_votes) == w.votes_var())

        #############################
        # Vote movement constraints #
        #############################

        # Relationship between deltas, total final votes and total initial votes (for parties)

        for p in self.parties:
            total_party_deltas = [p.votes_var()]
            for op in self.parties_names:
                if op != p.name:
                    total_party_deltas.append((-1) * p.delta_pos_votes_by_party_var(op))
                    total_party_deltas.append(p.delta_neg_votes_by_party_var(op))
            self.solver.Add(self.solver.Sum(total_party_deltas) == p.my_votes)

        # Relationship between deltas by wings and deltas by parties (positive AND negative)

        for w1 in self.wings:
            for w2 in self.wings:
                if w2.name != w1.name:
                    parties_w1 = [p for p in self.parties if p.my_wing == w1.name]
                    parties_w2 = [q for q in self.parties if q.my_wing == w2.name]
                    total_positive_party_deltas_from_w1_to_w2 = []
                    total_negative_party_deltas_from_w1_to_w2 = []
                    for p in parties_w1:
                        for q in parties_w2:
                            total_positive_party_deltas_from_w1_to_w2.append(p.delta_pos_votes_by_party_var(q.name))
                            total_negative_party_deltas_from_w1_to_w2.append(p.delta_neg_votes_by_party_var(q.name))
                    self.solver.Add(self.solver.Sum(total_positive_party_deltas_from_w1_to_w2) == w1.delta_pos_votes_by_wing_var(w2.name))
                    self.solver.Add(self.solver.Sum(total_negative_party_deltas_from_w1_to_w2) == w1.delta_neg_votes_by_wing_var(w2.name))

        # Relationship between positive and negative deltas by parties

        for p in self.parties:
            for q in self.parties:
                if p.name != q.name:
                    self.solver.Add(p.delta_pos_votes_by_party_var(q.name) == q.delta_neg_votes_by_party_var(p.name))

        ############################
        # Permeability constraints #
        ############################

        for p in self.parties:
            for q in self.parties_names:
                if p.name != q:
                    self.solver.Add(p.delta_neg_votes_by_party_var(q) <= self.parties_permeability.get(p.name).get(q, self.default_party_permeability) * p.my_votes)

        for w1 in self.wings:
            for w2 in self.wings_names:
                if w1.name != w2:
                    self.solver.Add(w1.delta_neg_votes_by_wing_var(w2) <= self.wings_permeability.get(w1.name).get(w2, self.default_wing_permeability) * w1.my_votes)

        ###############################
        # Seat assignment constraints #
        ###############################

        # Partial round wins
        for p in self.parties:
            for q in self.parties:
                if p.name != q.name:
                    # First seat
                    self.solver.Add(p.votes_var()/(1 + self.lastline_S[p.name]) - q.votes_var()/(1 + self.lastline_S[q.name]) >= -self.M*(1 - p.partial_wins_indicators_var(self.first_contested_seat,q.name)))
                    self.solver.Add(p.votes_var()/(1 + self.lastline_S[p.name]) - q.votes_var()/(1 + self.lastline_S[q.name]) <= self.M*p.partial_wins_indicators_var(self.first_contested_seat,q.name))

                    # Rest of seats
                    for k in range(self.first_contested_seat + 1, self.num_seats + 1):
                        self.solver.Add(p.quotient_before_k_var(k) - q.quotient_before_k_var(k) >= -self.M*(1 - p.partial_wins_indicators_var(k,q.name)))
                        self.solver.Add(p.quotient_before_k_var(k) - q.quotient_before_k_var(k) <= self.M*p.partial_wins_indicators_var(k,q.name))
        
        # Round wins
        for p in self.parties:
            for k in range(self.first_contested_seat, self.num_seats + 1):
                self.solver.Add(p.round_wins_indicators_var(k) == self.solver.Sum([p.partial_wins_indicators_var(k,q) for q in self.parties_names if q != p.name]))
        
        # Seat assignments
        for p in self.parties:
            for k in range(self.first_contested_seat, self.num_seats + 1):
                self.solver.Add(p.round_wins_indicators_var(k) - (self.parties_number - 1) >= -self.M * (1 - p.seat_k_is_assigned_var(k)))
        
        for k in range(self.first_contested_seat, self.num_seats + 1):
            self.solver.Add(self.solver.Sum([p.seat_k_is_assigned_var(k) for p in self.parties]) == 1)

        # Seats at the assignment of seat k
        for p in self.parties:
            for k in range(self.first_contested_seat + 1, self.num_seats + 1):
                self.solver.Add(self.solver.Sum([p.seat_k_is_assigned_var(t) for t in range(self.first_contested_seat, k)]) + p.sij == p.seats_before_k_var(k))
        
        # Auxiliary indicator variables of number of seats at the assignment of seat k
        for p in self.parties:
            for k in range(self.first_contested_seat + 1, self.num_seats + 1):
                for m in range(p.sij, k):
                    self.solver.Add(p.seats_before_k_var(k) - m >= - self.M * (1 - p.seats_before_k_indicators_var(k, m)))
                    self.solver.Add(p.seats_before_k_var(k) - m <= self.M * (1 - p.seats_before_k_indicators_var(k, m)))
                # Additional condition for ensuring indicator is 1 when seats_before_k_var(k) == m
                self.solver.Add(self.solver.Sum([p.seats_before_k_indicators_var(k, m) for m in range(p.sij, k)]) == 1)

        # Assignment of quotients
        for p in self.parties:
            for k in range(self.first_contested_seat + 1, k+1):
                for m in range(p.sij,k):
                    self.solver.Add(p.quotient_before_k_var(k) - (1/(m+1))*p.votes_var() >= -self.M*(1 - p.seats_before_k_indicators_var(k,m)))
                    self.solver.Add(p.quotient_before_k_var(k) - (1/(m+1))*p.votes_var() <= self.M*(1 - p.seats_before_k_indicators_var(k,m)))

        # Total seats for each party after all seats are allocated

        for p in self.parties:
            self.solver.Add(self.solver.Sum([p.seat_k_is_assigned_var(k) for k in range(self.first_contested_seat, self.num_seats + 1)]) + p.sij == p.seats_var())

        # Total seats in wing
        for w in self.wings:
            all_parties_in_wing_seats = [p.seats_var() for p in self.parties if p.my_wing == w.name]
            self.solver.Add(self.solver.Sum(all_parties_in_wing_seats) == w.seats_var())

    def create_objective(self):
        obj = self.solver.Objective()
        obj.SetMaximization()

        # Party seats component 
        for p in self.parties:
            obj.SetCoefficient(p.seats_var(), self.objective_function_weights.get("party_seats").get(p.name, self.default_party_seats_weight))

        # Wing seats component
        for w in self.wings:
            obj.SetCoefficient(w.seats_var(), self.objective_function_weights.get("wing_seats").get(w.name, self.default_wing_seats_weight))

        # Party movements component
        for p in self.parties:
            for q in self.parties_names:
                if q != p.name:
                    obj.SetCoefficient(p.delta_neg_votes_by_party_var(q), self.objective_function_weights.get("party_movements").get(p.name).get(q,self.default_party_movements_weight))

        # Wing movements component
        for w1 in self.wings:
            for w2 in self.wings_names:
                if w2 != w1.name:
                    obj.SetCoefficient(w1.delta_neg_votes_by_wing_var(w2), self.objective_function_weights.get("wing_movements").get(w1.name).get(w2,self.default_wing_movements_weight))
    
    def solve_model(self):
        status = self.solver.Solve()
        print(status)
        if status == pywraplp.Solver.OPTIMAL:
            print('Solución encontrada')
            print("Valor de la función objetivo:", self.solver.Objective().Value())
            print("\n")
            for p in self.parties:
                print(p)
                print(p.my_votes, "votos iniciales")
                print(math.floor(p.votes_var().solution_value()), "votos finales")
                print(self.parties_dhont[p.name]["wins"], "escaños iniciales")
                print(int(p.seats_var().solution_value()), "escaños finales")
                print("\n")
            for w in self.wings:
                print(w)
                print(w.my_votes, "votos iniciales")
                print(math.floor(w.votes_var().solution_value()), "votos finales")
                print(self.wings_dhont[w.name]["wins"], "escaños iniciales")
                print(int(w.seats_var().solution_value()), "escaños finales")
                print("\n")
            print("Movimientos de partidos:")
            for p in self.parties:
                for q in self.parties_names:
                    if p.name != q:
                        print("De", p.name, "a", q, p.delta_neg_votes_by_party_var(q).solution_value())
            print("\n")
            print("Movimientos de alas:")
            for p in self.wings:
                for q in self.wings_names:
                    if p.name != q:
                        print("De", p.name, "a", q, p.delta_neg_votes_by_wing_var(q).solution_value())
            print("\n \n \n")

            # Debugging
            # print(self.parties)
        else:
            print('El problema no tiene solución óptima')

class Province:

    def __init__(self, province, solver, num_seats, parties_data, parties_permeability, wings_permeability, objective_function_weights,
                default_party_permeability = 0, default_wing_permeability = 1,
                default_party_seats_weight = -1, default_wing_seats_weight = -1,
                default_party_movements_weight = -1, default_wing_movements_weight = -1,
                first_contested_seat = 1):
        
        self.province = province
        self.solver = solver
        self.num_seats = num_seats
        self.parties_data = parties_data
        self.parties_permeability = parties_permeability
        self.wings_permeability = wings_permeability
        self.objective_function_weights = objective_function_weights
        self.first_contested_seat = first_contested_seat

        self.default_party_permeability = default_party_permeability
        self.default_wing_permeability = default_wing_permeability
        self.default_party_movements_weight = default_party_movements_weight
        self.default_wing_movements_weight = default_wing_movements_weight
        self.default_party_seats_weight = default_party_seats_weight
        self.default_wing_seats_weight = default_wing_seats_weight

        self.M = 1e12

        # Several derived parameters in the model

        self.total_votes = sum(data.get('votes') for p, data in parties_data.items())

        wings_data = {}
        for p, data in parties_data.items(): # Structured data for wings
            wing = data.get('wing')
            if wing not in wings_data:
                wings_data[wing] = {'parties': [p], 'votes': data.get('votes')}
            else:
                wings_data[wing]['parties'].append(p)
                wings_data[wing]['votes'] += data.get('votes')
        self.wings_data = wings_data

        self.parties_names = [p for p, data in parties_data.items()]
        self.wings_names = [w for w, data in wings_data.items()]

        self.parties_number = len(self.parties_names)
        self.wings_number = len(self.wings_names)

        # Initialize lists

        self.parties = []
        self.wings = []

        # Initial D'Hont distribution

        self.parties_dhont = self.initial_distribution()
        self.wings_dhont = self.initial_distribution_wings()

        # matrix_S, containing information about the required number of seats for each of the n-1 non-disputed rounds

        self.build_S()
        self.lastline_S = self.matrix_S[self.first_contested_seat - 1]

    def initial_distribution(self):
        parties_dhont = {}
        matrix_A = [] # Matrix with information about which party wins each round
        for p in self.parties_names:
            parties_dhont[p] = {"original_votes": self.parties_data[p]["votes"], "quotient": self.parties_data[p]["votes"], "wins": 0, "wing": self.parties_data[p]["wing"]}
        for i in range(0, self.num_seats):
            current_party = self.parties_names[0]
            for comparison_party in self.parties_names[1:]:
                if parties_dhont[current_party]["quotient"] < parties_dhont[comparison_party]["quotient"]:
                    current_party = comparison_party
            A_entry = {p: int(current_party == p) for p in self.parties_names}
            matrix_A.append(A_entry)
            parties_dhont[current_party]["wins"] = parties_dhont[current_party]["wins"] + 1
            parties_dhont[current_party]["quotient"] = parties_dhont[current_party]["original_votes"] / (parties_dhont[current_party]["wins"] + 1)
        self.matrix_A = matrix_A
        return parties_dhont

    def build_S(self):
        matrix_S = [{p:0 for p in self.parties_names}]
        for i in range(1, self.first_contested_seat): # Value self.first_contested_seat will be used for denominators in first iteration of constraints
            S_entry = matrix_S[i - 1].copy()
            A_entry = self.matrix_A[i - 1]
            for p, v in A_entry.items():
                S_entry[p] = S_entry[p] + v
            matrix_S.append(S_entry)
        self.matrix_S = matrix_S

    def initial_distribution_wings(self):
        wings_dhont = {w: {"wins": 0} for w in self.wings_names}
        for p in self.parties_names:
            wings_dhont[self.parties_dhont[p]["wing"]]["wins"] = wings_dhont[self.parties_dhont[p]["wing"]]["wins"] + self.parties_dhont[p]["wins"]
        return wings_dhont

    def create_parties(self):
        for p in self.parties_names:
            party = Party(p, self)
            self.parties.append(party)
        self.parties_dict = {party.name: party for party in self.parties}
    
    def create_wings(self):
        for w in self.wings_names:
            wing = Wing(w, self)
            self.wings.append(wing)
        self.wings_dict = {wing.name: wing for wing in self.wings}

class SeatsModel:

    # How the settings dictionary works:
    # The _default subdict will contain the default settings for every province
    # For any province that is explicitly specified, those settings will be used instead
    # If some settings are redundant accross several provinces, they may also be specified as part of a group 
    # Also, an optional _global subdict will allow the user to specify global constraints

    # Note: in the future, specific settings may be partially specified, that is,
    # one may specify several province-specific settings, some other group-specific settings,
    # and leave the rest equal to the _default values.
    # This is still work in progress because currently the focus is on getting everything to work right
    
    # Note: The province_list variable is just a dictionary whose keys are the provinces' names
    # and whose values are dictionaries contaning each party's "party data" and the total number of disputed seats
    
    # The settings for each province must be specified in the settings variable

    def __init__(self, province_list, settings):
        self.province_list = province_list
        self.settings = settings
        self.province_object_list = {}

        # Solver config

        self.solver = pywraplp.Solver.CreateSolver('SCIP')
        self.solver.SetSolverSpecificParametersAsString('display/verblevel 5')

        # Creation of the Province objects

        self.default_provinces = list(province_list.keys())

        for p in province_list:
            if p in settings:                
                p_data = province_list[p]
                if "group" in settings[p]:
                    p_settings = settings[settings[p]["group"]]
                else:
                    p_settings = settings[p]

                self.province_object_list[p] = Province(p, self.solver, p_data["num_seats"], p_data["parties_data"],
                                                        p_settings["parties_permeability"], p_settings["wings_permeability"], 
                                                        p_settings["objective_function_weights"], p_settings["default_party_permeability"],
                                                        p_settings["default_wing_permeability"], p_settings["default_party_seats_weight"], 
                                                        p_settings["default_wing_seats_weight"], p_settings["default_party_movements_weight"], 
                                                        p_settings["default_wing_movements_weight"], p_settings["first_contested_seat"])
                self.default_provinces.remove(p)
            else:
                p_data = province_list[p]
                p_settings = settings["_default"]

                self.province_object_list[p] = Province(p, self.solver, p_data["num_seats"], p_data["parties_data"],
                                                        p_settings["parties_permeability"], p_settings["wings_permeability"], 
                                                        p_settings["objective_function_weights"], p_settings["default_party_permeability"],
                                                        p_settings["default_wing_permeability"], p_settings["default_party_seats_weight"], 
                                                        p_settings["default_wing_seats_weight"], p_settings["default_party_movements_weight"], 
                                                        p_settings["default_wing_movements_weight"], p_settings["first_contested_seat"])
        # Initialization of global variables and auxiliary dictionaries
        self.__party_votes = {}
        self.__party_seats = {}
        self.__wing_votes = {}
        self.__wing_seats = {}
        self.__delta_neg_votes_by_party = {}
        self.__delta_neg_votes_by_wing = {}
        
        self.all_votes = 0
        self.all_seats = 0
        self.all_parties = {} # Will contain seats, votes and provinces where party exists
        self.all_wings = {} # Ibidem

    def create_model(self):
        for prov in self.province_object_list.values():
            prov.create_parties()
            prov.create_wings()
        self.create_global_variables() # IMPORTANT: has to be executed AFTER parties and wings are created
        self.create_constraints()
        self.create_objective()

    def create_global_variables(self):

        # First step: populate dictionaries

        for prov, prov_obj in self.province_object_list.items():
            self.all_seats = self.all_seats + prov_obj.num_seats
            parties = prov_obj.parties
            wings = prov_obj.wings
            # We can use either parties or wings to count votes, let's use parties as they are the more basic units
            for p in parties:
                self.all_votes = self.all_votes + p.my_votes
                if p.name not in self.all_parties:
                    self.all_parties[p.name] = {"votes": p.my_votes, "seats": prov_obj.parties_dhont[p.name]["wins"], "provinces": [prov]}
                else:
                    self.all_parties[p.name]["votes"] = self.all_parties[p.name]["votes"] + p.my_votes
                    self.all_parties[p.name]["seats"] = self.all_parties[p.name]["seats"] + prov_obj.parties_dhont[p.name]["wins"]
                    self.all_parties[p.name]["provinces"].append(prov)
            for w in wings:
                if w.name not in self.all_wings:
                    self.all_wings[w.name] = {"votes": w.my_votes, "seats": prov_obj.wings_dhont[w.name]["wins"], "provinces": [prov]}
                else:
                    self.all_wings[w.name]["votes"] = self.all_wings[w.name]["votes"] + w.my_votes
                    self.all_wings[w.name]["seats"] = self.all_wings[w.name]["seats"] + prov_obj.wings_dhont[w.name]["wins"]
                    self.all_wings[w.name]["provinces"].append(prov)

        # Second step: initialize variables. We want to have FINAL VOTES, FINAL SEATS AND NEGATIVE DELTAS FOR EACH PARTY AND WING

        for party in self.all_parties:
            self.party_votes_var(party)
            self.party_seats_var(party)
            for party2 in [party2 for party2 in self.all_parties if party2 != party]:
                self.delta_neg_votes_by_party_var(party, party2)

        for wing in self.all_wings:
            self.wing_votes_var(wing)
            self.wing_seats_var(wing)
            for wing2 in [wing2 for wing2 in self.all_wings if wing2 != wing]:
                self.delta_neg_votes_by_wing_var(wing, wing2)

    def party_votes_var(self, party):
        if not party in self.__party_votes:
            self.__party_votes[party] = self.solver.NumVar(
                0,
                self.all_votes,
                f'party_votes_{party}'
            )
        return self.__party_votes[party]

    def party_seats_var(self, party):
        if not party in self.__party_seats:
            self.__party_seats[party] = self.solver.IntVar(
                0,
                self.all_seats,
                f'party_seats_{party}'
            )
        return self.__party_seats[party]

    def wing_votes_var(self, wing):
        if not wing in self.__wing_votes:
            self.__wing_votes[wing] = self.solver.NumVar(
                0,
                self.all_votes,
                f'wing_votes_{wing}'
            )
        return self.__wing_votes[wing]

    def wing_seats_var(self, wing):
        if not wing in self.__wing_seats:
            self.__wing_seats[wing] = self.solver.IntVar(
                0,
                self.all_seats,
                f'wing_seats_{wing}'
            )
        return self.__wing_seats[wing]

    def delta_neg_votes_by_party_var(self, party1, party2):
        party1_data = self.all_parties[party1]
        if not (party1, party2) in self.__delta_neg_votes_by_party:
            self.__delta_neg_votes_by_party[(party1, party2)] = self.solver.NumVar(
                    0,
                    party1_data["votes"],
                    f'delta_neg_votes_by_party_{party1}_{party2}'
                )
        return self.__delta_neg_votes_by_party[(party1, party2)]

    def delta_neg_votes_by_wing_var(self, wing1, wing2):
        wing1_data = self.all_wings[wing1]
        if not (wing1, wing2) in self.__delta_neg_votes_by_wing:
            self.__delta_neg_votes_by_wing[(wing1, wing2)] = self.solver.NumVar(
                    0,
                    wing1_data["votes"],
                    f'delta_neg_votes_by_wing_{wing1}_{wing2}'
                )
        return self.__delta_neg_votes_by_wing[(wing1, wing2)]

    def create_constraints(self):

        # GLOBAL CONSTRAINTS (Work in progress)

        # Obvious constraints:

        # For parties
        for p, p_data in self.all_parties.items():
            p_provinces = p_data["provinces"]
            p_provinces_obj = [self.province_object_list[prov] for prov in p_provinces]
            # Total votes for the party equals sum of votes in each province
            party_votes_vars = [prov.parties_dict[p].votes_var() for prov in p_provinces_obj]
            self.solver.Add(self.solver.Sum(party_votes_vars) == self.party_votes_var(p))
            # Total seats for the party equals sum of seats in each province
            party_seats_vars = [prov.parties_dict[p].seats_var() for prov in p_provinces_obj]
            self.solver.Add(self.solver.Sum(party_seats_vars) == self.party_seats_var(p))
            # Total delta neg votes for party p with party q equals sum of delta neg votes in each province where they BOTH exist
            for q, q_data in self.all_parties.items():
                q_provinces = q_data["provinces"]
                pq_provinces = [prov for prov in p_provinces if prov in q_provinces]
                pq_provinces_obj = [self.province_object_list[prov] for prov in pq_provinces]
                party_delta_vars = [prov.parties_dict[p].delta_neg_votes_by_party_var(q) for prov in pq_provinces_obj]
                self.solver.Add(self.solver.Sum(party_delta_vars) == self.delta_neg_votes_by_party_var(p, q))

        # For wings
        for w1, w1_data in self.all_wings.items():
            w1_provinces = w1_data["provinces"]
            w1_provinces_obj = [self.province_object_list[prov] for prov in w1_provinces]
            # Total votes for the wing equals sum of votes in each province
            wing_votes_vars = [prov.wings_dict[w1].votes_var() for prov in w1_provinces_obj]
            self.solver.Add(self.solver.Sum(wing_votes_vars) == self.wing_votes_var(w1))
            # Total seats for the wing equals sum of seats in each province
            wing_seats_vars = [prov.wings_dict[w1].seats_var() for prov in w1_provinces_obj]
            self.solver.Add(self.solver.Sum(wing_seats_vars) == self.wing_seats_var(w1))
            # Total delta neg votes for wing p with wing w2 equals sum of delta neg votes in each province where they BOTH exist
            for w2, w2_data in self.all_wings.items():
                w2_provinces = w2_data["provinces"]
                w1w2_provinces = [prov for prov in w1_provinces if prov in w2_provinces]
                w1w2_provinces_obj = [self.province_object_list[prov] for prov in w1w2_provinces]
                wing_delta_vars = [prov.wings_dict[w1].delta_neg_votes_by_wing_var(w2) for prov in w1w2_provinces_obj]
                self.solver.Add(self.solver.Sum(wing_delta_vars) == self.delta_neg_votes_by_wing_var(w1, w2))

        # Constraints that are only set if _global settings exist (i.e., global permeability constraints):
        
        if "_global" in self.settings:
            global_default_parties = self.settings["_global"]["parties"]["_default"]
            for p in self.all_parties:
                for q in self.all_parties:
                    if p != q and [prov for prov in self.all_parties[p]["provinces"] if prov in self.all_parties[q]["provinces"]]: # Non empty province intersection
                        self.solver.Add(self.delta_neg_votes_by_party_var(p, q) <= self.settings["_global"]["parties"].get((p,q), global_default_parties) * self.all_parties[p]["votes"])
    
    
            global_default_wings = self.settings["_global"]["wings"]["_default"]
            for p in self.all_wings:
                for q in self.all_wings:
                    if p != q and [prov for prov in self.all_wings[p]["provinces"] if prov in self.all_wings[q]["provinces"]]: # Non empty province intersection
                        self.solver.Add(self.delta_neg_votes_by_wing_var(p, q) <= self.settings["_global"]["wings"].get((p,q), global_default_wings) * self.all_wings[p]["votes"])


        # NON-GLOBAL CONSTRAINTS

        for prov in self.province_object_list.values():

            ####################################################################
            # Final votes constraints under > 1 first contested seat condition #
            ####################################################################

            for i in range(0, prov.first_contested_seat - 1):
                for p in prov.parties:
                    if prov.matrix_A[i][p.name] == 1:
                        for q in [q for q in prov.parties if q.name != p.name]:
                            sip = prov.matrix_S[i][p.name]
                            siq = prov.matrix_S[i][q.name]
                            prov.solver.Add((1/(1 + sip))*p.votes_var() >= (1/(1 + siq))*q.votes_var())

            ###########################
            # Total votes constraints #
            ###########################

            # Sum of votes for all parties = Total votes

            all_parties_votes = [p.votes_var() for p in prov.parties]
            prov.solver.Add(prov.solver.Sum(all_parties_votes) == prov.total_votes)

            # Sum of all votes in wing = Total wing votes

            for w in prov.wings:
                all_parties_in_wing_votes = [p.votes_var() for p in prov.parties if p.my_wing == w.name]
                prov.solver.Add(prov.solver.Sum(all_parties_in_wing_votes) == w.votes_var())

            #############################
            # Vote movement constraints #
            #############################

            # Relationship between deltas, total final votes and total initial votes (for parties)

            for p in prov.parties:
                total_party_deltas = [p.votes_var()]
                for op in prov.parties_names:
                    if op != p.name:
                        total_party_deltas.append((-1) * p.delta_pos_votes_by_party_var(op))
                        total_party_deltas.append(p.delta_neg_votes_by_party_var(op))
                prov.solver.Add(prov.solver.Sum(total_party_deltas) == p.my_votes)

            # Relationship between deltas by wings and deltas by parties (positive AND negative)

            for w1 in prov.wings:
                for w2 in prov.wings:
                    if w2.name != w1.name:
                        parties_w1 = [p for p in prov.parties if p.my_wing == w1.name]
                        parties_w2 = [q for q in prov.parties if q.my_wing == w2.name]
                        total_positive_party_deltas_from_w1_to_w2 = []
                        total_negative_party_deltas_from_w1_to_w2 = []
                        for p in parties_w1:
                            for q in parties_w2:
                                total_positive_party_deltas_from_w1_to_w2.append(p.delta_pos_votes_by_party_var(q.name))
                                total_negative_party_deltas_from_w1_to_w2.append(p.delta_neg_votes_by_party_var(q.name))
                        prov.solver.Add(prov.solver.Sum(total_positive_party_deltas_from_w1_to_w2) == w1.delta_pos_votes_by_wing_var(w2.name))
                        prov.solver.Add(prov.solver.Sum(total_negative_party_deltas_from_w1_to_w2) == w1.delta_neg_votes_by_wing_var(w2.name))

            # Relationship between positive and negative deltas by parties

            for p in prov.parties:
                for q in prov.parties:
                    if p.name != q.name:
                        prov.solver.Add(p.delta_pos_votes_by_party_var(q.name) == q.delta_neg_votes_by_party_var(p.name))

            ############################
            # Permeability constraints #
            ############################

            for p in prov.parties:
                for q in prov.parties_names:
                    if p.name != q:
                        prov.solver.Add(p.delta_neg_votes_by_party_var(q) <= prov.parties_permeability.get(p.name).get(q, prov.default_party_permeability) * p.my_votes)

            for w1 in prov.wings:
                for w2 in prov.wings_names:
                    if w1.name != w2:
                        prov.solver.Add(w1.delta_neg_votes_by_wing_var(w2) <= prov.wings_permeability.get(w1.name).get(w2, prov.default_wing_permeability) * w1.my_votes)

            ###############################
            # Seat assignment constraints #
            ###############################

            # Partial round wins
            for p in prov.parties:
                for q in prov.parties:
                    if p.name != q.name:
                        # First seat
                        prov.solver.Add(p.votes_var()/(1 + prov.lastline_S[p.name]) - q.votes_var()/(1 + prov.lastline_S[q.name]) >= -prov.M*(1 - p.partial_wins_indicators_var(prov.first_contested_seat,q.name)))
                        prov.solver.Add(p.votes_var()/(1 + prov.lastline_S[p.name]) - q.votes_var()/(1 + prov.lastline_S[q.name]) <= prov.M*p.partial_wins_indicators_var(prov.first_contested_seat,q.name))

                        # Rest of seats
                        for k in range(prov.first_contested_seat + 1, prov.num_seats + 1):
                            prov.solver.Add(p.quotient_before_k_var(k) - q.quotient_before_k_var(k) >= -prov.M*(1 - p.partial_wins_indicators_var(k,q.name)))
                            prov.solver.Add(p.quotient_before_k_var(k) - q.quotient_before_k_var(k) <= prov.M*p.partial_wins_indicators_var(k,q.name))

            # Round wins
            for p in prov.parties:
                for k in range(prov.first_contested_seat, prov.num_seats + 1):
                    prov.solver.Add(p.round_wins_indicators_var(k) == prov.solver.Sum([p.partial_wins_indicators_var(k,q) for q in prov.parties_names if q != p.name]))

            # Seat assignments
            for p in prov.parties:
                for k in range(prov.first_contested_seat, prov.num_seats + 1):
                    prov.solver.Add(p.round_wins_indicators_var(k) - (prov.parties_number - 1) >= -prov.M * (1 - p.seat_k_is_assigned_var(k)))

            for k in range(prov.first_contested_seat, prov.num_seats + 1):
                prov.solver.Add(prov.solver.Sum([p.seat_k_is_assigned_var(k) for p in prov.parties]) == 1)

            # Seats at the assignment of seat k
            for p in prov.parties:
                for k in range(prov.first_contested_seat + 1, prov.num_seats + 1):
                    prov.solver.Add(prov.solver.Sum([p.seat_k_is_assigned_var(t) for t in range(prov.first_contested_seat, k)]) + p.sij == p.seats_before_k_var(k))

            # Auxiliary indicator variables of number of seats at the assignment of seat k
            for p in prov.parties:
                for k in range(prov.first_contested_seat + 1, prov.num_seats + 1):
                    for m in range(p.sij, k):
                        prov.solver.Add(p.seats_before_k_var(k) - m >= - prov.M * (1 - p.seats_before_k_indicators_var(k, m)))
                        prov.solver.Add(p.seats_before_k_var(k) - m <= prov.M * (1 - p.seats_before_k_indicators_var(k, m)))
                    # Additional condition for ensuring indicator is 1 when seats_before_k_var(k) == m
                    prov.solver.Add(prov.solver.Sum([p.seats_before_k_indicators_var(k, m) for m in range(p.sij, k)]) == 1)

            # Assignment of quotients
            for p in prov.parties:
                for k in range(prov.first_contested_seat + 1, prov.num_seats + 1):
                    for m in range(p.sij,k):
                        prov.solver.Add(p.quotient_before_k_var(k) - (1/(m+1))*p.votes_var() >= -prov.M*(1 - p.seats_before_k_indicators_var(k,m)))
                        prov.solver.Add(p.quotient_before_k_var(k) - (1/(m+1))*p.votes_var() <= prov.M*(1 - p.seats_before_k_indicators_var(k,m)))

            # Total seats for each party after all seats are allocated

            for p in prov.parties:
                prov.solver.Add(prov.solver.Sum([p.seat_k_is_assigned_var(k) for k in range(prov.first_contested_seat, prov.num_seats + 1)]) + p.sij == p.seats_var())

            # Total seats in wing
            for w in prov.wings:
                all_parties_in_wing_seats = [p.seats_var() for p in prov.parties if p.my_wing == w.name]
                prov.solver.Add(prov.solver.Sum(all_parties_in_wing_seats) == w.seats_var())

    def create_objective(self):
        obj = self.solver.Objective()
        obj.SetMaximization()

        for prov in self.province_object_list.values():

            # Party seats component 
            for p in prov.parties:
                obj.SetCoefficient(p.seats_var(), prov.objective_function_weights.get("party_seats").get(p.name, prov.default_party_seats_weight))

            # Wing seats component
            for w in prov.wings:
                obj.SetCoefficient(w.seats_var(), prov.objective_function_weights.get("wing_seats").get(w.name, prov.default_wing_seats_weight))

            # Party movements component
            for p in prov.parties:
                for q in prov.parties_names:
                    if q != p.name:
                        weight = prov.objective_function_weights.get("party_movements").get(p.name).get(q,prov.default_party_movements_weight)
                        if isinstance(weight, str) and weight[0:4] == "auto":
                            weight = - float(weight[4:])*(prov.num_seats / prov.total_votes)
                        obj.SetCoefficient(p.delta_neg_votes_by_party_var(q), weight)

            # Wing movements component
            for w1 in prov.wings:
                for w2 in prov.wings_names:
                    if w2 != w1.name:
                        weight = prov.objective_function_weights.get("wing_movements").get(w1.name).get(w2,prov.default_wing_movements_weight)
                        if isinstance(weight, str) and weight[0:4] == "auto":
                            weight = - float(weight[4:])*(prov.num_seats / prov.total_votes)
                        obj.SetCoefficient(w1.delta_neg_votes_by_wing_var(w2), weight)
    
    def solve_model(self):
        status = self.solver.Solve()
        print(status)
        if status == pywraplp.Solver.OPTIMAL:
            print('Solución encontrada')
            print("Valor de la función objetivo:", self.solver.Objective().Value())
            print("\n")
            for prov in self.province_object_list.values():
                print("--- PROVINCIA DE: ", prov.province, " ---\n")
                for p in prov.parties:
                    print(p)
                    print(p.my_votes, "votos iniciales")
                    print(math.floor(p.votes_var().solution_value()), "votos finales")
                    print(prov.parties_dhont[p.name]["wins"], "escaños iniciales")
                    print(int(p.seats_var().solution_value()), "escaños finales")
                    print("\n")
                for w in prov.wings:
                    print(w)
                    print(w.my_votes, "votos iniciales")
                    print(math.floor(w.votes_var().solution_value()), "votos finales")
                    print(prov.wings_dhont[w.name]["wins"], "escaños iniciales")
                    print(int(w.seats_var().solution_value()), "escaños finales")
                    print("\n")
                print("Movimientos de partidos:")
                for p in prov.parties:
                    for q in prov.parties_names:
                        if p.name != q:
                            print("De", p.name, "a", q, p.delta_neg_votes_by_party_var(q).solution_value())
                print("\n")
                print("Movimientos de alas:")
                for p in prov.wings:
                    for q in prov.wings_names:
                        if p.name != q:
                            print("De", p.name, "a", q, p.delta_neg_votes_by_wing_var(q).solution_value())
                print("\n")
            print("=== RESULTADOS GLOBALES ===\n\n")
            # Partidos
            print("Resultados para partidos:\n")
            for p, p_obj in self.all_parties.items():
                print(f"Partido {p}:\n")
                print(f"Votos iniciales: {p_obj['votes']}")
                print(f"Votos finales: {math.floor(self.party_votes_var(p).solution_value())}")
                print(f"Escaños iniciales: {p_obj['seats']}")
                print(f"Escaños finales: {int(self.party_seats_var(p).solution_value())}")
            print("\nMovimientos de votos")
            for p, p_obj in self.all_parties.items():
                for q in [q for q in self.all_parties if q != p]:
                    q_obj = self.all_parties[q]
                    p_provinces = p_obj["provinces"]
                    q_provinces = q_obj["provinces"]
                    pq_provinces = [prov for prov in p_provinces if prov in q_provinces]
                    if pq_provinces:
                        print(f"Votos de {p} a {q}: {math.floor(self.delta_neg_votes_by_party_var(p, q).solution_value())}")
            # Alas
            print("\nResultados para alas:\n")
            for p, p_obj in self.all_wings.items():
                print(f"Ala {p}:\n")
                print(f"Votos iniciales: {p_obj['votes']}")
                print(f"Votos finales: {math.floor(self.wing_votes_var(p).solution_value())}")
                print(f"Escaños iniciales: {p_obj['seats']}")
                print(f"Escaños finales: {int(self.wing_seats_var(p).solution_value())}")
            print("\nMovimientos de votos")
            for p, p_obj in self.all_wings.items():
                for q in [q for q in self.all_wings if q != p]:
                    q_obj = self.all_wings[q]
                    p_provinces = p_obj["provinces"]
                    q_provinces = q_obj["provinces"]
                    pq_provinces = [prov for prov in p_provinces if prov in q_provinces]
                    if pq_provinces:
                        print(f"Votos de {p} a {q}: {math.floor(self.delta_neg_votes_by_wing_var(p, q).solution_value())}")
        else:
            print('El problema no tiene solución óptima')
