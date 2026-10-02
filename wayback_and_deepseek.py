import requests
import json
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
import time
import os
import numpy as np
import ollama
from openai import OpenAI

# ===== CONFIGURABLE CONSTANTS =====
DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]  # Replace with your actual API key
START_DATE = "2000-01-18"  # Start date for crawling
END_DATE = datetime.now().strftime("%Y-%m-%d")  # End date (today)
PAGES_TO_CRAWL_PER_SOURCE = 10  # Number of subpages to crawl per news source
REQUEST_DELAY = 2  # Delay between requests in seconds
DEEPSEEK_REQUEST_DELAY = 1  # Delay between DeepSeek API calls in seconds
EMBEDDING_DELAY = 0.5  # Delay between embedding generation calls in seconds
MAX_RETRIES = 3  # Maximum retries for failed requests
MAIN_FOLDER_NAME = "Ultimate Archive"  # Main folder name
EMBEDDING_MODEL = "nomic-embed-text"  # Ollama embedding model

# News sources that existed since 2000
NEWS_SOURCES = {
    "CNN": "cnn.com",
    "BBC": "bbc.co.uk",
    "Reuters": "reuters.com",
    "Associated_Press": "ap.org",
    "New_York_Times": "nytimes.com",
    "Washington_Post": "washingtonpost.com",
    "USA_Today": "usatoday.com",
    "Wall_Street_Journal": "wsj.com",
    "Los_Angeles_Times": "latimes.com",
    "Chicago_Tribune": "chicagotribune.com",
    "Guardian": "theguardian.com",
    "Fox_News": "foxnews.com",
    "MSNBC": "msnbc.com",
    "ABC_News": "abcnews.go.com",
    "CBS_News": "cbsnews.com",
    "NBC_News": "nbcnews.com",
    "NPR": "npr.org",
    "Time": "time.com",
    "Newsweek": "newsweek.com",
    "The_Independent": "independent.co.uk"
}

# Initialize DeepSeek client
try:
    deepseek_client = OpenAI(
        api_key=DEEPSEEK_API_KEY, 
        base_url="https://api.deepseek.com"
    )
except Exception as e:
    print(f"Warning: DeepSeek client initialization failed: {e}")
    deepseek_client = None

def clean_filename(filename):
    """
    Clean filename to be safe for file systems
    """
    # Remove or replace problematic characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = filename.replace('\n', ' ').replace('\r', ' ')
    # Limit length
    if len(filename) > 100:
        filename = filename[:100]
    return filename.strip()

def generate_embedding(text):
    """
    Generate embedding using Ollama
    """
    try:
        if not text or len(text.strip()) < 10:
            return None
        
        # Limit text length to avoid issues
        text = text[:5000] if len(text) > 5000 else text
        
        response = ollama.embeddings(model=EMBEDDING_MODEL, prompt=text)
        embedding = response['embedding']
        
        time.sleep(EMBEDDING_DELAY)
        return np.array(embedding, dtype=np.float32)
    
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None

def save_embedding(embedding, filepath):
    """
    Save embedding as .npy file
    """
    try:
        if embedding is not None:
            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            np.save(filepath, embedding)
            print(f"Saved embedding to: {filepath}")
            return True
    except Exception as e:
        print(f"Error saving embedding to {filepath}: {e}")
    return False

def clean_text_with_deepseek(text, title="", is_news_content=True):
    """
    Clean and summarize text using DeepSeek API without removing information
    """
    if not deepseek_client:
        print("DeepSeek client not available, returning original text")
        return text
    
    if not text or len(text.strip()) < 50:
        return text
    
    try:
        if is_news_content:
            prompt = f"""Extract and clean only the main news content from this webpage text. 

Requirements:
1. Remove navigation menus, headers, footers, sidebars, and advertisement text
2. Keep ONLY the actual news article content, headlines, and story text
3. Fix formatting issues and garbled text
4. Do NOT include phrases like "Here's the cleaned version" or explanatory text
5. Return ONLY the cleaned news content
6. If this appears to be a news article, extract the headline, date, and article body
7. If this is a homepage, extract only the main news headlines and story summaries
8. Remove repeated navigation elements like "POLITICS LAW SCI-TECH SPACE HEALTH"

Title: {title}

Webpage text:
{text[:4000]}"""
        else:
            prompt = f"""Clean and organize this text content while removing navigation elements.

Requirements:
1. Remove navigation menus and repetitive elements
2. Keep main content only
3. Fix formatting issues
4. Return only the cleaned content without explanatory text

Text:
{text[:4000]}"""

        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a text extraction assistant. Extract only the main content from webpage text, removing navigation and formatting issues. Return only the cleaned content without any explanatory phrases."},
                {"role": "user", "content": prompt}
            ],
            stream=False
        )
        
        cleaned_text = response.choices[0].message.content.strip()
        time.sleep(DEEPSEEK_REQUEST_DELAY)
        return cleaned_text
    
    except Exception as e:
        print(f"Error with DeepSeek API: {e}")
        return text

def parse_date_input(date_input):
    """
    Parse date input and convert to Wayback timestamp format
    """
    try:
        parsed_date = datetime.strptime(date_input, "%Y-%m-%d")
        return parsed_date.strftime("%Y%m%d")
    except ValueError:
        print(f"Invalid date format: {date_input}")
        return None

def get_wayback_url(url, timestamp):
    """
    Get the Wayback Machine URL for a given URL and timestamp
    """
    api_url = f"http://archive.org/wayback/available?url={url}&timestamp={timestamp}"
    
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(api_url, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if 'archived_snapshots' in data and 'closest' in data['archived_snapshots']:
                snapshot = data['archived_snapshots']['closest']
                if snapshot.get('available', False):
                    return snapshot['url'], snapshot['timestamp']
            
            return None, None
        except requests.RequestException as e:
            print(f"Attempt {attempt + 1} failed for {url}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(REQUEST_DELAY)
            continue
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON response for {url}: {e}")
            return None, None
    
    return None, None

def get_page_content_with_metadata(wayback_url):
    """
    Get page content and return structured data
    """
    for attempt in range(MAX_RETRIES):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(wayback_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract title
            title = soup.find('title')
            title_text = title.get_text().strip() if title else "No title found"
            
            # Remove script and style elements for text extraction
            soup_for_text = BeautifulSoup(response.content, 'html.parser')
            for script in soup_for_text(["script", "style"]):
                script.decompose()
            
            # Get text content
            text = soup_for_text.get_text()
            
            # Clean up the text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            clean_text = '\n'.join(chunk for chunk in chunks if chunk)
            
            return {
                'text': clean_text,
                'title': title_text,
                'soup': soup,
                'url': wayback_url
            }
        
        except requests.RequestException as e:
            print(f"Attempt {attempt + 1} failed fetching {wayback_url}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(REQUEST_DELAY)
            continue
        except Exception as e:
            print(f"Error processing page content: {e}")
            return None
    
    return None

def extract_links(soup, base_url, news_source_domain):
    """
    Extract links from the soup object for the specific news source
    """
    links = []
    
    # Extract the timestamp from the Wayback URL
    wayback_timestamp = extract_timestamp_from_wayback(base_url)
    
    if not wayback_timestamp:
        return links
    
    # Find all anchor tags with href attributes
    for link in soup.find_all('a', href=True):
        href = link['href'].strip()
        
        # Skip empty hrefs, javascript, mailto, and anchor links
        if not href or href.startswith(('#', 'javascript:', 'mailto:', 'ftp:')):
            continue
        
        final_url = None
        
        # Check if href is already a Wayback URL
        if href.startswith('/web/') and wayback_timestamp:
            final_url = f"http://web.archive.org{href}"
        elif href.startswith('http') and 'web.archive.org' in href:
            final_url = href
        elif href.startswith('http'):
            # Regular absolute URL - convert to Wayback if it's from our news source
            if news_source_domain in href.lower():
                clean_url = href.replace(':80/', '/').replace(':80', '')
                final_url = f"http://web.archive.org/web/{wayback_timestamp}/{clean_url}"
        elif href.startswith('/'):
            # Root-relative URL - convert to Wayback
            original_url = f"http://{news_source_domain}{href}"
            final_url = f"http://web.archive.org/web/{wayback_timestamp}/{original_url}"
        else:
            # Relative URL - convert to Wayback
            original_url = f"http://{news_source_domain}/{href}"
            final_url = f"http://web.archive.org/web/{wayback_timestamp}/{original_url}"
        
        # Only add URLs from our news source
        if final_url and (news_source_domain in final_url.lower() or 'web.archive.org' in final_url):
            if 'web.archive.org' in final_url:
                original_check = extract_original_url_from_wayback(final_url)
                if original_check and news_source_domain in original_check.lower():
                    links.append(final_url)
            elif news_source_domain in final_url.lower():
                links.append(final_url)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_links = []
    for link in links:
        if link not in seen:
            seen.add(link)
            unique_links.append(link)
    
    return unique_links

def crawl_news_source_links(homepage_data, news_source_domain, source_name, date_dir, max_links=PAGES_TO_CRAWL_PER_SOURCE):
    """
    Crawl links found on the news source homepage and generate embeddings
    """
    if not homepage_data or not homepage_data.get('soup'):
        return {}
    
    print(f"Extracting links from {news_source_domain} homepage...")
    
    # Extract links from homepage
    links = extract_links(homepage_data['soup'], homepage_data['url'], news_source_domain)
    
    print(f"Found {len(links)} unique links for {news_source_domain}")
    
    # Limit the number of links to crawl
    if len(links) > max_links:
        print(f"Limiting to first {max_links} links")
        links = links[:max_links]
    
    crawled_data = {}
    
    # Create embedding directory for this news source
    embedding_dir = os.path.join(date_dir, source_name)
    os.makedirs(embedding_dir, exist_ok=True)
    
    for i, link in enumerate(links, 1):
        print(f"Crawling link {i}/{len(links)} for {news_source_domain}")
        
        try:
            # Add delay to be respectful
            if i > 1:
                time.sleep(REQUEST_DELAY)
            
            original_url = extract_original_url_from_wayback(link)
            if not original_url:
                original_url = link
            
            page_data = get_page_content_with_metadata(link)
            
            if page_data:
                # Clean text with DeepSeek
                cleaned_text = clean_text_with_deepseek(page_data['text'], page_data['title'], is_news_content=True)
                
                # Generate embedding from cleaned text
                embedding = generate_embedding(cleaned_text)
                
                # Save embedding with cleaned filename
                clean_title = clean_filename(page_data['title'])
                embedding_filename = f"{source_name}_{clean_title}.npy"
                embedding_path = os.path.join(embedding_dir, embedding_filename)
                save_embedding(embedding, embedding_path)
                
                crawled_data[f"page_{i}"] = {
                    'title': page_data['title'],
                    'original_text': page_data['text'],
                    'cleaned_text': cleaned_text,
                    'wayback_url': link,
                    'original_url': original_url,
                    'embedding_file': embedding_filename,
                    'status': 'success'
                }
            else:
                crawled_data[f"page_{i}"] = {
                    'title': 'Failed to load',
                    'original_text': 'Content could not be retrieved',
                    'cleaned_text': 'Content could not be retrieved',
                    'wayback_url': link,
                    'original_url': original_url,
                    'embedding_file': None,
                    'status': 'failed'
                }
        
        except Exception as e:
            print(f"Error crawling {link}: {e}")
            crawled_data[f"page_{i}"] = {
                'title': 'Error',
                'original_text': f'Error occurred: {str(e)}',
                'cleaned_text': f'Error occurred: {str(e)}',
                'wayback_url': link,
                'original_url': original_url,
                'embedding_file': None,
                'status': 'error'
            }
    
    return crawled_data

def extract_original_url_from_wayback(wayback_url):
    """
    Extract the original URL from a Wayback Machine URL
    """
    match = re.search(r'web\.archive\.org/web/(\d+)/(.+)', wayback_url)
    if match:
        return match.group(2)
    return None

def extract_timestamp_from_wayback(wayback_url):
    """
    Extract timestamp from a Wayback Machine URL
    """
    match = re.search(r'web\.archive\.org/web/(\d+)/', wayback_url)
    if match:
        return match.group(1)
    return None

def extract_date_from_timestamp(timestamp):
    """
    Extract date from Wayback timestamp (YYYYMMDDHHMMSS -> YYYY-MM-DD)
    """
    try:
        if len(timestamp) >= 8:
            date_str = timestamp[:8]
            date_obj = datetime.strptime(date_str, "%Y%m%d")
            return date_obj.strftime("%Y-%m-%d")
    except:
        pass
    return None

def validate_date_match(requested_date, wayback_url):
    """
    Check if the Wayback URL date matches the requested date
    """
    timestamp = extract_timestamp_from_wayback(wayback_url)
    if not timestamp:
        return False
    
    actual_date = extract_date_from_timestamp(timestamp)
    return actual_date == requested_date

def create_directory_structure(date_str):
    """
    Create the directory structure for a given date
    """
    main_dir = MAIN_FOLDER_NAME
    date_dir = os.path.join(main_dir, date_str)
    
    # Create directories if they don't exist
    os.makedirs(date_dir, exist_ok=True)
    
    return date_dir

def save_news_source_data(date_dir, source_name, homepage_data, crawled_data, requested_date, actual_date):
    """
    Save data for a single news source to JSON file
    """
    filename = os.path.join(date_dir, f"{source_name}.json")
    
    # Generate and save homepage embedding if homepage data exists
    homepage_embedding_file = None
    if homepage_data and homepage_data.get('cleaned_text'):
        embedding_dir = os.path.join(date_dir, source_name)
        os.makedirs(embedding_dir, exist_ok=True)
        
        homepage_embedding = generate_embedding(homepage_data['cleaned_text'])
        homepage_embedding_file = f"{source_name}main.npy"
        homepage_embedding_path = os.path.join(embedding_dir, homepage_embedding_file)
        save_embedding(homepage_embedding, homepage_embedding_path)
    
    structured_data = {
        'crawl_info': {
            'news_source': source_name,
            'requested_date': requested_date,
            'actual_date': actual_date,
            'crawl_timestamp': datetime.now().isoformat(),
            'total_pages_crawled': len(crawled_data),
            'homepage_url': homepage_data['url'] if homepage_data else None
        },
        'homepage': {
            'title': homepage_data['title'] if homepage_data else 'Failed to load',
            'original_text': homepage_data['text'] if homepage_data else 'Content could not be retrieved',
            'cleaned_text': homepage_data.get('cleaned_text', 'Content could not be retrieved'),
            'url': homepage_data['url'] if homepage_data else None,
            'embedding_file': homepage_embedding_file
        } if homepage_data else None,
        'crawled_pages': crawled_data
    }
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(structured_data, f, indent=2, ensure_ascii=False)
        print(f"Saved {source_name} data to: {filename}")
        return True
    except Exception as e:
        print(f"Error saving {source_name} data: {e}")
        return False

def process_single_date(date_str):
    """
    Process all news sources for a single date
    """
    print(f"\n{'='*60}")
    print(f"PROCESSING DATE: {date_str}")
    print(f"{'='*60}")
    
    # Create directory structure
    date_dir = create_directory_structure(date_str)
    
    # Convert date to timestamp format
    timestamp = parse_date_input(date_str)
    if not timestamp:
        print(f"Invalid date format: {date_str}")
        return
    
    # Process each news source
    for source_name, source_url in NEWS_SOURCES.items():
        print(f"\n--- Processing {source_name} ({source_url}) ---")
        
        try:
            # Get Wayback URL for this news source
            wayback_url, actual_timestamp = get_wayback_url(source_url, timestamp)
            
            if not wayback_url:
                print(f"No archived version found for {source_name} on {date_str}")
                # Save empty data
                save_news_source_data(date_dir, source_name, None, {}, date_str, None)
                continue
            
            # Validate date match
            if not validate_date_match(date_str, wayback_url):
                actual_date = extract_date_from_timestamp(actual_timestamp)
                print(f"Date mismatch for {source_name}: requested {date_str}, got {actual_date}")
                # Save empty data for date mismatch
                save_news_source_data(date_dir, source_name, None, {}, date_str, actual_date)
                continue
            
            actual_date = extract_date_from_timestamp(actual_timestamp)
            print(f"Found archived version from: {actual_date}")
            
            # Get homepage content
            homepage_data = get_page_content_with_metadata(wayback_url)
            
            if not homepage_data:
                print(f"Failed to retrieve homepage content for {source_name}")
                save_news_source_data(date_dir, source_name, None, {}, date_str, actual_date)
                continue
            
            # Clean homepage text with DeepSeek
            print(f"Cleaning homepage text for {source_name}...")
            cleaned_homepage_text = clean_text_with_deepseek(homepage_data['text'], homepage_data['title'], is_news_content=True)
            homepage_data['cleaned_text'] = cleaned_homepage_text
            
            print(f"Homepage retrieved successfully for {source_name}")
            
            # Crawl subpages (this now includes embedding generation)
            print(f"Starting to crawl subpages for {source_name}...")
            crawled_data = crawl_news_source_links(homepage_data, source_url, source_name, date_dir)
            
            # Save data (this now includes homepage embedding)
            save_news_source_data(date_dir, source_name, homepage_data, crawled_data, date_str, actual_date)
            
            print(f"Completed {source_name}: {len(crawled_data)} pages crawled")
            
            # Add delay between news sources
            time.sleep(REQUEST_DELAY)
            
        except Exception as e:
            print(f"Error processing {source_name}: {e}")
            save_news_source_data(date_dir, source_name, None, {}, date_str, None)
            continue

def generate_date_range(start_date, end_date):
    """
    Generate all dates between start_date and end_date (inclusive)
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    
    current = start
    while current <= end:
        yield current.strftime("%Y-%m-%d")
        current += timedelta(days=1)

def main():
    """
    Main function to run the complete crawling operation
    """
    print("Ultimate News Archive Crawler with Embeddings")
    print("=" * 55)
    print(f"Date range: {START_DATE} to {END_DATE}")
    print(f"News sources: {len(NEWS_SOURCES)}")
    print(f"Pages per source: {PAGES_TO_CRAWL_PER_SOURCE}")
    print(f"Main folder: {MAIN_FOLDER_NAME}")
    print(f"Embedding model: {EMBEDDING_MODEL}")
    print("=" * 55)
    
    # Check if DeepSeek is configured
    if not deepseek_client:
        print("WARNING: DeepSeek API not configured. Text cleaning will be skipped.")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            return
    
    # Test Ollama connection
    try:
        test_embedding = ollama.embeddings(model=EMBEDDING_MODEL, prompt="test")
        print(f"✓ Ollama connection successful with model {EMBEDDING_MODEL}")
    except Exception as e:
        print(f"✗ Ollama connection failed: {e}")
        response = input("Continue without embeddings? (y/n): ")
        if response.lower() != 'y':
            return
    
    # Generate all dates
    all_dates = list(generate_date_range(START_DATE, END_DATE))
    total_dates = len(all_dates)
    
    print(f"\nTotal dates to process: {total_dates}")
    print("Starting crawl...\n")
    
    # Process each date
    for i, date_str in enumerate(all_dates, 1):
        print(f"\nProgress: {i}/{total_dates} ({(i/total_dates)*100:.1f}%)")
        
        try:
            process_single_date(date_str)
        except KeyboardInterrupt:
            print("\n\nCrawling interrupted by user.")
            break
        except Exception as e:
            print(f"Error processing date {date_str}: {e}")
            continue
    
    print(f"\n{'='*60}")
    print("CRAWLING COMPLETED!")
    print(f"Processed {i} dates out of {total_dates}")
    print(f"Data saved in: {MAIN_FOLDER_NAME}/")
    print(f"{'='*60}")

if __name__ == "__main__":
    # Check if required libraries are available
    try:
        import requests
        import bs4
        import numpy as np
        import ollama
    except ImportError:
        print("Required libraries not found. Please install them using:")
        print("pip install requests beautifulsoup4 openai numpy ollama")
        exit(1)
    
    main()