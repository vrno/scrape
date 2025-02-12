import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

# Function to extract data from a given URL
def extract_data_from_url(url):
    try:
        # Send a GET request to the URL
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad status codes

        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find the div with class "blog-content"
        content_div = soup.find('div', {'class': 'blog-content'})
        if not content_div:
            print(f"No content found for URL: {url}")
            return None

        # Find the table with ID "ship" within the div
        table = content_div.find('table', {'id': 'ship'})
        if not table:
            print(f"No table with ID 'ship' found for URL: {url}")
            return None

        # Initialize a list to store data
        data = []

        # Iterate through each row to extract data (skip header row)
        rows = table.find_all('tr')[1:]  # Start from the second row to skip the header
        for row in rows:
            # Find all cells in the row
            cells = row.find_all('td')

            # Ensure there are at least 4 cells
            if len(cells) >= 4:
                name_of_ship = cells[0].text.strip()  # Ship Name
                register_no = cells[1].text.strip()  # Registration Number
                imo_no = cells[2].text.strip()  # IMO Number
                status = cells[3].text.strip()  # Status

                # Append to the list
                data.append({
                    'Nama Kapal': name_of_ship,
                    'No. Register': register_no,
                    'No. IMO': imo_no,
                    'Status': status
                })

        return data

    except requests.exceptions.RequestException as e:
        print(f"Request failed for URL: {url}, Error: {e}")
        return None
    except Exception as e:
        print(f"An error occurred while processing URL: {url}, Error: {e}")
        return None

# Function to extract table data from HTML tables
def extract_table_data(table):
    headers = [header.text.strip() for header in table.find_all('th')]
    rows = []
    for row in table.find_all('tr')[1:]:  # Skip the header row
        cells = row.find_all('td')
        rows.append([cell.text.strip() for cell in cells])
    return headers, rows

# Function to extract main machine and auxiliary engine data
def extract_machine_data(page_number):
    url = f"https://www.bki.co.id/shipregister-{page_number}.html#"
    response = requests.get(url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find the tables by their headers
        main_machine_table = soup.find('h4', string='MAIN MACHINE')
        auxiliary_engine_table = soup.find('h4', string='AUXILIARY ENGINE DATA')

        if main_machine_table and auxiliary_engine_table:
            main_machine_table = main_machine_table.find_next('table')
            auxiliary_engine_table = auxiliary_engine_table.find_next('table')

            # Extract data from both tables
            main_machine_headers, main_machine_rows = extract_table_data(main_machine_table)
            auxiliary_engine_headers, auxiliary_engine_rows = extract_table_data(auxiliary_engine_table)

            # Convert data to JSON format
            main_machine_data = [dict(zip(main_machine_headers, row)) for row in main_machine_rows]
            auxiliary_engine_data = [dict(zip(auxiliary_engine_headers, row)) for row in auxiliary_engine_rows]

            # Create DataFrames
            main_machine_df = pd.DataFrame(main_machine_data)
            auxiliary_engine_df = pd.DataFrame(auxiliary_engine_data)

            # Add 'No. Register' column with the current page number
            main_machine_df['No. Register'] = page_number
            auxiliary_engine_df['No. Register'] = page_number

            return main_machine_df, auxiliary_engine_df
        else:
            print(f"No tables found on page {page_number}")
            return pd.DataFrame(), pd.DataFrame()
    else:
        print(f"Failed to retrieve page {page_number}. Status code: {response.status_code}")
        return pd.DataFrame(), pd.DataFrame()

# Base URL
base_url = "https://www.bki.co.id/shipregister-{}.html#"

# List to store all extracted data
all_ship_data = []
all_main_machine_dfs = []
all_auxiliary_engine_dfs = []

# Loop through the range of URLs
for page_num in range(1, 28371):
    url = base_url.format(page_num)
    print(f"Processing URL: {url}")
    # Add a retry mechanism with exponential backoff
    for attempt in range(5):  # Try up to 5 times
        try:
            ship_data = extract_data_from_url(url)
            if ship_data:
                all_ship_data.extend(ship_data)
            
            main_machine_df, auxiliary_engine_df = extract_machine_data(page_num)
            all_main_machine_dfs.append(main_machine_df)
            all_auxiliary_engine_dfs.append(auxiliary_engine_df)
            
            break  # Exit the retry loop if successful
        except (requests.exceptions.RequestException, requests.exceptions.ConnectTimeout) as e:
            print(f"Attempt {attempt + 1} failed for URL: {url}, Error: {e}")
            time.sleep(2 ** attempt)  # Exponential backoff: wait 1, 2, 4, 8, ... seconds
        
    
    time.sleep(1)

# Create a Pandas DataFrame from the combined ship data
ship_df = pd.DataFrame(all_ship_data)

# Concatenate all main machine and auxiliary engine DataFrames
final_main_machine_df = pd.concat(all_main_machine_dfs, ignore_index=True)
final_auxiliary_engine_df = pd.concat(all_auxiliary_engine_dfs, ignore_index=True)

"""# Filter out rows containing 'NIL' in any column
final_main_machine_df = final_main_machine_df[~final_main_machine_df.apply(lambda row: row.astype(str).str.contains('NIL').any(), axis=1)]
final_auxiliary_engine_df = final_auxiliary_engine_df[~final_auxiliary_engine_df.apply(lambda row: row.astype(str).str.contains('NIL').any(), axis=1)]
"""
# Function to transform DataFrame to horizontal format
def transform_to_horizontal(df, headers):
    if df.empty:
        return pd.DataFrame(columns=headers)

    # Create a new DataFrame with repeated headers
    new_columns = []
    for i in range(len(df)):
        new_columns.extend([f"{col}_{i+1}" for col in headers])

    # Flatten the data
    flat_data = []
    for _, row in df.iterrows():
        flat_data.extend(row.values)

    # Create a new DataFrame with the flattened data
    horizontal_df = pd.DataFrame([flat_data], columns=new_columns)
    return horizontal_df

# Transform main_machine and auxiliary_engine DataFrames
main_machine_columns = ['Merk', 'Manufacture', 'Cyl', 'Tenaga', 'RPM', 'Year', 'Model', 'Serie', 'Position']
auxiliary_engine_columns = ['Merk', 'Manufacture', 'Location', 'Model', 'BHP', 'Year']

main_machine_horizontal_dfs = []
auxiliary_engine_horizontal_dfs = []

for page_number in range(1, 28371):
    main_machine_page_df = final_main_machine_df[final_main_machine_df['No. Register'] == page_number]
    auxiliary_engine_page_df = final_auxiliary_engine_df[final_auxiliary_engine_df['No. Register'] == page_number]

    main_machine_horizontal_df = transform_to_horizontal(main_machine_page_df[main_machine_columns], main_machine_columns)
    auxiliary_engine_horizontal_df = transform_to_horizontal(auxiliary_engine_page_df[auxiliary_engine_columns], auxiliary_engine_columns)

    main_machine_horizontal_dfs.append(main_machine_horizontal_df)
    auxiliary_engine_horizontal_dfs.append(auxiliary_engine_horizontal_df)

# Concatenate all horizontal DataFrames
final_main_machine_horizontal_df = pd.concat(main_machine_horizontal_dfs, ignore_index=True)
final_auxiliary_engine_horizontal_df = pd.concat(auxiliary_engine_horizontal_dfs, ignore_index=True)

# Combine both DataFrames into a single DataFrame
testT1_df = pd.concat([final_main_machine_horizontal_df, final_auxiliary_engine_horizontal_df], axis=1)

# Add 'Nama Kapal' and 'Status' columns to the combined DataFrame
testT1_df.insert(0, 'No. Register', ship_df['No. Register'])
#testT1_df.insert(1, 'Nama Kapal', ship_df['Nama Kapal'])
#testT1_df.insert(2, 'Status', ship_df['Status'])

# Print the final combined DataFrame
print("testT1 DataFrame:")
print(testT1_df)

# Save DataFrame in pickle format
testT1_df.to_pickle('testT1.pkl')

# Optionally, save the DataFrame to an Excel file
testT1_df.to_excel("testT1.xlsx", index=False)
print("Data berhasil disimpan ke dalam file 'testT1.xlsx'.")
