import math
from pathlib import Path
from datetime import datetime
import pickle

# This has to be put here as the imports
# Time for use when creating output
timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")  # current date and time

import numpy as np
import pycxsimulator
from pylab import *

''' 
Viral infection base simulation

Environment: 1x1 2d space

Agent states/behaviour:
States are susceptible, carrier, infected, and immune
Agents encounter each other randomly, and move around the space via random walk within a square around them with sides of length speed.

Rules:
- Infected or carrier agents may infect susceptible agents in their neighborhood or immune agents with a very small probability.
- During infection, agents may die or recover.
- Recovered agents become immune and are less likely to contract the virus or die if they do.

The parameters set below are preliminary and can be adjusted to fit specific viruses.

Notes:
In it's current state, the simulation is set up so 2 thirds of the population die of the virus. 
We can calibrate the prob_death parameter by ensuring the overall percentage of infected who die matches
the percentage value of the actual virus we're modelling

'''

pop_init = 300  # initial population
infected_init = 1  # number of 'infected' agents at initialisation

# Default values
params = {"max_infection_rate": 0.9,
          "case_fatality_rate": 0.025,
          "min_recovery_period": 14,
          "max_recovery_period": 31,
          "min_carrier_period": 1,
          "max_carrier_period": 5}

# Dictionary to store the virus attributes.
virus_dict = {"covid": {"max_infection_rate": 0.9,
                        "case_fatality_rate": 0.025,
                        "min_recovery_period": 11,
                        "max_recovery_period": 20,
                        "min_carrier_period": 4,
                        "max_carrier_period": 6},

              "marburg": {"max_infection_rate": 0.9,
                          "case_fatality_rate": 0.88,
                          "min_recovery_period": 14,
                          "max_recovery_period": 31,
                          "min_carrier_period": 2,
                          "max_carrier_period": 7}}

# Prompt the user for the name of the virus, if none is supplied the default parameters are used.
virus_name = input(
    "Please enter the name of a virus to simulate from the following: Covid, Influenza. Press enter to continue to "
    "custom selection.")

virus_name = virus_name.strip().lower()

# If we have parameters for the given virus name, select and load them.
if virus_name in virus_dict.keys():
    print("A virus with this name has been found. Loading variables...")

    params = virus_dict[virus_name]

else:
    # If the supplied name (or no input is given) is not in the dictionary, use the default values.
    virus_name = "default"
    print("No value was passed or no virus was found with that name, the default values are in use."
          "To change the values please go to the parameter tab and update the parameters")

# load the parameters.
max_infection_rate = params["max_infection_rate"]
case_fatality_rate = params["case_fatality_rate"]
min_recovery_period = params["min_recovery_period"]
max_recovery_period = params["max_recovery_period"]
min_carrier_period = params["min_carrier_period"]
max_carrier_period = params["max_carrier_period"]

# Death probability option 1, inverse geometric. So the cumulative probability up to the mean recovery is roughly equal
# to the case fatality. After this  point the probabilities are mirrored and decrease as the agent gets closer to
# recovery. The motivation is that the agent will be more likely to die as the illness progresses and then less likely
# as they recover once the pass the mean recovery time.
mean_recovery_period = round((min_recovery_period + max_recovery_period) / 2)
prob_death = 1 - (case_fatality_rate ** (1 / mean_recovery_period))

# Death probability option 2, equal probs. The case fatality rate is divided by the mean recovery period to find the
# probability at each time step. This means that the cumulative probability by the mean recovery time is equal to the
# case fatality rate.
# prob_death = case_fatality_rate / round((min_recovery_period + max_recovery_period) / 2)

speed = 0.05  # movement speed (diffusion rate)

rec_time_range = [min_recovery_period, max_recovery_period]  # time frame in which each agent recovers
carrier_time_range = [min_carrier_period, max_carrier_period]  # Time frame when an agent is a carrier

# vac_rates = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9,
#              1.0]  # percentage of agents that are immune (vaccinated) at the start. Changes for each sim run
# Commented out as we are leaving the script in a state where the vaccination rate can be changed in the GUI.
vac_rate = 0

cd = 0.05  # neighborhood radius

# Path to store the output.
output_path = Path.cwd() / "Simulations" / f"{virus_name}_{timestamp}"
output_path.mkdir(parents=True, exist_ok=True)

# List to capture the cases from deceased agents.
deceased_cases = []


class agent:
    pass


# For each of the vaccination rates, run the experiments.
# Note: the simulation stops updating but does not stop running as pycxsimulator keeps calling the functions.
# for vac_rate in vac_rates:
# Commented out as we want the vac_rate to be an available parameter to set in the GUI.
def initialize():
    """
    This function initializes the simulation. It spawns the agents, assigns them types and random co-ordinates
    within the environment.
    """
    global agents, time, current_output_path, agents_path, final_plots_path
    global total_infected, total_casualties
    global infected_ts, total_infected_ts, casualty_ts, total_casualty_ts, basic_reproduction_number_ts

    # List for holding agents and the variable to store the time step we are currently on.
    agents = []
    time = 0

    # Set the seed here so that the agent initialization is constant and reproducible.
    seed(42)

    # initialise population.
    for i in range(pop_init):

        # create an agent instance.
        ag = agent()
        ag.type = 'susceptible'
        ag.immune = False
        ag.prior_infection = False
        ag.new_infection = False

        # randomly assign immune to "vac_rate"% of agents.
        if random() < vac_rate:
            ag.immune = True

        # start with just 1 infected agent.
        if i >= pop_init - infected_init:
            # Give the agent type infected, an attribute to store the time infected and a randomly sampled
            # recovery time from a uniform distribution between a minimum and maximum.
            ag.type = 'infected'
            ag.prior_infection = True
            ag.new_infection = True
            ag.infected_time = 0
            ag.rec_time = uniform(rec_time_range[0], rec_time_range[1])

        # Assign a random x and y value to the agent.
        ag.x = random()
        ag.y = random()

        # Give the agent an attribute to record how many agents they infect in a time step (Needed to calculate the
        # basic reproduction number).
        ag.no_infected = 0

        # Append the agents to a list.
        agents.append(ag)

    # initialise plots and variables
    total_casualties = 0
    total_infected = 0

    casualty_ts = [0]
    infected_ts = [0]

    total_infected_ts = [total_infected]
    total_casualty_ts = [total_casualties]
    basic_reproduction_number_ts = [0]

    # Set up the directories for storing the output images
    current_output_path = output_path / f"vac_rate_{str(vac_rate)}"
    plot_path = current_output_path / "Plots"

    agents_path = plot_path / "agents"
    final_plots_path = plot_path / "final"

    agents_path.mkdir(parents=True, exist_ok=True)
    final_plots_path.mkdir(parents=True, exist_ok=True)


def observe():
    """
    This function oberves the current state of all agents and updates the variables for storing data regarding the state
    of the simulation.
    """
    global agents, time, current_output_path, agents_path, final_plots_path
    global infected_ts, total_infected_ts, casualty_ts, total_casualty_ts, basic_reproduction_number_ts

    # Create a subplot for displaying the agents in the environment.
    subplot(3, 1, (1, 2))

    plt.show()

    # plot the environment
    cla()

    # Get the lists of agents of each type.
    susceptible = [ag for ag in agents if ag.type == 'susceptible' and not ag.immune]
    carrier = [ag for ag in agents if ag.type == 'carrier']
    infected = [ag for ag in agents if ag.type == 'infected']
    immune = [ag for ag in agents if ag.type == 'susceptible' and ag.immune]

    # Plot the agents on the space in their respective colours.
    scatter([ag.x for ag in susceptible], [ag.y for ag in susceptible], color='green', marker='o',
            edgecolor='black')
    scatter([ag.x for ag in carrier], [ag.y for ag in carrier], color='yellow', marker='o', edgecolor='black')
    scatter([ag.x for ag in infected], [ag.y for ag in infected], color='red', marker='o', edgecolor='black')
    scatter([ag.x for ag in immune], [ag.y for ag in immune], color='grey', marker='o', edgecolor='black')

    axis('scaled')
    axis([0, 1, 0, 1])
    title(f't = {time}_vaccination_rate_{vac_rate}')

    subplot(3, 1, 3)
    # plot the population change over time
    cla()
    plot(total_casualty_ts, color='orange')
    tight_layout()
    title('Total casualties')

    # Save the figure for use during the write-up.
    savefig(agents_path / f"{time}_agents.png")


def update():
    """
    This function updates the agents asynchronously.
    """
    global agents, time, current_output_path
    global daily_infected, daily_casualties
    global total_infected, total_casualties
    global infected_ts, total_infected_ts, casualty_ts, total_casualty_ts, basic_reproduction_number_ts

    # if there are no agents left, end the simulation.
    # Note: this just prevents future updates, pycxsimulator continues to call the functions.
    carrier = [ag for ag in agents if ag.type == 'carrier']
    infected = [ag for ag in agents if ag.type == 'infected']

    if not carrier and not infected:
        pkl_file = current_output_path / "statistics.pkl"
        if not pkl_file.exists():
            statistics_dict = {"infected_ts": infected_ts,
                               "total_infected_ts": total_infected_ts,
                               "casualty_ts": casualty_ts,
                               "total_casualty_ts": total_casualty_ts,
                               "basic_reproduction_number_ts": basic_reproduction_number_ts,
                               "agents": agents,
                               "agent_immunity": [ag.immune for ag in agents]}

            with open(pkl_file, 'wb') as handle:
                pickle.dump(statistics_dict, handle, protocol=pickle.HIGHEST_PROTOCOL)
        return

    # randomly choose an agent to move (asynchronous updating)
    ag = choice(agents)

    # simulate random movement before agent interactions
    ag.x += uniform(-speed, speed)
    ag.x = clip(ag.x, 0, 1)
    ag.y += uniform(-speed, speed)
    ag.y = clip(ag.y, 0, 1)

    # susceptible behaviour
    if ag.type == 'susceptible':

        # Get the distances to the infected agents.
        squared_distance_to_infected = {nb: (((ag.x - nb.x) ** 2) + (ag.y - nb.y) ** 2) for nb in agents if
                                        nb.type == 'infected' or nb.type == 'carrier'}

        # If we have more than one infected.
        if len(squared_distance_to_infected) > 0:

            # Get the closest agent and get the distance from the current agent to this neighbour.
            closest_nb = min(squared_distance_to_infected, key=squared_distance_to_infected.get)
            distance = math.sqrt(squared_distance_to_infected[closest_nb])

            # Scale the infection rate dependent on the distance between the agents.
            infection_rate = max(0, (max_infection_rate * (1 - (distance / cd))))

            # If the agent is immune (vaccinated or recovered) lower the chance of infection.
            if ag.immune:
                infection_rate = infection_rate / 5

            # If the neighbour is immune (vaccinated or recovered) lower the chance of infection. The motivation is
            # that an immune agent will have a lower viral load, meaning the virus is not present in large amounts.
            if closest_nb.immune:
                infection_rate = infection_rate / 5

            # If the infection rate is non-zero.
            if infection_rate > 0:

                # Check if the agent has got infected.
                if random() < infection_rate:

                    # If this agent was not previously infected, add them to the neighbours secondary infections for
                    # the basic reproduction number
                    if not ag.prior_infection:
                        ag.prior_infection = True
                        ag.new_infection = True
                        closest_nb.no_infected += 1

                    # Change the agent to a carrier type
                    ag.type = 'carrier'

                    # Set up the agent with a recovery time, carrier time and infected time.
                    ag.rec_time = uniform(rec_time_range[0], rec_time_range[1])
                    ag.carrier_time = uniform(carrier_time_range[0], carrier_time_range[1])
                    ag.infected_time = 0

                    # Add this infection to the metrics.
                    daily_infected += 1
                    total_infected += 1

    # carrier behaviour
    if ag.type == 'carrier':

        # After the incubation period the carrier becomes an infected.
        if ag.carrier_time < ag.infected_time:
            ag.type = 'infected'
        else:
            # Otherwise, increase the time by one unit.
            ag.infected_time += 1

    # infected behaviour
    if ag.type == 'infected':

        # agent dies from infection with some probability. death prob option 1
        probability_timestep = (max_recovery_period - ag.infected_time) - 1

        if probability_timestep < mean_recovery_period:
            probability_timestep = max_recovery_period - probability_timestep

        dynamic_prob_death = ((1 - prob_death) ** probability_timestep) * prob_death
        dynamic_prob_death = min(dynamic_prob_death, case_fatality_rate / 2)

        # option 2 is to use prob_death directly.
        # if random_death < prob_death:

        random_death = random()

        # If the agent is immune they are less likely to die from the infection.
        if ag.immune:
            dynamic_prob_death = dynamic_prob_death / 10

        # Check if the agent has died.
        if random_death < dynamic_prob_death:
            # If they have, add their secondary cases to the list to allow them to be used in the calculation of the
            # basic reproduction number metric.
            deceased_cases.append(ag.no_infected)
            agents.remove(ag)

            # Add the casualty to the metrics.
            total_casualties += 1
            daily_casualties += 1

        # agent recovers and becomes immune if they survive until recovery.
        elif ag.rec_time < ag.infected_time:
            ag.immune = True
            ag.type = "susceptible"

        # If they survuve, update the infected time for this agent.
        else:
            ag.infected_time += 1


def update_one_unit_time():
    """
    Each "update" should result in each agent moving an average of 1 time.
    """
    global agents, time
    global daily_infected, daily_casualties
    global total_infected, total_casualties
    global infected_ts, total_infected_ts, casualty_ts, total_casualty_ts, basic_reproduction_number_ts

    # Increase the number of time steps that have been performed.
    time += 1

    # Initialise variables to store the daily infected and daily casualties.
    daily_infected = 0
    daily_casualties = 0

    # Perform an update for every agent.
    # Note: The agents updated are chosen randomly, so an agent may not be updated in a time step.
    t = 0
    while t < 1:
        t += 1 / len(agents)
        update()

    # update infected and casualtiy time series
    infected_ts.append(daily_infected)
    casualty_ts.append(daily_casualties)
    total_infected_ts.append(total_infected)
    total_casualty_ts.append(total_casualties)

    # Get the number of secondary cases. These are the cases that have been confirmed, excluding new infections from
    # the current time step.
    secondary_cases = [ag.no_infected for ag in agents if
                       ag.type == "infected" and not ag.new_infection] + deceased_cases

    # If we have seconday cases, we can average them.
    if len(secondary_cases) > 0:
        basic_reproduction_number_ts.append(np.mean(secondary_cases))
    # Otherwise, append 0.
    else:
        basic_reproduction_number_ts.append(0)

    # then reset it for the next time step
    for ag in agents:
        ag.new_infection = False


def vac_rate_param(val=vac_rate):
    """
    This function allow the max_carrier_period to be changed within the simulation GUI.
    """
    global vac_rate
    vac_rate = float(val)
    return vac_rate


def max_infection_rate_param(val=max_infection_rate):
    """
    This function allow the max_infection_rate to be changed within the simulation GUI.
    """
    global max_infection_rate
    max_infection_rate = float(val)
    return max_infection_rate


def case_fatality_rate_param(val=case_fatality_rate):
    """
    This function allow the case_fatality_rate to be changed within the simulation GUI.
    """
    global case_fatality_rate
    case_fatality_rate = float(val)
    return case_fatality_rate


def min_recovery_period_param(val=min_recovery_period):
    """
    This function allow the min_recovery_period to be changed within the simulation GUI.
    """
    global min_recovery_period
    min_recovery_period = int(val)
    return min_recovery_period


def max_recovery_period_param(val=max_recovery_period):
    """
    This function allow the max_recovery_period to be changed within the simulation GUI.
    """
    global max_recovery_period
    max_recovery_period = int(val)
    return max_recovery_period


def min_carrier_period_param(val=min_carrier_period):
    """
    This function allow the min_carrier_period to be changed within the simulation GUI.
    """
    global min_carrier_period
    min_carrier_period = int(val)
    return min_carrier_period


def max_carrier_period_param(val=max_carrier_period):
    """
    This function allow the max_carrier_period to be changed within the simulation GUI.
    """
    global max_carrier_period
    max_carrier_period = int(val)
    return max_carrier_period


pycxsimulator.GUI(parameterSetters=[vac_rate_param, max_infection_rate_param, case_fatality_rate_param, min_recovery_period_param,
                                    max_recovery_period_param, min_carrier_period_param, max_carrier_period_param]
                  ).start(func=[initialize, observe, update_one_unit_time])
