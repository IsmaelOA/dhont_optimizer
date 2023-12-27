
# dhont_optimizer

dhont_optimizer is a Python library designed for optimizing seat allocations in electoral systems using the D'Hondt method. It offers a flexible approach to model electoral systems, making it suitable for various provinces and parties.

## Installation

To install dhont_optimizer, clone the repository and use the setup script:

```bash
git clone https://github.com/IsmaelOA/dhont_optimizer.git
cd dhont_optimizer
python setup.py install
```

This will install the package along with its required dependencies.

## Usage

## Settings

In "dhont_optimizer," settings play a crucial role in tailoring the optimization process to the specific electoral system and political landscape you want to analyze. Here's a breakdown of the key settings:

### `province_list`

This dictionary defines the electoral landscape, including the number of seats in each province and the voting data for each party within those provinces. You can customize this to represent the electoral scenario you're interested in.

### `_global`

- `parties` and `wings`: These sub-settings allow you to define default values for parties' and wings' properties. You can set global defaults for party permeability and wing permeability.

### Custom Province Settings

You can define custom settings for specific provinces. For example, in the "Cadiz" province, we've defined a "group" as "group-test." This allows you to group provinces with similar settings for easier management.

### `group-test`

- `parties_permeability` and `wings_permeability`: These settings specify the permeability between parties and wings within the "grupo-test" group. It allows you to model how parties and wings interact within this specific group.

- `objective_function_weights`: This setting defines the weights for the objective functions used in the optimization process. It determines the importance of different factors such as party seats, wing seats, party movements, and wing movements.

- `default_party_permeability` and `default_wing_permeability`: These settings specify default permeability values for parties and wings if not explicitly defined for a province or group.

- `default_party_seats_weight` and `default_wing_seats_weight`: These settings define default weights for party and wing seats if not specified for a province or group.

- `default_party_movements_weight` and `default_wing_movements_weight`: These settings define default weights for party and wing movements if not specified for a province or group.

- `first_contested_seat`: This setting determines the first contested seat in the optimization process.

### `_default`

This section provides default settings that apply globally if not overridden at the province or group level. It's a convenient way to ensure consistency in settings across the project.

Feel free to customize these settings to model different electoral systems and scenarios effectively.

### Seat Allocation Process

To understand the seat allocation process in "dhont_optimizer," consider the following code snippet:

```python
model = SeatsModel(province_list, settings)
self.model.create_model()
self.model.solve_model()
```

1. Model Initialization (model = SeatsModel(province_list, settings)): In this step, an instance of the SeatsModel object is created. This object serves as the representation of the electoral system and is configured using the information provided in province_list and settings. Essentially, it sets up the electoral model that will be used for seat allocation calculations.

2. Model Creation (self.model.create_model()): After initializing the model, the create_model() method is called on the model instance. This method is responsible for defining and constructing the mathematical optimization model that encapsulates the configured electoral system. It establishes the rules and constraints necessary for seat allocation.

3. Model Solving (self.model.solve_model()): Once the model is created and all constraints are set, the solve_model() method is invoked. This method leverages a mathematical solver, potentially implemented using Google OR-Tools, to find the optimal solution for seat allocation. In essence, it executes the optimization process that determines how seats are allocated based on the votes and configurations specified in province_list and settings.

These code snippets represent the core workflow of "dhont_optimizer," where you create, configure, and solve the electoral model to obtain the optimal seat distribution according to the defined electoral rules and constraints.

## Contributing

Contributions to dhont_optimizer are welcome! If you have suggestions for improvement or want to contribute to the code, please feel free to fork the repository, make changes, and submit a pull request. Please ensure your code adheres to the current coding standards and test before submitting any changes.

## Running Tests

To run the tests, navigate to the project's root directory and execute:

```bash
python -m unittest discover
```

## Authors and Acknowledgments

- Ismael Osuna Ayuste - [GitHub](https://github.com/IsmaelOA)
- Alexander Romero Vinogradov - [GitHub](https://github.com/aleromvin)

## Project Status

The project is currently in development. Features and documentation may be added or improved over time.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
