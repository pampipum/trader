import openai
import os
import json
import logging
from datetime import datetime, date

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load your API key from an environment variable or secret management service
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def default_serializer(obj):
    if isinstance(obj, (datetime, date)):
        return obj.replace(tzinfo=None).isoformat()  # Remove timezone info
    if isinstance(obj, (int, float)):
        return float(obj)
    return str(obj)

def analyze_with_openai(compiled_data, system_prompt):
    try:
        logger.info("Preparing message for OpenAI analysis")
        
        # Ensure compiled_data is JSON serializable
        serializable_data = json.loads(json.dumps(compiled_data, default=default_serializer))
        
        message = f"""
Here's the compiled chart data, price action information, and technical indicator information for analysis:
{json.dumps(serializable_data, indent=2)}

Please provide your analysis based on this data, focusing on price action, technical indicators, and potential trading strategies. Format your response according to the following structure:

# Multi-Timeframe Analysis: {compiled_data['symbol']}

## 1. Price Action Analysis

### a) Candlestick Patterns
[Analysis of significant candlestick patterns for 4h, Daily, and Weekly]

### b) Chart Patterns
[Analysis of chart patterns for 4h, Daily, and Weekly]

### c) Market Structure
[Analysis of market structure for 4h, Daily, and Weekly]

### d) Support and Resistance
[Analysis of key support and resistance levels based on price action]

### e) Price Action Momentum
[Analysis of price action momentum for 4h, Daily, and Weekly]

### f) Orderblocks and Liquidity
[Analysis of significant orderblocks and liquidity areas]

### g) Fibonacci Levels
[Analysis of key Fibonacci retracement and extension levels for 4h, Daily, and Weekly]

## 2. Trend Analysis

[4h, Daily, and Weekly trend analysis]

## 3. Indicator Analysis

### a) WaveTrend (WT_LB)

[WaveTrend analysis for 4h, Daily, and Weekly]

### b) Awesome Oscillator (AO)

[AO analysis for 4h, Daily, and Weekly]

### c) RSI

[RSI analysis for 4h, Daily, and Weekly]

### d) MA-X

[MA-X analysis for 4h, Daily, and Weekly]

### e) Bollinger Bands

[Bollinger Bands analysis]

### f) On-Balance Volume (OBV)

[OBV analysis for 4h, Daily, and Weekly]

### g) Average True Range (ATR)

[ATR analysis for 4h, Daily, and Weekly]

## 4. Multi-Timeframe Confluence

[Multi-timeframe confluence analysis, including price action, indicators, and Fibonacci levels]

## 5. Setup Quality Assessment: [Score]/10

[Explanation of setup quality, considering price action, indicators, and Fibonacci levels]

## 6. Directional Bias: [LONG/SHORT]

### Rationale for [Long/Short] Bias

[Rationale points, including price action, indicator analysis, and Fibonacci levels]

## 7. Additional Market Factors

### b) Fear and Greed Index

[Analysis of Fear and Greed Index]

### c) Order Book Analysis

[Analysis of order book data]

### d) Funding Rate

[Analysis of funding rate]

## 8. Detailed Trade Idea

### Entry

[Entry strategy based on price action, indicators, and Fibonacci levels]

### Stop Loss

[Stop loss strategy based on price action, technical levels, and Fibonacci levels]

### Take Profit Targets

[Take profit targets based on price action, technical levels, and Fibonacci extension levels]

### Risk Management

[Risk management strategies]

### Key Levels to Watch

[Key levels based on price action, indicators, and Fibonacci levels]

### Potential Catalysts for Improved Setup

[Potential catalysts]

## 9. Price Action and Indicator Confluence

[Analysis of how price action, indicators, and Fibonacci levels support or contradict each other]

## Conclusion

[Conclusion of the analysis, synthesizing price action, indicator insights, and Fibonacci level analysis]
"""

        response = client.chat.completions.create(
            #model="gpt-4o-mini",  # or another appropriate model
            model="gpt-4o",  # or another appropriate model
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            max_tokens=2000,
            n=1,
            temperature=0.7,
        )

        analysis = response.choices[0].message.content.strip()
        logger.info("OpenAI analysis completed successfully")
        return analysis
    except Exception as e:
        logger.error(f"Error in OpenAI analysis: {str(e)}")
        return f"Error in OpenAI analysis: {str(e)}"