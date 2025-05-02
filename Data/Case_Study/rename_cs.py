import os
import re

# Set your parent directory here
parent_dir = os.path.dirname(__file__)

# Regular expression to match folder names
pattern = re.compile(r'^([A-Z]{2}(?:-[A-Z]{2}){1,3})_(Collab|Autarky)$')

for folder in os.listdir(parent_dir):
    match = pattern.match(folder)
    if match:
        countries, suffix = match.groups()
        country_list = countries.split('-')
        sorted_countries = sorted(country_list)

        new_folder_name = '-'.join(sorted_countries) + f'_{suffix}'

        if folder != new_folder_name:
            old_path = os.path.join(parent_dir, folder)
            new_path = os.path.join(parent_dir, new_folder_name)
            print(f'Renaming: {folder} → {new_folder_name}')
            os.rename(old_path, new_path)