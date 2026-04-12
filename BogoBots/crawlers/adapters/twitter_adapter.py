# BogoBots/crawlers/adapters/twitter_adapter.py
from datetime import datetime
from typing import List, Optional

from BogoBots.crawlers.news_crawler import BaseNewsCrawler, RawNewsItem


class TwitterAdapter(BaseNewsCrawler):
    """
    Adapter for Twitter/X API.
    Fetches tweets from specific accounts relevant to AI/ML.
    
    Requires Twitter API v2 credentials in config:
    - bearer_token
    - (optional) api_key, api_secret, access_token, access_secret
    """
    
    source_type = 'twitter'
    
    def _get_tweepy_client(self):
        """Initialize Tweepy client with credentials from config"""
        try:
            import tweepy
        except ImportError:
            raise ImportError("tweepy is required for Twitter adapter. Install: pip install tweepy")
        
        bearer_token = self.config.get('bearer_token')
        if not bearer_token:
            raise ValueError("Twitter bearer_token required in config")
        
        return tweepy.Client(
            bearer_token=bearer_token,
            wait_on_rate_limit=True
        )
    
    def fetch_new_items(self, since: datetime) -> List[RawNewsItem]:
        """
        Fetch tweets from configured accounts after 'since' timestamp.
        """
        items = []
        
        # Get accounts to track from config
        accounts = self.config.get('accounts', [])
        if isinstance(accounts, str):
            accounts = accounts.split(',')
        
        if not accounts:
            print(f"No accounts configured for source: {self.news_source.name}")
            return items
        
        max_results = self.config.get('max_results', 10)
        exclude_replies = self.config.get('exclude_replies', True)
        exclude_retweets = self.config.get('exclude_retweets', False)
        min_likes = self.config.get('min_likes', 10)  # Filter low-engagement tweets
        
        try:
            client = self._get_tweepy_client()
            
            for account in accounts:
                account = account.strip().lstrip('@')
                
                try:
                    # Get user ID
                    user = client.get_user(username=account)
                    if not user.data:
                        print(f"User not found: {account}")
                        continue
                    
                    user_id = user.data.id
                    
                    # Fetch tweets
                    tweets = client.get_users_tweets(
                        id=user_id,
                        max_results=max_results,
                        exclude=['replies'] if exclude_replies else [],
                        tweet_fields=['created_at', 'public_metrics', 'entities', 'attachments'],
                        expansions=['attachments.media_keys'],
                        media_fields=['url', 'preview_image_url']
                    )
                    
                    if not tweets.data:
                        continue
                    
                    # Get media lookup
                    media_lookup = {}
                    if tweets.includes and 'media' in tweets.includes:
                        for media in tweets.includes['media']:
                            media_lookup[media.media_key] = media
                    
                    for tweet in tweets.data:
                        # Parse timestamp
                        tweet_time = tweet.created_at
                        if tweet_time and tweet_time < since:
                            continue
                        
                        # Check engagement
                        metrics = tweet.public_metrics or {}
                        likes = metrics.get('like_count', 0)
                        if likes < min_likes:
                            continue
                        
                        # Build URL
                        tweet_url = f"https://twitter.com/{account}/status/{tweet.id}"
                        
                        # Get images
                        image_urls = []
                        if tweet.attachments and 'media_keys' in tweet.attachments:
                            for media_key in tweet.attachments['media_keys']:
                                media = media_lookup.get(media_key)
                                if media:
                                    url = media.url or media.preview_image_url
                                    if url:
                                        image_urls.append(url)
                        
                        # Build content
                        content = tweet.text
                        if tweet.entities:
                            # Handle URLs, mentions, hashtags
                            urls = tweet.entities.get('urls', [])
                            for url_info in urls:
                                expanded = url_info.get('expanded_url', '')
                                display = url_info.get('display_url', '')
                                if expanded:
                                    content = content.replace(url_info['url'], f"[{display}]({expanded})")
                        
                        # Format as markdown
                        md_content = f"""**@{account}** posted:

{content}

[Likes: {likes} | Retweets: {metrics.get('retweet_count', 0)} | Replies: {metrics.get('reply_count', 0)}]
"""
                        
                        item = RawNewsItem(
                            external_id=str(tweet.id),
                            title=f"Tweet from @{account}: {tweet.text[:80]}...",
                            url=tweet_url,
                            author=f"@{account}",
                            published_at=tweet_time or since,
                            content_raw=md_content,
                            image_urls=image_urls
                        )
                        items.append(item)
                        
                except Exception as e:
                    print(f"Error fetching tweets for {account}: {e}")
                    continue
                    
        except ImportError as e:
            print(f"Twitter adapter error: {e}")
        except Exception as e:
            print(f"Error in Twitter adapter: {e}")
        
        return items
    
    def parse_content(self, raw_data) -> str:
        """Content is already formatted"""
        return str(raw_data)
