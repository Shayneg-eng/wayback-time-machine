import requests
import json
from datetime import datetime
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
import time

def parse_date_input(date_input):
    """
    Parse user date input and convert to Wayback timestamp format
    """
    try:
        # Try different date formats
        date_formats = [
            "%Y-%m-%d",      # 2023-01-15
            "%m/%d/%Y",      # 01/15/2023
            "%m-%d-%Y",      # 01-15-2023
            "%Y/%m/%d",      # 2023/01/15
            "%B %d, %Y",     # January 15, 2023
            "%b %d, %Y",     # Jan 15, 2023
            "%d %B %Y",      # 15 January 2023
            "%d %b %Y",      # 15 Jan 2023
        ]
        
        for date_format in date_formats:
            try:
                parsed_date = datetime.strptime(date_input, date_format)
                # Convert to Wayback timestamp format (YYYYMMDD)
                return parsed_date.strftime("%Y%m%d")
            except ValueError:
                continue
        
        # If no format worked, raise an error
        raise ValueError("Invalid date format")
    
    except ValueError:
        print("Invalid date format. Please use formats like:")
        print("  - YYYY-MM-DD (e.g., 2023-01-15)")
        print("  - MM/DD/YYYY (e.g., 01/15/2023)")
        print("  - January 15, 2023")
        print("  - Jan 15, 2023")
        return None

def get_wayback_url(url, timestamp):
    """
    Get the Wayback Machine URL for a given URL and timestamp
    """
    api_url = f"http://archive.org/wayback/available?url={url}&timestamp={timestamp}"
    
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()
        
        if 'archived_snapshots' in data and 'closest' in data['archived_snapshots']:
            snapshot = data['archived_snapshots']['closest']
            if snapshot.get('available', False):
                return snapshot['url'], snapshot['timestamp']
        
        return None, None
    except requests.RequestException as e:
        print(f"Error accessing Wayback API: {e}")
        return None, None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        return None, None

def get_page_content_with_metadata(wayback_url):
    """
    Enhanced version that returns both text content and BeautifulSoup object
    """
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
        print(f"Error fetching page content: {e}")
        return None
    except Exception as e:
        print(f"Error processing page content: {e}")
        return None

def extract_links(soup, base_url):
    """
    Extract all links from the soup object and convert relative URLs to absolute
    """
    links = []
    
    # Extract the timestamp from the Wayback URL
    wayback_timestamp = extract_timestamp_from_wayback(base_url)
    
    # Find all anchor tags with href attributes
    for link in soup.find_all('a', href=True):
        href = link['href'].strip()
        
        # Skip empty hrefs, javascript, mailto, and anchor links
        if not href or href.startswith(('#', 'javascript:', 'mailto:', 'ftp:')):
            continue
        
        final_url = None
        
        # Check if href is already a Wayback URL
        if href.startswith('/web/') and wayback_timestamp:
            # This is a relative Wayback URL, make it absolute
            final_url = f"http://web.archive.org{href}"
        elif href.startswith('http') and 'web.archive.org' in href:
            # Already a complete Wayback URL
            final_url = href
        elif href.startswith('http'):
            # Regular absolute URL - convert to Wayback
            if 'cnn.com' in href.lower():
                clean_url = href.replace(':80/', '/').replace(':80', '')
                final_url = f"http://web.archive.org/web/{wayback_timestamp}/{clean_url}"
        elif href.startswith('/'):
            # Root-relative URL - convert to Wayback
            original_url = f"http://www.cnn.com{href}"
            final_url = f"http://web.archive.org/web/{wayback_timestamp}/{original_url}"
        else:
            # Relative URL - convert to Wayback
            original_url = f"http://www.cnn.com/{href}"
            final_url = f"http://web.archive.org/web/{wayback_timestamp}/{original_url}"
        
        # Only add CNN-related URLs
        if final_url and ('cnn.com' in final_url.lower() or 'web.archive.org' in final_url):
            # Extract original URL to check if it's CNN
            if 'web.archive.org' in final_url:
                original_check = extract_original_url_from_wayback(final_url)
                if original_check and 'cnn.com' in original_check.lower():
                    links.append(final_url)
            elif 'cnn.com' in final_url.lower():
                links.append(final_url)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_links = []
    for link in links:
        if link not in seen:
            seen.add(link)
            unique_links.append(link)
    
    print(f"Debug: Found {len(unique_links)} links after processing")
    if unique_links:
        print(f"Debug: First few links: {unique_links[:3]}")
    
    return unique_links

def crawl_cnn_links(homepage_data, max_links=20, delay=1):
    """
    Crawl links found on the CNN homepage one level deep
    """
    if not homepage_data or not homepage_data.get('soup'):
        return {}
    
    print("Extracting links from homepage...")
    
    # Extract links from homepage
    links = extract_links(homepage_data['soup'], homepage_data['url'])
    
    print(f"Found {len(links)} unique CNN links")
    
    # Limit the number of links to crawl
    if len(links) > max_links:
        print(f"Limiting to first {max_links} links to avoid overwhelming the server")
        links = links[:max_links]
    
    crawled_data = {}
    
    for i, link in enumerate(links, 1):
        print(f"Crawling link {i}/{len(links)}: {link}")
        
        try:
            # Add delay to be respectful to the Wayback Machine
            if i > 1:
                time.sleep(delay)
            
            # Try to get the Wayback URL for this link
            # Extract the original URL from the Wayback URL
            original_url = extract_original_url_from_wayback(link)
            if not original_url:
                original_url = link
            
            # Get timestamp from homepage URL to find same-day archive
            homepage_timestamp = extract_timestamp_from_wayback(homepage_data['url'])
            if homepage_timestamp:
                wayback_url, actual_timestamp = get_wayback_url(original_url, homepage_timestamp)
                if wayback_url:
                    link = wayback_url
            
            page_data = get_page_content_with_metadata(link)
            
            if page_data:
                crawled_data[original_url] = {
                    'title': page_data['title'],
                    'text': page_data['text'],
                    'wayback_url': link,
                    'status': 'success'
                }
            else:
                crawled_data[original_url] = {
                    'title': 'Failed to load',
                    'text': 'Content could not be retrieved',
                    'wayback_url': link,
                    'status': 'failed'
                }
        
        except Exception as e:
            print(f"Error crawling {link}: {e}")
            crawled_data[link] = {
                'title': 'Error',
                'text': f'Error occurred: {str(e)}',
                'wayback_url': link,
                'status': 'error'
            }
    
    return crawled_data

def extract_original_url_from_wayback(wayback_url):
    """
    Extract the original URL from a Wayback Machine URL
    """
    # Wayback URLs have format: http://web.archive.org/web/TIMESTAMP/ORIGINAL_URL
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
        return match.group(1)  # Return just the timestamp
    return None

def save_crawled_data_to_json(homepage_data, crawled_data, timestamp, filename=None):
    """
    Save all crawled data to a structured JSON file
    """
    if not filename:
        date_str = datetime.strptime(timestamp[:8], "%Y%m%d").strftime("%Y-%m-%d")
        filename = f"cnn_crawl_{date_str}.json"
    
    structured_data = {
        'crawl_info': {
            'date_requested': timestamp[:8],
            'crawl_timestamp': datetime.now().isoformat(),
            'homepage_url': homepage_data['url'],
            'total_links_crawled': len(crawled_data)
        },
        'homepage': {
            'title': homepage_data['title'],
            'text': homepage_data['text'],
            'url': homepage_data['url']
        },
        'crawled_pages': crawled_data
    }
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(structured_data, f, indent=2, ensure_ascii=False)
        print(f"\nCrawled data saved to: {filename}")
        return filename
    except Exception as e:
        print(f"Error saving JSON file: {e}")
        return None

def main():
    # Check if required libraries are available
    try:
        import requests
        import bs4
    except ImportError:
        print("Required libraries not found. Please install them using:")
        print("pip install requests beautifulsoup4")
        exit(1)
    
    print("CNN Homepage Historical Content Crawler")
    print("=" * 45)
    print()
    
    while True:
        # Get date from user
        date_input = input("Enter a date to crawl CNN's homepage from that day (or 'quit' to exit): ").strip()
        
        if date_input.lower() in ['quit', 'exit', 'q']:
            print("Goodbye!")
            break
        
        # Parse the date
        timestamp = parse_date_input(date_input)
        if not timestamp:
            continue
        
        print(f"\nSearching for CNN homepage from {date_input}...")
        
        # Get Wayback URL for CNN
        cnn_url = "cnn.com"
        wayback_url, actual_timestamp = get_wayback_url(cnn_url, timestamp)
        
        if not wayback_url:
            print(f"Sorry, no archived version of CNN's homepage found for {date_input}")
            print("Try a different date.\n")
            continue
        
        # Format the actual timestamp for display
        try:
            actual_date = datetime.strptime(actual_timestamp[:8], "%Y%m%d")
            formatted_date = actual_date.strftime("%B %d, %Y")
        except:
            formatted_date = actual_timestamp[:8]
        
        print(f"Found archived version from: {formatted_date}")
        print(f"Wayback URL: {wayback_url}")
        print("\nFetching homepage content...\n")
        
        # Get homepage content with metadata
        homepage_data = get_page_content_with_metadata(wayback_url)
        
        if not homepage_data:
            print("Failed to retrieve homepage content.")
            continue
        
        print("=" * 60)
        print(f"CNN HOMEPAGE - {formatted_date}")
        print("=" * 60)
        print(f"Title: {homepage_data['title']}")
        print()
        print(homepage_data['text'][:500] + "..." if len(homepage_data['text']) > 500 else homepage_data['text'])
        print()
        
        # Ask user if they want to crawl links
        crawl_choice = input("Do you want to crawl the links on this page? (y/n): ").strip().lower()
        
        if crawl_choice in ['y', 'yes']:
            max_links = input("Maximum number of links to crawl (default 20, max 50): ").strip()
            try:
                max_links = min(int(max_links), 50) if max_links else 20
            except ValueError:
                max_links = 20
            
            print(f"\nStarting crawl of up to {max_links} links...")
            crawled_data = crawl_cnn_links(homepage_data, max_links=max_links)
            
            # Save to JSON
            json_filename = save_crawled_data_to_json(homepage_data, crawled_data, actual_timestamp)
            
            print(f"\nCrawl completed! Found content from {len(crawled_data)} pages.")
            print("Data structure:")
            print(f"  - Homepage content")
            print(f"  - {len(crawled_data)} linked pages")
            
            # Show summary of crawled pages
            successful_crawls = sum(1 for page in crawled_data.values() if page['status'] == 'success')
            print(f"  - {successful_crawls} pages successfully crawled")
            print(f"  - {len(crawled_data) - successful_crawls} pages failed or had errors")
        
        print("\n" + "-" * 60 + "\n")

if __name__ == "__main__":
    main()