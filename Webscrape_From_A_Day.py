import requests
from bs4 import BeautifulSoup
import json
import time
import random
from datetime import datetime, timedelta
from urllib.parse import urlencode, quote, urlparse
import re
from dataclasses import dataclass
from typing import List, Dict, Optional
import cloudscraper
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import concurrent.futures
import threading

class AdvancedHistoricalNewsScraper:
    def __init__(self):
        # Use CloudScraper to bypass basic anti-bot measures
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False
            }
        )
        
        # Fallback session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        self.search_terms = [
            "US news", "national news", "breaking news", "major events", 
            "US politics", "elections", "government policy", "Congress legislation", 
            "Supreme Court", "crime justice", "shootings", "protests demonstrations",
            "economy markets", "business news", "company news", "financial reports",
            "science technology", "health medicine", "hospitals public health",
            "environment climate", "natural disasters", "education schools",
            "sports highlights", "entertainment news", "celebrity news", "TV movies",
            "internet trends", "social media", "tech launches", "innovation research",
            "public safety"
        ]
        
        # Multiple search engines and sources
        self.search_engines = [
            'google', 'bing', 'duckduckgo', 'startpage', 'searx'
        ]
        
        # Major news sources for direct searching
        self.news_sources = [
            'cnn.com', 'reuters.com', 'apnews.com', 'bbc.com', 'npr.org',
            'cbsnews.com', 'abcnews.go.com', 'nytimes.com', 'washingtonpost.com',
            'usatoday.com', 'foxnews.com', 'nbcnews.com', 'politico.com',
            'thehill.com', 'bloomberg.com', 'wsj.com', 'guardian.com',
            'latimes.com', 'chicagotribune.com', 'nypost.com'
        ]
        
        self.driver = None
        
    def setup_selenium_driver(self):
        """Setup Selenium WebDriver for JavaScript-heavy sites"""
        if self.driver is None:
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            try:
                self.driver = webdriver.Chrome(options=chrome_options)
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            except Exception as e:
                print(f"Could not setup Selenium driver: {e}")
                self.driver = None
    
    def search_google_comprehensive(self, query: str, target_date: str, max_results: int = 10) -> List[Dict]:
        """Comprehensive Google search with date filtering"""
        results = []
        
        try:
            # Format date for Google
            date_obj = datetime.strptime(target_date, "%Y-%m-%d")
            date_formatted = date_obj.strftime("%m/%d/%Y")
            
            # Multiple search variations
            search_variations = [
                f'"{query}" after:{date_formatted} before:{date_formatted}',
                f'{query} site:news after:{date_formatted} before:{date_formatted}',
                f'{query} intitle:"{date_obj.strftime("%B %d, %Y")}"',
                f'{query} "{date_obj.strftime("%B %d, %Y")}"',
                f'{query} "{date_obj.strftime("%m/%d/%Y")}"'
            ]
            
            for search_query in search_variations:
                # Try multiple Google domains
                google_domains = [
                    'https://www.google.com/search',
                    'https://www.google.ca/search',
                    'https://www.google.co.uk/search'
                ]
                
                for google_url in google_domains:
                    try:
                        params = {
                            'q': search_query,
                            'num': max_results,
                            'hl': 'en',
                            'lr': 'lang_en',
                            'tbm': 'nws'  # News search
                        }
                        
                        # Try CloudScraper first
                        response = self.scraper.get(google_url, params=params, timeout=15)
                        
                        if response.status_code == 200:
                            soup = BeautifulSoup(response.content, 'html.parser')
                            search_results = self.parse_google_results(soup)
                            results.extend(search_results)
                            
                            if len(results) >= max_results:
                                break
                        
                        time.sleep(random.uniform(2, 5))
                        
                    except Exception as e:
                        print(f"Google search error: {e}")
                        continue
                
                if len(results) >= max_results:
                    break
                    
        except Exception as e:
            print(f"Google comprehensive search error: {e}")
        
        return results[:max_results]
    
    def search_bing_comprehensive(self, query: str, target_date: str, max_results: int = 10) -> List[Dict]:
        """Comprehensive Bing search"""
        results = []
        
        try:
            date_obj = datetime.strptime(target_date, "%Y-%m-%d")
            
            search_variations = [
                f'{query} site:news',
                f'"{query}" {date_obj.strftime("%B %d, %Y")}',
                f'{query} {date_obj.strftime("%m/%d/%Y")}',
                f'{query} news {target_date}'
            ]
            
            for search_query in search_variations:
                bing_url = "https://www.bing.com/search"
                params = {
                    'q': search_query,
                    'count': max_results,
                    'qft': f'filterui:newsdate-lt{target_date}T23:59:59.999Z filterui:newsdate-gt{target_date}T00:00:00.000Z'
                }
                
                try:
                    response = self.scraper.get(bing_url, params=params, timeout=15)
                    
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.content, 'html.parser')
                        search_results = self.parse_bing_results(soup)
                        results.extend(search_results)
                        
                        if len(results) >= max_results:
                            break
                    
                    time.sleep(random.uniform(1, 3))
                    
                except Exception as e:
                    print(f"Bing search error: {e}")
                    continue
        
        except Exception as e:
            print(f"Bing comprehensive search error: {e}")
        
        return results[:max_results]
    
    def search_duckduckgo(self, query: str, target_date: str, max_results: int = 10) -> List[Dict]:
        """DuckDuckGo search (generally more permissive)"""
        results = []
        
        try:
            date_obj = datetime.strptime(target_date, "%Y-%m-%d")
            search_query = f'{query} {date_obj.strftime("%B %d, %Y")} site:news'
            
            ddg_url = "https://duckduckgo.com/html/"
            params = {
                'q': search_query,
                'kl': 'us-en'
            }
            
            response = self.session.get(ddg_url, params=params, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                search_results = self.parse_duckduckgo_results(soup)
                results.extend(search_results)
            
        except Exception as e:
            print(f"DuckDuckGo search error: {e}")
        
        return results[:max_results]
    
    def search_news_sites_directly(self, query: str, target_date: str, max_results: int = 10) -> List[Dict]:
        """Search news sites directly"""
        results = []
        
        date_obj = datetime.strptime(target_date, "%Y-%m-%d")
        
        for source in self.news_sources[:10]:  # Limit to avoid overwhelming
            try:
                # Try different search patterns for each site
                search_patterns = [
                    f'site:{source} "{query}" {date_obj.strftime("%B %d, %Y")}',
                    f'site:{source} {query} {target_date}',
                    f'site:{source}/search?q={quote(query)}'
                ]
                
                for pattern in search_patterns:
                    try:
                        if pattern.startswith('site:'):
                            # Use Google to search within site
                            google_url = "https://www.google.com/search"
                            params = {'q': pattern, 'num': 5}
                            response = self.scraper.get(google_url, params=params, timeout=10)
                        else:
                            # Direct site search
                            response = self.scraper.get(pattern, timeout=10)
                        
                        if response.status_code == 200:
                            soup = BeautifulSoup(response.content, 'html.parser')
                            site_results = self.parse_generic_results(soup, source)
                            results.extend(site_results)
                            
                            if len(results) >= max_results:
                                break
                        
                        time.sleep(random.uniform(1, 2))
                        
                    except Exception as e:
                        continue
                
                if len(results) >= max_results:
                    break
                    
            except Exception as e:
                print(f"Direct site search error for {source}: {e}")
                continue
        
        return results[:max_results]
    
    def search_wayback_machine_aggressive(self, query: str, target_date: str, max_results: int = 10) -> List[Dict]:
        """Aggressive Wayback Machine search"""
        results = []
        
        try:
            date_obj = datetime.strptime(target_date, "%Y-%m-%d")
            timestamp = date_obj.strftime("%Y%m%d")
            
            for source in self.news_sources[:15]:
                try:
                    # Get snapshots for that specific date
                    cdx_url = "http://web.archive.org/cdx/search/cdx"
                    params = {
                        'url': f"{source}/*",
                        'from': timestamp,
                        'to': timestamp,
                        'output': 'json',
                        'limit': 20,
                        'filter': 'statuscode:200'
                    }
                    
                    response = self.session.get(cdx_url, params=params, timeout=15)
                    
                    if response.status_code == 200:
                        try:
                            data = response.json()
                            for row in data[1:]:  # Skip header
                                if len(row) >= 3:
                                    archived_url = f"http://web.archive.org/web/{row[1]}/{row[2]}"
                                    
                                    # Check if URL might contain relevant content
                                    url_lower = row[2].lower()
                                    query_words = query.lower().split()
                                    
                                    if any(word in url_lower for word in query_words) or \
                                       any(keyword in url_lower for keyword in ['news', 'article', 'story']):
                                        
                                        results.append({
                                            'title': f"Archived: {query} from {source}",
                                            'url': archived_url,
                                            'source': f"{source} (Wayback)",
                                            'original_url': row[2],
                                            'timestamp': row[1]
                                        })
                        except json.JSONDecodeError:
                            continue
                    
                    time.sleep(0.5)
                    
                    if len(results) >= max_results:
                        break
                        
                except Exception as e:
                    continue
        
        except Exception as e:
            print(f"Wayback Machine search error: {e}")
        
        return results[:max_results]
    
    def parse_google_results(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse Google search results"""
        results = []
        
        # Multiple selectors for different Google layouts
        selectors = [
            'div.g', 'div[data-ved]', '.rc', '.g .r', 'div.ZINbbc',
            'div[jscontroller="SC7lYd"]', 'div.MjjYud'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                for element in elements:
                    try:
                        title_elem = element.select_one('h3, .LC20lb, .r a h3, [role="heading"]')
                        link_elem = element.select_one('a[href]')
                        
                        if title_elem and link_elem:
                            title = title_elem.get_text(strip=True)
                            url = link_elem.get('href', '')
                            
                            if url.startswith('/url?'):
                                # Extract actual URL from Google redirect
                                import urllib.parse
                                parsed = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                                url = parsed.get('q', [url])[0]
                            
                            if url.startswith('http') and title:
                                results.append({
                                    'title': title,
                                    'url': url,
                                    'source': 'Google Search'
                                })
                    except Exception:
                        continue
                break
        
        return results
    
    def parse_bing_results(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse Bing search results"""
        results = []
        
        selectors = [
            '.b_algo', '.b_algoheader', '.NewsArticle', '.na_cnt'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                for element in elements:
                    try:
                        title_elem = element.select_one('h2 a, .b_algoheader a, h3 a')
                        
                        if title_elem:
                            title = title_elem.get_text(strip=True)
                            url = title_elem.get('href', '')
                            
                            if url.startswith('http') and title:
                                results.append({
                                    'title': title,
                                    'url': url,
                                    'source': 'Bing Search'
                                })
                    except Exception:
                        continue
                break
        
        return results
    
    def parse_duckduckgo_results(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse DuckDuckGo search results"""
        results = []
        
        elements = soup.select('.result__body, .web-result')
        
        for element in elements:
            try:
                title_elem = element.select_one('.result__title a, .result__a')
                
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    url = title_elem.get('href', '')
                    
                    if url.startswith('http') and title:
                        results.append({
                            'title': title,
                            'url': url,
                            'source': 'DuckDuckGo Search'
                        })
            except Exception:
                continue
        
        return results
    
    def parse_generic_results(self, soup: BeautifulSoup, source: str) -> List[Dict]:
        """Parse results from any webpage"""
        results = []
        
        # Generic selectors for article links
        selectors = [
            'a[href*="article"]', 'a[href*="story"]', 'a[href*="news"]',
            '.article-title a', '.headline a', '.story-headline a',
            'h1 a', 'h2 a', 'h3 a', '.title a'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for element in elements[:5]:  # Limit per selector
                try:
                    title = element.get_text(strip=True)
                    url = element.get('href', '')
                    
                    if not url.startswith('http'):
                        if url.startswith('/'):
                            url = f"https://{source}{url}"
                        else:
                            url = f"https://{source}/{url}"
                    
                    if title and url:
                        results.append({
                            'title': title,
                            'url': url,
                            'source': source
                        })
                except Exception:
                    continue
        
        return results
    
    def extract_article_text_aggressive(self, url: str) -> Optional[str]:
        """Aggressive text extraction with multiple methods"""
        methods = ['cloudscraper', 'requests', 'selenium']
        
        for method in methods:
            try:
                if method == 'cloudscraper':
                    response = self.scraper.get(url, timeout=20)
                elif method == 'requests':
                    response = self.session.get(url, timeout=20)
                elif method == 'selenium':
                    if self.driver is None:
                        self.setup_selenium_driver()
                    if self.driver:
                        self.driver.get(url)
                        time.sleep(3)
                        response = type('Response', (), {
                            'content': self.driver.page_source.encode(),
                            'status_code': 200
                        })()
                    else:
                        continue
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Remove unwanted elements
                    for element in soup(['script', 'style', 'nav', 'header', 'footer', 
                                       'aside', 'advertisement', 'ad', '.ad', '#ad',
                                       '.comments', '.social', '.share', '.related']):
                        element.decompose()
                    
                    # Comprehensive content selectors
                    content_selectors = [
                        # News-specific selectors
                        'article .story-body', 'article .content', 'article .text',
                        '.article-content', '.story-content', '.entry-content',
                        '.post-content', '.article-body', '.content-body',
                        '.story-text', '.article-text', '.news-content',
                        '.main-content', '.primary-content', '.body-content',
                        
                        # JSON-LD structured data
                        'script[type="application/ld+json"]',
                        
                        # Generic selectors
                        'article', '.content', '.main', '#content', '#main',
                        '.container .content', '.wrapper .content'
                    ]
                    
                    article_text = ""
                    
                    # Try structured data first
                    json_scripts = soup.find_all('script', type='application/ld+json')
                    for script in json_scripts:
                        try:
                            data = json.loads(script.string)
                            if isinstance(data, dict) and 'articleBody' in data:
                                article_text = data['articleBody']
                                break
                            elif isinstance(data, list):
                                for item in data:
                                    if isinstance(item, dict) and 'articleBody' in item:
                                        article_text = item['articleBody']
                                        break
                        except:
                            continue
                    
                    # If no structured data, try selectors
                    if not article_text:
                        for selector in content_selectors:
                            elements = soup.select(selector)
                            if elements:
                                text_parts = []
                                for elem in elements:
                                    text = elem.get_text(strip=True)
                                    if len(text) > 50:  # Ensure substantial content
                                        text_parts.append(text)
                                
                                article_text = ' '.join(text_parts)
                                if len(article_text) > 200:
                                    break
                    
                    # Final fallback: all paragraphs
                    if len(article_text) < 200:
                        paragraphs = soup.find_all('p')
                        article_text = ' '.join([
                            p.get_text(strip=True) for p in paragraphs 
                            if len(p.get_text(strip=True)) > 30
                        ])
                    
                    # Clean text
                    article_text = re.sub(r'\s+', ' ', article_text).strip()
                    
                    if len(article_text) > 150:  # Minimum threshold
                        return article_text[:15000]  # Limit length
                
            except Exception as e:
                print(f"Extraction method {method} failed for {url}: {e}")
                continue
        
        return None
    
    def search_all_engines(self, query: str, target_date: str, max_results_per_engine: int = 15) -> List[Dict]:
        """Search all available engines and sources"""
        all_results = []
        
        search_methods = [
            ('Google', self.search_google_comprehensive),
            ('Bing', self.search_bing_comprehensive),
            ('DuckDuckGo', self.search_duckduckgo),
            ('Direct Sites', self.search_news_sites_directly),
            ('Wayback Machine', self.search_wayback_machine_aggressive)
        ]
        
        for engine_name, search_method in search_methods:
            try:
                print(f"    Searching {engine_name}...")
                results = search_method(query, target_date, max_results_per_engine)
                
                # Add engine info to results
                for result in results:
                    result['search_engine'] = engine_name
                
                all_results.extend(results)
                print(f"    {engine_name}: Found {len(results)} results")
                
                # Delay between engines
                time.sleep(random.uniform(2, 4))
                
            except Exception as e:
                print(f"    {engine_name} search failed: {e}")
                continue
        
        # Remove duplicates based on URL
        seen_urls = set()
        unique_results = []
        for result in all_results:
            url = result.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(result)
        
        print(f"    Total unique results: {len(unique_results)}")
        return unique_results
    
    def process_search_term_parallel(self, search_term: str, target_date: str, max_articles: int = 10):
        """Process a single search term with parallel article extraction"""
        print(f"\nProcessing: {search_term}")
        
        # Get all search results
        search_results = self.search_all_engines(search_term, target_date, max_results_per_engine=20)
        
        # Limit and shuffle for variety
        if len(search_results) > max_articles * 2:
            random.shuffle(search_results)
            search_results = search_results[:max_articles * 2]
        
        articles = []
        successful_extractions = 0
        
        # Use ThreadPoolExecutor for parallel text extraction
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_result = {
                executor.submit(self.extract_article_text_aggressive, result['url']): result 
                for result in search_results
            }
            
            for future in concurrent.futures.as_completed(future_to_result, timeout=300):
                if successful_extractions >= max_articles:
                    break
                    
                result = future_to_result[future]
                try:
                    article_text = future.result(timeout=30)
                    
                    if article_text:
                        article = {
                            'title': result.get('title', 'No title'),
                            'url': result.get('url', ''),
                            'source': result.get('source', 'Unknown'),
                            'search_engine': result.get('search_engine', 'Unknown'),
                            'text': article_text,
                            'word_count': len(article_text.split()),
                            'search_term': search_term,
                            'extraction_timestamp': datetime.now().isoformat(),
                            'target_date': target_date
                        }
                        
                        articles.append(article)
                        successful_extractions += 1
                        print(f"  ✓ Extracted article {successful_extractions}: {article['title'][:60]}...")
                
                except Exception as e:
                    print(f"  ✗ Extraction failed: {e}")
                    continue
        
        print(f"  Completed: {successful_extractions} articles extracted for '{search_term}'")
        return articles
    
    def create_comprehensive_snapshot(self, target_date: str, max_articles_per_term: int = 10) -> Dict:
        """Create the most comprehensive historical snapshot possible"""
        print(f"Creating COMPREHENSIVE historical snapshot for: {target_date}")
        print("=" * 80)
        
        snapshot_data = {
            'date': target_date,
            'snapshot_created': datetime.now().isoformat(),
            'search_terms': self.search_terms,
            'max_articles_per_term': max_articles_per_term,
            'articles': [],
            'summary': {
                'total_articles': 0,
                'total_words': 0,
                'search_terms_processed': 0,
                'search_terms_with_results': 0,
                'sources': set(),
                'search_engines': set()
            }
        }
        
        # Process each search term
        for i, search_term in enumerate(self.search_terms):
            print(f"\n[{i+1}/{len(self.search_terms)}] Processing: {search_term}")
            print("-" * 60)
            
            try:
                articles = self.process_search_term_parallel(
                    search_term, target_date, max_articles_per_term
                )
                
                snapshot_data['articles'].extend(articles)
                
                # Update summary
                for article in articles:
                    snapshot_data['summary']['sources'].add(article['source'])
                    snapshot_data['summary']['search_engines'].add(article['search_engine'])
                    snapshot_data['summary']['total_words'] += article['word_count']
                
                if articles:
                    snapshot_data['summary']['search_terms_with_results'] += 1
                
                snapshot_data['summary']['search_terms_processed'] += 1
                
            except Exception as e:
                print(f"Error processing '{search_term}': {e}")
                continue
        
        # Convert sets to lists for JSON serialization
        snapshot_data['summary']['sources'] = list(snapshot_data['summary']['sources'])
        snapshot_data['summary']['search_engines'] = list(snapshot_data['summary']['search_engines'])
        snapshot_data['summary']['total_articles'] = len(snapshot_data['articles'])
        
        return snapshot_data
    
    def save_comprehensive_snapshot(self, snapshot_data: Dict) -> str:
        """Save comprehensive snapshot with detailed metadata"""
        date_str = snapshot_data['date'].replace('-', '_')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"comprehensive_historical_snapshot_{date_str}_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(snapshot_data, f, indent=2, ensure_ascii=False)
        
        # Also save a summary file
        summary_filename = f"summary_{date_str}_{timestamp}.json"
        summary_data = {
            'date': snapshot_data['date'],
            'summary': snapshot_data['summary'],
            'search_terms': snapshot_data['search_terms'],
            'article_titles': [article['title'] for article in snapshot_data['articles']]
        }
        
        with open(summary_filename, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, indent=2, ensure_ascii=False)
        
        return filename
    
    def print_comprehensive_summary(self, snapshot_data: Dict):
        """Print detailed summary"""
        summary = snapshot_data['summary']
        
        print(f"\n{'='*80}")
        print(f"COMPREHENSIVE HISTORICAL NEWS SNAPSHOT COMPLETE")
        print(f"{'='*80}")
        print(f"Target Date: {snapshot_data['date']}")
        print(f"Snapshot Created: {snapshot_data['snapshot_created']}")
        print(f"")
        print(f"COLLECTION STATISTICS:")
        print(f"  Total Articles Collected: {summary['total_articles']}")
        print(f"  Total Words Collected: {summary['total_words']:,}")
        print(f"  Average Words per Article: {summary['total_words'] // max(summary['total_articles'], 1):,}")
        print(f"  Search Terms Processed: {summary['search_terms_processed']}")
        print(f"  Search Terms with Results: {summary['search_terms_with_results']}")
        print(f"  Success Rate: {(summary['search_terms_with_results'] / max(summary['search_terms_processed'], 1) * 100):.1f}%")
        print(f"")
        print(f"SOURCES ({len(summary['sources'])}):")
        for source in sorted(summary['sources'])[:20]:  # Show top 20
            print(f"  - {source}")
        if len(summary['sources']) > 20:
            print(f"  ... and {len(summary['sources']) - 20} more")
        print(f"")
        print(f"SEARCH ENGINES USED:")
        for engine in summary['search_engines']:
            print(f"  - {engine}")
    
    def run_comprehensive_scrape(self, target_date: str, max_articles_per_term: int = 10):
        """Run the complete comprehensive scraping process"""
        try:
            # Validate date
            datetime.strptime(target_date, "%Y-%m-%d")
            
            print("COMPREHENSIVE HISTORICAL NEWS SCRAPER")
            print("=" * 80)
            print(f"Target Date: {target_date}")
            print(f"Search Terms: {len(self.search_terms)}")
            print(f"Max Articles per Term: {max_articles_per_term}")
            print(f"Estimated Total Articles: {len(self.search_terms) * max_articles_per_term}")
            print("=" * 80)
            
            # Setup Selenium
            self.setup_selenium_driver()
            
            # Create snapshot
            snapshot_data = self.create_comprehensive_snapshot(target_date, max_articles_per_term)
            
            # Save results
            filename = self.save_comprehensive_snapshot(snapshot_data)
            
            # Print summary
            self.print_comprehensive_summary(snapshot_data)
            
            print(f"\nFiles saved:")
            print(f"  Main data: {filename}")
            print(f"  Summary: summary_{filename}")
            
            return filename
            
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD")
            return None
        except Exception as e:
            print(f"Error during comprehensive scraping: {e}")
            return None
        finally:
            if self.driver:
                self.driver.quit()

# Usage
if __name__ == "__main__":
    scraper = AdvancedHistoricalNewsScraper()
    
    print("ADVANCED HISTORICAL NEWS SCRAPER")
    print("=" * 50)
    print("This tool will comprehensively scrape news from multiple sources")
    print("for any historical date using various search engines and methods.")
    print()
    
    target_date = input("Enter the historical date (YYYY-MM-DD): ").strip()
    
    if target_date:
        max_articles = input("Max articles per search term (default 10): ").strip()
        max_articles = int(max_articles) if max_articles.isdigit() else 10
        
        print(f"\nStarting comprehensive scrape for {target_date}...")
        print(f"This may take 30-60 minutes depending on the date and available content.")
        print("Press Ctrl+C to stop at any time.\n")
        
        try:
            filename = scraper.run_comprehensive_scrape(target_date, max_articles)
            if filename:
                print(f"\n🎉 Comprehensive historical snapshot completed!")
                print(f"📁 Data saved to: {filename}")
        except KeyboardInterrupt:
            print("\n⏹️  Scraping stopped by user.")
        except Exception as e:
            print(f"\n❌ Error: {e}")
    else:
        print("No date provided.")