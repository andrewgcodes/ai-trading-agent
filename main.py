import streamlit as st
import time
import re
import json
import requests
import yfinance as yf
from exa_py import Exa
import anthropic
import os

# ----------------------
# Configuration / API Keys
# ----------------------
ANTHROPIC_API_KEY = os.environ['ANTHROPIC_API_KEY']
PERPLEXITY_API_KEY = os.environ['PERPLEXITY_API_KEY']
EXA_API_KEY = os.environ['EXA_API_KEY']

MODEL_NAME = "claude-3-5-sonnet-20241022"
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
exa = Exa(api_key=EXA_API_KEY)

def fetch_yahoo_finance(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="7d")
        if hist.empty:
            return f"Yahoo Finance: No market data found for {ticker} in the last week."
        return f"Yahoo Finance: Last week's market data for {ticker}:\n{hist.to_string()}"
    except Exception as e:
        return f"Error fetching Yahoo Finance data: {e}"

def fetch_perplexity_news(ticker):
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": "Be precise and concise."},
            {"role": "user", "content": f"Provide the latest news headlines and summaries for {ticker}."}
        ],
        "max_tokens": 500,
        "temperature": 0.2,
        "top_p": 0.9,
        "top_k": 0,
        "stream": False,
        "presence_penalty": 0,
        "frequency_penalty": 1,
        "search_recency_filter": "week"
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return f"Perplexity News: {answer}"
        else:
            return f"Error fetching Perplexity news: {response.text}"
    except Exception as e:
        return f"Exception in Perplexity API call: {e}"

def fetch_exa_search(ticker, start_date, end_date, num_results=5):
    try:
        query = f"financial news and reports on {ticker}"
        result = exa.search_and_contents(
            query,
            text=True,
            num_results=num_results,
            start_published_date=start_date,
            end_published_date=end_date,
            include_text=[ticker]
        )
        results = result.results
        if results:
            entries = []
            for res in results:
                title = getattr(res, "title", None)
                if not title:
                    title = getattr(res, "url", "No title")
                content = getattr(res, "text", None)
                if not content:
                    content = getattr(res, "text", "No content available.")
                published_date = getattr(res, "published_date", "N/A")
                entry = (
                    f"Title: {title}\n"
                    f"Published: {published_date}\n"
                    f"Content: {content}"
                )
                entries.append(entry)
            return f"Exa Search: Found {len(entries)} results:\n" + "\n\n".join(entries)
        else:
            return f"Exa Search: No results found for {ticker} in the given period."
    except Exception as e:
        return f"Error fetching Exa Search results: {e}"

def calculate(expression):
    expression = re.sub(r'[^0-9+\-*/().]', '', expression)
    try:
        result = eval(expression)
        return str(result)
    except Exception:
        return "Error: Invalid expression"

tools = [
    {
        "name": "yahoo_finance",
        "description": (
            "Fetches current stock data for a given ticker from Yahoo Finance. "
            "Provides real-time pricing, volume, and market trends. "
            "Use this tool when you need quantitative data about a stock."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "The stock ticker symbol (e.g., TSLA)."}
            },
            "required": ["ticker"]
        }
    },
    {
        "name": "perplexity_news",
        "description": (
            "Fetches recent news and financial reports for a given stock ticker using the Perplexity API. "
            "Use this tool to retrieve the latest headlines and summaries related to the stock."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "The stock ticker symbol (e.g., TSLA)."}
            },
            "required": ["ticker"]
        }
    },
    {
        "name": "exa_search",
        "description": (
            "Performs a detailed search for financial news and reports on a given stock ticker using the Exa AI Search API. "
            "Use this tool when you need to fetch comprehensive search results, including reports within a specific date range."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "The stock ticker symbol (e.g., TSLA)."},
                "start_date": {"type": "string", "description": "The start date for the search in ISO format."},
                "end_date": {"type": "string", "description": "The end date for the search in ISO format."},
                "num_results": {"type": "integer", "description": "The number of search results to return.", "default": 5}
            },
            "required": ["ticker", "start_date", "end_date"]
        }
    },
    {
        "name": "calculator",
        "description": (
            "A simple calculator that performs basic arithmetic operations. "
            "Use this tool to perform any necessary calculations (e.g., computing ratios or adjusting numbers)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "The mathematical expression to evaluate (e.g., '2 + 3 * 4')."}
            },
            "required": ["expression"]
        }
    }
]

def process_tool_call(tool_name, tool_input):
    if tool_name == "yahoo_finance":
        return fetch_yahoo_finance(tool_input["ticker"])
    elif tool_name == "perplexity_news":
        return fetch_perplexity_news(tool_input["ticker"])
    elif tool_name == "exa_search":
        ticker = tool_input["ticker"]
        start_date = tool_input["start_date"]
        end_date = tool_input["end_date"]
        num_results = tool_input.get("num_results", 5)
        return fetch_exa_search(ticker, start_date, end_date, num_results)
    elif tool_name == "calculator":
        return calculate(tool_input["expression"])
    else:
        return f"Error: Unknown tool {tool_name}"

def run_conversation(ticker, start_date, end_date, output_container):
    conversation = [
        {
            "role": "user",
            "content": (
                f"Please provide a comprehensive investment assessment for {ticker}. "
                "Include an analysis of the current stock data, recent news, and any additional financial reports if available. "
                "Use the available tools as needed: use 'yahoo_finance' for current market data, 'perplexity_news' for recent news, "
                "'exa_search' for a detailed search over a specified date range, and 'calculator' for any necessary arithmetic. "
                "Make sure to use the calculator at least two times to generate accurate numerical results."
            )
        }
    ]
    system_prompt = (
        "You are an investment analysis assistant. Your task is to provide a comprehensive investment assessment for a given stock. "
        "Use the following tools as needed:\n\n"
        "1. yahoo_finance: To get real-time stock data (price, volume, trends).\n"
        "2. perplexity_news: To fetch recent news headlines and financial reports about the stock.\n"
        "3. exa_search: To perform an in-depth search for financial news and detailed reports within a specified date range.\n"
        "4. calculator: To perform any arithmetic calculations required during your analysis.\n\n"
        "When you are done, stop using tools and just provide your final verdict."
    )

    progress_bar = st.progress(0)
    progress = 0

    for i in range(10):
        output_container.markdown(f"#### Iteration {i+1}")
        response = client.messages.create(
            model=MODEL_NAME,
            system=system_prompt,
            max_tokens=4096,
            tools=tools,
            messages=conversation
        )

        conversation.append({
            "role": "assistant",
            "content": response.content
        })
        output_container.markdown("**Assistant response:**")
        output_container.write(response.content)

        tool_called = False
        blocks = []
        if isinstance(response.content, list):
            blocks = response.content
        else:
            try:
                blocks = json.loads(response.content)
            except Exception:
                blocks = []

        for block in blocks:
            if hasattr(block, "type") and block.type == "tool_use":
                tool_called = True
                tool_name = block.name
                tool_input = block.input
                output_container.markdown(f"**[Agent requests tool call]** `{tool_name}` with input: `{json.dumps(tool_input)}`")
                result = process_tool_call(tool_name, tool_input)
                output_container.markdown(f"**[Tool '{tool_name}' result]**")
                output_container.write(result)
                tool_result_message = {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result
                        }
                    ]
                }
                conversation.append(tool_result_message)
                break 

        progress += 10
        progress_bar.progress(min(progress, 100))
        time.sleep(1)

        if not tool_called:
            final_answer = ""
            if isinstance(response.content, list):
                for block in response.content:
                    if hasattr(block, "type") and block.type == "text":
                        final_answer += block.text
            else:
                final_answer = response.content
            output_container.markdown("### Final Investment Assessment")
            output_container.write(final_answer)
            break
    else:
        output_container.write("Maximum iterations reached without a finalized response.")

st.title("Eigensurance AI Hedge Fund Agent")
st.subheader("💰🤖 for treehacks 2025. not financial advice!")
st.sidebar.header("Input Parameters")a
ticker = st.sidebar.text_input("Enter the stock ticker (e.g., TSLA)", value="TSLA")
start_date = st.sidebar.text_input("Enter start date for news search (ISO format)", value="2024-01-15T08:00:00.000Z")
end_date = st.sidebar.text_input("Enter end date for news search (ISO format)", value="2025-02-15T07:59:59.999Z")

if st.sidebar.button("Run Investment Analysis"):
    output_container = st.container()
    with st.spinner("Running analysis..."):
        run_conversation(ticker, start_date, end_date, output_container)


