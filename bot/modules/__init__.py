import os

DRIVE_NAME = []
DRIVE_ID = []
INDEX_URL = []

if os.path.exists('drivef_folder'):
    with open('drivef_folder', 'r+') as f:
        lines = f.readlines()
        for line in lines:
            temp = line.strip().split()
            DRIVE_NAME.append(temp[0].replace("_", " "))
            DRIVE_ID.append(temp[1])
            try:
                INDEX_URL.append(temp[2])
            except IndexError as e:
                INDEX_URL.append(None)

if DRIVE_ID :
    pass
else :
    LOGGER.error("The README.md file there to be read! Exiting now!")
    exit(1)

