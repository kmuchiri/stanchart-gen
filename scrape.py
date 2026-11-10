import csv
import requests
from bs4 import beautifulsoup
import xml.etree.ElementTree as ET
from pathlib import Path
import os

process_folder=Path("data/processing/xml")

'''
loadXML
Dumps the XML file from a website into a file
link:str - the url of the xml file
filename:str - filename of the XML file
'''
def loadXML(link:str,filename:str):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    url = link
    resp = requests.get(url,headers=headers)
    with open(f"{filename}.xml",'wb') as f:
        f.write(resp.content)

def processURL(link:str):
    pass