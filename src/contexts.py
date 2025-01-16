#!########################################
#!########### CONTEXTS ###################
#!########################################

#! DATES, CATEGORIES, GRANULARITY
CONTEXT_INTRODUCTION_TO_GET_INFORMATION = """
You are an AI assistant who is an expert in extracting information from user queries to generate SQL queries for the PostgreSQL database.
Please use the below context to extract the required information from the user's question.
""".strip()

#! CONTEXTS FOR CREATION OF SQL QUERIES
CONTEXT_INTRODUCTION = """
Given an input question, first create a syntactically correct SQLite query to run, then look at the results of the query and return the answer to the input question.
Never query for all columns from a table. You must query only the columns that are needed to answer the question.
Pay attention to use only the column names you can see in the tables below in the TABLE_INFO. Be careful to not query for columns that do not exist. Also, pay attention to which column is in which table.
"""

CONTEXT_FOR_CREATION_QUERY = """
- Use the `station` table to get information about stations, including their name, latitude, longitude, dock count, city, and installation date.
- Use the `status` table to get real-time information about bike availability, docks availability, and the timestamp. Use `station_id` to join this table with the `station` table.
- Use the `trip` table for trip details such as duration, start and end station IDs, bike IDs, subscription types, and zip codes.
- Use the `weather` table to get weather details, including temperatures, humidity, wind speed, and precipitation. Use the `date` and `zip_code` columns for filtering and joining with other tables.
- For joins between tables:
  - Join `station` and `status` tables using `station.id = status.station_id`.
  - Join `trip` and `station` tables using `trip.start_station_id = station.id` or `trip.end_station_id = station.id`.
  - Join `trip` and `weather` tables using `trip.zip_code = weather.zip_code` and `trip.start_date = weather.date`.
- Use aggregate functions like COUNT(), AVG(), or SUM() where appropriate.
- Use date/time functions for filtering or grouping data by date or time, especially in the `trip` and `weather` tables.
"""


TABLE_INFO = """
- Table `station`:
  Columns: id (INTEGER, primary key), name (TEXT), lat (NUMERIC), long (NUMERIC), dock_count (INTEGER), city (TEXT), installation_date (TEXT)

- Table `status`:
  Columns: station_id (INTEGER, foreign key to station.id), bikes_available (INTEGER), docks_available (INTEGER), time (TEXT)

- Table `trip`:
  Columns: id (INTEGER, primary key), duration (INTEGER), start_date (TEXT), start_station_id (INTEGER, foreign key to station.id), end_date (TEXT), end_station_id (INTEGER, foreign key to station.id), bike_id (INTEGER), subscription_type (TEXT), zip_code (INTEGER)

- Table `weather`:
  Columns: date (TEXT), max_temperature_f (INTEGER), mean_temperature_f (INTEGER), min_temperature_f (INTEGER), max_dew_point_f (INTEGER), mean_dew_point_f (INTEGER), min_dew_point_f (INTEGER), max_humidity (INTEGER), mean_humidity (INTEGER), min_humidity (INTEGER), max_sea_level_pressure_inches (NUMERIC), mean_sea_level_pressure_inches (NUMERIC), min_sea_level_pressure_inches (NUMERIC), max_visibility_miles (INTEGER), mean_visibility_miles (INTEGER), min_visibility_miles (INTEGER), max_wind_speed_mph (INTEGER), mean_wind_speed_mph (INTEGER), max_gust_speed_mph (INTEGER), precipitation_inches (INTEGER), cloud_cover (INTEGER), events (TEXT), wind_dir_degrees (INTEGER), zip_code (INTEGER)
"""


#!########################################
#!########### FUNCTIONS ##################
#!########################################


def _context_introduction() -> str:
    """Returns the context introduction."""
    return CONTEXT_INTRODUCTION


def _context_for_creation_query(
    schema_name: str,
) -> str:
    """Returns the context for creating visits for one day."""
    # Formatting dates from %Y-%m-%d to %Y_%m_%d
    return CONTEXT_FOR_CREATION_QUERY.format(
        schema_name=schema_name,
    )


def _table_info(schema_name: str) -> str:
    """Returns the table info."""
    return TABLE_INFO.format(schema_name=schema_name)


#! EXAMPLES FOR VECTOR DATABASE


EXAMPLES_QUERIES = [
    {
        "input": "What is the total number of trips starting from station ID 63 on '8/21/2015'?",
        "query": "SELECT COUNT(*) AS trip_count FROM trip WHERE start_station_id = 63 AND (SUBSTR(start_date, 6, 4) || '-' || (CASE WHEN LENGTH(SUBSTR(start_date, 1, 1)) = 1 THEN '0' || SUBSTR(start_date, 1, 1) ELSE SUBSTR(start_date, 1, 1) END) || '-' || SUBSTR(start_date, 3, 2)) = '2015-08-21';",
    },
    {
        "input": "Get the average duration of trips grouped by subscription type.",
        "query": "SELECT subscription_type, AVG(duration) AS average_duration FROM trip GROUP BY subscription_type;",
    },
    {
        "input": "Find the number of available bikes at station ID 3 at '2015-06-02 12:46:02'.",
        "query": "SELECT bikes_available FROM status WHERE station_id = 3 AND time = '2015-06-02 12:46:02';",
    },
    {
        "input": "Get the daily maximum temperature for zip code 94107 between '8/29/2013' and '9/3/2013'.",
        "query": "SELECT date, max_temperature_f FROM weather WHERE zip_code = 94107 AND (SUBSTR(date, 6, 4) || '-' || (CASE WHEN LENGTH(SUBSTR(date, 1, 1)) = 1 THEN '0' || SUBSTR(date, 1, 1) ELSE SUBSTR(date, 1, 1) END) || '-' || SUBSTR(date, 3, 2))  BETWEEN '2013-08-29' AND '2013-09-03' ORDER BY date;",
    },
    {
        "input": "List all stations with their names, dock counts, and installation dates in San Jose.",
        "query": "SELECT name, dock_count, installation_date FROM station WHERE city = 'San Jose';",
    },
    {
        "input": "Find the total number of docks available across all stations at '2015-06-02 12:47:02'.",
        "query": "SELECT SUM(docks_available) AS total_docks FROM status WHERE time = '2015-06-02 12:47:02';",
    },
]
