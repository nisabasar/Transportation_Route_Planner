# TransportationRoutePlanner

A comprehensive route planning system for public transportation and taxi services in Izmit (Kocaeli). This project is developed as part of the Programming Lab II course and implements Object-Oriented Programming (OOP) principles. The system calculates the optimal route based on cost, travel time, and number of transfers, combining public transportation and taxi options when necessary.

## Features

- **Public Transportation Routing:** Utilizes bus and tram network data in JSON format.
- **Taxi Fare Calculation:** Computes taxi fares using a fixed opening fee and cost per kilometer.
- **OOP Design:** Implements classes for passengers (with subtypes), vehicles (Bus, Tram, Taxi), stops, and routes.
- **Route Calculation:** Uses Dijkstra's algorithm to determine the fastest route (time-based).
- **Multiple Route Options:** Provides both a combined route (public transport with taxi segments) and a taxi-only option.
- **User Interface:** Command-line interface for entering start and destination coordinates.

## File Structure

```plaintext
TransportationRoutePlanner/
├── README.md              # Project overview and instructions (this file)
├── requirements.txt       # Required Python packages
├── setup.py               # (Optional) Packaging script
├── data/
│   └── stops_data.json    # JSON file containing stops and taxi fare data
├── docs/
│   └── project_report.pdf # IEEE-format project report, flowcharts, pseudocode, etc.
├── src/
│   ├── __init__.py
│   ├── main.py            # Application entry point (user interface)
│   ├── models/            # Data models
│   │   ├── __init__.py
│   │   ├── passenger.py   # Passenger abstract class and subtypes (General, Student, Senior)
│   │   ├── vehicle.py     # Vehicle abstract class and subtypes (Bus, Tram, Taxi)
│   │   ├── stop.py        # Stop model (bus and tram stop details)
│   │   └── route.py       # Route and route segment classes
│   ├── utils/             # Helper functions (e.g., distance calculation using Haversine formula)
│   │   ├── __init__.py
│   │   └── helpers.py
│   └── route_calculator.py# Route calculation logic (Dijkstra algorithm implementation)
└── tests/                 # Unit tests
    ├── __init__.py
    └── test_route_calculator.py

```

## Installation

### 1. Prerequisites:

Ensure you have Python 3.7 or higher installed.

### 2. Install Dependencies:

Run the following command to install required packages:
`bash
    pip install -r requirements.txt
    `

### 3. Setup (Optional):

If you intend to package the project, run:
`bash
    python setup.py install
    `

## Usage

Run the application by executing:

    ```bash
    python src/main.py
    ```

You will be prompted to enter your starting and destination coordinates (latitude and longitude). The system then displays detailed route information including segments (e.g., walk, taxi, bus, tram), total distance, travel time, and cost.

## Testing

Unit tests are located in the `tests` directory. To run tests, execute:

    ```bash
    python -m unittest discover tests
    ```

## Project Report

The IEEE-format project report, including flowcharts, pseudocode, algorithm explanations, and detailed OOP design, is available in the `docs` folder as `project_report.pdf`.

## Future Enhancements

Additional Transportation Modes: Integration of electric scooters, autonomous taxis, etc.

Graphical User Interface: Development of a GUI or map-based visualization for improved user experience.

Advanced Discount Policies: Enhanced fare calculations for different passenger types (students, seniors, teachers, etc.).

Open/Closed Principle: The design allows new transportation modes to be added without modifying existing code.

## License

This project is licensed under the MIT License. See the LICENSE file for details.
