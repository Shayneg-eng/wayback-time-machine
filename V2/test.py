from comcrawl import IndexClient
from bs4 import BeautifulSoup
import requests

# Disable SSL verification warnings
requests.packages.urllib3.disable_warnings()

# Monkey patch the requests to disable SSL verification
import comcrawl.utils.initialization
original_get = requests.get
requests.get = lambda *args, **kwargs: original_get(*args, **{**kwargs, 'verify': False})

client = IndexClient()
client.search("*")  # Search for any URL
client.download()

first_page_html = client.results[0]["html"]

# Parse and extract text content
soup = BeautifulSoup(first_page_html, 'html.parser')
text_content = soup.get_text(separator='\n', strip=True)

print(text_content)