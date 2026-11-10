import csv
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
import os
import json

process_folder=Path("data/processing/xml")

with open ("events.json","r") as file:
    events = json.load(file)

'''
loadXML
Dumps the XML file from a website into a file and checks if the current page is the last page.
link:str - the url of the xml file
filename:str - filename of the XML file
'''
def loadXML(link:str,filename:str) -> bool:
    try: 
        is_last=False
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        url = link
        resp = requests.get(url,headers=headers)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        last_tag = root.find(f".//last")

        if last_tag is True:
            is_last = last_tag

        with open(f"{filename}.xml",'wb') as f:
            f.write(resp.content)

        return is_last
    except requests.exceptions.RequestException as e:
        print(f"Network error: {e}")
    except ET.ParseError as e:
        print(f"Failed to parse XML: {e}")



def getEvents():
    
    for event in events:
        eventName = event["eventName"]
        eventURL = event["eventURL"]

    process_path = os.join.path(process_folder,eventURL)
    
