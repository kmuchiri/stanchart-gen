import csv
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
import os
import json
import time

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
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',"Accept": "application/xml" }
        url = link
        resp = requests.get(url,headers=headers)
        resp.raise_for_status()

        print(f"HTTP Status Code: {resp.status_code}")
        print(f"Content Type Header: {resp.headers.get('Content-Type')}")
        
        root = ET.fromstring(resp.content)
        last_tag = root.find(f".//last").text
        print(last_tag)

        if last_tag is "true":
            is_last = True

        with open(f"{filename}.xml",'wb') as f:
            f.write(resp.content)

        return is_last
    except requests.exceptions.RequestException as e:
        print(f"\nNetwork error: {e}")
    except ET.ParseError as e:
        print(f"\nFailed to parse XML: {e}")



def getEvents(file:json):
    events = file
    for event in events:
        print (event)
        page_num = int(0)
        eventName = event["eventName"]
        eventURL = event["eventURL"]

        process_path = os.path.join(process_folder,eventName)
        os.makedirs(process_path,exist_ok=True)

        url = f"{eventURL}participants?page={page_num}&size=10&category=ALL_RESULTS"
        print(url)

        last = False
        
        while last is False:
            file_path=os.path.join(process_path,f"page_{page_num}")
            filename_str = str(file_path)
            last = loadXML(url,filename_str)
            page_num += 1
            print(page_num)
            time.sleep(2)

def main():
    getEvents(events)

if __name__ == "__main__":
    main()

