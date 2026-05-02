import requests
from openai import OpenAI

OPENROUTER_MODEL_PRICES = None

def get_model_price(model_name, provider):
    global OPENROUTER_MODEL_PRICES
    if provider in ['OpenRouter', 'OpenAI']:
        if OPENROUTER_MODEL_PRICES is None:
            try:
                # get data from OpenRouter API
                response = requests.get('https://openrouter.ai/api/v1/models')
                response.raise_for_status()  # Raises stored HTTPError, if one occurred.
                response = response.json()
                OPENROUTER_MODEL_PRICES = dict()
                for model_info in response['data']:
                    OPENROUTER_MODEL_PRICES[model_info['id']] = model_info['pricing']
            except requests.HTTPError as http_err:
                print(f'HTTP error occurred: {http_err}')
                return None
            except Exception as err:
                print(f'Other error occurred: {err}')
                return None
        if model_name in OPENROUTER_MODEL_PRICES:
            price_dict = OPENROUTER_MODEL_PRICES[model_name]
            # escape for LaTex syntax
            result = {
                'input': f"\\${float(price_dict['prompt'])*1000000:.2f}/M tkns",
                'output': f"\\${float(price_dict['completion'])*1000000:.2f}/M tkns",
            }
            if float(price_dict.get('image', 0)) > 0:
                result['image'] = f"\\${float(price_dict.get('image', 0))*1000:.2f}/K imgs"
            if provider == 'OpenRouter':
                result['your credit'] = '[link](https://openrouter.ai/credits)'
            return result
        return None
    elif provider in ['Qwen', 'Qwen Open Source']:
        # TODO: get data from Qwen API
        return {
            'Price detail': '[link](https://dashscope.console.aliyun.com/billing)',
            'your billing': '[link](https://usercenter2.aliyun.com/home)',
        }


# =================== AI Hub LLM Utilities ===================

import json
from typing import Optional, Dict, Any, Callable
from datetime import datetime, timedelta, timezone

def get_llm_client(model_name: str, api_key: Optional[str] = None):
    """
    Get an OpenAI-compatible client (official OpenAI package).
    Uses OpenRouter by default.
    """
    import streamlit as st
    
    # Default to OpenRouter
    base_url = "https://openrouter.ai/api/v1"
    default_api_key = st.secrets.get('open_router_key', '')
    
    # Check if it's a Qwen model (uses different base URL)
    # if 'qwen' in model_name.lower():
    #     base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    #     default_api_key = st.secrets.get('DASHSCOPE_API_KEY', '')
    
    # # Check if it's an OpenAI official model
    # if model_name.startswith('gpt-') or model_name.startswith('o1'):
    #     base_url = "https://api.openai.com/v1"
    #     default_api_key = st.secrets.get('OPENAI_API_KEY', '')
    
    api_key = api_key or default_api_key
    
    return OpenAI(api_key=api_key, base_url=base_url)


def _chat_completion(model_name: str, prompt: str, max_tokens: int = 50000, temperature: float = 0.3):
    print(f"Calling {model_name} with prompt: {prompt}")
    client = get_llm_client(model_name)
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": "You are a concise and accurate AI news assistant."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    print(response)
    content = response.choices[0].message.content or ""
    usage = response.usage
    input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    if input_tokens == 0:
        input_tokens = len(prompt) // 4
    if output_tokens == 0:
        output_tokens = len(content) // 4
    return content.strip(), input_tokens, output_tokens


def _summarization_content_for_item(item, fallback_content: str) -> str:
    content = fallback_content or ""
    if content.strip():
        return content

    episode_description = getattr(item, "episode_description", None) or ""
    if episode_description.strip():
        return episode_description

    return content


def summarize_news_item(item_id: int, title: str, content: str, 
                        model_name: str = 'deepseek-chat') -> Dict[str, Any]:
    """
    Generate an LLM summary for a news item and track token usage.
    """
    from BogoBots.database.session import get_session
    from BogoBots.models.news_item import NewsItem
    from BogoBots.models.news_hub_config import NewsHubConfig
    
    # Get the prompt template from config
    session = get_session()
    try:
        config = NewsHubConfig.get_or_create(session)
        prompt_template = config.summary_prompt_template
        item = session.query(NewsItem).filter_by(id=item_id).first()
        content = _summarization_content_for_item(item, content) if item else content
    finally:
        session.close()
    
    # Prepare prompt
    max_content_chars = 10000 
    if len(content) > max_content_chars:
        content = content[:max_content_chars] + "..."
    
    prompt = prompt_template.format(title=title, content=content)
    
    # Call LLM
    summary, input_tokens, output_tokens = _chat_completion(
        model_name=model_name,
        prompt=prompt,
        temperature=0.3,
    )
    
    # Update the news item with summary and token info
    session = get_session()
    try:
        item = session.query(NewsItem).filter_by(id=item_id).first()
        if item:
            item.content_summary = summary
            item.summary_model = model_name
            item.summary_tokens_input = input_tokens
            item.summary_tokens_output = output_tokens
            item.status = 'processed'
            session.commit()
    finally:
        session.close()
    
    return {
        'summary': summary,
        'model': model_name,
        'input_tokens': input_tokens,
        'output_tokens': output_tokens
    }


def generate_podcast_transcript(
    item_id: int,
    model_name: Optional[str] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    Generate a podcast transcript/summary from the episode audio and save it to content_raw.
    Public wrapper kept here for UI callers; podcast-specific implementation lives in podcast_utils.
    """
    import streamlit as st
    from BogoBots.utils.podcast_utils import generate_podcast_transcript_for_item

    api_key = st.secrets.get('open_router_key', '')
    if not api_key:
        raise RuntimeError("Missing OpenRouter API key in st.secrets['open_router_key']")
    return generate_podcast_transcript_for_item(
        item_id=item_id,
        api_key=api_key,
        model_name=model_name,
        progress_callback=progress_callback,
    )


def extract_metadata(item_id: int, title: str, content: str,
                     model_name: str = 'deepseek-chat') -> Dict[str, Any]:
    """
    Extract structured metadata from a news item using LLM.
    """
    from BogoBots.database.session import get_session
    from BogoBots.models.news_item import NewsItem
    
    prompt = f"""Analyze the following AI news article and extract structured information.

Title: {title}
Content: {content[:3000]}...

Please provide a JSON response with the following fields:
{{
    "entities": ["list of companies, people, models mentioned"],
    "tags": ["AI", "ML", "specific topics like 'transformer', 'agent', etc."],
    "news_type": "one of: model_release, research_paper, company_announcement, framework_update, opinion, other",
    "technical_level": "beginner|intermediate|advanced",
    "relevance_score": 0.0-1.0 (how relevant to AI/ML practitioners),
    "key_insight": "one sentence summary of the main takeaway"
}}

JSON:"""
    
    content, _, _ = _chat_completion(
        model_name=model_name,
        prompt=prompt,
        temperature=0.2,
    )
    
    # Try to parse JSON response
    try:
        content = content.strip()
        # Extract JSON if wrapped in code blocks
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0]
        elif '```' in content:
            content = content.split('```')[1].split('```')[0]
        
        metadata = json.loads(content)
        
        # Update news item
        session = get_session()
        try:
            item = session.query(NewsItem).filter_by(id=item_id).first()
            if item:
                item.llm_extracted_metadata = metadata
                item.relevance_score = metadata.get('relevance_score', 0.5)
                session.commit()
        finally:
            session.close()
        
        return metadata
        
    except json.JSONDecodeError:
        return {
            'error': 'Failed to parse LLM response as JSON',
            'raw_response': content
        }


def generate_report_summary(news_items: list, model_name: str = 'deepseek-chat') -> str:
    """
    Generate an overall summary for a report from a collection of news items.
    """
    from BogoBots.database.session import get_session
    from BogoBots.models.news_hub_config import NewsHubConfig
    
    # Get prompt template
    session = get_session()
    try:
        config = NewsHubConfig.get_or_create(session)
        prompt_template = config.report_prompt_template
    finally:
        session.close()
    
    # Format news items for prompt
    items_text = "\n\n".join([
        f"{i+1}. {item.get('title', item.title)}\n   Summary: {item.get('content_summary', item.content_summary)[:200]}..."
        for i, item in enumerate(news_items[:20])  # Limit to 20 items
    ])
    
    prompt = prompt_template.format(news_items=items_text)
    
    content, _, _ = _chat_completion(
        model_name=model_name,
        prompt=prompt,
        temperature=0.3,
    )
    return content


def get_news_token_usage_summary(days: int = 30) -> Dict[str, Any]:
    """
    Get a summary of LLM token usage for news processing.
    """
    from BogoBots.database.session import get_session
    from BogoBots.models.news_item import NewsItem
    from sqlalchemy import func
    
    session = get_session()
    try:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Get summary stats
        summary_result = session.query(
            func.sum(NewsItem.summary_tokens_input),
            func.sum(NewsItem.summary_tokens_output),
            func.count(NewsItem.id)
        ).filter(
            NewsItem.crawled_at >= since,
            NewsItem.summary_tokens_input.isnot(None)
        ).first()
        
        total_input = summary_result[0] or 0
        total_output = summary_result[1] or 0
        count = summary_result[2] or 0
        
        # Get per-model breakdown
        model_breakdown = session.query(
            NewsItem.summary_model,
            func.sum(NewsItem.summary_tokens_input),
            func.sum(NewsItem.summary_tokens_output),
            func.count(NewsItem.id)
        ).filter(
            NewsItem.crawled_at >= since,
            NewsItem.summary_model.isnot(None)
        ).group_by(NewsItem.summary_model).all()
        
        return {
            'period_days': days,
            'total_items': count,
            'total_input_tokens': total_input,
            'total_output_tokens': total_output,
            'estimated_cost': _estimate_cost(total_input, total_output),
            'per_model': [
                {
                    'model': model,
                    'input_tokens': inp or 0,
                    'output_tokens': out or 0,
                    'count': cnt
                }
                for model, inp, out, cnt in model_breakdown
            ]
        }
    finally:
        session.close()


def _estimate_cost(input_tokens: int, output_tokens: int, 
                   input_price_per_1m: float = 0.5,
                   output_price_per_1m: float = 1.5) -> float:
    """
    Rough cost estimation based on typical OpenRouter prices.
    """
    input_cost = (input_tokens / 1_000_000) * input_price_per_1m
    output_cost = (output_tokens / 1_000_000) * output_price_per_1m
    return round(input_cost + output_cost, 4)
