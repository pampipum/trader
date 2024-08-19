import anthropic
import logging
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

def analyze_with_claude(data, system_prompt):
    # Get the API key from environment variable
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found in environment variables")

    client = anthropic.Client(api_key=api_key)
    try:    
        logger.info("Preparing message for Claude analysis")
        
        if 'macro_assets' in data and 'trade_assets' in data:
            # This is market analysis data
            message = f"""
Here's the compiled market data for analysis:
Macro Assets:
{json.dumps(data['macro_assets'], indent=2)}

Trade Assets:
{json.dumps(data['trade_assets'], indent=2)}

Failed Analyses:
{json.dumps(data['failed_analyses'], indent=2)}

Please provide a comprehensive market analysis based on this data.
"""
        else:
            # This is individual asset data
            message = f"""
Here's the compiled chart data, price action information, and technical indicator information for analysis:
{json.dumps(data, indent=2)}

Please provide your analysis based on this data, focusing on price action, technical indicators, and potential trading strategies.
"""
        
        logger.info("Sending request to Claude API")
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            #model="claude-3-5-sonnet-20240620",            
            max_tokens=4000,
            temperature=1,
            system=system_prompt,
            messages=[{"role": "user", "content": message}]
        )
        
        logger.info("Received response from Claude API")
        content = response.content[0].text if isinstance(response.content, list) else response.content
        
        logger.info("Analysis completed successfully")
        return content
    except Exception as e:
        logger.error(f"Error in analyze_with_claude: {str(e)}")
        raise