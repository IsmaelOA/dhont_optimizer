import unittest
from seats import SeatsModel

class TestSeatsModel(unittest.TestCase):
    def setUp(self):
        province_list = {
            "Province1": {
                "num_seats": 12,
                "parties_data": {
                    "party_a": {"votes": 386513, "wing": "wing_b"},
                    "party_b": {"votes": 352102, "wing": "wing_a"},
                    "party_c": {"votes": 147773, "wing": "wing_b"},
                    "party_d": {"votes": 140522, "wing": "wing_a"}
                }
            },

            "Province2": {
                "num_seats": 11,
                "parties_data": {
                    "party_a": {"votes": 299977, "wing": "wing_b"},
                    "party_b": {"votes": 236935, "wing": "wing_a"},
                    "party_d": {"votes": 128965, "wing": "wing_a"},
                    "party_c": {"votes": 95662, "wing": "wing_b"}
                }
            },

            "Province3": {
                "num_seats": 9,
                "parties_data": {
                    "party_a": {"votes": 210596, "wing": "wing_b"},
                    "party_b": {"votes": 221020, "wing": "wing_a"},
                    "party_d": {"votes": 96391, "wing": "wing_a"},
                    "party_c": {"votes": 81544, "wing": "wing_b"}
                }
            }

        }

        settings = {

                "_global": {"parties": {"_default": 0.01}, "wings": {"_default": 1}},

            "Cadiz": {"group": "grupo-test"},

            "grupo-test": {
                "parties_permeability": {'party_b': {'party_a': 0.1, 'party_d': 0.1, 'party_c': 0.02}, 'party_a': {'party_b': 0.1, 'party_c': 0.1, 'party_d': 0.02}, 'party_d': {'party_b': 0.05, 'party_a': 0.02}, 'party_c': {'party_a': 0.05, 'party_b': 0.02}},

                "wings_permeability": {'wing_b': {}, 'wing_a': {}},

                "objective_function_weights": {
                        'party_seats': {
                            'party_b': 0, 'party_a': 0, 'party_d': 0, 'party_c': -0.5
                        },

                        'wing_seats': {
                            'wing_a': 0, 'wing_b': 1
                        },

                        'party_movements': {
                            'party_b': {}, 'party_a': {}, 'party_d': {}, 'party_c': {}
                        },

                        'wing_movements': {
                            'wing_b': {}, 'wing_a': {}
                        }
                    },

                "default_party_permeability": 0,

                "default_wing_permeability": 0.2,

                "default_party_seats_weight": 0,

                "default_wing_seats_weight": 0,

                "default_party_movements_weight": "auto1",

                "default_wing_movements_weight": 0,

                "first_contested_seat": 1
            },

            "_default": {
                "parties_permeability": {'party_b': {'party_a': 0.1, 'party_d': 0.1, 'party_c': 0.02}, 'party_a': {'party_b': 0.1, 'party_c': 0.1, 'party_d': 0.02}, 'party_d': {'party_b': 0.05, 'party_a': 0.02}, 'party_c': {'party_a': 0.05, 'party_b': 0.02}},

                "wings_permeability": {'wing_b': {}, 'wing_a': {}},

                "objective_function_weights": {
                            'party_seats': {
                                'party_b': 1, 'party_a': 0, 'party_d': 0, 'party_c': 0
                            },

                            'wing_seats': {
                                'wing_a': 0, 'wing_b': 0
                            },

                            'party_movements': {
                                'party_b': {}, 'party_a': {}, 'party_d': {}, 'party_c': {}
                            },

                            'wing_movements': {
                                'wing_b': {}, 'wing_a': {}
                            }
                        },

                "default_party_permeability": 0,

                "default_wing_permeability": 0.2,

                "default_party_seats_weight": 0,

                "default_wing_seats_weight": 0,

                "default_party_movements_weight": "auto1",

                "default_wing_movements_weight": 0,

                "first_contested_seat": 1
                }
            }

        model = SeatsModel(province_list, settings)

    def test_model_creation(self):
        self.model.create_model()

    def test_model_solution(self):
        self.model.solve_model()
if __name__ == '__main__':
    unittest.main()
